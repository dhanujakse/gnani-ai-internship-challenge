package ai.mack.sarvagyan.data

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.JsonObject

@Serializable
data class User(
    val id: String,
    @SerialName("display_name") val displayName: String,
    val username: String? = null,
    val email: String? = null,
    @SerialName("is_demo") val isDemo: Boolean = false,
    val language: String = "ta-IN",
    @SerialName("allow_calls") val allowCalls: String = "contacts", // who can call me: contacts | everyone
    @SerialName("read_receipts") val readReceipts: Boolean = true,
    @SerialName("chat_retention_days") val chatRetentionDays: Int = 30,
    @SerialName("phone_added") val phoneAdded: Boolean = false, // friends can find me in "Discover from Phone"
)

@Serializable
data class Session(
    val token: String,
    val user: User,
    @SerialName("refresh_token") val refreshToken: String = "",
    @SerialName("expires_in") val expiresIn: Int = 900,
)

/** A phone or other device that is signed in to this account. */
@Serializable
data class DeviceSession(
    val id: String,
    val device: String,
    @SerialName("created_at") val createdAt: Double,
    @SerialName("last_used_at") val lastUsedAt: Double,
    val current: Boolean = false,
)

@Serializable
data class DeviceSessionsResponse(val sessions: List<DeviceSession>)

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
    val ringing: Boolean = false, // a direct call to a person (rings their phone), not an invite-code call
    val reachable: Boolean = true, // false: their app is not connected right now
    @SerialName("peer_id") val peerId: String? = null,
    @SerialName("peer_name") val peerName: String? = null,
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
    val direction: String? = null,   // "incoming" | "outgoing"
) {
    val missedByMe get() = direction == "incoming" && status == "missed"
}

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
    Language("hi-IN", "Hindi", "हिन्दी", listOf("Nalini", "Deepak", "Bhavna", "Chitra", "Roopesh", "Urmila")),
    Language("te-IN", "Telugu", "తెలుగు", listOf("Lavanya", "Suhana", "Lehara")),
    Language("kn-IN", "Kannada", "ಕನ್ನಡ", listOf("Kavin", "Saanvi")),
    Language("ml-IN", "Malayalam", "മലയാളം", listOf("Reshma", "Riyaan")),
    Language("mr-IN", "Marathi", "मराठी", listOf("Ishaan")),
    Language("bn-IN", "Bengali", "বাংলা", listOf("Kirra", "Dhruva")),
    Language("gu-IN", "Gujarati", "ગુજરાતી", listOf("Falak")),
    Language("pa-IN", "Punjabi", "ਪੰਜਾਬੀ", listOf("Mehuli")),
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

@Serializable
data class CheckUsernameResponse(
    val available: Boolean,
    val username: String,
    val reason: String? = null,
)

@Serializable
data class UserSearchResult(
    val id: String,
    @SerialName("display_name") val displayName: String,
    val username: String? = null,
    val avatar: String? = null,
    val language: String = "en-IN",
    @SerialName("is_demo") val isDemo: Boolean = false,
)

@Serializable
data class SearchUsersResponse(val users: List<UserSearchResult>)

@Serializable
data class ConversationMember(
    val id: String,
    @SerialName("display_name") val displayName: String,
    val username: String? = null,
    val language: String = "ta-IN",
    val role: String = "member",
    @SerialName("joined_at") val joinedAt: Double = 0.0,
)

@Serializable
data class ChatMessage(
    val id: String,
    @SerialName("conversation_id") val conversationId: String,
    @SerialName("sender_id") val senderId: String,
    @SerialName("sender_name") val senderName: String,
    @SerialName("source_lang") val sourceLang: String = "en-IN",
    @SerialName("original_text") val originalText: String,
    @SerialName("translated_text") val translatedText: String? = null,
    @SerialName("is_translated") val isTranslated: Boolean = false,
    @SerialName("audio_id") val audioId: String? = null,
    @SerialName("audio_url") val audioUrl: String? = null,
    @SerialName("duration_ms") val durationMs: Long = 0,
    @SerialName("created_at") val createdAt: Double = 0.0,
    val status: String? = null, // my messages only: sent | delivered | read
    val deleted: Boolean = false, // deleted for everyone by the sender
)

@Serializable
data class Conversation(
    val id: String,
    @SerialName("is_group") val isGroup: Boolean = false,
    val name: String? = null,
    @SerialName("created_by") val createdBy: String? = null,
    @SerialName("created_at") val createdAt: Double = 0.0,
    @SerialName("updated_at") val updatedAt: Double = 0.0,
    val members: List<ConversationMember> = emptyList(),
    @SerialName("member_count") val memberCount: Int = 0,
    val peer: ConversationMember? = null,
    @SerialName("other_user") val otherUser: User? = null,
    @SerialName("last_message") val lastMessage: ChatMessage? = null,
    @SerialName("unread_count") val unreadCount: Int = 0,
)

@Serializable
data class ConversationsResponse(val conversations: List<Conversation>)

@Serializable
data class SingleConversationResponse(val conversation: Conversation)

@Serializable
data class ChatMessagesResponse(val messages: List<ChatMessage>)

@Serializable
data class SendMessageResponse(val message: ChatMessage)

@Serializable
data class ContactUser(
    val id: String,
    val name: String,
    val username: String? = null,
    val language: String = "ta-IN",
    @SerialName("is_demo") val isDemo: Boolean = false,
)

@Serializable
data class ContactUsersResponse(val contacts: List<ContactUser>)

@Serializable
data class MatchedContact(
    val id: String,
    val name: String,
    val username: String? = null,
    val language: String = "ta-IN",
    @SerialName("phone_hash") val phoneHash: String? = null,
)

@Serializable
data class MatchPhonesResponse(val matches: List<MatchedContact>)
