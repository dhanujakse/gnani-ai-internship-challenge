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
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBarsPadding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.Call
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.MeetingRoom
import androidx.compose.material.icons.filled.MoreVert
import androidx.compose.material.icons.filled.People
import androidx.compose.material.icons.filled.Person
import androidx.compose.material.icons.filled.PersonAdd
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material.icons.filled.Search
import androidx.compose.material.icons.filled.Share
import androidx.compose.material.icons.filled.Sync
import androidx.compose.material.icons.filled.Voicemail
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.FilterChip
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.OutlinedTextFieldDefaults
import androidx.compose.material3.Surface
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
import androidx.compose.ui.focus.FocusRequester
import androidx.compose.ui.focus.focusRequester
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.input.KeyboardCapitalization
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
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
import ai.mack.sarvagyan.ui.components.PostLoginBackground
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
 * Unified Call Hub: Consolidates direct member calls, contacts, discovery,
 * and room operations into one streamlined, cohesive experience.
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
    val user by c.user.collectAsStateWithLifecycle()
    val placeCall = rememberPlaceCall(onCallStarted)

    // Primary mode: 0: Direct Call / Contact, 1: Create or Join Room
    var selectedOption by remember { mutableIntStateOf(0) }

    // Contact Sub-Tab: 0: My Contacts, 1: Discover from Phone
    var contactSubTab by remember { mutableIntStateOf(0) }

    // Direct search & dialer state
    var dialNumber by remember { mutableStateOf("") }
    var dialingPhone by remember { mutableStateOf(false) }

    // Username search & add state
    var usernameQuery by remember { mutableStateOf("") }
    var suggestions by remember { mutableStateOf<List<UserSearchResult>>(emptyList()) }
    var searchingUsers by remember { mutableStateOf(false) }
    var searchAttempted by remember { mutableStateOf(false) }
    var addingContact by remember { mutableStateOf(false) }
    val usernameFocus = remember { FocusRequester() }

    // Contact list state
    var contacts by remember { mutableStateOf<List<ContactUser>?>(null) }
    var error by remember { mutableStateOf<String?>(null) }

    // Phone discovery state
    var hasContactPermission by remember {
        mutableStateOf(ContextCompat.checkSelfPermission(context, Manifest.permission.READ_CONTACTS) == PackageManager.PERMISSION_GRANTED)
    }
    var phoneContacts by remember { mutableStateOf<List<DevicePhoneContact>>(emptyList()) }
    var matchedUsers by remember { mutableStateOf<List<MatchedContact>>(emptyList()) }
    var syncingContacts by remember { mutableStateOf(false) }
    var syncProgress by remember { mutableStateOf<String?>(null) }
    var discoverFilterQuery by remember { mutableStateOf("") }

    // Room join state
    var roomCode by remember { mutableStateOf("") }

    fun mergeContact(added: ContactUser) {
        val current = contacts ?: emptyList()
        contacts = (current.filterNot { it.id == added.id } + added).sortedBy { it.name.lowercase() }
    }

    suspend fun loadContacts() {
        try {
            contacts = c.api.contacts().contacts
            error = null
        } catch (e: ApiException) {
            error = e.message
            if (contacts == null) contacts = emptyList()
        }
    }

    fun syncPhone() {
        if (!hasContactPermission) return
        syncingContacts = true
        scope.launch {
            try {
                val (stats, matches) = syncDeviceContactsWithServer(context, c.api) { syncProgress = it }
                phoneContacts = stats.contacts
                matchedUsers = matches
            } catch (e: Exception) {
                error = (e as? ApiException)?.message ?: e.message
            } finally {
                syncingContacts = false
                syncProgress = null
            }
        }
    }

    val contactPermissionLauncher = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { granted ->
        hasContactPermission = granted
        if (granted) syncPhone()
    }

    LaunchedEffect(Unit) {
        loadContacts()
        if (hasContactPermission) syncPhone()
    }

    // Debounced username search
    LaunchedEffect(usernameQuery) {
        val clean = usernameQuery.trim().removePrefix("@").trim()
        if (clean.isEmpty()) {
            suggestions = emptyList()
            searchingUsers = false
            searchAttempted = false
            return@LaunchedEffect
        }
        searchingUsers = true
        searchAttempted = false
        delay(300)
        try {
            suggestions = c.api.searchUsers(clean).users.take(10)
            searchAttempted = true
        } catch (_: Exception) {
            suggestions = emptyList()
            searchAttempted = true
        } finally {
            searchingUsers = false
        }
    }

    fun addPerson(targetUsername: String? = null, targetUserId: String? = null) {
        val clean = targetUsername?.trim()?.removePrefix("@")?.trim()?.takeIf { it.isNotEmpty() }
        if (clean == null && targetUserId.isNullOrBlank()) return
        addingContact = true
        scope.launch {
            try {
                val added = c.api.addContact(username = clean, userId = targetUserId)
                mergeContact(added)
                usernameQuery = ""
                suggestions = emptyList()
                searchAttempted = false
                error = null
                loadContacts()
            } catch (e: ApiException) {
                error = e.message
            } finally {
                addingContact = false
            }
        }
    }

    fun callOrAddByPhone() {
        val norm = normalizePhoneE164(dialNumber, "+91")
        if (norm == null) {
            error = "Enter a valid phone number (e.g. +91 9876543210)."
            return
        }
        dialingPhone = true
        error = null
        scope.launch {
            try {
                val matches = c.api.matchPhones(listOf(sha256Hex(norm))).matches
                val found = matches.firstOrNull()
                if (found != null) {
                    placeCall(found.id, found.name)
                } else {
                    error = "No Sarvagyan account found with that phone number."
                }
            } catch (e: Exception) {
                error = (e as? ApiException)?.message ?: e.message
            } finally {
                dialingPhone = false
            }
        }
    }

    fun String.normFilter(): String = lowercase().replace(" ", "").replace("-", "")

    val phoneByHash = remember(phoneContacts) { phoneContacts.associate { it.hash to it.number } }
    val allMatched = remember(matchedUsers, phoneContacts, contacts) {
        val list = matchedUsers.toMutableList()
        val existingIds = list.map { it.id }.toSet()
        val existingHashes = list.mapNotNull { it.phoneHash }.toSet()

        phoneContacts.forEach { pc ->
            if (pc.hash !in existingHashes) {
                val pcNorm = pc.name.normFilter()
                val match = contacts?.firstOrNull { c ->
                    c.id !in existingIds && (
                        c.name.normFilter() == pcNorm ||
                        (c.username?.normFilter() != null && c.username.normFilter() == pcNorm) ||
                        (pcNorm.length >= 4 && c.name.normFilter().contains(pcNorm)) ||
                        (c.name.normFilter().length >= 4 && pcNorm.contains(c.name.normFilter()))
                    )
                }
                if (match != null) {
                    list.add(
                        MatchedContact(
                            id = match.id,
                            name = pc.name,
                            username = match.username,
                            avatar = match.avatar,
                            language = match.language,
                            phoneHash = pc.hash,
                        )
                    )
                }
            }
        }
        list
    }

    val matchedHashes = remember(allMatched) { allMatched.mapNotNull { it.phoneHash }.toSet() }
    val unmatched = remember(phoneContacts, matchedHashes, contacts) {
        phoneContacts.filter { pc ->
            if (pc.hash in matchedHashes) false
            else {
                val pcNorm = pc.name.normFilter()
                val matchesKnown = contacts?.any { c ->
                    c.name.normFilter() == pcNorm ||
                    (c.username?.normFilter() != null && c.username.normFilter() == pcNorm) ||
                    (pcNorm.length >= 4 && c.name.normFilter().contains(pcNorm)) ||
                    (c.name.normFilter().length >= 4 && pcNorm.contains(c.name.normFilter()))
                } == true
                !matchesKnown
            }
        }
    }

    val normDiscoverQuery = remember(discoverFilterQuery) { discoverFilterQuery.normFilter() }
    val filteredMatched = remember(allMatched, phoneByHash, normDiscoverQuery) {
        if (normDiscoverQuery.isEmpty()) allMatched
        else allMatched.filter { m ->
            m.name.normFilter().contains(normDiscoverQuery) ||
                (m.username?.normFilter()?.contains(normDiscoverQuery) == true) ||
                (m.phoneHash?.let { phoneByHash[it]?.normFilter()?.contains(normDiscoverQuery) } == true)
        }
    }
    val filteredUnmatched = remember(unmatched, normDiscoverQuery) {
        if (normDiscoverQuery.isEmpty()) unmatched
        else unmatched.filter { u ->
            u.name.normFilter().contains(normDiscoverQuery) || u.number.normFilter().contains(normDiscoverQuery)
        }
    }

    PostLoginBackground {
        Column(Modifier.fillMaxSize().statusBarsPadding().padding(top = 8.dp)) {
            // Screen Header
            Row(
                Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 4.dp, vertical = 6.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                IconButton(onClick = onBack) {
                    Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "Back", tint = Brand.HighlightAccent)
                }
                Column(Modifier.weight(1f)) {
                    Text("Start a Call", style = MaterialTheme.typography.titleLarge, fontWeight = FontWeight.Bold, color = Brand.PrimaryText)
                    Text("Call someone directly or create / join a room", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
            }

            // Primary 2-Option Selector
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

            Spacer(Modifier.height(4.dp))

            if (selectedOption == 0) {
                // ---------------------------------------------------------------------------------
                // OPTION A: DIRECT CALL / CONTACT (With embedded My Contacts & Discover from Phone)
                // ---------------------------------------------------------------------------------
                LazyColumn(
                    modifier = Modifier.fillMaxSize(),
                    contentPadding = PaddingValues(horizontal = 20.dp, vertical = 8.dp),
                ) {
                    // Call by Phone Number input (direct dialing)
                    item(key = "call_by_phone_number") {
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            OutlinedTextField(
                                value = dialNumber,
                                onValueChange = { dialNumber = it.filter { ch -> ch.isDigit() || ch == '+' || ch == ' ' || ch == '-' }.take(20) },
                                label = { Text("Call by phone number") },
                                placeholder = { Text("e.g. +91 9876543210") },
                                singleLine = true,
                                modifier = Modifier.weight(1f),
                                keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Phone, imeAction = ImeAction.Go),
                                keyboardActions = KeyboardActions(onGo = { callOrAddByPhone() }),
                                colors = OutlinedTextFieldDefaults.colors(
                                    focusedTextColor = Brand.PrimaryText,
                                    unfocusedTextColor = Brand.PrimaryText,
                                    focusedBorderColor = Brand.HighlightAccent,
                                    unfocusedBorderColor = Brand.Borders.copy(alpha = 0.8f),
                                    focusedLabelColor = Brand.HighlightAccent,
                                    unfocusedLabelColor = Brand.SecondaryText,
                                    focusedContainerColor = Brand.CardBg.copy(alpha = 0.85f),
                                    unfocusedContainerColor = Brand.CardBg.copy(alpha = 0.65f),
                                ),
                            )
                            Spacer(Modifier.width(8.dp))
                            IconButton(
                                onClick = { callOrAddByPhone() },
                                enabled = dialNumber.isNotBlank() && !dialingPhone,
                                modifier = Modifier
                                    .size(48.dp)
                                    .clip(RoundedCornerShape(12.dp))
                                    .background(if (dialNumber.isNotBlank()) Brand.PrimaryAccent else Brand.CardBg.copy(alpha = 0.65f)),
                            ) {
                                if (dialingPhone) {
                                    CircularProgressIndicator(Modifier.size(20.dp), strokeWidth = 2.dp, color = Brand.ButtonContent)
                                } else {
                                    Icon(Icons.Filled.Call, contentDescription = "Call number", tint = if (dialNumber.isNotBlank()) Brand.ButtonContent else MaterialTheme.colorScheme.onSurfaceVariant)
                                }
                            }
                        }
                        Spacer(Modifier.height(14.dp))
                    }

                    // Contact Sub-Tabs: "My Contacts" vs "Discover from Phone"
                    item(key = "contact_sub_tabs") {
                        Row(
                            modifier = Modifier
                                .fillMaxWidth()
                                .clip(RoundedCornerShape(12.dp))
                                .background(MaterialTheme.colorScheme.surfaceVariant)
                                .padding(4.dp),
                            horizontalArrangement = Arrangement.spacedBy(4.dp),
                        ) {
                            listOf("My Contacts", "Discover from Phone").forEachIndexed { i, label ->
                                val selected = contactSubTab == i
                                Column(
                                    modifier = Modifier
                                        .weight(1f)
                                        .clip(RoundedCornerShape(10.dp))
                                        .background(if (selected) MaterialTheme.colorScheme.primary else Color.Transparent)
                                        .clickable {
                                            contactSubTab = i
                                            if (i == 1 && hasContactPermission && phoneContacts.isEmpty()) {
                                                syncPhone()
                                            }
                                        }
                                        .padding(vertical = 10.dp, horizontal = 8.dp),
                                    horizontalAlignment = Alignment.CenterHorizontally,
                                ) {
                                    Text(
                                        label,
                                        color = if (selected) MaterialTheme.colorScheme.onPrimary else MaterialTheme.colorScheme.onSurfaceVariant,
                                        fontWeight = if (selected) FontWeight.Bold else FontWeight.Normal,
                                        style = MaterialTheme.typography.labelLarge,
                                        textAlign = TextAlign.Center,
                                    )
                                }
                            }
                        }
                        Spacer(Modifier.height(14.dp))
                    }

                    error?.let { err ->
                        item(key = "error_banner") {
                            ErrorBanner(err, onDismiss = { error = null })
                            Spacer(Modifier.height(10.dp))
                        }
                    }

                    if (contactSubTab == 0) {
                        // -------------------------------------------------------------------------
                        // SUB-TAB 0: MY CONTACTS (Add by @username with suggestions, Contacts list)
                        // -------------------------------------------------------------------------
                        item(key = "add_by_username_box") {
                            Row(verticalAlignment = Alignment.CenterVertically) {
                                OutlinedTextField(
                                    value = usernameQuery,
                                    onValueChange = { usernameQuery = it.filter { ch -> ch.isLetterOrDigit() || ch == '_' || ch == '@' || ch == ' ' }.take(25) },
                                    label = { Text("Find & Add by @username") },
                                    placeholder = { Text("Type username...") },
                                    singleLine = true,
                                    modifier = Modifier.weight(1f).focusRequester(usernameFocus),
                                    keyboardOptions = KeyboardOptions(imeAction = ImeAction.Search),
                                    keyboardActions = KeyboardActions(onSearch = {
                                        val clean = usernameQuery.trim().removePrefix("@").trim()
                                        if (clean.isNotEmpty()) addPerson(targetUsername = clean)
                                    }),
                                    colors = OutlinedTextFieldDefaults.colors(
                                        focusedTextColor = Brand.PrimaryText,
                                        unfocusedTextColor = Brand.PrimaryText,
                                        focusedBorderColor = Brand.HighlightAccent,
                                        unfocusedBorderColor = Brand.Borders.copy(alpha = 0.8f),
                                        focusedLabelColor = Brand.HighlightAccent,
                                        unfocusedLabelColor = Brand.SecondaryText,
                                        focusedContainerColor = Brand.CardBg.copy(alpha = 0.85f),
                                        unfocusedContainerColor = Brand.CardBg.copy(alpha = 0.65f),
                                    ),
                                )
                                Spacer(Modifier.width(8.dp))
                                IconButton(
                                    onClick = {
                                        val clean = usernameQuery.trim().removePrefix("@").trim()
                                        if (clean.isNotEmpty()) addPerson(targetUsername = clean)
                                    },
                                    enabled = usernameQuery.isNotBlank() && !addingContact,
                                    modifier = Modifier
                                        .size(48.dp)
                                        .clip(RoundedCornerShape(12.dp))
                                        .background(if (usernameQuery.isNotBlank()) Brand.HighlightAccent else Brand.CardBg.copy(alpha = 0.65f)),
                                ) {
                                    if (addingContact) {
                                        CircularProgressIndicator(Modifier.size(20.dp), strokeWidth = 2.dp, color = Color(0xFF071B20))
                                    } else {
                                        Icon(
                                            Icons.Filled.PersonAdd,
                                            contentDescription = "Add contact",
                                            tint = if (usernameQuery.isNotBlank()) Color(0xFF071B20) else MaterialTheme.colorScheme.onSurfaceVariant
                                        )
                                    }
                                }
                            }
                        }

                        // Username suggestions while typing
                        val cleanQuery = usernameQuery.trim().removePrefix("@").trim()
                        if (cleanQuery.isNotEmpty()) {
                            item(key = "username_suggestions") {
                                Spacer(Modifier.height(8.dp))
                                when {
                                    searchingUsers -> Text("Searching…", color = MaterialTheme.colorScheme.onSurfaceVariant, style = MaterialTheme.typography.bodyMedium)
                                    suggestions.isEmpty() && searchAttempted -> Text("No user found", color = MaterialTheme.colorScheme.onSurfaceVariant, style = MaterialTheme.typography.bodyMedium)
                                    suggestions.isNotEmpty() -> AppCard {
                                        suggestions.forEachIndexed { idx, s ->
                                            val isAdded = contacts?.any { it.id == s.id } == true
                                            Row(
                                                modifier = Modifier
                                                    .fillMaxWidth()
                                                    .padding(vertical = 8.dp),
                                                verticalAlignment = Alignment.CenterVertically,
                                            ) {
                                                Avatar(s.displayName, LocalCallColors.current.peer, 38.dp, avatar = s.avatar, useMain = false)
                                                Spacer(Modifier.width(12.dp))
                                                Column(Modifier.weight(1f)) {
                                                    Text(s.displayName, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
                                                    s.username?.let { Text("@$it", style = MaterialTheme.typography.bodySmall, color = Brand.HighlightAccent) }
                                                }
                                                IconButton(onClick = { placeCall(s.id, s.displayName) }) {
                                                    Icon(Icons.Filled.Call, contentDescription = "Call ${s.displayName}", tint = Brand.PrimaryAccent)
                                                }
                                                if (!isAdded) {
                                                    TextButton(onClick = { addPerson(targetUsername = s.username, targetUserId = s.id) }, enabled = !addingContact) {
                                                        Text("Add")
                                                    }
                                                } else {
                                                    Text("Added", style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
                                                }
                                            }
                                            if (idx < suggestions.lastIndex) HorizontalDivider(color = MaterialTheme.colorScheme.outlineVariant)
                                        }
                                    }
                                }
                                Spacer(Modifier.height(8.dp))
                            }
                        }

                        item(key = "my_contacts_header") {
                            SectionTitle("Your Contacts (Tap to Call)")
                        }

                        val contactList = contacts
                        when {
                            contactList == null -> item(key = "loading_contacts") {
                                Row(Modifier.padding(16.dp), verticalAlignment = Alignment.CenterVertically) {
                                    CircularProgressIndicator(Modifier.size(18.dp), strokeWidth = 2.dp)
                                    Spacer(Modifier.width(8.dp))
                                    Text("Loading contacts…", color = MaterialTheme.colorScheme.onSurfaceVariant)
                                }
                            }
                            contactList.isEmpty() -> item(key = "empty_contacts") {
                                EmptyState(
                                    Icons.Filled.People,
                                    "No contacts yet",
                                    "Add people above by their @username or phone number. Tap any contact to place a direct call."
                                )
                            }
                            else -> items(contactList, key = { "contact_${it.id}" }) { contact ->
                                AppCard(modifier = Modifier.fillMaxWidth().padding(vertical = 4.dp)) {
                                    ContactItemRow(
                                        name = contact.name,
                                        username = contact.username,
                                        avatar = contact.avatar,
                                        language = c.language(contact.language)?.name ?: contact.language,
                                        onTapCall = { placeCall(contact.id, contact.name) },
                                        onVoicemail = { onVoicemail(contact.id, contact.name) },
                                        menu = listOf(
                                            "Remove from contacts" to { scope.launch { runCatching { c.api.removeContact(contact.id) }; loadContacts() } },
                                            "Block" to { scope.launch { runCatching { c.api.block(contact.id) }; loadContacts() } },
                                        )
                                    )
                                }
                            }
                        }

                        item(key = "contacts_bottom_spacer") {
                            Spacer(Modifier.height(24.dp))
                        }
                    } else {
                        // -------------------------------------------------------------------------
                        // SUB-TAB 1: DISCOVER FROM PHONE (Sync, Search, Matched & Invite list)
                        // -------------------------------------------------------------------------
                        if (!hasContactPermission) {
                            item(key = "permission_request_banner") {
                                AppCard {
                                    Row(verticalAlignment = Alignment.CenterVertically) {
                                        Icon(Icons.Filled.People, contentDescription = null, tint = Brand.HighlightAccent, modifier = Modifier.size(32.dp))
                                        Spacer(Modifier.width(12.dp))
                                        Column(Modifier.weight(1f)) {
                                            Text("Find friends from your phone", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.Bold)
                                            Text("Discover which of your phone contacts already use Sarvagyan.", style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
                                        }
                                    }
                                    Spacer(Modifier.height(12.dp))
                                    PrimaryButton(
                                        text = "Sync Phone Contacts",
                                        onClick = { contactPermissionLauncher.launch(Manifest.permission.READ_CONTACTS) },
                                        modifier = Modifier.fillMaxWidth(),
                                    )
                                }
                                Spacer(Modifier.height(16.dp))
                            }
                        } else {
                            // Sync status bar with prominent "Sync now" button
                            item(key = "sync_status_bar") {
                                AppCard {
                                    Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                                        Column(Modifier.weight(1f)) {
                                            Text(
                                                "${phoneContacts.size} contacts scanned · ${allMatched.size} on Sarvagyan",
                                                style = MaterialTheme.typography.bodyMedium,
                                                fontWeight = FontWeight.SemiBold,
                                                color = Brand.PrimaryText,
                                            )
                                            if (syncingContacts) {
                                                Spacer(Modifier.height(4.dp))
                                                Text(
                                                    syncProgress ?: "Syncing phone contacts…",
                                                    style = MaterialTheme.typography.bodySmall,
                                                    color = Brand.HighlightAccent,
                                                )
                                            }
                                        }
                                        Button(
                                            onClick = { syncPhone() },
                                            enabled = !syncingContacts,
                                            shape = RoundedCornerShape(10.dp),
                                            colors = ButtonDefaults.buttonColors(
                                                containerColor = Brand.HighlightAccent,
                                                contentColor = Color(0xFF071B20)
                                            ),
                                            contentPadding = PaddingValues(horizontal = 14.dp, vertical = 8.dp)
                                        ) {
                                            if (syncingContacts) {
                                                CircularProgressIndicator(Modifier.size(16.dp), strokeWidth = 2.dp, color = Color(0xFF071B20))
                                            } else {
                                                Icon(Icons.Filled.Sync, contentDescription = null, modifier = Modifier.size(16.dp))
                                                Spacer(Modifier.width(6.dp))
                                                Text("Sync now", fontWeight = FontWeight.Bold, style = MaterialTheme.typography.labelMedium)
                                            }
                                        }
                                    }
                                    if (syncingContacts) {
                                        Spacer(Modifier.height(8.dp))
                                        LinearProgressIndicator(modifier = Modifier.fillMaxWidth(), color = Brand.HighlightAccent)
                                    }
                                }
                                Spacer(Modifier.height(14.dp))
                            }

                            // Search filter box for phone contacts
                            item(key = "phone_search_box") {
                                OutlinedTextField(
                                    value = discoverFilterQuery,
                                    onValueChange = { discoverFilterQuery = it },
                                    label = { Text("Search phone contacts") },
                                    placeholder = { Text("Search by name or number...") },
                                    leadingIcon = { Icon(Icons.Filled.Search, null, tint = Brand.HighlightAccent) },
                                    trailingIcon = {
                                        if (discoverFilterQuery.isNotEmpty()) {
                                            IconButton(onClick = { discoverFilterQuery = "" }) { Icon(Icons.Filled.Close, null) }
                                        }
                                    },
                                    singleLine = true,
                                    modifier = Modifier.fillMaxWidth(),
                                    colors = OutlinedTextFieldDefaults.colors(
                                        focusedTextColor = Brand.PrimaryText,
                                        unfocusedTextColor = Brand.PrimaryText,
                                        focusedBorderColor = Brand.HighlightAccent,
                                        unfocusedBorderColor = Brand.Borders.copy(alpha = 0.8f),
                                        focusedLabelColor = Brand.HighlightAccent,
                                        unfocusedLabelColor = Brand.SecondaryText,
                                        focusedContainerColor = Brand.CardBg.copy(alpha = 0.85f),
                                        unfocusedContainerColor = Brand.CardBg.copy(alpha = 0.65f),
                                    ),
                                )
                                Spacer(Modifier.height(14.dp))
                            }

                            // Section: Discovered on Sarvagyan
                            item(key = "matched_section_header") {
                                SectionTitle("On Sarvagyan (${filteredMatched.size})")
                            }
                            if (filteredMatched.isEmpty()) {
                                item(key = "no_matched_contacts") {
                                    Text(
                                        if (discoverFilterQuery.isNotEmpty()) "No matching friends found." else "None of your phone contacts have joined Sarvagyan yet.",
                                        style = MaterialTheme.typography.bodyMedium,
                                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                                        modifier = Modifier.padding(vertical = 8.dp),
                                    )
                                }
                            } else {
                                items(filteredMatched, key = { "matched_${it.id}" }) { m ->
                                    val num = m.phoneHash?.let { phoneByHash[it] }
                                    AppCard(modifier = Modifier.fillMaxWidth().padding(vertical = 4.dp)) {
                                        ContactItemRow(
                                            name = m.name,
                                            username = m.username,
                                            avatar = m.avatar,
                                            language = c.language(m.language)?.name ?: m.language,
                                            subtitle = num,
                                            onTapCall = { placeCall(m.id, m.name) },
                                            onVoicemail = { onVoicemail(m.id, m.name) },
                                        )
                                    }
                                }
                            }

                            // Section: Invite from your phone
                            item(key = "unmatched_section_header") {
                                Spacer(Modifier.height(16.dp))
                                SectionTitle("Invite to Sarvagyan (${filteredUnmatched.size})")
                            }
                            if (filteredUnmatched.isEmpty()) {
                                item(key = "no_unmatched_contacts") {
                                    Text("No contacts to invite.", style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
                                }
                            } else {
                                items(filteredUnmatched.take(50), key = { "unmatched_${it.hash}" }) { u ->
                                    Row(
                                        Modifier
                                            .fillMaxWidth()
                                            .padding(vertical = 8.dp),
                                        verticalAlignment = Alignment.CenterVertically,
                                    ) {
                                        Avatar(u.name, LocalCallColors.current.peer, 40.dp, avatar = null, useMain = false)
                                        Spacer(Modifier.width(12.dp))
                                        Column(Modifier.weight(1f)) {
                                            Text(u.name, style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
                                            Text(u.number, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                                        }
                                        TextButton(onClick = { shareInvite(context, u.name) }) {
                                            Icon(Icons.Filled.Share, contentDescription = null, modifier = Modifier.size(16.dp))
                                            Spacer(Modifier.width(4.dp))
                                            Text("Invite")
                                        }
                                    }
                                }
                            }
                            item(key = "discover_bottom_spacer") {
                                Spacer(Modifier.height(32.dp))
                            }
                        }
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
 * Reusable contact item row where tapping anywhere on the row immediately places a call.
 */
@Composable
private fun ContactItemRow(
    name: String,
    username: String?,
    avatar: String?,
    language: String?,
    subtitle: String? = null,
    onTapCall: () -> Unit,
    onVoicemail: () -> Unit,
    menu: List<Pair<String, () -> Unit>> = emptyList(),
) {
    var showMenu by remember { mutableStateOf(false) }

    Row(
        Modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(12.dp))
            .clickable { onTapCall() }
            .padding(vertical = 4.dp, horizontal = 2.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Avatar(name, LocalCallColors.current.peer, 44.dp, avatar = avatar, useMain = false)
        Spacer(Modifier.width(12.dp))
        Column(Modifier.weight(1f)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text(
                    text = name,
                    style = MaterialTheme.typography.titleMedium,
                    fontWeight = FontWeight.SemiBold,
                    color = Brand.PrimaryText,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                    modifier = Modifier.weight(1f, fill = false),
                )
                if (language != null) {
                    Spacer(Modifier.width(8.dp))
                    LanguagePill(language, highlighted = false)
                }
            }
            Spacer(Modifier.height(3.dp))
            Row(
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(6.dp),
            ) {
                if (username != null) {
                    Text(
                        text = "@$username",
                        style = MaterialTheme.typography.bodySmall,
                        color = Brand.HighlightAccent,
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis,
                    )
                }
                if (username != null && subtitle != null) {
                    Text("·", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
                if (subtitle != null) {
                    Text(
                        text = subtitle,
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis,
                    )
                }
            }
        }
        Spacer(Modifier.width(8.dp))
        IconButton(
            onClick = onTapCall,
            modifier = Modifier
                .size(42.dp)
                .clip(RoundedCornerShape(12.dp))
                .background(Brand.PrimaryAccent),
        ) {
            Icon(Icons.Filled.Call, contentDescription = "Call $name", tint = Brand.ButtonContent, modifier = Modifier.size(20.dp))
        }
        if (menu.isNotEmpty()) {
            Box {
                IconButton(onClick = { showMenu = true }) {
                    Icon(Icons.Filled.MoreVert, contentDescription = "Options", tint = MaterialTheme.colorScheme.onSurfaceVariant)
                }
                DropdownMenu(expanded = showMenu, onDismissRequest = { showMenu = false }) {
                    menu.forEach { (label, act) ->
                        DropdownMenuItem(text = { Text(label) }, onClick = { showMenu = false; act() })
                    }
                }
            }
        }
    }
}
