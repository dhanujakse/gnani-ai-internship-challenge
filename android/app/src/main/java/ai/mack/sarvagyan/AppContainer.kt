package ai.mack.sarvagyan

import android.app.Application
import android.content.Context
import android.util.Log
import ai.mack.sarvagyan.call.AppSocket
import ai.mack.sarvagyan.call.CallSession
import ai.mack.sarvagyan.call.CallStatus
import ai.mack.sarvagyan.call.IncomingCall
import ai.mack.sarvagyan.call.Ringer
import ai.mack.sarvagyan.data.int
import ai.mack.sarvagyan.data.objOrNull
import ai.mack.sarvagyan.data.str
import kotlinx.coroutines.flow.collectLatest
import kotlinx.coroutines.flow.distinctUntilChanged
import kotlinx.coroutines.flow.map
import kotlinx.serialization.json.JsonObject
import ai.mack.sarvagyan.data.ApiClient
import ai.mack.sarvagyan.data.ApiException
import ai.mack.sarvagyan.data.AvatarStore
import ai.mack.sarvagyan.data.Session
import ai.mack.sarvagyan.data.AppSettings
import ai.mack.sarvagyan.data.CallInfo
import ai.mack.sarvagyan.data.FallbackLanguages
import ai.mack.sarvagyan.data.Language
import ai.mack.sarvagyan.data.SettingsStore
import ai.mack.sarvagyan.data.TokenStore
import ai.mack.sarvagyan.data.TranscriptStore
import ai.mack.sarvagyan.data.User
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.launch
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.withContext
import kotlinx.serialization.json.Json
import okhttp3.OkHttpClient
import java.util.concurrent.TimeUnit

/** Manual dependency container: one instance per process, created by [SarvagyanApp]. */
class AppContainer(private val context: Context) {
    val scope = CoroutineScope(SupervisorJob() + Dispatchers.Default)
    val json = Json { ignoreUnknownKeys = true; explicitNulls = false }
    val http: OkHttpClient = OkHttpClient.Builder()
        .connectTimeout(10, TimeUnit.SECONDS)
        .readTimeout(30, TimeUnit.SECONDS)
        .pingInterval(15, TimeUnit.SECONDS) // keeps the call socket alive through NATs and detects drops
        .build()
    val settingsStore = SettingsStore(context)
    val settings: StateFlow<AppSettings> = settingsStore.settings.stateIn(scope, SharingStarted.Eagerly, AppSettings())
    val tokens = TokenStore(context)
    val transcripts = TranscriptStore(context, json)
    val avatars = AvatarStore(context, http, { settings.value.serverUrl }) { tokens.get() }
    val api = ApiClient(http, json, baseUrl = { settings.value.serverUrl }, token = { tokens.get() },
        refresh = { stale -> refreshSession(stale) })
    private val refreshLock = Mutex()
    private val answerLock = Mutex()
    @Volatile private var answeringCallId: String? = null

    val user = MutableStateFlow<User?>(null)
    val languages = MutableStateFlow(FallbackLanguages)
    val activeCall = MutableStateFlow<CallSession?>(null)
    val incomingCall = MutableStateFlow<IncomingCall?>(null)
    val appSocket = AppSocket(http, json, api)
    private val ringer = Ringer(context)

    init {
        // the always-on connection runs while someone is signed in; incoming calls arrive through it
        scope.launch { user.map { it?.id }.distinctUntilChanged().collectLatest { id -> if (id != null) appSocket.run() } }
        scope.launch { appSocket.events.collect { onAppEvent(it) } }
        scope.launch { settingsStore.cachedLanguages(json)?.let { languages.value = it } }
    }

    suspend fun refreshLanguages() {
        runCatching { api.languages().languages }.onSuccess {
            if (it.isNotEmpty()) {
                languages.value = it
                settingsStore.cacheLanguages(json, it)
            }
        }
    }

    fun language(code: String): Language? = languages.value.firstOrNull { it.code == code }

    /** Keeps the server's copy of my language in step, so voicemails to me are translated into it. */
    suspend fun syncLanguage() {
        val mine = settings.value.myLanguage
        val me = user.value ?: runCatching { api.me() }.getOrNull()?.also { user.value = it } ?: return
        if (me.language != mine) runCatching { api.updateMe(language = mine) }.onSuccess { user.value = it }
    }

    fun saveSession(session: Session) {
        tokens.set(session.token)
        tokens.setRefresh(session.refreshToken.ifEmpty { null })
        user.value = session.user
    }

    /** Swaps the refresh token for a new pair. One refresh at a time; a refresh another caller just did counts. */
    suspend fun refreshSession(stale: String?): Boolean = refreshLock.withLock {
        val now = tokens.get()
        if (now != null && now != stale) return@withLock true
        val refreshToken = tokens.getRefresh() ?: return@withLock false
        try {
            saveSession(api.refreshTokens(refreshToken))
            true
        } catch (e: ApiException) {
            if (e.isAuth) { tokens.clear(); user.value = null } // session ended (signed out elsewhere)
            false
        }
    }

    /** After the account was deleted: forget it on this phone (the server session is already gone). */
    fun forgetAccount() {
        tokens.clear()
        user.value = null
    }

    fun signOut() {
        val token = tokens.get()
        tokens.clear()
        user.value = null
        if (token != null) scope.launch { runCatching { api.logout(token) } } // ends the session on the server too
    }

    private fun inCall(): Boolean = activeCall.value?.state?.value?.status?.let { it != CallStatus.Ended && it != CallStatus.Failed } == true

    fun effectiveMyLanguage(): String =
        settings.value.myLanguage.takeIf { it.isNotBlank() }
            ?: user.value?.language?.takeIf { it.isNotBlank() }
            ?: "en-IN"

    private fun sendCallAck(callId: String, state: String, ackId: String? = null) {
        val payload = kotlinx.serialization.json.buildJsonObject {
            put("type", kotlinx.serialization.json.JsonPrimitive("call_ack"))
            put("call_id", kotlinx.serialization.json.JsonPrimitive(callId))
            put("state", kotlinx.serialization.json.JsonPrimitive(state))
            if (ackId != null) put("ack_id", kotlinx.serialization.json.JsonPrimitive(ackId))
        }
        appSocket.send(payload)
    }

    private fun applyCallStateFeedback(callId: String, state: String, peerName: String?) {
        val session = activeCall.value?.takeIf { it.info.callId == callId } ?: return
        val name = peerName ?: session.info.peerName ?: "They"
        when (state) {
            "declined" -> {
                Log.i("CallLifecycle", "state=ended direction=outgoing callId=$callId reason=declined")
                session.markUnanswered("Declined", "$name declined the call.")
            }
            "busy" -> {
                Log.i("CallLifecycle", "state=ended direction=outgoing callId=$callId reason=busy")
                session.markUnanswered("Busy", "$name is on another call.")
            }
            "no_answer", "missed" -> {
                Log.i("CallLifecycle", "state=ended direction=outgoing callId=$callId reason=no_answer")
                session.markUnanswered("No answer", "$name didn't answer.")
            }
            "unavailable" -> {
                Log.i("CallLifecycle", "state=ended direction=outgoing callId=$callId reason=unavailable")
                session.markUnanswered("Unavailable", "$name is offline.")
            }
            "answered" -> {
                Log.i("CallLifecycle", "state=accepted direction=outgoing callId=$callId")
            }
        }
    }

    private fun onAppEvent(ev: JsonObject) {
        val callId = ev.str("call_id") ?: return
        val ackId = ev.str("ack_id")
        when (ev.str("type")) {
            "incoming_call" -> {
                sendCallAck(callId, "ringing", ackId)
                if (inCall()) {
                    Log.i("CallLifecycle", "state=ended callId=$callId reason=busy_auto_decline")
                    scope.launch { runCatching { api.declineCall(callId, reason = "busy") } }
                    return
                }
                val from = ev.objOrNull("from") ?: return
                val call = IncomingCall(callId, from.str("id") ?: return, from.str("name") ?: "Someone", from.str("username"),
                    from.str("language") ?: "en-IN", ev.int("expires_in") ?: 40, fromAvatar = from.str("avatar"))
                Log.i("CallLifecycle", "state=ringing direction=incoming callId=$callId from=${call.fromName}")
                incomingCall.value = call
                ringer.start(call.fromName, call.expiresInS * 1000L)
            }
            "call_state" -> {
                val state = ev.str("state") ?: return
                sendCallAck(callId, state, ackId)
                if ((state == "cancelled" || state == "no_answer") && incomingCall.value?.callId == callId) {
                    Log.i("CallLifecycle", "state=ended direction=incoming callId=$callId reason=$state")
                    incomingCall.value = null
                    ringer.stop()
                }
                applyCallStateFeedback(callId, state, ev.str("peer_name"))
            }
            "call_cancelled" -> if (incomingCall.value?.callId == callId) {
                val reason = ev.str("reason") ?: "cancelled"
                sendCallAck(callId, reason, ackId)
                if (answeringCallId == callId && reason == "answered_elsewhere") return
                Log.i("CallLifecycle", "state=ended direction=incoming callId=$callId reason=$reason")
                incomingCall.value = null
                ringer.stop()
            }
            "call_declined" -> {
                sendCallAck(callId, "declined", ackId)
                applyCallStateFeedback(callId, "declined", ev.str("peer_name"))
            }
            "call_busy" -> {
                sendCallAck(callId, "busy", ackId)
                applyCallStateFeedback(callId, "busy", ev.str("peer_name"))
            }
            "call_missed" -> {
                sendCallAck(callId, "no_answer", ackId)
                applyCallStateFeedback(callId, "no_answer", ev.str("peer_name"))
            }
            "call_answered" -> {
                sendCallAck(callId, "answered", ackId)
                applyCallStateFeedback(callId, "answered", ev.str("peer_name"))
            }
        }
    }

    /** Rings a person; the call screen shows "Ringing" until they answer, decline, busy, no answer, or unavailable. */
    suspend fun callPerson(id: String, name: String): CallSession {
        val lang = effectiveMyLanguage()
        Log.i("CallLifecycle", "state=ringing direction=outgoing to=$name lang=$lang")
        val info = api.callPerson(id, lang)
        val session = startCall(info, lang)
        when {
            info.callState == "busy" -> session.markUnanswered("Busy", "${info.peerName ?: name} is on another call.")
            !info.reachable || info.callState == "unavailable" -> {
                session.markUnanswered("Unavailable", "${info.peerName ?: name} is offline.")
                scope.launch { runCatching { api.cancelCall(info.callId) } }
            }
        }
        return session
    }

    /**
     * Runs accept + CallSession setup on the container scope so dismissing [IncomingCallScreen]
     * can never cancel the coroutine mid-flight. Caller must call [clearIncoming] after navigating.
     */
    suspend fun answerIncoming(): CallSession = withContext(scope.coroutineContext) {
        answerLock.withLock {
            val call = incomingCall.value ?: throw ApiException(404, "The call has ended.")
            answeringCallId = call.callId
            Log.i("CallLifecycle", "state=accepted direction=incoming callId=${call.callId}")
            ringer.stop()
            val lang = effectiveMyLanguage()
            try {
                val info = api.answerCall(call.callId, lang)
                startCall(info, lang)
            } catch (t: Throwable) {
                Log.w("CallLifecycle", "state=ended direction=incoming callId=${call.callId} reason=accept_failed error=${t.message}")
                if (incomingCall.value?.callId == call.callId) incomingCall.value = null
                throw t
            } finally {
                if (answeringCallId == call.callId) answeringCallId = null
            }
        }
    }

    fun clearIncoming(callId: String) {
        if (incomingCall.value?.callId == callId) incomingCall.value = null
    }

    suspend fun declineIncoming() {
        val call = incomingCall.value ?: return
        Log.i("CallLifecycle", "state=ended direction=incoming callId=${call.callId} reason=declined_by_me")
        ringer.stop()
        incomingCall.value = null
        runCatching { api.declineCall(call.callId) }
    }

    suspend fun startCall(info: CallInfo, myLanguage: String, initialRoute: ai.mack.sarvagyan.call.AudioRoute? = null): CallSession {
        activeCall.value?.takeIf { it.info.callId != info.callId }?.end(notifyServer = true)
        Log.i("CallLifecycle", "state=connecting callId=${info.callId} ringing=${info.ringing} lang=$myLanguage")
        val session = CallSession(context, api, http, json, transcripts, info, settings.value, myLanguage)
        activeCall.value = session
        CallService.start(context)
        session.start(initialRoute)
        return session
    }
}

class SarvagyanApp : Application() {
    lateinit var container: AppContainer
        private set

    override fun onCreate() {
        super.onCreate()
        container = AppContainer(this)
    }
}

val Context.container: AppContainer get() = (applicationContext as SarvagyanApp).container
