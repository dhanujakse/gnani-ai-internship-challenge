package ai.mack.sarvagyan.ui.screens

import androidx.compose.animation.core.Animatable
import androidx.compose.animation.core.FastOutSlowInEasing
import androidx.compose.animation.core.Spring
import androidx.compose.animation.core.spring
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.animation.AnimatedContent
import androidx.compose.animation.core.tween
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.togetherWith
import androidx.compose.foundation.BorderStroke
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.safeDrawingPadding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.pager.HorizontalPager
import androidx.compose.foundation.pager.rememberPagerState
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Call
import androidx.compose.material.icons.filled.Language
import androidx.compose.material.icons.filled.RecordVoiceOver
import androidx.compose.material.icons.filled.ArrowDropDown
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.OutlinedCard
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.sp
import ai.mack.sarvagyan.R
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import ai.mack.sarvagyan.data.Language
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.SegmentedButton
import androidx.compose.material3.SegmentedButtonDefaults
import androidx.compose.material3.SingleChoiceSegmentedButtonRow
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
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import ai.mack.sarvagyan.container
import ai.mack.sarvagyan.data.ApiException
import ai.mack.sarvagyan.ui.Routes
import ai.mack.sarvagyan.ui.components.EmeraldAnimatedBackground
import ai.mack.sarvagyan.ui.components.ErrorBanner
import ai.mack.sarvagyan.ui.components.LogoMark
import ai.mack.sarvagyan.ui.components.PrimaryButton
import ai.mack.sarvagyan.ui.components.SecondaryButton
import ai.mack.sarvagyan.ui.theme.Brand
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch

@Composable
fun SplashScreen(onDone: (Any) -> Unit) {
    val c = LocalContext.current.container
    var word by remember { mutableIntStateOf(0) }
    val words = listOf("வணக்கம்", "Hello", "नमस्ते", "Hello")
    // the logo pops in (grows with a small bounce), then the name and tagline fade up beneath it
    val logoScale = remember { Animatable(0.3f) }
    val logoAlpha = remember { Animatable(0f) }
    val textIn = remember { Animatable(0f) }
    LaunchedEffect(Unit) {
        launch { logoAlpha.animateTo(1f, tween(300)) }
        logoScale.animateTo(1f, spring(dampingRatio = 0.45f, stiffness = Spring.StiffnessLow))
    }
    LaunchedEffect(Unit) {
        delay(450)
        textIn.animateTo(1f, tween(500, easing = FastOutSlowInEasing))
    }
    val rise = Modifier.graphicsLayer { alpha = textIn.value; translationY = (1f - textIn.value) * 40f }
    LaunchedEffect(Unit) {
        val started = System.currentTimeMillis()
        launch { while (true) { delay(450); word = (word + 1) % words.size } }
        val s = c.settingsStore.current()
        val dest: Any = when {
            !s.onboarded -> Routes.Onboarding
            c.tokens.get() == null -> Routes.Auth
            else -> runCatching { c.api.me() }.fold(
                onSuccess = { c.user.value = it; Routes.Home },
                onFailure = { if ((it as? ApiException)?.isAuth == true) { c.signOut(); Routes.Auth } else Routes.Home }, // offline: still enter
            )
        }
        launch { c.refreshLanguages() }
        delay((1900 - (System.currentTimeMillis() - started)).coerceAtLeast(0)) // long enough to see the logo
        onDone(dest)
    }
    EmeraldAnimatedBackground {
        // Reference design: Subtle mandala-inspired decorative pattern at top
        Image(
            painter = painterResource(R.drawable.bg_mandala_top),
            contentDescription = null,
            contentScale = ContentScale.FillWidth,
            modifier = Modifier
                .align(Alignment.TopCenter)
                .fillMaxWidth()
                .alpha(0.85f)
        )

        // Reference design: Heritage skyline & colourful flowing curves at bottom
        Image(
            painter = painterResource(R.drawable.bg_splash_heritage),
            contentDescription = null,
            contentScale = ContentScale.FillWidth,
            modifier = Modifier
                .align(Alignment.BottomCenter)
                .fillMaxWidth()
                .alpha(0.95f)
        )

        Column(
            Modifier.fillMaxSize().padding(horizontal = 24.dp),
            verticalArrangement = Arrangement.Center,
            horizontalAlignment = Alignment.CenterHorizontally,
        ) {
            Box(Modifier.graphicsLayer { scaleX = logoScale.value; scaleY = logoScale.value; alpha = logoAlpha.value }) {
                LogoMark(140.dp)
            }
            Spacer(Modifier.height(24.dp))
            Text(
                "Sarvagyan",
                style = MaterialTheme.typography.displaySmall.copy(fontWeight = FontWeight.Bold, letterSpacing = 0.5.sp),
                color = Brand.IvoryWhite,
                modifier = rise
            )
            Spacer(Modifier.height(16.dp))
            AnimatedContent(
                words[word],
                transitionSpec = { fadeIn(tween(250)) togetherWith fadeOut(tween(250)) },
                label = "word",
                modifier = rise
            ) {
                Text(it, style = MaterialTheme.typography.titleLarge, color = Brand.MintGreen)
            }
            Spacer(Modifier.height(12.dp))
            Text(
                "Speak Naturally. Understand Everyone.",
                style = MaterialTheme.typography.bodyLarge.copy(fontWeight = FontWeight.Medium),
                color = Brand.IvoryWhite,
                textAlign = TextAlign.Center,
                modifier = rise
            )
        }
    }
}

private data class Step(val icon: ImageVector, val title: String, val body: String)

private val steps = listOf(
    Step(Icons.Filled.Language, "1. Choose your language", "Pick the language you speak. Sarvagyan supports Tamil and English first, plus 8 more Indian languages."),
    Step(Icons.Filled.Call, "2. Start a call", "Create a call and share the invitation code, or join a friend's call with theirs."),
    Step(Icons.Filled.RecordVoiceOver, "3. Understand each other instantly", "Just talk. They hear you in their language and read live subtitles — and you hear their reply in yours."),
)

@Composable
fun OnboardingScreen(onFinish: () -> Unit) {
    val c = LocalContext.current.container
    val scope = rememberCoroutineScope()
    val pager = rememberPagerState(pageCount = { steps.size })
    val finish: () -> Unit = { scope.launch { c.settingsStore.update { it.copy(onboarded = true) }; onFinish() } }
    Column(Modifier.fillMaxSize().safeDrawingPadding().padding(24.dp)) {
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.End) {
            TextButton(onClick = finish) { Text("Skip") }
        }
        HorizontalPager(pager, Modifier.weight(1f)) { page ->
            val s = steps[page]
            Column(Modifier.fillMaxSize(), verticalArrangement = Arrangement.Center, horizontalAlignment = Alignment.CenterHorizontally) {
                Box(Modifier.size(120.dp).clip(CircleShape).background(MaterialTheme.colorScheme.secondaryContainer), contentAlignment = Alignment.Center) {
                    Icon(s.icon, contentDescription = null, tint = MaterialTheme.colorScheme.secondary, modifier = Modifier.size(56.dp))
                }
                Spacer(Modifier.height(32.dp))
                Text(s.title, style = MaterialTheme.typography.headlineSmall, textAlign = TextAlign.Center)
                Spacer(Modifier.height(12.dp))
                Text(s.body, style = MaterialTheme.typography.bodyLarge, textAlign = TextAlign.Center, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
        }
        Row(
            Modifier.fillMaxWidth().padding(vertical = 16.dp).semantics { contentDescription = "Step ${pager.currentPage + 1} of ${steps.size}" },
            horizontalArrangement = Arrangement.Center,
        ) {
            repeat(steps.size) { i ->
                Box(Modifier.padding(4.dp).size(if (i == pager.currentPage) 22.dp else 8.dp, 8.dp).clip(CircleShape)
                    .background(if (i == pager.currentPage) MaterialTheme.colorScheme.secondary else MaterialTheme.colorScheme.outline))
            }
        }
        if (pager.currentPage == steps.lastIndex) {
            PrimaryButton("Get Started", finish, Modifier.fillMaxWidth())
        } else {
            PrimaryButton("Next", { scope.launch { pager.animateScrollToPage(pager.currentPage + 1) } }, Modifier.fillMaxWidth())
        }
    }
}

@Composable
private fun LanguagePickerField(
    title: String = "Which language do you speak?",
    languages: List<Language>,
    selectedCode: String?,
    onSelect: (String) -> Unit
) {
    var expanded by remember { mutableStateOf(false) }
    val selectedLang = languages.firstOrNull { it.code == selectedCode }
    Column(Modifier.fillMaxWidth().padding(vertical = 4.dp)) {
        Text(title, style = MaterialTheme.typography.titleSmall)
        Spacer(Modifier.height(4.dp))
        OutlinedCard(
            onClick = { expanded = true },
            modifier = Modifier.fillMaxWidth(),
            colors = CardDefaults.outlinedCardColors(
                containerColor = Brand.CardBg,
            ),
            border = BorderStroke(
                width = if (selectedCode != null) 1.5.dp else 1.dp,
                color = if (selectedCode != null) Brand.SelectedBorder else Brand.Borders,
            ),
        ) {
            Row(
                Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 14.dp),
                verticalAlignment = Alignment.CenterVertically
            ) {
                Icon(
                    Icons.Filled.Language,
                    null,
                    tint = if (selectedCode != null) Brand.SelectedBorder else Brand.SecondaryText,
                )
                Spacer(Modifier.width(12.dp))
                Text(
                    text = if (selectedLang != null) "${selectedLang.native} · ${selectedLang.name}" else "Select your language…",
                    style = MaterialTheme.typography.bodyLarge,
                    color = if (selectedCode != null) Brand.PrimaryText else Brand.SecondaryText,
                    modifier = Modifier.weight(1f)
                )
                Icon(Icons.Filled.ArrowDropDown, null, tint = Brand.SecondaryText)
            }
        }
        DropdownMenu(expanded = expanded, onDismissRequest = { expanded = false }) {
            languages.forEach { l ->
                DropdownMenuItem(
                    text = { Text("${l.native} · ${l.name}") },
                    onClick = {
                        onSelect(l.code)
                        expanded = false
                    }
                )
            }
        }
    }
}

@Composable
fun AuthScreen(onSignedIn: (isNewAccount: Boolean) -> Unit) {
    val c = LocalContext.current.container
    val scope = rememberCoroutineScope()
    val supportedLanguages by c.languages.collectAsStateWithLifecycle()
    var tab by remember { mutableIntStateOf(0) } // 0 sign in, 1 create account
    var email by remember { mutableStateOf("") }
    var password by remember { mutableStateOf("") }
    var name by remember { mutableStateOf("") }
    var username by remember { mutableStateOf("") }
    var usernameStatus by remember { mutableStateOf<String?>(null) }
    var usernameAvailable by remember { mutableStateOf(false) }
    var checkingUsername by remember { mutableStateOf(false) }
    var accountLanguage by remember { mutableStateOf<String?>(null) }
    var phone by remember { mutableStateOf("") }
    var busy by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf<String?>(null) }
    var showServer by remember { mutableStateOf(false) }
    var server by remember { mutableStateOf(c.settings.value.serverUrl) }

    LaunchedEffect(server) {
        c.refreshLanguages()
    }

    LaunchedEffect(username) {
        val u = username.trim().removePrefix("@")
        if (u.isEmpty()) {
            usernameStatus = null
            usernameAvailable = false
            return@LaunchedEffect
        }
        if (u.length < 3) {
            usernameStatus = "At least 3 characters needed"
            usernameAvailable = false
            return@LaunchedEffect
        }
        if (!u.all { it.isLetterOrDigit() || it == '_' }) {
            usernameStatus = "Letters, numbers, and underscores only"
            usernameAvailable = false
            return@LaunchedEffect
        }
        delay(400)
        checkingUsername = true
        try {
            val res = c.api.checkUsername(u)
            usernameAvailable = res.available
            usernameStatus = if (res.available) "✓ Username is available" else (res.reason ?: "This username is already taken. Please choose another username.")
        } catch (_: Exception) {
            usernameStatus = null
            usernameAvailable = false
        } finally {
            checkingUsername = false
        }
    }

    fun run(isNewAccount: Boolean, block: suspend () -> ai.mack.sarvagyan.data.Session) {
        busy = true
        error = null
        scope.launch {
            try {
                if (server != c.settings.value.serverUrl) c.settingsStore.update { it.copy(serverUrl = server) }
                val session = block()
                c.saveSession(session)
                c.refreshLanguages()
                onSignedIn(isNewAccount)
            } catch (e: ApiException) {
                error = e.message
            } finally {
                busy = false
            }
        }
    }

    Column(Modifier.fillMaxSize().safeDrawingPadding().imePadding().verticalScroll(rememberScrollState()).padding(24.dp)) {
        Spacer(Modifier.height(24.dp))
        LogoMark(64.dp, animated = false)
        Spacer(Modifier.height(16.dp))
        Text("Welcome to Sarvagyan", style = MaterialTheme.typography.headlineMedium)
        Text("Sign in to start translated calls.", color = MaterialTheme.colorScheme.onSurfaceVariant)
        Spacer(Modifier.height(24.dp))
        SingleChoiceSegmentedButtonRow(Modifier.fillMaxWidth()) {
            listOf("Sign in", "Create account").forEachIndexed { i, label ->
                SegmentedButton(selected = tab == i, onClick = { tab = i; error = null }, shape = SegmentedButtonDefaults.itemShape(i, 2)) { Text(label) }
            }
        }
        Spacer(Modifier.height(16.dp))
        if (tab == 1) {
            OutlinedTextField(name, { name = it }, label = { Text("Your name") }, singleLine = true, modifier = Modifier.fillMaxWidth())
            Spacer(Modifier.height(8.dp))
            OutlinedTextField(
                value = username,
                onValueChange = { username = it.trim().lowercase() },
                label = { Text("Unique username") },
                prefix = { Text("@") },
                singleLine = true,
                isError = usernameStatus != null && !usernameAvailable && !checkingUsername,
                supportingText = {
                    if (checkingUsername) {
                        Text("Checking availability...", color = MaterialTheme.colorScheme.onSurfaceVariant)
                    } else if (usernameStatus != null) {
                        Text(
                            usernameStatus!!,
                            color = if (usernameAvailable) Brand.HighlightAccent else MaterialTheme.colorScheme.error
                        )
                    } else {
                        Text("3-30 letters, numbers, or underscores")
                    }
                },
                modifier = Modifier.fillMaxWidth()
            )
            Spacer(Modifier.height(8.dp))
            LanguagePickerField(
                title = "Which language do you speak?",
                languages = supportedLanguages,
                selectedCode = accountLanguage,
                onSelect = { accountLanguage = it }
            )
            Spacer(Modifier.height(8.dp))
            OutlinedTextField(
                value = phone,
                onValueChange = { phone = it.filter { ch -> ch.isDigit() || ch == '+' || ch == ' ' || ch == '-' }.take(20) },
                label = { Text("Phone number") },
                placeholder = { Text("Type your number") },
                singleLine = true,
                keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Phone),
                modifier = Modifier.fillMaxWidth()
            )
            Spacer(Modifier.height(8.dp))
        }
        OutlinedTextField(email, { email = it.trim() }, label = { Text("Email") }, singleLine = true, modifier = Modifier.fillMaxWidth(),
            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Email))
        Spacer(Modifier.height(8.dp))
        OutlinedTextField(password, { password = it }, label = { Text(if (tab == 1) "Password (8+ characters)" else "Password") }, singleLine = true,
            visualTransformation = PasswordVisualTransformation(), modifier = Modifier.fillMaxWidth(),
            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Password))
        error?.let { Spacer(Modifier.height(12.dp)); ErrorBanner(it) }
        Spacer(Modifier.height(16.dp))
        val canSubmit = if (tab == 0) {
            email.contains('@') && password.length >= 1
        } else {
            email.contains('@') && password.length >= 8 && name.isNotBlank() && usernameAvailable && !checkingUsername && accountLanguage != null
        }
        PrimaryButton(
            if (tab == 0) "Sign in" else "Create account",
            onClick = {
                if (tab == 0) {
                    run(false) { c.api.login(email, password) }
                } else {
                    val cleanUsername = username.trim().removePrefix("@")
                    val chosen = accountLanguage!!
                    val phoneHash = phone.takeIf { it.isNotBlank() }?.let { normalizePhoneE164(it, "+91") }?.let { sha256Hex(it) }
                    run(true) {
                        val sess = c.api.register(email, password, name.ifBlank { email.substringBefore('@') }, cleanUsername, language = chosen, phoneHash = phoneHash)
                        c.settingsStore.update { it.copy(myLanguage = chosen) }
                        sess
                    }
                }
            },
            enabled = canSubmit,
            loading = busy, modifier = Modifier.fillMaxWidth(),
        )
        Spacer(Modifier.height(20.dp))
        TextButton(onClick = { showServer = !showServer }) { Text(if (showServer) "Hide server settings" else "Server settings") }
        if (showServer) {
            OutlinedTextField(server, { server = it.trim() }, label = { Text("Server URL") }, singleLine = true, modifier = Modifier.fillMaxWidth(),
                supportingText = { Text("Use https:// in production. Emulator → your PC: http://10.0.2.2:8787") })
        }
        Spacer(Modifier.width(1.dp))
    }
}
