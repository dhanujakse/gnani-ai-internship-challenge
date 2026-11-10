package ai.mack.sarvagyan.ui.screens

import android.Manifest
import android.content.ClipData
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.net.ConnectivityManager
import android.net.Network
import android.net.NetworkCapabilities
import android.os.Build
import androidx.activity.compose.BackHandler
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.safeDrawingPadding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.VolumeUp
import androidx.compose.material.icons.filled.Voicemail
import androidx.compose.material.icons.filled.Call
import androidx.compose.material.icons.filled.CallEnd
import androidx.compose.material.icons.filled.People
import androidx.compose.material.icons.filled.Check
import androidx.compose.material.icons.filled.ContentCopy
import androidx.compose.material.icons.filled.Delete
import androidx.compose.material.icons.filled.Language
import androidx.compose.material.icons.filled.Mic
import androidx.compose.material.icons.filled.MicOff
import androidx.compose.foundation.clickable
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.layout.heightIn
import ai.mack.sarvagyan.data.Language
import androidx.compose.material.icons.filled.Share
import androidx.compose.material.icons.filled.SignalCellularAlt
import androidx.compose.material.icons.filled.SubtitlesOff
import androidx.compose.material.icons.filled.TextFields
import androidx.compose.material.icons.filled.Translate
import androidx.compose.material.icons.filled.UnfoldLess
import androidx.compose.material.icons.filled.UnfoldMore
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilledIconButton
import androidx.compose.material3.FilledTonalIconButton
import androidx.compose.material3.FilterChip
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButtonDefaults
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Slider
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableLongStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.platform.ClipEntry
import androidx.compose.ui.platform.LocalClipboard
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.core.content.ContextCompat
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import ai.mack.sarvagyan.call.AudioRoute
import ai.mack.sarvagyan.call.AudioRouter
import ai.mack.sarvagyan.call.CallStatus
import ai.mack.sarvagyan.call.PipelineState
import ai.mack.sarvagyan.call.Quality
import ai.mack.sarvagyan.container
import ai.mack.sarvagyan.data.ApiException
import ai.mack.sarvagyan.data.formatDuration
import ai.mack.sarvagyan.data.normaliseCode
import ai.mack.sarvagyan.ui.components.AppCard
import ai.mack.sarvagyan.ui.components.Avatar
import ai.mack.sarvagyan.ui.components.EmeraldAnimatedBackground
import ai.mack.sarvagyan.ui.components.EmptyState
import ai.mack.sarvagyan.ui.components.ErrorBanner
import ai.mack.sarvagyan.ui.components.GlowingMicButton
import ai.mack.sarvagyan.ui.components.LanguagePill
import ai.mack.sarvagyan.ui.components.ListeningBubble
import ai.mack.sarvagyan.ui.components.PrimaryButton
import ai.mack.sarvagyan.ui.components.SecondaryButton
import ai.mack.sarvagyan.ui.components.SectionTitle
import ai.mack.sarvagyan.ui.components.StatusChip
import ai.mack.sarvagyan.ui.components.SubtitleBubble
import ai.mack.sarvagyan.ui.theme.Brand
import ai.mack.sarvagyan.ui.theme.LocalCallColors
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch

// ---------------------------------------------------------------------------------------------
// Call setup
// ---------------------------------------------------------------------------------------------

@Composable
private fun rememberOnline(): Boolean {
    val context = LocalContext.current
    val cm = remember { context.getSystemService(Context.CONNECTIVITY_SERVICE) as ConnectivityManager }
    var online by remember { mutableStateOf(cm.activeNetwork?.let { cm.getNetworkCapabilities(it)?.hasCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET) } == true) }
    DisposableEffect(cm) {
        val cb = object : ConnectivityManager.NetworkCallback() {
            override fun onAvailable(network: Network) { online = true }
            override fun onLost(network: Network) { online = cm.activeNetwork != null }
        }
        cm.registerDefaultNetworkCallback(cb)
        onDispose { cm.unregisterNetworkCallback(cb) }
    }
    return online
}

private fun hasMic(context: Context) = ContextCompat.checkSelfPermission(context, Manifest.permission.RECORD_AUDIO) == PackageManager.PERMISSION_GRANTED

@Composable
fun CallSetupScreen(join: Boolean, initialCode: String?, onBack: () -> Unit, onLanguages: () -> Unit, onStarted: () -> Unit) {
    val context = LocalContext.current
    val c = context.container
    val scope = rememberCoroutineScope()
    val s by c.settings.collectAsStateWithLifecycle()
    val online = rememberOnline()
    var code by remember { mutableStateOf(initialCode ?: "") }
    var micGranted by remember { mutableStateOf(hasMic(context)) }
    var micDenied by remember { mutableStateOf(false) }
    var busy by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf<String?>(null) }
    var routes by remember { mutableStateOf(AudioRouter(context).available()) }
    var route by remember {
        val initial = if (s.speakerOn) AudioRoute.Speaker else AudioRoute.Earpiece
        mutableStateOf(if (routes.contains(initial)) initial else routes.firstOrNull() ?: AudioRoute.Speaker)
    }
    DisposableEffect(context) {
        val receiver = object : android.content.BroadcastReceiver() {
            override fun onReceive(c: Context?, intent: Intent?) {
                val avail = AudioRouter(context).available()
                routes = avail
                if (!avail.contains(route)) {
                    route = if (avail.contains(AudioRoute.Earpiece)) AudioRoute.Earpiece else AudioRoute.Speaker
                }
            }
        }
        try {
            context.registerReceiver(receiver, android.content.IntentFilter(Intent.ACTION_HEADSET_PLUG))
        } catch (_: Exception) {}
        onDispose {
            try { context.unregisterReceiver(receiver) } catch (_: Exception) {}
        }
    }
    val permission = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { ok ->
        micGranted = ok
        micDenied = !ok
    }
    val notifPermission = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { }

    fun go() {
        if (!micGranted) { permission.launch(Manifest.permission.RECORD_AUDIO); return }
        if (Build.VERSION.SDK_INT >= 33 && ContextCompat.checkSelfPermission(context, Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED) {
            notifPermission.launch(Manifest.permission.POST_NOTIFICATIONS) // the call notification shows the mic is on
        }
        busy = true
        error = null
        scope.launch {
            try {
                c.settingsStore.update { it.copy(speakerOn = route == AudioRoute.Speaker) }
                val info = if (join) c.api.joinCall(normaliseCode(code), s.myLanguage) else c.api.createCall(s.myLanguage)
                c.startCall(info, s.myLanguage, initialRoute = route)
                onStarted()
            } catch (e: ApiException) {
                error = when (e.status) {
                    404 -> "That invitation code isn't valid or has expired. Ask for a new one."
                    409 -> "That call already has two people."
                    0 -> "No connection to the server. Check your internet and try again."
                    else -> e.message
                }
            } finally {
                busy = false
            }
        }
    }

    ScreenScaffold(if (join) "Join a call" else "Start a call", onBack) {
        AppCard {
            Text("Languages", style = MaterialTheme.typography.titleMedium)
            Spacer(Modifier.height(8.dp))
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text("You speak ", color = MaterialTheme.colorScheme.onSurfaceVariant)
                LanguagePill(c.language(s.myLanguage)?.native ?: s.myLanguage, highlighted = true)
            }
            Spacer(Modifier.height(6.dp))
            Text(
                if (join) "You'll hear the other person in ${c.language(s.myLanguage)?.name ?: s.myLanguage}."
                else "Invite someone who speaks ${c.language(s.partnerLanguage)?.name ?: s.partnerLanguage} (or any supported language — they choose theirs).",
                style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            TextButton(onClick = onLanguages, contentPadding = PaddingValues(0.dp)) { Text("Change languages") }
        }
        Spacer(Modifier.height(12.dp))
        if (join) {
            OutlinedTextField(code, { code = normaliseCode(it).take(6) }, label = { Text("Invitation code") }, singleLine = true,
                textStyle = MaterialTheme.typography.headlineSmall.copy(fontFamily = FontFamily.Monospace), modifier = Modifier.fillMaxWidth())
            Spacer(Modifier.height(12.dp))
        } else {
            AppCard {
                Text("Who are you calling?", style = MaterialTheme.typography.titleMedium)
                Text("You'll get a code and a link to send them (WhatsApp, SMS…). They open Sarvagyan, tap Join and enter it. Sarvagyan cannot ring people directly yet.",
                    style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
            Spacer(Modifier.height(12.dp))
        }
        AppCard {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Icon(if (micGranted) Icons.Filled.Mic else Icons.Filled.MicOff, null, tint = if (micGranted) LocalCallColors.current.success else MaterialTheme.colorScheme.error)
                Spacer(Modifier.width(10.dp))
                Column(Modifier.weight(1f)) {
                    Text(if (micGranted) "Microphone allowed" else "Microphone needed", style = MaterialTheme.typography.titleMedium)
                    Text("Used only during calls, to send your voice to the other person and to translate it. Sarvagyan never records calls.",
                        style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
            }
            if (!micGranted) {
                Spacer(Modifier.height(8.dp))
                SecondaryButton("Allow microphone", { permission.launch(Manifest.permission.RECORD_AUDIO) })
                if (micDenied) Text("Permission was denied. If Android stops asking, enable it in Settings → Apps → Sarvagyan → Permissions.",
                    style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.error)
            }
        }
        Spacer(Modifier.height(12.dp))
        SectionTitle("Audio output")
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            routes.forEach { r -> FilterChip(selected = route == r, onClick = { route = r }, label = { Text(r.label) }) }
        }
        Spacer(Modifier.height(12.dp))
        Row(verticalAlignment = Alignment.CenterVertically) {
            StatusChip(if (online) "Network connected" else "No network", if (online) LocalCallColors.current.success else MaterialTheme.colorScheme.error)
        }
        error?.let { Spacer(Modifier.height(12.dp)); ErrorBanner(it, onRetry = { go() }) }
        Spacer(Modifier.height(20.dp))
        PrimaryButton(
            if (join) "Join call" else "Create call", { go() }, Modifier.fillMaxWidth(), loading = busy,
            enabled = online && (!join || code.length == 6),
        )
        Spacer(Modifier.height(24.dp))
    }
}

// ---------------------------------------------------------------------------------------------
// Active call
// ---------------------------------------------------------------------------------------------

@Composable
fun ActiveCallScreen(onFinished: (String) -> Unit, onLeaveScreen: () -> Unit, onVoicemail: (String, String) -> Unit) {
    val context = LocalContext.current
    val c = context.container
    val session by c.activeCall.collectAsStateWithLifecycle()
    val call = session ?: run { LaunchedEffect(Unit) { onLeaveScreen() }; return }
    val st by call.state.collectAsStateWithLifecycle()
    val settings by c.settings.collectAsStateWithLifecycle()
    val scope = rememberCoroutineScope()
    val clipboard = LocalClipboard.current
    var now by remember { mutableLongStateOf(System.currentTimeMillis()) }
    var compact by remember { mutableStateOf(false) }
    var showAudio by remember { mutableStateOf(false) }
    var showLanguageSheet by remember { mutableStateOf(false) }
    val listState = rememberLazyListState()
    val colors = LocalCallColors.current
    val myLang = c.language(st.me?.language ?: settings.myLanguage)
    val peerLang = st.peer?.let { c.language(it.language) }

    LaunchedEffect(Unit) { while (true) { delay(1000); now = System.currentTimeMillis() } }
    LaunchedEffect(st.status) {
        if ((st.status == CallStatus.Ended || st.status == CallStatus.Failed) && st.unanswered == null) { delay(600); onFinished(call.info.callId) }
    }
    LaunchedEffect(st.conversation.turns.size, st.conversation.speaking) {
        val count = st.conversation.turns.size + st.conversation.speaking.size
        if (count > 0) listState.animateScrollToItem(count - 1)
    }
    BackHandler { onLeaveScreen() } // the call continues in the background (notification) — End is explicit

    EmeraldAnimatedBackground {
        Column(Modifier.fillMaxSize().safeDrawingPadding()) {
        // header
        Row(Modifier.fillMaxWidth().padding(16.dp), verticalAlignment = Alignment.CenterVertically) {
            Avatar(st.peer?.name ?: "?", colors.peer)
            Spacer(Modifier.width(12.dp))
            Column(Modifier.weight(1f)) {
                Text(st.peer?.name ?: call.info.peerName ?: "Waiting for someone to join", style = MaterialTheme.typography.titleMedium)
                val dur = st.startedAtMs?.let { formatDuration((now - it) / 1000) } ?: "--:--"
                Text("$dur · ${statusLabel(st.status)}", style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
            QualityChip(st.quality, st.rttMs, st.mediaConnected)
        }
        Row(Modifier.fillMaxWidth().padding(horizontal = 16.dp), verticalAlignment = Alignment.CenterVertically) {
            Box(Modifier.clickable { showLanguageSheet = true }) {
                LanguagePill("You: ${myLang?.native ?: "?"} ▾", highlighted = true)
            }
            Icon(Icons.Filled.Translate, null, Modifier.padding(horizontal = 8.dp).size(18.dp), tint = MaterialTheme.colorScheme.onSurfaceVariant)
            LanguagePill("Them: ${peerLang?.native ?: "…"}")
            Spacer(Modifier.weight(1f))
            if (!st.muted && st.micStreaming) StatusChip("Mic on", colors.endCall, pulsing = true)
            else if (st.muted) StatusChip("Muted", MaterialTheme.colorScheme.onSurfaceVariant)
        }
        if (!settings.privacyAcknowledged && st.status != CallStatus.Ended) {
            Spacer(Modifier.height(8.dp))
            ErrorBanner("Your speech is processed by Gnani and MyMemory to translate it. Nothing is recorded.",
                Modifier.padding(horizontal = 16.dp), onDismiss = { scope.launch { c.settingsStore.update { it.copy(privacyAcknowledged = true) } } })
        }
        st.banner?.let { b -> Spacer(Modifier.height(8.dp)); ErrorBanner(b.message, Modifier.padding(horizontal = 16.dp), onDismiss = { call.dismissBanner() }, severe = b.severe) }
        st.notice?.let { n -> Spacer(Modifier.height(8.dp)); ErrorBanner(n, Modifier.padding(horizontal = 16.dp), onDismiss = { call.dismissBanner() }) }
        if (st.myPipeline == PipelineState.Reconnecting) {
            Spacer(Modifier.height(8.dp)); ErrorBanner("Speech recognition reconnecting…", Modifier.padding(horizontal = 16.dp))
        }

        // conversation
        Box(Modifier.weight(1f).fillMaxWidth()) {
            if (st.unanswered != null) {
                UnansweredCard(st.unanswered!!, call.info.peerName ?: "them",
                    onVoicemail = call.info.peerId?.let { id -> { onVoicemail(id, call.info.peerName ?: "") } },
                    onClose = onLeaveScreen)
            } else if (call.info.ringing && (st.status == CallStatus.WaitingForPeer || st.status == CallStatus.Connecting)) {
                RingingCard(call.info.peerName ?: "them", call.info.reachable)
            } else if (st.status == CallStatus.WaitingForPeer || st.status == CallStatus.Connecting) {
                InviteCard(call.info.inviteCode, call.info.inviteLink, onCopy = {
                    scope.launch { clipboard.setClipEntry(ClipEntry(ClipData.newPlainText("Sarvagyan invite", inviteText(call.info.inviteCode, call.info.inviteLink)))) }
                }, onShare = { share(context, inviteText(call.info.inviteCode, call.info.inviteLink)) })
            } else if (st.conversation.turns.isEmpty() && st.conversation.speaking.isEmpty()) {
                EmptyState(Icons.Filled.Translate, "Start talking", "Speak naturally and pause at the end of a sentence. Subtitles and the translated voice appear here.",
                    Modifier.padding(24.dp))
            } else {
                val turns = if (compact) st.conversation.last(2) else st.conversation.turns
                LazyColumn(state = listState, contentPadding = PaddingValues(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
                    items(turns, key = { it.id }) { t ->
                        SubtitleBubble(t, playing = st.conversation.playingId == t.id, textScale = st.subtitleScale,
                            myLabel = "You · ${c.language(t.sourceLang)?.name ?: t.sourceLang}",
                            peerLabel = "${st.peer?.name ?: "Them"} · translated from ${c.language(t.sourceLang)?.name ?: t.sourceLang}",
                            onRetry = { call.retry(it) })
                    }
                    st.conversation.speaking.forEach { who ->
                        item(key = "speaking-$who") { ListeningBubble(mine = who == st.me?.id, label = if (who == st.me?.id) "Listening to you…" else "${st.peer?.name ?: "They"} is speaking…") }
                    }
                }
            }
        }

        // controls
        Row(
            Modifier.fillMaxWidth().background(Brand.CardBg).navigationBarsPadding().padding(vertical = 10.dp, horizontal = 8.dp),
            horizontalArrangement = Arrangement.SpaceEvenly, verticalAlignment = Alignment.CenterVertically,
        ) {
            GlowingMicButton(
                onClick = { call.setMuted(!st.muted) },
                isMuted = st.muted,
                isListening = !st.muted && st.micStreaming,
                size = 52.dp,
            )
            CallControl(Icons.Filled.Language, myLang?.code?.substringBefore("-")?.uppercase() ?: "Lang") { showLanguageSheet = true }
            CallControl(Icons.AutoMirrored.Filled.VolumeUp, st.route?.label ?: "Audio") { showAudio = true }
            CallControl(if (st.translatedAudio) Icons.Filled.Translate else Icons.Filled.SubtitlesOff,
                if (st.translatedAudio) "Voice on" else "Subtitles only", active = !st.translatedAudio) { call.setTranslatedAudio(!st.translatedAudio) }
            CallControl(if (compact) Icons.Filled.UnfoldMore else Icons.Filled.UnfoldLess, if (compact) "Transcript" else "Focus") { compact = !compact }
            FilledIconButton(onClick = { call.end() }, modifier = Modifier.size(56.dp),   // hangs up at once, like a phone
                colors = IconButtonDefaults.filledIconButtonColors(containerColor = colors.endCall)) {
                Icon(Icons.Filled.CallEnd, contentDescription = "End call", tint = Color.White, modifier = Modifier.size(28.dp))
            }
        }
    }
}

    val langs by c.languages.collectAsStateWithLifecycle()
    if (showLanguageSheet) LanguageSheet(
        languages = langs,
        currentCode = st.me?.language ?: settings.myLanguage,
        onSelect = { newCode ->
            call.setLanguage(newCode, settings.autoDetect)
            scope.launch { c.settingsStore.update { it.copy(myLanguage = newCode) } }
        },
        onDismiss = { showLanguageSheet = false }
    )

    if (showAudio) AudioSheet(
        routes = st.routes, route = st.route, volume = st.originalVolume, scale = st.subtitleScale,
        onRoute = call::setRoute, onVolume = call::setOriginalVolume, onScale = call::setSubtitleScale, onDismiss = { showAudio = false },
    )
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun LanguageSheet(
    languages: List<Language>,
    currentCode: String,
    onSelect: (String) -> Unit,
    onDismiss: () -> Unit
) {
    ModalBottomSheet(onDismissRequest = onDismiss) {
        Column(
            Modifier.fillMaxWidth().padding(horizontal = 24.dp).padding(bottom = 32.dp)
        ) {
            Text("Switch speaking language", style = MaterialTheme.typography.titleMedium)
            Spacer(Modifier.height(4.dp))
            Text("Changes what you speak mid-call. Your peer's audio stays connected.",
                style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            Spacer(Modifier.height(16.dp))
            LazyColumn(verticalArrangement = Arrangement.spacedBy(8.dp), modifier = Modifier.heightIn(max = 360.dp)) {
                items(languages) { l ->
                    val isSelected = l.code == currentCode
                    Row(
                        Modifier.fillMaxWidth().clip(RoundedCornerShape(12.dp))
                            .background(if (isSelected) MaterialTheme.colorScheme.primaryContainer else MaterialTheme.colorScheme.surfaceVariant)
                            .clickable {
                                onSelect(l.code)
                                onDismiss()
                            }
                            .padding(horizontal = 16.dp, vertical = 12.dp),
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Column(Modifier.weight(1f)) {
                            Text(l.native, style = MaterialTheme.typography.bodyLarge, fontWeight = if (isSelected) FontWeight.Bold else FontWeight.Normal)
                            Text(l.name, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                        }
                        if (isSelected) {
                            Icon(Icons.Filled.Check, null, tint = MaterialTheme.colorScheme.primary)
                        }
                    }
                }
            }
        }
    }
}

private fun statusLabel(s: CallStatus) = when (s) {
    CallStatus.Connecting -> "Connecting…"
    CallStatus.WaitingForPeer -> "Waiting for them to join"
    CallStatus.ConnectingAudio -> "Connecting audio…"
    CallStatus.Live -> "Live translation"
    CallStatus.Reconnecting -> "Reconnecting…"
    CallStatus.Ended -> "Call ended"
    CallStatus.Failed -> "Call failed"
}

@Composable
private fun QualityChip(q: Quality, rtt: Int?, connected: Boolean) {
    val colors = LocalCallColors.current
    val (label, color) = when {
        !connected -> "No direct audio" to MaterialTheme.colorScheme.onSurfaceVariant
        q == Quality.Good -> "Good" to colors.success
        q == Quality.Fair -> "Fair" to colors.warning
        q == Quality.Poor -> "Poor" to MaterialTheme.colorScheme.error
        else -> "Connected" to colors.success
    }
    Row(Modifier.semantics { contentDescription = "Connection quality $label" }, verticalAlignment = Alignment.CenterVertically) {
        Icon(Icons.Filled.SignalCellularAlt, null, tint = color, modifier = Modifier.size(18.dp))
        Spacer(Modifier.width(4.dp))
        Text(label + (rtt?.let { " · $it ms" } ?: ""), style = MaterialTheme.typography.labelMedium, color = color)
    }
}

@Composable
private fun CallControl(icon: ImageVector, label: String, active: Boolean = false, onClick: () -> Unit) {
    Column(horizontalAlignment = Alignment.CenterHorizontally) {
        FilledTonalIconButton(onClick = onClick, modifier = Modifier.size(54.dp),
            colors = if (active) IconButtonDefaults.filledTonalIconButtonColors(containerColor = MaterialTheme.colorScheme.onSurface, contentColor = MaterialTheme.colorScheme.surface)
            else IconButtonDefaults.filledTonalIconButtonColors()) {
            Icon(icon, contentDescription = label)
        }
        Spacer(Modifier.height(4.dp))
        Text(label, style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
    }
}

@Composable
private fun InviteCard(code: String, link: String, onCopy: () -> Unit, onShare: () -> Unit) {
    Column(Modifier.fillMaxSize().padding(24.dp), verticalArrangement = Arrangement.Center, horizontalAlignment = Alignment.CenterHorizontally) {
        Text("Invite someone", style = MaterialTheme.typography.titleLarge)
        Spacer(Modifier.height(8.dp))
        Text("Share this code. The call starts when they join.", color = MaterialTheme.colorScheme.onSurfaceVariant)
        Spacer(Modifier.height(20.dp))
        Text(code.chunked(3).joinToString(" "), fontSize = 44.sp, fontWeight = FontWeight.Bold, fontFamily = FontFamily.Monospace,
            letterSpacing = 4.sp, modifier = Modifier.clip(MaterialTheme.shapes.large).background(MaterialTheme.colorScheme.surfaceContainerHigh)
                .padding(horizontal = 24.dp, vertical = 12.dp).semantics { contentDescription = "Invitation code ${code.toList().joinToString(" ")}" })
        Spacer(Modifier.height(8.dp))
        Text(link, style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
        Spacer(Modifier.height(20.dp))
        Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
            SecondaryButton("Copy", onCopy, icon = Icons.Filled.ContentCopy)
            PrimaryButton("Share", onShare, icon = Icons.Filled.Share)
        }
    }
}

private fun inviteText(code: String, link: String) =
    "Join my Sarvagyan call — we can each speak our own language. Code: $code  ($link)"

private fun share(context: Context, text: String) {
    val send = Intent(Intent.ACTION_SEND).setType("text/plain").putExtra(Intent.EXTRA_TEXT, text)
    context.startActivity(Intent.createChooser(send, "Invite to Sarvagyan").addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun AudioSheet(
    routes: List<AudioRoute>, route: AudioRoute?, volume: Float, scale: Float,
    onRoute: (AudioRoute) -> Unit, onVolume: (Float) -> Unit, onScale: (Float) -> Unit, onDismiss: () -> Unit,
) {
    ModalBottomSheet(onDismissRequest = onDismiss) {
        Column(Modifier.padding(horizontal = 24.dp, vertical = 8.dp)) {
            Text("Audio output", style = MaterialTheme.typography.titleMedium)
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp), modifier = Modifier.padding(vertical = 8.dp)) {
                routes.forEach { r -> FilterChip(selected = route == r, onClick = { onRoute(r) }, label = { Text(r.label) }) }
            }
            Text("Other person's original voice: ${"%.0f".format(volume * 100)}%", style = MaterialTheme.typography.titleMedium)
            Slider(value = volume, onValueChange = onVolume, valueRange = 0f..1f)
            Row(verticalAlignment = Alignment.CenterVertically) {
                Icon(Icons.Filled.TextFields, null)
                Spacer(Modifier.width(8.dp))
                Text("Subtitle size ${"%.0f".format(scale * 100)}%", style = MaterialTheme.typography.titleMedium)
            }
            Slider(value = scale, onValueChange = onScale, valueRange = 0.8f..1.8f)
            Spacer(Modifier.height(24.dp))
        }
    }
}

// ---------------------------------------------------------------------------------------------
// Summary
// ---------------------------------------------------------------------------------------------

@Composable
fun CallSummaryScreen(callId: String, onCallStarted: () -> Unit, onContacts: () -> Unit, onHome: () -> Unit) {
    val c = LocalContext.current.container
    val session by c.activeCall.collectAsStateWithLifecycle()
    val st = session?.takeIf { it.info.callId == callId }?.state?.collectAsStateWithLifecycle()?.value
    val settings by c.settings.collectAsStateWithLifecycle()
    val saved = remember(callId) { c.transcripts.load(callId) }
    var deleted by remember { mutableStateOf(false) }
    val scope = rememberCoroutineScope()
    val clipboard = LocalClipboard.current
    val turns = st?.conversation?.turns.orEmpty()
    val duration = st?.let { s -> s.startedAtMs?.let { ((s.endedAtMs ?: System.currentTimeMillis()) - it) / 1000 } } ?: saved?.durationS
    val languages = listOfNotNull(st?.me?.language, st?.peer?.language).distinct().map { c.language(it)?.name ?: it }
    val transcriptText = if (turns.isNotEmpty()) turns.joinToString("\n") { t ->
        val who = if (t.mine) "You" else (st?.peer?.name ?: "Them")
        "$who: ${t.original}" + (t.translation?.takeIf { it != t.original }?.let { "  →  $it" } ?: "")
    } else saved?.lines?.joinToString("\n") { "${if (it.speaker == "me") "You" else saved.peerName}: ${it.original}" + (it.translation?.let { tr -> "  →  $tr" } ?: "") } ?: ""

    val placeCall = rememberPlaceCall(onCallStarted)
    DisposableEffect(Unit) { onDispose { if (session?.info?.callId == callId) c.activeCall.value = null } }

    ScreenScaffold("Call summary", onHome) {
        st?.endReason?.let { Text(it, color = MaterialTheme.colorScheme.onSurfaceVariant); Spacer(Modifier.height(12.dp)) }
        AppCard {
            Row {
                Column(Modifier.weight(1f)) {
                    Text("Duration", color = MaterialTheme.colorScheme.onSurfaceVariant)
                    Text(duration?.let { formatDuration(it) } ?: "–", style = MaterialTheme.typography.headlineSmall)
                }
                Column(Modifier.weight(1f)) {
                    Text("Translated", color = MaterialTheme.colorScheme.onSurfaceVariant)
                    Text("${st?.conversation?.translatedCount ?: saved?.lines?.size ?: 0} utterances", style = MaterialTheme.typography.headlineSmall)
                }
            }
            if (languages.isNotEmpty()) {
                Spacer(Modifier.height(8.dp))
                Text("Languages: ${languages.joinToString(" ↔ ")}", color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
        }
        SectionTitle("Transcript")
        when {
            deleted -> Text("Transcript deleted.", color = MaterialTheme.colorScheme.onSurfaceVariant)
            transcriptText.isBlank() -> Text("Nothing was said in this call.", color = MaterialTheme.colorScheme.onSurfaceVariant)
            else -> {
                AppCard { Text(transcriptText, style = MaterialTheme.typography.bodyLarge) }
                Text(
                    if (settings.saveTranscripts) "Saved on this phone only. Audio was not recorded."
                    else "Not saved — this transcript disappears when you leave this screen. Turn on saving in Settings → Privacy.",
                    style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant, modifier = Modifier.padding(top = 8.dp),
                )
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp), modifier = Modifier.padding(top = 8.dp)) {
                    SecondaryButton("Copy", { scope.launch { clipboard.setClipEntry(ClipEntry(ClipData.newPlainText("Transcript", transcriptText))) } }, icon = Icons.Filled.ContentCopy)
                    SecondaryButton("Delete", { c.transcripts.delete(callId); deleted = true; session?.takeIf { it.info.callId == callId }?.let { c.activeCall.value = null } }, icon = Icons.Filled.Delete)
                }
            }
        }
        Spacer(Modifier.height(24.dp))
        // call the same person again directly (rings them), or pick someone from contacts
        val again = session?.takeIf { it.info.callId == callId }
        val peerId = st?.peer?.id ?: again?.info?.peerId
        val peerName = st?.peer?.name ?: again?.info?.peerName ?: saved?.peerName
        if (peerId != null && peerName != null) {
            PrimaryButton("Call $peerName again", { placeCall(peerId, peerName) }, Modifier.fillMaxWidth(), icon = Icons.Filled.Call)
            Spacer(Modifier.height(8.dp))
        }
        SecondaryButton("Open contacts", onContacts, Modifier.fillMaxWidth(), icon = Icons.Filled.People)
        Spacer(Modifier.height(8.dp))
        SecondaryButton("Back to home", onHome, Modifier.fillMaxWidth())
        Spacer(Modifier.height(24.dp))
    }
}

@Composable
private fun RingingCard(name: String, reachable: Boolean) {
    Column(Modifier.fillMaxSize().padding(24.dp), horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.Center) {
        Avatar(name, LocalCallColors.current.peer, 96.dp)
        Spacer(Modifier.height(16.dp))
        Text("Calling $name…", style = MaterialTheme.typography.headlineSmall)
        Spacer(Modifier.height(8.dp))
        StatusChip(if (reachable) "Ringing" else "Their phone is offline", LocalCallColors.current.warning, pulsing = true)
        if (!reachable) {
            Spacer(Modifier.height(8.dp))
            Text("Sarvagyan isn't open on their phone right now. If they don't answer, you can leave a voicemail.",
                color = MaterialTheme.colorScheme.onSurfaceVariant, style = MaterialTheme.typography.bodyMedium)
        }
    }
}

@Composable
private fun UnansweredCard(reason: String, name: String, onVoicemail: (() -> Unit)?, onClose: () -> Unit) {
    Column(Modifier.fillMaxSize().padding(24.dp), horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.Center) {
        Avatar(name, LocalCallColors.current.peer, 96.dp)
        Spacer(Modifier.height(16.dp))
        Text(reason, style = MaterialTheme.typography.headlineSmall)
        Spacer(Modifier.height(24.dp))
        if (onVoicemail != null) {
            PrimaryButton("Leave a voicemail", onVoicemail, Modifier.fillMaxWidth(), icon = Icons.Filled.Voicemail)
            Spacer(Modifier.height(8.dp))
        }
        SecondaryButton("Close", onClose, Modifier.fillMaxWidth())
    }
}
