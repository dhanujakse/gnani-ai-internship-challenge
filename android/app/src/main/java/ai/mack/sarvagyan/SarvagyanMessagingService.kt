package ai.mack.sarvagyan

import com.google.firebase.messaging.FirebaseMessagingService
import com.google.firebase.messaging.RemoteMessage
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.launch

/**
 * Pushes from the server (Firebase Cloud Messaging) while the app is closed or in the background. The server sends
 * data-only messages with a `type`, and the app builds the notification itself: a ringing call, a missed call,
 * someone added you, or a message. Needs Firebase configured (android/app/google-services.json).
 */
class SarvagyanMessagingService : FirebaseMessagingService() {
    private val serviceScope = CoroutineScope(SupervisorJob() + Dispatchers.IO)

    override fun onNewToken(token: String) {
        super.onNewToken(token)
        val c = applicationContext.container
        if (c.user.value != null) {
            serviceScope.launch { runCatching { c.api.registerPushToken(token) } }
        }
    }

    override fun onMessageReceived(message: RemoteMessage) {
        super.onMessageReceived(message)
        val data = message.data
        val c = applicationContext.container
        val title = message.notification?.title ?: data["title"] ?: "Sarvagyan"
        val body = message.notification?.body ?: data["body"] ?: "New message"
        when (data["type"]) {
            "incoming_call" -> {
                val callId = data["call_id"] ?: return
                c.ringFromPush(callId, data["user_id"] ?: "", title, data["language"] ?: "en-IN",
                    data["expires_in"]?.toIntOrNull() ?: 40)
            }
            "missed_call" -> c.notifier.missedCall(data["call_id"] ?: return, body)
            "contact_added" -> c.notifier.contactAdded(data["user_id"] ?: return, title)
            else -> {
                val conversationId = data["conversation_id"]
                if (conversationId != null && conversationId == c.appSocket.focusedConversation) return
                c.notifier.message(conversationId, title, body)
            }
        }
    }
}
