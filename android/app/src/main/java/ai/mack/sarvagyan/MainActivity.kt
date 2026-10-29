package ai.mack.sarvagyan

import android.content.Intent
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.material3.MaterialTheme
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.ui.Modifier
import androidx.core.splashscreen.SplashScreen.Companion.installSplashScreen
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.navigation.compose.rememberNavController
import ai.mack.sarvagyan.data.normaliseCode
import ai.mack.sarvagyan.ui.AppNav
import ai.mack.sarvagyan.ui.theme.SarvagyanTheme

class MainActivity : ComponentActivity() {
    private val pendingJoin = mutableStateOf<String?>(null)

    override fun onCreate(savedInstanceState: Bundle?) {
        installSplashScreen()
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        handleIntent(intent)
        setContent {
            val settings by container.settings.collectAsStateWithLifecycle()
            SarvagyanTheme(mode = settings.theme) {
                Box(Modifier.fillMaxSize().background(MaterialTheme.colorScheme.background)) {
                    AppNav(rememberNavController(), pendingJoin.value, onJoinCodeConsumed = { pendingJoin.value = null })
                }
            }
        }
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        handleIntent(intent)
    }

    /** sarvagyan://join/ABC234  or  https://sarvagyan.app/join/ABC234 */
    private fun handleIntent(intent: Intent?) {
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
