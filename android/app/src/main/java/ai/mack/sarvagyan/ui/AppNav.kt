package ai.mack.sarvagyan.ui

import android.widget.Toast
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import ai.mack.sarvagyan.container
import androidx.compose.runtime.LaunchedEffect
import androidx.navigation.NavHostController
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.toRoute
import ai.mack.sarvagyan.ui.screens.ActiveCallScreen
import ai.mack.sarvagyan.ui.screens.AuthScreen
import ai.mack.sarvagyan.ui.screens.CallSetupScreen
import ai.mack.sarvagyan.ui.screens.CallSummaryScreen
import ai.mack.sarvagyan.ui.screens.ChooseAvatarScreen
import ai.mack.sarvagyan.ui.screens.ContactsScreen
import ai.mack.sarvagyan.ui.screens.IncomingCallScreen
import ai.mack.sarvagyan.ui.screens.ChatConversationScreen
import ai.mack.sarvagyan.ui.screens.GlobalChatScreen
import ai.mack.sarvagyan.ui.screens.HelpScreen
import ai.mack.sarvagyan.ui.screens.HomeScreen
import ai.mack.sarvagyan.ui.screens.LanguageScreen
import ai.mack.sarvagyan.ui.screens.OnboardingScreen
import ai.mack.sarvagyan.ui.screens.SettingsScreen
import ai.mack.sarvagyan.ui.screens.PrivacyPolicyScreen
import ai.mack.sarvagyan.ui.screens.SplashScreen
import kotlinx.coroutines.launch
import kotlinx.serialization.Serializable

object Routes {
    @Serializable data object Splash
    @Serializable data object Onboarding
    @Serializable data object Auth
    @Serializable data class ChooseAvatar(val onboarding: Boolean = false)
    @Serializable data object Home
    @Serializable data object Languages
    @Serializable data class CallSetup(val join: Boolean, val code: String? = null)
    @Serializable data object ActiveCall
    @Serializable data class Summary(val callId: String)
    @Serializable data object Settings
    @Serializable data class SettingsPage(val group: String)
    @Serializable data object PrivacyPolicy
    @Serializable data object Help
    @Serializable data object Contacts
    @Serializable data class Voicemail(val tab: Int = 0)
    @Serializable data class ChatConversation(val conversationId: String, val voicemail: Boolean = false)
}

@Composable
fun AppNav(
    nav: NavHostController,
    pendingJoinCode: String?,
    onJoinCodeConsumed: () -> Unit,
    pendingConversationId: String? = null,
    onConversationConsumed: () -> Unit = {},
) {
    val container = LocalContext.current.container
    val incoming by container.incomingCall.collectAsStateWithLifecycle()
    Box(Modifier.fillMaxSize()) {
        Screens(nav, pendingJoinCode, onJoinCodeConsumed, pendingConversationId, onConversationConsumed)
        // someone is calling: the ringing screen covers whatever is open
        incoming?.let { call ->
            IncomingCallScreen(call, onAnswered = {
                nav.navigate(Routes.ActiveCall) { launchSingleTop = true }
                container.clearIncoming(call.callId)
            })
        }
    }
}

@Composable
private fun Screens(
    nav: NavHostController,
    pendingJoinCode: String?,
    onJoinCodeConsumed: () -> Unit,
    pendingConversationId: String?,
    onConversationConsumed: () -> Unit,
) {
    val context = LocalContext.current
    val c = context.container
    val scope = rememberCoroutineScope()
    fun openChatWithUser(userId: String, voicemail: Boolean = false) {
        scope.launch {
            try {
                val res = c.api.directChat(userId = userId)
                nav.navigate(Routes.ChatConversation(res.conversation.id, voicemail = voicemail))
            } catch (e: Exception) {
                Toast.makeText(context, e.message ?: "Could not open chat.", Toast.LENGTH_SHORT).show()
            }
        }
    }
    NavHost(nav, startDestination = Routes.Splash) {
        composable<Routes.Splash> {
            SplashScreen(onDone = { dest ->
                nav.navigate(dest) { popUpTo(Routes.Splash) { inclusive = true } }
            })
        }
        composable<Routes.Onboarding> {
            OnboardingScreen(onFinish = { nav.navigate(Routes.Auth) { popUpTo(Routes.Onboarding) { inclusive = true } } })
        }
        composable<Routes.Auth> {
            AuthScreen(onSignedIn = { isNew ->
                val dest: Any = if (isNew) Routes.ChooseAvatar(onboarding = true) else Routes.Home
                nav.navigate(dest) { popUpTo(Routes.Auth) { inclusive = true } }
            })
        }
        composable<Routes.ChooseAvatar> { entry ->
            val args = entry.toRoute<Routes.ChooseAvatar>()
            ChooseAvatarScreen(
                isOnboarding = args.onboarding,
                onDone = {
                    if (args.onboarding) {
                        nav.navigate(Routes.Home) { popUpTo(0) }
                    } else {
                        nav.popBackStack()
                    }
                },
            )
        }
        composable<Routes.Home> {
            LaunchedEffect(pendingJoinCode, pendingConversationId) {
                if (pendingJoinCode != null) {
                    nav.navigate(Routes.CallSetup(join = true, code = pendingJoinCode))
                    onJoinCodeConsumed()
                } else if (pendingConversationId != null) {
                    nav.navigate(Routes.ChatConversation(pendingConversationId))
                    onConversationConsumed()
                }
            }
            HomeScreen(
                onStartCall = { nav.navigate(Routes.CallSetup(join = false)) },
                onJoin = { code -> nav.navigate(Routes.CallSetup(join = true, code = code)) },
                onLanguages = { nav.navigate(Routes.Languages) },
                onSettings = { nav.navigate(Routes.Settings) },
                onHelp = { nav.navigate(Routes.Help) },
                onResumeCall = { nav.navigate(Routes.ActiveCall) },
                onVoicemail = { nav.navigate(Routes.Voicemail()) },
                onContacts = { nav.navigate(Routes.Contacts) },
                onRecordVoicemail = { id, _ -> openChatWithUser(id) },
                onSignedOut = { nav.navigate(Routes.Auth) { popUpTo(Routes.Home) { inclusive = true } } },
            )
        }
        composable<Routes.Languages> { LanguageScreen(onBack = { nav.popBackStack() }) }
        composable<Routes.CallSetup> { entry ->
            val args = entry.toRoute<Routes.CallSetup>()
            CallSetupScreen(
                join = args.join, initialCode = args.code,
                onBack = { nav.popBackStack() },
                onLanguages = { nav.navigate(Routes.Languages) },
                onStarted = { nav.navigate(Routes.ActiveCall) { popUpTo(Routes.Home) } },
            )
        }
        composable<Routes.ActiveCall> {
            ActiveCallScreen(
                onFinished = { callId -> nav.navigate(Routes.Summary(callId)) { popUpTo(Routes.Home) } },
                onLeaveScreen = { nav.popBackStack(Routes.Home, inclusive = false) },
                onVoicemail = { id, _ -> nav.popBackStack(Routes.Home, inclusive = false); openChatWithUser(id, voicemail = true) },
            )
        }
        composable<Routes.Contacts> {
            ContactsScreen(
                onBack = { nav.popBackStack() },
                onCallStarted = { nav.navigate(Routes.ActiveCall) },
                onVoicemail = { id, _ -> openChatWithUser(id) },
            )
        }
        composable<Routes.Summary> { entry ->
            CallSummaryScreen(
                callId = entry.toRoute<Routes.Summary>().callId,
                onNewCall = { nav.navigate(Routes.CallSetup(join = false)) { popUpTo(Routes.Home) } },
                onHome = { nav.popBackStack(Routes.Home, inclusive = false) },
            )
        }
        composable<Routes.Settings> { SettingsPageFor(nav, null) }
        composable<Routes.SettingsPage> { entry -> SettingsPageFor(nav, entry.toRoute<Routes.SettingsPage>().group) }
        composable<Routes.PrivacyPolicy> { PrivacyPolicyScreen(onBack = { nav.popBackStack() }) }
        composable<Routes.Help> { HelpScreen(onBack = { nav.popBackStack() }) }
        composable<Routes.Voicemail> { entry ->
            GlobalChatScreen(
                initialTab = entry.toRoute<Routes.Voicemail>().tab,
                onBack = { nav.popBackStack() },
                onOpenConversation = { cid -> nav.navigate(Routes.ChatConversation(cid)) },
            )
        }
        composable<Routes.ChatConversation> { entry ->
            val args = entry.toRoute<Routes.ChatConversation>()
            ChatConversationScreen(
                conversationId = args.conversationId,
                isVoicemail = args.voicemail,
                onBack = { nav.popBackStack() },
            )
        }
    }
}

@Composable
private fun SettingsPageFor(nav: NavHostController, group: String?) {
    SettingsScreen(
        group = group,
        onBack = { nav.popBackStack() },
        onOpenGroup = { nav.navigate(Routes.SettingsPage(it)) },
        onLanguages = { nav.navigate(Routes.Languages) },
        onHelp = { nav.navigate(Routes.Help) },
        onSignedOut = { nav.navigate(Routes.Auth) { popUpTo(0) } },
        onContacts = { nav.navigate(Routes.Contacts) },
        onPrivacyPolicy = { nav.navigate(Routes.PrivacyPolicy) },
        onChooseAvatar = { nav.navigate(Routes.ChooseAvatar(onboarding = false)) },
    )
}
