package ai.mack.sarvagyan.call

import org.junit.Assert.assertArrayEquals
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import kotlin.math.PI
import kotlin.math.abs
import kotlin.math.sin

class AudioFramesTest {
    private fun tone(rate: Int, ms: Int, hz: Double = 440.0) =
        ShortArray(rate * ms / 1000) { i -> (8000 * sin(2 * PI * hz * i / rate)).toInt().toShort() }

    @Test
    fun bytesAndShortsRoundTripLittleEndian() {
        val s = shortArrayOf(1, -2, 300, Short.MAX_VALUE, Short.MIN_VALUE)
        val b = Pcm.shortsToBytes(s)
        assertEquals(0x01.toByte(), b[0])
        assertEquals(0x00.toByte(), b[1])
        assertArrayEquals(s, Pcm.bytesToShorts(b))
    }

    @Test
    fun downmixAveragesChannels() {
        assertArrayEquals(shortArrayOf(150, -50), Pcm.toMono(shortArrayOf(100, 200, -100, 0), 2))
    }

    @Test
    fun resampleKeepsDurationAndShape() {
        val src = tone(48_000, 100)
        val out = Pcm.resample(src, 48_000)
        assertEquals(1600, out.size) // 100 ms at 16 kHz
        val peak = out.maxOf { abs(it.toInt()) }
        assertTrue("440 Hz survives the low-pass: peak=$peak", peak in 7000..8100)
        assertEquals(1600, Pcm.resample(tone(8_000, 100), 8_000).size)
        assertTrue(Pcm.resample(src, 16_000, 16_000) === src) // no-op when already 16 kHz
    }

    @Test
    fun framerEmitsExact1024ByteFramesAcrossCalls() {
        val frames = mutableListOf<ByteArray>()
        val f = Framer(1024) { frames += it }
        f.feed(ByteArray(700) { 1 })
        f.feed(ByteArray(700) { 2 })
        f.feed(ByteArray(700) { 3 })
        assertEquals(2, frames.size)
        assertTrue(frames.all { it.size == 1024 })
        assertEquals(1.toByte(), frames[0][0])
        assertEquals(2.toByte(), frames[0][1023]) // remainder carried over, not dropped
    }

    @Test
    fun echoGateBlocksMicWhileAndJustAfterTranslationPlays() {
        val g = EchoGate(tailMs = 350)
        assertTrue(g.allowMic(0))
        g.setPlaying(true, 1000)
        assertFalse(g.allowMic(1200))
        g.setPlaying(false, 3000)
        assertFalse(g.allowMic(3100)) // speaker tail can still be in the mic
        assertTrue(g.allowMic(3400))
    }

    @Test
    fun micPipelineSendsSilenceInsteadOfTranslatedEchoAndNothingWhenMuted() {
        val sent = mutableListOf<ByteArray>()
        var now = 0L
        val gate = EchoGate(tailMs = 0)
        val mic = MicPipeline(gate, { now }) { sent += it }
        val chunk = Pcm.shortsToBytes(tone(16_000, 64)) // 2048 bytes = 2 frames
        mic.onSamples(chunk, 16_000, 1)
        assertEquals(2, sent.size)
        assertTrue(sent[0].any { it != 0.toByte() })

        gate.setPlaying(true, now)
        mic.onSamples(chunk, 16_000, 1)
        assertEquals(4, sent.size)
        assertTrue("cadence kept, content silenced", sent[2].all { it == 0.toByte() } && sent[3].all { it == 0.toByte() })

        gate.setPlaying(false, now)
        mic.muted = true
        mic.onSamples(chunk, 16_000, 1)
        assertEquals(4, sent.size) // muted: nothing at all leaves the phone for translation
    }

    @Test
    fun micPipelineResamples48kStereoTo16kMono() {
        val sent = mutableListOf<ByteArray>()
        val mic = MicPipeline(EchoGate(0), { 0L }) { sent += it }
        val mono = tone(48_000, 96)
        val stereo = ShortArray(mono.size * 2) { mono[it / 2] }
        mic.onSamples(Pcm.shortsToBytes(stereo), 48_000, 2)
        // 96 ms at 16 kHz = 1536 samples = 3072 bytes = 3 frames
        assertEquals(3, sent.size)
    }
}
