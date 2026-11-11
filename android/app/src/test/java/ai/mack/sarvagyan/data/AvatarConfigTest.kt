package ai.mack.sarvagyan.data

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class AvatarConfigTest {
    @Test
    fun missingFileIsSkippedWithoutCrashingAndNamedInWarning() {
        val raw = """
            [
              {"id": "avatar-01", "main": "avatar-01.webp", "thumb": "avatar-01-thumb.webp"},
              {"id": "avatar-02", "main": "avatar-02.webp", "thumb": "avatar-02-thumb.webp"},
              {"id": "avatar-03", "main": "avatar-03.webp", "thumb": "avatar-03-thumb.webp"}
            ]
        """.trimIndent()
        val warnings = mutableListOf<String>()
        val existing = setOf(
            "avatars/avatar-01.webp",
            "avatars/avatar-01-thumb.webp",
            // avatar-02.webp intentionally missing!
            "avatars/avatar-02-thumb.webp",
            "avatars/avatar-03.webp",
            "avatars/avatar-03-thumb.webp",
        )

        val entries = parseAndVerifyAvatarConfig(
            rawJson = raw,
            assetExists = { it in existing },
            warn = { warnings += it },
        )

        assertEquals(listOf("avatar-01", "avatar-03"), entries.map { it.id })
        assertEquals(1, warnings.size)
        assertTrue(
            "Warning should name the missing file avatar-02.webp, got: ${warnings[0]}",
            warnings[0].contains("avatar-02.webp"),
        )
    }

    @Test
    fun corruptConfigReturnsEmptyListWithoutCrashing() {
        val warnings = mutableListOf<String>()
        val entries = parseAndVerifyAvatarConfig(
            rawJson = "{broken json",
            assetExists = { true },
            warn = { warnings += it },
        )
        assertTrue(entries.isEmpty())
        assertEquals(1, warnings.size)
    }
}

