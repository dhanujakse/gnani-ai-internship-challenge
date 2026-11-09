package ai.mack.sarvagyan.ui.screens

import androidx.activity.compose.BackHandler
import androidx.compose.foundation.clickable
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Lock
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import ai.mack.sarvagyan.ui.components.EmeraldAnimatedBackground
import ai.mack.sarvagyan.ui.components.LogoMark
import ai.mack.sarvagyan.ui.components.PrimaryButton

/** Covers the whole app until the phone's fingerprint, face or PIN check succeeds. */
@Composable
fun LockScreen(onUnlock: () -> Unit) {
    BackHandler { } // the app stays covered
    EmeraldAnimatedBackground {
        Column(
            Modifier.fillMaxSize()
                .clickable(remember { MutableInteractionSource() }, indication = null) { } // nothing underneath is tappable
                .padding(32.dp),
            verticalArrangement = Arrangement.Center, horizontalAlignment = Alignment.CenterHorizontally,
        ) {
            LogoMark(96.dp, animated = false)
            Spacer(Modifier.height(24.dp))
            Text("Sarvagyan is locked", style = MaterialTheme.typography.headlineSmall)
            Spacer(Modifier.height(8.dp))
            Text("Unlock with your fingerprint, face or phone PIN.", color = MaterialTheme.colorScheme.onSurfaceVariant)
            Spacer(Modifier.height(32.dp))
            PrimaryButton("Unlock", onUnlock, icon = Icons.Filled.Lock)
        }
    }
}
