package ai.mack.sarvagyan.data

import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.currentCoroutineContext
import kotlinx.coroutines.ensureActive
import kotlinx.coroutines.job
import kotlinx.coroutines.suspendCancellableCoroutine
import kotlinx.coroutines.withContext
import kotlinx.serialization.KSerializer
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.jsonObject
import okhttp3.Call
import okhttp3.Callback
import okhttp3.HttpUrl.Companion.toHttpUrl
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody
import okhttp3.RequestBody.Companion.toRequestBody
import okhttp3.Response
import java.io.IOException
import kotlin.coroutines.resume
import kotlin.coroutines.resumeWithException

/** A failure the UI can show as-is. `status` 0 means the server could not be reached. */
class ApiException(val status: Int, override val message: String) : Exception(message) {
    val isNetwork get() = status == 0
    val isAuth get() = status == 401
}

class ApiClient(
    private val http: OkHttpClient,
    private val json: Json,
    private val baseUrl: () -> String,
    private val token: () -> String?,
) {
    private val jsonType = "application/json".toMediaType()

    private suspend fun Call.await(): Response = suspendCancellableCoroutine { cont ->
        enqueue(object : Callback {
            override fun onFailure(call: Call, e: IOException) {
                if (!cont.isCancelled) cont.resumeWithException(e)
            }

            override fun onResponse(call: Call, response: Response) = cont.resume(response)
        })
        cont.invokeOnCancellation { cancel() }
    }

    private suspend fun <T> request(method: String, path: String, body: JsonObject?, serializer: KSerializer<T>): T {
        val reqBody = if (method == "GET") null else (body?.toString() ?: "{}").toRequestBody(jsonType)
        return send(method, baseUrl().trimEnd('/') + path, reqBody, serializer)
    }

    private fun authorised(url: String): Request.Builder {
        val builder = Request.Builder().url(url)
        token()?.let { builder.header("Authorization", "Bearer $it") }
        return builder
    }

    private suspend fun open(request: Request): Response = try {
        http.newCall(request).await()
    } catch (e: IOException) {
        throw ApiException(0, "Can't reach the Sarvagyan server. Check your connection.")
    }

    private suspend fun <T> send(method: String, url: String, body: RequestBody?, serializer: KSerializer<T>): T =
        withContext(Dispatchers.IO) {
            val response = open(authorised(url).method(method, body).build())
            response.use { r ->
                val text = r.body.string()
                if (!r.isSuccessful) throw ApiException(r.code, errorMessage(r.code, text))
                try {
                    json.decodeFromString(serializer, text)
                } catch (e: Exception) {
                    throw ApiException(r.code, "Unexpected response from the server.")
                }
            }
        }

    private fun errorMessage(code: Int, body: String): String {
        val detail = runCatching {
            val obj = json.parseToJsonElement(body).jsonObject
            val d = obj["detail"]
            if (d is JsonPrimitive) d.content else null
        }.getOrNull()
        return detail ?: when (code) {
            401 -> "Please sign in again."
            404 -> "Not found."
            409 -> "That is already in use."
            422 -> "Some details are not valid."
            429 -> "Too many requests. Please wait a moment."
            in 500..599 -> "The server had a problem. Please try again."
            else -> "Request failed ($code)."
        }
    }

    private fun obj(vararg pairs: Pair<String, Any?>) = buildJsonObject {
        for ((k, v) in pairs) when (v) {
            null -> Unit
            is String -> put(k, JsonPrimitive(v))
            is Number -> put(k, JsonPrimitive(v))
            is Boolean -> put(k, JsonPrimitive(v))
            else -> put(k, JsonPrimitive(v.toString()))
        }
    }

    suspend fun health(): Health = request("GET", "/health", null, Health.serializer())
    suspend fun register(email: String, password: String, name: String, username: String? = null): Session =
        request("POST", "/v1/auth/register", obj("email" to email, "password" to password, "display_name" to name, "username" to username), Session.serializer())
    suspend fun login(email: String, password: String): Session =
        request("POST", "/v1/auth/login", obj("email" to email, "password" to password), Session.serializer())
    suspend fun demo(name: String, username: String? = null): Session =
        request("POST", "/v1/auth/demo", obj("display_name" to name, "username" to username), Session.serializer())
    suspend fun me(): User = request("GET", "/v1/me", null, User.serializer())
    suspend fun updateMe(name: String? = null, language: String? = null, username: String? = null): User =
        request("PATCH", "/v1/me", obj("display_name" to name, "language" to language, "username" to username), User.serializer())

    suspend fun checkUsername(username: String): CheckUsernameResponse =
        request("GET", "/v1/users/check-username?username=$username", null, CheckUsernameResponse.serializer())

    suspend fun searchUsers(query: String): SearchUsersResponse =
        request("GET", "/v1/users/search?q=$query", null, SearchUsersResponse.serializer())
    suspend fun languages(): LanguagesResponse = request("GET", "/v1/languages", null, LanguagesResponse.serializer())
    suspend fun createCall(language: String): CallInfo = request("POST", "/v1/calls", obj("language" to language), CallInfo.serializer())
    suspend fun joinCall(code: String, language: String): CallInfo =
        request("POST", "/v1/calls/join", obj("code" to code, "language" to language), CallInfo.serializer())
    suspend fun history(): HistoryResponse = request("GET", "/v1/calls/history", null, HistoryResponse.serializer())
    suspend fun favourites(): ContactsResponse = request("GET", "/v1/contacts/favourites", null, ContactsResponse.serializer())
    suspend fun setFavourite(contactId: String, on: Boolean) {
        request(if (on) "PUT" else "DELETE", "/v1/contacts/favourites/$contactId", null, JsonObject.serializer())
    }
    suspend fun diagnostics(): JsonObject = request("GET", "/v1/diagnostics", null, JsonObject.serializer())

    /** Uploads a recording (16 kHz mono PCM s16le). The server translates it in the background. */
    suspend fun sendVoicemail(to: String, language: String, autoDetect: Boolean, pcm: ByteArray): SentVoicemail {
        val url = (baseUrl().trimEnd('/') + "/v1/voicemails").toHttpUrl().newBuilder()
            .addQueryParameter("to", to)
            .addQueryParameter("language", language)
            .addQueryParameter("auto_detect", autoDetect.toString())
            .build().toString()
        return send("POST", url, pcm.toRequestBody("application/octet-stream".toMediaType()), SentVoicemail.serializer())
    }
    suspend fun voicemails(): VoicemailsResponse = request("GET", "/v1/voicemails", null, VoicemailsResponse.serializer())
    suspend fun deleteVoicemail(id: String) {
        request("DELETE", "/v1/voicemails/$id", null, JsonObject.serializer())
    }

    /** Streams the translated voice (16 kHz mono PCM), generated by the server when asked. */
    suspend fun streamVoicemailAudio(id: String, onChunk: (ByteArray, Int) -> Unit) = withContext(Dispatchers.IO) {
        val call = http.newCall(authorised(baseUrl().trimEnd('/') + "/v1/voicemails/$id/audio").get().build())
        currentCoroutineContext().job.invokeOnCompletion { call.cancel() } // stops a blocking read on cancel
        val response = try {
            call.await()
        } catch (e: IOException) {
            throw ApiException(0, "Can't reach the Sarvagyan server. Check your connection.")
        }
        response.use { r ->
            if (!r.isSuccessful) throw ApiException(r.code, errorMessage(r.code, r.body.string()))
            val input = r.body.byteStream()
            val buf = ByteArray(8192)
            while (true) {
                currentCoroutineContext().ensureActive()
                val n = try { input.read(buf) } catch (e: IOException) { break }
                if (n < 0) break
                if (n > 0) onChunk(buf, n)
            }
        }
    }

    suspend fun conversations(): ConversationsResponse =
        request("GET", "/v1/chat/conversations", null, ConversationsResponse.serializer())

    suspend fun directChat(username: String? = null, userId: String? = null): SingleConversationResponse =
        request("POST", "/v1/chat/direct", obj("username" to username, "user_id" to userId), SingleConversationResponse.serializer())

    suspend fun createGroup(name: String, memberIds: List<String>): SingleConversationResponse {
        val jsonArray = kotlinx.serialization.json.buildJsonArray {
            memberIds.forEach { add(JsonPrimitive(it)) }
        }
        val body = buildJsonObject {
            put("name", JsonPrimitive(name))
            put("member_ids", jsonArray)
        }
        return send("POST", baseUrl().trimEnd('/') + "/v1/chat/groups", body.toString().toRequestBody(jsonType), SingleConversationResponse.serializer())
    }

    suspend fun conversation(id: String): SingleConversationResponse =
        request("GET", "/v1/chat/conversations/$id", null, SingleConversationResponse.serializer())

    suspend fun chatMessages(conversationId: String, limit: Int = 50, before: Double? = null): ChatMessagesResponse {
        val path = if (before != null) "/v1/chat/conversations/$conversationId/messages?limit=$limit&before=$before"
        else "/v1/chat/conversations/$conversationId/messages?limit=$limit"
        return request("GET", path, null, ChatMessagesResponse.serializer())
    }

    suspend fun sendChatMessage(conversationId: String, text: String, language: String? = null): SendMessageResponse =
        request("POST", "/v1/chat/conversations/$conversationId/messages", obj("text" to text, "language" to language), SendMessageResponse.serializer())

    suspend fun sendChatVoice(conversationId: String, language: String, pcm: ByteArray): SendMessageResponse {
        val url = (baseUrl().trimEnd('/') + "/v1/chat/conversations/$conversationId/voice").toHttpUrl().newBuilder()
            .addQueryParameter("language", language)
            .build().toString()
        return send("POST", url, pcm.toRequestBody("application/octet-stream".toMediaType()), SendMessageResponse.serializer())
    }

    suspend fun streamChatAudio(audioId: String, onChunk: (ByteArray, Int) -> Unit) = withContext(Dispatchers.IO) {
        val call = http.newCall(authorised(baseUrl().trimEnd('/') + "/v1/chat/audio/$audioId").get().build())
        currentCoroutineContext().job.invokeOnCompletion { call.cancel() }
        val response = try {
            call.await()
        } catch (e: IOException) {
            throw ApiException(0, "Can't reach the Sarvagyan server. Check your connection.")
        }
        response.use { r ->
            if (!r.isSuccessful) throw ApiException(r.code, errorMessage(r.code, r.body.string()))
            val input = r.body.byteStream()
            val buf = ByteArray(8192)
            while (true) {
                currentCoroutineContext().ensureActive()
                val n = try { input.read(buf) } catch (e: IOException) { break }
                if (n < 0) break
                if (n > 0) onChunk(buf, n)
            }
        }
    }

    fun chatWebSocketUrl(): String =
        baseUrl().trimEnd('/').replaceFirst("https://", "wss://").replaceFirst("http://", "ws://") + "/v1/chat/ws"

    fun webSocketUrl(callId: String): String =
        baseUrl().trimEnd('/').replaceFirst("https://", "wss://").replaceFirst("http://", "ws://") + "/v1/calls/$callId/ws"

    fun currentToken(): String? = token()
}

fun JsonObject.str(key: String): String? = (this[key] as? JsonPrimitive)?.takeIf { it.isString }?.content
fun JsonObject.bool(key: String): Boolean? = (this[key] as? JsonPrimitive)?.content?.toBooleanStrictOrNull()
fun JsonObject.int(key: String): Int? = (this[key] as? JsonPrimitive)?.content?.toDoubleOrNull()?.toInt()
fun JsonObject.objOrNull(key: String): JsonObject? = this[key] as? JsonObject
