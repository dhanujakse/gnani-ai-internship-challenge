package ai.mack.sarvagyan.call

import ai.mack.sarvagyan.container
import com.google.firebase.messaging.FirebaseMessagingService
import com.google.firebase.messaging.RemoteMessage
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.buildJsonObject

/**
 * Firebase Cloud Messaging: wakes the app for an incoming call even when it is closed.
 * The server sends small data-only messages (no conversation content): who is calling and the call id, and later
 * that the ringing stopped. They go through the same handler as the live connection's events, so a call that
 * arrives both ways rings once.
 */
class PushService : FirebaseMessagingService() {
    override fun onNewToken(token: String) {
        applicationContext.container.registerPushToken(token)
    }

    override fun onMessageReceived(message: RemoteMessage) {
        val d = message.data
        val type = d["type"] ?: return
        val callId = d["call_id"] ?: return
        // a push that arrives after the ringing would have stopped is ignored
        val sentAt = d["sent_at"]?.toDoubleOrNull()
        val expiresIn = d["expires_in"]?.toIntOrNull() ?: 30
        if (type == "incoming_call" && sentAt != null && System.currentTimeMillis() / 1000.0 - sentAt > expiresIn) return
        val ev: JsonObject = buildJsonObject {
            put("type", JsonPrimitive(type))
            put("call_id", JsonPrimitive(callId))
            d["reason"]?.let { put("reason", JsonPrimitive(it)) }
            if (type == "incoming_call") {
                put("expires_in", JsonPrimitive(expiresIn))
                put("from", buildJsonObject {
                    put("id", JsonPrimitive(d["from_id"] ?: return))
                    put("name", JsonPrimitive(d["from_name"] ?: "Someone"))
                    d["from_username"]?.takeIf { it.isNotEmpty() }?.let { put("username", JsonPrimitive(it)) }
                    put("language", JsonPrimitive(d["from_language"] ?: "en-IN"))
                })
            }
        }
        applicationContext.container.onPush(ev)
    }
}
