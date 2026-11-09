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
        Column(
            Modifier.fillMaxSize().padding(24.dp),
            verticalArrangement = Arrangement.Center, horizontalAlignment = Alignment.CenterHorizontally,
        ) {
            Box(Modifier.graphicsLayer { scaleX = logoScale.value; scaleY = logoScale.value; alpha = logoAlpha.value }) {
                LogoMark(140.dp)
            }
            Spacer(Modifier.height(24.dp))
            Text("Sarvagyan", style = MaterialTheme.typography.displaySmall, color = Brand.TextHi, modifier = rise)
            Spacer(Modifier.height(20.dp))
            AnimatedContent(words[word], transitionSpec = { fadeIn(tween(250)) togetherWith fadeOut(tween(250)) }, label = "word",
                modifier = rise) {
                Text(it, style = MaterialTheme.typography.titleLarge, color = Brand.TextMid)
            }
            Spacer(Modifier.height(12.dp))
            Text("Speak Naturally. Understand Everyone.", style = MaterialTheme.typography.bodyLarge, color = Brand.TextMid, modifier = rise)
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
fun AuthScreen(onSignedIn: () -> Unit) {
    val c = LocalContext.current.container
    val scope = rememberCoroutineScope()
    var tab by remember { mutableIntStateOf(0) } // 0 sign in, 1 create account
    var email by remember { mutableStateOf("") }
    var password by remember { mutableStateOf("") }
    var name by remember { mutableStateOf("") }
    var guestName by remember { mutableStateOf("") }
    var busy by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf<String?>(null) }
    var showServer by remember { mutableStateOf(false) }
    var server by remember { mutableStateOf(c.settings.value.serverUrl) }

    fun run(block: suspend () -> ai.mack.sarvagyan.data.Session) {
        busy = true
        error = null
        scope.launch {
            try {
                if (server != c.settings.value.serverUrl) c.settingsStore.update { it.copy(serverUrl = server) }
                val session = block()
                c.saveSession(session)
                c.refreshLanguages()
                onSignedIn()
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
        }
        OutlinedTextField(email, { email = it.trim() }, label = { Text("Email") }, singleLine = true, modifier = Modifier.fillMaxWidth(),
            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Email))
        Spacer(Modifier.height(8.dp))
        OutlinedTextField(password, { password = it }, label = { Text(if (tab == 1) "Password (8+ characters)" else "Password") }, singleLine = true,
            visualTransformation = PasswordVisualTransformation(), modifier = Modifier.fillMaxWidth(),
            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Password))
        error?.let { Spacer(Modifier.height(12.dp)); ErrorBanner(it) }
        Spacer(Modifier.height(16.dp))
        PrimaryButton(
            if (tab == 0) "Sign in" else "Create account",
            onClick = { if (tab == 0) run { c.api.login(email, password) } else run { c.api.register(email, password, name.ifBlank { email.substringBefore('@') }) } },
            enabled = email.contains('@') && password.length >= (if (tab == 1) 8 else 1) && (tab == 0 || name.isNotBlank()),
            loading = busy, modifier = Modifier.fillMaxWidth(),
        )
        Spacer(Modifier.height(28.dp))
        Text("Hackathon demo mode", style = MaterialTheme.typography.titleMedium)
        Text("Try it without an account. Guest accounts are marked as demo users.", style = MaterialTheme.typography.bodyMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant)
        Spacer(Modifier.height(8.dp))
        OutlinedTextField(guestName, { guestName = it }, label = { Text("Name shown to the other person") }, singleLine = true, modifier = Modifier.fillMaxWidth())
        Spacer(Modifier.height(8.dp))
        SecondaryButton("Continue as guest (demo)", { run { c.api.demo(guestName.ifBlank { "Guest" }) } }, Modifier.fillMaxWidth(), enabled = !busy)
        Spacer(Modifier.height(20.dp))
        TextButton(onClick = { showServer = !showServer }) { Text(if (showServer) "Hide server settings" else "Server settings") }
        if (showServer) {
            OutlinedTextField(server, { server = it.trim() }, label = { Text("Server URL") }, singleLine = true, modifier = Modifier.fillMaxWidth(),
                supportingText = { Text("Use https:// in production. Emulator → your PC: http://10.0.2.2:8787") })
        }
        Spacer(Modifier.width(1.dp))
    }
}
