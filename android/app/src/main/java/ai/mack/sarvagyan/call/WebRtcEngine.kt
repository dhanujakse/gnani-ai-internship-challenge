package ai.mack.sarvagyan.call

import android.content.Context
import android.media.AudioAttributes
import android.media.MediaRecorder
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.jsonPrimitive
import org.webrtc.AudioSource
import org.webrtc.AudioTrack
import org.webrtc.DataChannel
import org.webrtc.IceCandidate
import org.webrtc.MediaConstraints
import org.webrtc.MediaStream
import org.webrtc.PeerConnection
import org.webrtc.PeerConnectionFactory
import org.webrtc.RtpReceiver
import org.webrtc.SdpObserver
import org.webrtc.SessionDescription
import org.webrtc.audio.JavaAudioDeviceModule

enum class Quality { Unknown, Good, Fair, Poor }

/**
 * Peer-to-peer audio call over WebRTC (original voices). The audio device module records the mic once:
 * WebRTC sends it to the peer and the samples callback hands the same audio to the translator.
 * Signalling (offer/answer/ICE) travels over the Sarvagyan server WebSocket.
 */
class WebRtcEngine(
    context: Context,
    private val onMicSamples: (data: ByteArray, sampleRate: Int, channels: Int) -> Unit,
    private val listener: Listener,
) {
    interface Listener {
        fun onLocalSignal(payload: JsonObject)
        fun onConnectionState(state: PeerConnection.PeerConnectionState)
        fun onQuality(quality: Quality, rttMs: Int?)
        fun onMicError(message: String)
    }

    private val adm: JavaAudioDeviceModule
    private val factory: PeerConnectionFactory
    private val audioSource: AudioSource
    private val localTrack: AudioTrack
    private var pc: PeerConnection? = null
    private var remoteTrack: AudioTrack? = null
    private val pendingCandidates = mutableListOf<IceCandidate>()
    private var remoteDescriptionSet = false
    @Volatile private var remoteVolume = 0.35

    init {
        ensureInitialized(context)
        adm = JavaAudioDeviceModule.builder(context)
            .setAudioSource(MediaRecorder.AudioSource.VOICE_COMMUNICATION)
            .setUseHardwareAcousticEchoCanceler(true)
            .setUseHardwareNoiseSuppressor(true)
            .setInputSampleRate(TARGET_RATE) // the translator wants 16 kHz; no resampling on most phones
            .setAudioAttributes(
                AudioAttributes.Builder().setUsage(AudioAttributes.USAGE_VOICE_COMMUNICATION)
                    .setContentType(AudioAttributes.CONTENT_TYPE_SPEECH).build(),
            )
            .setSamplesReadyCallback { s -> onMicSamples(s.data, s.sampleRate, s.channelCount) }
            .setAudioRecordErrorCallback(object : JavaAudioDeviceModule.AudioRecordErrorCallback {
                override fun onWebRtcAudioRecordInitError(errorMessage: String) = listener.onMicError("Microphone could not start.")
                override fun onWebRtcAudioRecordStartError(errorCode: JavaAudioDeviceModule.AudioRecordStartErrorCode, errorMessage: String) =
                    listener.onMicError("Microphone is in use by another app.")
                override fun onWebRtcAudioRecordError(errorMessage: String) = listener.onMicError("Microphone stopped unexpectedly.")
            })
            .createAudioDeviceModule()
        factory = PeerConnectionFactory.builder().setAudioDeviceModule(adm).createPeerConnectionFactory()
        val constraints = MediaConstraints().apply {
            mandatory.add(MediaConstraints.KeyValuePair("googEchoCancellation", "true"))
            mandatory.add(MediaConstraints.KeyValuePair("googNoiseSuppression", "true"))
            mandatory.add(MediaConstraints.KeyValuePair("googAutoGainControl", "true"))
        }
        audioSource = factory.createAudioSource(constraints)
        localTrack = factory.createAudioTrack("sarvagyan-mic", audioSource)
    }

    fun start(iceServers: List<PeerConnection.IceServer>) {
        if (pc != null) return
        val config = PeerConnection.RTCConfiguration(iceServers).apply {
            sdpSemantics = PeerConnection.SdpSemantics.UNIFIED_PLAN
            continualGatheringPolicy = PeerConnection.ContinualGatheringPolicy.GATHER_CONTINUALLY
            bundlePolicy = PeerConnection.BundlePolicy.MAXBUNDLE
        }
        pc = factory.createPeerConnection(config, observer)?.also { it.addTrack(localTrack, listOf("sarvagyan")) }
    }

    val started: Boolean get() = pc != null

    fun makeOffer(iceRestart: Boolean) {
        val peer = pc ?: return
        if (iceRestart) peer.restartIce()
        val constraints = MediaConstraints().apply {
            mandatory.add(MediaConstraints.KeyValuePair("OfferToReceiveAudio", "true"))
        }
        peer.createOffer(object : SimpleSdp() {
            override fun onCreateSuccess(desc: SessionDescription) {
                peer.setLocalDescription(SimpleSdp(), desc)
                listener.onLocalSignal(sdpJson(desc))
            }
        }, constraints)
    }

    fun onRemoteSignal(payload: JsonObject) {
        val peer = pc ?: return
        when (payload["kind"]?.jsonPrimitive?.content) {
            "offer", "answer" -> {
                val type = if (payload["kind"]!!.jsonPrimitive.content == "offer") SessionDescription.Type.OFFER else SessionDescription.Type.ANSWER
                val sdp = payload["sdp"]?.jsonPrimitive?.content ?: return
                peer.setRemoteDescription(object : SimpleSdp() {
                    override fun onSetSuccess() {
                        remoteDescriptionSet = true
                        synchronized(pendingCandidates) {
                            pendingCandidates.forEach { peer.addIceCandidate(it) }
                            pendingCandidates.clear()
                        }
                        if (type == SessionDescription.Type.OFFER) answer(peer)
                    }
                }, SessionDescription(type, sdp))
            }
            "candidate" -> {
                val c = IceCandidate(
                    payload["mid"]?.jsonPrimitive?.content ?: "",
                    payload["index"]?.jsonPrimitive?.content?.toIntOrNull() ?: 0,
                    payload["candidate"]?.jsonPrimitive?.content ?: return,
                )
                if (remoteDescriptionSet) peer.addIceCandidate(c) else synchronized(pendingCandidates) { pendingCandidates.add(c) }
            }
        }
    }

    private fun answer(peer: PeerConnection) {
        peer.createAnswer(object : SimpleSdp() {
            override fun onCreateSuccess(desc: SessionDescription) {
                peer.setLocalDescription(SimpleSdp(), desc)
                listener.onLocalSignal(sdpJson(desc))
            }
        }, MediaConstraints())
    }

    fun setMuted(muted: Boolean) {
        localTrack.setEnabled(!muted)
    }

    /** Volume of the peer's ORIGINAL voice (0..1). Lowered by default so the translation is clear. */
    fun setRemoteVolume(volume: Float) {
        remoteVolume = (volume.coerceIn(0f, 1f) * 10.0) // WebRTC's scale is 0..10
        remoteTrack?.setVolume(remoteVolume)
    }

    fun pollStats() {
        pc?.getStats { report ->
            var rtt: Double? = null
            var lost = 0.0
            var received = 0.0
            for (s in report.statsMap.values) {
                when (s.type) {
                    "candidate-pair" -> if (s.members["state"] == "succeeded" && s.members["nominated"] == true) {
                        rtt = (s.members["currentRoundTripTime"] as? Number)?.toDouble() ?: rtt
                    }
                    "inbound-rtp" -> {
                        lost += (s.members["packetsLost"] as? Number)?.toDouble() ?: 0.0
                        received += (s.members["packetsReceived"] as? Number)?.toDouble() ?: 0.0
                    }
                }
            }
            val lossPct = if (received + lost > 0) lost / (received + lost) * 100 else 0.0
            val rttMs = rtt?.let { (it * 1000).toInt() }
            val q = when {
                rttMs == null -> Quality.Unknown
                rttMs < 250 && lossPct < 2 -> Quality.Good
                rttMs < 600 && lossPct < 8 -> Quality.Fair
                else -> Quality.Poor
            }
            listener.onQuality(q, rttMs)
        }
    }

    fun close() {
        runCatching { pc?.close() }
        runCatching { pc?.dispose() }
        pc = null
        runCatching { localTrack.dispose() }
        runCatching { audioSource.dispose() }
        runCatching { factory.dispose() }
        runCatching { adm.release() }
    }

    private fun sdpJson(desc: SessionDescription) = buildJsonObject {
        put("kind", JsonPrimitive(if (desc.type == SessionDescription.Type.OFFER) "offer" else "answer"))
        put("sdp", JsonPrimitive(desc.description))
    }

    private val observer = object : PeerConnection.Observer {
        override fun onIceCandidate(c: IceCandidate) = listener.onLocalSignal(buildJsonObject {
            put("kind", JsonPrimitive("candidate"))
            put("candidate", JsonPrimitive(c.sdp))
            put("mid", JsonPrimitive(c.sdpMid ?: ""))
            put("index", JsonPrimitive(c.sdpMLineIndex))
        })

        override fun onConnectionChange(newState: PeerConnection.PeerConnectionState) = listener.onConnectionState(newState)

        override fun onAddTrack(receiver: RtpReceiver, streams: Array<out MediaStream>) {
            (receiver.track() as? AudioTrack)?.let {
                remoteTrack = it
                it.setVolume(remoteVolume)
            }
        }

        override fun onSignalingChange(state: PeerConnection.SignalingState) = Unit
        override fun onIceConnectionChange(state: PeerConnection.IceConnectionState) = Unit
        override fun onIceConnectionReceivingChange(receiving: Boolean) = Unit
        override fun onIceGatheringChange(state: PeerConnection.IceGatheringState) = Unit
        override fun onIceCandidatesRemoved(candidates: Array<out IceCandidate>) = Unit
        override fun onAddStream(stream: MediaStream) = Unit
        override fun onRemoveStream(stream: MediaStream) = Unit
        override fun onDataChannel(channel: DataChannel) = Unit
        override fun onRenegotiationNeeded() = Unit
    }

    private open class SimpleSdp : SdpObserver {
        override fun onCreateSuccess(desc: SessionDescription) = Unit
        override fun onSetSuccess() = Unit
        override fun onCreateFailure(error: String) = Unit
        override fun onSetFailure(error: String) = Unit
    }

    companion object {
        @Volatile private var initialized = false

        private fun ensureInitialized(context: Context) {
            if (initialized) return
            synchronized(this) {
                if (initialized) return
                PeerConnectionFactory.initialize(PeerConnectionFactory.InitializationOptions.builder(context.applicationContext).createInitializationOptions())
                initialized = true
            }
        }

        fun iceServers(list: JsonArray): List<PeerConnection.IceServer> = list.mapNotNull { el ->
            val o = el as? JsonObject ?: return@mapNotNull null
            val urls = (o["urls"] as? JsonArray)?.map { it.jsonPrimitive.content } ?: listOfNotNull(o["urls"]?.jsonPrimitive?.content)
            if (urls.isEmpty()) return@mapNotNull null
            PeerConnection.IceServer.builder(urls).apply {
                o["username"]?.jsonPrimitive?.content?.let { setUsername(it) }
                o["credential"]?.jsonPrimitive?.content?.let { setPassword(it) }
            }.createIceServer()
        }
    }
}
