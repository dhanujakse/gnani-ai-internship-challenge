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
    val saffron: Color = Color(0xFFFF8A00),
    val deepRed: Color = Color(0xFFD7263D),
    val gold: Color = Color(0xFFF4B323),
    val emerald: Color = Color(0xFF00A878),
    val blue: Color = Color(0xFF2585D8),
    val purple: Color = Color(0xFF9638B5),
    val deepTeal: Color = Color(0xFF002B24),
    val darkEmerald: Color = Color(0xFF001A16),
    val mintGreen: Color = Color(0xFFA8DCC5),
    val ivoryWhite: Color = Color(0xFFF6F1E7),
    val mutedGreen: Color = Color(0xFF829B90),
)

/**
 * Sarvagyan Reference Design Palette:
 * Main background: Deep Teal #002B24
 * Dark background: Dark Emerald #001A16
 * Primary accent: Neon Emerald Green #00F0A0
 * Secondary elements: Mint Green #A8DCC5
 * Main text: Ivory / Soft White #F6F1E7
 * Secondary text: Muted Green #829B90
 * Saffron: #FF8A00, Red: #D7263D, Gold: #F4B323, Green: #00A878, Blue: #2585D8, Purple: #9638B5
 */
val DarkBrandColors = BrandColors(
    primaryBg = Color(0xFF001A16),           // Dark Emerald
    secondaryBg = Color(0xFF002B24),         // Deep Teal
    cardBg = Color(0xFF00221C),              // Deep Emerald card surface
    primaryAccent = Color(0xFF00F0A0),       // Neon Emerald Green
    highlightAccent = Color(0xFF00F0A0),     // Neon Emerald Green
    secondaryHighlight = Color(0xFF00382E),  // Deep Teal container
    primaryText = Color(0xFFF6F1E7),         // Ivory / Soft White
    secondaryText = Color(0xFF829B90),       // Muted Green
    textLow = Color(0xFF5A7569),             // Muted Green subtle
    borders = Color(0xFF134539),             // Deep Teal border
    softBg = Color(0xFFA8DCC5),              // Mint Green
    danger = Color(0xFFD7263D),              // Deep Red
    warning = Color(0xFFFF8A00),             // Saffron
    success = Color(0xFF00F0A0),             // Neon Emerald Green
    emeraldGlowSubtle = Color(0x2600F0A0),   // 15% opacity Neon Emerald
    emeraldGlowMedium = Color(0x4D00F0A0),   // 30% opacity Neon Emerald
    emeraldGlowIntense = Color(0x8000F0A0),  // 50% opacity Neon Emerald
    ambientGlow = Color(0x1A00F0A0),         // 10% opacity Neon Emerald
    glassCardBorder = Color(0x4000F0A0),     // 25% glowing Neon Emerald border
    glassSurface = Color(0xD900221C),        // 85% opacity CardBg
    cardSurfaceEnd = Color(0xFF001A16),
    buttonContent = Color(0xFF001A16),
    isDark = true,
    saffron = Color(0xFFFF8A00),
    deepRed = Color(0xFFD7263D),
    gold = Color(0xFFF4B323),
    emerald = Color(0xFF00A878),
    blue = Color(0xFF2585D8),
    purple = Color(0xFF9638B5),
    deepTeal = Color(0xFF002B24),
    darkEmerald = Color(0xFF001A16),
    mintGreen = Color(0xFFA8DCC5),
    ivoryWhite = Color(0xFFF6F1E7),
    mutedGreen = Color(0xFF829B90),
)

/**
 * Sarvagyan Emerald Light Mode design system color palette.
 */
val LightBrandColors = BrandColors(
    primaryBg = Color(0xFFF6FBF8),           // Clean mint-white background
    secondaryBg = Color(0xFFE2F3EB),         // Soft mint container
    cardBg = Color(0xFFFFFFFF),              // Pure white card
    primaryAccent = Color(0xFF00A878),       // Deep accessible emerald
    highlightAccent = Color(0xFF00A878),     // Signature emerald accent
    secondaryHighlight = Color(0xFFCDEBDD),  // Light emerald container
    primaryText = Color(0xFF001A16),         // Dark emerald text
    secondaryText = Color(0xFF385846),       // Readable forest-green
    textLow = Color(0xFF6B8B79),             // Muted forest gray
    borders = Color(0xFFCBE3D5),             // Clean mint border
    softBg = Color(0xFFA8DCC5),              // Mint Green
    danger = Color(0xFFD7263D),              // Deep Red
    warning = Color(0xFFFF8A00),             // Saffron
    success = Color(0xFF00A878),             // Emerald success
    emeraldGlowSubtle = Color(0x1800A878),
    emeraldGlowMedium = Color(0x2800A878),
    emeraldGlowIntense = Color(0x3800A878),
    ambientGlow = Color(0x1200A878),
    glassCardBorder = Color(0x2800A878),
    glassSurface = Color(0xF2FFFFFF),
    cardSurfaceEnd = Color(0xFFF7FCF9),
    buttonContent = Color.White,
    isDark = false,
    saffron = Color(0xFFFF8A00),
    deepRed = Color(0xFFD7263D),
    gold = Color(0xFFF4B323),
    emerald = Color(0xFF00A878),
    blue = Color(0xFF2585D8),
    purple = Color(0xFF9638B5),
    deepTeal = Color(0xFF002B24),
    darkEmerald = Color(0xFF001A16),
    mintGreen = Color(0xFFA8DCC5),
    ivoryWhite = Color(0xFFF6F1E7),
    mutedGreen = Color(0xFF829B90),
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

    // Reference-based palette tokens
    val Saffron: Color @Composable get() = LocalBrandColors.current.saffron
    val DeepRed: Color @Composable get() = LocalBrandColors.current.deepRed
    val Red: Color @Composable get() = LocalBrandColors.current.deepRed
    val Gold: Color @Composable get() = LocalBrandColors.current.gold
    val Emerald: Color @Composable get() = LocalBrandColors.current.emerald
    val Blue: Color @Composable get() = LocalBrandColors.current.blue
    val Purple: Color @Composable get() = LocalBrandColors.current.purple
    val DeepTeal: Color @Composable get() = LocalBrandColors.current.deepTeal
    val DarkEmerald: Color @Composable get() = LocalBrandColors.current.darkEmerald
    val MintGreen: Color @Composable get() = LocalBrandColors.current.mintGreen
    val IvoryWhite: Color @Composable get() = LocalBrandColors.current.ivoryWhite
    val MutedGreen: Color @Composable get() = LocalBrandColors.current.mutedGreen

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
    me = DarkBrandColors.highlightAccent, // Neon Emerald
    meContainer = Color(0xFF00382E),
    peer = DarkBrandColors.emerald, // Emerald
    peerContainer = DarkBrandColors.secondaryBg, // Deep Teal
    endCall = DarkBrandColors.danger, // Deep Red
    success = DarkBrandColors.highlightAccent,
    warning = DarkBrandColors.warning, // Saffron
)

private val LightCallColors = CallColors(
    me = Color(0xFF00A878),
    meContainer = Color(0xFFDDF5E8),
    peer = Color(0xFF00754A),
    peerContainer = Color(0xFFE5F7EE),
    endCall = Color(0xFFD7263D),
    success = Color(0xFF00A878),
    warning = Color(0xFFFF8A00),
)

val LocalCallColors = staticCompositionLocalOf { DarkCallColors }

private val DarkScheme = darkColorScheme(
    primary = DarkBrandColors.primaryAccent,
    onPrimary = DarkBrandColors.primaryBg,
    primaryContainer = DarkBrandColors.secondaryHighlight,
    onPrimaryContainer = DarkBrandColors.primaryText,
    secondary = DarkBrandColors.softBg,
    onSecondary = DarkBrandColors.primaryBg,
    secondaryContainer = DarkBrandColors.secondaryBg,
    onSecondaryContainer = DarkBrandColors.primaryText,
    tertiary = DarkBrandColors.emerald,
    onTertiary = DarkBrandColors.primaryBg,
    background = DarkBrandColors.primaryBg,
    onBackground = DarkBrandColors.primaryText,
    surface = DarkBrandColors.primaryBg,
    onSurface = DarkBrandColors.primaryText,
    surfaceVariant = DarkBrandColors.secondaryBg,
    onSurfaceVariant = DarkBrandColors.secondaryText,
    surfaceContainer = DarkBrandColors.cardBg,
    surfaceContainerHigh = Color(0xFF002E26),
    surfaceContainerHighest = Color(0xFF003B31),
    surfaceContainerLow = Color(0xFF001F1A),
    outline = DarkBrandColors.borders,
    outlineVariant = Color(0xFF1A5244),
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
