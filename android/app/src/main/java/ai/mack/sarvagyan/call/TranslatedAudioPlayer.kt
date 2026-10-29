package ai.mack.sarvagyan.call

import android.media.AudioAttributes
import android.media.AudioFormat
import android.media.AudioTrack
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.channels.Channel
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.launch

/**
 * Plays translated speech (16 kHz mono PCM chunks streamed from the server) on its own AudioTrack,
 * separate from the WebRTC call audio. Chunks are played as they arrive for the lowest latency.
 * `playingId` drives the "playing translation" indicator and the echo gate.
 */
class TranslatedAudioPlayer(private val sampleRate: Int = TARGET_RATE, private val onPlaying: (String?) -> Unit = {}) {
    private sealed interface Cmd {
        data class Start(val id: String) : Cmd
        class Chunk(val data: ByteArray) : Cmd
        data class End(val id: String) : Cmd
        data object Flush : Cmd
    }

    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.IO)
    private val commands = Channel<Cmd>(Channel.UNLIMITED)
    private val _playing = MutableStateFlow<String?>(null)
    val playingId: StateFlow<String?> = _playing
    @Volatile var volume: Float = 1.0f
        set(value) {
            field = value.coerceIn(0f, 1f)
            track?.setVolume(field)
        }
    @Volatile var lastError: String? = null
        private set

    private var track: AudioTrack? = null
    private var framesWritten = 0L

    init {
        scope.launch { run() }
    }

    private fun ensureTrack(): AudioTrack? {
        track?.let { return it }
        return try {
            val min = AudioTrack.getMinBufferSize(sampleRate, AudioFormat.CHANNEL_OUT_MONO, AudioFormat.ENCODING_PCM_16BIT)
            AudioTrack.Builder()
                .setAudioAttributes(
                    AudioAttributes.Builder()
                        .setUsage(AudioAttributes.USAGE_VOICE_COMMUNICATION) // follows the call route; visible to echo cancellation
                        .setContentType(AudioAttributes.CONTENT_TYPE_SPEECH)
                        .build(),
                )
                .setAudioFormat(
                    AudioFormat.Builder().setSampleRate(sampleRate).setEncoding(AudioFormat.ENCODING_PCM_16BIT)
                        .setChannelMask(AudioFormat.CHANNEL_OUT_MONO).build(),
                )
                .setTransferMode(AudioTrack.MODE_STREAM)
                .setBufferSizeInBytes(maxOf(min, sampleRate / 5 * 2)) // ~200 ms
                .build()
                .also {
                    it.setVolume(volume)
                    it.play()
                    track = it
                }
        } catch (e: Exception) {
            lastError = "Can't play translated audio on this device."
            null
        }
    }

    private suspend fun run() {
        var current: String? = null
        for (cmd in commands) {
            when (cmd) {
                is Cmd.Start -> {
                    current = cmd.id
                    setPlaying(cmd.id)
                }
                is Cmd.Chunk -> ensureTrack()?.let { t ->
                    val n = t.write(cmd.data, 0, cmd.data.size, AudioTrack.WRITE_BLOCKING)
                    if (n > 0) framesWritten += n / 2
                }
                is Cmd.End -> {
                    if (cmd.id == current) {
                        drain()
                        current = null
                        setPlaying(null)
                    }
                }
                Cmd.Flush -> {
                    track?.pause()
                    track?.flush()
                    track?.play()
                    framesWritten = track?.playbackHeadPosition?.toLong()?.and(0xFFFFFFFFL) ?: 0L
                    current = null
                    setPlaying(null)
                }
            }
        }
    }

    private suspend fun drain() {
        val t = track ?: return
        repeat(150) { // up to ~3 s
            val played = t.playbackHeadPosition.toLong() and 0xFFFFFFFFL
            if (played >= framesWritten) return
            delay(20)
        }
    }

    private fun setPlaying(id: String?) {
        _playing.value = id
        onPlaying(id)
    }

    fun start(id: String) { commands.trySend(Cmd.Start(id)) }
    fun write(data: ByteArray) { commands.trySend(Cmd.Chunk(data)) }
    fun end(id: String) { commands.trySend(Cmd.End(id)) }
    fun stopCurrent() { commands.trySend(Cmd.Flush) }

    fun release() {
        commands.close()
        scope.cancel()
        runCatching { track?.stop() }
        runCatching { track?.release() }
        track = null
    }
}
