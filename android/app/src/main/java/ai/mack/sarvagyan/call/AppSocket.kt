package ai.mack.sarvagyan.call

import ai.mack.sarvagyan.data.ApiClient
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.SharedFlow
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonObject
import okhttp3.OkHttpClient

/**
 * The app's always-on connection while signed in: incoming calls ring through it, and the caller hears
 * whether the call was answered, declined or missed. Reconnects with back-off after network drops.
 * (When the app is fully closed, only a push notification can wake it; that needs Firebase, not set up yet.)
 */
class AppSocket(private val http: OkHttpClient, private val json: Json, private val api: ApiClient) {
    private val _events = MutableSharedFlow<JsonObject>(extraBufferCapacity = 32)
    val events: SharedFlow<JsonObject> = _events

    @Volatile var connected = false
        private set

    /** Runs until the calling coroutine is cancelled (sign-out). */
    suspend fun run() {
        var backoffMs = 1_000L
        while (true) {
            val token = api.freshToken()
            if (token == null) { delay(5_000); continue }
            val socket = CallSocket(http, json)
            try {
                socket.connect(api.appSocketUrl(), token).collect { ev ->
                    when (ev) {
                        SocketEvent.Open -> { connected = true; backoffMs = 1_000L }
                        is SocketEvent.Message -> _events.tryEmit(ev.json)
                        else -> Unit
                    }
                }
            } finally {
                connected = false
                socket.close()
            }
            delay(backoffMs)
            backoffMs = (backoffMs * 2).coerceAtMost(30_000L)
        }
    }
}

/** Someone is calling this phone. */
data class IncomingCall(
    val callId: String,
    val fromId: String,
    val fromName: String,
    val fromUsername: String?,
    val fromLanguage: String,
    val expiresInS: Int,
)
