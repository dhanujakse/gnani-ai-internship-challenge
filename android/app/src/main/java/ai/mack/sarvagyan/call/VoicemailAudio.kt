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

/**
 * Plays a stream of 16 kHz mono PCM chunks through the media speaker.
 * Guarantees strict 16-bit PCM frame alignment (preventing byte-swapping static noise),
 * pre-buffers to prevent hardware starvation underruns, strips any container headers,
 * and waits dynamically for the full duration of the message.
 */
class VoicemailPlayer(private val sampleRate: Int = TARGET_RATE) {
    private var track: AudioTrack? = null
    private var writtenFrames = 0L
    private var leftoverByte: Int = -1
    private var isFirstChunk = true
    private var started = false
    private var bufferedBytes = 0
    private val preRollBytes = sampleRate * 2 * 3 / 10 // ~300 ms pre-roll before starting playback

    private fun ensure(): AudioTrack {
        track?.let { return it }
        val min = AudioTrack.getMinBufferSize(sampleRate, AudioFormat.CHANNEL_OUT_MONO, AudioFormat.ENCODING_PCM_16BIT)
        val bufSize = maxOf(min * 2, sampleRate * 2 * 2) // ~2 seconds buffer capacity to prevent underruns
        return AudioTrack.Builder()
            .setAudioAttributes(
                AudioAttributes.Builder()
                    .setUsage(AudioAttributes.USAGE_MEDIA)
                    .setContentType(AudioAttributes.CONTENT_TYPE_SPEECH)
                    .build()
            )
            .setAudioFormat(
                AudioFormat.Builder()
                    .setSampleRate(sampleRate)
                    .setEncoding(AudioFormat.ENCODING_PCM_16BIT)
                    .setChannelMask(AudioFormat.CHANNEL_OUT_MONO)
                    .build()
            )
            .setTransferMode(AudioTrack.MODE_STREAM)
            .setBufferSizeInBytes(bufSize)
            .build()
            .also {
                track = it
            }
    }

    /**
     * Blocking write; call from a background thread.
     * Ensures strict 2-byte frame alignment so PCM samples are never corrupted by network chunk splits.
     */
    fun write(data: ByteArray, length: Int) {
        if (length <= 0) return
        var offset = 0
        var len = length

        // Check for and skip RIFF WAV header on first chunk if present
        if (isFirstChunk) {
            isFirstChunk = false
            if (len >= 44 && data[0] == 'R'.code.toByte() && data[1] == 'I'.code.toByte() &&
                data[2] == 'F'.code.toByte() && data[3] == 'F'.code.toByte()
            ) {
                var dataOffset = 12
                while (dataOffset + 8 <= len) {
                    if (data[dataOffset] == 'd'.code.toByte() && data[dataOffset + 1] == 'a'.code.toByte() &&
                        data[dataOffset + 2] == 't'.code.toByte() && data[dataOffset + 3] == 'a'.code.toByte()
                    ) {
                        dataOffset += 8 // skip "data" + 4-byte size field
                        break
                    }
                    dataOffset++
                }
                if (dataOffset in 12..len) {
                    offset = dataOffset
                    len -= dataOffset
                } else {
                    offset = 44
                    len -= 44
                }
            }
        }

        if (len <= 0) return
        val t = ensure()

        // Combine any leftover byte from the previous chunk with the first byte of this chunk
        if (leftoverByte != -1) {
            val combined = byteArrayOf(leftoverByte.toByte(), data[offset])
            leftoverByte = -1
            offset += 1
            len -= 1
            val n = t.write(combined, 0, 2, AudioTrack.WRITE_BLOCKING)
            if (n > 0) {
                writtenFrames += n / 2
                bufferedBytes += n
            }
        }

        if (len <= 0) return

        // Write an even number of bytes to preserve 16-bit frame alignment
        val writeLen = if (len % 2 != 0) len - 1 else len
        if (writeLen > 0) {
            val n = t.write(data, offset, writeLen, AudioTrack.WRITE_BLOCKING)
            if (n > 0) {
                writtenFrames += n / 2
                bufferedBytes += n
            }
        }

        // Save any odd trailing byte for the next chunk
        if (len % 2 != 0) {
            leftoverByte = data[offset + writeLen].toInt() and 0xFF
        }

        // Start playback once pre-roll buffer threshold is met to avoid starvation clicks
        if (!started && bufferedBytes >= preRollBytes) {
            t.play()
            started = true
        }
    }

    /** Waits until everything written has been heard. */
    suspend fun drain() {
        val t = track ?: return

        // Flush any trailing odd byte padded with 0
        if (leftoverByte != -1) {
            val lastSample = byteArrayOf(leftoverByte.toByte(), 0x00)
            leftoverByte = -1
            val n = t.write(lastSample, 0, 2, AudioTrack.WRITE_BLOCKING)
            if (n > 0) {
                writtenFrames += n / 2
                bufferedBytes += n
            }
        }

        if (writtenFrames == 0L) return

        if (!started) {
            t.play()
            started = true
        }

        val audioDurationMs = writtenFrames * 1000L / sampleRate
        val maxWaitMs = audioDurationMs + 2500L
        val maxSteps = (maxWaitMs / 20).toInt().coerceAtLeast(50)

        for (i in 0 until maxSteps) {
            val head = t.playbackHeadPosition.toLong() and 0xFFFFFFFFL
            if (head >= writtenFrames) break
            delay(20)
        }
    }

    fun release() {
        runCatching {
            track?.let { t ->
                if (t.playState == AudioTrack.PLAYSTATE_PLAYING) {
                    t.pause()
                }
                t.flush()
                t.stop()
            }
        }
        runCatching { track?.release() }
        track = null
        writtenFrames = 0L
        leftoverByte = -1
        bufferedBytes = 0
        started = false
        isFirstChunk = true
    }
}
