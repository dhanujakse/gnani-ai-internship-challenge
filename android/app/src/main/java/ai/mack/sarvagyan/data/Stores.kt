package ai.mack.sarvagyan.data

import android.content.Context
import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyProperties
import android.util.Base64
import androidx.datastore.core.DataStore
import androidx.datastore.preferences.core.Preferences
import androidx.datastore.preferences.core.booleanPreferencesKey
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.floatPreferencesKey
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import ai.mack.sarvagyan.BuildConfig
import ai.mack.sarvagyan.ui.theme.ThemeMode
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.map
import kotlinx.serialization.Serializable
import kotlinx.serialization.builtins.ListSerializer
import kotlinx.serialization.json.Json
import java.io.File
import java.security.KeyStore
import javax.crypto.Cipher
import javax.crypto.KeyGenerator
import javax.crypto.SecretKey
import javax.crypto.spec.GCMParameterSpec

private val Context.dataStore: DataStore<Preferences> by preferencesDataStore(name = "settings")

data class AppSettings(
    val onboarded: Boolean = false,
    val serverUrl: String = BuildConfig.DEFAULT_SERVER_URL,
    val myLanguage: String = "en-IN",
    val partnerLanguage: String = "en-IN",
    val autoDetect: Boolean = false,
    val voice: String? = null, // voice used for translations YOU hear (in your language)
    val speed: Float = 1.0f,
    val subtitleScale: Float = 1.0f,
    val theme: ThemeMode = ThemeMode.Dark,
    val translatedAudio: Boolean = true,
    val originalVolume: Float = 0.35f, // peer's own voice under the translation
    val speakerOn: Boolean = true,
    val saveTranscripts: Boolean = false, // opt-in only
    val privacyAcknowledged: Boolean = false,
    val appLock: Boolean = false, // fingerprint / face / phone PIN to open the app
    val blockScreenshots: Boolean = false,
    val noiseReduction: Boolean = true,
)

class SettingsStore(private val context: Context) {
    private object K {
        val onboarded = booleanPreferencesKey("onboarded")
        val server = stringPreferencesKey("server_url")
        val myLang = stringPreferencesKey("my_language")
        val partnerLang = stringPreferencesKey("partner_language")
        val auto = booleanPreferencesKey("auto_detect")
        val voice = stringPreferencesKey("voice")
        val speed = floatPreferencesKey("speed")
        val scale = floatPreferencesKey("subtitle_scale")
        val theme = stringPreferencesKey("theme")
        val ttsAudio = booleanPreferencesKey("translated_audio")
        val origVol = floatPreferencesKey("original_volume")
        val speaker = booleanPreferencesKey("speaker_on")
        val save = booleanPreferencesKey("save_transcripts")
        val privacy = booleanPreferencesKey("privacy_ack")
        val appLock = booleanPreferencesKey("app_lock")
        val noShots = booleanPreferencesKey("block_screenshots")
        val noiseReduction = booleanPreferencesKey("noise_reduction")
        val langCache = stringPreferencesKey("languages_cache")
    }

    val settings: Flow<AppSettings> = context.dataStore.data.map { p ->
        AppSettings(
            onboarded = p[K.onboarded] ?: false,
            serverUrl = p[K.server] ?: BuildConfig.DEFAULT_SERVER_URL,
            myLanguage = p[K.myLang] ?: "en-IN",
            partnerLanguage = p[K.partnerLang] ?: "en-IN",
            autoDetect = p[K.auto] ?: false,
            voice = p[K.voice],
            speed = p[K.speed] ?: 1.0f,
            subtitleScale = p[K.scale] ?: 1.0f,
            theme = runCatching { ThemeMode.valueOf(p[K.theme] ?: "Dark") }.getOrDefault(ThemeMode.Dark),
            translatedAudio = p[K.ttsAudio] ?: true,
            originalVolume = p[K.origVol] ?: 0.35f,
            speakerOn = p[K.speaker] ?: true,
            saveTranscripts = p[K.save] ?: false,
            privacyAcknowledged = p[K.privacy] ?: false,
            appLock = p[K.appLock] ?: false,
            blockScreenshots = p[K.noShots] ?: false,
            noiseReduction = p[K.noiseReduction] ?: true,
        )
    }

    suspend fun current(): AppSettings = settings.first()

    suspend fun update(transform: (AppSettings) -> AppSettings) {
        val next = transform(current())
        context.dataStore.edit { p ->
            p[K.onboarded] = next.onboarded
            p[K.server] = next.serverUrl.trim()
            p[K.myLang] = next.myLanguage
            p[K.partnerLang] = next.partnerLanguage
            p[K.auto] = next.autoDetect
            if (next.voice != null) p[K.voice] = next.voice else p.remove(K.voice)
            p[K.speed] = next.speed
            p[K.scale] = next.subtitleScale
            p[K.theme] = next.theme.name
            p[K.ttsAudio] = next.translatedAudio
            p[K.origVol] = next.originalVolume
            p[K.speaker] = next.speakerOn
            p[K.save] = next.saveTranscripts
            p[K.privacy] = next.privacyAcknowledged
            p[K.appLock] = next.appLock
            p[K.noShots] = next.blockScreenshots
            p[K.noiseReduction] = next.noiseReduction
        }
    }

    suspend fun cachedLanguages(json: Json): List<Language>? =
        context.dataStore.data.first()[K.langCache]?.let { runCatching { json.decodeFromString(ListSerializer(Language.serializer()), it) }.getOrNull() }

    suspend fun cacheLanguages(json: Json, languages: List<Language>) {
        context.dataStore.edit { it[K.langCache] = json.encodeToString(ListSerializer(Language.serializer()), languages) }
    }
}

/** The sign-in token, encrypted with an Android Keystore AES-GCM key (never stored in plain text). */
class TokenStore(context: Context) {
    private val prefs = context.getSharedPreferences("auth", Context.MODE_PRIVATE)
    private val alias = "sarvagyan_token_key"

    @Volatile private var cached: String? = null

    private fun key(): SecretKey {
        val ks = KeyStore.getInstance("AndroidKeyStore").apply { load(null) }
        (ks.getEntry(alias, null) as? KeyStore.SecretKeyEntry)?.let { return it.secretKey }
        val gen = KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES, "AndroidKeyStore")
        gen.init(
            KeyGenParameterSpec.Builder(alias, KeyProperties.PURPOSE_ENCRYPT or KeyProperties.PURPOSE_DECRYPT)
                .setBlockModes(KeyProperties.BLOCK_MODE_GCM)
                .setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE)
                .build(),
        )
        return gen.generateKey()
    }

    @Volatile private var cachedRefresh: String? = null

    private fun read(name: String): String? {
        val blob = prefs.getString(name, null) ?: return null
        return runCatching {
            val raw = Base64.decode(blob, Base64.NO_WRAP)
            val cipher = Cipher.getInstance("AES/GCM/NoPadding")
            cipher.init(Cipher.DECRYPT_MODE, key(), GCMParameterSpec(128, raw.copyOfRange(0, 12)))
            String(cipher.doFinal(raw.copyOfRange(12, raw.size)))
        }.getOrNull()
    }

    private fun write(name: String, value: String?) {
        if (value == null) {
            prefs.edit().remove(name).apply()
            return
        }
        val cipher = Cipher.getInstance("AES/GCM/NoPadding")
        cipher.init(Cipher.ENCRYPT_MODE, key())
        val out = cipher.iv + cipher.doFinal(value.toByteArray())
        prefs.edit().putString(name, Base64.encodeToString(out, Base64.NO_WRAP)).apply()
    }

    /** The short-lived access token (15 minutes). */
    fun get(): String? = cached ?: read("token").also { cached = it }

    fun set(token: String?) {
        cached = token
        write("token", token)
    }

    /** The refresh token: replaced by the server on every use; both are encrypted with a Keystore key. */
    fun getRefresh(): String? = cachedRefresh ?: read("refresh").also { cachedRefresh = it }

    fun setRefresh(token: String?) {
        cachedRefresh = token
        write("refresh", token)
    }

    fun clear() {
        set(null)
        setRefresh(null)
    }
}

@Serializable
data class SavedLine(val speaker: String, val original: String, val translation: String?, val sourceLang: String, val targetLang: String?)

@Serializable
data class SavedTranscript(val callId: String, val startedAt: Long, val durationS: Long, val peerName: String, val lines: List<SavedLine>)

/** Transcripts are stored only on this device, only when the user opted in, and can be deleted any time. */
/**
 * Saved call transcripts (opt-in), encrypted on the phone with an AES-GCM key kept in the Android Keystore, so the
 * files are unreadable outside the app. Transcripts saved by older versions as plain JSON are encrypted on first read.
 */
class TranscriptStore(context: Context, private val json: Json) {
    private val dir = File(context.filesDir, "transcripts").apply { mkdirs() }
    private val alias = "sarvagyan_transcripts_key"

    private fun key(): SecretKey {
        val ks = KeyStore.getInstance("AndroidKeyStore").apply { load(null) }
        (ks.getEntry(alias, null) as? KeyStore.SecretKeyEntry)?.let { return it.secretKey }
        val gen = KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES, "AndroidKeyStore")
        gen.init(KeyGenParameterSpec.Builder(alias, KeyProperties.PURPOSE_ENCRYPT or KeyProperties.PURPOSE_DECRYPT)
            .setBlockModes(KeyProperties.BLOCK_MODE_GCM).setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE).build())
        return gen.generateKey()
    }

    private fun encFile(callId: String) = File(dir, "$callId.enc")
    private fun legacyFile(callId: String) = File(dir, "$callId.json")

    fun save(t: SavedTranscript) {
        val cipher = Cipher.getInstance("AES/GCM/NoPadding")
        cipher.init(Cipher.ENCRYPT_MODE, key())
        val plain = json.encodeToString(SavedTranscript.serializer(), t).toByteArray()
        encFile(t.callId).writeBytes(cipher.iv + cipher.doFinal(plain))
        legacyFile(t.callId).delete()
    }

    fun load(callId: String): SavedTranscript? {
        encFile(callId).takeIf { it.exists() }?.let { f ->
            return runCatching {
                val raw = f.readBytes()
                val cipher = Cipher.getInstance("AES/GCM/NoPadding")
                cipher.init(Cipher.DECRYPT_MODE, key(), GCMParameterSpec(128, raw.copyOfRange(0, 12)))
                json.decodeFromString(SavedTranscript.serializer(), String(cipher.doFinal(raw.copyOfRange(12, raw.size))))
            }.getOrNull()
        }
        val legacy = legacyFile(callId).takeIf { it.exists() } ?: return null
        val t = runCatching { json.decodeFromString(SavedTranscript.serializer(), legacy.readText()) }.getOrNull() ?: return null
        runCatching { save(t) } // re-save encrypted, delete the plain file
        return t
    }

    fun delete(callId: String) = encFile(callId).delete() or legacyFile(callId).delete()
    fun deleteAll(): Int = dir.listFiles()?.count { it.delete() } ?: 0
    fun count(): Int = dir.listFiles()?.size ?: 0
}
