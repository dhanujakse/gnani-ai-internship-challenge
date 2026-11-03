package ai.mack.sarvagyan.ui.theme

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Shapes
import androidx.compose.material3.Typography
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.Immutable
import androidx.compose.runtime.staticCompositionLocalOf
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

/**
 * Sarvagyan Dark Emerald Glow design system color palette.
 * Primary background: #06140E (Obsidian Black)
 * Secondary background: #0A281B (Deep Forest)
 * Card background: #0D2118
 * Primary accent: #00A86B (Emerald Green)
 * Highlight accent: #00D68F (Neon Mint)
 * Secondary highlight: #064D32 (Dark Emerald)
 * Primary text: #F2FFF7
 * Secondary text: #91A99A
 * Borders: #254637
 * Soft background: #DFF8EA
 */
object Brand {
    // Dark Emerald Glow palette
    val PrimaryBg = Color(0xFF06140E)           // Obsidian Black
    val SecondaryBg = Color(0xFF0A281B)         // Deep Forest
    val CardBg = Color(0xFF0D2118)              // Card background
    val PrimaryAccent = Color(0xFF00A86B)       // Emerald Green
    val HighlightAccent = Color(0xFF00D68F)     // Neon Mint
    val SecondaryHighlight = Color(0xFF064D32)  // Dark Emerald
    val PrimaryText = Color(0xFFF2FFF7)         // Primary text
    val SecondaryText = Color(0xFF91A99A)       // Secondary text
    val Borders = Color(0xFF254637)             // Borders
    val SoftBg = Color(0xFFDFF8EA)              // Soft background

    // Semantic mappings for app surfaces and accents
    val Navy950 = PrimaryBg                     // Obsidian Black
    val Navy900 = SecondaryBg                   // Deep Forest
    val Navy800 = CardBg                        // Card background
    val Navy700 = SecondaryHighlight            // Dark Emerald
    val Charcoal = CardBg                       // Charcoal surfaces -> Card background
    val Line = Borders                          // Borders
    val NeonBlue = HighlightAccent              // Neon Mint
    val Teal = PrimaryAccent                    // Emerald Green
    val TealDim = SecondaryHighlight            // Dark Emerald
    val TextHi = PrimaryText                    // Primary text
    val TextMid = SecondaryText                 // Secondary text
    val TextLow = Color(0xFF6B8576)             // Muted text
    val Danger = Color(0xFFFF4D5E)
    val Warning = Color(0xFFFFB547)
    val Success = HighlightAccent               // Neon Mint

    // Glow accents
    val EmeraldGlowSubtle = Color(0x2600D68F)   // 15% opacity Neon Mint
    val EmeraldGlowMedium = Color(0x4D00D68F)   // 30% opacity Neon Mint
    val EmeraldGlowIntense = Color(0x8000D68F)  // 50% opacity Neon Mint
    val AmbientGlow = Color(0x1A00A86B)         // 10% opacity Emerald
    val GlassCardBorder = Color(0x4000D68F)     // 25% glowing border
    val GlassSurface = Color(0xD90D2118)        // 85% opacity CardBg
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
    me = Brand.HighlightAccent,
    meContainer = Color(0xFF0C2B1D),
    peer = Brand.PrimaryAccent,
    peerContainer = Brand.CardBg,
    endCall = Brand.Danger,
    success = Brand.HighlightAccent,
    warning = Brand.Warning,
)

private val LightCallColors = CallColors(
    me = Color(0xFF008955),
    meContainer = Color(0xFFDDF5E8),
    peer = Color(0xFF00754A),
    peerContainer = Color(0xFFE5F7EE),
    endCall = Color(0xFFD7263D),
    success = Color(0xFF00A86B),
    warning = Color(0xFFB86E00),
)

val LocalCallColors = staticCompositionLocalOf { DarkCallColors }

private val DarkScheme = darkColorScheme(
    primary = Brand.PrimaryAccent,
    onPrimary = Brand.PrimaryBg,
    primaryContainer = Brand.SecondaryHighlight,
    onPrimaryContainer = Brand.PrimaryText,
    secondary = Brand.HighlightAccent,
    onSecondary = Brand.PrimaryBg,
    secondaryContainer = Brand.SecondaryBg,
    onSecondaryContainer = Brand.PrimaryText,
    tertiary = Brand.HighlightAccent,
    onTertiary = Brand.PrimaryBg,
    background = Brand.PrimaryBg,
    onBackground = Brand.PrimaryText,
    surface = Brand.PrimaryBg,
    onSurface = Brand.PrimaryText,
    surfaceVariant = Brand.CardBg,
    onSurfaceVariant = Brand.SecondaryText,
    surfaceContainer = Brand.CardBg,
    surfaceContainerHigh = Color(0xFF10281E),
    surfaceContainerHighest = Color(0xFF153427),
    surfaceContainerLow = Brand.SecondaryBg,
    outline = Brand.Borders,
    outlineVariant = Color(0xFF183326),
    error = Brand.Danger,
    onError = Color.White,
)

private val LightScheme = lightColorScheme(
    primary = Color(0xFF008955),
    onPrimary = Color.White,
    secondary = Brand.PrimaryAccent,
    onSecondary = Color.White,
    background = Color(0xFFF3FAF6),
    onBackground = Color(0xFF06140E),
    surface = Color.White,
    onSurface = Color(0xFF06140E),
    surfaceVariant = Brand.SoftBg,
    onSurfaceVariant = Color(0xFF234433),
    outline = Color(0xFFB4D8C4),
    error = Brand.Danger,
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
    small = RoundedCornerShape(10.dp),
    medium = RoundedCornerShape(16.dp),
    large = RoundedCornerShape(24.dp),
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
