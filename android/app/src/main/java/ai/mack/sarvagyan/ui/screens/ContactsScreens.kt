package ai.mack.sarvagyan.ui.screens

import android.Manifest
import android.content.pm.PackageManager
import android.widget.Toast
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
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
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Call
import androidx.compose.material.icons.filled.CallEnd
import androidx.compose.material.icons.filled.MoreVert
import androidx.compose.material.icons.filled.PersonAdd
import androidx.compose.material.icons.filled.People
import androidx.compose.material.icons.filled.Voicemail
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.FilterChip
import androidx.compose.material3.FloatingActionButton
import androidx.compose.material3.FloatingActionButtonDefaults
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.core.content.ContextCompat
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import ai.mack.sarvagyan.call.IncomingCall
import ai.mack.sarvagyan.container
import ai.mack.sarvagyan.data.ApiException
import ai.mack.sarvagyan.data.ContactUser
import ai.mack.sarvagyan.ui.components.AppCard
import ai.mack.sarvagyan.ui.components.Avatar
import ai.mack.sarvagyan.ui.components.EmeraldAnimatedBackground
import ai.mack.sarvagyan.ui.components.EmptyState
import ai.mack.sarvagyan.ui.components.ErrorBanner
import ai.mack.sarvagyan.ui.components.SectionTitle
import ai.mack.sarvagyan.ui.theme.LocalCallColors
import kotlinx.coroutines.launch

/**
 * Starts a ringing call to a person (asks for the microphone first). Returns a function (id, name) -> Unit;
 * [onStarted] runs once the call is placed, to open the call screen.
 */
@Composable
fun rememberPlaceCall(onStarted: () -> Unit): (String, String) -> Unit {
    val context = LocalContext.current
    val c = context.container
    val scope = rememberCoroutineScope()
    var pending by remember { mutableStateOf<Pair<String, String>?>(null) }
    fun place(id: String, name: String) {
        scope.launch {
            try {
                c.callPerson(id, name)
                onStarted()
            } catch (e: ApiException) {
                Toast.makeText(context, e.message, Toast.LENGTH_LONG).show()
            }
        }
    }
    val permission = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { ok ->
        val p = pending
        pending = null
        if (ok && p != null) place(p.first, p.second)
        else if (!ok) Toast.makeText(context, "Sarvagyan needs the microphone for calls.", Toast.LENGTH_LONG).show()
    }
    return { id, name ->
        if (ContextCompat.checkSelfPermission(context, Manifest.permission.RECORD_AUDIO) == PackageManager.PERMISSION_GRANTED) place(id, name)
        else { pending = id to name; permission.launch(Manifest.permission.RECORD_AUDIO) }
    }
}

@Composable
fun ContactsScreen(onBack: () -> Unit, onCallStarted: () -> Unit, onVoicemail: (String, String) -> Unit) {
    val c = LocalContext.current.container
    val scope = rememberCoroutineScope()
    val user by c.user.collectAsStateWithLifecycle()
    var contacts by remember { mutableStateOf<List<ContactUser>?>(null) }
    var blocked by remember { mutableStateOf<List<ContactUser>>(emptyList()) }
    var username by remember { mutableStateOf("") }
    var error by remember { mutableStateOf<String?>(null) }
    var adding by remember { mutableStateOf(false) }
    val placeCall = rememberPlaceCall(onCallStarted)

    suspend fun load() {
        try {
            contacts = c.api.contacts().contacts
            blocked = c.api.blockedContacts().contacts
            error = null
        } catch (e: ApiException) {
            error = e.message
            if (contacts == null) contacts = emptyList()
        }
    }
    LaunchedEffect(Unit) { load() }

    fun add() {
        val name = username.trim().removePrefix("@")
        if (name.isEmpty()) return
        adding = true
        scope.launch {
            try { c.api.addContact(name); username = ""; load() } catch (e: ApiException) { error = e.message } finally { adding = false }
        }
    }

    ScreenScaffold("Contacts", onBack) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            OutlinedTextField(
                username, { username = it.filter { ch -> ch.isLetterOrDigit() || ch == '_' || ch == '@' }.take(25) },
                label = { Text("Add by @username") }, singleLine = true, modifier = Modifier.weight(1f),
                keyboardOptions = KeyboardOptions(imeAction = ImeAction.Done), keyboardActions = KeyboardActions(onDone = { add() }),
            )
            Spacer(Modifier.width(8.dp))
            IconButton(onClick = { add() }, enabled = username.isNotBlank() && !adding) { Icon(Icons.Filled.PersonAdd, "Add contact") }
        }
        error?.let { Spacer(Modifier.height(8.dp)); ErrorBanner(it, onDismiss = { error = null }) }

        SectionTitle("Your contacts")
        val list = contacts
        when {
            list == null -> Text("Loading…", color = MaterialTheme.colorScheme.onSurfaceVariant)
            list.isEmpty() -> EmptyState(Icons.Filled.People, "No contacts yet",
                "Add people by their @username. Contacts can call you; others can't, unless you allow everyone below.")
            else -> list.forEach { p ->
                PersonRow(p, c.language(p.language)?.name ?: p.language,
                    onCall = { placeCall(p.id, p.name) },
                    onVoicemail = { onVoicemail(p.id, p.name) },
                    menu = listOf(
                        "Remove from contacts" to { scope.launch { runCatching { c.api.removeContact(p.id) }; load() } },
                        "Block" to { scope.launch { runCatching { c.api.block(p.id) }; load() } },
                    ))
            }
        }

        SectionTitle("Who can call me")
        AppCard {
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                listOf("contacts" to "My contacts", "everyone" to "Everyone").forEach { (value, label) ->
                    FilterChip(selected = (user?.allowCalls ?: "contacts") == value, onClick = {
                        scope.launch {
                            try { c.user.value = c.api.updateMe(allowCalls = value) } catch (e: ApiException) { error = e.message }
                        }
                    }, label = { Text(label) })
                }
            }
            Text("People you've already had a call with can always call you back. Blocked people never can.",
                style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }

        if (blocked.isNotEmpty()) {
            SectionTitle("Blocked")
            blocked.forEach { p ->
                Row(Modifier.fillMaxWidth().padding(vertical = 4.dp), verticalAlignment = Alignment.CenterVertically) {
                    Avatar(p.name, MaterialTheme.colorScheme.onSurfaceVariant, 36.dp)
                    Spacer(Modifier.width(12.dp))
                    Text(p.name, Modifier.weight(1f))
                    TextButton(onClick = { scope.launch { runCatching { c.api.unblock(p.id) }; load() } }) { Text("Unblock") }
                }
            }
        }
        Spacer(Modifier.height(24.dp))
    }
}

@Composable
private fun PersonRow(p: ContactUser, language: String, onCall: () -> Unit, onVoicemail: () -> Unit, menu: List<Pair<String, () -> Unit>>) {
    var open by remember { mutableStateOf(false) }
    Row(Modifier.fillMaxWidth().padding(vertical = 6.dp), verticalAlignment = Alignment.CenterVertically) {
        Avatar(p.name, LocalCallColors.current.peer, 40.dp)
        Spacer(Modifier.width(12.dp))
        Column(Modifier.weight(1f)) {
            Text(p.name, style = MaterialTheme.typography.titleMedium)
            Text(listOfNotNull(p.username?.let { "@$it" }, language).joinToString(" · "),
                style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
        IconButton(onClick = onVoicemail) { Icon(Icons.Filled.Voicemail, "Leave ${p.name} a voicemail") }
        IconButton(onClick = onCall) { Icon(Icons.Filled.Call, "Call ${p.name}") }
        Box {
            IconButton(onClick = { open = true }) { Icon(Icons.Filled.MoreVert, "More options for ${p.name}") }
            DropdownMenu(expanded = open, onDismissRequest = { open = false }) {
                menu.forEach { (label, action) -> DropdownMenuItem(text = { Text(label) }, onClick = { open = false; action() }) }
            }
        }
    }
}

/** Full-screen ringing screen, shown over everything while someone is calling. */
@Composable
fun IncomingCallScreen(call: IncomingCall, onAnswered: () -> Unit) {
    val context = LocalContext.current
    val c = context.container
    val scope = rememberCoroutineScope()
    var busy by remember { mutableStateOf(false) }
    fun answer() {
        busy = true
        scope.launch {
            try { c.answerIncoming(); onAnswered() } catch (e: ApiException) {
                Toast.makeText(context, e.message, Toast.LENGTH_LONG).show()
            } finally { busy = false }
        }
    }
    val permission = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { ok ->
        if (ok) answer() else Toast.makeText(context, "Sarvagyan needs the microphone to answer.", Toast.LENGTH_LONG).show()
    }
    EmeraldAnimatedBackground {
        Column(Modifier.fillMaxSize().safeDrawingPadding().padding(32.dp), horizontalAlignment = Alignment.CenterHorizontally) {
            Spacer(Modifier.weight(1f))
            Avatar(call.fromName, LocalCallColors.current.peer, 112.dp)
            Spacer(Modifier.height(24.dp))
            Text(call.fromName, style = MaterialTheme.typography.headlineMedium, textAlign = TextAlign.Center)
            call.fromUsername?.let { Text("@$it", color = MaterialTheme.colorScheme.onSurfaceVariant) }
            Spacer(Modifier.height(8.dp))
            val theirs = c.language(call.fromLanguage)?.name ?: call.fromLanguage
            val mine = c.language(c.settings.value.myLanguage)?.name ?: c.settings.value.myLanguage
            Text("Calling you · they speak $theirs, you'll hear $mine", color = MaterialTheme.colorScheme.onSurfaceVariant, textAlign = TextAlign.Center)
            Spacer(Modifier.weight(1f))
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceEvenly) {
                RoundAction(Icons.Filled.CallEnd, "Decline", LocalCallColors.current.endCall, enabled = !busy) {
                    scope.launch { c.declineIncoming() }
                }
                RoundAction(Icons.Filled.Call, "Accept", LocalCallColors.current.success, enabled = !busy) {
                    if (ContextCompat.checkSelfPermission(context, Manifest.permission.RECORD_AUDIO) == PackageManager.PERMISSION_GRANTED) answer()
                    else permission.launch(Manifest.permission.RECORD_AUDIO)
                }
            }
            Spacer(Modifier.height(48.dp))
        }
    }
}

@Composable
private fun RoundAction(icon: androidx.compose.ui.graphics.vector.ImageVector, label: String, color: Color, enabled: Boolean, onClick: () -> Unit) {
    Column(horizontalAlignment = Alignment.CenterHorizontally) {
        FloatingActionButton(onClick = { if (enabled) onClick() }, shape = CircleShape, containerColor = color,
            elevation = FloatingActionButtonDefaults.elevation(0.dp), modifier = Modifier.size(72.dp)) {
            Icon(icon, contentDescription = label, tint = Color.White, modifier = Modifier.size(32.dp))
        }
        Spacer(Modifier.height(8.dp))
        Text(label)
    }
}
