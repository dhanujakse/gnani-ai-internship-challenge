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
 * Complete semantic brand palette definition.
 * Preserves the dark emerald glow identity in Dark Mode and provides
 * a clean, comfortable, high-contrast emerald counterpart in Light Mode.
 */
@Immutable
data class BrandColors(
    val primaryBg: Color,
    val secondaryBg: Color,
    val cardBg: Color,
    val primaryAccent: Color,
    val highlightAccent: Color,
    val secondaryHighlight: Color,
    val primaryText: Color,
    val secondaryText: Color,
    val textLow: Color,
    val borders: Color,
    val softBg: Color,
    val danger: Color,
    val warning: Color,
    val success: Color,
    val emeraldGlowSubtle: Color,
    val emeraldGlowMedium: Color,
    val emeraldGlowIntense: Color,
    val ambientGlow: Color,
    val glassCardBorder: Color,
    val glassSurface: Color,
    val cardSurfaceEnd: Color,
    val buttonContent: Color,
    val isDark: Boolean,
)

/**
 * Sarvagyan Dark Emerald Glow design system color palette (100% preserved).
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
val DarkBrandColors = BrandColors(
    primaryBg = Color(0xFF06140E),           // Obsidian Black
    secondaryBg = Color(0xFF0A281B),         // Deep Forest
    cardBg = Color(0xFF0D2118),              // Card background
    primaryAccent = Color(0xFF00A86B),       // Emerald Green
    highlightAccent = Color(0xFF00D68F),     // Neon Mint
    secondaryHighlight = Color(0xFF064D32),  // Dark Emerald
    primaryText = Color(0xFFF2FFF7),         // Primary text
    secondaryText = Color(0xFF91A99A),       // Secondary text
    textLow = Color(0xFF6B8576),             // Muted text
    borders = Color(0xFF254637),             // Borders
    softBg = Color(0xFFDFF8EA),              // Soft background
    danger = Color(0xFFFF4D5E),
    warning = Color(0xFFFFB547),
    success = Color(0xFF00D68F),
    emeraldGlowSubtle = Color(0x2600D68F),   // 15% opacity Neon Mint
    emeraldGlowMedium = Color(0x4D00D68F),   // 30% opacity Neon Mint
    emeraldGlowIntense = Color(0x8000D68F),  // 50% opacity Neon Mint
    ambientGlow = Color(0x1A00A86B),         // 10% opacity Emerald
    glassCardBorder = Color(0x4000D68F),     // 25% glowing border
    glassSurface = Color(0xD90D2118),        // 85% opacity CardBg
    cardSurfaceEnd = Color(0xFF091A12),
    buttonContent = Color(0xFF06140E),
    isDark = true,
)

/**
 * Sarvagyan Emerald Light Mode design system color palette.
 * Tailored to belong to the exact same emerald brand identity:
 * - Crisp, comfortable light mint-white background (#F4FAF6)
 * - Deep forest-black primary text with >14:1 contrast (#092015)
 * - Accessible mid-tone forest-green secondary text (#385846)
 * - Pure white cards with subtle mint-gray borders (#CBE3D5)
 * - Rich emerald primary interactive accents (#008955 / #007A4D)
 */
val LightBrandColors = BrandColors(
    primaryBg = Color(0xFFF4FAF6),           // Clean mint-white background
    secondaryBg = Color(0xFFE5F3EC),         // Soft mint container
    cardBg = Color(0xFFFFFFFF),              // Pure white card
    primaryAccent = Color(0xFF008955),       // Deep accessible emerald
    highlightAccent = Color(0xFF007A4D),     // Signature emerald accent
    secondaryHighlight = Color(0xFFD4EDE0),  // Light emerald container
    primaryText = Color(0xFF092015),         // Deep forest-black (>14:1 contrast)
    secondaryText = Color(0xFF385846),       // Readable forest-green (>5.5:1 contrast)
    textLow = Color(0xFF6B8B79),             // Muted forest gray
    borders = Color(0xFFCBE3D5),             // Clean mint border
    softBg = Color(0xFFEAF5EE),              // Soft light container
    danger = Color(0xFFD32F2F),              // Accessible red
    warning = Color(0xFFC77700),             // Accessible amber
    success = Color(0xFF008955),             // Vibrant emerald success
    emeraldGlowSubtle = Color(0x18008955),
    emeraldGlowMedium = Color(0x28008955),
    emeraldGlowIntense = Color(0x38008955),
    ambientGlow = Color(0x12008955),
    glassCardBorder = Color(0x28008955),
    glassSurface = Color(0xF2FFFFFF),
    cardSurfaceEnd = Color(0xFFF7FCF9),
    buttonContent = Color.White,
    isDark = false,
)

val LocalBrandColors = staticCompositionLocalOf { DarkBrandColors }

/**
 * Dynamic Brand color accessors.
 * Resolves to the current active theme palette (Dark or Light) via [LocalBrandColors],
 * ensuring backward compatibility across all existing UI components and screens.
 */
object Brand {
    val current: BrandColors
        @Composable get() = LocalBrandColors.current

    val PrimaryBg: Color @Composable get() = LocalBrandColors.current.primaryBg
    val SecondaryBg: Color @Composable get() = LocalBrandColors.current.secondaryBg
    val CardBg: Color @Composable get() = LocalBrandColors.current.cardBg
    val PrimaryAccent: Color @Composable get() = LocalBrandColors.current.primaryAccent
    val HighlightAccent: Color @Composable get() = LocalBrandColors.current.highlightAccent
    val SecondaryHighlight: Color @Composable get() = LocalBrandColors.current.secondaryHighlight
    val PrimaryText: Color @Composable get() = LocalBrandColors.current.primaryText
    val SecondaryText: Color @Composable get() = LocalBrandColors.current.secondaryText
    val Borders: Color @Composable get() = LocalBrandColors.current.borders
    val SoftBg: Color @Composable get() = LocalBrandColors.current.softBg

    // Semantic mappings for app surfaces and accents
    val Navy950: Color @Composable get() = PrimaryBg
    val Navy900: Color @Composable get() = SecondaryBg
    val Navy800: Color @Composable get() = CardBg
    val Navy700: Color @Composable get() = SecondaryHighlight
    val Charcoal: Color @Composable get() = CardBg
    val Line: Color @Composable get() = Borders
    val NeonBlue: Color @Composable get() = HighlightAccent
    val Teal: Color @Composable get() = PrimaryAccent
    val TealDim: Color @Composable get() = SecondaryHighlight
    val TextHi: Color @Composable get() = PrimaryText
    val TextMid: Color @Composable get() = SecondaryText
    val TextLow: Color @Composable get() = LocalBrandColors.current.textLow
    val Danger: Color @Composable get() = LocalBrandColors.current.danger
    val Warning: Color @Composable get() = LocalBrandColors.current.warning
    val Success: Color @Composable get() = LocalBrandColors.current.success

    // Glow accents
    val EmeraldGlowSubtle: Color @Composable get() = LocalBrandColors.current.emeraldGlowSubtle
    val EmeraldGlowMedium: Color @Composable get() = LocalBrandColors.current.emeraldGlowMedium
    val EmeraldGlowIntense: Color @Composable get() = LocalBrandColors.current.emeraldGlowIntense
    val AmbientGlow: Color @Composable get() = LocalBrandColors.current.ambientGlow
    val GlassCardBorder: Color @Composable get() = LocalBrandColors.current.glassCardBorder
    val GlassSurface: Color @Composable get() = LocalBrandColors.current.glassSurface

    // Additional theme properties
    val CardSurfaceEnd: Color @Composable get() = LocalBrandColors.current.cardSurfaceEnd
    val ButtonContent: Color @Composable get() = LocalBrandColors.current.buttonContent
    val IsDark: Boolean @Composable get() = LocalBrandColors.current.isDark
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
    me = DarkBrandColors.highlightAccent,
    meContainer = Color(0xFF0C2B1D),
    peer = DarkBrandColors.primaryAccent,
    peerContainer = DarkBrandColors.cardBg,
    endCall = DarkBrandColors.danger,
    success = DarkBrandColors.highlightAccent,
    warning = DarkBrandColors.warning,
)

private val LightCallColors = CallColors(
    me = Color(0xFF008955),
    meContainer = Color(0xFFDDF5E8),
    peer = Color(0xFF00754A),
    peerContainer = Color(0xFFE5F7EE),
    endCall = Color(0xFFD32F2F),
    success = Color(0xFF008955),
    warning = Color(0xFFC77700),
)

val LocalCallColors = staticCompositionLocalOf { DarkCallColors }

private val DarkScheme = darkColorScheme(
    primary = DarkBrandColors.primaryAccent,
    onPrimary = DarkBrandColors.primaryBg,
    primaryContainer = DarkBrandColors.secondaryHighlight,
    onPrimaryContainer = DarkBrandColors.primaryText,
    secondary = DarkBrandColors.highlightAccent,
    onSecondary = DarkBrandColors.primaryBg,
    secondaryContainer = DarkBrandColors.secondaryBg,
    onSecondaryContainer = DarkBrandColors.primaryText,
    tertiary = DarkBrandColors.highlightAccent,
    onTertiary = DarkBrandColors.primaryBg,
    background = DarkBrandColors.primaryBg,
    onBackground = DarkBrandColors.primaryText,
    surface = DarkBrandColors.primaryBg,
    onSurface = DarkBrandColors.primaryText,
    surfaceVariant = DarkBrandColors.cardBg,
    onSurfaceVariant = DarkBrandColors.secondaryText,
    surfaceContainer = DarkBrandColors.cardBg,
    surfaceContainerHigh = Color(0xFF10281E),
    surfaceContainerHighest = Color(0xFF153427),
    surfaceContainerLow = DarkBrandColors.secondaryBg,
    outline = DarkBrandColors.borders,
    outlineVariant = Color(0xFF183326),
    error = DarkBrandColors.danger,
    onError = Color.White,
)

private val LightScheme = lightColorScheme(
    primary = LightBrandColors.primaryAccent,
    onPrimary = Color.White,
    primaryContainer = LightBrandColors.secondaryHighlight,
    onPrimaryContainer = LightBrandColors.primaryText,
    secondary = LightBrandColors.highlightAccent,
    onSecondary = Color.White,
    secondaryContainer = LightBrandColors.secondaryBg,
    onSecondaryContainer = LightBrandColors.primaryText,
    tertiary = LightBrandColors.primaryAccent,
    onTertiary = Color.White,
    background = LightBrandColors.primaryBg,
    onBackground = LightBrandColors.primaryText,
    surface = LightBrandColors.cardBg,
    onSurface = LightBrandColors.primaryText,
    surfaceVariant = Color(0xFFEAF5EE),
    onSurfaceVariant = LightBrandColors.secondaryText,
    surfaceContainer = LightBrandColors.cardBg,
    surfaceContainerHigh = Color(0xFFEDF7F1),
    surfaceContainerHighest = Color(0xFFE3F3EA),
    surfaceContainerLow = Color(0xFFF7FCF9),
    outline = LightBrandColors.borders,
    outlineVariant = Color(0xFFDAEBE0),
    error = LightBrandColors.danger,
    onError = Color.White,
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
    val brandColors = if (dark) DarkBrandColors else LightBrandColors
    val callColors = if (dark) DarkCallColors else LightCallColors

    CompositionLocalProvider(
        LocalBrandColors provides brandColors,
        LocalCallColors provides callColors,
    ) {
        MaterialTheme(
            colorScheme = if (dark) DarkScheme else LightScheme,
            typography = AppTypography,
            shapes = AppShapes,
            content = content,
        )
    }
}
