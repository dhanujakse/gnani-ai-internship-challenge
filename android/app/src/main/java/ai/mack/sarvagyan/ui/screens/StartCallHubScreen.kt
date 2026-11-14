package ai.mack.sarvagyan.ui.screens

import android.Manifest
import android.content.pm.PackageManager
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.Call
import androidx.compose.material.icons.filled.Check
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.GroupAdd
import androidx.compose.material.icons.filled.MeetingRoom
import androidx.compose.material.icons.filled.People
import androidx.compose.material.icons.filled.Person
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material.icons.filled.Search
import androidx.compose.material.icons.filled.SwapHoriz
import androidx.compose.material.icons.filled.Voicemail
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Surface
import androidx.compose.material3.Tab
import androidx.compose.material3.TabRow
import androidx.compose.material3.TabRowDefaults
import androidx.compose.material3.TabRowDefaults.tabIndicatorOffset
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.input.KeyboardCapitalization
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.core.content.ContextCompat
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import ai.mack.sarvagyan.container
import ai.mack.sarvagyan.data.ApiException
import ai.mack.sarvagyan.data.ContactUser
import ai.mack.sarvagyan.data.MatchedContact
import ai.mack.sarvagyan.data.UserSearchResult
import ai.mack.sarvagyan.data.normaliseCode
import ai.mack.sarvagyan.ui.components.AppCard
import ai.mack.sarvagyan.ui.components.Avatar
import ai.mack.sarvagyan.ui.components.EmeraldAnimatedBackground
import ai.mack.sarvagyan.ui.components.EmptyState
import ai.mack.sarvagyan.ui.components.ErrorBanner
import ai.mack.sarvagyan.ui.components.LanguagePill
import ai.mack.sarvagyan.ui.components.PrimaryButton
import ai.mack.sarvagyan.ui.components.SecondaryButton
import ai.mack.sarvagyan.ui.components.SectionTitle
import ai.mack.sarvagyan.ui.components.StatusChip
import ai.mack.sarvagyan.ui.theme.Brand
import ai.mack.sarvagyan.ui.theme.LocalCallColors
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch

/**
 * Unified Call Hub: Consolidates direct member calls, contact discovery, and room creation/joining
 * into one seamless, structured workflow.
 */
@Composable
fun StartCallHubScreen(
    onBack: () -> Unit,
    onCallStarted: () -> Unit,
    onCreateRoom: () -> Unit,
    onJoinRoom: (String) -> Unit,
    onVoicemail: (String, String) -> Unit,
) {
    val context = LocalContext.current
    val c = context.container
    val scope = rememberCoroutineScope()
    val placeCall = rememberPlaceCall(onCallStarted)

    // 0: Direct Call / Contact, 1: Create or Join Room
    var selectedOption by remember { mutableIntStateOf(0) }

    // Direct Call state
    var searchQuery by remember { mutableStateOf("") }
    var searching by remember { mutableStateOf(false) }
    var searchAttempted by remember { mutableStateOf(false) }
    var usernameResults by remember { mutableStateOf<List<UserSearchResult>>(emptyList()) }
    var phoneResult by remember { mutableStateOf<MatchedContact?>(null) }
    var contacts by remember { mutableStateOf<List<ContactUser>?>(null) }
    var matchedPhoneContacts by remember { mutableStateOf<List<MatchedContact>>(emptyList()) }
    var syncingPhone by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf<String?>(null) }

    // Room join state
    var roomCode by remember { mutableStateOf("") }

    val hasContactPermission = remember {
        ContextCompat.checkSelfPermission(context, Manifest.permission.READ_CONTACTS) == PackageManager.PERMISSION_GRANTED
    }
    var permissionGranted by remember { mutableStateOf(hasContactPermission) }

    fun syncContacts() {
        if (!permissionGranted) return
        syncingPhone = true
        scope.launch {
            try {
                val (_, matches) = syncDeviceContactsWithServer(context, c.api)
                matchedPhoneContacts = matches
            } catch (e: Exception) {
                // Keep existing contacts on failure
            } finally {
                syncingPhone = false
            }
        }
    }

    val contactPermissionLauncher = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { granted ->
        permissionGranted = granted
        if (granted) syncContacts()
    }

    // Load initial contacts and sync if permission already granted
    LaunchedEffect(Unit) {
        try {
            contacts = c.api.contacts().contacts
        } catch (e: ApiException) {
            contacts = emptyList()
        }
        if (permissionGranted) syncContacts()
    }

    // Debounced search for username or phone number
    LaunchedEffect(searchQuery) {
        val query = searchQuery.trim()
        if (query.isEmpty()) {
            usernameResults = emptyList()
            phoneResult = null
            searching = false
            searchAttempted = false
            return@LaunchedEffect
        }

        searching = true
        searchAttempted = false
        delay(300)

        // Determine if searching by phone or username
        val isPhone = query.startsWith("+") || query.all { it.isDigit() || it == '-' || it == ' ' }
        if (isPhone) {
            val norm = normalizePhoneE164(query, "+91")
            if (norm != null) {
                try {
                    val hash = sha256Hex(norm)
                    val res = c.api.matchPhones(listOf(hash))
                    phoneResult = res.matches.firstOrNull()
                    usernameResults = emptyList()
                } catch (_: Exception) {
                    phoneResult = null
                }
            } else {
                phoneResult = null
            }
        } else {
            val cleanUsername = query.removePrefix("@").trim()
            if (cleanUsername.isNotEmpty()) {
                try {
                    usernameResults = c.api.searchUsers(cleanUsername).users.take(10)
                    phoneResult = null
                } catch (_: Exception) {
                    usernameResults = emptyList()
                }
            }
        }
        searching = false
        searchAttempted = true
    }

    EmeraldAnimatedBackground {
        Column(Modifier.fillMaxSize()) {
            // Screen Header
            Row(
                Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 4.dp, vertical = 6.dp),
                verticalAlignment = Alignment.CenterVertically
            ) {
                IconButton(onClick = onBack) {
                    Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "Back", tint = Brand.HighlightAccent)
                }
                Column(Modifier.weight(1f)) {
                    Text("Start a Call", style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold, color = Brand.PrimaryText)
                    Text("Choose how you want to connect", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
            }

            // Primary 2-Option Selector: Option A (Direct Call / Contact) vs Option B (Create or Join Room)
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 20.dp, vertical = 8.dp)
                    .clip(RoundedCornerShape(14.dp))
                    .background(MaterialTheme.colorScheme.surfaceVariant)
                    .padding(4.dp),
                horizontalArrangement = Arrangement.spacedBy(4.dp),
            ) {
                listOf(
                    0 to "Direct Call / Contact",
                    1 to "Create or Join Room"
                ).forEach { (idx, label) ->
                    val selected = selectedOption == idx
                    Column(
                        modifier = Modifier
                            .weight(1f)
                            .clip(RoundedCornerShape(10.dp))
                            .background(if (selected) MaterialTheme.colorScheme.primary else Color.Transparent)
                            .clickable { selectedOption = idx }
                            .padding(vertical = 12.dp, horizontal = 8.dp),
                        horizontalAlignment = Alignment.CenterHorizontally,
                    ) {
                        Text(
                            label,
                            color = if (selected) MaterialTheme.colorScheme.onPrimary else MaterialTheme.colorScheme.onSurfaceVariant,
                            fontWeight = if (selected) FontWeight.Bold else FontWeight.Medium,
                            style = MaterialTheme.typography.labelLarge,
                            textAlign = TextAlign.Center,
                        )
                    }
                }
            }

            Spacer(Modifier.height(8.dp))

            if (selectedOption == 0) {
                // ---------------------------------------------------------------------------------
                // OPTION A: DIRECT CALL / CONTACT DISCOVERY
                // ---------------------------------------------------------------------------------
                LazyColumn(
                    modifier = Modifier.fillMaxSize(),
                    contentPadding = PaddingValues(horizontal = 20.dp, vertical = 8.dp),
                ) {
                    // Search Bar
                    item(key = "search_bar") {
                        OutlinedTextField(
                            value = searchQuery,
                            onValueChange = { searchQuery = it },
                            label = { Text("Search by @username or phone number") },
                            placeholder = { Text("e.g. @priya or +91 9876543210") },
                            leadingIcon = {
                                Icon(Icons.Filled.Search, contentDescription = null, tint = Brand.HighlightAccent)
                            },
                            trailingIcon = {
                                if (searchQuery.isNotEmpty()) {
                                    IconButton(onClick = { searchQuery = "" }) {
                                        Icon(Icons.Filled.Close, contentDescription = "Clear search")
                                    }
                                }
                            },
                            singleLine = true,
                            modifier = Modifier.fillMaxWidth(),
                            keyboardOptions = KeyboardOptions(imeAction = ImeAction.Search),
                        )
                        Spacer(Modifier.height(12.dp))
                    }

                    // Live Search Results
                    if (searchQuery.isNotBlank()) {
                        item(key = "search_status") {
                            SectionTitle("Search Results")
                        }

                        if (searching) {
                            item(key = "searching_indicator") {
                                Row(
                                    Modifier.fillMaxWidth().padding(16.dp),
                                    horizontalArrangement = Arrangement.Center,
                                    verticalAlignment = Alignment.CenterVertically
                                ) {
                                    CircularProgressIndicator(Modifier.size(20.dp), strokeWidth = 2.dp, color = MaterialTheme.colorScheme.primary)
                                    Spacer(Modifier.width(10.dp))
                                    Text("Searching Sarvagyan members…", style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
                                }
                            }
                        } else if (phoneResult != null) {
                            val res = phoneResult!!
                            item(key = "phone_result_${res.id}") {
                                MemberCallRow(
                                    name = res.name,
                                    username = res.username,
                                    avatar = res.avatar,
                                    language = c.language(res.language)?.name ?: res.language,
                                    isMember = true,
                                    onCall = { placeCall(res.id, res.name) },
                                    onVoicemail = { onVoicemail(res.id, res.name) },
                                )
                            }
                        } else if (usernameResults.isNotEmpty()) {
                            items(usernameResults, key = { "user_res_${it.id}" }) { u ->
                                MemberCallRow(
                                    name = u.displayName,
                                    username = u.username,
                                    avatar = u.avatar,
                                    language = null,
                                    isMember = true,
                                    onCall = { placeCall(u.id, u.displayName) },
                                    onVoicemail = { onVoicemail(u.id, u.displayName) },
                                )
                            }
                        } else if (searchAttempted) {
                            item(key = "no_search_results") {
                                EmptyState(
                                    Icons.Filled.Person,
                                    "No members found",
                                    "No Sarvagyan account matched '$searchQuery'. Try checking the spelling or phone number."
                                )
                            }
                        }
                        item(key = "search_divider") {
                            Spacer(Modifier.height(16.dp))
                            HorizontalDivider()
                            Spacer(Modifier.height(12.dp))
                        }
                    }

                    // Synchronized / Discovered Members Section
                    if (matchedPhoneContacts.isNotEmpty()) {
                        item(key = "discovered_from_phone_header") {
                            SectionTitle("From Your Phone Contacts")
                        }
                        items(matchedPhoneContacts, key = { "matched_phone_${it.id}" }) { m ->
                            MemberCallRow(
                                name = m.name,
                                username = m.username,
                                avatar = m.avatar,
                                language = c.language(m.language)?.name ?: m.language,
                                isMember = true,
                                onCall = { placeCall(m.id, m.name) },
                                onVoicemail = { onVoicemail(m.id, m.name) },
                            )
                        }
                        item(key = "phone_contacts_spacer") {
                            Spacer(Modifier.height(12.dp))
                        }
                    }

                    // Existing Saved Contacts Section
                    item(key = "contacts_header") {
                        Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                            SectionTitle("Your Contacts")
                            Spacer(Modifier.weight(1f))
                            if (!permissionGranted) {
                                TextButton(
                                    onClick = { contactPermissionLauncher.launch(Manifest.permission.READ_CONTACTS) },
                                    contentPadding = PaddingValues(horizontal = 8.dp)
                                ) {
                                    Icon(Icons.Filled.Refresh, contentDescription = null, modifier = Modifier.size(16.dp))
                                    Spacer(Modifier.width(4.dp))
                                    Text("Sync Phone", style = MaterialTheme.typography.labelMedium)
                                }
                            }
                        }
                    }

                    val contactList = contacts
                    when {
                        contactList == null -> item(key = "contacts_loading") {
                            Row(Modifier.padding(16.dp), verticalAlignment = Alignment.CenterVertically) {
                                CircularProgressIndicator(Modifier.size(18.dp), strokeWidth = 2.dp)
                                Spacer(Modifier.width(8.dp))
                                Text("Loading contacts…", color = MaterialTheme.colorScheme.onSurfaceVariant)
                            }
                        }
                        contactList.isEmpty() && matchedPhoneContacts.isEmpty() -> item(key = "contacts_empty") {
                            EmptyState(
                                Icons.Filled.People,
                                "No contacts yet",
                                "Search above using a member's @username or mobile number to connect and start a call."
                            )
                        }
                        else -> {
                            if (contactList.isNotEmpty()) {
                                items(contactList, key = { "saved_contact_${it.id}" }) { contact ->
                                    MemberCallRow(
                                        name = contact.name,
                                        username = contact.username,
                                        avatar = contact.avatar,
                                        language = c.language(contact.language)?.name ?: contact.language,
                                        isMember = true,
                                        onCall = { placeCall(contact.id, contact.name) },
                                        onVoicemail = { onVoicemail(contact.id, contact.name) },
                                    )
                                }
                            }
                        }
                    }
                    item(key = "bottom_padding") {
                        Spacer(Modifier.height(32.dp))
                    }
                }
            } else {
                // ---------------------------------------------------------------------------------
                // OPTION B: CREATE OR JOIN ROOM
                // ---------------------------------------------------------------------------------
                LazyColumn(
                    modifier = Modifier.fillMaxSize(),
                    contentPadding = PaddingValues(horizontal = 20.dp, vertical = 12.dp),
                ) {
                    // Choice 1: Create a Room
                    item(key = "create_room_card") {
                        Surface(
                            onClick = onCreateRoom,
                            shape = MaterialTheme.shapes.extraLarge,
                            modifier = Modifier.fillMaxWidth(),
                            color = Brand.PrimaryAccent,
                        ) {
                            Column(
                                Modifier
                                    .fillMaxWidth()
                                    .background(
                                        Brush.horizontalGradient(
                                            listOf(Brand.PrimaryAccent, Brand.HighlightAccent)
                                        )
                                    )
                                    .padding(24.dp)
                            ) {
                                Row(verticalAlignment = Alignment.CenterVertically) {
                                    Icon(
                                        Icons.Filled.Call,
                                        contentDescription = null,
                                        tint = Brand.ButtonContent,
                                        modifier = Modifier.size(32.dp),
                                    )
                                    Spacer(Modifier.width(12.dp))
                                    Text(
                                        "Create a Calling Room",
                                        style = MaterialTheme.typography.titleLarge,
                                        fontWeight = FontWeight.Bold,
                                        color = Brand.ButtonContent,
                                    )
                                }
                                Spacer(Modifier.height(8.dp))
                                Text(
                                    "Generate an instant room code and link to share with anyone. Participants can join from their phone or any web browser.",
                                    style = MaterialTheme.typography.bodyMedium,
                                    color = Brand.ButtonContent.copy(alpha = 0.9f),
                                )
                                Spacer(Modifier.height(16.dp))
                                Row(
                                    Modifier.fillMaxWidth(),
                                    horizontalArrangement = Arrangement.End,
                                    verticalAlignment = Alignment.CenterVertically,
                                ) {
                                    Text(
                                        "Create Room →",
                                        style = MaterialTheme.typography.labelLarge,
                                        fontWeight = FontWeight.Bold,
                                        color = Brand.ButtonContent,
                                    )
                                }
                            }
                        }
                        Spacer(Modifier.height(20.dp))
                    }

                    // Choice 2: Join an Existing Room
                    item(key = "join_room_card") {
                        AppCard {
                            Row(verticalAlignment = Alignment.CenterVertically) {
                                Icon(
                                    Icons.Filled.MeetingRoom,
                                    contentDescription = null,
                                    tint = Brand.HighlightAccent,
                                    modifier = Modifier.size(28.dp),
                                )
                                Spacer(Modifier.width(12.dp))
                                Text("Join an Existing Room", style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold)
                            }
                            Spacer(Modifier.height(8.dp))
                            Text(
                                "Enter the 6-letter invitation code provided by the call host.",
                                style = MaterialTheme.typography.bodyMedium,
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                            )
                            Spacer(Modifier.height(16.dp))

                            OutlinedTextField(
                                value = roomCode,
                                onValueChange = { roomCode = normaliseCode(it).take(6) },
                                label = { Text("6-Letter Room Code") },
                                placeholder = { Text("e.g. ABCXYZ") },
                                singleLine = true,
                                modifier = Modifier.fillMaxWidth(),
                                textStyle = MaterialTheme.typography.titleLarge.copy(
                                    fontFamily = FontFamily.Monospace,
                                    fontWeight = FontWeight.Bold,
                                    textAlign = TextAlign.Center,
                                ),
                                keyboardOptions = KeyboardOptions(
                                    capitalization = KeyboardCapitalization.Characters,
                                    imeAction = ImeAction.Go,
                                ),
                                keyboardActions = KeyboardActions(
                                    onGo = { if (roomCode.length == 6) onJoinRoom(roomCode) }
                                ),
                            )

                            Spacer(Modifier.height(16.dp))

                            PrimaryButton(
                                text = "Join Room →",
                                onClick = { onJoinRoom(roomCode) },
                                modifier = Modifier.fillMaxWidth(),
                                enabled = roomCode.length == 6,
                            )
                        }
                    }

                    item(key = "room_bottom_space") {
                        Spacer(Modifier.height(32.dp))
                    }
                }
            }
        }
    }
}

/**
 * Reusable contact/member row with 1-click Direct Call initiation.
 */
@Composable
private fun MemberCallRow(
    name: String,
    username: String?,
    avatar: String?,
    language: String?,
    isMember: Boolean,
    onCall: () -> Unit,
    onVoicemail: () -> Unit,
) {
    Row(
        Modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(12.dp))
            .clickable { onCall() }
            .padding(vertical = 8.dp, horizontal = 4.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Avatar(name, LocalCallColors.current.peer, 44.dp, avatar = avatar, useMain = false)
        Spacer(Modifier.width(12.dp))
        Column(Modifier.weight(1f)) {
            Text(name, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
            Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                username?.let {
                    Text("@$it", style = MaterialTheme.typography.bodySmall, color = Brand.HighlightAccent)
                }
                language?.let {
                    LanguagePill(it, highlighted = false)
                }
            }
        }
        IconButton(onClick = onVoicemail) {
            Icon(Icons.Filled.Voicemail, contentDescription = "Send voicemail", tint = MaterialTheme.colorScheme.onSurfaceVariant)
        }
        IconButton(
            onClick = onCall,
            modifier = Modifier
                .size(40.dp)
                .clip(RoundedCornerShape(10.dp))
                .background(Brand.PrimaryAccent)
        ) {
            Icon(Icons.Filled.Call, contentDescription = "Call $name", tint = Brand.ButtonContent, modifier = Modifier.size(20.dp))
        }
    }
}
