package ai.mack.sarvagyan.ui.screens

import android.Manifest
import android.content.Context
import android.content.pm.PackageManager
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.combinedClickable
import androidx.compose.material.icons.filled.Done
import androidx.compose.material.icons.filled.DoneAll
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import ai.mack.sarvagyan.data.str
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.automirrored.filled.Chat
import androidx.compose.material.icons.automirrored.filled.Reply
import androidx.compose.material.icons.automirrored.filled.Send
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.Check
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.Delete
import androidx.compose.material.icons.filled.Group
import androidx.compose.material.icons.filled.GroupAdd
import androidx.compose.material.icons.filled.Mic
import androidx.compose.material.icons.filled.Person
import androidx.compose.material.icons.filled.PersonAdd
import androidx.compose.material.icons.filled.PlayArrow
import androidx.compose.material.icons.filled.RecordVoiceOver
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material.icons.filled.Search
import androidx.compose.material.icons.filled.Stop
import androidx.compose.material.icons.filled.Translate
import androidx.compose.material.icons.filled.Voicemail
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.FilterChip
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.InputChip
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
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.mutableStateMapOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.core.content.ContextCompat
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import ai.mack.sarvagyan.call.CallStatus
import ai.mack.sarvagyan.call.VOICEMAIL_MAX_MS
import ai.mack.sarvagyan.call.VoicemailPlayer
import ai.mack.sarvagyan.call.VoicemailRecorder
import ai.mack.sarvagyan.container
import ai.mack.sarvagyan.data.ApiException
import ai.mack.sarvagyan.data.ChatMessage
import ai.mack.sarvagyan.data.Conversation
import ai.mack.sarvagyan.data.UserSearchResult
import ai.mack.sarvagyan.data.Voicemail
import ai.mack.sarvagyan.data.VoicemailsResponse
import ai.mack.sarvagyan.data.formatDuration
import ai.mack.sarvagyan.ui.components.AppCard
import ai.mack.sarvagyan.ui.components.Avatar
import ai.mack.sarvagyan.ui.components.EmeraldAnimatedBackground
import ai.mack.sarvagyan.ui.components.EmptyState
import ai.mack.sarvagyan.ui.components.ErrorBanner
import ai.mack.sarvagyan.ui.components.LoadingView
import ai.mack.sarvagyan.ui.components.PrimaryButton
import ai.mack.sarvagyan.ui.components.SecondaryButton
import ai.mack.sarvagyan.ui.components.SectionTitle
import ai.mack.sarvagyan.ui.components.StatusChip
import ai.mack.sarvagyan.ui.theme.Brand
import ai.mack.sarvagyan.ui.theme.LocalCallColors
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import java.text.DateFormat
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import java.util.concurrent.atomic.AtomicBoolean

private const val MIN_RECORDING_BYTES = 16_000 // 0.5 s at 16 kHz

/**
 * Backward compatibility wrapper for existing Voicemail route.
 */
@Composable
fun VoicemailScreen(
    initialTab: Int = 0,
    onBack: () -> Unit,
    onRecord: (toId: String?, toName: String?) -> Unit,
    onOpenConversation: (String) -> Unit = {},
) {
    GlobalChatScreen(
        initialTab = if (initialTab == 1) 2 else initialTab,
        onBack = onBack,
        onOpenConversation = onOpenConversation,
        onRecordVoicemail = onRecord,
    )
}

/**
 * Global Chat: Evolved communication center containing:
 * - Direct 1-to-1 chats
 * - Multilingual group chats
 * - Voice Messages (fully preserved voicemail functionality)
 */
@Composable
fun GlobalChatScreen(
    initialTab: Int = 0,
    onBack: () -> Unit,
    onOpenConversation: (String) -> Unit,
    onRecordVoicemail: (toId: String?, toName: String?) -> Unit,
) {
    val c = LocalContext.current.container
    val scope = rememberCoroutineScope()
    var topTab by remember { mutableIntStateOf(initialTab.coerceIn(0, 2)) }

    // Conversations state
    var conversations by remember { mutableStateOf<List<Conversation>?>(null) }
    var chatError by remember { mutableStateOf<String?>(null) }
    var showSearchUser by remember { mutableStateOf(false) }
    var showNewGroup by remember { mutableStateOf(false) }

    // Voicemails state
    var vmData by remember { mutableStateOf<VoicemailsResponse?>(null) }
    var vmError by remember { mutableStateOf<String?>(null) }
    var vmSubTab by remember { mutableIntStateOf(0) } // 0: Inbox, 1: Sent
    var playingId by remember { mutableStateOf<String?>(null) }
    var playJob by remember { mutableStateOf<Job?>(null) }
    var activePlayer by remember { mutableStateOf<VoicemailPlayer?>(null) }

    suspend fun loadConversations() {
        try {
            val res = c.api.conversations()
            conversations = res.conversations
            chatError = null
        } catch (e: ApiException) {
            chatError = e.message
            if (conversations == null) conversations = emptyList()
        }
    }

    suspend fun loadVoicemails() {
        try {
            vmData = c.api.voicemails()
            vmError = null
        } catch (e: ApiException) {
            vmError = e.message
            if (vmData == null) vmData = VoicemailsResponse(emptyList(), emptyList())
        }
    }

    LaunchedEffect(Unit) {
        c.syncLanguage()
        while (true) {
            loadConversations()
            loadVoicemails()
            delay(5_000)
        }
    }

    DisposableEffect(Unit) {
        onDispose {
            playJob?.cancel()
            activePlayer?.release()
            activePlayer = null
        }
    }

    fun playVoicemail(v: Voicemail) {
        val wasPlayingThis = (playingId == v.id)
        playJob?.cancel()
        activePlayer?.release()
        activePlayer = null
        playingId = null

        if (wasPlayingThis) return

        playingId = v.id
        playJob = scope.launch {
            val player = VoicemailPlayer()
            activePlayer = player
            try {
                c.api.streamVoicemailAudio(v.id) { buf, n -> player.write(buf, n) }
                player.drain()
            } catch (e: Exception) {
                if (e !is CancellationException) {
                    vmError = (e as? ApiException)?.message ?: e.message
                }
            } finally {
                player.release()
                if (activePlayer === player) activePlayer = null
                if (playingId == v.id) playingId = null
            }
            loadVoicemails()
        }
    }

    fun deleteVoicemail(v: Voicemail) {
        scope.launch {
            try { c.api.deleteVoicemail(v.id) } catch (e: ApiException) { vmError = e.message }
            loadVoicemails()
        }
    }

    val unreadVoicemail = vmData?.unread ?: 0

    ScreenScaffold("Global Chat", onBack) {
        TabRow(selectedTabIndex = topTab, containerColor = Brand.CardBg) {
            Tab(topTab == 0, { topTab = 0 }, text = { Text("Chats") })
            Tab(topTab == 1, { topTab = 1 }, text = { Text("Groups") })
            Tab(
                topTab == 2, { topTab = 2 },
                text = { Text(if (unreadVoicemail > 0) "Voice ($unreadVoicemail)" else "Voice") },
            )
        }
        Spacer(Modifier.height(14.dp))

        when (topTab) {
            0 -> {
                // Chats tab
                PrimaryButton("New chat", { showSearchUser = true }, Modifier.fillMaxWidth(), icon = Icons.Filled.PersonAdd)
                Spacer(Modifier.height(12.dp))
                chatError?.let { ErrorBanner(it, onRetry = { scope.launch { loadConversations() } }); Spacer(Modifier.height(12.dp)) }

                val directChats = conversations?.filter { !it.isGroup }
                when {
                    directChats == null -> LoadingView("Loading chats…")
                    directChats.isEmpty() -> EmptyState(
                        Icons.AutoMirrored.Filled.Chat, "No chats yet",
                        "Find other users by username to start a private multilingual chat.",
                    )
                    else -> directChats.forEach { conv ->
                        ConversationCard(
                            conversation = conv,
                            onClick = { onOpenConversation(conv.id) },
                        )
                        Spacer(Modifier.height(10.dp))
                    }
                }
            }
            1 -> {
                // Groups tab
                PrimaryButton("New group", { showNewGroup = true }, Modifier.fillMaxWidth(), icon = Icons.Filled.GroupAdd)
                Spacer(Modifier.height(12.dp))
                chatError?.let { ErrorBanner(it, onRetry = { scope.launch { loadConversations() } }); Spacer(Modifier.height(12.dp)) }

                val groupChats = conversations?.filter { it.isGroup }
                when {
                    groupChats == null -> LoadingView("Loading groups…")
                    groupChats.isEmpty() -> EmptyState(
                        Icons.Filled.Group, "No groups yet",
                        "Create a group to communicate with multiple members across different languages.",
                    )
                    else -> groupChats.forEach { conv ->
                        ConversationCard(
                            conversation = conv,
                            onClick = { onOpenConversation(conv.id) },
                        )
                        Spacer(Modifier.height(10.dp))
                    }
                }
            }
            2 -> {
                // Voice Messages tab (fully preserved Voicemail implementation)
                PrimaryButton("New voice message", { onRecordVoicemail(null, null) }, Modifier.fillMaxWidth(), icon = Icons.Filled.Mic)
                Spacer(Modifier.height(12.dp))
                TabRow(selectedTabIndex = vmSubTab, containerColor = Brand.CardBg) {
                    Tab(vmSubTab == 0, { vmSubTab = 0 }, text = { Text(if (unreadVoicemail > 0) "Inbox ($unreadVoicemail new)" else "Inbox") })
                    Tab(vmSubTab == 1, { vmSubTab = 1 }, text = { Text("Sent") })
                }
                Spacer(Modifier.height(12.dp))
                vmError?.let { ErrorBanner(it, onRetry = { scope.launch { loadVoicemails() } }); Spacer(Modifier.height(12.dp)) }
                val d = vmData
                when {
                    d == null -> LoadingView("Loading voice messages…")
                    vmSubTab == 0 && d.inbox.isEmpty() -> EmptyState(
                        Icons.Filled.Voicemail, "No voice messages yet",
                        "When someone leaves you a voice message, it appears here translated into your language.",
                    )
                    vmSubTab == 1 && d.sent.isEmpty() -> EmptyState(
                        Icons.Filled.Voicemail, "Nothing sent yet",
                        "Record a voice message in your language. The other person hears it in theirs.",
                    )
                    vmSubTab == 0 -> d.inbox.forEach { v ->
                        VoicemailCard(
                            v, sent = false, playing = playingId == v.id, onPlay = { playVoicemail(v) },
                            onReply = { onRecordVoicemail(v.contact.id, v.contact.name) }, onDelete = { deleteVoicemail(v) },
                        )
                        Spacer(Modifier.height(10.dp))
                    }
                    else -> d.sent.forEach { v ->
                        VoicemailCard(
                            v, sent = true, playing = playingId == v.id, onPlay = { playVoicemail(v) },
                            onReply = null, onDelete = { deleteVoicemail(v) },
                        )
                        Spacer(Modifier.height(10.dp))
                    }
                }
                Spacer(Modifier.height(8.dp))
                Text(
                    "Voice messages are converted to text and translated into each user's preferred language. Playback is generated fresh on play.",
                    style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
        }
        Spacer(Modifier.height(24.dp))
    }

    if (showSearchUser) {
        SearchUserDialog(
            onDismiss = { showSearchUser = false },
            onSelectUser = { user ->
                showSearchUser = false
                scope.launch {
                    try {
                        val res = c.api.directChat(username = user.username, userId = user.id)
                        onOpenConversation(res.conversation.id)
                    } catch (e: ApiException) {
                        chatError = e.message
                    }
                }
            },
        )
    }

    if (showNewGroup) {
        NewGroupDialog(
            onDismiss = { showNewGroup = false },
            onCreate = { name, memberIds ->
                showNewGroup = false
                scope.launch {
                    try {
                        val res = c.api.createGroup(name, memberIds)
                        onOpenConversation(res.conversation.id)
                    } catch (e: ApiException) {
                        chatError = e.message
                    }
                }
            },
        )
    }
}

@Composable
private fun ConversationCard(conversation: Conversation, onClick: () -> Unit) {
    val colors = LocalCallColors.current
    val title = if (conversation.isGroup) conversation.name ?: "Group" else conversation.peer?.displayName ?: conversation.name ?: "Chat"
    val username = conversation.peer?.username

    AppCard(Modifier.clickable(role = Role.Button, onClick = onClick)) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            if (conversation.isGroup) {
                Box(
                    modifier = Modifier.size(42.dp).clip(CircleShape).background(Brand.EmeraldGlowSubtle),
                    contentAlignment = Alignment.Center,
                ) {
                    Icon(Icons.Filled.Group, contentDescription = null, tint = Brand.HighlightAccent)
                }
            } else {
                Avatar(title, colors.peer, 42.dp)
            }
            Spacer(Modifier.width(12.dp))
            Column(Modifier.weight(1f)) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Text(title, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
                    if (!username.isNullOrBlank()) {
                        Spacer(Modifier.width(6.dp))
                        Text("@$username", style = MaterialTheme.typography.bodySmall, color = Brand.HighlightAccent)
                    }
                }
                val lastText = conversation.lastMessage?.originalText ?: if (conversation.isGroup) "${conversation.memberCount} members" else "Tap to chat"
                Text(
                    lastText,
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                )
            }
            if (conversation.unreadCount > 0) {
                StatusChip("${conversation.unreadCount}", colors.success)
            }
        }
    }
}

@Composable
private fun SearchUserDialog(onDismiss: () -> Unit, onSelectUser: (UserSearchResult) -> Unit) {
    val c = LocalContext.current.container
    val scope = rememberCoroutineScope()
    var query by remember { mutableStateOf("") }
    var results by remember { mutableStateOf<List<UserSearchResult>>(emptyList()) }
    var searching by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf<String?>(null) }

    LaunchedEffect(query) {
        val q = query.trim()
        if (q.isEmpty()) {
            results = emptyList()
            return@LaunchedEffect
        }
        delay(300)
        searching = true
        error = null
        try {
            results = c.api.searchUsers(q).users
        } catch (e: Exception) {
            error = (e as? ApiException)?.message ?: e.message
        } finally {
            searching = false
        }
    }

    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("Find User") },
        text = {
            Column(Modifier.fillMaxWidth().height(320.dp)) {
                OutlinedTextField(
                    value = query,
                    onValueChange = { query = it },
                    label = { Text("Username or Name") },
                    placeholder = { Text("e.g. john_doe") },
                    leadingIcon = { Icon(Icons.Filled.Search, null) },
                    singleLine = true,
                    modifier = Modifier.fillMaxWidth(),
                )
                Spacer(Modifier.height(8.dp))
                error?.let { Text(it, color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodySmall) }
                if (searching) {
                    LinearProgressIndicator(Modifier.fillMaxWidth().padding(vertical = 4.dp))
                }
                Spacer(Modifier.height(4.dp))
                LazyColumn(Modifier.weight(1f)) {
                    if (results.isEmpty() && query.isNotBlank() && !searching) {
                        item {
                            Text("No users found matching \"$query\"", style = MaterialTheme.typography.bodyMedium,
                                color = MaterialTheme.colorScheme.onSurfaceVariant, modifier = Modifier.padding(top = 16.dp))
                        }
                    }
                    items(results) { u ->
                        Row(
                            Modifier.fillMaxWidth().clickable { onSelectUser(u) }.padding(vertical = 8.dp),
                            verticalAlignment = Alignment.CenterVertically,
                        ) {
                            Avatar(u.displayName, LocalCallColors.current.peer, 36.dp)
                            Spacer(Modifier.width(10.dp))
                            Column(Modifier.weight(1f)) {
                                Text(u.displayName, style = MaterialTheme.typography.bodyLarge, fontWeight = FontWeight.Medium)
                                u.username?.let {
                                    Text("@$it", style = MaterialTheme.typography.bodySmall, color = Brand.HighlightAccent)
                                }
                            }
                            TextButton(onClick = { onSelectUser(u) }) {
                                Text("Chat")
                            }
                        }
                    }
                }
            }
        },
        confirmButton = {},
        dismissButton = {
            TextButton(onClick = onDismiss) { Text("Cancel") }
        },
    )
}

@OptIn(ExperimentalLayoutApi::class)
@Composable
private fun NewGroupDialog(onDismiss: () -> Unit, onCreate: (String, List<String>) -> Unit) {
    val c = LocalContext.current.container
    var name by remember { mutableStateOf("") }
    var query by remember { mutableStateOf("") }
    val selectedMembers = remember { mutableStateListOf<UserSearchResult>() }
    var results by remember { mutableStateOf<List<UserSearchResult>>(emptyList()) }
    var searching by remember { mutableStateOf(false) }

    LaunchedEffect(query) {
        val q = query.trim()
        if (q.isEmpty()) {
            results = emptyList()
            return@LaunchedEffect
        }
        delay(300)
        searching = true
        try {
            results = c.api.searchUsers(q).users
        } catch (_: Exception) {
            results = emptyList()
        } finally {
            searching = false
        }
    }

    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("Create Group") },
        text = {
            Column(Modifier.fillMaxWidth().height(360.dp)) {
                OutlinedTextField(
                    value = name,
                    onValueChange = { name = it },
                    label = { Text("Group Name") },
                    singleLine = true,
                    modifier = Modifier.fillMaxWidth(),
                )
                Spacer(Modifier.height(8.dp))
                if (selectedMembers.isNotEmpty()) {
                    Text("Selected Members (${selectedMembers.size}):", style = MaterialTheme.typography.labelSmall)
                    FlowRow(horizontalArrangement = Arrangement.spacedBy(4.dp)) {
                        selectedMembers.forEach { m ->
                            InputChip(
                                selected = true,
                                onClick = { selectedMembers.remove(m) },
                                label = { Text(m.displayName) },
                                trailingIcon = { Icon(Icons.Filled.Close, null, Modifier.size(16.dp)) },
                            )
                        }
                    }
                    Spacer(Modifier.height(8.dp))
                }
                OutlinedTextField(
                    value = query,
                    onValueChange = { query = it },
                    label = { Text("Search members by username") },
                    leadingIcon = { Icon(Icons.Filled.Search, null) },
                    singleLine = true,
                    modifier = Modifier.fillMaxWidth(),
                )
                if (searching) LinearProgressIndicator(Modifier.fillMaxWidth().padding(vertical = 4.dp))
                LazyColumn(Modifier.weight(1f).padding(top = 4.dp)) {
                    items(results.filter { r -> selectedMembers.none { it.id == r.id } }) { u ->
                        Row(
                            Modifier.fillMaxWidth().clickable { selectedMembers.add(u) }.padding(vertical = 6.dp),
                            verticalAlignment = Alignment.CenterVertically,
                        ) {
                            Avatar(u.displayName, LocalCallColors.current.peer, 32.dp)
                            Spacer(Modifier.width(8.dp))
                            Column(Modifier.weight(1f)) {
                                Text(u.displayName, style = MaterialTheme.typography.bodyMedium)
                                u.username?.let { Text("@$it", style = MaterialTheme.typography.bodySmall, color = Brand.HighlightAccent) }
                            }
                            IconButton(onClick = { selectedMembers.add(u) }) {
                                Icon(Icons.Filled.Add, null)
                            }
                        }
                    }
                }
            }
        },
        confirmButton = {
            PrimaryButton(
                "Create",
                onClick = { onCreate(name.trim(), selectedMembers.map { it.id }) },
                enabled = name.isNotBlank() && selectedMembers.isNotEmpty(),
            )
        },
        dismissButton = {
            TextButton(onClick = onDismiss) { Text("Cancel") }
        },
    )
}

/**
 * Dedicated conversation screen for direct and group multilingual chat.
 * Includes automatic translation toggle and voice messaging with glitch-free playback.
 */
@Composable
fun ChatConversationScreen(
    conversationId: String,
    onBack: () -> Unit,
) {
    val context = LocalContext.current
    val c = context.container
    val scope = rememberCoroutineScope()
    val me by c.user.collectAsStateWithLifecycle()
    val settings by c.settings.collectAsStateWithLifecycle()

    var conversation by remember { mutableStateOf<Conversation?>(null) }
    var messages by remember { mutableStateOf<List<ChatMessage>>(emptyList()) }
    var textInput by remember { mutableStateOf("") }
    var sending by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf<String?>(null) }

    // Toggle map for viewing original text vs translated text
    val showOriginalMap = remember { mutableStateMapOf<String, Boolean>() }

    // Audio playback state
    var playingAudioId by remember { mutableStateOf<String?>(null) }
    var playJob by remember { mutableStateOf<Job?>(null) }
    var activePlayer by remember { mutableStateOf<VoicemailPlayer?>(null) }

    // Voice recording state
    var isRecording by remember { mutableStateOf(false) }
    var recordElapsed by remember { mutableLongStateOf(0L) }
    var recordLevel by remember { mutableFloatStateOf(0f) }
    val recordStop = remember { AtomicBoolean(false) }
    var micGranted by remember { mutableStateOf(hasMicPermission(context)) }
    val permission = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { ok ->
        micGranted = ok
        if (!ok) error = "Microphone permission is required to send voice messages."
    }

    val listState = rememberLazyListState()

    suspend fun loadMessages() {
        try {
            val res = c.api.chatMessages(conversationId)
            messages = res.messages
            error = null
        } catch (e: ApiException) {
            error = e.message
        }
    }

    LaunchedEffect(conversationId) {
        runCatching {
            conversation = c.api.conversation(conversationId).conversation
        }
        while (true) {
            loadMessages()
            delay(2_500)
        }
    }
    // new messages, read receipts and deletions arrive at once over the app's connection
    LaunchedEffect(conversationId) {
        c.appSocket.events.collect { ev ->
            if (ev.str("conversation_id") == conversationId &&
                ev.str("type") in setOf("message", "chat_read", "message_deleted")) loadMessages()
        }
    }

    LaunchedEffect(messages.size) {
        if (messages.isNotEmpty()) {
            listState.animateScrollToItem(messages.size - 1)
        }
    }

    DisposableEffect(Unit) {
        onDispose {
            playJob?.cancel()
            activePlayer?.release()
            activePlayer = null
            recordStop.set(true)
        }
    }

    fun playAudio(audioId: String) {
        val wasPlayingThis = (playingAudioId == audioId)
        playJob?.cancel()
        activePlayer?.release()
        activePlayer = null
        playingAudioId = null

        if (wasPlayingThis) return

        playingAudioId = audioId
        playJob = scope.launch {
            val player = VoicemailPlayer()
            activePlayer = player
            try {
                c.api.streamChatAudio(audioId) { buf, n -> player.write(buf, n) }
                player.drain()
            } catch (e: Exception) {
                if (e !is CancellationException) {
                    error = (e as? ApiException)?.message ?: e.message
                }
            } finally {
                player.release()
                if (activePlayer === player) activePlayer = null
                if (playingAudioId == audioId) playingAudioId = null
            }
        }
    }

    fun sendText() {
        val text = textInput.trim()
        if (text.isEmpty() || sending) return
        textInput = ""
        sending = true
        scope.launch {
            try {
                val res = c.api.sendChatMessage(conversationId, text, language = settings.myLanguage)
                loadMessages()
            } catch (e: ApiException) {
                error = e.message
            } finally {
                sending = false
            }
        }
    }

    fun startVoiceRecording() {
        if (!micGranted) {
            permission.launch(Manifest.permission.RECORD_AUDIO)
            return
        }
        isRecording = true
        recordElapsed = 0L
        recordStop.set(false)
        scope.launch {
            try {
                val pcm = VoicemailRecorder.record(
                    maxMs = VOICEMAIL_MAX_MS,
                    shouldStop = { recordStop.get() },
                    onProgress = { ms, lvl ->
                        recordElapsed = ms
                        recordLevel = lvl
                    },
                )
                if (pcm.size >= MIN_RECORDING_BYTES && !recordStop.get()) {
                    c.api.sendChatVoice(conversationId, language = settings.myLanguage, pcm = pcm)
                    loadMessages()
                }
            } catch (e: Exception) {
                if (e !is CancellationException) {
                    error = (e as? ApiException)?.message ?: e.message
                }
            } finally {
                isRecording = false
            }
        }
    }

    val title = conversation?.let { conv ->
        if (conv.isGroup) conv.name ?: "Group" else conv.peer?.displayName ?: conv.name ?: "Chat"
    } ?: "Chat"
    val subtitle = conversation?.let { conv ->
        if (conv.isGroup) "${conv.memberCount} members"
        else conv.peer?.username?.let { "@$it" } ?: ""
    } ?: ""

    EmeraldAnimatedBackground {
        Column(
            Modifier.fillMaxSize().imePadding().padding(horizontal = 16.dp, vertical = 8.dp),
        ) {
            // Header
            Row(
                Modifier.fillMaxWidth().padding(vertical = 4.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                IconButton(onClick = onBack) {
                    Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "Back", tint = Brand.HighlightAccent)
                }
                Spacer(Modifier.width(4.dp))
                Column(Modifier.weight(1f)) {
                    Text(title, style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.SemiBold, maxLines = 1)
                    if (subtitle.isNotBlank()) {
                        Text(subtitle, style = MaterialTheme.typography.bodySmall, color = Brand.HighlightAccent)
                    }
                }
            }

            error?.let {
                Spacer(Modifier.height(4.dp))
                ErrorBanner(it, onDismiss = { error = null })
            }

            // Message list
            LazyColumn(
                state = listState,
                modifier = Modifier.weight(1f).fillMaxWidth(),
                verticalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                items(messages) { msg ->
                    val isMe = msg.senderId == me?.id
                    val isOrig = showOriginalMap[msg.id] == true
                    val displayText = if (isOrig) msg.originalText else (msg.translatedText ?: msg.originalText)

                    ChatMessageBubble(
                        message = msg,
                        isMe = isMe,
                        displayText = displayText,
                        showingOriginal = isOrig,
                        isPlaying = playingAudioId == msg.audioId,
                        onToggleOriginal = { showOriginalMap[msg.id] = !isOrig },
                        onPlayAudio = { msg.audioId?.let { playAudio(it) } },
                        onDelete = { everyone ->
                            scope.launch {
                                try { c.api.deleteChatMessage(msg.id, everyone); loadMessages() } catch (e: ApiException) { error = e.message }
                            }
                        },
                    )
                }
            }

            Spacer(Modifier.height(8.dp))

            // Bottom Input Bar
            if (isRecording) {
                // Recording active bar
                Row(
                    Modifier.fillMaxWidth().background(Brand.CardBg, RoundedCornerShape(24.dp))
                        .border(1.dp, Brand.Borders, RoundedCornerShape(24.dp)).padding(12.dp),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    Box(Modifier.size(12.dp).clip(CircleShape).background(Brand.Danger))
                    Spacer(Modifier.width(8.dp))
                    Text(
                        "Recording ${formatDuration(recordElapsed / 1000)}",
                        style = MaterialTheme.typography.bodyMedium,
                        fontWeight = FontWeight.Medium,
                        color = Brand.Danger,
                    )
                    Spacer(Modifier.weight(1f))
                    IconButton(onClick = { recordStop.set(true); isRecording = false }) {
                        Icon(Icons.Filled.Close, contentDescription = "Cancel", tint = MaterialTheme.colorScheme.error)
                    }
                    IconButton(onClick = { recordStop.set(true) }) {
                        Icon(Icons.Filled.Check, contentDescription = "Send", tint = Brand.HighlightAccent)
                    }
                }
            } else {
                // Normal text + mic input bar
                Row(
                    Modifier.fillMaxWidth(),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    OutlinedTextField(
                        value = textInput,
                        onValueChange = { textInput = it },
                        placeholder = { Text("Message in your language…") },
                        modifier = Modifier.weight(1f),
                        shape = RoundedCornerShape(24.dp),
                        singleLine = false,
                        maxLines = 4,
                        keyboardOptions = KeyboardOptions(imeAction = ImeAction.Send),
                        keyboardActions = KeyboardActions(onSend = { sendText() }),
                    )
                    Spacer(Modifier.width(8.dp))
                    if (textInput.isBlank()) {
                        Surface(
                            onClick = { startVoiceRecording() },
                            shape = CircleShape,
                            color = Brand.PrimaryAccent,
                            modifier = Modifier.size(48.dp),
                        ) {
                            Box(contentAlignment = Alignment.Center) {
                                Icon(Icons.Filled.Mic, contentDescription = "Voice Message", tint = Brand.ButtonContent)
                            }
                        }
                    } else {
                        Surface(
                            onClick = { sendText() },
                            shape = CircleShape,
                            color = Brand.PrimaryAccent,
                            modifier = Modifier.size(48.dp),
                        ) {
                            Box(contentAlignment = Alignment.Center) {
                                Icon(Icons.AutoMirrored.Filled.Send, contentDescription = "Send Message", tint = Brand.ButtonContent)
                            }
                        }
                    }
                }
            }
            Spacer(Modifier.height(8.dp))
        }
    }
}

@OptIn(androidx.compose.foundation.ExperimentalFoundationApi::class)
@Composable
private fun ChatMessageBubble(
    message: ChatMessage,
    isMe: Boolean,
    displayText: String,
    showingOriginal: Boolean,
    isPlaying: Boolean,
    onToggleOriginal: () -> Unit,
    onPlayAudio: () -> Unit,
    onDelete: (forEveryone: Boolean) -> Unit,
) {
    var menu by remember { mutableStateOf(false) }
    val clipboard = androidx.compose.ui.platform.LocalClipboardManager.current
    val bubbleColor = if (isMe) Brand.PrimaryAccent else Brand.CardBg
    val textColor = if (isMe) Brand.ButtonContent else Brand.PrimaryText
    val align = if (isMe) Alignment.End else Alignment.Start

    Column(Modifier.fillMaxWidth(), horizontalAlignment = align) {
        if (!isMe) {
            Text(
                message.senderName,
                style = MaterialTheme.typography.labelSmall,
                color = Brand.HighlightAccent,
                modifier = Modifier.padding(start = 12.dp, bottom = 2.dp),
            )
        }
        Box(
            Modifier.clip(RoundedCornerShape(16.dp))
                .background(bubbleColor)
                .border(if (!isMe) 1.dp else 0.dp, Brand.Borders, RoundedCornerShape(16.dp))
                .combinedClickable(onClick = {}, onLongClick = { menu = true }, onLongClickLabel = "Message options")
                .padding(horizontal = 14.dp, vertical = 10.dp),
        ) {
            DropdownMenu(expanded = menu, onDismissRequest = { menu = false }) {
                if (!message.deleted && displayText.isNotBlank()) DropdownMenuItem(text = { Text("Copy") }, onClick = {
                    menu = false
                    clipboard.setText(androidx.compose.ui.text.AnnotatedString(displayText))
                })
                DropdownMenuItem(text = { Text("Delete for me") }, onClick = { menu = false; onDelete(false) })
                if (isMe && !message.deleted) DropdownMenuItem(text = { Text("Delete for everyone") }, onClick = { menu = false; onDelete(true) })
            }
            Column {
                if (message.deleted) {
                    Text(if (isMe) "You deleted this message" else "This message was deleted",
                        style = MaterialTheme.typography.bodyMedium, color = textColor.copy(alpha = 0.7f),
                        fontStyle = androidx.compose.ui.text.font.FontStyle.Italic)
                } else if (message.audioId != null) {
                    // Voice message bubble
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Surface(
                            onClick = onPlayAudio,
                            shape = CircleShape,
                            color = if (isMe) Brand.HighlightAccent else Brand.PrimaryAccent,
                            modifier = Modifier.size(36.dp),
                        ) {
                            Box(contentAlignment = Alignment.Center) {
                                Icon(
                                    if (isPlaying) Icons.Filled.Stop else Icons.Filled.PlayArrow,
                                    contentDescription = if (isPlaying) "Stop" else "Play",
                                    tint = Brand.ButtonContent,
                                    modifier = Modifier.size(20.dp),
                                )
                            }
                        }
                        Spacer(Modifier.width(10.dp))
                        Column {
                            Text("Voice message", style = MaterialTheme.typography.labelMedium, color = textColor)
                            Text(formatDuration(message.durationMs / 1000), style = MaterialTheme.typography.bodySmall, color = textColor.copy(alpha = 0.8f))
                        }
                    }
                    if (displayText.isNotBlank() && displayText != "[Voice Message]") {
                        Spacer(Modifier.height(6.dp))
                        Text(displayText, style = MaterialTheme.typography.bodyMedium, color = textColor)
                    }
                } else {
                    // Text message bubble
                    Text(displayText, style = MaterialTheme.typography.bodyMedium, color = textColor)
                }

                // If message was translated, provide toggle button
                if (message.isTranslated && !message.deleted) {
                    Spacer(Modifier.height(4.dp))
                    Text(
                        if (showingOriginal) "Show translated" else "View original (${message.sourceLang})",
                        style = MaterialTheme.typography.labelSmall,
                        color = if (isMe) Brand.HighlightAccent else Brand.PrimaryAccent,
                        fontWeight = FontWeight.Bold,
                        modifier = Modifier.clickable { onToggleOriginal() }.padding(top = 2.dp),
                    )
                }

                Spacer(Modifier.height(2.dp))
                val timeStr = SimpleDateFormat("h:mm a", Locale.getDefault()).format(Date((message.createdAt * 1000).toLong()))
                Row(Modifier.align(Alignment.End), verticalAlignment = Alignment.CenterVertically) {
                    Text(
                        timeStr,
                        style = MaterialTheme.typography.labelSmall.copy(fontSize = 10.sp),
                        color = textColor.copy(alpha = 0.65f),
                    )
                    // ticks on my messages: one = sent, two = delivered, two highlighted = read
                    if (isMe && message.status != null && !message.deleted) {
                        Spacer(Modifier.width(4.dp))
                        Icon(
                            if (message.status == "sent") Icons.Filled.Done else Icons.Filled.DoneAll,
                            contentDescription = when (message.status) { "read" -> "Read"; "delivered" -> "Delivered"; else -> "Sent" },
                            tint = if (message.status == "read") Brand.SoftBg else textColor.copy(alpha = 0.6f),
                            modifier = Modifier.size(14.dp),
                        )
                    }
                }
            }
        }
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
        phase = RecPhase.Recording
        elapsed = 0L
        pcm = null
        error = null
        stop.set(false)
        scope.launch {
            try {
                pcm = VoicemailRecorder.record(
                    maxMs = VOICEMAIL_MAX_MS,
                    shouldStop = { stop.get() },
                    onProgress = { ms, lvl -> elapsed = ms; level = lvl },
                )
                phase = if (pcm != null && pcm!!.size >= MIN_RECORDING_BYTES) RecPhase.Recorded else RecPhase.Idle
                if (pcm != null && pcm!!.size < MIN_RECORDING_BYTES) error = "Too short. Hold the button and speak."
            } catch (e: Exception) {
                error = e.message
                phase = RecPhase.Idle
            }
        }
    }

    fun send() {
        val data = pcm ?: return
        val target = recipient ?: return
        phase = RecPhase.Sending
        error = null
        scope.launch {
            try {
                c.api.sendVoicemail(
                    to = target,
                    language = settings.myLanguage,
                    autoDetect = settings.autoDetect,
                    pcm = data,
                )
                onSent()
            } catch (e: ApiException) {
                error = e.message
                phase = RecPhase.Recorded
            }
        }
    }

    ScreenScaffold("Record voicemail", onBack) {
        SectionTitle("To")
        if (people.isNotEmpty()) {
            FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                people.forEach { (id, name) ->
                    FilterChip(
                        selected = pickedId == id,
                        onClick = { pickedId = id; pickedName = name; email = "" },
                        label = { Text(name) },
                    )
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
                    tint = Brand.ButtonContent, modifier = Modifier.size(44.dp))
            }
        }
    }
}
