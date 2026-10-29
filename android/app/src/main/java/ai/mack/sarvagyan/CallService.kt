package ai.mack.sarvagyan

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.content.pm.ServiceInfo
import android.os.Build
import androidx.core.app.NotificationCompat
import androidx.core.app.ServiceCompat
import androidx.core.content.ContextCompat
import androidx.lifecycle.LifecycleService
import androidx.lifecycle.lifecycleScope
import ai.mack.sarvagyan.call.CallStatus
import kotlinx.coroutines.flow.collectLatest
import kotlinx.coroutines.launch

/**
 * Keeps the call (and the microphone) alive while the app is in the background, with an ongoing
 * notification that makes it obvious the mic is in use. Stops itself when the call ends.
 */
class CallService : LifecycleService() {
    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        super.onStartCommand(intent, flags, startId)
        val type = if (Build.VERSION.SDK_INT >= 30) ServiceInfo.FOREGROUND_SERVICE_TYPE_MICROPHONE else 0
        runCatching { ServiceCompat.startForeground(this, NOTIFICATION_ID, notification(), type) }
            .onFailure { stopSelf(); return START_NOT_STICKY }
        lifecycleScope.launch {
            container.activeCall.collectLatest { session ->
                if (session == null) {
                    stopSelf()
                    return@collectLatest
                }
                session.state.collect { s -> if (s.status == CallStatus.Ended || s.status == CallStatus.Failed) stopSelf() }
            }
        }
        return START_NOT_STICKY
    }

    private fun notification(): Notification {
        val nm = getSystemService(NotificationManager::class.java)
        if (Build.VERSION.SDK_INT >= 26) {
            nm.createNotificationChannel(NotificationChannel(CHANNEL, "Active call", NotificationManager.IMPORTANCE_LOW).apply {
                description = "Shown while a Sarvagyan call is using the microphone"
            })
        }
        val open = PendingIntent.getActivity(
            this, 0, Intent(this, MainActivity::class.java).addFlags(Intent.FLAG_ACTIVITY_SINGLE_TOP),
            PendingIntent.FLAG_IMMUTABLE,
        )
        return NotificationCompat.Builder(this, CHANNEL)
            .setSmallIcon(R.drawable.ic_stat_call)
            .setContentTitle("Sarvagyan call in progress")
            .setContentText("Microphone on · live translation active")
            .setOngoing(true)
            .setCategory(NotificationCompat.CATEGORY_CALL)
            .setContentIntent(open)
            .build()
    }

    companion object {
        private const val CHANNEL = "active_call"
        private const val NOTIFICATION_ID = 41

        fun start(context: Context) {
            runCatching { ContextCompat.startForegroundService(context, Intent(context, CallService::class.java)) }
        }
    }
}
