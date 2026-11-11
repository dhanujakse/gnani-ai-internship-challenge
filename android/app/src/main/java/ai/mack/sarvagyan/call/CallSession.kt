package ai.mack.sarvagyan.call

import android.content.Context
import android.util.Log
import ai.mack.sarvagyan.data.ApiClient
import ai.mack.sarvagyan.data.AppSettings
import ai.mack.sarvagyan.data.CallInfo
import ai.mack.sarvagyan.data.SavedLine
import ai.mack.sarvagyan.data.SavedTranscript
import ai.mack.sarvagyan.data.TranscriptStore
import ai.mack.sarvagyan.data.bool
import ai.mack.sarvagyan.data.int
import ai.mack.sarvagyan.data.objOrNull
import ai.mack.sarvagyan.data.str
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.jsonPrimitive
import okhttp3.OkHttpClient
import org.webrtc.PeerConnection

enum class CallStatus { Connecting, WaitingForPeer, ConnectingAudio, Live, Reconnecting, Ended, Failed }
enum class PipelineState { Idle, Connecting, Ready, Reconnecting, Error }

data class ParticipantUi(val id: String, val name: String, val language: String, val avatar: String? = null, val muted: Boolean = false, val connected: Boolean = true)

data class Banner(val message: String, val retryId: String? = null, val severe: Boolean = false)

data class CallUiState(
    val status: CallStatus = CallStatus.Connecting,
    val call: CallInfo? = null,
    val me: ParticipantUi? = null,
    val peer: ParticipantUi? = null,
    val startedAtMs: Long? = null,
    val endedAtMs: Long? = null,
    val conversation: Conversation = Conversation(),
    val muted: Boolean = false,
    val translatedAudio: Boolean = true,
    val route: AudioRoute? = null,
    val routes: List<AudioRoute> = emptyList(),
    val originalVolume: Float = 0.35f,
    val subtitleScale: Float = 1f,
    val autoDetect: Boolean = false,
    val mediaConnected: Boolean = false,
    val quality: Quality = Quality.Unknown,
    val rttMs: Int? = null,
    val myPipeline: PipelineState = PipelineState.Idle,
    val banner: Banner? = null,
    val notice: String? = null,
    val endReason: String? = null,
    val micStreaming: Boolean = false,
    val unanswered: String? = null, // a ringing call that was declined, busy, no answer, or unavailable
    val unansweredDetail: String? = null,
)

/**
 * One active call. Owns the server socket, the WebRTC engine, the translated-audio player and the
 * mic pipeline, and exposes a single immutable [CallUiState] to the UI.
 */
class CallSession(
    private val context: Context,
    private val api: ApiClient,
    private val http: OkHttpClient,
    private val json: kotlinx.serialization.json.Json,
    private val transcripts: TranscriptStore,
    val info: CallInfo,
    private val settings: AppSettings,
    private var myLanguage: String,
) {
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.Default)
    private val _state = MutableStateFlow(
        CallUiState(call = info, translatedAudio = settings.translatedAudio, originalVolume = settings.originalVolume,
            subtitleScale = settings.subtitleScale, autoDetect = settings.autoDetect),
    )
    val state: StateFlow<CallUiState> = _state

    private val socket = CallSocket(http, json)
    private val gate = EchoGate()
    private val router: AudioRouter = AudioRouter(context) { r ->
        _state.update { it.copy(routes = r.available(), route = r.current()) }
    }
    private val player = TranslatedAudioPlayer { id ->
        gate.setPlaying(id != null, System.currentTimeMillis())
        _state.update { it.copy(conversation = it.conversation.withPlaying(id)) }
    }
    private val mic = MicPipeline(gate, System::currentTimeMillis, noiseReduction = settings.noiseReduction) { frame ->
        if (socket.sendAudio(frame) && !_state.value.micStreaming) _state.update { it.copy(micStreaming = true) }
    }
    private var rtc: WebRtcEngine? = null
    private var iceServers: List<PeerConnection.IceServer>? = null
    private var pendingOffer: Boolean? = null // initiator flag received before ICE servers
    private val pendingSignals = mutableListOf<JsonObject>()
    private var myId: String? = null
    private var ttsId: String? = null
    private var socketJob: Job? = null
    private var ended = false
    private var reconnectAttempt = 0
    private var everConnected = false // after the first connection, re-offers restart ICE (network change)

    fun start(initialRoute: AudioRoute? = null) {
        router.begin()
        val avail = router.available()
        _state.update { it.copy(routes = avail) }
        val chosen = initialRoute ?: if (settings.speakerOn) AudioRoute.Speaker else AudioRoute.Earpiece
        if (avail.contains(chosen)) {
            router.select(chosen)
        } else if (avail.isNotEmpty()) {
            router.select(avail.first())
        } else {
            router.select(chosen)
        }
        _state.update { it.copy(route = router.current()) }
        player.volume = 1f
        Log.i("CallLifecycle", "state=connecting callId=${info.callId} route=${router.current()}")
        connectSocket()
        scope.launch { // stats + keepalive
            while (isActive) {
                delay(3000)
                rtc?.pollStats()
                socket.send(buildJsonObject { put("type", JsonPrimitive("ping")); put("t", JsonPrimitive(System.currentTimeMillis())) })
            }
        }
    }

    private fun connectSocket() {
        socketJob?.cancel()
        socketJob = scope.launch {
            val token = api.freshToken() ?: return@launch fail("Please sign in again.")
            socket.connect(api.webSocketUrl(info.callId), token).collect { ev -> onSocket(ev) }
        }
    }

    private fun hello() = buildJsonObject {
        put("type", JsonPrimitive("hello"))
        put("language", JsonPrimitive(myLanguage))
        put("auto_detect", JsonPrimitive(_state.value.autoDetect))
        settings.voice?.let { put("voice", JsonPrimitive(it)) }
        put("speed", JsonPrimitive(settings.speed))
        put("translate_audio", JsonPrimitive(_state.value.translatedAudio))
        put("muted", JsonPrimitive(_state.value.muted))
    }

    private fun onSocket(ev: SocketEvent) {
        when (ev) {
            SocketEvent.Open -> {
                reconnectAttempt = 0
                socket.send(hello())
                _state.update { it.copy(banner = null) }
            }
            is SocketEvent.Message -> onMessage(ev.json)
            is SocketEvent.Audio -> if (ttsId != null) player.write(ev.data)
            is SocketEvent.Closed -> when (ev.code) {
                4401 -> fail("Your sign-in expired. Please sign in again.")
                4404 -> fail("This call has ended or the invitation is no longer valid.")
                else -> if (!ended) reconnect()
            }
            is SocketEvent.Failure -> when (ev.httpCode) {
                401 -> fail("Your sign-in expired. Please sign in again.")
                else -> if (!ended) reconnect()
            }
        }
    }

    private fun reconnect() {
        if (ended) return
        reconnectAttempt++
        if (reconnectAttempt > 6) return fail("Lost connection to the server.")
        _state.update { it.copy(status = CallStatus.Reconnecting, banner = Banner("Connection lost — reconnecting…")) }
        scope.launch {
            delay(minOf(1000L shl (reconnectAttempt - 1), 8000L))
            if (!ended) connectSocket()
        }
    }

    private fun onMessage(m: JsonObject) {
        when (m.str("type")) {
            "joined" -> {
                val you = m.objOrNull("you")
                myId = you?.str("user_id")
                val peer = m.objOrNull("peer")?.let { participant(it) }
                val nextStatus = if (peer?.connected == true) CallStatus.ConnectingAudio else CallStatus.WaitingForPeer
                Log.i("CallLifecycle", "state=connecting callId=${info.callId} socket=joined status=$nextStatus peerConnected=${peer?.connected == true}")
                _state.update {
                    it.copy(
                        me = you?.let { y -> participant(y) },
                        peer = peer,
                        status = nextStatus,
                    )
                }
            }
            "ice_servers" -> {
                iceServers = WebRtcEngine.iceServers(m["ice_servers"] as? JsonArray ?: JsonArray(emptyList()))
                ensureRtc()
                pendingOffer?.let { offerIfInitiator(it) }
                pendingOffer = null
                synchronized(pendingSignals) {
                    pendingSignals.forEach { rtc?.onRemoteSignal(it) }
                    pendingSignals.clear()
                }
            }
            "peer_joined" -> {
                val initiator = m.bool("initiator") ?: false
                Log.i("CallLifecycle", "state=connecting callId=${info.callId} peer_joined initiator=$initiator")
                _state.update {
                    it.copy(peer = m.objOrNull("peer")?.let { p -> participant(p) },
                        status = if (it.mediaConnected) CallStatus.Live else CallStatus.ConnectingAudio,
                        startedAtMs = it.startedAtMs ?: System.currentTimeMillis(), banner = null)
                }
                if (rtc?.started == true) offerIfInitiator(initiator) else pendingOffer = initiator
            }
            "peer_reconnecting" -> _state.update { it.copy(banner = Banner("${it.peer?.name ?: "The other person"} lost connection — waiting for them…")) }
            "peer_left" -> {
                val reason = if (m.str("reason") == "left") "${_state.value.peer?.name ?: "The other person"} ended the call." else "The other person's connection was lost."
                end(reason, notifyServer = true)
            }
            "signal" -> {
                val payload = m.objOrNull("payload") ?: return
                if (rtc?.started == true) rtc?.onRemoteSignal(payload) else synchronized(pendingSignals) { pendingSignals.add(payload) }
            }
            "pipeline" -> if (m.str("speaker_id") == myId) {
                val p = when (m.str("stt")) {
                    "connecting" -> PipelineState.Connecting
                    "ready" -> PipelineState.Ready
                    "reconnecting" -> PipelineState.Reconnecting
                    "error" -> PipelineState.Error
                    else -> PipelineState.Idle
                }
                _state.update { it.copy(myPipeline = p) }
            }
            "speech_activity" -> {
                val who = m.str("speaker_id") ?: return
                val active = m.bool("active") ?: false
                _state.update { it.copy(conversation = it.conversation.withSpeech(who, active)) }
            }
            "utterance" -> {
                val ev = parseUtterance(m) ?: return
                val me = myId ?: return
                _state.update { it.copy(conversation = it.conversation.apply(ev, me, System.currentTimeMillis())) }
            }
            "tts_start" -> {
                ttsId = m.str("id")
                ttsId?.let { player.start(it) }
            }
            "tts_end" -> {
                m.str("id")?.let { player.end(it) }
                ttsId = null
            }
            "participant" -> {
                val p = m.objOrNull("participant")?.let { participant(it) } ?: return
                _state.update { if (p.id == myId) it.copy(me = p) else it.copy(peer = p) }
            }
            "error" -> {
                val scopeName = m.str("scope")
                val msg = m.str("message") ?: "Something went wrong."
                val text = when (scopeName) {
                    "stt" -> "Speech recognition: $msg"
                    "tts" -> "Translated voice unavailable — subtitles still work."
                    "translation" -> "Translation: $msg"
                    else -> msg
                }
                _state.update { it.copy(banner = Banner(text, severe = m.bool("retryable") == false && scopeName == "stt")) }
            }
            "notice" -> _state.update { it.copy(notice = m.str("message")) }
        }
    }

    private fun participant(o: JsonObject) = ParticipantUi(
        id = o.str("user_id") ?: "", name = o.str("name") ?: "Guest", language = o.str("language") ?: "",
        avatar = o.str("avatar"), muted = o.bool("muted") ?: false, connected = o.bool("connected") ?: true,
    )

    private fun parseUtterance(m: JsonObject): UtteranceEvent? {
        val metrics = (m["metrics"] as? JsonObject)?.mapNotNull { (k, v) -> (v as? JsonPrimitive)?.content?.toDoubleOrNull()?.let { k to it.toInt() } }?.toMap().orEmpty()
        return UtteranceEvent(
            id = m.str("id") ?: return null, speakerId = m.str("speaker_id") ?: return null, seq = m.int("seq") ?: 0,
            stage = Stage.parse(m.str("stage")), rev = m.int("rev") ?: 0, original = m.str("original") ?: "",
            sourceLang = m.str("source_lang") ?: "", translation = m.str("translation"), targetLang = m.str("target_lang"),
            error = m.str("error"), metrics = metrics,
        )
    }

    private fun ensureRtc() {
        if (rtc != null) return
        val engine = WebRtcEngine(context, { data, rate, ch -> mic.onSamples(data, rate, ch) }, object : WebRtcEngine.Listener {
            override fun onLocalSignal(payload: JsonObject) {
                socket.send(buildJsonObject { put("type", JsonPrimitive("signal")); put("payload", payload) })
            }

            override fun onConnectionState(state: PeerConnection.PeerConnectionState) {
                when (state) {
                    PeerConnection.PeerConnectionState.CONNECTED -> {
                        everConnected = true
                        Log.i("CallLifecycle", "state=connected callId=${info.callId} peer=${_state.value.peer?.id?.take(8)}")
                        _state.update { it.copy(mediaConnected = true, status = CallStatus.Live, banner = null) }
                        router.reapply()
                        _state.update { it.copy(routes = router.available(), route = router.current()) }
                    }
                    PeerConnection.PeerConnectionState.DISCONNECTED -> _state.update {
                        it.copy(mediaConnected = false, banner = Banner("Call audio interrupted — recovering…"))
                    }
                    PeerConnection.PeerConnectionState.FAILED -> _state.update {
                        it.copy(mediaConnected = false, status = if (it.peer != null) CallStatus.Live else it.status,
                            banner = Banner("Direct audio could not connect (a TURN server may be needed on this network). Translated speech and subtitles still work."))
                    }
                    else -> Unit
                }
            }

            override fun onQuality(quality: Quality, rttMs: Int?) = _state.update { it.copy(quality = quality, rttMs = rttMs) }
            override fun onMicError(message: String) = _state.update { it.copy(banner = Banner(message, severe = true)) }
        })
        engine.setRemoteVolume(_state.value.originalVolume)
        engine.start(iceServers ?: emptyList())
        engine.setMuted(_state.value.muted)
        rtc = engine
    }

    private fun offerIfInitiator(initiator: Boolean) {
        if (initiator) rtc?.makeOffer(iceRestart = everConnected)
    }

    // --- user actions -----------------------------------------------------------------------
    fun setMuted(muted: Boolean) {
        mic.muted = muted
        rtc?.setMuted(muted)
        _state.update { it.copy(muted = muted) }
        socket.send(buildJsonObject { put("type", JsonPrimitive("settings")); put("muted", JsonPrimitive(muted)) })
    }

    fun setTranslatedAudio(on: Boolean) {
        if (!on) player.stopCurrent()
        _state.update { it.copy(translatedAudio = on) }
        socket.send(buildJsonObject { put("type", JsonPrimitive("settings")); put("translate_audio", JsonPrimitive(on)) })
    }

    fun setRoute(route: AudioRoute) {
        router.select(route)
        _state.update { it.copy(route = router.current() ?: route) }
    }

    fun setOriginalVolume(v: Float) {
        rtc?.setRemoteVolume(v)
        _state.update { it.copy(originalVolume = v) }
    }

    fun setSubtitleScale(scale: Float) = _state.update { it.copy(subtitleScale = scale.coerceIn(0.8f, 1.8f)) }

    fun setLanguage(code: String, autoDetect: Boolean) {
        myLanguage = code
        _state.update { it.copy(autoDetect = autoDetect, me = it.me?.copy(language = code)) }
        Log.i("CallLifecycle", "state=language_changed callId=${info.callId} lang=$code autoDetect=$autoDetect")
        socket.send(buildJsonObject {
            put("type", JsonPrimitive("settings")); put("language", JsonPrimitive(code)); put("auto_detect", JsonPrimitive(autoDetect))
        })
    }

    fun retry(turnId: String) {
        socket.send(buildJsonObject { put("type", JsonPrimitive("retry")); put("id", JsonPrimitive(turnId)) })
    }

    fun dismissBanner() = _state.update { it.copy(banner = null, notice = null) }

    private fun fail(message: String) {
        Log.i("CallLifecycle", "state=ended callId=${info.callId} status=failed reason=$message")
        _state.update { it.copy(status = CallStatus.Failed, banner = Banner(message, severe = true), endReason = message) }
        teardown()
    }

    /** The person we rang declined, was busy, didn't answer, or was unavailable; the server has ended the call. */
    fun markUnanswered(title: String, detail: String = title) {
        if (ended) return
        _state.update { it.copy(unanswered = title, unansweredDetail = detail) }
        end(detail, notifyServer = false)
    }

    fun end(reason: String = "You ended the call.", notifyServer: Boolean = true) {
        if (ended) return
        Log.i("CallLifecycle", "state=ended callId=${info.callId} status=ended notifyServer=$notifyServer reason=$reason")
        if (notifyServer) {
            if (info.ringing && _state.value.peer == null && _state.value.unanswered == null) {
                scope.launch { runCatching { api.cancelCall(info.callId) } }
            }
            socket.send(buildJsonObject { put("type", JsonPrimitive("leave")) })
        }
        _state.update { it.copy(status = CallStatus.Ended, endedAtMs = System.currentTimeMillis(), endReason = reason) }
        if (settings.saveTranscripts) saveTranscript()
        teardown()
    }

    private fun saveTranscript() {
        val s = _state.value
        if (s.conversation.turns.isEmpty()) return
        val start = s.startedAtMs ?: return
        transcripts.save(
            SavedTranscript(
                callId = info.callId, startedAt = start, durationS = ((s.endedAtMs ?: System.currentTimeMillis()) - start) / 1000,
                peerName = s.peer?.name ?: "Guest",
                lines = s.conversation.turns.map { SavedLine(if (it.mine) "me" else "peer", it.original, it.translation, it.sourceLang, it.targetLang) },
            ),
        )
    }

    private fun teardown() {
        ended = true
        mic.enabled = false
        scope.launch {
            delay(300) // let the "leave" frame go out
            socket.close()
            rtc?.close()
            rtc = null
            player.release()
            router.end()
            scope.cancel()
        }
    }
}
