package ai.mack.sarvagyan.call

/**
 * Conversation state for the active call. Pure and immutable so it is easy to test.
 *
 * The server sends `utterance` events for each turn as it moves through the pipeline. Each carries
 * an id and a revision number that only grows, so we upsert by id and ignore anything older than
 * what we already show. That keeps subtitles free of duplicates and stops late responses from
 * overwriting newer state. Turns keep the order in which they were first finalised.
 */
enum class Stage(val wire: String) {
    Listening("listening"),
    Recognized("recognized"),
    Translating("translating"),
    Translated("translated"),
    Speaking("speaking"),
    Done("done"),
    Failed("failed"),
    Skipped("skipped");

    companion object {
        fun parse(value: String?): Stage = entries.firstOrNull { it.wire == value } ?: Recognized
    }
}

data class Turn(
    val id: String,
    val speakerId: String,
    val mine: Boolean,
    val seq: Int,
    val stage: Stage,
    val rev: Int,
    val original: String,
    val sourceLang: String,
    val translation: String?,
    val targetLang: String?,
    val error: String?,
    val metrics: Map<String, Int>,
    val firstSeenMs: Long,
) {
    /** Text the reader cares about most: the peer's words in my language, my own words as I said them. */
    val headline: String get() = if (mine) original else translation ?: original
    val secondary: String? get() = if (mine) translation?.takeIf { it != original } else original.takeIf { translation != null && it != translation }
    val totalLatencyMs: Int? get() = metrics["server_total_ms"]?.let { it + (metrics["stt_ms"] ?: 0) }
}

data class UtteranceEvent(
    val id: String,
    val speakerId: String,
    val seq: Int,
    val stage: Stage,
    val rev: Int,
    val original: String,
    val sourceLang: String,
    val translation: String?,
    val targetLang: String?,
    val error: String?,
    val metrics: Map<String, Int>,
)

data class Conversation(
    val turns: List<Turn> = emptyList(),
    val speaking: Set<String> = emptySet(), // speaker ids whose speech is being recognised right now
    val playingId: String? = null, // turn whose translated speech is playing on this device
) {
    fun apply(ev: UtteranceEvent, myId: String, nowMs: Long): Conversation {
        val idx = turns.indexOfFirst { it.id == ev.id }
        if (idx >= 0 && turns[idx].rev >= ev.rev) return this // stale or duplicate
        val turn = Turn(
            id = ev.id, speakerId = ev.speakerId, mine = ev.speakerId == myId, seq = ev.seq, stage = ev.stage,
            rev = ev.rev, original = ev.original, sourceLang = ev.sourceLang,
            translation = ev.translation ?: turns.getOrNull(idx)?.translation,
            targetLang = ev.targetLang ?: turns.getOrNull(idx)?.targetLang,
            error = ev.error, metrics = (turns.getOrNull(idx)?.metrics ?: emptyMap()) + ev.metrics,
            firstSeenMs = turns.getOrNull(idx)?.firstSeenMs ?: nowMs,
        )
        val next = if (idx >= 0) turns.toMutableList().also { it[idx] = turn } else turns + turn
        return copy(turns = next, speaking = speaking - ev.speakerId)
    }

    fun withSpeech(speakerId: String, active: Boolean) = copy(speaking = if (active) speaking + speakerId else speaking - speakerId)
    fun withPlaying(id: String?) = copy(playingId = id)

    val translatedCount: Int get() = turns.count { it.translation != null && it.stage != Stage.Failed }
    fun last(n: Int): List<Turn> = turns.takeLast(n)
}
