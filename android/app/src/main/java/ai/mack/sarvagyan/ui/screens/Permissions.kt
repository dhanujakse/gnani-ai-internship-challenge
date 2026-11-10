package ai.mack.sarvagyan.ui.screens

import android.Manifest
import android.app.NotificationManager
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Build
import android.provider.Settings
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.NotificationsActive
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.lifecycle.compose.LocalLifecycleOwner
import androidx.compose.ui.unit.dp
import androidx.core.content.ContextCompat
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleEventObserver
import ai.mack.sarvagyan.ui.components.AppCard
import ai.mack.sarvagyan.ui.components.SecondaryButton

private fun granted(context: Context, permission: String) =
    ContextCompat.checkSelfPermission(context, permission) == PackageManager.PERMISSION_GRANTED

/** What incoming calls still need from this phone, re-checked every time the app comes back to the front. */
data class CallReadiness(val notifications: Boolean, val fullScreen: Boolean, val microphone: Boolean) {
    val ready get() = notifications && fullScreen && microphone
}

fun callReadiness(context: Context): CallReadiness {
    val notifications = Build.VERSION.SDK_INT < 33 || granted(context, Manifest.permission.POST_NOTIFICATIONS)
    // Android 14+: showing an incoming call over the lock screen needs this separate permission
    val fullScreen = Build.VERSION.SDK_INT < 34 ||
        context.getSystemService(NotificationManager::class.java)?.canUseFullScreenIntent() != false
    return CallReadiness(notifications, fullScreen, granted(context, Manifest.permission.RECORD_AUDIO))
}

/**
 * Asks, once per app start, for what receiving calls needs: notifications (the ringing call alert) and the
 * microphone (to answer). Without them a call to this phone would ring silently or fail to connect.
 * Then shows a card while anything is still missing, with a button to fix it.
 */
@Composable
fun CallPermissionsCard() {
    val context = LocalContext.current
    var tick by remember { mutableIntStateOf(0) }
    val readiness = remember(tick) { callReadiness(context) }
    var asked by rememberSaveable { mutableStateOf(false) }
    val launcher = rememberLauncherForActivityResult(ActivityResultContracts.RequestMultiplePermissions()) { tick++ }

    LaunchedEffect(Unit) {
        if (asked) return@LaunchedEffect
        asked = true
        val missing = buildList {
            if (Build.VERSION.SDK_INT >= 33 && !granted(context, Manifest.permission.POST_NOTIFICATIONS)) add(Manifest.permission.POST_NOTIFICATIONS)
            if (!granted(context, Manifest.permission.RECORD_AUDIO)) add(Manifest.permission.RECORD_AUDIO)
        }
        if (missing.isNotEmpty()) launcher.launch(missing.toTypedArray())
    }
    // re-check when the user comes back from the system settings
    val owner = LocalLifecycleOwner.current
    DisposableEffect(owner) {
        val obs = LifecycleEventObserver { _, e -> if (e == Lifecycle.Event.ON_RESUME) tick++ }
        owner.lifecycle.addObserver(obs)
        onDispose { owner.lifecycle.removeObserver(obs) }
    }

    if (readiness.ready) return
    AppCard {
        Column(Modifier.fillMaxWidth()) {
            Text("Let calls reach you", style = MaterialTheme.typography.titleMedium)
            Spacer(Modifier.height(4.dp))
            val needs = buildList {
                if (!readiness.notifications) add("notifications, so incoming calls ring")
                if (!readiness.fullScreen) add("full-screen alerts, so calls show over the lock screen")
                if (!readiness.microphone) add("the microphone, so you can answer")
            }
            Text("Sarvagyan needs " + needs.joinToString("; ") + ".",
                style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
            Spacer(Modifier.height(8.dp))
            SecondaryButton("Turn on", {
                val intent = if (!readiness.fullScreen && readiness.notifications && Build.VERSION.SDK_INT >= 34)
                    Intent(Settings.ACTION_MANAGE_APP_USE_FULL_SCREEN_INTENT, Uri.parse("package:${context.packageName}"))
                else Intent(Settings.ACTION_APPLICATION_DETAILS_SETTINGS, Uri.parse("package:${context.packageName}"))
                runCatching { context.startActivity(intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)) }
            }, Modifier.fillMaxWidth(), icon = Icons.Filled.NotificationsActive)
        }
    }
}
