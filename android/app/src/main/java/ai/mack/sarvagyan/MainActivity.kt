package ai.mack.sarvagyan

import android.Manifest
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build
import android.os.Bundle
import android.os.SystemClock
import android.view.WindowManager
import androidx.fragment.app.FragmentActivity
import androidx.compose.foundation.layout.Box
import androidx.lifecycle.lifecycleScope
import kotlinx.coroutines.launch
import ai.mack.sarvagyan.ui.screens.LockScreen
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.activity.result.contract.ActivityResultContracts
import androidx.activity.SystemBarStyle
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.ui.Modifier
import androidx.core.content.ContextCompat
import androidx.core.splashscreen.SplashScreen.Companion.installSplashScreen
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.navigation.compose.rememberNavController
import ai.mack.sarvagyan.data.normaliseCode
import ai.mack.sarvagyan.ui.AppNav
import ai.mack.sarvagyan.ui.theme.SarvagyanTheme
import ai.mack.sarvagyan.ui.theme.ThemeMode
import android.graphics.Color as AndroidColor

class MainActivity : FragmentActivity() { // FragmentActivity: needed by the fingerprint / PIN prompt
    private val pendingJoin = mutableStateOf<String?>(null)
    private val pendingConversation = mutableStateOf<String?>(null)
    private val pendingReturnToCall = mutableStateOf(false)
    private val locked = mutableStateOf(false)
    private var leftAt = 0L

    override fun onCreate(savedInstanceState: Bundle?) {
        installSplashScreen()
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        handleIntent(intent)
        // app lock: locked from the start when turned on
        lifecycleScope.launch { if (container.settingsStore.current().appLock) locked.value = true }
        setContent {
            val settings by container.settings.collectAsStateWithLifecycle()
            val dark = when (settings.theme) {
                ThemeMode.Dark -> true
                ThemeMode.Light -> false
                ThemeMode.System -> isSystemInDarkTheme()
            }
            LaunchedEffect(dark) {
                // light status/navigation bar icons on the dark theme, dark icons on the light theme
                val style = if (dark) SystemBarStyle.dark(AndroidColor.TRANSPARENT)
                else SystemBarStyle.light(AndroidColor.TRANSPARENT, AndroidColor.TRANSPARENT)
                enableEdgeToEdge(statusBarStyle = style, navigationBarStyle = style)
            }
            LaunchedEffect(settings.blockScreenshots) {
                if (settings.blockScreenshots) window.setFlags(WindowManager.LayoutParams.FLAG_SECURE, WindowManager.LayoutParams.FLAG_SECURE)
                else window.clearFlags(WindowManager.LayoutParams.FLAG_SECURE)
            }
            LaunchedEffect(locked.value) { if (locked.value) unlock() }

            // Ask for Notification permission on app entry (Android 13+ / API 33+)
            val notificationPermissionLauncher = rememberLauncherForActivityResult(
                ActivityResultContracts.RequestPermission()
            ) { isGranted ->
                if (isGranted) container.syncPushToken()
            }
            LaunchedEffect(Unit) {
                if (Build.VERSION.SDK_INT >= 33) {
                    if (ContextCompat.checkSelfPermission(this@MainActivity, Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED) {
                        notificationPermissionLauncher.launch(Manifest.permission.POST_NOTIFICATIONS)
                    } else {
                        container.syncPushToken()
                    }
                } else {
                    container.syncPushToken()
                }
            }

            SarvagyanTheme(mode = settings.theme) {
                // Surface provides the theme's content colour, so every Text defaults to readable colours
                Surface(Modifier.fillMaxSize(), color = MaterialTheme.colorScheme.background) {
                    Box(Modifier.fillMaxSize()) {
                        AppNav(
                            rememberNavController(),
                            pendingJoin.value,
                            onJoinCodeConsumed = { pendingJoin.value = null },
                            pendingConversationId = pendingConversation.value,
                            onConversationConsumed = { pendingConversation.value = null },
                            pendingReturnToCall = pendingReturnToCall.value,
                            onReturnToCallConsumed = { pendingReturnToCall.value = false },
                        )
                        if (locked.value) LockScreen(onUnlock = { unlock() })
                    }
                }
            }
        }
    }

    private fun unlock() = AppLock.prompt(this) { locked.value = false }

    override fun onStop() {
        super.onStop()
        leftAt = SystemClock.elapsedRealtime()
    }

    override fun onStart() {
        super.onStart()
        // back after more than 30 seconds away: lock again
        if (leftAt > 0 && SystemClock.elapsedRealtime() - leftAt > AppLock.RELOCK_AFTER_MS && container.settings.value.appLock) {
            locked.value = true
        }
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        handleIntent(intent)
    }

    /** sarvagyan://join/ABC234  or  https://sarvagyan.app/join/ABC234  or push notification extra conversation_id */
    private fun handleIntent(intent: Intent?) {
        if (intent?.action == "ai.mack.sarvagyan.RETURN_TO_CALL" || intent?.getBooleanExtra("return_to_call", false) == true) {
            pendingReturnToCall.value = true
        }
        intent?.getStringExtra("conversation_id")?.takeIf { it.isNotBlank() }?.let {
            pendingConversation.value = it
        }
        val data = intent?.data ?: return
        val segments = data.pathSegments.orEmpty()
        val code = when {
            data.scheme == "sarvagyan" && data.host == "join" -> segments.firstOrNull()
            segments.size >= 2 && segments[0] == "join" -> segments[1]
            else -> null
        }
        code?.let { pendingJoin.value = normaliseCode(it) }
    }
}
