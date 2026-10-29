package ai.mack.sarvagyan.ui.theme

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Shapes
import androidx.compose.material3.Typography
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.Immutable
import androidx.compose.runtime.staticCompositionLocalOf
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

// Brand palette: deep navy / charcoal surfaces, neon blue + teal accents.
object Brand {
    val Navy950 = Color(0xFF070B14)
    val Navy900 = Color(0xFF0B1220)
    val Navy800 = Color(0xFF121B2E)
    val Navy700 = Color(0xFF1A2540)
    val Charcoal = Color(0xFF1E2430)
    val Line = Color(0xFF2A3550)
    val NeonBlue = Color(0xFF3D8BFF)
    val Teal = Color(0xFF19D3C5)
    val TealDim = Color(0xFF0F8F86)
    val TextHi = Color(0xFFEAF0FF)
    val TextMid = Color(0xFFA9B4CC)
    val TextLow = Color(0xFF6E7A94)
    val Danger = Color(0xFFFF4D5E)
    val Warning = Color(0xFFFFB547)
    val Success = Color(0xFF3DDC97)
}

/** Colours with a meaning beyond Material roles (speaker identity, call states). */
@Immutable
data class CallColors(
    val me: Color,
    val meContainer: Color,
    val peer: Color,
    val peerContainer: Color,
    val endCall: Color,
    val success: Color,
    val warning: Color,
)

private val DarkCallColors = CallColors(
    me = Brand.Teal, meContainer = Color(0xFF0E2A2E),
    peer = Brand.NeonBlue, peerContainer = Color(0xFF12203D),
    endCall = Brand.Danger, success = Brand.Success, warning = Brand.Warning,
)
private val LightCallColors = CallColors(
    me = Color(0xFF00897F), meContainer = Color(0xFFDDF5F2),
    peer = Color(0xFF1F63D6), peerContainer = Color(0xFFE2ECFF),
    endCall = Color(0xFFD7263D), success = Color(0xFF138A5A), warning = Color(0xFFB86E00),
)

val LocalCallColors = staticCompositionLocalOf { DarkCallColors }

private val DarkScheme = darkColorScheme(
    primary = Brand.NeonBlue, onPrimary = Color.White,
    primaryContainer = Color(0xFF173A73), onPrimaryContainer = Brand.TextHi,
    secondary = Brand.Teal, onSecondary = Brand.Navy950,
    secondaryContainer = Color(0xFF0E3B3A), onSecondaryContainer = Brand.TextHi,
    background = Brand.Navy950, onBackground = Brand.TextHi,
    surface = Brand.Navy900, onSurface = Brand.TextHi,
    surfaceVariant = Brand.Navy800, onSurfaceVariant = Brand.TextMid,
    surfaceContainer = Brand.Navy800, surfaceContainerHigh = Brand.Navy700,
    surfaceContainerLow = Brand.Navy900, surfaceContainerHighest = Brand.Charcoal,
    outline = Brand.Line, outlineVariant = Color(0xFF222C44),
    error = Brand.Danger, onError = Color.White,
)
private val LightScheme = lightColorScheme(
    primary = Color(0xFF1F63D6), onPrimary = Color.White,
    secondary = Color(0xFF00897F), onSecondary = Color.White,
    background = Color(0xFFF5F7FC), onBackground = Color(0xFF0B1220),
    surface = Color.White, onSurface = Color(0xFF0B1220),
    surfaceVariant = Color(0xFFE8EDF7), onSurfaceVariant = Color(0xFF46526B),
    outline = Color(0xFFC3CCDD), error = Color(0xFFD7263D),
)

private val AppTypography = Typography(
    displaySmall = TextStyle(fontSize = 34.sp, fontWeight = FontWeight.Bold, letterSpacing = (-0.5).sp),
    headlineMedium = TextStyle(fontSize = 26.sp, fontWeight = FontWeight.SemiBold),
    headlineSmall = TextStyle(fontSize = 22.sp, fontWeight = FontWeight.SemiBold),
    titleLarge = TextStyle(fontSize = 20.sp, fontWeight = FontWeight.SemiBold),
    titleMedium = TextStyle(fontSize = 16.sp, fontWeight = FontWeight.SemiBold),
    bodyLarge = TextStyle(fontSize = 16.sp, lineHeight = 24.sp),
    bodyMedium = TextStyle(fontSize = 14.sp, lineHeight = 20.sp),
    labelLarge = TextStyle(fontSize = 15.sp, fontWeight = FontWeight.SemiBold),
    labelMedium = TextStyle(fontSize = 12.sp, fontWeight = FontWeight.Medium, letterSpacing = 0.3.sp),
)

private val AppShapes = Shapes(
    small = RoundedCornerShape(10.dp), medium = RoundedCornerShape(16.dp), large = RoundedCornerShape(24.dp),
)

enum class ThemeMode { System, Dark, Light }

@Composable
fun SarvagyanTheme(mode: ThemeMode = ThemeMode.Dark, content: @Composable () -> Unit) {
    val dark = when (mode) {
        ThemeMode.System -> isSystemInDarkTheme()
        ThemeMode.Dark -> true
        ThemeMode.Light -> false
    }
    CompositionLocalProvider(LocalCallColors provides if (dark) DarkCallColors else LightCallColors) {
        MaterialTheme(
            colorScheme = if (dark) DarkScheme else LightScheme,
            typography = AppTypography,
            shapes = AppShapes,
            content = content,
        )
    }
}
