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
    val elevatedSurface: Color,
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
    val saffron: Color = Color(0xFFFF8A24),
    val heritageRed: Color = Color(0xFFC62845),
    val deepRed: Color = Color(0xFFC62845),
    val royalGold: Color = Color(0xFFF5B52E),
    val gold: Color = Color(0xFFF5B52E),
    val peacockGreen: Color = Color(0xFF009B77),
    val emerald: Color = Color(0xFF009B77),
    val royalBlue: Color = Color(0xFF2478C8),
    val blue: Color = Color(0xFF2478C8),
    val culturalPurple: Color = Color(0xFF8950B5),
    val purple: Color = Color(0xFF8950B5),
    val selectedBorder: Color = Color(0xFF00CBA0),
    val deepTeal: Color = Color(0xFF0B292E),
    val darkEmerald: Color = Color(0xFF071B20),
    val mintGreen: Color = Color(0xFFA8DCC5),
    val ivoryWhite: Color = Color(0xFFF5F7F2),
    val mutedGreen: Color = Color(0xFFA9BFBA),
)

/**
 * Sarvagyan Dark Indian Aurora Palette:
 * Primary background: #071B20
 * Secondary background: #0B292E
 * Card surface: #12363A
 * Elevated surface: #194449
 * Primary text: #F5F7F2
 * Secondary text: #A9BFBA
 * Saffron: #FF8A24, Heritage Red: #C62845, Royal Gold: #F5B52E,
 * Peacock Green: #009B77, Royal Blue: #2478C8, Cultural Purple: #8950B5,
 * Selected border / highlight: #00CBA0
 */
val DarkBrandColors = BrandColors(
    primaryBg = Color(0xFF071B20),           // Dark Indian Aurora Primary background
    secondaryBg = Color(0xFF0B292E),         // Secondary background
    cardBg = Color(0xFF12363A),              // Card surface
    elevatedSurface = Color(0xFF194449),     // Elevated surface
    primaryAccent = Color(0xFF009B77),       // Peacock Green (Primary buttons, success)
    highlightAccent = Color(0xFF00CBA0),     // Vibrant Teal / Selected language border
    secondaryHighlight = Color(0xFF194449),  // Elevated container
    primaryText = Color(0xFFF5F7F2),         // Headings and important text
    secondaryText = Color(0xFFA9BFBA),       // Descriptions and subtitles
    textLow = Color(0xFF6B8B86),             // Muted hint text
    borders = Color(0xFF1E4D53),             // Subtle teal border
    softBg = Color(0xFFA8DCC5),              // Mint accent
    danger = Color(0xFFC62845),              // Heritage Red (End call button)
    warning = Color(0xFFFF8A24),             // Saffron
    success = Color(0xFF009B77),             // Peacock Green
    emeraldGlowSubtle = Color(0x26009B77),   // 15% opacity Peacock Green
    emeraldGlowMedium = Color(0x4D009B77),   // 30% opacity Peacock Green
    emeraldGlowIntense = Color(0x80009B77),  // 50% opacity Peacock Green
    ambientGlow = Color(0x1A009B77),         // 10% opacity Peacock Green
    glassCardBorder = Color(0x4000CBA0),     // 25% glowing border
    glassSurface = Color(0xD912363A),        // 85% opacity CardBg
    cardSurfaceEnd = Color(0xFF0B292E),
    buttonContent = Color(0xFFF5F7F2),       // Primary text on buttons
    isDark = true,
    saffron = Color(0xFFFF8A24),
    heritageRed = Color(0xFFC62845),
    deepRed = Color(0xFFC62845),
    royalGold = Color(0xFFF5B52E),
    gold = Color(0xFFF5B52E),
    peacockGreen = Color(0xFF009B77),
    emerald = Color(0xFF009B77),
    royalBlue = Color(0xFF2478C8),
    blue = Color(0xFF2478C8),
    culturalPurple = Color(0xFF8950B5),
    purple = Color(0xFF8950B5),
    selectedBorder = Color(0xFF00CBA0),
    deepTeal = Color(0xFF0B292E),
    darkEmerald = Color(0xFF071B20),
    mintGreen = Color(0xFFA8DCC5),
    ivoryWhite = Color(0xFFF5F7F2),
    mutedGreen = Color(0xFFA9BFBA),
)

/**
 * Sarvagyan Emerald Light Mode design system color palette.
 */
val LightBrandColors = BrandColors(
    primaryBg = Color(0xFFF6FBF8),           // Clean mint-white background
    secondaryBg = Color(0xFFE2F3EB),         // Soft mint container
    cardBg = Color(0xFFFFFFFF),              // Pure white card
    elevatedSurface = Color(0xFFEDF7F1),
    primaryAccent = Color(0xFF009B77),       // Peacock green
    highlightAccent = Color(0xFF00CBA0),     // Vibrant teal accent
    secondaryHighlight = Color(0xFFCDEBDD),  // Light container
    primaryText = Color(0xFF071B20),         // Dark text
    secondaryText = Color(0xFF385846),       // Readable forest-green
    textLow = Color(0xFF6B8B79),             // Muted forest gray
    borders = Color(0xFFCBE3D5),             // Clean mint border
    softBg = Color(0xFFA8DCC5),              // Mint Green
    danger = Color(0xFFC62845),              // Heritage Red
    warning = Color(0xFFFF8A24),             // Saffron
    success = Color(0xFF009B77),             // Peacock green success
    emeraldGlowSubtle = Color(0x18009B77),
    emeraldGlowMedium = Color(0x28009B77),
    emeraldGlowIntense = Color(0x38009B77),
    ambientGlow = Color(0x12009B77),
    glassCardBorder = Color(0x28009B77),
    glassSurface = Color(0xF2FFFFFF),
    cardSurfaceEnd = Color(0xFFF7FCF9),
    buttonContent = Color.White,
    isDark = false,
    saffron = Color(0xFFFF8A24),
    heritageRed = Color(0xFFC62845),
    deepRed = Color(0xFFC62845),
    royalGold = Color(0xFFF5B52E),
    gold = Color(0xFFF5B52E),
    peacockGreen = Color(0xFF009B77),
    emerald = Color(0xFF009B77),
    royalBlue = Color(0xFF2478C8),
    blue = Color(0xFF2478C8),
    culturalPurple = Color(0xFF8950B5),
    purple = Color(0xFF8950B5),
    selectedBorder = Color(0xFF00CBA0),
    deepTeal = Color(0xFF0B292E),
    darkEmerald = Color(0xFF071B20),
    mintGreen = Color(0xFFA8DCC5),
    ivoryWhite = Color(0xFFF5F7F2),
    mutedGreen = Color(0xFFA9BFBA),
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
    val HeritageRed: Color @Composable get() = LocalBrandColors.current.heritageRed
    val DeepRed: Color @Composable get() = LocalBrandColors.current.deepRed
    val Red: Color @Composable get() = LocalBrandColors.current.deepRed
    val RoyalGold: Color @Composable get() = LocalBrandColors.current.royalGold
    val Gold: Color @Composable get() = LocalBrandColors.current.gold
    val PeacockGreen: Color @Composable get() = LocalBrandColors.current.peacockGreen
    val Emerald: Color @Composable get() = LocalBrandColors.current.emerald
    val RoyalBlue: Color @Composable get() = LocalBrandColors.current.royalBlue
    val Blue: Color @Composable get() = LocalBrandColors.current.blue
    val CulturalPurple: Color @Composable get() = LocalBrandColors.current.culturalPurple
    val Purple: Color @Composable get() = LocalBrandColors.current.purple
    val SelectedBorder: Color @Composable get() = LocalBrandColors.current.selectedBorder
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
    val ElevatedSurface: Color @Composable get() = LocalBrandColors.current.elevatedSurface
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
    me = Color(0xFF009B77), // Peacock Green
    meContainer = Color(0xFF12363A), // Card surface
    peer = Color(0xFF2478C8), // Royal Blue
    peerContainer = Color(0xFF0B292E), // Secondary bg
    endCall = Color(0xFFC62845), // Heritage Red
    success = Color(0xFF009B77), // Peacock Green
    warning = Color(0xFFFF8A24), // Saffron
)

private val LightCallColors = CallColors(
    me = Color(0xFF009B77),
    meContainer = Color(0xFFDDF5E8),
    peer = Color(0xFF00754A),
    peerContainer = Color(0xFFE5F7EE),
    endCall = Color(0xFFC62845),
    success = Color(0xFF009B77),
    warning = Color(0xFFFF8A24),
)

val LocalCallColors = staticCompositionLocalOf { DarkCallColors }

private val DarkScheme = darkColorScheme(
    primary = DarkBrandColors.primaryAccent,
    onPrimary = DarkBrandColors.buttonContent,
    primaryContainer = DarkBrandColors.secondaryHighlight,
    onPrimaryContainer = DarkBrandColors.primaryText,
    secondary = DarkBrandColors.softBg,
    onSecondary = DarkBrandColors.primaryBg,
    secondaryContainer = DarkBrandColors.secondaryBg,
    onSecondaryContainer = DarkBrandColors.primaryText,
    tertiary = DarkBrandColors.emerald,
    onTertiary = DarkBrandColors.buttonContent,
    background = DarkBrandColors.primaryBg,
    onBackground = DarkBrandColors.primaryText,
    surface = DarkBrandColors.primaryBg,
    onSurface = DarkBrandColors.primaryText,
    surfaceVariant = DarkBrandColors.secondaryBg,
    onSurfaceVariant = DarkBrandColors.secondaryText,
    surfaceContainer = DarkBrandColors.cardBg,
    surfaceContainerHigh = DarkBrandColors.elevatedSurface,
    surfaceContainerHighest = Color(0xFF1E4D53),
    surfaceContainerLow = Color(0xFF071B20),
    outline = DarkBrandColors.borders,
    outlineVariant = Color(0xFF1E4D53),
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
