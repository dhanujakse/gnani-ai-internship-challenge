package ai.mack.sarvagyan.ui

import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.navigation.NavHostController
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.toRoute
import ai.mack.sarvagyan.ui.screens.ActiveCallScreen
import ai.mack.sarvagyan.ui.screens.AuthScreen
import ai.mack.sarvagyan.ui.screens.CallSetupScreen
import ai.mack.sarvagyan.ui.screens.CallSummaryScreen
import ai.mack.sarvagyan.ui.screens.HelpScreen
import ai.mack.sarvagyan.ui.screens.HomeScreen
import ai.mack.sarvagyan.ui.screens.LanguageScreen
import ai.mack.sarvagyan.ui.screens.OnboardingScreen
import ai.mack.sarvagyan.ui.screens.SettingsScreen
import ai.mack.sarvagyan.ui.screens.SplashScreen
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
    @Serializable data object Help
}

@Composable
fun AppNav(nav: NavHostController, pendingJoinCode: String?, onJoinCodeConsumed: () -> Unit) {
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
            )
        }
        composable<Routes.Summary> { entry ->
            CallSummaryScreen(
                callId = entry.toRoute<Routes.Summary>().callId,
                onNewCall = { nav.navigate(Routes.CallSetup(join = false)) { popUpTo(Routes.Home) } },
                onHome = { nav.popBackStack(Routes.Home, inclusive = false) },
            )
        }
        composable<Routes.Settings> {
            SettingsScreen(
                onBack = { nav.popBackStack() },
                onLanguages = { nav.navigate(Routes.Languages) },
                onHelp = { nav.navigate(Routes.Help) },
                onSignedOut = { nav.navigate(Routes.Auth) { popUpTo(0) } },
            )
        }
        composable<Routes.Help> { HelpScreen(onBack = { nav.popBackStack() }) }
    }
}
