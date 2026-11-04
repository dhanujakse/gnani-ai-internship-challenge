package ai.mack.sarvagyan.ui.screens

import android.Manifest
import android.content.Context
import android.content.pm.PackageManager
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.Reply
import androidx.compose.material.icons.automirrored.filled.Send
import androidx.compose.material.icons.filled.Delete
import androidx.compose.material.icons.filled.Mic
import androidx.compose.material.icons.filled.PlayArrow
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material.icons.filled.Stop
import androidx.compose.material.icons.filled.Voicemail
import androidx.compose.material3.FilterChip
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Surface
import androidx.compose.material3.Tab
import androidx.compose.material3.TabRow
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableFloatStateOf
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableLongStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import androidx.core.content.ContextCompat
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import ai.mack.sarvagyan.call.CallStatus
import ai.mack.sarvagyan.call.VOICEMAIL_MAX_MS
import ai.mack.sarvagyan.call.VoicemailPlayer
import ai.mack.sarvagyan.call.VoicemailRecorder
import ai.mack.sarvagyan.container
import ai.mack.sarvagyan.data.ApiException
import ai.mack.sarvagyan.data.Voicemail
import ai.mack.sarvagyan.data.VoicemailsResponse
import ai.mack.sarvagyan.data.formatDuration
import ai.mack.sarvagyan.ui.components.AppCard
import ai.mack.sarvagyan.ui.components.Avatar
import ai.mack.sarvagyan.ui.components.EmptyState
import ai.mack.sarvagyan.ui.components.ErrorBanner
import ai.mack.sarvagyan.ui.components.LoadingView
import ai.mack.sarvagyan.ui.components.PrimaryButton
import ai.mack.sarvagyan.ui.components.SecondaryButton
import ai.mack.sarvagyan.ui.components.StatusChip
import ai.mack.sarvagyan.ui.theme.Brand
import ai.mack.sarvagyan.ui.theme.LocalCallColors
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import java.text.DateFormat
import java.util.Date
import java.util.concurrent.atomic.AtomicBoolean

private const val MIN_RECORDING_BYTES = 16_000 // 0.5 s at 16 kHz

@Composable
fun VoicemailScreen(initialTab: Int, onBack: () -> Unit, onRecord: (toId: String?, toName: String?) -> Unit) {
    val c = LocalContext.current.container
    val scope = rememberCoroutineScope()
    var data by remember { mutableStateOf<VoicemailsResponse?>(null) }
    var error by remember { mutableStateOf<String?>(null) }
    var tab by remember { mutableIntStateOf(initialTab) }
    var playingId by remember { mutableStateOf<String?>(null) }
    var playJob by remember { mutableStateOf<Job?>(null) }

    suspend fun load() {
        try {
            data = c.api.voicemails()
            error = null
        } catch (e: ApiException) {
            error = e.message
            if (data == null) data = VoicemailsResponse(emptyList(), emptyList())
        }
    }
    LaunchedEffect(Unit) {
        c.syncLanguage() // voicemails to me are translated into the language I chose
        while (true) {
            load()
            delay(if (data?.sent?.any { it.status == "processing" } == true) 3_000 else 15_000)
        }
    }
    DisposableEffect(Unit) { onDispose { playJob?.cancel() } }

    fun play(v: Voicemail) {
        playJob?.cancel()
        if (playingId == v.id) { playingId = null; return }
        playingId = v.id
        playJob = scope.launch {
            val player = VoicemailPlayer()
            try {
                c.api.streamVoicemailAudio(v.id) { buf, n -> player.write(buf, n) }
                player.drain()
            } catch (e: ApiException) {
                error = e.message
            } finally {
                player.release()
                if (playingId == v.id) playingId = null
            }
            load()
        }
    }

    fun delete(v: Voicemail) {
        scope.launch {
            try { c.api.deleteVoicemail(v.id) } catch (e: ApiException) { error = e.message }
            load()
        }
    }

    ScreenScaffold("Voicemail", onBack) {
        PrimaryButton("New voicemail", { onRecord(null, null) }, Modifier.fillMaxWidth(), icon = Icons.Filled.Mic)
        Spacer(Modifier.height(12.dp))
        val unread = data?.unread ?: 0
        TabRow(selectedTabIndex = tab, containerColor = Brand.CardBg) {
            Tab(tab == 0, { tab = 0 }, text = { Text(if (unread > 0) "Inbox ($unread new)" else "Inbox") })
            Tab(tab == 1, { tab = 1 }, text = { Text("Sent") })
        }
        Spacer(Modifier.height(12.dp))
        error?.let { ErrorBanner(it, onRetry = { scope.launch { load() } }); Spacer(Modifier.height(12.dp)) }
        val d = data
        when {
            d == null -> LoadingView("Loading voicemail…")
            tab == 0 && d.inbox.isEmpty() -> EmptyState(Icons.Filled.Voicemail, "No voicemail yet",
                "When someone leaves you a voicemail, it appears here in your language.")
            tab == 1 && d.sent.isEmpty() -> EmptyState(Icons.Filled.Voicemail, "Nothing sent yet",
                "Record a voicemail in your language. The other person hears it in theirs.")
            tab == 0 -> d.inbox.forEach { v ->
                VoicemailCard(v, sent = false, playing = playingId == v.id, onPlay = { play(v) },
                    onReply = { onRecord(v.contact.id, v.contact.name) }, onDelete = { delete(v) })
                Spacer(Modifier.height(10.dp))
            }
            else -> d.sent.forEach { v ->
                VoicemailCard(v, sent = true, playing = playingId == v.id, onPlay = { play(v) },
                    onReply = null, onDelete = { delete(v) })
                Spacer(Modifier.height(10.dp))
            }
        }
        Spacer(Modifier.height(8.dp))
        Text("Only the text of a voicemail is kept on the server, for up to 7 days or until it is deleted. " +
            "Recordings are never stored; the translated voice is created when you press play.",
            style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
        Spacer(Modifier.height(24.dp))
    }
}

@Composable
private fun VoicemailCard(
    v: Voicemail, sent: Boolean, playing: Boolean, onPlay: () -> Unit, onReply: (() -> Unit)?, onDelete: () -> Unit,
) {
    val c = LocalContext.current.container
    val colors = LocalCallColors.current
    val from = c.language(v.sourceLang)?.name ?: v.sourceLang
    val to = c.language(v.targetLang)?.name ?: v.targetLang
    AppCard {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Avatar(v.contact.name, if (sent) colors.me else colors.peer, 40.dp)
            Spacer(Modifier.width(12.dp))
            Column(Modifier.weight(1f)) {
                Text(if (sent) "To ${v.contact.name}" else v.contact.name, style = MaterialTheme.typography.titleMedium)
                val meta = listOf(
                    DateFormat.getDateTimeInstance(DateFormat.SHORT, DateFormat.SHORT).format(Date((v.createdAt * 1000).toLong())),
                    formatDuration(v.durationMs / 1000),
                    "$from → $to",
                ).joinToString(" · ")
                Text(meta, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
            when {
                sent && v.status == "processing" -> StatusChip("Translating…", colors.warning, pulsing = true)
                sent && v.status == "failed" -> StatusChip("Not sent", MaterialTheme.colorScheme.error)
                sent -> StatusChip(if (v.heard) "Heard" else "Delivered", colors.success)
                !v.heard -> StatusChip("New", colors.success)
            }
        }
        if (v.status == "failed") {
            Spacer(Modifier.height(8.dp))
            Text(v.error ?: "Couldn't translate this voicemail.", color = MaterialTheme.colorScheme.error)
        }
        v.translation?.let {
            Spacer(Modifier.height(10.dp))
            if (sent) Text("They hear ($to):", style = MaterialTheme.typography.labelMedium, color = Brand.HighlightAccent)
            Text(it, style = MaterialTheme.typography.bodyLarge)
        }
        if (v.original != null && v.original != v.translation) {
            Spacer(Modifier.height(6.dp))
            Text("${if (sent) "You said" else "Original"} ($from): ${v.original}", style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
        Spacer(Modifier.height(10.dp))
        Row(verticalAlignment = Alignment.CenterVertically) {
            if (v.status == "ready") {
                val label = if (playing) "Stop" else if (sent) "Preview" else "Play in $to"
                if (sent) SecondaryButton(label, onPlay, icon = if (playing) Icons.Filled.Stop else Icons.Filled.PlayArrow)
                else PrimaryButton(label, onPlay, icon = if (playing) Icons.Filled.Stop else Icons.Filled.PlayArrow)
            }
            Spacer(Modifier.weight(1f))
            onReply?.let { IconButton(onClick = it) { Icon(Icons.AutoMirrored.Filled.Reply, contentDescription = "Reply with a voicemail") } }
            IconButton(onClick = onDelete) { Icon(Icons.Filled.Delete, contentDescription = "Delete voicemail") }
        }
    }
}

private enum class RecPhase { Idle, Recording, Recorded, Sending }

private fun hasMicPermission(context: Context) =
    ContextCompat.checkSelfPermission(context, Manifest.permission.RECORD_AUDIO) == PackageManager.PERMISSION_GRANTED

@OptIn(ExperimentalLayoutApi::class)
@Composable
fun RecordVoicemailScreen(toId: String?, toName: String?, onBack: () -> Unit, onLanguages: () -> Unit, onSent: () -> Unit) {
    val context = LocalContext.current
    val c = context.container
    val scope = rememberCoroutineScope()
    val settings by c.settings.collectAsStateWithLifecycle()
    val active by c.activeCall.collectAsStateWithLifecycle()
    val callState = active?.state?.collectAsStateWithLifecycle()?.value
    val inCall = callState != null && callState.status != CallStatus.Ended && callState.status != CallStatus.Failed

    // recipient: a person picked from calls/favourites, or an email address
    var pickedId by remember { mutableStateOf(toId) }
    var pickedName by remember { mutableStateOf(toName) }
    var email by remember { mutableStateOf("") }
    var people by remember { mutableStateOf<List<Pair<String, String>>>(emptyList()) }
    LaunchedEffect(Unit) {
        val favs = runCatching { c.api.favourites().contacts.map { it.id to it.name } }.getOrDefault(emptyList())
        val recent = runCatching { c.api.history().calls.mapNotNull { h -> h.peer?.let { it.id to (it.name ?: "Unknown") } } }
            .getOrDefault(emptyList())
        people = (favs + recent).distinctBy { it.first }.take(12)
    }
    val recipient = pickedId ?: email.trim().takeIf { "@" in it && "." in it.substringAfter("@") }

    var phase by remember { mutableStateOf(RecPhase.Idle) }
    var elapsed by remember { mutableLongStateOf(0L) }
    var level by remember { mutableFloatStateOf(0f) }
    var pcm by remember { mutableStateOf<ByteArray?>(null) }
    var error by remember { mutableStateOf<String?>(null) }
    val stop = remember { AtomicBoolean(false) }
    var micGranted by remember { mutableStateOf(hasMicPermission(context)) }
    val permission = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { ok ->
        micGranted = ok
        if (!ok) error = "Sarvagyan needs the microphone to record a voicemail."
    }
    DisposableEffect(Unit) { onDispose { stop.set(true) } }

    fun startRecording() {
        if (!micGranted) { permission.launch(Manifest.permission.RECORD_AUDIO); return }
        error = null
        pcm = null
        elapsed = 0
        stop.set(false)
        phase = RecPhase.Recording
        scope.launch {
            try {
                val audio = VoicemailRecorder.record(shouldStop = { stop.get() }, onProgress = { ms, l -> elapsed = ms; level = l })
                if (audio.size < MIN_RECORDING_BYTES) {
                    error = "That was too short. Hold on a little longer."
                    phase = RecPhase.Idle
                } else {
                    pcm = audio
                    phase = RecPhase.Recorded
                }
            } catch (e: Exception) {
                error = e.message ?: "Recording failed."
                phase = RecPhase.Idle
            }
        }
    }

    fun send() {
        val to = recipient ?: return
        val audio = pcm ?: return
        phase = RecPhase.Sending
        scope.launch {
            try {
                c.api.sendVoicemail(to, settings.myLanguage, settings.autoDetect, audio)
                pcm = null
                onSent()
            } catch (e: ApiException) {
                error = e.message
                phase = RecPhase.Recorded
            }
        }
    }

    ScreenScaffold("New voicemail", onBack) {
        Text("To", style = MaterialTheme.typography.titleMedium)
        Spacer(Modifier.height(8.dp))
        if (people.isNotEmpty() || pickedName != null) {
            FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                val shown = if (pickedId != null && people.none { it.first == pickedId }) listOf(pickedId!! to (pickedName ?: "")) + people else people
                shown.forEach { (id, name) ->
                    FilterChip(selected = pickedId == id, onClick = {
                        if (pickedId == id) { pickedId = null; pickedName = null } else { pickedId = id; pickedName = name; email = "" }
                    }, label = { Text(name) })
                }
            }
            Spacer(Modifier.height(8.dp))
        }
        OutlinedTextField(
            email, { email = it; if (it.isNotBlank()) { pickedId = null; pickedName = null } },
            label = { Text("…or their email address") }, singleLine = true, modifier = Modifier.fillMaxWidth(),
            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Email, imeAction = ImeAction.Done),
        )
        Spacer(Modifier.height(16.dp))

        AppCard(Modifier.clickable(role = Role.Button, onClick = onLanguages)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Column(Modifier.weight(1f)) {
                    val mine = c.language(settings.myLanguage)?.name ?: settings.myLanguage
                    Text(if (settings.autoDetect) "You speak: detected automatically" else "You speak: $mine",
                        style = MaterialTheme.typography.titleMedium)
                    Text("They hear it in the language they chose. Mixing in English words (Tanglish) is fine.",
                        style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
                Text("Change", color = MaterialTheme.colorScheme.primary)
            }
        }
        Spacer(Modifier.height(24.dp))

        if (inCall) {
            ErrorBanner("You're in a call. Finish the call to record a voicemail.")
        } else {
            RecordButton(phase == RecPhase.Recording, level) {
                when (phase) {
                    RecPhase.Recording -> stop.set(true)
                    RecPhase.Sending -> Unit
                    else -> startRecording()
                }
            }
            Spacer(Modifier.height(12.dp))
            val status = when (phase) {
                RecPhase.Idle -> "Tap to record (up to ${VOICEMAIL_MAX_MS / 1000} seconds)"
                RecPhase.Recording -> "Recording ${formatDuration(elapsed / 1000)} · tap to stop"
                RecPhase.Recorded, RecPhase.Sending -> "Recorded ${formatDuration((pcm?.size ?: 0) / 32_000L)}"
            }
            Text(status, style = MaterialTheme.typography.titleMedium, modifier = Modifier.fillMaxWidth(), textAlign = TextAlign.Center)
            if (phase == RecPhase.Recording) {
                Spacer(Modifier.height(8.dp))
                LinearProgressIndicator(progress = { elapsed.toFloat() / VOICEMAIL_MAX_MS }, modifier = Modifier.fillMaxWidth())
            }
        }
        error?.let { Spacer(Modifier.height(12.dp)); ErrorBanner(it, onDismiss = { error = null }) }
        Spacer(Modifier.height(20.dp))
        if (phase == RecPhase.Recorded || phase == RecPhase.Sending) {
            PrimaryButton(
                if (recipient == null) "Choose who to send to" else "Send voicemail", { send() }, Modifier.fillMaxWidth(),
                enabled = recipient != null, icon = Icons.AutoMirrored.Filled.Send, loading = phase == RecPhase.Sending,
            )
            Spacer(Modifier.height(8.dp))
            TextButton(onClick = { startRecording() }, enabled = phase != RecPhase.Sending, modifier = Modifier.fillMaxWidth()) {
                Icon(Icons.Filled.Refresh, null)
                Spacer(Modifier.width(6.dp))
                Text("Record again")
            }
        }
        Spacer(Modifier.height(24.dp))
    }
}

@Composable
private fun RecordButton(recording: Boolean, level: Float, onClick: () -> Unit) {
    Box(Modifier.fillMaxWidth(), contentAlignment = Alignment.Center) {
        val ring = if (recording) 112.dp + (40 * level).dp else 112.dp
        Box(Modifier.size(ring).background(Brand.EmeraldGlowSubtle, CircleShape))
        Surface(
            onClick = onClick, shape = CircleShape, modifier = Modifier.size(96.dp),
            color = if (recording) Brand.Danger else Brand.PrimaryAccent,
        ) {
            Box(contentAlignment = Alignment.Center) {
                Icon(if (recording) Icons.Filled.Stop else Icons.Filled.Mic,
                    contentDescription = if (recording) "Stop recording" else "Start recording",
                    tint = Brand.PrimaryBg, modifier = Modifier.size(44.dp))
            }
        }
    }
}
