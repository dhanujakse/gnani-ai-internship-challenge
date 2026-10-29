package ai.mack.sarvagyan.call

import kotlinx.coroutines.channels.Channel
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.receiveAsFlow
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.jsonObject
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.Response
import okhttp3.WebSocket
import okhttp3.WebSocketListener
import okio.ByteString
import okio.ByteString.Companion.toByteString

sealed interface SocketEvent {
    data object Open : SocketEvent
    data class Message(val json: JsonObject) : SocketEvent
    class Audio(val data: ByteArray) : SocketEvent
    data class Closed(val code: Int, val reason: String) : SocketEvent
    data class Failure(val message: String, val httpCode: Int?) : SocketEvent
}

/**
 * One WebSocket to the Sarvagyan server per call: JSON events both ways, mic PCM up, translated PCM down.
 * The token goes in the Authorization header (never in the URL, which could end up in logs).
 */
class CallSocket(private val http: OkHttpClient, private val json: Json) {
    private var ws: WebSocket? = null
    private var events = Channel<SocketEvent>(Channel.UNLIMITED)

    fun connect(url: String, token: String): Flow<SocketEvent> {
        close(1000, "reconnect")
        val channel = Channel<SocketEvent>(Channel.UNLIMITED)
        events = channel
        val request = Request.Builder().url(url).header("Authorization", "Bearer $token").build()
        ws = http.newWebSocket(request, object : WebSocketListener() {
            override fun onOpen(webSocket: WebSocket, response: Response) {
                channel.trySend(SocketEvent.Open)
            }

            override fun onMessage(webSocket: WebSocket, text: String) {
                runCatching { json.parseToJsonElement(text).jsonObject }.getOrNull()?.let { channel.trySend(SocketEvent.Message(it)) }
            }

            override fun onMessage(webSocket: WebSocket, bytes: ByteString) {
                channel.trySend(SocketEvent.Audio(bytes.toByteArray()))
            }

            override fun onClosing(webSocket: WebSocket, code: Int, reason: String) {
                webSocket.close(code, null)
            }

            override fun onClosed(webSocket: WebSocket, code: Int, reason: String) {
                channel.trySend(SocketEvent.Closed(code, reason))
                channel.close()
            }

            override fun onFailure(webSocket: WebSocket, t: Throwable, response: Response?) {
                channel.trySend(SocketEvent.Failure(t.message ?: "connection failed", response?.code))
                channel.close()
            }
        })
        return channel.receiveAsFlow()
    }

    fun send(obj: JsonObject): Boolean = ws?.send(obj.toString()) ?: false

    /** Mic frames are dropped rather than queued if the network falls behind (stay real-time). */
    fun sendAudio(frame: ByteArray): Boolean {
        val socket = ws ?: return false
        if (socket.queueSize() > 64 * 1024) return false
        return socket.send(frame.toByteString())
    }

    fun close(code: Int = 1000, reason: String = "bye") {
        ws?.close(code, reason)
        ws = null
    }
}
