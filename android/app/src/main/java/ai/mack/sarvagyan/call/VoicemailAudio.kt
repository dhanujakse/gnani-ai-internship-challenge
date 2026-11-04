package ai.mack.sarvagyan.call

import android.annotation.SuppressLint
import android.media.AudioAttributes
import android.media.AudioFormat
import android.media.AudioRecord
import android.media.AudioTrack
import android.media.MediaRecorder
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.currentCoroutineContext
import kotlinx.coroutines.delay
import kotlinx.coroutines.isActive
import kotlinx.coroutines.withContext
import java.io.ByteArrayOutputStream
import kotlin.math.sqrt

const val VOICEMAIL_MAX_MS = 60_000L

/**
 * Records a voicemail into memory as 16 kHz mono PCM (what the server's speech recogniser needs).
 * Nothing is written to disk. Runs until [shouldStop] returns true or [maxMs] is reached.
 */
object VoicemailRecorder {
    private val rates = intArrayOf(TARGET_RATE, 48_000, 44_100)

    @SuppressLint("MissingPermission") // the screen asks for RECORD_AUDIO before calling this
    suspend fun record(
        maxMs: Long = VOICEMAIL_MAX_MS,
        shouldStop: () -> Boolean,
        onProgress: (elapsedMs: Long, level: Float) -> Unit,
    ): ByteArray = withContext(Dispatchers.IO) {
        val (rec, rate) = openRecorder() ?: throw IllegalStateException("Can't use the microphone on this device.")
        val out = ByteArrayOutputStream()
        val buf = ShortArray(rate / 20) // 50 ms
        var samples = 0L
        try {
            rec.startRecording()
            while (currentCoroutineContext().isActive && !shouldStop()) {
                val n = rec.read(buf, 0, buf.size)
                if (n <= 0) continue
                val chunk = buf.copyOf(n)
                out.write(Pcm.shortsToBytes(Pcm.resample(chunk, rate)))
                samples += n
                val elapsed = samples * 1000 / rate
                onProgress(elapsed, rms(chunk))
                if (elapsed >= maxMs) break
            }
        } finally {
            runCatching { rec.stop() }
            rec.release()
        }
        out.toByteArray()
    }

    @SuppressLint("MissingPermission")
    private fun openRecorder(): Pair<AudioRecord, Int>? {
        for (rate in rates) {
            val min = AudioRecord.getMinBufferSize(rate, AudioFormat.CHANNEL_IN_MONO, AudioFormat.ENCODING_PCM_16BIT)
            if (min <= 0) continue
            val rec = try {
                AudioRecord(MediaRecorder.AudioSource.VOICE_RECOGNITION, rate, AudioFormat.CHANNEL_IN_MONO,
                    AudioFormat.ENCODING_PCM_16BIT, maxOf(min, rate / 5 * 2))
            } catch (e: Exception) {
                null
            }
            if (rec?.state == AudioRecord.STATE_INITIALIZED) return rec to rate
            rec?.release()
        }
        return null
    }

    private fun rms(s: ShortArray): Float {
        if (s.isEmpty()) return 0f
        var sum = 0.0
        for (v in s) sum += v.toDouble() * v
        return (sqrt(sum / s.size) / 8000.0).toFloat().coerceIn(0f, 1f)
    }
}

/** Plays a stream of 16 kHz mono PCM chunks through the media speaker. */
class VoicemailPlayer(private val sampleRate: Int = TARGET_RATE) {
    private var track: AudioTrack? = null
    private var written = 0L

    private fun ensure(): AudioTrack {
        track?.let { return it }
        val min = AudioTrack.getMinBufferSize(sampleRate, AudioFormat.CHANNEL_OUT_MONO, AudioFormat.ENCODING_PCM_16BIT)
        return AudioTrack.Builder()
            .setAudioAttributes(AudioAttributes.Builder().setUsage(AudioAttributes.USAGE_MEDIA)
                .setContentType(AudioAttributes.CONTENT_TYPE_SPEECH).build())
            .setAudioFormat(AudioFormat.Builder().setSampleRate(sampleRate).setEncoding(AudioFormat.ENCODING_PCM_16BIT)
                .setChannelMask(AudioFormat.CHANNEL_OUT_MONO).build())
            .setTransferMode(AudioTrack.MODE_STREAM)
            .setBufferSizeInBytes(maxOf(min, sampleRate / 2 * 2)) // ~500 ms
            .build()
            .also { it.play(); track = it }
    }

    /** Blocking write; call from a background thread. */
    fun write(data: ByteArray, length: Int) {
        val t = ensure()
        val n = t.write(data, 0, length, AudioTrack.WRITE_BLOCKING)
        if (n > 0) written += n / 2
    }

    /** Waits until everything written has been heard. */
    suspend fun drain() {
        val t = track ?: return
        repeat(400) { // up to ~8 s
            if ((t.playbackHeadPosition.toLong() and 0xFFFFFFFFL) >= written) return
            delay(20)
        }
    }

    fun release() {
        runCatching { track?.pause(); track?.flush(); track?.stop() }
        runCatching { track?.release() }
        track = null
        written = 0
    }
}
