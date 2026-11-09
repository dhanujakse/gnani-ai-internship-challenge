package ai.mack.sarvagyan.call

import java.nio.ByteBuffer
import java.nio.ByteOrder

/** Speech recognition expects 16 kHz mono PCM s16le in exactly 1,024-byte frames (Gnani Prisma streaming). */
const val TARGET_RATE = 16_000
const val FRAME_BYTES = 1024

object Pcm {
    fun bytesToShorts(data: ByteArray, length: Int = data.size): ShortArray {
        val out = ShortArray(length / 2)
        ByteBuffer.wrap(data, 0, length - length % 2).order(ByteOrder.LITTLE_ENDIAN).asShortBuffer().get(out)
        return out
    }

    fun shortsToBytes(samples: ShortArray): ByteArray {
        val buf = ByteBuffer.allocate(samples.size * 2).order(ByteOrder.LITTLE_ENDIAN)
        buf.asShortBuffer().put(samples)
        return buf.array()
    }

    /** Mix interleaved channels down to mono. */
    fun toMono(samples: ShortArray, channels: Int): ShortArray {
        if (channels <= 1) return samples
        val out = ShortArray(samples.size / channels)
        for (i in out.indices) {
            var sum = 0
            for (c in 0 until channels) sum += samples[i * channels + c]
            out[i] = (sum / channels).toShort()
        }
        return out
    }

    /**
     * Resample to [TARGET_RATE]. Downsampling averages the samples that fall into each output step
     * (a box low-pass that prevents most aliasing); upsampling interpolates linearly.
     */
    fun resample(samples: ShortArray, fromRate: Int, toRate: Int = TARGET_RATE): ShortArray {
        if (fromRate == toRate || samples.isEmpty()) return samples
        val outLen = (samples.size.toLong() * toRate / fromRate).toInt()
        val out = ShortArray(outLen)
        val step = fromRate.toDouble() / toRate
        if (step > 1.0) {
            for (i in 0 until outLen) {
                val start = (i * step).toInt()
                val end = minOf(samples.size, ((i + 1) * step).toInt().coerceAtLeast(start + 1))
                var sum = 0L
                for (j in start until end) sum += samples[j]
                out[i] = (sum / (end - start)).toShort()
            }
        } else {
            for (i in 0 until outLen) {
                val pos = i * step
                val j = pos.toInt()
                val frac = pos - j
                val a = samples[j]
                val b = samples[minOf(j + 1, samples.size - 1)]
                out[i] = (a + (b - a) * frac).toInt().toShort()
            }
        }
        return out
    }
}

/** Accumulates PCM bytes and emits fixed-size frames, carrying the remainder over. */
class Framer(private val frameBytes: Int = FRAME_BYTES, private val emit: (ByteArray) -> Unit) {
    private val buffer = ByteArray(frameBytes)
    private var filled = 0

    fun feed(data: ByteArray) {
        var offset = 0
        while (offset < data.size) {
            val n = minOf(frameBytes - filled, data.size - offset)
            System.arraycopy(data, offset, buffer, filled, n)
            filled += n
            offset += n
            if (filled == frameBytes) {
                emit(buffer.copyOf())
                filled = 0
            }
        }
    }

    fun reset() {
        filled = 0
    }
}

/**
 * While translated speech plays on this phone (and briefly after), the mic stream to the translator
 * is replaced with silence so the translation is never picked up and re-translated. The original
 * call audio over WebRTC is unaffected. The server's echo guard is a second line of defence.
 */
class EchoGate(private val tailMs: Long = 350) {
    @Volatile private var playing = false
    @Volatile private var lastPlayEndMs = Long.MIN_VALUE / 2 // nothing has played yet

    fun setPlaying(isPlaying: Boolean, nowMs: Long) {
        if (playing && !isPlaying) lastPlayEndMs = nowMs
        playing = isPlaying
    }

    fun allowMic(nowMs: Long): Boolean = !playing && nowMs - lastPlayEndMs >= tailMs
}

/** Converts whatever the recorder delivers into 1,024-byte 16 kHz frames, applying mute, noise reduction/VAD and the echo gate. */
class MicPipeline(
    private val gate: EchoGate,
    private val clock: () -> Long,
    var noiseReduction: Boolean = true,
    private val energyThreshold: Double = 350.0,
    private val minSpeechMs: Long = 200L,
    private val hangoverMs: Long = 350L,
    private val send: (ByteArray) -> Unit,
) {
    @Volatile var muted = false
    @Volatile var enabled = true
    private val framer = Framer(FRAME_BYTES) { send(it) }

    private var speechStartMs = -1L
    private var lastSpeechMs = -1L

    private fun rms(samples: ShortArray): Double {
        if (samples.isEmpty()) return 0.0
        var sum = 0.0
        for (s in samples) {
            val v = s.toDouble()
            sum += v * v
        }
        return kotlin.math.sqrt(sum / samples.size)
    }

    fun onSamples(data: ByteArray, sampleRate: Int, channels: Int) {
        if (!enabled || muted) return
        val mono = Pcm.toMono(Pcm.bytesToShorts(data), channels)
        val pcm = Pcm.resample(mono, sampleRate)
        val now = clock()

        var passSpeech = true
        if (noiseReduction) {
            val level = rms(pcm)
            if (level >= energyThreshold) {
                if (speechStartMs < 0) {
                    speechStartMs = now
                }
                val duration = now - speechStartMs
                if (duration >= minSpeechMs) {
                    lastSpeechMs = now
                    passSpeech = true
                } else {
                    passSpeech = false
                }
            } else {
                speechStartMs = -1L
                if (lastSpeechMs > 0 && now - lastSpeechMs < hangoverMs) {
                    passSpeech = true
                } else {
                    passSpeech = false
                }
            }
        }

        val bytes = if (gate.allowMic(now) && passSpeech) {
            Pcm.shortsToBytes(pcm)
        } else {
            ByteArray(pcm.size * 2) // keep cadence: silence
        }
        framer.feed(bytes)
    }
}
