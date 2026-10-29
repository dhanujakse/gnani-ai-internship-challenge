package ai.mack.sarvagyan.call

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertSame
import org.junit.Assert.assertTrue
import org.junit.Test

class ConversationTest {
    private val me = "me"
    private val peer = "peer"

    private fun ev(id: String, speaker: String, stage: Stage, rev: Int, translation: String? = null, metrics: Map<String, Int> = emptyMap()) =
        UtteranceEvent(id, speaker, seq = 1, stage = stage, rev = rev, original = "நாளை பள்ளிக்கு விடுமுறை", sourceLang = "ta-IN",
            translation = translation, targetLang = "en-IN", error = null, metrics = metrics)

    @Test
    fun streamingUpdatesNeverDuplicateATurn() {
        var c = Conversation()
        c = c.apply(ev("x-a1", peer, Stage.Recognized, 1), me, 0)
        c = c.apply(ev("x-a1", peer, Stage.Translating, 2), me, 10)
        c = c.apply(ev("x-a1", peer, Stage.Translated, 3, "Tomorrow is a school holiday"), me, 20)
        c = c.apply(ev("x-a1", peer, Stage.Done, 5, null, mapOf("tts_first_ms" to 700)), me, 30)
        assertEquals(1, c.turns.size)
        val t = c.turns.single()
        assertEquals(Stage.Done, t.stage)
        assertEquals("Tomorrow is a school holiday", t.translation) // kept even when a later event omits it
        assertEquals(0L, t.firstSeenMs)
        assertEquals(700, t.metrics["tts_first_ms"])
    }

    @Test
    fun lateOrDuplicateEventsDoNotOverwriteNewerState() {
        var c = Conversation()
        c = c.apply(ev("x-a1", peer, Stage.Done, 5, "final"), me, 0)
        val before = c
        c = c.apply(ev("x-a1", peer, Stage.Translating, 2), me, 50) // arrives late
        c = c.apply(ev("x-a1", peer, Stage.Done, 5, "final"), me, 60) // duplicate
        assertSame(before, c)
        assertEquals(Stage.Done, c.turns.single().stage)
    }

    @Test
    fun overlappingSpeakersStaySeparateAndOrdered() {
        var c = Conversation().withSpeech(me, true).withSpeech(peer, true)
        c = c.apply(ev("x-b1", me, Stage.Recognized, 1), me, 0)
        c = c.apply(ev("x-a1", peer, Stage.Recognized, 1), me, 5)
        c = c.apply(ev("x-b1", me, Stage.Translated, 3, "mine"), me, 9)
        assertEquals(listOf("x-b1", "x-a1"), c.turns.map { it.id })
        assertTrue(c.turns[0].mine)
        assertTrue(!c.turns[1].mine)
        assertTrue(c.speaking.isEmpty()) // a finalised turn ends that speaker's "listening" state
    }

    @Test
    fun headlineShowsTheRightLanguageForEachSide() {
        var c = Conversation()
        c = c.apply(ev("p", peer, Stage.Translated, 1, "Tomorrow is a holiday"), me, 0)
        c = c.apply(ev("m", me, Stage.Translated, 1, "Tomorrow is a holiday"), me, 0)
        assertEquals("Tomorrow is a holiday", c.turns[0].headline) // theirs: in my language
        assertEquals("நாளை பள்ளிக்கு விடுமுறை", c.turns[0].secondary)
        assertEquals("நாளை பள்ளிக்கு விடுமுறை", c.turns[1].headline) // mine: as I said it
        assertEquals("Tomorrow is a holiday", c.turns[1].secondary)
    }

    @Test
    fun translatedCountIgnoresFailures() {
        var c = Conversation()
        c = c.apply(ev("a", peer, Stage.Done, 4, "ok"), me, 0)
        c = c.apply(ev("b", peer, Stage.Failed, 3), me, 0)
        assertEquals(1, c.translatedCount)
        assertNull(c.withPlaying("a").withPlaying(null).playingId)
    }
}
