package ai.mack.sarvagyan.ui.screens

import android.Manifest
import android.content.Context
import android.content.Intent
import android.provider.ContactsContract
import java.security.MessageDigest
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material.icons.filled.Chat
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.Share
import androidx.compose.material.icons.filled.Search
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.material3.LinearProgressIndicator
import ai.mack.sarvagyan.data.MatchedContact
import ai.mack.sarvagyan.data.UserSearchResult
import ai.mack.sarvagyan.ui.components.PrimaryButton
import ai.mack.sarvagyan.ui.components.SecondaryButton
import ai.mack.sarvagyan.ui.theme.Brand
import android.content.pm.PackageManager
import android.widget.Toast
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
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
import androidx.compose.foundation.layout.statusBarsPadding
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
import androidx.compose.material3.HorizontalDivider
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
import androidx.compose.ui.draw.clip
import androidx.compose.ui.focus.FocusRequester
import androidx.compose.ui.focus.focusRequester
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.input.KeyboardType
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
import ai.mack.sarvagyan.ui.components.PostLoginBackground
import ai.mack.sarvagyan.ui.components.EmptyState
import ai.mack.sarvagyan.ui.components.ErrorBanner
import ai.mack.sarvagyan.ui.components.SectionTitle
import ai.mack.sarvagyan.ui.theme.LocalCallColors
import kotlinx.coroutines.delay
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

data class DevicePhoneContact(val name: String, val number: String, val hash: String)

data class ContactSyncStats(
    val contactsRead: Int,
    val numbersRead: Int,
    val normalizedNumbers: Int,
    val failedNumbers: Int,
    val uniqueNumbers: Int,
    val contacts: List<DevicePhoneContact>,
)

fun normalizePhoneE164(raw: String, defaultCountryCode: String = "+91"): String? {
    val trimmed = raw.trim()
    if (trimmed.isEmpty()) return null
    var cleaned = trimmed.replace(Regex("[^0-9+]"), "")
    if (cleaned.startsWith("+")) {
        val digits = cleaned.substring(1).filter { it.isDigit() }
        return if (digits.length in 7..15) "+$digits" else null
    }
    if (cleaned.startsWith("00")) {
        val digits = cleaned.substring(2).filter { it.isDigit() }
        return if (digits.length in 7..15) "+$digits" else null
    }
    cleaned = cleaned.replace("+", "")
    if (cleaned.startsWith("0") && cleaned.length == 11) {
        val without0 = cleaned.substring(1)
        return "$defaultCountryCode$without0"
    }
    if (cleaned.length == 10) {
        return "$defaultCountryCode$cleaned"
    }
    if (cleaned.length == 12 && cleaned.startsWith("91")) {
        return "+$cleaned"
    }
    if (cleaned.length in 7..15) {
        return "$defaultCountryCode$cleaned"
    }
    return null
}

internal fun sha256Hex(s: String): String {
    val md = MessageDigest.getInstance("SHA-256")
    val bytes = md.digest(s.toByteArray(Charsets.UTF_8))
    return bytes.joinToString("") { "%02x".format(it) }
}

internal fun readDeviceContacts(context: Context): ContactSyncStats {
    val result = mutableListOf<DevicePhoneContact>()
    val seenHashes = mutableSetOf<String>()
    val seenContactIds = mutableSetOf<String>()
    var totalNumbers = 0
    var normalizedCount = 0
    var failedCount = 0

    try {
        val cr = context.contentResolver
        val cursor = cr.query(
            ContactsContract.CommonDataKinds.Phone.CONTENT_URI,
            arrayOf(
                ContactsContract.CommonDataKinds.Phone.CONTACT_ID,
                ContactsContract.CommonDataKinds.Phone.DISPLAY_NAME,
                ContactsContract.CommonDataKinds.Phone.NUMBER
            ),
            null, null,
            ContactsContract.CommonDataKinds.Phone.DISPLAY_NAME + " ASC"
        )
        cursor?.use { c ->
            val idIdx = c.getColumnIndex(ContactsContract.CommonDataKinds.Phone.CONTACT_ID)
            val nameIdx = c.getColumnIndex(ContactsContract.CommonDataKinds.Phone.DISPLAY_NAME)
            val numIdx = c.getColumnIndex(ContactsContract.CommonDataKinds.Phone.NUMBER)
            while (c.moveToNext()) {
                val contactId = if (idIdx >= 0) c.getString(idIdx) ?: "" else ""
                if (contactId.isNotEmpty()) seenContactIds.add(contactId)
                val name = if (nameIdx >= 0) c.getString(nameIdx) ?: "Contact" else "Contact"
                val num = if (numIdx >= 0) c.getString(numIdx) ?: "" else ""
                totalNumbers++
                val norm = normalizePhoneE164(num, "+91")
                if (norm != null) {
                    normalizedCount++
                    val hash = sha256Hex(norm)
                    if (seenHashes.add(hash)) {
                        result.add(DevicePhoneContact(name, norm, hash))
                    }
                } else {
                    failedCount++
                }
            }
        }
    } catch (e: Exception) {
        android.util.Log.e("ContactSync", "Error reading contacts: ${e.message}", e)
    }

    val contactsCount = if (seenContactIds.isNotEmpty()) seenContactIds.size else result.size
    android.util.Log.i(
        "ContactSync",
        "Contacts read: $contactsCount, numbers read: $totalNumbers, normalized: $normalizedCount, failed: $failedCount, unique: ${result.size}"
    )
    return ContactSyncStats(
        contactsRead = contactsCount,
        numbersRead = totalNumbers,
        normalizedNumbers = normalizedCount,
        failedNumbers = failedCount,
        uniqueNumbers = result.size,
        contacts = result
    )
}

internal suspend fun syncDeviceContactsWithServer(
    context: Context,
    api: ai.mack.sarvagyan.data.ApiClient,
    onProgress: (String) -> Unit = {}
): Pair<ContactSyncStats, List<MatchedContact>> {
    onProgress("Reading contacts…")
    val stats = readDeviceContacts(context)
    val list = stats.contacts
    val allMatches = mutableListOf<MatchedContact>()
    if (list.isNotEmpty()) {
        val chunks = list.chunked(100)
        var processed = 0
        chunks.forEach { chunk ->
            val hashes = chunk.map { it.hash }
            val res = api.matchPhones(hashes)
            allMatches.addAll(res.matches)
            processed += chunk.size
            onProgress("Synced $processed of ${list.size}")
        }
        android.util.Log.i(
            "ContactSync",
            "Sync completed. Contacts read: ${stats.contactsRead}, Numbers after normalization: ${stats.normalizedNumbers}, Unique numbers: ${stats.uniqueNumbers}, Matched: ${allMatches.size}, Failed: ${stats.failedNumbers}"
        )
    }
    return stats to allMatches
}

internal fun shareInvite(context: Context, contactName: String) {
    val sendIntent = Intent(Intent.ACTION_SEND).apply {
        type = "text/plain"
        putExtra(Intent.EXTRA_TEXT, "Join me on Sarvagyan for real-time multilingual voice translation! Web App: https://gnani-ai-internship-challenge.vercel.app")
    }
    context.startActivity(Intent.createChooser(sendIntent, "Invite $contactName to Sarvagyan").addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
}

@Composable
fun ContactsScreen(onBack: () -> Unit, onCallStarted: () -> Unit, onVoicemail: (String, String) -> Unit) {
    val context = LocalContext.current
    val c = context.container
    val scope = rememberCoroutineScope()
    val user by c.user.collectAsStateWithLifecycle()
    var tab by remember { mutableIntStateOf(0) } // 0: App contacts, 1: Discover from Phone
    var contacts by remember { mutableStateOf<List<ContactUser>?>(null) }
    var blocked by remember { mutableStateOf<List<ContactUser>>(emptyList()) }
    var username by remember { mutableStateOf("") }
    var manualPhone by remember { mutableStateOf("") }
    var findingPhone by remember { mutableStateOf(false) }
    var suggestions by remember { mutableStateOf<List<UserSearchResult>>(emptyList()) }
    var searching by remember { mutableStateOf(false) }
    var searchAttempted by remember { mutableStateOf(false) }
    var discoverQuery by remember { mutableStateOf("") }
    var error by remember { mutableStateOf<String?>(null) }
    var adding by remember { mutableStateOf(false) }
    val usernameFocus = remember { FocusRequester() }
    val phoneFocus = remember { FocusRequester() }
    val placeCall = rememberPlaceCall(onCallStarted)

    var hasContactPermission by remember {
        mutableStateOf(ContextCompat.checkSelfPermission(context, Manifest.permission.READ_CONTACTS) == PackageManager.PERMISSION_GRANTED)
    }
    var phoneContacts by remember { mutableStateOf<List<DevicePhoneContact>>(emptyList()) }
    var matchedUsers by remember { mutableStateOf<List<MatchedContact>>(emptyList()) }
    var syncingContacts by remember { mutableStateOf(false) }
    var syncProgress by remember { mutableStateOf<String?>(null) }

    fun mergeContact(added: ContactUser) {
        val current = contacts ?: emptyList()
        contacts = (current.filterNot { it.id == added.id } + added).sortedBy { it.name.lowercase() }
    }

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
    LaunchedEffect(Unit) {
        load()
        runCatching { c.api.me() }.onSuccess { c.user.value = it }
    }

    LaunchedEffect(username) {
        val clean = username.trim().removePrefix("@").trim()
        if (clean.isEmpty()) {
            suggestions = emptyList()
            searching = false
            searchAttempted = false
            return@LaunchedEffect
        }
        searching = true
        searchAttempted = false
        delay(300)
        try {
            suggestions = c.api.searchUsers(clean).users.take(10)
            searchAttempted = true
        } catch (_: ApiException) {
            suggestions = emptyList()
            searchAttempted = true
        } finally {
            searching = false
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
        if (granted) {
            syncPhone()
        } else {
            Toast.makeText(context, "Contacts permission was not granted.", Toast.LENGTH_SHORT).show()
        }
    }

    fun addPerson(targetUsername: String? = null, targetUserId: String? = null, clearInput: Boolean = false) {
        val clean = targetUsername?.trim()?.removePrefix("@")?.trim()?.takeIf { it.isNotEmpty() }
        if (clean == null && targetUserId.isNullOrBlank()) return
        adding = true
        scope.launch {
            try {
                val added = c.api.addContact(username = clean, userId = targetUserId)
                mergeContact(added)
                if (clearInput) {
                    username = ""
                    suggestions = emptyList()
                    searchAttempted = false
                }
                error = null
                load()
            } catch (e: ApiException) {
                error = e.message
            } finally {
                adding = false
            }
        }
    }

    fun add() {
        val name = username.trim().removePrefix("@").trim()
        if (name.isEmpty()) return
        addPerson(targetUsername = name, clearInput = true)
    }

    fun String.normFilter(): String = lowercase().replace(" ", "").replace("-", "")

    val phoneByHash = remember(phoneContacts) { phoneContacts.associate { it.hash to it.number } }
    val allMatched = remember(matchedUsers, phoneContacts, contacts) {
        val list = matchedUsers.toMutableList()
        val existingIds = list.map { it.id }.toSet()
        val existingHashes = list.mapNotNull { it.phoneHash }.toSet()

        // Match any device contacts against user's existing Sarvagyan contacts list by name or username
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

    val normQuery = remember(discoverQuery) { discoverQuery.normFilter() }
    val filteredMatched = remember(allMatched, phoneByHash, normQuery) {
        if (normQuery.isEmpty()) allMatched
        else allMatched.filter { m ->
            m.name.normFilter().contains(normQuery) ||
                (m.username?.normFilter()?.contains(normQuery) == true) ||
                (m.phoneHash?.let { phoneByHash[it]?.normFilter()?.contains(normQuery) } == true)
        }
    }
    val filteredUnmatched = remember(unmatched, normQuery) {
        if (normQuery.isEmpty()) unmatched
        else unmatched.filter { u ->
            u.name.normFilter().contains(normQuery) || u.number.normFilter().contains(normQuery)
        }
    }

    PostLoginBackground {
        Column(Modifier.fillMaxSize().statusBarsPadding().padding(top = 8.dp)) {
            Row(Modifier.fillMaxWidth().padding(horizontal = 4.dp, vertical = 4.dp), verticalAlignment = Alignment.CenterVertically) {
                IconButton(onClick = onBack) { Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "Back", tint = Brand.HighlightAccent) }
                Text("Contacts", style = MaterialTheme.typography.titleLarge, color = Brand.PrimaryText)
            }

            LazyColumn(
                modifier = Modifier.weight(1f).fillMaxWidth(),
                contentPadding = PaddingValues(horizontal = 20.dp, vertical = 8.dp),
            ) {
                item(key = "tabs") {
                    Row(
                        modifier = Modifier
                            .fillMaxWidth()
                            .clip(RoundedCornerShape(12.dp))
                            .background(MaterialTheme.colorScheme.surfaceVariant)
                            .padding(4.dp),
                        horizontalArrangement = Arrangement.spacedBy(4.dp),
                    ) {
                        listOf("My Contacts", "Discover from Phone").forEachIndexed { i, label ->
                            val selected = tab == i
                            Column(
                                modifier = Modifier
                                    .weight(1f)
                                    .clip(RoundedCornerShape(10.dp))
                                    .background(if (selected) MaterialTheme.colorScheme.primary else Color.Transparent)
                                    .clickable {
                                        tab = i
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
                    Spacer(Modifier.height(16.dp))
                }

                error?.let { err ->
                    item(key = "error") {
                        ErrorBanner(err, onDismiss = { error = null })
                        Spacer(Modifier.height(8.dp))
                    }
                }

                if (tab == 0) {
                    item(key = "add_by_username") {
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            OutlinedTextField(
                                username, { username = it.filter { ch -> ch.isLetterOrDigit() || ch == '_' || ch == '@' || ch == ' ' }.take(25) },
                                label = { Text("Add by @username") }, singleLine = true,
                                modifier = Modifier.weight(1f).focusRequester(usernameFocus),
                                keyboardOptions = KeyboardOptions(imeAction = ImeAction.Done), keyboardActions = KeyboardActions(onDone = { add() }),
                            )
                            Spacer(Modifier.width(8.dp))
                            IconButton(
                                onClick = { usernameFocus.requestFocus() },
                                enabled = username.isBlank() && !adding,
                            ) { Icon(Icons.Filled.PersonAdd, "Add contact") }
                        }
                        Spacer(Modifier.height(8.dp))
                        fun addByPhone() {
                            val norm = normalizePhoneE164(manualPhone, "+91")
                            if (norm == null) {
                                error = "Enter a valid phone number."
                                return
                            }
                            findingPhone = true
                            error = null
                            scope.launch {
                                try {
                                    val matches = c.api.matchPhones(listOf(sha256Hex(norm))).matches
                                    val found = matches.firstOrNull()
                                    if (found == null) {
                                        error = "No Sarvagyan user found with that phone number."
                                    } else {
                                        val added = c.api.addContact(userId = found.id)
                                        mergeContact(added)
                                        manualPhone = ""
                                    }
                                } catch (e: ApiException) {
                                    error = e.message
                                } finally {
                                    findingPhone = false
                                }
                            }
                        }
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            OutlinedTextField(
                                manualPhone,
                                { manualPhone = it.filter { ch -> ch.isDigit() || ch == '+' || ch == ' ' || ch == '-' }.take(20) },
                                label = { Text("Add by phone number") },
                                placeholder = { Text("Type phone number") },
                                singleLine = true,
                                modifier = Modifier.weight(1f).focusRequester(phoneFocus),
                                keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Phone, imeAction = ImeAction.Done),
                                keyboardActions = KeyboardActions(onDone = { addByPhone() }),
                            )
                            Spacer(Modifier.width(8.dp))
                            IconButton(
                                onClick = { phoneFocus.requestFocus() },
                                enabled = manualPhone.isBlank() && !findingPhone && !adding,
                            ) { Icon(Icons.Filled.PersonAdd, "Add by phone number") }
                        }
                    }

                    val cleanQuery = username.trim().removePrefix("@").trim()
                    if (cleanQuery.isNotEmpty()) {
                        item(key = "username_suggestions") {
                            Spacer(Modifier.height(8.dp))
                            when {
                                searching -> Text("Searching…", color = MaterialTheme.colorScheme.onSurfaceVariant, style = MaterialTheme.typography.bodyMedium)
                                suggestions.isEmpty() && searchAttempted -> Text("No user found", color = MaterialTheme.colorScheme.onSurfaceVariant, style = MaterialTheme.typography.bodyMedium)
                                suggestions.isNotEmpty() -> AppCard {
                                    suggestions.forEachIndexed { idx, s ->
                                        val isAdded = contacts?.any { it.id == s.id } == true
                                        Row(
                                            modifier = Modifier
                                                .fillMaxWidth()
                                                .then(
                                                    if (!isAdded && !adding) Modifier.clickable {
                                                        addPerson(targetUsername = s.username, targetUserId = s.id, clearInput = true)
                                                    } else Modifier
                                                )
                                                .padding(vertical = 8.dp),
                                            verticalAlignment = Alignment.CenterVertically,
                                        ) {
                                            Avatar(s.displayName, LocalCallColors.current.peer, 36.dp, avatar = s.avatar, useMain = false)
                                            Spacer(Modifier.width(12.dp))
                                            Column(Modifier.weight(1f)) {
                                                Text(s.displayName, style = MaterialTheme.typography.titleMedium)
                                                s.username?.let { Text("@$it", style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant) }
                                            }
                                            if (isAdded) {
                                                Text("Added", style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
                                            }
                                        }
                                        if (idx < suggestions.lastIndex) HorizontalDivider(color = MaterialTheme.colorScheme.outlineVariant)
                                    }
                                }
                            }
                        }
                    }

                    item(key = "your_contacts_header") { SectionTitle("Your contacts") }

                    val list = contacts
                    when {
                        list == null -> item(key = "loading") { Text("Loading…", color = MaterialTheme.colorScheme.onSurfaceVariant) }
                        list.isEmpty() -> item(key = "empty") {
                            EmptyState(Icons.Filled.People, "No contacts yet",
                                "Add people by their @username. Contacts can call you; others can't, unless you allow everyone below.")
                        }
                        else -> items(list, key = { "contact_${it.id}" }) { p ->
                            PersonRow(p, c.language(p.language)?.name ?: p.language,
                                onCall = { placeCall(p.id, p.name) },
                                onVoicemail = { onVoicemail(p.id, p.name) },
                                menu = listOf(
                                    "Remove from contacts" to { scope.launch { runCatching { c.api.removeContact(p.id) }; load() } },
                                    "Block" to { scope.launch { runCatching { c.api.block(p.id) }; load() } },
                                ))
                        }
                    }

                    item(key = "who_can_call_me") {
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
                            Text("My contacts: only people in your contacts list can call you. Everyone: anyone not blocked can call you.",
                                style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                        }
                    }

                    if (blocked.isNotEmpty()) {
                        item(key = "blocked_header") { SectionTitle("Blocked") }
                        items(blocked, key = { "blocked_${it.id}" }) { p ->
                            Row(Modifier.fillMaxWidth().padding(vertical = 4.dp), verticalAlignment = Alignment.CenterVertically) {
                                Avatar(p.name, MaterialTheme.colorScheme.onSurfaceVariant, 36.dp, avatar = p.avatar, useMain = false)
                                Spacer(Modifier.width(12.dp))
                                Text(p.name, Modifier.weight(1f))
                                TextButton(onClick = { scope.launch { runCatching { c.api.unblock(p.id) }; load() } }) { Text("Unblock") }
                            }
                        }
                    }
                } else {
                    if (!hasContactPermission) {
                        item(key = "discover_permission") {
                            AppCard {
                                Text("Discover Friends from Contacts", style = MaterialTheme.typography.titleMedium)
                                Spacer(Modifier.height(8.dp))
                                Text(
                                    "Sarvagyan securely discovers which of your phone contacts are registered on the platform without storing your contacts on our server. Phone numbers are hashed using SHA-256 directly on your device before matching.",
                                    style = MaterialTheme.typography.bodyMedium,
                                    color = MaterialTheme.colorScheme.onSurfaceVariant
                                )
                                Spacer(Modifier.height(16.dp))
                                PrimaryButton(
                                    "Sync Phone Contacts",
                                    onClick = { contactPermissionLauncher.launch(Manifest.permission.READ_CONTACTS) },
                                    modifier = Modifier.fillMaxWidth()
                                )
                            }
                        }
                    } else {
                        item(key = "discover_search_and_header") {
                            OutlinedTextField(
                                value = discoverQuery,
                                onValueChange = { discoverQuery = it },
                                label = { Text("Search name or phone number") },
                                singleLine = true,
                                leadingIcon = { Icon(Icons.Filled.Search, contentDescription = null) },
                                trailingIcon = {
                                    if (discoverQuery.isNotEmpty()) {
                                        IconButton(onClick = { discoverQuery = "" }) {
                                            Icon(Icons.Filled.Close, contentDescription = "Clear search")
                                        }
                                    }
                                },
                                modifier = Modifier.fillMaxWidth(),
                            )
                            Spacer(Modifier.height(12.dp))
                            Row(verticalAlignment = Alignment.CenterVertically) {
                                Text(
                                    "Device Contacts (${phoneContacts.size})",
                                    style = MaterialTheme.typography.titleMedium,
                                    modifier = Modifier.weight(1f)
                                )
                                IconButton(onClick = { syncPhone() }, enabled = !syncingContacts) {
                                    Icon(Icons.Filled.Refresh, "Refresh Contacts")
                                }
                            }
                            if (syncingContacts) {
                                syncProgress?.let {
                                    Text(it, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.primary, modifier = Modifier.padding(vertical = 4.dp))
                                }
                                LinearProgressIndicator(Modifier.fillMaxWidth().padding(vertical = 4.dp))
                            }
                            SectionTitle("On Sarvagyan (${filteredMatched.size})")
                        }

                        if (filteredMatched.isEmpty() && !syncingContacts) {
                            item(key = "matched_empty") {
                                EmptyState(
                                    Icons.Filled.People,
                                    if (normQuery.isNotEmpty()) "No matching contacts" else "None of your contacts found",
                                    if (normQuery.isNotEmpty()) "Try a different name or phone number." else "None of your phone contacts are on Sarvagyan yet. Send them an invite below!"
                                )
                            }
                        } else {
                            items(filteredMatched, key = { "matched_${it.id}_${it.phoneHash ?: ""}" }) { m ->
                                val isExistingContact = contacts?.any { it.id == m.id } == true
                                Row(
                                    Modifier.fillMaxWidth().padding(vertical = 6.dp),
                                    verticalAlignment = Alignment.CenterVertically
                                ) {
                                    Avatar(m.name, LocalCallColors.current.peer, 40.dp, avatar = m.avatar, useMain = false)
                                    Spacer(Modifier.width(12.dp))
                                    Column(Modifier.weight(1f)) {
                                        Text(m.name, style = MaterialTheme.typography.titleMedium)
                                        val sub = listOfNotNull(
                                            m.username?.let { "@$it" },
                                            c.language(m.language)?.name ?: m.language,
                                            if (isExistingContact) "In Contacts" else null
                                        ).joinToString(" · ")
                                        Text(sub, style = MaterialTheme.typography.bodyMedium, color = Brand.HighlightAccent)
                                    }
                                    IconButton(onClick = { onVoicemail(m.id, m.name) }) {
                                        Icon(Icons.Filled.Chat, "Chat with ${m.name}")
                                    }
                                    IconButton(onClick = { placeCall(m.id, m.name) }) {
                                        Icon(Icons.Filled.Call, "Call ${m.name}")
                                    }
                                    if (!isExistingContact) {
                                        IconButton(
                                            onClick = { addPerson(targetUsername = m.username, targetUserId = m.id) },
                                            enabled = !adding,
                                        ) {
                                            Icon(Icons.Filled.PersonAdd, "Add to contacts")
                                        }
                                    }
                                }
                            }
                        }

                        item(key = "invite_header") { SectionTitle("Invite to Sarvagyan (${filteredUnmatched.size})") }
                        if (filteredUnmatched.isEmpty() && !syncingContacts) {
                            item(key = "invite_empty") {
                                Text(
                                    if (normQuery.isNotEmpty()) "No matching contacts to invite." else "All your phone contacts are already on Sarvagyan!",
                                    color = MaterialTheme.colorScheme.onSurfaceVariant
                                )
                            }
                        } else {
                            items(filteredUnmatched, key = { "invite_${it.hash}" }) { u ->
                                Row(
                                    Modifier.fillMaxWidth().padding(vertical = 6.dp),
                                    verticalAlignment = Alignment.CenterVertically
                                ) {
                                    Avatar(u.name, MaterialTheme.colorScheme.surfaceVariant, 40.dp)
                                    Spacer(Modifier.width(12.dp))
                                    Column(Modifier.weight(1f)) {
                                        Text(u.name, style = MaterialTheme.typography.titleMedium)
                                        Text(u.number, style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
                                    }
                                    TextButton(onClick = { shareInvite(context, u.name) }) {
                                        Icon(Icons.Filled.Share, null, modifier = Modifier.size(16.dp))
                                        Spacer(Modifier.width(4.dp))
                                        Text("Invite")
                                    }
                                }
                            }
                        }
                    }
                }
                item(key = "bottom_spacer") { Spacer(Modifier.height(24.dp)) }
            }
        }
    }
}

@Composable
private fun PersonRow(p: ContactUser, language: String, onCall: () -> Unit, onVoicemail: () -> Unit, menu: List<Pair<String, () -> Unit>>) {
    var open by remember { mutableStateOf(false) }
    Row(Modifier.fillMaxWidth().padding(vertical = 6.dp), verticalAlignment = Alignment.CenterVertically) {
        Avatar(p.name, LocalCallColors.current.peer, 40.dp, avatar = p.avatar, useMain = false)
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
        if (busy) return
        busy = true
        scope.launch {
            try {
                c.answerIncoming()
                onAnswered()
            } catch (e: Exception) {
                if (e is kotlinx.coroutines.CancellationException) throw e
                val msg = (e as? ApiException)?.message ?: "Could not connect the call."
                Toast.makeText(context, msg, Toast.LENGTH_LONG).show()
                c.clearIncoming(call.callId)
            } finally {
                busy = false
            }
        }
    }
    val permission = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { ok ->
        if (ok) answer() else Toast.makeText(context, "Sarvagyan needs the microphone to answer.", Toast.LENGTH_LONG).show()
    }
    EmeraldAnimatedBackground {
        Column(Modifier.fillMaxSize().safeDrawingPadding().padding(32.dp), horizontalAlignment = Alignment.CenterHorizontally) {
            Spacer(Modifier.weight(1f))
            Avatar(call.fromName, LocalCallColors.current.peer, 112.dp, avatar = call.fromAvatar, useMain = true)
            Spacer(Modifier.height(24.dp))
            Text(call.fromName, style = MaterialTheme.typography.headlineMedium, textAlign = TextAlign.Center)
            call.fromUsername?.let { Text("@$it", color = MaterialTheme.colorScheme.onSurfaceVariant) }
            Spacer(Modifier.height(8.dp))
            val theirs = c.language(call.fromLanguage)?.name ?: call.fromLanguage
            val mine = c.language(c.effectiveMyLanguage())?.name ?: c.effectiveMyLanguage()
            Text(
                if (busy) "Connecting call…" else "Calling you · they speak $theirs, you'll hear $mine",
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                textAlign = TextAlign.Center,
            )
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
