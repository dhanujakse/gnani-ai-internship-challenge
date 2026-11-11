package ai.mack.sarvagyan.ui.screens

import android.net.Uri
import android.widget.Toast
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.PickVisualMediaRequest
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.safeDrawingPadding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.PhotoLibrary
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import ai.mack.sarvagyan.container
import ai.mack.sarvagyan.data.ApiException
import ai.mack.sarvagyan.data.AvatarEntry
import ai.mack.sarvagyan.data.AvatarStore
import ai.mack.sarvagyan.ui.components.Avatar
import ai.mack.sarvagyan.ui.components.ErrorBanner
import ai.mack.sarvagyan.ui.components.PrimaryButton
import ai.mack.sarvagyan.ui.components.SecondaryButton
import ai.mack.sarvagyan.ui.theme.LocalCallColors
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

@Composable
fun ChooseAvatarScreen(
    isOnboarding: Boolean,
    onDone: () -> Unit,
) {
    val context = LocalContext.current
    val c = context.container
    val scope = rememberCoroutineScope()
    val user by c.user.collectAsStateWithLifecycle()
    val entries = remember { c.avatars.catalog() }
    var busy by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf<String?>(null) }

    fun selectPreset(entry: AvatarEntry) {
        if (busy) return
        busy = true
        error = null
        scope.launch {
            try {
                val updated = c.api.updateMe(avatar = entry.id)
                c.user.value = updated
            } catch (e: Exception) {
                error = (e as? ApiException)?.message ?: e.message
            } finally {
                busy = false
            }
        }
    }

    fun clearAvatar() {
        if (busy) return
        busy = true
        error = null
        scope.launch {
            try {
                val updated = c.api.updateMe(avatar = "")
                c.user.value = updated
            } catch (e: Exception) {
                error = (e as? ApiException)?.message ?: e.message
            } finally {
                busy = false
            }
        }
    }

    fun uploadPhoto(uri: Uri) {
        if (busy) return
        busy = true
        error = null
        scope.launch {
            try {
                val bytes = withContext(Dispatchers.IO) { AvatarStore.prepareAvatarUpload(context, uri) }
                val updated = c.api.uploadAvatar(bytes)
                c.user.value = updated
                Toast.makeText(context, "Profile photo updated!", Toast.LENGTH_SHORT).show()
            } catch (e: Exception) {
                error = (e as? ApiException)?.message ?: e.message ?: "Could not upload photo."
            } finally {
                busy = false
            }
        }
    }

    val photoPicker = rememberLauncherForActivityResult(ActivityResultContracts.PickVisualMedia()) { uri ->
        if (uri != null) uploadPhoto(uri)
    }

    Column(
        Modifier
            .fillMaxSize()
            .safeDrawingPadding()
            .verticalScroll(rememberScrollState())
            .padding(24.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.CenterVertically) {
            Text(if (isOnboarding) "Choose your avatar" else "Profile avatar", style = MaterialTheme.typography.headlineSmall)
            if (isOnboarding) {
                TextButton(onClick = onDone, enabled = !busy) { Text("Skip") }
            }
        }
        Spacer(Modifier.height(16.dp))

        Box(contentAlignment = Alignment.Center) {
            Avatar(
                name = user?.displayName ?: "User",
                color = LocalCallColors.current.me,
                size = 112.dp,
                avatar = user?.avatar,
                useMain = true,
            )
            if (busy) {
                CircularProgressIndicator(Modifier.size(36.dp))
            }
        }
        Spacer(Modifier.height(16.dp))

        Row(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalAlignment = Alignment.CenterVertically) {
            SecondaryButton("Upload a photo", {
                photoPicker.launch(PickVisualMediaRequest(ActivityResultContracts.PickVisualMedia.ImageOnly))
            }, enabled = !busy, icon = Icons.Filled.PhotoLibrary)
            if (!user?.avatar.isNullOrBlank()) {
                TextButton(onClick = { clearAvatar() }, enabled = !busy) {
                    Text("Use initials")
                }
            }
        }

        error?.let {
            Spacer(Modifier.height(12.dp))
            ErrorBanner(it, onDismiss = { error = null })
        }

        Spacer(Modifier.height(20.dp))

        // Plain uniform grid of all avatars from avatars.json — no sections, filters, or labels
        val rows = remember(entries) { entries.chunked(4) }
        Column(verticalArrangement = Arrangement.spacedBy(12.dp), modifier = Modifier.fillMaxWidth()) {
            rows.forEachIndexed { rowIdx, rowEntries ->
                Row(
                    Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceEvenly,
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    for (colIdx in 0 until 4) {
                        val entry = rowEntries.getOrNull(colIdx)
                        if (entry == null) {
                            Spacer(Modifier.size(72.dp))
                        } else {
                            val number = rowIdx * 4 + colIdx + 1
                            val label = "Avatar $number"
                            val selected = user?.avatar == entry.id
                            Box(
                                Modifier
                                    .size(72.dp)
                                    .clip(CircleShape)
                                    .border(
                                        width = if (selected) 3.dp else 1.dp,
                                        color = if (selected) MaterialTheme.colorScheme.primary else Color.Transparent,
                                        shape = CircleShape,
                                    )
                                    .clickable(enabled = !busy, role = Role.Button) { selectPreset(entry) }
                                    .semantics { contentDescription = label }
                                    .padding(3.dp),
                                contentAlignment = Alignment.Center,
                            ) {
                                Avatar(
                                    name = label,
                                    color = LocalCallColors.current.me,
                                    size = 64.dp,
                                    avatar = entry.id,
                                    useMain = false,
                                    contentDescription = label,
                                )
                            }
                        }
                    }
                }
            }
        }

        Spacer(Modifier.height(24.dp))
        PrimaryButton(
            text = if (isOnboarding) "Continue" else "Done",
            onClick = onDone,
            modifier = Modifier.fillMaxWidth(),
            enabled = !busy,
        )
        Spacer(Modifier.height(16.dp))
    }
}

