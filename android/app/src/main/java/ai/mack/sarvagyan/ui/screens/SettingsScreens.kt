package ai.mack.sarvagyan.ui.screens

import androidx.compose.foundation.layout.width
import androidx.compose.material.icons.automirrored.filled.Chat
import androidx.compose.material.icons.automirrored.filled.Help
import androidx.compose.material.icons.automirrored.filled.KeyboardArrowRight
import androidx.compose.material.icons.filled.Call
import androidx.compose.material.icons.filled.Lock
import androidx.compose.material.icons.filled.Notifications
import androidx.compose.material.icons.filled.Palette
import androidx.compose.material.icons.filled.Person
import androidx.compose.material.icons.filled.Storage
import androidx.compose.material.icons.filled.Translate
import ai.mack.sarvagyan.AppLock
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.safeDrawingPadding
import androidx.compose.foundation.layout.width
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
        Spacer(Modifier.height(6.dp))
        Text("The other person sets their own speaking language; Sarvagyan exchanges languages automatically during calls.",
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

@OptIn(ExperimentalLayoutApi::class)
@Composable
fun SettingsScreen(
    group: String?, onBack: () -> Unit, onOpenGroup: (String) -> Unit, onLanguages: () -> Unit, onHelp: () -> Unit,
    onSignedOut: () -> Unit, onContacts: () -> Unit, onPrivacyPolicy: () -> Unit, onChooseAvatar: () -> Unit = {},
) {
    val context = LocalContext.current
    val c = context.container
    var lockError by remember { mutableStateOf<String?>(null) }
    val scope = rememberCoroutineScope()
    val s by c.settings.collectAsStateWithLifecycle()
    val user by c.user.collectAsStateWithLifecycle()
    var nameDraft by remember(user?.displayName) { mutableStateOf(user?.displayName ?: "") }
    var nameError by remember { mutableStateOf<String?>(null) }
    var nameSaved by remember { mutableStateOf(false) }
    var nameBusy by remember { mutableStateOf(false) }
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

    ScreenScaffold(settingsGroups.firstOrNull { it.id == group }?.title ?: "Settings", onBack) {
        if (group == null) {
            SettingsHub(user?.displayName, user?.username, user?.avatar, onOpen = onOpenGroup)
            Spacer(Modifier.height(16.dp))
            SecondaryButton("Sign out", { c.activeCall.value?.end(); c.signOut(); onSignedOut() }, Modifier.fillMaxWidth())
            Spacer(Modifier.height(24.dp))
            return@ScreenScaffold
        }
        when (group) {
            "account" -> {
        SectionTitle("Profile and username")
        AppCard {
            Row(verticalAlignment = Alignment.CenterVertically, modifier = Modifier.fillMaxWidth()) {
                ai.mack.sarvagyan.ui.components.Avatar(user?.displayName ?: "User", LocalCallColors.current.me, 72.dp, avatar = user?.avatar, useMain = true)
                Spacer(Modifier.width(14.dp))
                Column(Modifier.weight(1f)) {
                    Text(user?.displayName ?: "User", style = MaterialTheme.typography.titleMedium)
                    Text(user?.email ?: (if (user?.isDemo == true) "Guest account" else ""), style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    TextButton(onClick = onChooseAvatar, contentPadding = PaddingValues(0.dp)) {
                        Text("Change avatar")
                    }
                }
            }
            Spacer(Modifier.height(8.dp))
            OutlinedTextField(
                value = nameDraft,
                onValueChange = {
                    if (it.length <= 60) {
                        nameDraft = it
                        nameError = null
                        nameSaved = false
                    }
                },
                label = { Text("Display name") },
                placeholder = { Text("Your name") },
                singleLine = true,
                modifier = Modifier.fillMaxWidth()
            )
            nameError?.let {
                Spacer(Modifier.height(4.dp))
                Text(it, color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodySmall)
            }
            if (nameSaved) {
                Spacer(Modifier.height(4.dp))
                Text("Display name updated!", color = LocalCallColors.current.success, style = MaterialTheme.typography.bodySmall)
            }
            Spacer(Modifier.height(8.dp))
            SecondaryButton("Save name", {
                val trimmed = nameDraft.trim()
                if (trimmed.isEmpty()) {
                    nameError = "Name cannot be empty."
                    return@SecondaryButton
                }
                if (trimmed.length > 60) {
                    nameError = "Name must be 60 characters or less."
                    return@SecondaryButton
                }
                nameBusy = true
                nameError = null
                nameSaved = false
                scope.launch {
                    try {
                        val updated = c.api.updateMe(name = trimmed)
                        c.user.value = updated
                        nameDraft = updated.displayName
                        nameSaved = true
                    } catch (e: Exception) {
                        nameError = (e as? ApiException)?.message ?: e.message
                    } finally {
                        nameBusy = false
                    }
                }
            }, enabled = nameDraft.trim().isNotEmpty() && nameDraft.trim() != (user?.displayName ?: "") && !nameBusy)
            HorizontalDivider(Modifier.padding(vertical = 12.dp))
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

        DevicesCard()

                DeleteAccountCard(onDeleted = onSignedOut)
                Spacer(Modifier.height(16.dp))
                SecondaryButton("Sign out", { c.activeCall.value?.end(); c.signOut(); onSignedOut() }, Modifier.fillMaxWidth())
            }
            "privacy" -> {
                SectionTitle("App lock")
                AppCard {
                    SettingSwitch("Lock Sarvagyan", "Ask for your fingerprint, face or phone PIN when the app opens or after 30 seconds away.",
                        s.appLock) { on ->
                        if (on && !AppLock.available(context)) lockError = "Set a screen lock (PIN, pattern or fingerprint) on your phone first."
                        else update { it.copy(appLock = on) }
                    }
                    lockError?.let { Text(it, color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodySmall) }
                    SettingSwitch("Block screenshots", "Stops screenshots and screen recording of Sarvagyan, and hides it in the recent-apps view.",
                        s.blockScreenshots) { on -> update { it.copy(blockScreenshots = on) } }
                }
                SectionTitle("Calls and contacts")
                AppCard(Modifier.clickable(role = Role.Button, onClick = onContacts)) {
                    Text("Who can call me: " + if (user?.allowCalls == "everyone") "Everyone" else "My contacts")
                    Text("Change it, and see blocked people, in Contacts", color = MaterialTheme.colorScheme.primary)
                }
                SectionTitle("Call transcripts")
                SettingSwitch("Save transcripts on this phone", "Off by default. Saved only on this phone, encrypted, never on our server. Audio is never recorded.", s.saveTranscripts) { on ->
                    update { it.copy(saveTranscripts = on) }
                }
                Text("During a call, your speech is sent to our server and to Gnani (speech recognition and voice) and MyMemory (translation) to be translated. Calls are never recorded.",
                    style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant, modifier = Modifier.padding(top = 8.dp))
                Spacer(Modifier.height(12.dp))
                AppCard(Modifier.clickable(role = Role.Button, onClick = onPrivacyPolicy)) {
                    Text("Privacy policy")
                    Text("What is stored, where, and for how long", color = MaterialTheme.colorScheme.primary)
                }
            }
            "language" -> {
        SectionTitle("Language and voice")
        AppCard(Modifier.clickable(role = Role.Button, onClick = onLanguages)) {
            Text("${c.language(s.myLanguage)?.name ?: s.myLanguage} · voice ${s.voice ?: "default"} · ${"%.2f".format(s.speed)}×")
            Text("Change languages, voice and speed", color = MaterialTheme.colorScheme.primary)
        }
            }
            "calls" -> {
        SectionTitle("Audio")
        SettingSwitch("Noise reduction", "Filter out background noise and silence before sending to speech recognition.", s.noiseReduction) { on -> update { it.copy(noiseReduction = on) } }
        SettingSwitch("Hear translated speech", "Off = subtitles only. You still hear the other person's own voice.", s.translatedAudio) { on -> update { it.copy(translatedAudio = on) } }
        SettingSwitch("Start calls on speaker", "Otherwise the phone earpiece is used.", s.speakerOn) { on -> update { it.copy(speakerOn = on) } }
        Text("Other person's original voice: ${"%.0f".format(s.originalVolume * 100)}%")
        Slider(value = s.originalVolume, onValueChange = { v -> update { it.copy(originalVolume = v) } }, valueRange = 0f..1f)
        Text("Kept quieter under the translation so both are understandable.", style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)

        SectionTitle("Subtitles")
        Text("Text size ${"%.0f".format(s.subtitleScale * 100)}%")
        Slider(value = s.subtitleScale, onValueChange = { v -> update { it.copy(subtitleScale = v) } }, valueRange = 0.8f..1.8f)
            }
            "chats" -> {
        SectionTitle("Chats")
        AppCard {
            SettingSwitch("Read receipts", "Others see when you've read their messages. Off: you don't see theirs either.",
                user?.readReceipts ?: true) { on ->
                scope.launch { runCatching { c.api.updateMe(readReceipts = on) }.onSuccess { c.user.value = it } }
            }
            Text("Keep chat history for", style = MaterialTheme.typography.titleMedium)
            FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                listOf(7 to "7 days", 30 to "30 days", 365 to "1 year").forEach { (days, label) ->
                    FilterChip(selected = (user?.chatRetentionDays ?: 30) == days, onClick = {
                        scope.launch { runCatching { c.api.updateMe(chatRetentionDays = days) }.onSuccess { c.user.value = it } }
                    }, label = { Text(label) })
                }
            }
            Text("Applies to new messages. A chat keeps messages for the shortest time any of its members chose; " +
                "then they're deleted from the server.",
                style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }

            }
            "notifications" -> {
                SectionTitle("Notifications")
                val granted = android.os.Build.VERSION.SDK_INT < 33 || androidx.core.content.ContextCompat.checkSelfPermission(
                    context, android.Manifest.permission.POST_NOTIFICATIONS) == android.content.pm.PackageManager.PERMISSION_GRANTED
                AppCard {
                    Text(if (granted) "Notifications are allowed" else "Notifications are off",
                        style = MaterialTheme.typography.titleMedium)
                    Text("Sarvagyan uses them to ring for incoming calls and to show that the microphone is on during a call.",
                        style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    Spacer(Modifier.height(8.dp))
                    SecondaryButton("Open notification settings", {
                        context.startActivity(android.content.Intent(android.provider.Settings.ACTION_APP_NOTIFICATION_SETTINGS)
                            .putExtra(android.provider.Settings.EXTRA_APP_PACKAGE, context.packageName))
                    }, Modifier.fillMaxWidth())
                }
            }
            "storage" -> {
                SectionTitle("On this phone")
                AppCard {
                    Text("Saved call transcripts: $savedCount", style = MaterialTheme.typography.titleMedium)
                    Text("Encrypted, and only on this phone.", style = MaterialTheme.typography.bodyMedium,
                        color = MaterialTheme.colorScheme.onSurfaceVariant)
                    Spacer(Modifier.height(8.dp))
                    SecondaryButton("Delete saved transcripts", { confirmDelete = true }, Modifier.fillMaxWidth(), enabled = savedCount > 0)
                }
                SectionTitle("On our server")
                Text("Chat messages and voice messages are kept for the time chosen in Settings → Chats, voicemail text for at most 7 days. " +
                    "Deleting your account (Settings → Account) removes everything at once.",
                    style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
            "appearance" -> {
        SectionTitle("Theme")
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            ThemeMode.entries.forEach { m -> FilterChip(selected = s.theme == m, onClick = { update { it.copy(theme = m) } }, label = { Text(m.name) }) }
        }
            }
            "help" -> {
                AppCard(Modifier.clickable(role = Role.Button, onClick = onHelp)) {
                    Text("Sarvagyan ${BuildConfig.VERSION_NAME}")
                    Text("How it works, tips and troubleshooting", color = MaterialTheme.colorScheme.primary)
                }
                Spacer(Modifier.height(12.dp))
                AppCard(Modifier.clickable(role = Role.Button, onClick = onPrivacyPolicy)) {
                    Text("Privacy policy")
                    Text("What is stored, where, and for how long", color = MaterialTheme.colorScheme.primary)
                }
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

            }
        }
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

/** Every phone signed in to this account, with sign-out for one or all others (lost or old phones). */
@Composable
private fun DevicesCard() {
    val c = LocalContext.current.container
    val scope = rememberCoroutineScope()
    var devices by remember { mutableStateOf<List<ai.mack.sarvagyan.data.DeviceSession>?>(null) }
    var error by remember { mutableStateOf<String?>(null) }
    suspend fun load() {
        try { devices = c.api.devices().sessions; error = null } catch (e: ApiException) { error = e.message }
    }
    LaunchedEffect(Unit) { load() }

    SectionTitle("Signed-in devices")
    AppCard {
        val list = devices
        when {
            list == null && error == null -> Text("Loading…", color = MaterialTheme.colorScheme.onSurfaceVariant)
            list != null -> list.forEach { d ->
                Row(Modifier.fillMaxWidth().padding(vertical = 4.dp), verticalAlignment = Alignment.CenterVertically) {
                    Column(Modifier.weight(1f)) {
                        Text(d.device + if (d.current) " (this phone)" else "", style = MaterialTheme.typography.titleSmall)
                        Text("Last active " + java.text.DateFormat.getDateTimeInstance(java.text.DateFormat.SHORT, java.text.DateFormat.SHORT)
                            .format(java.util.Date((d.lastUsedAt * 1000).toLong())),
                            style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                    }
                    if (!d.current) TextButton(onClick = { scope.launch {
                        try { c.api.signOutDevice(d.id) } catch (e: ApiException) { error = e.message }
                        load()
                    } }) { Text("Sign out") }
                }
            }
        }
        error?.let { Text(it, color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodySmall) }
        if ((devices?.size ?: 0) > 1) {
            Spacer(Modifier.height(8.dp))
            SecondaryButton("Sign out all other devices", { scope.launch {
                try { c.api.signOutOtherDevices() } catch (e: ApiException) { error = e.message }
                load()
            } }, Modifier.fillMaxWidth())
        }
        Text("Lost a phone? Sign it out here. Its access ends straight away.",
            style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
    }
}

/** The nine Settings groups shown on the hub, in order. */
data class SettingsGroup(val id: String, val title: String, val summary: String, val icon: androidx.compose.ui.graphics.vector.ImageVector)

val settingsGroups = listOf(
    SettingsGroup("account", "Account", "Profile, @username, devices, delete account", Icons.Filled.Person),
    SettingsGroup("privacy", "Privacy and security", "App lock, screenshots, transcripts, privacy policy", Icons.Filled.Lock),
    SettingsGroup("language", "Language and voice", "Your language, voice and speed", Icons.Filled.Translate),
    SettingsGroup("calls", "Calls", "Translated voice, speaker, subtitles", Icons.Filled.Call),
    SettingsGroup("chats", "Chats", "Read receipts, chat history", Icons.AutoMirrored.Filled.Chat),
    SettingsGroup("notifications", "Notifications", "Incoming calls and call alerts", Icons.Filled.Notifications),
    SettingsGroup("storage", "Storage and data", "What is kept on this phone and on our server", Icons.Filled.Storage),
    SettingsGroup("appearance", "Appearance", "Dark, light or system theme", Icons.Filled.Palette),
    SettingsGroup("help", "Help and about", "How it works, privacy policy, diagnostics", Icons.AutoMirrored.Filled.Help),
)

@Composable
private fun SettingsHub(name: String?, username: String?, avatar: String?, onOpen: (String) -> Unit) {
    AppCard(Modifier.clickable(role = Role.Button, onClick = { onOpen("account") })) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            ai.mack.sarvagyan.ui.components.Avatar(name ?: "User", LocalCallColors.current.me, avatar = avatar, useMain = false)
            Spacer(Modifier.width(12.dp))
            Column {
                Text(name ?: "Your account", style = MaterialTheme.typography.titleMedium)
                Text(username?.let { "@$it" } ?: "Set a username so people can find you",
                    style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
        }
    }
    Spacer(Modifier.height(12.dp))
    settingsGroups.drop(1).forEach { g ->
        Row(Modifier.fillMaxWidth().clickable(role = Role.Button) { onOpen(g.id) }.padding(vertical = 12.dp),
            verticalAlignment = Alignment.CenterVertically) {
            Icon(g.icon, null, tint = Brand.HighlightAccent)
            Spacer(Modifier.width(16.dp))
            Column(Modifier.weight(1f)) {
                Text(g.title, style = MaterialTheme.typography.titleMedium)
                Text(g.summary, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
            Icon(Icons.AutoMirrored.Filled.KeyboardArrowRight, null, tint = MaterialTheme.colorScheme.onSurfaceVariant)
        }
        HorizontalDivider(color = Brand.Borders)
    }
}

/** Deletes the account and all its server data, after typing DELETE (and the password, for email accounts). */
@Composable
private fun DeleteAccountCard(onDeleted: () -> Unit) {
    val c = LocalContext.current.container
    val scope = rememberCoroutineScope()
    val user by c.user.collectAsStateWithLifecycle()
    var open by remember { mutableStateOf(false) }
    var confirm by remember { mutableStateOf("") }
    var password by remember { mutableStateOf("") }
    var busy by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf<String?>(null) }
    val needsPassword = user?.email != null

    SectionTitle("Delete account")
    AppCard {
        Text("Deletes your account and everything our server holds about you: profile, devices, contacts, call history, " +
            "voicemail, and your chat and voice messages. It cannot be undone.",
            style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
        Spacer(Modifier.height(8.dp))
        TextButton(onClick = { open = true }) { Text("Delete my account", color = MaterialTheme.colorScheme.error) }
    }
    if (open) AlertDialog(
        onDismissRequest = { if (!busy) open = false },
        title = { Text("Delete your account?") },
        text = {
            Column {
                Text("This cannot be undone. Type DELETE to confirm.")
                Spacer(Modifier.height(8.dp))
                OutlinedTextField(confirm, { confirm = it.trim() }, singleLine = true, label = { Text("Type DELETE") })
                if (needsPassword) {
                    Spacer(Modifier.height(8.dp))
                    OutlinedTextField(password, { password = it }, singleLine = true, label = { Text("Your password") },
                        visualTransformation = androidx.compose.ui.text.input.PasswordVisualTransformation())
                }
                error?.let { Spacer(Modifier.height(8.dp)); Text(it, color = MaterialTheme.colorScheme.error) }
            }
        },
        confirmButton = {
            TextButton(enabled = confirm == "DELETE" && (!needsPassword || password.isNotEmpty()) && !busy, onClick = {
                busy = true
                error = null
                scope.launch {
                    try {
                        c.api.deleteAccount(password.takeIf { needsPassword })
                        c.activeCall.value?.end(notifyServer = false)
                        c.transcripts.deleteAll()
                        c.forgetAccount()
                        open = false
                        onDeleted()
                    } catch (e: ApiException) {
                        error = e.message
                    } finally { busy = false }
                }
            }) { Text("Delete for ever", color = MaterialTheme.colorScheme.error) }
        },
        dismissButton = { TextButton(onClick = { open = false }, enabled = !busy) { Text("Cancel") } },
    )
}

@Composable
fun PrivacyPolicyScreen(onBack: () -> Unit) {
    ScreenScaffold("Privacy policy", onBack) {
        PrivacyPolicy.sections.forEach { (title, body) ->
            SectionTitle(title)
            Text(body, style = MaterialTheme.typography.bodyLarge)
        }
        Spacer(Modifier.height(24.dp))
    }
}
