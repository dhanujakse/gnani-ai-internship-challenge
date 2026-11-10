package ai.mack.sarvagyan.ui

import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
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
import ai.mack.sarvagyan.ui.screens.ContactsScreen
import ai.mack.sarvagyan.ui.screens.IncomingCallScreen
import ai.mack.sarvagyan.ui.screens.ChatConversationScreen
import ai.mack.sarvagyan.ui.screens.GlobalChatScreen
import ai.mack.sarvagyan.ui.screens.HelpScreen
import ai.mack.sarvagyan.ui.screens.HomeScreen
import ai.mack.sarvagyan.ui.screens.LanguageScreen
import ai.mack.sarvagyan.ui.screens.OnboardingScreen
import ai.mack.sarvagyan.ui.screens.RecordVoicemailScreen
import ai.mack.sarvagyan.ui.screens.SettingsScreen
import ai.mack.sarvagyan.ui.screens.PrivacyPolicyScreen
import ai.mack.sarvagyan.ui.screens.SplashScreen
import ai.mack.sarvagyan.ui.screens.VoicemailScreen
import kotlinx.serialization.Serializable

object Routes {
    @Serializable data object Splash
    @Serializable data object Onboarding
    @Serializable data object Auth
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
    @Serializable data class RecordVoicemail(val toId: String? = null, val toName: String? = null)
    @Serializable data class ChatConversation(val conversationId: String)
}

@Composable
fun AppNav(nav: NavHostController, pendingJoinCode: String?, onJoinCodeConsumed: () -> Unit) {
    val incoming by LocalContext.current.container.incomingCall.collectAsStateWithLifecycle()
    Box(Modifier.fillMaxSize()) {
        Screens(nav, pendingJoinCode, onJoinCodeConsumed)
        // someone is calling: the ringing screen covers whatever is open
        incoming?.let { call -> IncomingCallScreen(call, onAnswered = { nav.navigate(Routes.ActiveCall) }) }
    }
}

@Composable
private fun Screens(nav: NavHostController, pendingJoinCode: String?, onJoinCodeConsumed: () -> Unit) {
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
            AuthScreen(onSignedIn = { nav.navigate(Routes.Home) { popUpTo(Routes.Auth) { inclusive = true } } })
        }
        composable<Routes.Home> {
            LaunchedEffect(pendingJoinCode) {
                if (pendingJoinCode != null) {
                    nav.navigate(Routes.CallSetup(join = true, code = pendingJoinCode))
                    onJoinCodeConsumed()
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
                onRecordVoicemail = { id, name -> nav.navigate(Routes.RecordVoicemail(id, name)) },
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
                onVoicemail = { id, name -> nav.navigate(Routes.RecordVoicemail(id, name)) { popUpTo(Routes.Home) } },
            )
        }
        composable<Routes.Contacts> {
            ContactsScreen(
                onBack = { nav.popBackStack() },
                onCallStarted = { nav.navigate(Routes.ActiveCall) },
                onVoicemail = { id, name -> nav.navigate(Routes.RecordVoicemail(id, name)) },
            )
        }
        composable<Routes.Summary> { entry ->
            CallSummaryScreen(
                callId = entry.toRoute<Routes.Summary>().callId,
                onCallStarted = { nav.navigate(Routes.ActiveCall) { popUpTo(Routes.Home) } },
                onContacts = { nav.navigate(Routes.Contacts) { popUpTo(Routes.Home) } },
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
                onRecordVoicemail = { id, name -> nav.navigate(Routes.RecordVoicemail(id, name)) },
            )
        }
        composable<Routes.ChatConversation> { entry ->
            val args = entry.toRoute<Routes.ChatConversation>()
            ChatConversationScreen(
                conversationId = args.conversationId,
                onBack = { nav.popBackStack() },
            )
        }
        composable<Routes.RecordVoicemail> { entry ->
            val args = entry.toRoute<Routes.RecordVoicemail>()
            RecordVoicemailScreen(
                toId = args.toId, toName = args.toName,
                onBack = { nav.popBackStack() },
                onLanguages = { nav.navigate(Routes.Languages) },
                onSent = { nav.navigate(Routes.Voicemail(tab = 1)) { popUpTo(Routes.Home) } },
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
    )
}
