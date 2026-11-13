package ai.mack.sarvagyan.ui.components

import androidx.compose.animation.animateColorAsState
import androidx.compose.animation.core.FastOutSlowInEasing
import androidx.compose.animation.core.LinearEasing
import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.Image
import androidx.compose.ui.graphics.ImageBitmap
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.painterResource
import ai.mack.sarvagyan.R
import ai.mack.sarvagyan.container
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxScope
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.VolumeUp
import androidx.compose.material.icons.filled.ErrorOutline
import androidx.compose.material.icons.filled.Mic
import androidx.compose.material.icons.filled.MicOff
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material.icons.filled.Translate
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.ripple
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.produceState
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.drawBehind
import androidx.compose.ui.draw.shadow
import androidx.compose.ui.geometry.CornerRadius
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.TextUnit
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import ai.mack.sarvagyan.call.Stage
import ai.mack.sarvagyan.call.Turn
import ai.mack.sarvagyan.ui.theme.Brand
import ai.mack.sarvagyan.ui.theme.LocalCallColors
import kotlin.math.cos
import kotlin.math.sin

/**
 * Immersive Dark Emerald background with flowing light waves,
 * slowly floating green orbs, and subtle ambient particles.
 */
@Composable
fun EmeraldAnimatedBackground(
    modifier: Modifier = Modifier,
    content: @Composable BoxScope.() -> Unit
) {
    val t = rememberInfiniteTransition(label = "bgTransition")

    // Slow organic phase for wave oscillation and orb drifting
    val phase by t.animateFloat(
        initialValue = 0f,
        targetValue = 6.28318f,
        animationSpec = infiniteRepeatable(tween(8000, easing = LinearEasing), RepeatMode.Restart),
        label = "bgPhase",
    )

    // Particle drift
    val particlePhase by t.animateFloat(
        initialValue = 0f,
        targetValue = 6.28318f,
        animationSpec = infiniteRepeatable(tween(5000, easing = LinearEasing), RepeatMode.Restart),
        label = "particlePhase",
    )

    val isDark = Brand.IsDark
    val bg = Brand.PrimaryBg
    val secBg = Brand.SecondaryBg
    val secHi = Brand.SecondaryHighlight
    val glowSubtle = Brand.EmeraldGlowSubtle
    val pColor = Brand.HighlightAccent

    Box(
        modifier = modifier
            .fillMaxSize()
            .background(bg)
            .drawBehind {
                val w = size.width
                val h = size.height

                // 1. Moving blurred emerald light orb (top-center)
                val orb1X = w * (0.5f + 0.15f * sin(phase * 0.7f))
                val orb1Y = h * (0.12f + 0.05f * cos(phase * 0.5f))
                // drawRect, not drawCircle: drawCircle clips the gradient to a hard-edged disc
                // the width of the screen, which showed as lines across the top and bottom.
                val orb1Colors = if (isDark) {
                    listOf(
                        secBg.copy(alpha = 0.85f),
                        secHi.copy(alpha = 0.35f),
                        Color.Transparent,
                    )
                } else {
                    listOf(
                        Color(0xFFE2F4EA).copy(alpha = 0.85f),
                        Color(0xFFCEEEDB).copy(alpha = 0.45f),
                        Color.Transparent,
                    )
                }
                drawRect(
                    brush = Brush.radialGradient(
                        colors = orb1Colors,
                        center = Offset(orb1X, orb1Y),
                        radius = w * 0.9f,
                    )
                )

                // 2. Moving blurred mint light orb (bottom-center)
                val orb2X = w * (0.5f + 0.12f * cos(phase * 0.6f))
                val orb2Y = h * (0.78f + 0.06f * sin(phase * 0.4f))
                val orb2Colors = if (isDark) {
                    listOf(
                        glowSubtle.copy(alpha = 0.22f),
                        Color.Transparent,
                    )
                } else {
                    listOf(
                        Color(0xFFD6F2E2).copy(alpha = 0.40f),
                        Color.Transparent,
                    )
                }
                drawRect(
                    brush = Brush.radialGradient(
                        colors = orb2Colors,
                        center = Offset(orb2X, orb2Y),
                        radius = w * 0.75f,
                    )
                )

                // 3. Floating subtle emerald particles
                val particleSeeds = listOf(
                    0.15f to 0.25f, 0.82f to 0.18f, 0.35f to 0.45f,
                    0.68f to 0.38f, 0.22f to 0.65f, 0.88f to 0.60f,
                    0.45f to 0.78f, 0.75f to 0.82f, 0.12f to 0.90f,
                    0.55f to 0.15f, 0.28f to 0.32f, 0.92f to 0.72f,
                )
                for ((idx, pos) in particleSeeds.withIndex()) {
                    val px = w * ((pos.first + 0.04f * sin(particlePhase + idx)) % 1f)
                    val py = h * ((pos.second - 0.06f * ((particlePhase / 6.28318f) + idx * 0.15f)) % 1f)
                    val maxAlpha = if (isDark) 0.35f else 0.25f
                    val pAlpha = ((sin(particlePhase * 1.5f + idx) + 1f) / 2f * maxAlpha).coerceIn(0.05f, 0.45f)
                    drawCircle(
                        color = pColor.copy(alpha = pAlpha),
                        radius = (1.5f + (idx % 3) * 0.8f).dp.toPx(),
                        center = Offset(px, py),
                    )
                }
            },
        content = content,
    )
}

@Composable
fun PrimaryButton(
    text: String,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
    enabled: Boolean = true,
    icon: ImageVector? = null,
    loading: Boolean = false,
) {
    val isDark = Brand.IsDark
    val btnContent = Brand.ButtonContent
    Button(
        onClick = onClick,
        enabled = enabled && !loading,
        modifier = modifier.heightIn(min = 52.dp),
        shape = MaterialTheme.shapes.medium,
        colors = ButtonDefaults.buttonColors(
            containerColor = Brand.PrimaryAccent,
            contentColor = btnContent,
            disabledContainerColor = if (isDark) Brand.CardBg.copy(alpha = 0.6f) else Color(0xFFD8EBE0),
            disabledContentColor = if (isDark) Brand.SecondaryText.copy(alpha = 0.4f) else Color(0xFF8FA89A),
        ),
        contentPadding = PaddingValues(horizontal = 20.dp, vertical = 14.dp),
    ) {
        if (loading) {
            CircularProgressIndicator(
                Modifier.size(20.dp),
                strokeWidth = 2.dp,
                color = btnContent,
            )
        } else if (icon != null) {
            Icon(icon, contentDescription = null, modifier = Modifier.size(20.dp), tint = btnContent)
        }
        if (icon != null || loading) Spacer(Modifier.width(10.dp))
        Text(text, style = MaterialTheme.typography.labelLarge, fontWeight = FontWeight.Bold)
    }
}

@Composable
fun SecondaryButton(
    text: String,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
    enabled: Boolean = true,
    icon: ImageVector? = null,
) {
    val isDark = Brand.IsDark
    OutlinedButton(
        onClick = onClick,
        enabled = enabled,
        modifier = modifier.heightIn(min = 48.dp),
        shape = MaterialTheme.shapes.medium,
        colors = ButtonDefaults.outlinedButtonColors(
            containerColor = if (isDark) Brand.SecondaryBg.copy(alpha = 0.45f) else Brand.SecondaryBg,
            contentColor = Brand.HighlightAccent,
            disabledContentColor = Brand.SecondaryText.copy(alpha = 0.38f),
        ),
        border = androidx.compose.foundation.BorderStroke(1.dp, Brand.Borders),
    ) {
        if (icon != null) {
            Icon(icon, contentDescription = null, modifier = Modifier.size(18.dp), tint = Brand.HighlightAccent)
            Spacer(Modifier.width(8.dp))
        }
        Text(text, style = MaterialTheme.typography.labelLarge)
    }
}

/**
 * Enhanced glassmorphic AppCard with subtle animated light sweep along the border
 * and soft emerald shadow elevation.
 */
@Composable
fun AppCard(
    modifier: Modifier = Modifier,
    padding: Dp = 16.dp,
    content: @Composable ColumnScope.() -> Unit,
) {
    val isDark = Brand.IsDark
    val t = rememberInfiniteTransition(label = "cardBorderTransition")
    val sweepOffset by t.animateFloat(
        initialValue = -0.5f,
        targetValue = 1.5f,
        animationSpec = infiniteRepeatable(tween(4500, easing = LinearEasing), RepeatMode.Restart),
        label = "cardBorderSweep",
    )

    val borderBrush = Brush.linearGradient(
        0.0f to Brand.Borders,
        (sweepOffset - 0.25f).coerceIn(0f, 1f) to Brand.Borders,
        sweepOffset.coerceIn(0f, 1f) to Brand.HighlightAccent.copy(alpha = if (isDark) 0.45f else 0.35f),
        (sweepOffset + 0.25f).coerceIn(0f, 1f) to Brand.Borders,
        1.0f to Brand.Borders,
    )

    Surface(
        modifier = modifier
            .fillMaxWidth()
            .shadow(
                elevation = if (isDark) 4.dp else 2.dp,
                shape = MaterialTheme.shapes.large,
                ambientColor = if (isDark) Brand.HighlightAccent.copy(alpha = 0.1f) else Color(0x14005030),
                spotColor = if (isDark) Brand.HighlightAccent.copy(alpha = 0.15f) else Color(0x1A005030),
            ),
        shape = MaterialTheme.shapes.large,
        color = Brand.CardBg,
        border = androidx.compose.foundation.BorderStroke(1.dp, borderBrush),
    ) {
        Box(
            modifier = Modifier
                .background(
                    Brush.verticalGradient(
                        colors = listOf(Brand.CardBg, Brand.CardSurfaceEnd)
                    )
                )
                .padding(padding)
        ) {
            Column(content = content)
        }
    }
}

@Composable
fun SectionTitle(text: String, modifier: Modifier = Modifier, action: (@Composable () -> Unit)? = null) {
    Row(modifier.fillMaxWidth().padding(top = 8.dp, bottom = 8.dp), verticalAlignment = Alignment.CenterVertically) {
        Box(
            Modifier
                .size(4.dp, 16.dp)
                .clip(RoundedCornerShape(2.dp))
                .background(Brand.HighlightAccent)
        )
        Spacer(Modifier.width(8.dp))
        Text(text, style = MaterialTheme.typography.titleMedium, color = Brand.PrimaryText, modifier = Modifier.weight(1f))
        action?.invoke()
    }
}

@Composable
fun StatusChip(text: String, color: Color, modifier: Modifier = Modifier, pulsing: Boolean = false) {
    val alpha = if (pulsing) {
        val t = rememberInfiniteTransition(label = "pulse")
        t.animateFloat(0.35f, 1f, infiniteRepeatable(tween(700), RepeatMode.Reverse), label = "a").value
    } else 1f
    Row(
        modifier
            .clip(CircleShape)
            .background(color.copy(alpha = 0.14f))
            .border(1.dp, color.copy(alpha = 0.35f), CircleShape)
            .padding(horizontal = 10.dp, vertical = 5.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Box(Modifier.size(8.dp).clip(CircleShape).background(color.copy(alpha = alpha)))
        Spacer(Modifier.width(6.dp))
        Text(text, style = MaterialTheme.typography.labelMedium, color = color, fontWeight = FontWeight.SemiBold)
    }
}

@Composable
fun ErrorBanner(
    message: String,
    modifier: Modifier = Modifier,
    onRetry: (() -> Unit)? = null,
    onDismiss: (() -> Unit)? = null,
    severe: Boolean = false,
) {
    val c = if (severe) MaterialTheme.colorScheme.error else LocalCallColors.current.warning
    Row(
        modifier
            .fillMaxWidth()
            .clip(MaterialTheme.shapes.medium)
            .background(c.copy(alpha = 0.12f))
            .border(1.dp, c.copy(alpha = 0.4f), MaterialTheme.shapes.medium)
            .padding(12.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Icon(Icons.Filled.ErrorOutline, contentDescription = null, tint = c)
        Spacer(Modifier.width(10.dp))
        Text(message, style = MaterialTheme.typography.bodyMedium, color = Brand.PrimaryText, modifier = Modifier.weight(1f))
        if (onRetry != null) {
            TextButton(onClick = onRetry) {
                Icon(Icons.Filled.Refresh, null, Modifier.size(16.dp), tint = c)
                Spacer(Modifier.width(4.dp))
                Text("Retry", color = c)
            }
        }
        if (onDismiss != null) {
            TextButton(onClick = onDismiss) { Text("OK", color = c) }
        }
    }
}

@Composable
fun LoadingView(label: String, modifier: Modifier = Modifier) {
    val highlight = Brand.HighlightAccent
    Column(modifier.fillMaxWidth().padding(24.dp), horizontalAlignment = Alignment.CenterHorizontally) {
        Box(contentAlignment = Alignment.Center) {
            Canvas(Modifier.size(48.dp)) {
                drawCircle(
                    brush = Brush.radialGradient(
                        listOf(highlight.copy(alpha = 0.25f), Color.Transparent)
                    )
                )
            }
            CircularProgressIndicator(
                color = highlight,
                trackColor = Brand.Borders,
            )
        }
        Spacer(Modifier.height(12.dp))
        Text(label, color = Brand.SecondaryText)
    }
}

@Composable
fun EmptyState(icon: ImageVector, title: String, body: String, modifier: Modifier = Modifier) {
    Column(modifier.fillMaxWidth().padding(vertical = 20.dp, horizontal = 12.dp), horizontalAlignment = Alignment.CenterHorizontally) {
        Box(
            Modifier
                .size(56.dp)
                .clip(CircleShape)
                .background(Brand.SecondaryBg)
                .border(1.dp, Brand.Borders, CircleShape),
            contentAlignment = Alignment.Center,
        ) {
            Icon(icon, contentDescription = null, tint = Brand.HighlightAccent, modifier = Modifier.size(28.dp))
        }
        Spacer(Modifier.height(10.dp))
        Text(title, style = MaterialTheme.typography.titleMedium, color = Brand.PrimaryText)
        Spacer(Modifier.height(4.dp))
        Text(body, style = MaterialTheme.typography.bodyMedium, color = Brand.SecondaryText, textAlign = TextAlign.Center)
    }
}

private fun initialsFor(name: String): String {
    val words = name.trim()
        .split(Regex("\\s+"))
        .mapNotNull { w -> w.firstOrNull { it.isLetterOrDigit() }?.uppercaseChar() }
    return when {
        words.size >= 2 -> "${words[0]}${words[1]}"
        words.size == 1 -> "${words[0]}"
        else -> "U"
    }
}

@Composable
fun Avatar(
    name: String,
    color: Color,
    size: Dp = 44.dp,
    avatar: String? = null,
    useMain: Boolean = size > 64.dp,
    contentDescription: String? = null,
) {
    val context = LocalContext.current
    val store = remember(context) { runCatching { context.container.avatars }.getOrNull() }
    val cached = remember(avatar, useMain, store) { store?.peekCached(avatar, useMain) }
    val bitmap by produceState<ImageBitmap?>(initialValue = cached, key1 = avatar, key2 = useMain) {
        value = if (!avatar.isNullOrBlank() && store != null) {
            store.peekCached(avatar, useMain) ?: store.loadBitmap(avatar, useMain)
        } else {
            null
        }
    }

    Box(
        Modifier
            .size(size)
            .clip(CircleShape)
            .background(
                Brush.radialGradient(
                    listOf(color.copy(alpha = 0.28f), color.copy(alpha = 0.08f))
                )
            )
            .border(1.5.dp, color.copy(alpha = 0.7f), CircleShape),
        contentAlignment = Alignment.Center,
    ) {
        val loaded = bitmap
        if (loaded != null) {
            Image(
                bitmap = loaded,
                contentDescription = contentDescription,
                contentScale = ContentScale.Crop,
                modifier = Modifier.fillMaxSize().clip(CircleShape),
            )
        } else {
            val init = remember(name) { initialsFor(name) }
            Text(
                init,
                color = color,
                fontWeight = FontWeight.Bold,
                fontSize = (size.value * if (init.length > 1) 0.34f else 0.42f).sp,
            )
        }
    }
}

/**
 * Animated audio waveform with multi-layer harmonic oscillation,
 * vertical emerald-mint gradients, and peak glowing sparkles.
 */
@Composable
fun Waveform(
    color: Color = Color.Unspecified,
    modifier: Modifier = Modifier,
    bars: Int = 6,
    active: Boolean = true,
) {
    val highlight = Brand.HighlightAccent
    val auroraPalette = listOf(
        Brand.Saffron,
        Brand.RoyalGold,
        Brand.PeacockGreen,
        Brand.RoyalBlue,
        Brand.CulturalPurple,
        Brand.HeritageRed,
    )
    val isMulticolor = color == Color.Unspecified
    val barColor = if (!isMulticolor) color else highlight
    val t = rememberInfiniteTransition(label = "wave")
    val phase by t.animateFloat(
        initialValue = 0f,
        targetValue = 6.28318f,
        animationSpec = infiniteRepeatable(tween(1100, easing = LinearEasing), RepeatMode.Restart),
        label = "phase",
    )

    Canvas(modifier.semantics { contentDescription = if (active) "Voice activity" else "" }) {
        val totalSpacing = (bars - 1)
        val w = size.width / (bars * 1.8f)
        val gap = (size.width - bars * w) / totalSpacing.coerceAtLeast(1)

        // Soft ambient glow halo behind active waveform
        if (active) {
            drawCircle(
                brush = Brush.radialGradient(
                    colors = listOf(
                        highlight.copy(alpha = 0.18f),
                        Color.Transparent,
                    ),
                    radius = size.width * 0.6f,
                )
            )
        }

        for (i in 0 until bars) {
            val barTop = if (isMulticolor) auroraPalette[i % auroraPalette.size] else highlight
            val barBottom = if (isMulticolor) auroraPalette[i % auroraPalette.size] else barColor

            val harmonic1 = sin(phase + i * 0.9f)
            val harmonic2 = sin(phase * 1.6f + i * 1.3f) * 0.35f
            val baseAmp = ((harmonic1 + harmonic2 + 1.35f) / 2.7f).coerceIn(0.2f, 1.0f)
            val amp = if (active) 0.30f + 0.70f * baseAmp else 0.24f

            val h = size.height * amp
            val x = i * (w + gap)
            val y = (size.height - h) / 2f

            drawRoundRect(
                brush = Brush.verticalGradient(
                    colors = listOf(barTop, barBottom),
                    startY = y,
                    endY = y + h,
                ),
                topLeft = Offset(x, y),
                size = Size(w, h),
                cornerRadius = CornerRadius(w / 2, w / 2),
            )

            // Sparkle dot above peak on alternate bars
            if (active && i % 2 == 1 && amp > 0.65f) {
                drawCircle(
                    color = barTop.copy(alpha = 0.75f),
                    radius = (w * 0.35f),
                    center = Offset(x + w / 2f, (y - 3.dp.toPx()).coerceAtLeast(1.dp.toPx())),
                )
            }
        }
    }
}

/**
 * Signature Brand LogoMark with glowing concentric rings and animated waveform.
 */
@Composable
fun LogoMark(size: Dp = 96.dp, animated: Boolean = true) {
    val highlight = Brand.HighlightAccent
    val t = rememberInfiniteTransition(label = "logoBreath")
    val pulse by t.animateFloat(
        initialValue = 0.9f,
        targetValue = 1.08f,
        animationSpec = infiniteRepeatable(tween(2200, easing = FastOutSlowInEasing), RepeatMode.Reverse),
        label = "logoPulse",
    )
    val glow = if (animated) pulse else 1f

    Box(
        modifier = Modifier
            .size(size)
            .drawBehind {
                drawRoundRect(
                    brush = Brush.radialGradient(
                        colors = listOf(
                            highlight.copy(alpha = 0.22f * glow),
                            Color.Transparent,
                        ),
                        radius = (this.size.minDimension / 2f) * 1.4f,
                    ),
                    cornerRadius = CornerRadius(this.size.minDimension * 0.22f, this.size.minDimension * 0.22f),
                )
            },
        contentAlignment = Alignment.Center,
    ) {
        Image(
            painter = painterResource(R.drawable.sarvagyan_logo),
            contentDescription = "Sarvagyan logo",
            modifier = Modifier.size(size).clip(RoundedCornerShape(size * 0.22f)),
        )
    }
}

/**
 * Signature Concentric Glowing Microphone Button.
 * - Breathing aura + expanding/contracting ripples.
 * - Rotating neon emerald sweep ring.
 * - Clear active vs muted transitions.
 */
@Composable
fun GlowingMicButton(
    onClick: () -> Unit,
    isMuted: Boolean,
    modifier: Modifier = Modifier,
    isListening: Boolean = true,
    size: Dp = 68.dp,
) {
    val highlight = Brand.HighlightAccent
    val primary = Brand.PrimaryAccent
    val secondaryHi = Brand.SecondaryHighlight
    val t = rememberInfiniteTransition(label = "micAnimation")

    // Breathing pulse
    val breathScale by t.animateFloat(
        initialValue = 1.0f,
        targetValue = 1.25f,
        animationSpec = infiniteRepeatable(tween(1400, easing = FastOutSlowInEasing), RepeatMode.Reverse),
        label = "breathScale",
    )
    val breathAlpha by t.animateFloat(
        initialValue = 0.25f,
        targetValue = 0.65f,
        animationSpec = infiniteRepeatable(tween(1400, easing = FastOutSlowInEasing), RepeatMode.Reverse),
        label = "breathAlpha",
    )

    // Ripple phase for listening rings
    val ripplePhase by t.animateFloat(
        initialValue = 0f,
        targetValue = 1f,
        animationSpec = infiniteRepeatable(tween(1600, easing = LinearEasing), RepeatMode.Restart),
        label = "ripplePhase",
    )

    Box(
        modifier = modifier
            .size(size * 1.55f)
            .clickable(
                interactionSource = remember { MutableInteractionSource() },
                indication = ripple(bounded = false, radius = size / 2),
                role = Role.Button,
                onClick = onClick,
            ),
        contentAlignment = Alignment.Center,
    ) {
        Canvas(modifier = Modifier.fillMaxSize()) {
            val center = Offset(this.size.width / 2f, this.size.height / 2f)
            val baseRadius = (size.toPx() / 2f)

            if (!isMuted) {
                // Expanding concentric ripple 1
                if (isListening) {
                    val r1 = baseRadius * (1.0f + ripplePhase * 0.5f)
                    val a1 = ((1f - ripplePhase) * 0.55f).coerceIn(0f, 1f)
                    drawCircle(
                        color = highlight.copy(alpha = a1),
                        radius = r1,
                        center = center,
                        style = Stroke(width = 2.dp.toPx()),
                    )

                    // Expanding concentric ripple 2
                    val phase2 = (ripplePhase + 0.5f) % 1f
                    val r2 = baseRadius * (1.0f + phase2 * 0.5f)
                    val a2 = ((1f - phase2) * 0.45f).coerceIn(0f, 1f)
                    drawCircle(
                        color = primary.copy(alpha = a2),
                        radius = r2,
                        center = center,
                        style = Stroke(width = 1.5.dp.toPx()),
                    )
                }

                // Breathing aura halo
                drawCircle(
                    brush = Brush.radialGradient(
                        colors = listOf(
                            highlight.copy(alpha = breathAlpha * 0.45f),
                            secondaryHi.copy(alpha = 0.15f),
                            Color.Transparent,
                        ),
                        center = center,
                        radius = baseRadius * breathScale,
                    ),
                    center = center,
                    radius = baseRadius * breathScale,
                )
            }
        }

        // Inner central microphone button
        Box(
            modifier = Modifier
                .size(size)
                .clip(CircleShape)
                .then(
                    if (!isMuted) {
                        Modifier
                            .background(
                                Brush.horizontalGradient(
                                    listOf(Brand.PrimaryAccent, Brand.HighlightAccent)
                                )
                            )
                            .shadow(8.dp, CircleShape, ambientColor = Brand.HighlightAccent, spotColor = Brand.HighlightAccent)
                    } else {
                        Modifier
                            .background(Brand.CardBg)
                            .border(1.5.dp, Brand.Borders, CircleShape)
                    }
                ),
            contentAlignment = Alignment.Center,
        ) {
            Icon(
                imageVector = if (isMuted) Icons.Filled.MicOff else Icons.Filled.Mic,
                contentDescription = if (isMuted) "Unmute microphone" else "Mute microphone",
                tint = if (isMuted) Brand.SecondaryText else Brand.ButtonContent,
                modifier = Modifier.size(size * 0.46f),
            )
        }
    }
}

@Composable
fun LanguagePill(text: String, modifier: Modifier = Modifier, highlighted: Boolean = false) {
    Row(
        modifier = modifier
            .clip(CircleShape)
            .background(if (highlighted) Brand.SecondaryBg else Brand.CardBg)
            .border(1.dp, if (highlighted) Brand.HighlightAccent.copy(alpha = 0.7f) else Brand.Borders, CircleShape)
            .padding(horizontal = 14.dp, vertical = 8.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        if (highlighted) {
            Box(
                Modifier
                    .size(6.dp)
                    .clip(CircleShape)
                    .background(Brand.HighlightAccent)
            )
            Spacer(Modifier.width(6.dp))
        }
        Text(
            text,
            style = MaterialTheme.typography.labelLarge,
            fontWeight = if (highlighted) FontWeight.Bold else FontWeight.Medium,
            color = if (highlighted) Brand.HighlightAccent else Brand.PrimaryText,
        )
    }
}

/** A conversation turn. Mine on the right (neon mint/deep forest), theirs on the left (emerald/card); clear pipeline state. */
@Composable
fun SubtitleBubble(turn: Turn, playing: Boolean, textScale: Float, myLabel: String, peerLabel: String, onRetry: (String) -> Unit) {
    val accent = if (turn.mine) Brand.HighlightAccent else Brand.PrimaryAccent
    val container = if (turn.mine) Brand.SecondaryBg else Brand.CardBg
    val bubbleShape = RoundedCornerShape(20.dp, 20.dp, if (turn.mine) 6.dp else 20.dp, if (turn.mine) 20.dp else 6.dp)

    Column(Modifier.fillMaxWidth(), horizontalAlignment = if (turn.mine) Alignment.End else Alignment.Start) {
        Text(
            if (turn.mine) myLabel else peerLabel,
            style = MaterialTheme.typography.labelMedium,
            color = accent,
            modifier = Modifier.padding(horizontal = 6.dp, vertical = 2.dp),
        )
        Column(
            Modifier.fillMaxWidth(0.88f)
                .clip(bubbleShape)
                .background(container)
                .border(
                    1.dp,
                    if (playing) Brand.HighlightAccent else accent.copy(alpha = 0.35f),
                    bubbleShape,
                )
                .then(
                    if (playing) {
                        Modifier.shadow(
                            elevation = 6.dp,
                            shape = bubbleShape,
                            ambientColor = Brand.HighlightAccent.copy(alpha = 0.25f),
                            spotColor = Brand.HighlightAccent.copy(alpha = 0.3f),
                        )
                    } else Modifier
                )
                .padding(14.dp)
                .semantics(mergeDescendants = true) {},
        ) {
            Text(turn.headline, fontSize = (19 * textScale).sp, lineHeight = (27 * textScale).sp, color = Brand.PrimaryText)
            turn.secondary?.let {
                Spacer(Modifier.height(6.dp))
                Text(
                    if (turn.mine) "They hear: $it" else it,
                    fontSize = (14 * textScale).sp,
                    lineHeight = (20 * textScale).sp,
                    color = Brand.SecondaryText,
                )
            }
            Spacer(Modifier.height(8.dp))
            TurnStatus(turn, playing, accent, onRetry)
        }
    }
}

@Composable
private fun TurnStatus(turn: Turn, playing: Boolean, accent: Color, onRetry: (String) -> Unit) {
    val muted = Brand.SecondaryText
    val translatingColor = Brand.RoyalBlue // #2478C8 Translating state
    val playingColor = Brand.CulturalPurple // #8950B5 Playing translated voice
    Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(6.dp)) {
        when {
            playing || turn.stage == Stage.Speaking -> {
                Icon(Icons.AutoMirrored.Filled.VolumeUp, null, tint = playingColor, modifier = Modifier.size(16.dp))
                Text(
                    if (turn.mine) "Playing translation to them" else "Playing translation",
                    style = MaterialTheme.typography.labelMedium,
                    fontWeight = FontWeight.SemiBold,
                    color = playingColor,
                )
                Waveform(playingColor, Modifier.size(24.dp, 12.dp), bars = 4, active = true)
            }
            turn.stage == Stage.Recognized || turn.stage == Stage.Translating -> {
                CircularProgressIndicator(
                    Modifier.size(12.dp),
                    strokeWidth = 1.5.dp,
                    color = translatingColor,
                    trackColor = Brand.Borders,
                )
                Text("Translating…", style = MaterialTheme.typography.labelMedium, color = translatingColor)
            }
            turn.stage == Stage.Failed -> {
                Text(
                    turn.error ?: "Translation failed",
                    style = MaterialTheme.typography.labelMedium,
                    color = Brand.Danger,
                    modifier = Modifier.weight(1f, fill = false),
                )
                TextButton(onClick = { onRetry(turn.id) }, contentPadding = PaddingValues(horizontal = 8.dp)) {
                    Text("Retry", color = Brand.HighlightAccent, fontWeight = FontWeight.Bold)
                }
            }
            else -> {
                Icon(Icons.Filled.Translate, null, tint = muted, modifier = Modifier.size(14.dp))
                val latency = turn.totalLatencyMs?.let { " · ${"%.1f".format(it / 1000f)} s" } ?: ""
                val delayed = if (turn.metrics["delayed"] == 1) " · translation was slow" else ""
                Text("Translated$latency$delayed" + (turn.error?.let { " · $it" } ?: ""), style = MaterialTheme.typography.labelMedium, color = muted)
            }
        }
    }
}

@Composable
fun ListeningBubble(mine: Boolean, label: String) {
    val accent = if (mine) Brand.SelectedBorder else Brand.PeacockGreen
    val container = Brand.ElevatedSurface
    val t = rememberInfiniteTransition(label = "listeningPulse")
    val borderAlpha by t.animateFloat(
        initialValue = 0.35f,
        targetValue = 0.85f,
        animationSpec = infiniteRepeatable(tween(750), RepeatMode.Reverse),
        label = "listeningAlpha",
    )

    Column(Modifier.fillMaxWidth(), horizontalAlignment = if (mine) Alignment.End else Alignment.Start) {
        Row(
            Modifier
                .clip(RoundedCornerShape(18.dp))
                .background(container)
                .border(1.dp, accent.copy(alpha = borderAlpha), RoundedCornerShape(18.dp))
                .padding(horizontal = 14.dp, vertical = 10.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Waveform(Color.Unspecified, Modifier.size(32.dp, 18.dp), bars = 6, active = true)
            Spacer(Modifier.width(10.dp))
            Text(label, style = MaterialTheme.typography.labelLarge, fontWeight = FontWeight.SemiBold, color = accent)
        }
    }
}

@Composable
fun FullScreenCentered(content: @Composable ColumnScope.() -> Unit) {
    Column(Modifier.fillMaxSize().padding(24.dp), verticalArrangement = Arrangement.Center, horizontalAlignment = Alignment.CenterHorizontally, content = content)
}

@Composable
fun scaledSp(base: Float, scale: Float): TextUnit = (base * scale).sp
