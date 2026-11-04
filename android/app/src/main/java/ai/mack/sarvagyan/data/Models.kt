package ai.mack.sarvagyan.data

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.JsonObject

@Serializable
data class User(
    val id: String,
    @SerialName("display_name") val displayName: String,
    val email: String? = null,
    @SerialName("is_demo") val isDemo: Boolean = false,
    val language: String = "ta-IN",
)

@Serializable
data class Session(val token: String, val user: User)

@Serializable
data class Language(
    val code: String,
    val name: String,
    val native: String,
    val voices: List<String>,
    @SerialName("auto_detect") val autoDetect: Boolean = true,
)

@Serializable
data class SpeedRange(val min: Float = 0.85f, val max: Float = 1.15f, val default: Float = 1.0f)

@Serializable
data class LanguagesResponse(val languages: List<Language>, val primary: List<String> = emptyList(), val speed: SpeedRange = SpeedRange())

@Serializable
data class CallInfo(
    @SerialName("call_id") val callId: String,
    @SerialName("invite_code") val inviteCode: String,
    @SerialName("invite_link") val inviteLink: String,
    @SerialName("app_link") val appLink: String,
    val participants: Int = 1,
)

@Serializable
data class Peer(
    val id: String,
    val name: String? = null,
    val language: String? = null,
    @SerialName("is_demo") val isDemo: Boolean = false,
    val favourite: Boolean = false,
)

@Serializable
data class CallRecord(
    @SerialName("call_id") val callId: String,
    val status: String,
    @SerialName("created_at") val createdAt: Double,
    @SerialName("duration_s") val durationS: Int? = null,
    val utterances: Int = 0,
    @SerialName("my_language") val myLanguage: String? = null,
    val peer: Peer? = null,
)

@Serializable
data class HistoryResponse(val calls: List<CallRecord>)

@Serializable
data class Contact(val id: String, val name: String, val language: String, @SerialName("is_demo") val isDemo: Boolean = false)

@Serializable
data class ContactsResponse(val contacts: List<Contact>)

@Serializable
data class Health(val status: String, val version: String)

@Serializable
data class Diagnostics(val raw: JsonObject)

/** Offline fallback so the app is usable before the first server contact; the server list wins. */
val FallbackLanguages = listOf(
    Language("ta-IN", "Tamil", "தமிழ்", listOf("Trisha", "Asmita", "Brinda", "Vedika", "Noopur")),
    Language("en-IN", "English", "English", listOf("Kaveri", "Pranav", "Trupti", "Devika", "Shlok", "Girish")),
)

/** Same rules as the server: uppercase, letters and digits only ("abc-234" -> "ABC234"). */
fun normaliseCode(code: String): String = code.uppercase().filter { it.isLetterOrDigit() }

fun formatDuration(seconds: Long): String = if (seconds >= 3600) "%d:%02d:%02d".format(seconds / 3600, seconds % 3600 / 60, seconds % 60)
else "%d:%02d".format(seconds / 60, seconds % 60)

/** The other person on a voicemail: the sender (inbox) or the recipient (sent). */
@Serializable
data class VoicemailContact(
    val id: String,
    val name: String,
    val language: String? = null,
    @SerialName("is_demo") val isDemo: Boolean = false,
)

@Serializable
data class Voicemail(
    val id: String,
    val status: String, // processing | ready | failed
    @SerialName("created_at") val createdAt: Double,
    val heard: Boolean = false,
    @SerialName("duration_ms") val durationMs: Long = 0,
    @SerialName("source_lang") val sourceLang: String,
    @SerialName("target_lang") val targetLang: String,
    val original: String? = null,
    val translation: String? = null,
    val error: String? = null,
    val contact: VoicemailContact,
)

@Serializable
data class VoicemailsResponse(val inbox: List<Voicemail>, val sent: List<Voicemail>, val unread: Int = 0)

@Serializable
data class SentVoicemail(val id: String, val status: String, val contact: VoicemailContact)
