package ai.mack.sarvagyan.ui.screens

import android.Manifest
import android.content.Context
import android.content.pm.PackageManager
import android.widget.Toast
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.combinedClickable
import androidx.compose.foundation.gestures.awaitEachGesture
import androidx.compose.foundation.gestures.awaitFirstDown
import androidx.compose.material.icons.filled.Done
import androidx.compose.material.icons.filled.DoneAll
import androidx.compose.material.icons.filled.ErrorOutline
import androidx.compose.material.icons.filled.Lock
import androidx.compose.material.icons.filled.Pause
import androidx.compose.material.icons.filled.Schedule
import androidx.compose.material.icons.filled.VolumeUp
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import ai.mack.sarvagyan.data.objOrNull
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
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.safeDrawingPadding
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
import androidx.compose.material.icons.automirrored.filled.Send
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.Check
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.Delete
import androidx.compose.material.icons.filled.Group
import androidx.compose.material.icons.filled.GroupAdd
import androidx.compose.material.icons.filled.Mic
import androidx.compose.material.icons.filled.PersonAdd
import androidx.compose.material.icons.filled.PlayArrow
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material.icons.filled.Search
import androidx.compose.material.icons.filled.Stop
import androidx.compose.material.icons.filled.Translate
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
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.core.content.ContextCompat
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import ai.mack.sarvagyan.call.VOICEMAIL_MAX_MS
import ai.mack.sarvagyan.call.VoicemailPlayer
import ai.mack.sarvagyan.call.VoicemailRecorder
import ai.mack.sarvagyan.container
import ai.mack.sarvagyan.data.ApiException
import ai.mack.sarvagyan.data.ChatMessage
import ai.mack.sarvagyan.data.Conversation
import ai.mack.sarvagyan.data.UserSearchResult
import ai.mack.sarvagyan.data.formatDuration
import ai.mack.sarvagyan.ui.components.AppCard
import ai.mack.sarvagyan.ui.components.Avatar
import ai.mack.sarvagyan.ui.components.EmeraldAnimatedBackground
import ai.mack.sarvagyan.ui.components.EmptyState
import ai.mack.sarvagyan.ui.components.ErrorBanner
import ai.mack.sarvagyan.ui.components.LoadingView
import ai.mack.sarvagyan.ui.components.PrimaryButton
import ai.mack.sarvagyan.ui.components.StatusChip
import ai.mack.sarvagyan.ui.theme.Brand
import ai.mack.sarvagyan.ui.theme.LocalCallColors
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import java.util.concurrent.atomic.AtomicBoolean
import kotlin.math.abs

private const val MIN_RECORDING_BYTES = 16_000 // 0.5 s at 16 kHz
private const val MAX_VOICE_BYTES = 1_920_000 // ~60 s PCM 16 kHz 16-bit

/**
 * Global Chat: Direct 1-to-1 chats and multilingual group chats with WhatsApp-style voice messages.
 */
@Composable
fun GlobalChatScreen(
    initialTab: Int = 0,
    onBack: () -> Unit,
    onOpenConversation: (String) -> Unit,
) {
    val c = LocalContext.current.container
    val scope = rememberCoroutineScope()
    var topTab by remember { mutableIntStateOf(initialTab.coerceIn(0, 1)) }

    var conversations by remember { mutableStateOf<List<Conversation>?>(null) }
    var chatError by remember { mutableStateOf<String?>(null) }
    var showSearchUser by remember { mutableStateOf(false) }
    var showNewGroup by remember { mutableStateOf(false) }

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

    LaunchedEffect(Unit) {
        c.syncLanguage()
        while (true) {
            loadConversations()
            delay(5_000)
        }
    }

    ScreenScaffold("Global Chat", onBack) {
        TabRow(selectedTabIndex = topTab, containerColor = Brand.CardBg) {
            Tab(topTab == 0, { topTab = 0 }, text = { Text("Chats") })
            Tab(topTab == 1, { topTab = 1 }, text = { Text("Groups") })
        }
        Spacer(Modifier.height(14.dp))

        when (topTab) {
            0 -> {
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
            else -> {
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
                Avatar(title, colors.peer, 42.dp, avatar = conversation.peer?.avatar ?: conversation.otherUser?.avatar, useMain = false)
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
                            Avatar(u.displayName, LocalCallColors.current.peer, 36.dp, avatar = u.avatar, useMain = false)
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
                    if (results.isEmpty() && query.isNotBlank() && !searching) {
                        item {
                            Text("No users found matching \"$query\"", style = MaterialTheme.typography.bodyMedium,
                                color = MaterialTheme.colorScheme.onSurfaceVariant, modifier = Modifier.padding(top = 16.dp))
                        }
                    }
                    items(results.filter { r -> selectedMembers.none { it.id == r.id } }) { u ->
                        Row(
                            Modifier.fillMaxWidth().clickable { selectedMembers.add(u) }.padding(vertical = 6.dp),
                            verticalAlignment = Alignment.CenterVertically,
                        ) {
                            Avatar(u.displayName, LocalCallColors.current.peer, 32.dp, avatar = u.avatar, useMain = false)
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

@Composable
private fun AddMemberDialog(
    existingMemberIds: List<String>,
    onDismiss: () -> Unit,
    onAdd: (UserSearchResult) -> Unit,
) {
    val c = LocalContext.current.container
    var query by remember { mutableStateOf("") }
    var results by remember { mutableStateOf<List<UserSearchResult>>(emptyList()) }
    var searching by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf<String?>(null) }

    LaunchedEffect(query) {
        val q = query.trim().removePrefix("@")
        if (q.isEmpty()) {
            results = emptyList()
            return@LaunchedEffect
        }
        delay(300)
        searching = true
        try {
            val res = c.api.searchUsers(q)
            results = res.users.filter { it.id !in existingMemberIds }
            error = null
        } catch (e: Exception) {
            error = (e as? ApiException)?.message ?: e.message
            results = emptyList()
        } finally {
            searching = false
        }
    }

    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("Add Member to Group") },
        text = {
            Column(Modifier.fillMaxWidth().height(320.dp)) {
                OutlinedTextField(
                    value = query,
                    onValueChange = { query = it },
                    label = { Text("Search by @username or name") },
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
                            Modifier.fillMaxWidth().clickable { onAdd(u) }.padding(vertical = 8.dp),
                            verticalAlignment = Alignment.CenterVertically,
                        ) {
                            Avatar(u.displayName, LocalCallColors.current.peer, 36.dp, avatar = u.avatar, useMain = false)
                            Spacer(Modifier.width(10.dp))
                            Column(Modifier.weight(1f)) {
                                Text(u.displayName, style = MaterialTheme.typography.bodyLarge, fontWeight = FontWeight.Medium)
                                u.username?.let {
                                    Text("@$it", style = MaterialTheme.typography.bodySmall, color = Brand.HighlightAccent)
                                }
                            }
                            TextButton(onClick = { onAdd(u) }) {
                                Text("Add")
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

/**
 * Dedicated conversation screen for direct and group multilingual chat.
 * Includes automatic translation toggle and voice messaging with glitch-free playback.
 */
@Composable
fun ChatConversationScreen(
    conversationId: String,
    isVoicemail: Boolean = false,
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
    var showAddMember by remember { mutableStateOf(false) }

    // Toggle map for viewing original text vs translated text
    val showOriginalMap = remember { mutableStateMapOf<String, Boolean>() }

    // Audio playback state (keyed as "orig:<msgId>" or "trans:<msgId>")
    var playingKey by remember { mutableStateOf<String?>(null) }
    var playProgress by remember { mutableFloatStateOf(0f) }
    var playJob by remember { mutableStateOf<Job?>(null) }
    var activePlayer by remember { mutableStateOf<VoicemailPlayer?>(null) }

    // WhatsApp-style voice recording state
    var isRecording by remember { mutableStateOf(false) }
    var isLocked by remember { mutableStateOf(false) }
    var uploadingVoice by remember { mutableStateOf(false) }
    var failedVoicePcm by remember { mutableStateOf<ByteArray?>(null) }
    var recordElapsed by remember { mutableLongStateOf(0L) }
    var recordLevel by remember { mutableFloatStateOf(0f) }
    var dragCancelProgress by remember { mutableFloatStateOf(0f) }
    var dragLockProgress by remember { mutableFloatStateOf(0f) }
    val recordStop = remember { AtomicBoolean(false) }
    val recordCancelled = remember { AtomicBoolean(false) }
    var micGranted by remember {
        mutableStateOf(
            ContextCompat.checkSelfPermission(context, Manifest.permission.RECORD_AUDIO) == PackageManager.PERMISSION_GRANTED
        )
    }
    val permission = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { ok ->
        micGranted = ok
        if (!ok) error = "Microphone permission is required to record voice messages."
    }

    val listState = rememberLazyListState()

    val failedVoicePcms = remember { mutableStateMapOf<String, ByteArray>() }

    suspend fun loadMessages() {
        try {
            val res = c.api.chatMessages(conversationId)
            val failedLocal = messages.filter { it.id.startsWith("local-") && it.status == "failed" }
            val sendingLocal = messages.filter { it.id.startsWith("local-") && it.status == "sending" }
            messages = res.messages + sendingLocal + failedLocal
            error = null
        } catch (e: ApiException) {
            error = e.message
        }
    }

    LaunchedEffect(conversationId) {
        c.appSocket.sendChatFocus(conversationId)
        runCatching {
            conversation = c.api.conversation(conversationId).conversation
        }
        while (true) {
            loadMessages()
            delay(15_000)
        }
    }
    LaunchedEffect(conversationId) {
        c.appSocket.events.collect { ev ->
            if (ev.str("conversation_id") != conversationId) return@collect
            when (ev.str("type")) {
                "message" -> {
                    val mObj = ev.objOrNull("message")
                    val incoming = mObj?.let { runCatching { c.json.decodeFromJsonElement(ChatMessage.serializer(), it) }.getOrNull() }
                    if (incoming != null) {
                        if (incoming.senderId == me?.id) {
                            if (messages.none { it.id == incoming.id }) {
                                messages = (messages + incoming.copy(status = incoming.status ?: "sent")).sortedBy { it.createdAt }
                            }
                        } else {
                            if (messages.none { it.id == incoming.id }) {
                                messages = (messages + incoming).sortedBy { it.createdAt }
                            }
                            scope.launch { loadMessages() }
                        }
                    } else {
                        loadMessages()
                    }
                }
                "message_updated" -> {
                    val mObj = ev.objOrNull("message")
                    val upd = mObj?.let { runCatching { c.json.decodeFromJsonElement(ChatMessage.serializer(), it) }.getOrNull() }
                    if (upd != null) {
                        messages = messages.map { cur ->
                            if (cur.id == upd.id) cur.copy(
                                originalText = upd.originalText,
                                translatedText = upd.translatedText,
                                isTranslated = upd.isTranslated,
                                sourceLang = upd.sourceLang,
                            ) else cur
                        }
                    }
                }
                "chat_delivered" -> {
                    messages = messages.map { cur ->
                        if (cur.senderId == me?.id && cur.status == "sent") cur.copy(status = "delivered") else cur
                    }
                }
                "chat_read" -> {
                    messages = messages.map { cur ->
                        if (cur.senderId == me?.id && (cur.status == "sent" || cur.status == "delivered")) cur.copy(status = "read") else cur
                    }
                }
                "message_deleted" -> {
                    val mid = ev.str("message_id")
                    if (mid != null) {
                        messages = messages.map { cur -> if (cur.id == mid) cur.copy(deleted = true, audioId = null) else cur }
                    }
                }
            }
        }
    }

    LaunchedEffect(messages.size) {
        if (messages.isNotEmpty()) {
            listState.animateScrollToItem(messages.size - 1)
        }
    }

    DisposableEffect(Unit) {
        onDispose {
            c.appSocket.sendChatFocus(null)
            playJob?.cancel()
            activePlayer?.release()
            activePlayer = null
            recordCancelled.set(true)
            recordStop.set(true)
        }
    }

    fun stopPlayback() {
        playJob?.cancel()
        activePlayer?.release()
        activePlayer = null
        playingKey = null
        playProgress = 0f
    }

    fun playVoice(msg: ChatMessage, translated: Boolean) {
        val targetKey = (if (translated) "trans:" else "orig:") + msg.id
        val wasPlayingThis = (playingKey == targetKey)
        stopPlayback()
        if (wasPlayingThis) return

        playingKey = targetKey
        playProgress = 0f
        playJob = scope.launch {
            val player = VoicemailPlayer()
            activePlayer = player
            val progressJob = launch {
                val estMs = maxOf(1000L, msg.durationMs)
                val t0 = System.currentTimeMillis()
                while (playingKey == targetKey) {
                    playProgress = ((System.currentTimeMillis() - t0).toFloat() / estMs).coerceIn(0.05f, 0.96f)
                    delay(80)
                }
            }
            try {
                if (translated) {
                    c.api.streamChatTranslatedAudio(msg.id) { buf, n -> player.write(buf, n) }
                } else {
                    val aid = msg.audioId ?: return@launch
                    c.api.streamChatAudio(aid) { buf, n -> player.write(buf, n) }
                }
                player.drain()
                playProgress = 1f
            } catch (e: Exception) {
                if (e !is CancellationException) {
                    error = (e as? ApiException)?.message ?: e.message ?: "Playback failed."
                }
            } finally {
                progressJob.cancel()
                player.release()
                if (activePlayer === player) activePlayer = null
                if (playingKey == targetKey) {
                    playingKey = null
                    playProgress = 0f
                }
            }
        }
    }

    fun sendText(retryMessage: ChatMessage? = null) {
        val text = retryMessage?.originalText ?: textInput.trim()
        if (text.isEmpty()) return
        val localId = retryMessage?.id ?: "local-${java.util.UUID.randomUUID()}"
        val lang = retryMessage?.sourceLang ?: c.effectiveMyLanguage()
        if (retryMessage == null) {
            textInput = ""
            val optimistic = ChatMessage(
                id = localId,
                conversationId = conversationId,
                senderId = me?.id ?: "",
                senderName = me?.displayName ?: "You",
                sourceLang = lang,
                originalText = text,
                translatedText = text,
                createdAt = System.currentTimeMillis() / 1000.0,
                status = "sending",
            )
            messages = messages + optimistic
        } else {
            messages = messages.map { if (it.id == localId) it.copy(status = "sending") else it }
        }
        scope.launch {
            try {
                val res = c.api.sendChatMessage(conversationId, text, language = lang)
                val confirmed = res.message.copy(status = res.message.status ?: "sent")
                messages = messages.filterNot { it.id == confirmed.id }.map { if (it.id == localId) confirmed else it }
                error = null
            } catch (e: ApiException) {
                messages = messages.map { if (it.id == localId) it.copy(status = "failed") else it }
                error = e.message
            }
        }
    }

    suspend fun uploadRecordedVoice(pcm: ByteArray, retryLocalId: String? = null) {
        if (pcm.size > MAX_VOICE_BYTES) {
            error = "Voice message exceeds the 60-second size limit."
            return
        }
        val localId = retryLocalId ?: "local-voice-${java.util.UUID.randomUUID()}"
        val lang = c.effectiveMyLanguage()
        val tag = if (isVoicemail) "voicemail" else null
        val durationMs = (pcm.size / 32L).coerceAtLeast(500L)
        if (retryLocalId == null) {
            val optimistic = ChatMessage(
                id = localId,
                conversationId = conversationId,
                senderId = me?.id ?: "",
                senderName = me?.displayName ?: "You",
                sourceLang = lang,
                originalText = "[Voice Message]",
                translatedText = "[Voice Message]",
                audioId = "pending",
                durationMs = durationMs,
                createdAt = System.currentTimeMillis() / 1000.0,
                status = "sending",
                tag = tag,
            )
            messages = messages + optimistic
        } else {
            messages = messages.map { if (it.id == localId) it.copy(status = "sending") else it }
        }
        uploadingVoice = true
        error = null
        try {
            val res = c.api.sendChatVoice(conversationId, language = lang, pcm = pcm, tag = tag)
            val confirmed = res.message.copy(status = res.message.status ?: "sent")
            failedVoicePcm = null
            failedVoicePcms.remove(localId)
            messages = messages.filterNot { it.id == confirmed.id }.map { if (it.id == localId) confirmed else it }
        } catch (e: Exception) {
            if (e is CancellationException) throw e
            failedVoicePcm = pcm
            failedVoicePcms[localId] = pcm
            messages = messages.map { if (it.id == localId) it.copy(status = "failed") else it }
            error = (e as? ApiException)?.message ?: "Voice message upload failed. Tap Retry."
        } finally {
            uploadingVoice = false
        }
    }

    fun startWhatsAppRecording() {
        if (isRecording || uploadingVoice) return
        isRecording = true
        isLocked = false
        recordElapsed = 0L
        recordLevel = 0f
        dragCancelProgress = 0f
        dragLockProgress = 0f
        recordStop.set(false)
        recordCancelled.set(false)
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
                val cancelled = recordCancelled.get()
                isRecording = false
                isLocked = false
                if (!cancelled) {
                    if (pcm.size < MIN_RECORDING_BYTES) {
                        Toast.makeText(context, "Hold the mic button to record a voice message.", Toast.LENGTH_SHORT).show()
                    } else {
                        uploadRecordedVoice(pcm)
                    }
                }
            } catch (e: Exception) {
                isRecording = false
                isLocked = false
                if (e !is CancellationException) {
                    error = (e as? ApiException)?.message ?: e.message ?: "Recording failed."
                }
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
            Modifier.fillMaxSize().safeDrawingPadding().imePadding().padding(horizontal = 16.dp, vertical = 8.dp),
        ) {
            // Header
            Row(
                Modifier.fillMaxWidth().padding(vertical = 4.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                IconButton(onClick = onBack) {
                    Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "Back", tint = Brand.HighlightAccent)
                }
                if (conversation?.isGroup != true) {
                    Avatar(
                        name = title,
                        color = LocalCallColors.current.peer,
                        size = 38.dp,
                        avatar = conversation?.peer?.avatar ?: conversation?.otherUser?.avatar,
                        useMain = false,
                    )
                    Spacer(Modifier.width(10.dp))
                } else {
                    Spacer(Modifier.width(4.dp))
                }
                Column(Modifier.weight(1f)) {
                    Text(title, style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.SemiBold, maxLines = 1, overflow = TextOverflow.Ellipsis)
                    if (subtitle.isNotBlank()) {
                        Text(subtitle, style = MaterialTheme.typography.bodySmall, color = Brand.HighlightAccent)
                    }
                }
                if (conversation?.isGroup == true) {
                    IconButton(onClick = { showAddMember = true }) {
                        Icon(Icons.Filled.PersonAdd, contentDescription = "Add Member", tint = Brand.HighlightAccent)
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
                items(messages, key = { it.id }) { msg ->
                    val isMe = msg.senderId == me?.id
                    val isOrig = showOriginalMap[msg.id] == true
                    val displayText = if (isOrig) msg.originalText else (msg.translatedText ?: msg.originalText)
                    val origPlaying = playingKey == "orig:${msg.id}"
                    val transPlaying = playingKey == "trans:${msg.id}"

                    ChatMessageBubble(
                        message = msg,
                        isMe = isMe,
                        displayText = displayText,
                        showingOriginal = isOrig,
                        isPlayingOrig = origPlaying,
                        isPlayingTrans = transPlaying,
                        playProgress = if (origPlaying || transPlaying) playProgress else 0f,
                        onToggleOriginal = { showOriginalMap[msg.id] = !isOrig },
                        onPlayOriginal = { if (msg.audioId != "pending") playVoice(msg, translated = false) },
                        onPlayTranslated = { if (msg.audioId != "pending") playVoice(msg, translated = true) },
                        onRetry = {
                            if (msg.audioId != null) {
                                val pcm = failedVoicePcms[msg.id]
                                if (pcm != null) scope.launch { uploadRecordedVoice(pcm, retryLocalId = msg.id) }
                            } else {
                                sendText(retryMessage = msg)
                            }
                        },
                        onDelete = { everyone ->
                            scope.launch {
                                try { c.api.deleteChatMessage(msg.id, everyone); loadMessages() } catch (e: ApiException) { error = e.message }
                            }
                        },
                    )
                }
            }

            // Failed voice upload retry banner
            failedVoicePcm?.let { pendingPcm ->
                Spacer(Modifier.height(6.dp))
                Row(
                    Modifier
                        .fillMaxWidth()
                        .background(Brand.CardBg, RoundedCornerShape(14.dp))
                        .border(1.dp, Brand.Danger, RoundedCornerShape(14.dp))
                        .padding(horizontal = 12.dp, vertical = 8.dp),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    Text(
                        "Voice message (${formatDuration(maxOf(1L, pendingPcm.size / 32_000L))}) failed to upload",
                        style = MaterialTheme.typography.bodySmall,
                        modifier = Modifier.weight(1f),
                    )
                    TextButton(onClick = { failedVoicePcm = null; error = null }, enabled = !uploadingVoice) {
                        Text("Discard", color = MaterialTheme.colorScheme.error)
                    }
                    TextButton(onClick = { scope.launch { uploadRecordedVoice(pendingPcm) } }, enabled = !uploadingVoice) {
                        Text("Retry")
                    }
                }
            }

            Spacer(Modifier.height(8.dp))

            // Bottom Input Bar
            if (isRecording && isLocked) {
                // Hands-free locked recording bar
                Row(
                    Modifier
                        .fillMaxWidth()
                        .navigationBarsPadding()
                        .background(Brand.CardBg, RoundedCornerShape(24.dp))
                        .border(1.dp, Brand.Borders, RoundedCornerShape(24.dp))
                        .padding(horizontal = 12.dp, vertical = 6.dp),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    Box(Modifier.size(12.dp).clip(CircleShape).background(Brand.Danger))
                    Spacer(Modifier.width(8.dp))
                    Text(
                        formatDuration(recordElapsed / 1000),
                        style = MaterialTheme.typography.titleMedium,
                        color = Brand.Danger,
                    )
                    Spacer(Modifier.width(8.dp))
                    Text(
                        "Recording (locked)",
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                        modifier = Modifier.weight(1f),
                    )
                    IconButton(onClick = {
                        recordCancelled.set(true)
                        recordStop.set(true)
                    }) {
                        Icon(Icons.Filled.Delete, contentDescription = "Cancel recording", tint = MaterialTheme.colorScheme.error)
                    }
                    Surface(
                        onClick = { recordStop.set(true) },
                        shape = CircleShape,
                        color = Brand.PrimaryAccent,
                        modifier = Modifier.size(44.dp),
                    ) {
                        Box(contentAlignment = Alignment.Center) {
                            Icon(Icons.AutoMirrored.Filled.Send, contentDescription = "Send voice message", tint = Brand.ButtonContent)
                        }
                    }
                }
            } else {
                Row(
                    Modifier.fillMaxWidth().navigationBarsPadding(),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    if (isRecording) {
                        // Slide-to-cancel / slide-up-to-lock active status pill
                        Row(
                            Modifier
                                .weight(1f)
                                .background(Brand.CardBg, RoundedCornerShape(24.dp))
                                .border(1.dp, Brand.Borders, RoundedCornerShape(24.dp))
                                .padding(horizontal = 14.dp, vertical = 12.dp),
                            verticalAlignment = Alignment.CenterVertically,
                        ) {
                            Box(Modifier.size((10 + 6 * recordLevel).dp).clip(CircleShape).background(Brand.Danger))
                            Spacer(Modifier.width(8.dp))
                            Text(
                                formatDuration(recordElapsed / 1000),
                                style = MaterialTheme.typography.titleSmall,
                                color = Brand.Danger,
                            )
                            Spacer(Modifier.width(12.dp))
                            Text(
                                if (dragCancelProgress > 0.6f) "Release to cancel" else "← Slide to cancel",
                                style = MaterialTheme.typography.bodySmall,
                                color = if (dragCancelProgress > 0.4f) MaterialTheme.colorScheme.error else MaterialTheme.colorScheme.onSurfaceVariant,
                                modifier = Modifier.weight(1f),
                            )
                            Icon(
                                Icons.Filled.Lock,
                                contentDescription = "Slide up to lock",
                                tint = if (dragLockProgress > 0.5f) Brand.HighlightAccent else MaterialTheme.colorScheme.onSurfaceVariant,
                                modifier = Modifier.size(18.dp),
                            )
                        }
                    } else {
                        OutlinedTextField(
                            value = textInput,
                            onValueChange = { textInput = it },
                            placeholder = { Text(if (uploadingVoice) "Sending voice message…" else "Message in your language…") },
                            enabled = !uploadingVoice,
                            modifier = Modifier.weight(1f),
                            shape = RoundedCornerShape(24.dp),
                            singleLine = false,
                            maxLines = 4,
                            keyboardOptions = KeyboardOptions(imeAction = ImeAction.Send),
                            keyboardActions = KeyboardActions(onSend = { sendText() }),
                        )
                    }
                    Spacer(Modifier.width(8.dp))
                    if (textInput.isBlank() || isRecording) {
                        Surface(
                            shape = CircleShape,
                            color = if (isRecording) Brand.Danger else Brand.PrimaryAccent,
                            modifier = Modifier
                                .size(if (isRecording) 56.dp else 48.dp)
                                .pointerInput(micGranted, uploadingVoice) {
                                    awaitEachGesture {
                                        val down = awaitFirstDown(requireUnconsumed = false)
                                        if (uploadingVoice) return@awaitEachGesture
                                        if (!micGranted) {
                                            permission.launch(Manifest.permission.RECORD_AUDIO)
                                            return@awaitEachGesture
                                        }
                                        startWhatsAppRecording()
                                        var totalDx = 0f
                                        var totalDy = 0f
                                        while (true) {
                                            val event = awaitPointerEvent()
                                            val change = event.changes.firstOrNull { it.id == down.id } ?: break
                                            if (!change.pressed) break
                                            totalDx += change.position.x - change.previousPosition.x
                                            totalDy += change.position.y - change.previousPosition.y
                                            dragCancelProgress = (-totalDx / 180f).coerceIn(0f, 1f)
                                            dragLockProgress = (-totalDy / 140f).coerceIn(0f, 1f)
                                            if (totalDx < -180f) {
                                                recordCancelled.set(true)
                                                recordStop.set(true)
                                                break
                                            }
                                            if (totalDy < -140f && abs(totalDx) < 90f) {
                                                isLocked = true
                                                break
                                            }
                                            change.consume()
                                        }
                                        // On release (if not locked and not cancelled), stop & send!
                                        if (!isLocked && !recordCancelled.get()) {
                                            recordStop.set(true)
                                        }
                                    }
                                },
                        ) {
                            Box(contentAlignment = Alignment.Center) {
                                Icon(Icons.Filled.Mic, contentDescription = "Hold to record voice message", tint = Brand.ButtonContent)
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
            Spacer(Modifier.height(4.dp))
        }

        if (showAddMember) {
            val existing = conversation?.members?.map { it.id }.orEmpty()
            AddMemberDialog(
                existingMemberIds = existing,
                onDismiss = { showAddMember = false },
                onAdd = { user ->
                    showAddMember = false
                    scope.launch {
                        try {
                            c.api.addConversationMember(conversationId, user.id)
                            conversation = c.api.conversation(conversationId).conversation
                            loadMessages()
                        } catch (e: ApiException) {
                            error = e.message
                        }
                    }
                }
            )
        }
    }
}

private val WAVEFORM_BARS = floatArrayOf(
    0.30f, 0.55f, 0.85f, 0.45f, 0.95f, 0.65f, 0.40f, 0.80f, 0.90f, 0.50f,
    0.35f, 0.75f, 0.95f, 0.60f, 0.45f, 0.85f, 0.55f, 0.70f, 0.40f, 0.30f,
)

@OptIn(androidx.compose.foundation.ExperimentalFoundationApi::class)
@Composable
private fun ChatMessageBubble(
    message: ChatMessage,
    isMe: Boolean,
    displayText: String,
    showingOriginal: Boolean,
    isPlayingOrig: Boolean,
    isPlayingTrans: Boolean,
    playProgress: Float,
    onToggleOriginal: () -> Unit,
    onPlayOriginal: () -> Unit,
    onPlayTranslated: () -> Unit,
    onRetry: () -> Unit = {},
    onDelete: (forEveryone: Boolean) -> Unit,
) {
    var menu by remember { mutableStateOf(false) }
    val clipboard = androidx.compose.ui.platform.LocalClipboardManager.current
    val bubbleColor = if (isMe) Brand.PrimaryAccent else Brand.CardBg
    val textColor = if (isMe) Brand.ButtonContent else Brand.PrimaryText
    val align = if (isMe) Alignment.End else Alignment.Start
    val isPlayingAny = isPlayingOrig || isPlayingTrans

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
                .combinedClickable(
                    onClick = { if (isMe && message.status == "failed") onRetry() },
                    onLongClick = { menu = true },
                    onLongClickLabel = "Message options",
                )
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
                    if (message.tag == "voicemail") {
                        Text(
                            "Voicemail",
                            style = MaterialTheme.typography.labelSmall,
                            color = if (isMe) Brand.HighlightAccent else Brand.PrimaryAccent,
                            fontWeight = FontWeight.Bold,
                            modifier = Modifier.padding(bottom = 4.dp),
                        )
                    }
                    // WhatsApp-style voice message bubble with Play/Pause + Waveform progress + Duration
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Surface(
                            onClick = onPlayOriginal,
                            shape = CircleShape,
                            color = if (isMe) Brand.HighlightAccent else Brand.PrimaryAccent,
                            modifier = Modifier.size(38.dp),
                        ) {
                            Box(contentAlignment = Alignment.Center) {
                                Icon(
                                    if (isPlayingOrig) Icons.Filled.Pause else Icons.Filled.PlayArrow,
                                    contentDescription = if (isPlayingOrig) "Pause" else "Play",
                                    tint = Brand.ButtonContent,
                                    modifier = Modifier.size(22.dp),
                                )
                            }
                        }
                        Spacer(Modifier.width(10.dp))
                        Column(Modifier.width(175.dp)) {
                            Row(
                                Modifier.fillMaxWidth().height(24.dp),
                                horizontalArrangement = Arrangement.spacedBy(3.dp),
                                verticalAlignment = Alignment.CenterVertically,
                            ) {
                                WAVEFORM_BARS.forEachIndexed { idx, amp ->
                                    val barFrac = (idx + 1).toFloat() / WAVEFORM_BARS.size
                                    val lit = isPlayingAny && barFrac <= playProgress
                                    Box(
                                        Modifier
                                            .weight(1f)
                                            .height((6 + 18 * amp).dp)
                                            .clip(RoundedCornerShape(2.dp))
                                            .background(
                                                if (lit) (if (isMe) Brand.SoftBg else Brand.HighlightAccent)
                                                else textColor.copy(alpha = 0.35f)
                                            )
                                    )
                                }
                            }
                            Spacer(Modifier.height(2.dp))
                            Text(
                                formatDuration(maxOf(1L, message.durationMs / 1000)),
                                style = MaterialTheme.typography.labelSmall,
                                color = textColor.copy(alpha = 0.8f),
                            )
                        }
                    }

                    // Transcript & Translation + Play translated speech option
                    if (displayText.isNotBlank() && displayText != "[Voice Message]") {
                        Spacer(Modifier.height(6.dp))
                        Text(displayText, style = MaterialTheme.typography.bodyMedium, color = textColor)
                        if (message.isTranslated) {
                            Spacer(Modifier.height(6.dp))
                            Row(
                                Modifier
                                    .clip(RoundedCornerShape(10.dp))
                                    .background(textColor.copy(alpha = 0.12f))
                                    .clickable { onPlayTranslated() }
                                    .padding(horizontal = 8.dp, vertical = 4.dp),
                                verticalAlignment = Alignment.CenterVertically,
                            ) {
                                Icon(
                                    if (isPlayingTrans) Icons.Filled.Stop else Icons.Filled.VolumeUp,
                                    contentDescription = if (isPlayingTrans) "Stop translated speech" else "Play translated speech",
                                    tint = if (isMe) Brand.HighlightAccent else Brand.PrimaryAccent,
                                    modifier = Modifier.size(16.dp),
                                )
                                Spacer(Modifier.width(4.dp))
                                Text(
                                    if (isPlayingTrans) "Playing translation…" else "Play translated voice",
                                    style = MaterialTheme.typography.labelSmall,
                                    fontWeight = FontWeight.SemiBold,
                                    color = if (isMe) Brand.HighlightAccent else Brand.PrimaryAccent,
                                )
                            }
                        }
                    }
                } else {
                    Text(displayText, style = MaterialTheme.typography.bodyMedium, color = textColor)
                }

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
                    if (isMe && message.status != null && !message.deleted) {
                        Spacer(Modifier.width(4.dp))
                        when (message.status) {
                            "sending" -> Icon(
                                Icons.Filled.Schedule,
                                contentDescription = "Sending",
                                tint = textColor.copy(alpha = 0.6f),
                                modifier = Modifier.size(13.dp),
                            )
                            "failed" -> Row(
                                verticalAlignment = Alignment.CenterVertically,
                                modifier = Modifier.clickable { onRetry() },
                            ) {
                                Icon(
                                    Icons.Filled.ErrorOutline,
                                    contentDescription = "Failed",
                                    tint = Brand.Danger,
                                    modifier = Modifier.size(13.dp),
                                )
                                Spacer(Modifier.width(2.dp))
                                Text(
                                    "Failed, tap to retry",
                                    style = MaterialTheme.typography.labelSmall.copy(fontSize = 10.sp),
                                    color = Brand.Danger,
                                )
                            }
                            else -> Icon(
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
}
