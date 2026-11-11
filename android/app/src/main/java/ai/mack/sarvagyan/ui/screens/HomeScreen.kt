package ai.mack.sarvagyan.ui.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
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
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowForward
import androidx.compose.material.icons.automirrored.filled.Chat
import androidx.compose.material.icons.automirrored.filled.Help
import androidx.compose.material.icons.automirrored.filled.Logout
import androidx.compose.material.icons.filled.Call
import androidx.compose.material.icons.filled.History
import androidx.compose.material.icons.filled.People
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material.icons.filled.Star
import androidx.compose.material.icons.filled.StarBorder
import androidx.compose.material.icons.filled.SwapHoriz
import androidx.compose.material.icons.filled.Voicemail
import androidx.compose.material3.DrawerValue
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.ModalDrawerSheet
import androidx.compose.material3.ModalNavigationDrawer
import androidx.compose.material3.NavigationDrawerItem
import androidx.compose.material3.NavigationDrawerItemDefaults
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.rememberDrawerState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.input.KeyboardCapitalization
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import ai.mack.sarvagyan.call.CallStatus
import ai.mack.sarvagyan.container
import ai.mack.sarvagyan.data.ApiException
import ai.mack.sarvagyan.data.CallRecord
import ai.mack.sarvagyan.data.Contact
import ai.mack.sarvagyan.data.Peer
import ai.mack.sarvagyan.data.formatDuration
import ai.mack.sarvagyan.data.normaliseCode
import ai.mack.sarvagyan.ui.components.AppCard
import ai.mack.sarvagyan.ui.components.Avatar
import ai.mack.sarvagyan.ui.components.EmeraldAnimatedBackground
import ai.mack.sarvagyan.ui.components.EmptyState
import ai.mack.sarvagyan.ui.components.ErrorBanner
import ai.mack.sarvagyan.ui.components.LanguagePill
import ai.mack.sarvagyan.ui.components.LoadingView
import ai.mack.sarvagyan.ui.components.SectionTitle
import ai.mack.sarvagyan.ui.components.StatusChip
import ai.mack.sarvagyan.ui.theme.Brand
import ai.mack.sarvagyan.ui.theme.LocalCallColors
import kotlinx.coroutines.launch
import java.text.DateFormat
import java.util.Date

@Composable
fun HomeScreen(
    onStartCall: () -> Unit, onJoin: (String) -> Unit, onLanguages: () -> Unit, onSettings: () -> Unit,
    onHelp: () -> Unit, onResumeCall: () -> Unit, onSignedOut: () -> Unit,
    onVoicemail: () -> Unit, onRecordVoicemail: (String, String) -> Unit, onContacts: () -> Unit,
) {
    val c = LocalContext.current.container
    val scope = rememberCoroutineScope()
    val user by c.user.collectAsStateWithLifecycle()
    val settings by c.settings.collectAsStateWithLifecycle()
    val active by c.activeCall.collectAsStateWithLifecycle()
    val activeState = active?.state?.collectAsStateWithLifecycle()?.value
    var history by remember { mutableStateOf<List<CallRecord>?>(null) }
    var favourites by remember { mutableStateOf<List<Contact>>(emptyList()) }
    var online by remember { mutableStateOf<Boolean?>(null) }
    var error by remember { mutableStateOf<String?>(null) }
    var code by remember { mutableStateOf("") }
    var unread by remember { mutableStateOf(0) }
    val placeCall = rememberPlaceCall(onResumeCall)
    val drawerState = rememberDrawerState(initialValue = DrawerValue.Closed)

    suspend fun load() {
        error = null
        online = runCatching { c.api.health() }.isSuccess
        if (online == false) {
            error = "Can't reach the server at ${settings.serverUrl}. Check your connection or the server address in Settings."
            history = history ?: emptyList()
            return
        }
        try {
            if (user == null) c.user.value = c.api.me()
            history = c.api.history().calls
            favourites = c.api.favourites().contacts
            c.syncLanguage()
            unread = runCatching { c.api.voicemails().unread }.getOrDefault(unread)
        } catch (e: ApiException) {
            if (e.isAuth) { c.signOut(); onSignedOut() } else error = e.message
        }
    }
    LaunchedEffect(Unit) { load() }

    ModalNavigationDrawer(
        drawerState = drawerState,
        drawerContent = {
            ModalDrawerSheet(
                drawerContainerColor = MaterialTheme.colorScheme.surface,
                modifier = Modifier.width(300.dp)
            ) {
                // Profile header card
                Column(Modifier.fillMaxWidth().padding(20.dp)) {
                    Avatar(user?.displayName ?: "User", LocalCallColors.current.me, 64.dp, avatar = user?.avatar, useMain = true)
                    Spacer(Modifier.height(12.dp))
                    Text(user?.displayName ?: "User", style = MaterialTheme.typography.titleLarge, fontWeight = androidx.compose.ui.text.font.FontWeight.Bold)
                    user?.username?.let {
                        Text("@$it", style = MaterialTheme.typography.bodyMedium, color = Brand.HighlightAccent)
                    }
                    Spacer(Modifier.height(8.dp))
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        LanguagePill(c.language(settings.myLanguage)?.native ?: settings.myLanguage, highlighted = true)
                        if (user?.isDemo == true) {
                            Spacer(Modifier.width(6.dp))
                            StatusChip("Demo account", LocalCallColors.current.warning)
                        }
                    }
                }
                HorizontalDivider(Modifier.padding(horizontal = 16.dp))
                Spacer(Modifier.height(12.dp))
                NavigationDrawerItem(
                    icon = { Icon(Icons.AutoMirrored.Filled.Chat, null) },
                    label = { Text("Chats & Voice Messages") },
                    selected = false,
                    onClick = {
                        scope.launch { drawerState.close() }
                        onVoicemail()
                    },
                    modifier = Modifier.padding(NavigationDrawerItemDefaults.ItemPadding)
                )
                NavigationDrawerItem(
                    icon = { Icon(Icons.Filled.People, null) },
                    label = { Text("Contacts") },
                    selected = false,
                    onClick = {
                        scope.launch { drawerState.close() }
                        onContacts()
                    },
                    modifier = Modifier.padding(NavigationDrawerItemDefaults.ItemPadding)
                )
                NavigationDrawerItem(
                    icon = { Icon(Icons.Filled.Settings, null) },
                    label = { Text("Settings") },
                    selected = false,
                    onClick = {
                        scope.launch { drawerState.close() }
                        onSettings()
                    },
                    modifier = Modifier.padding(NavigationDrawerItemDefaults.ItemPadding)
                )
                NavigationDrawerItem(
                    icon = { Icon(Icons.AutoMirrored.Filled.Help, null) },
                    label = { Text("Help & Manual") },
                    selected = false,
                    onClick = {
                        scope.launch { drawerState.close() }
                        onHelp()
                    },
                    modifier = Modifier.padding(NavigationDrawerItemDefaults.ItemPadding)
                )
                Spacer(Modifier.weight(1f))
                HorizontalDivider(Modifier.padding(horizontal = 16.dp))
                NavigationDrawerItem(
                    icon = { Icon(Icons.AutoMirrored.Filled.Logout, null, tint = MaterialTheme.colorScheme.error) },
                    label = { Text("Sign out", color = MaterialTheme.colorScheme.error) },
                    selected = false,
                    onClick = {
                        scope.launch {
                            drawerState.close()
                            c.signOut()
                            onSignedOut()
                        }
                    },
                    modifier = Modifier.padding(NavigationDrawerItemDefaults.ItemPadding)
                )
                Spacer(Modifier.height(16.dp))
            }
        }
    ) {
        EmeraldAnimatedBackground {
            Column(Modifier.fillMaxSize().safeDrawingPadding().verticalScroll(rememberScrollState()).padding(horizontal = 20.dp, vertical = 12.dp)) {
                // Header: Profile Avatar & Details (Click opens drawer)
                Row(
                    Modifier.fillMaxWidth().clickable { scope.launch { drawerState.open() } },
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Avatar(user?.displayName ?: "User", LocalCallColors.current.me, avatar = user?.avatar, useMain = false)
                    Spacer(Modifier.width(12.dp))
                    Column(Modifier.weight(1f)) {
                        Text(user?.displayName ?: "…", style = MaterialTheme.typography.titleLarge)
                        user?.username?.let {
                            Text("@$it", style = MaterialTheme.typography.bodySmall, color = Brand.HighlightAccent)
                        }
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            when (online) {
                                true -> StatusChip("Connected", LocalCallColors.current.success)
                                false -> StatusChip("Offline", MaterialTheme.colorScheme.error)
                                null -> StatusChip("Checking…", MaterialTheme.colorScheme.onSurfaceVariant, pulsing = true)
                            }
                            if (user?.isDemo == true) { Spacer(Modifier.width(6.dp)); StatusChip("Demo account", LocalCallColors.current.warning) }
                        }
                    }
                }
                Spacer(Modifier.height(16.dp))

        if (active != null && activeState != null && activeState.status != CallStatus.Ended && activeState.status != CallStatus.Failed) {
            AppCard(Modifier.clickable(role = Role.Button, onClick = onResumeCall)) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    StatusChip("Call in progress", LocalCallColors.current.success, pulsing = true)
                    Spacer(Modifier.weight(1f))
                    Text("Return to call", color = MaterialTheme.colorScheme.primary)
                    Icon(Icons.AutoMirrored.Filled.ArrowForward, null, tint = MaterialTheme.colorScheme.primary)
                }
            }
            Spacer(Modifier.height(12.dp))
        }

        // the most prominent action
            Surface(
                onClick = onStartCall, shape = MaterialTheme.shapes.large, modifier = Modifier.fillMaxWidth().height(112.dp),
                color = Brand.PrimaryAccent,
            ) {
                Row(
                    Modifier.fillMaxSize().background(Brush.horizontalGradient(listOf(Brand.PrimaryAccent, Brand.HighlightAccent))).padding(20.dp),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    Icon(Icons.Filled.Call, contentDescription = null, tint = Brand.ButtonContent, modifier = Modifier.size(36.dp))
                    Spacer(Modifier.width(16.dp))
                    Column(Modifier.weight(1f)) {
                        Text("Start a call", style = MaterialTheme.typography.headlineSmall, color = Brand.ButtonContent, fontWeight = androidx.compose.ui.text.font.FontWeight.Bold)
                        Text("Get an invitation code to share", color = Brand.ButtonContent.copy(alpha = 0.85f))
                    }
                }
            }
        Spacer(Modifier.height(12.dp))

        AppCard {
            Text("Join with an invitation code", style = MaterialTheme.typography.titleMedium)
            Spacer(Modifier.height(8.dp))
            Row(verticalAlignment = Alignment.CenterVertically) {
                OutlinedTextField(
                    code, { code = normaliseCode(it).take(6) }, placeholder = { Text("ABC234") }, singleLine = true, modifier = Modifier.weight(1f),
                    keyboardOptions = KeyboardOptions(capitalization = KeyboardCapitalization.Characters, imeAction = ImeAction.Go),
                    keyboardActions = KeyboardActions(onGo = { if (code.length == 6) onJoin(code) }),
                )
                Spacer(Modifier.width(8.dp))
                TextButton(onClick = { onJoin(code) }, enabled = code.length == 6) { Text("Join") }
            }
        }
        Spacer(Modifier.height(12.dp))

        AppCard(Modifier.clickable(role = Role.Button, onClick = onLanguages)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Column(Modifier.weight(1f)) {
                    Text("I speak", style = MaterialTheme.typography.titleMedium)
                    Spacer(Modifier.height(8.dp))
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        val mine = c.language(settings.myLanguage)
                        LanguagePill(
                            if (mine != null) "${mine.native} · ${mine.name}" else settings.myLanguage,
                            highlighted = true,
                        )
                    }
                    if (settings.autoDetect) Text("Auto-detect secondary check on", style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.secondary)
                }
                Text("Change", color = MaterialTheme.colorScheme.primary)
            }
        }

        Spacer(Modifier.height(12.dp))
        AppCard(Modifier.clickable(role = Role.Button, onClick = onContacts)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Icon(Icons.Filled.People, null, tint = Brand.HighlightAccent, modifier = Modifier.size(28.dp))
                Spacer(Modifier.width(12.dp))
                Column(Modifier.weight(1f)) {
                    Text("Contacts", style = MaterialTheme.typography.titleMedium)
                    Text("Call people directly: their phone rings", style = MaterialTheme.typography.bodyMedium,
                        color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
            }
        }
        Spacer(Modifier.height(12.dp))
        AppCard(Modifier.clickable(role = Role.Button, onClick = onVoicemail)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Icon(Icons.AutoMirrored.Filled.Chat, null, tint = Brand.HighlightAccent, modifier = Modifier.size(28.dp))
                Spacer(Modifier.width(12.dp))
                Column(Modifier.weight(1f)) {
                    Text("Global Chat", style = MaterialTheme.typography.titleMedium)
                    Text("Chats, groups and voice messages in any language", style = MaterialTheme.typography.bodyMedium,
                        color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
                if (unread > 0) StatusChip("$unread new", LocalCallColors.current.success)
            }
        }

        error?.let { Spacer(Modifier.height(12.dp)); ErrorBanner(it, onRetry = { scope.launch { load() } }) }

        SectionTitle("Favourite contacts")
        if (favourites.isEmpty()) {
            EmptyState(Icons.Filled.StarBorder, "No favourites yet", "Star someone in Recent calls. Only people you have actually called can be favourites.")
        } else {
            favourites.forEach { f ->
                ContactRow(f.name, c.language(f.language)?.name ?: f.language, f.isDemo, avatar = f.avatar, starred = true,
                    onStar = { scope.launch { runCatching { c.api.setFavourite(f.id, false) }; load() } },
                    onCall = { placeCall(f.id, f.name) }, onVoicemail = { onRecordVoicemail(f.id, f.name) })
            }
        }

        SectionTitle("Recent calls")
        when {
            history == null -> LoadingView("Loading your calls…")
            history!!.isEmpty() -> EmptyState(Icons.Filled.History, "No calls yet", "Your translated calls will appear here.")
            else -> history!!.take(15).forEach { h -> HistoryRow(h, onStar = { on ->
                h.peer?.let { p -> scope.launch { runCatching { c.api.setFavourite(p.id, on) }; load() } }
            }, onVoicemail = { p -> onRecordVoicemail(p.id, p.name ?: "") }) }
        }
            Spacer(Modifier.height(24.dp))
        }
    }
}
}

@Composable
private fun ContactRow(
    name: String, language: String, demo: Boolean, avatar: String?, starred: Boolean, onStar: () -> Unit, onCall: () -> Unit, onVoicemail: () -> Unit,
) {
    Row(Modifier.fillMaxWidth().padding(vertical = 6.dp), verticalAlignment = Alignment.CenterVertically) {
        Avatar(name, LocalCallColors.current.peer, 40.dp, avatar = avatar, useMain = false)
        Spacer(Modifier.width(12.dp))
        Column(Modifier.weight(1f)) {
            Text(name, style = MaterialTheme.typography.titleMedium)
            Text(language + if (demo) " · demo account" else "", style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
        IconButton(onClick = onStar) { Icon(if (starred) Icons.Filled.Star else Icons.Filled.StarBorder, contentDescription = if (starred) "Remove favourite" else "Add favourite") }
        IconButton(onClick = onVoicemail) { Icon(Icons.Filled.Voicemail, contentDescription = "Leave $name a voicemail") }
        IconButton(onClick = onCall) { Icon(Icons.Filled.Call, contentDescription = "Start a call and invite $name") }
    }
}

@Composable
private fun HistoryRow(h: CallRecord, onStar: (Boolean) -> Unit, onVoicemail: (Peer) -> Unit) {
    val peer = h.peer
    Row(Modifier.fillMaxWidth().padding(vertical = 6.dp), verticalAlignment = Alignment.CenterVertically) {
        Avatar(peer?.name ?: "Nobody", LocalCallColors.current.peer, 40.dp, avatar = peer?.avatar, useMain = false)
        Spacer(Modifier.width(12.dp))
        Column(Modifier.weight(1f)) {
            Text(peer?.name ?: "Nobody joined", style = MaterialTheme.typography.titleMedium)
            val isMissed = h.status == "missed" || h.outcome in listOf("missed", "no_answer", "cancelled")
            val outcomeLabel = when {
                isMissed -> "Missed call"
                h.outcome == "declined" -> "Declined"
                h.outcome == "busy" -> "Busy"
                else -> null
            }
            val meta = buildList {
                if (outcomeLabel != null) add(outcomeLabel)
                add(DateFormat.getDateTimeInstance(DateFormat.SHORT, DateFormat.SHORT).format(Date((h.createdAt * 1000).toLong())))
                h.durationS?.let { add(formatDuration(it.toLong())) }
                if (h.utterances > 0) add("${h.utterances} translated")
                if (peer?.isDemo == true) add("demo")
            }.joinToString(" · ")
            Text(
                meta,
                style = MaterialTheme.typography.bodyMedium,
                color = if (isMissed) LocalCallColors.current.endCall else MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
        if (peer != null) IconButton(onClick = { onVoicemail(peer) }) {
            Icon(Icons.Filled.Voicemail, contentDescription = "Leave ${peer.name ?: "them"} a voicemail")
        }
        if (peer != null) IconButton(onClick = { onStar(!peer.favourite) }) {
            Icon(if (peer.favourite) Icons.Filled.Star else Icons.Filled.StarBorder, contentDescription = if (peer.favourite) "Remove favourite" else "Add favourite")
        }
    }
}
