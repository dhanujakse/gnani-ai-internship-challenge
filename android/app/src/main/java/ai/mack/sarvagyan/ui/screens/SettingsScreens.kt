package ai.mack.sarvagyan.ui.screens

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.safeDrawingPadding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.selection.selectable
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.FilterChip
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.RadioButton
import androidx.compose.material3.Slider
import androidx.compose.material3.Switch
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
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import ai.mack.sarvagyan.BuildConfig
import ai.mack.sarvagyan.container
import ai.mack.sarvagyan.data.AppSettings
import ai.mack.sarvagyan.data.ApiException
import ai.mack.sarvagyan.data.bool
import ai.mack.sarvagyan.data.int
import ai.mack.sarvagyan.data.objOrNull
import ai.mack.sarvagyan.data.str
import ai.mack.sarvagyan.ui.components.AppCard
import ai.mack.sarvagyan.ui.components.EmeraldAnimatedBackground
import ai.mack.sarvagyan.ui.components.ErrorBanner
import ai.mack.sarvagyan.ui.components.PrimaryButton
import ai.mack.sarvagyan.ui.components.SecondaryButton
import ai.mack.sarvagyan.ui.components.SectionTitle
import ai.mack.sarvagyan.ui.components.StatusChip
import ai.mack.sarvagyan.ui.theme.Brand
import ai.mack.sarvagyan.ui.theme.LocalCallColors
import ai.mack.sarvagyan.ui.theme.ThemeMode
import kotlinx.coroutines.launch
import kotlinx.serialization.json.JsonObject

@Composable
fun ScreenScaffold(title: String, onBack: () -> Unit, content: @Composable () -> Unit) {
    EmeraldAnimatedBackground {
        Column(Modifier.fillMaxSize().safeDrawingPadding()) {
            Row(Modifier.fillMaxWidth().padding(horizontal = 4.dp, vertical = 4.dp), verticalAlignment = Alignment.CenterVertically) {
                IconButton(onClick = onBack) { Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "Back", tint = Brand.HighlightAccent) }
                Text(title, style = MaterialTheme.typography.titleLarge, color = Brand.PrimaryText)
            }
            Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(horizontal = 20.dp, vertical = 8.dp)) { content() }
        }
    }
}

@Composable
private fun SettingSwitch(title: String, body: String, checked: Boolean, onChange: (Boolean) -> Unit) {
    Row(Modifier.fillMaxWidth().clickable(role = Role.Switch) { onChange(!checked) }.padding(vertical = 10.dp), verticalAlignment = Alignment.CenterVertically) {
        Column(Modifier.weight(1f)) {
            Text(title, style = MaterialTheme.typography.titleMedium)
            Text(body, style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
        Switch(checked = checked, onCheckedChange = onChange)
    }
}

@OptIn(ExperimentalLayoutApi::class)
@Composable
fun LanguageScreen(onBack: () -> Unit) {
    val c = LocalContext.current.container
    val scope = rememberCoroutineScope()
    val s by c.settings.collectAsStateWithLifecycle()
    val langs by c.languages.collectAsStateWithLifecycle()
    val active by c.activeCall.collectAsStateWithLifecycle()
    LaunchedEffect(Unit) { c.refreshLanguages() }
    fun update(t: (AppSettings) -> AppSettings) = scope.launch { c.settingsStore.update(t) }

    ScreenScaffold("Languages", onBack) {
        Text("Showing only languages supported end to end (speech recognition, translation and voice).",
            style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
        SectionTitle("I speak")
        FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            langs.forEach { l ->
                FilterChip(selected = s.myLanguage == l.code, onClick = {
                    update { it.copy(myLanguage = l.code, voice = null) }
                    scope.launch { runCatching { c.api.updateMe(language = l.code) } }
                    active?.setLanguage(l.code, s.autoDetect) // changes language mid-call when a call is active
                }, label = { Text("${l.native} · ${l.name}") })
            }
        }
        SectionTitle("They speak (default for new calls)")
        FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            langs.forEach { l ->
                FilterChip(selected = s.partnerLanguage == l.code, onClick = { update { it.copy(partnerLanguage = l.code) } }, label = { Text("${l.native} · ${l.name}") })
            }
        }
        Text("Each person picks their own language when they join; this is only a reminder for invitations.",
            style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
        HorizontalDivider(Modifier.padding(vertical = 12.dp))
        SettingSwitch("Detect my language automatically", "Useful if you switch languages while talking (Gnani Prisma v3.0 auto-detect).", s.autoDetect) { on ->
            update { it.copy(autoDetect = on) }
            active?.setLanguage(s.myLanguage, on)
        }
        SectionTitle("Voice I hear translations in")
        val mine = langs.firstOrNull { it.code == s.myLanguage }
        mine?.voices?.forEach { v ->
            Row(Modifier.fillMaxWidth().selectable(selected = (s.voice ?: mine.voices.first()) == v, onClick = { update { it.copy(voice = v) } }, role = Role.RadioButton)
                .padding(vertical = 4.dp), verticalAlignment = Alignment.CenterVertically) {
                RadioButton(selected = (s.voice ?: mine.voices.first()) == v, onClick = null)
                Text(v, Modifier.padding(start = 8.dp))
            }
        }
        SectionTitle("Translation playback speed: ${"%.2f".format(s.speed)}×")
        Slider(value = s.speed, onValueChange = { v -> update { it.copy(speed = v) } }, valueRange = 0.85f..1.15f, steps = 5)
        Text("Applies to calls you start or join next.", style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
    }
}

@Composable
fun SettingsScreen(onBack: () -> Unit, onLanguages: () -> Unit, onHelp: () -> Unit, onSignedOut: () -> Unit) {
    val c = LocalContext.current.container
    val scope = rememberCoroutineScope()
    val s by c.settings.collectAsStateWithLifecycle()
    val user by c.user.collectAsStateWithLifecycle()
    var usernameDraft by remember(user?.username) { mutableStateOf(user?.username ?: "") }
    var usernameError by remember { mutableStateOf<String?>(null) }
    var usernameSaved by remember { mutableStateOf(false) }
    var usernameBusy by remember { mutableStateOf(false) }
    var serverDraft by remember(s.serverUrl) { mutableStateOf(s.serverUrl) }
    var diag by remember { mutableStateOf<JsonObject?>(null) }
    var diagError by remember { mutableStateOf<String?>(null) }
    var diagBusy by remember { mutableStateOf(false) }
    var confirmDelete by remember { mutableStateOf(false) }
    var savedCount by remember { mutableStateOf(c.transcripts.count()) }
    fun update(t: (AppSettings) -> AppSettings) = scope.launch { c.settingsStore.update(t) }

    ScreenScaffold("Settings", onBack) {
        SectionTitle("Profile and username")
        AppCard {
            Text(user?.displayName ?: "User", style = MaterialTheme.typography.titleMedium)
            Text(user?.email ?: (if (user?.isDemo == true) "Guest account" else ""), style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
            Spacer(Modifier.height(8.dp))
            OutlinedTextField(
                value = usernameDraft,
                onValueChange = {
                    usernameDraft = it.filter { ch -> ch.isLetterOrDigit() || ch == '_' }
                    usernameError = null
                    usernameSaved = false
                },
                label = { Text("Unique username (@username)") },
                placeholder = { Text("e.g. john_doe") },
                singleLine = true,
                modifier = Modifier.fillMaxWidth()
            )
            usernameError?.let {
                Spacer(Modifier.height(4.dp))
                Text(it, color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodySmall)
            }
            if (usernameSaved) {
                Spacer(Modifier.height(4.dp))
                Text("Username updated successfully!", color = LocalCallColors.current.success, style = MaterialTheme.typography.bodySmall)
            }
            Spacer(Modifier.height(8.dp))
            SecondaryButton("Save username", {
                usernameBusy = true
                usernameError = null
                usernameSaved = false
                scope.launch {
                    try {
                        val trimmed = usernameDraft.trim()
                        if (trimmed.length < 3 || trimmed.length > 24) {
                            usernameError = "Username must be 3 to 24 characters."
                            return@launch
                        }
                        val check = c.api.checkUsername(trimmed)
                        if (!check.available && trimmed != user?.username) {
                            usernameError = "Username @$trimmed is already taken."
                            return@launch
                        }
                        val updated = c.api.updateMe(username = trimmed)
                        c.user.value = updated
                        usernameSaved = true
                    } catch (e: Exception) {
                        usernameError = (e as? ApiException)?.message ?: e.message
                    } finally {
                        usernameBusy = false
                    }
                }
            }, enabled = usernameDraft.isNotBlank() && usernameDraft != (user?.username ?: "") && !usernameBusy)
        }

        SectionTitle("Language and voice")
        AppCard(Modifier.clickable(role = Role.Button, onClick = onLanguages)) {
            Text("${c.language(s.myLanguage)?.name ?: s.myLanguage} · voice ${s.voice ?: "default"} · ${"%.2f".format(s.speed)}×")
            Text("Change languages, voice and speed", color = MaterialTheme.colorScheme.primary)
        }
        SectionTitle("Subtitles")
        Text("Text size ${"%.0f".format(s.subtitleScale * 100)}%")
        Slider(value = s.subtitleScale, onValueChange = { v -> update { it.copy(subtitleScale = v) } }, valueRange = 0.8f..1.8f)
        SectionTitle("Theme")
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            ThemeMode.entries.forEach { m -> FilterChip(selected = s.theme == m, onClick = { update { it.copy(theme = m) } }, label = { Text(m.name) }) }
        }
        SectionTitle("Audio")
        SettingSwitch("Hear translated speech", "Off = subtitles only. You still hear the other person's own voice.", s.translatedAudio) { on -> update { it.copy(translatedAudio = on) } }
        SettingSwitch("Start calls on speaker", "Otherwise the phone earpiece is used.", s.speakerOn) { on -> update { it.copy(speakerOn = on) } }
        Text("Other person's original voice: ${"%.0f".format(s.originalVolume * 100)}%")
        Slider(value = s.originalVolume, onValueChange = { v -> update { it.copy(originalVolume = v) } }, valueRange = 0f..1f)
        Text("Kept quieter under the translation so both are understandable.", style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)

        SectionTitle("Privacy")
        SettingSwitch("Save transcripts on this phone", "Off by default. Saved only on this device, never on our server. Audio is never recorded.", s.saveTranscripts) { on ->
            update { it.copy(saveTranscripts = on) }
        }
        SecondaryButton("Delete saved transcripts ($savedCount)", { confirmDelete = true }, Modifier.fillMaxWidth(), enabled = savedCount > 0)
        Text("During a call, your speech is sent to our server and to Gnani (speech recognition and voice) and MyMemory (translation) to be translated. Nothing is stored by Sarvagyan.",
            style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant, modifier = Modifier.padding(top = 8.dp))

        SectionTitle("Connection and diagnostics")
        OutlinedTextField(serverDraft, { serverDraft = it.trim() }, label = { Text("Server URL") }, singleLine = true, modifier = Modifier.fillMaxWidth())
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp), modifier = Modifier.padding(top = 8.dp)) {
            SecondaryButton("Save", { update { it.copy(serverUrl = serverDraft) } }, enabled = serverDraft != s.serverUrl)
            PrimaryButton("Run diagnostics", {
                diagBusy = true; diagError = null
                scope.launch {
                    try {
                        c.api.health()
                        diag = c.api.diagnostics()
                    } catch (e: ApiException) {
                        diagError = e.message; diag = null
                    } finally { diagBusy = false }
                }
            }, loading = diagBusy)
        }
        diagError?.let { Spacer(Modifier.height(8.dp)); ErrorBanner(it) }
        diag?.let { d -> Spacer(Modifier.height(8.dp)); DiagnosticsCard(d) }

        SectionTitle("About and help")
        AppCard(Modifier.clickable(role = Role.Button, onClick = onHelp)) {
            Text("Sarvagyan ${BuildConfig.VERSION_NAME}")
            Text("How it works, privacy and troubleshooting", color = MaterialTheme.colorScheme.primary)
        }
        Spacer(Modifier.height(16.dp))
        SecondaryButton("Sign out", { c.activeCall.value?.end(); c.signOut(); onSignedOut() }, Modifier.fillMaxWidth())
        Spacer(Modifier.height(24.dp))
    }

    if (confirmDelete) AlertDialog(
        onDismissRequest = { confirmDelete = false },
        title = { Text("Delete saved transcripts?") },
        text = { Text("This removes all $savedCount transcripts from this phone. It cannot be undone.") },
        confirmButton = { TextButton(onClick = { c.transcripts.deleteAll(); savedCount = 0; confirmDelete = false }) { Text("Delete") } },
        dismissButton = { TextButton(onClick = { confirmDelete = false }) { Text("Cancel") } },
    )
}

@Composable
private fun DiagnosticsCard(d: JsonObject) {
    val ok = LocalCallColors.current.success
    val bad = MaterialTheme.colorScheme.error
    AppCard {
        @Composable
        fun line(label: String, good: Boolean?, detail: String) = Row(Modifier.fillMaxWidth().padding(vertical = 4.dp), verticalAlignment = Alignment.CenterVertically) {
            Text(label, Modifier.weight(1f))
            StatusChip(detail, if (good == true) ok else bad)
        }
        line("Server", true, "OK")
        line("Gnani API key", d.bool("gnani_key_configured"), if (d.bool("gnani_key_configured") == true) "Configured" else "Missing")
        val stt = d.objOrNull("speech_recognition")
        line("Speech recognition (Prisma)", stt?.bool("ok"), stt?.int("ms")?.let { "OK · $it ms" } ?: (stt?.str("error") ?: "Failed"))
        val tr = d.objOrNull("translation")
        line("Translation (${d.str("translator") ?: "?"})", tr?.bool("ok"), tr?.int("ms")?.let { "OK · $it ms" } ?: (tr?.str("error") ?: "Failed"))
        line("TURN relay", d.bool("turn_configured"), if (d.bool("turn_configured") == true) "Configured" else "Not set (STUN only)")
        if (d.bool("demo_mode") == true) Text("Server is in demo mode (guest sign-in allowed).", style = MaterialTheme.typography.bodyMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant)
    }
}

@Composable
fun HelpScreen(onBack: () -> Unit) {
    ScreenScaffold("Help", onBack) {
        val sections = listOf(
            "How it works" to "When you speak, your phone sends your voice to the other person directly (the original call) and, separately, to the Sarvagyan server. The server recognises what you said with Gnani Prisma, translates it with MyMemory and speaks it in the other person's language with Gnani Timbre. They hear the translation and see subtitles; you see what they heard. Their replies come back the same way.",
            "How fast is it?" to "Usually 2–5 seconds after you finish a sentence: speech recognition waits for a short pause, then translation and the voice take about a second each. Each subtitle shows the delay, and slow translations are marked.",
            "Tips for good results" to "Speak in full sentences and pause briefly at the end. Use a headset or keep the phone away from the speaker to avoid echo. If translations sound wrong, check that both people picked the right language.",
            "Privacy" to "Sarvagyan does not record calls. Speech is processed by our server, Gnani and MyMemory only to produce the translation. Transcripts are saved only on your phone, only if you turn that on in Settings, and you can delete them at any time.",
            "Troubleshooting" to "• \"Can't reach the server\": check your internet and the server address in Settings → Diagnostics.\n• Original voice doesn't connect but subtitles work: your network blocks direct connections; the server owner needs to add a TURN server.\n• \"Speech recognition\" errors: the server's Gnani key is missing or out of credits — Diagnostics shows which.",
            "Limitations" to "Calls are between two people inside Sarvagyan. It cannot translate ordinary phone calls or other apps' audio — Android does not allow apps to capture those.",
        )
        sections.forEach { (title, body) ->
            SectionTitle(title)
            Text(body, style = MaterialTheme.typography.bodyLarge)
        }
        Spacer(Modifier.height(24.dp))
        Text("Sarvagyan ${BuildConfig.VERSION_NAME} · Speech: Gnani Prisma & Timbre · Translation: MyMemory",
            style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
        Spacer(Modifier.height(24.dp))
    }
}
