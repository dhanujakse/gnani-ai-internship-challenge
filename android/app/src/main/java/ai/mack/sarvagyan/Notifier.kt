package ai.mack.sarvagyan

import android.Manifest
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build
import androidx.core.app.NotificationCompat
import androidx.core.content.ContextCompat

/**
 * Message, missed-call and new-contact notifications. Both the app's live connection (app running) and the push
 * service (app closed) post through here with the same ids, so one event never shows twice. Ringing calls have
 * their own full-screen notification (call/Ringer.kt).
 */
class Notifier(private val context: Context) {
    private val nm = context.getSystemService(NotificationManager::class.java)

    init {
        nm?.createNotificationChannels(listOf(
            NotificationChannel(CH_MESSAGES, "Messages", NotificationManager.IMPORTANCE_HIGH).apply {
                description = "New messages, voice messages and voicemails"
            },
            NotificationChannel(CH_MISSED, "Missed calls", NotificationManager.IMPORTANCE_HIGH).apply {
                description = "Calls you didn't answer"
            },
            NotificationChannel(CH_CONTACTS, "New contacts", NotificationManager.IMPORTANCE_DEFAULT).apply {
                description = "When someone adds you as a contact"
            },
        ))
    }

    private fun allowed(): Boolean = Build.VERSION.SDK_INT < 33 ||
        ContextCompat.checkSelfPermission(context, Manifest.permission.POST_NOTIFICATIONS) == PackageManager.PERMISSION_GRANTED

    private fun open(requestCode: Int, extras: Map<String, String> = emptyMap()): PendingIntent {
        val intent = Intent(context, MainActivity::class.java).apply {
            flags = Intent.FLAG_ACTIVITY_SINGLE_TOP or Intent.FLAG_ACTIVITY_CLEAR_TOP
            extras.forEach { (k, v) -> putExtra(k, v) }
        }
        return PendingIntent.getActivity(context, requestCode, intent, PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE)
    }

    private fun post(id: Int, channel: String, title: String, body: String, category: String, tap: PendingIntent) {
        if (!allowed()) return
        val n = NotificationCompat.Builder(context, channel)
            .setSmallIcon(R.mipmap.ic_launcher)
            .setContentTitle(title)
            .setContentText(body)
            .setStyle(NotificationCompat.BigTextStyle().bigText(body))
            .setCategory(category)
            .setPriority(NotificationCompat.PRIORITY_HIGH)
            .setAutoCancel(true)
            .setContentIntent(tap)
            .build()
        runCatching { nm?.notify(id, n) }
    }

    fun message(conversationId: String?, title: String, body: String) {
        val id = messageId(conversationId ?: title)
        val extras = if (conversationId.isNullOrBlank()) emptyMap() else mapOf("conversation_id" to conversationId)
        post(id, CH_MESSAGES, title, body, NotificationCompat.CATEGORY_MESSAGE, open(id, extras))
    }

    fun missedCall(callId: String, callerName: String) {
        val id = "missed:$callId".hashCode()
        post(id, CH_MISSED, "Missed call", callerName, NotificationCompat.CATEGORY_MISSED_CALL, open(id))
    }

    fun contactAdded(userId: String, name: String) {
        val id = "contact:$userId".hashCode()
        post(id, CH_CONTACTS, name, "Added you as a contact on Sarvagyan", NotificationCompat.CATEGORY_SOCIAL, open(id))
    }

    /** The chat was opened: its notification is no longer news. */
    fun clearMessages(conversationId: String) {
        runCatching { nm?.cancel(messageId(conversationId)) }
    }

    companion object {
        const val CH_MESSAGES = "chat_messages" // same id as before, so people's channel settings are kept
        const val CH_MISSED = "missed_calls"
        const val CH_CONTACTS = "new_contacts"
        fun messageId(key: String) = key.hashCode()
    }
}
