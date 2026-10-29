package ai.mack.sarvagyan.ui.components

import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
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
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.geometry.CornerRadius
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.graphics.vector.ImageVector
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

@Composable
fun PrimaryButton(text: String, onClick: () -> Unit, modifier: Modifier = Modifier, enabled: Boolean = true,
                  icon: ImageVector? = null, loading: Boolean = false) {
    Button(
        onClick = onClick, enabled = enabled && !loading, modifier = modifier.heightIn(min = 52.dp),
        shape = MaterialTheme.shapes.medium,
        contentPadding = PaddingValues(horizontal = 20.dp, vertical = 14.dp),
    ) {
        if (loading) CircularProgressIndicator(Modifier.size(20.dp), strokeWidth = 2.dp, color = MaterialTheme.colorScheme.onPrimary)
        else if (icon != null) Icon(icon, contentDescription = null, modifier = Modifier.size(20.dp))
        if (icon != null || loading) Spacer(Modifier.width(10.dp))
        Text(text, style = MaterialTheme.typography.labelLarge)
    }
}

@Composable
fun SecondaryButton(text: String, onClick: () -> Unit, modifier: Modifier = Modifier, enabled: Boolean = true, icon: ImageVector? = null) {
    OutlinedButton(onClick = onClick, enabled = enabled, modifier = modifier.heightIn(min = 48.dp), shape = MaterialTheme.shapes.medium) {
        if (icon != null) {
            Icon(icon, contentDescription = null, modifier = Modifier.size(18.dp))
            Spacer(Modifier.width(8.dp))
        }
        Text(text, style = MaterialTheme.typography.labelLarge)
    }
}

@Composable
fun AppCard(modifier: Modifier = Modifier, padding: Dp = 16.dp, content: @Composable ColumnScope.() -> Unit) {
    Surface(
        modifier = modifier.fillMaxWidth(), shape = MaterialTheme.shapes.large, color = MaterialTheme.colorScheme.surfaceContainer,
        border = androidx.compose.foundation.BorderStroke(1.dp, MaterialTheme.colorScheme.outlineVariant),
    ) { Column(Modifier.padding(padding), content = content) }
}

@Composable
fun SectionTitle(text: String, modifier: Modifier = Modifier, action: (@Composable () -> Unit)? = null) {
    Row(modifier.fillMaxWidth().padding(top = 8.dp, bottom = 8.dp), verticalAlignment = Alignment.CenterVertically) {
        Text(text, style = MaterialTheme.typography.titleMedium, color = MaterialTheme.colorScheme.onSurfaceVariant, modifier = Modifier.weight(1f))
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
        modifier.clip(CircleShape).background(color.copy(alpha = 0.14f)).padding(horizontal = 10.dp, vertical = 5.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Box(Modifier.size(8.dp).clip(CircleShape).background(color.copy(alpha = alpha)))
        Spacer(Modifier.width(6.dp))
        Text(text, style = MaterialTheme.typography.labelMedium, color = color)
    }
}

@Composable
fun ErrorBanner(message: String, modifier: Modifier = Modifier, onRetry: (() -> Unit)? = null, onDismiss: (() -> Unit)? = null, severe: Boolean = false) {
    val c = if (severe) MaterialTheme.colorScheme.error else LocalCallColors.current.warning
    Row(
        modifier.fillMaxWidth().clip(MaterialTheme.shapes.medium).background(c.copy(alpha = 0.12f))
            .border(1.dp, c.copy(alpha = 0.4f), MaterialTheme.shapes.medium).padding(12.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Icon(Icons.Filled.ErrorOutline, contentDescription = null, tint = c)
        Spacer(Modifier.width(10.dp))
        Text(message, style = MaterialTheme.typography.bodyMedium, modifier = Modifier.weight(1f))
        if (onRetry != null) TextButton(onClick = onRetry) { Icon(Icons.Filled.Refresh, null, Modifier.size(16.dp)); Spacer(Modifier.width(4.dp)); Text("Retry") }
        if (onDismiss != null) TextButton(onClick = onDismiss) { Text("OK") }
    }
}

@Composable
fun LoadingView(label: String, modifier: Modifier = Modifier) {
    Column(modifier.fillMaxWidth().padding(24.dp), horizontalAlignment = Alignment.CenterHorizontally) {
        CircularProgressIndicator()
        Spacer(Modifier.height(12.dp))
        Text(label, color = MaterialTheme.colorScheme.onSurfaceVariant)
    }
}

@Composable
fun EmptyState(icon: ImageVector, title: String, body: String, modifier: Modifier = Modifier) {
    Column(modifier.fillMaxWidth().padding(vertical = 20.dp, horizontal = 12.dp), horizontalAlignment = Alignment.CenterHorizontally) {
        Icon(icon, contentDescription = null, tint = MaterialTheme.colorScheme.onSurfaceVariant, modifier = Modifier.size(32.dp))
        Spacer(Modifier.height(8.dp))
        Text(title, style = MaterialTheme.typography.titleMedium)
        Spacer(Modifier.height(4.dp))
        Text(body, style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant, textAlign = TextAlign.Center)
    }
}

@Composable
fun Avatar(name: String, color: Color, size: Dp = 44.dp) {
    Box(
        Modifier.size(size).clip(CircleShape).background(color.copy(alpha = 0.18f)).border(1.5.dp, color.copy(alpha = 0.6f), CircleShape),
        contentAlignment = Alignment.Center,
    ) {
        Text(name.trim().take(1).uppercase().ifEmpty { "?" }, color = color, fontWeight = FontWeight.Bold, fontSize = (size.value * 0.42f).sp)
    }
}

/** Animated bars: used for "listening" and the logo. Restrained, low cost. */
@Composable
fun Waveform(color: Color, modifier: Modifier = Modifier, bars: Int = 5, active: Boolean = true) {
    val t = rememberInfiniteTransition(label = "wave")
    val phase by t.animateFloat(0f, 6.283f, infiniteRepeatable(tween(1100)), label = "phase")
    Canvas(modifier.semantics { contentDescription = if (active) "Listening" else "" }) {
        val w = size.width / (bars * 2 - 1)
        for (i in 0 until bars) {
            val amp = if (active) 0.35f + 0.65f * ((kotlin.math.sin(phase + i * 1.1f) + 1f) / 2f) else 0.3f
            val h = size.height * amp
            drawRoundRect(color, Offset(i * 2 * w, (size.height - h) / 2), Size(w, h), CornerRadius(w / 2, w / 2))
        }
    }
}

@Composable
fun LogoMark(size: Dp = 96.dp, animated: Boolean = true) {
    Box(
        Modifier.size(size).clip(CircleShape)
            .background(Brush.linearGradient(listOf(Brand.NeonBlue.copy(alpha = 0.25f), Brand.Teal.copy(alpha = 0.25f)))),
        contentAlignment = Alignment.Center,
    ) {
        Canvas(Modifier.size(size)) { drawCircle(Brand.Teal.copy(alpha = 0.6f), style = Stroke(width = 2.dp.toPx())) }
        Waveform(Brand.Teal, Modifier.size(size * 0.5f, size * 0.36f), active = animated)
    }
}

@Composable
fun LanguagePill(text: String, modifier: Modifier = Modifier, highlighted: Boolean = false) {
    Text(
        text, style = MaterialTheme.typography.labelLarge,
        color = if (highlighted) MaterialTheme.colorScheme.onSecondaryContainer else MaterialTheme.colorScheme.onSurface,
        modifier = modifier.clip(CircleShape)
            .background(if (highlighted) MaterialTheme.colorScheme.secondaryContainer else MaterialTheme.colorScheme.surfaceContainerHigh)
            .padding(horizontal = 14.dp, vertical = 8.dp),
    )
}

/** A conversation turn. Mine on the right (teal), theirs on the left (blue); clear pipeline state. */
@Composable
fun SubtitleBubble(turn: Turn, playing: Boolean, textScale: Float, myLabel: String, peerLabel: String, onRetry: (String) -> Unit) {
    val colors = LocalCallColors.current
    val accent = if (turn.mine) colors.me else colors.peer
    val container = if (turn.mine) colors.meContainer else colors.peerContainer
    Column(Modifier.fillMaxWidth(), horizontalAlignment = if (turn.mine) Alignment.End else Alignment.Start) {
        Text(if (turn.mine) myLabel else peerLabel, style = MaterialTheme.typography.labelMedium, color = accent,
            modifier = Modifier.padding(horizontal = 6.dp, vertical = 2.dp))
        Column(
            Modifier.fillMaxWidth(0.88f)
                .clip(RoundedCornerShape(20.dp, 20.dp, if (turn.mine) 6.dp else 20.dp, if (turn.mine) 20.dp else 6.dp))
                .background(container)
                .border(1.dp, if (playing) accent else accent.copy(alpha = 0.25f),
                    RoundedCornerShape(20.dp, 20.dp, if (turn.mine) 6.dp else 20.dp, if (turn.mine) 20.dp else 6.dp))
                .padding(14.dp)
                .semantics(mergeDescendants = true) {},
        ) {
            Text(turn.headline, fontSize = (19 * textScale).sp, lineHeight = (27 * textScale).sp, color = MaterialTheme.colorScheme.onSurface)
            turn.secondary?.let {
                Spacer(Modifier.height(6.dp))
                Text(if (turn.mine) "They hear: $it" else it, fontSize = (14 * textScale).sp, lineHeight = (20 * textScale).sp,
                    color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
            Spacer(Modifier.height(8.dp))
            TurnStatus(turn, playing, accent, onRetry)
        }
    }
}

@Composable
private fun TurnStatus(turn: Turn, playing: Boolean, accent: Color, onRetry: (String) -> Unit) {
    val muted = MaterialTheme.colorScheme.onSurfaceVariant
    Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(6.dp)) {
        when {
            playing || turn.stage == Stage.Speaking -> {
                Icon(Icons.AutoMirrored.Filled.VolumeUp, null, tint = accent, modifier = Modifier.size(16.dp))
                Text(if (turn.mine) "Playing translation to them" else "Playing translation", style = MaterialTheme.typography.labelMedium, color = accent)
            }
            turn.stage == Stage.Recognized || turn.stage == Stage.Translating -> {
                CircularProgressIndicator(Modifier.size(12.dp), strokeWidth = 1.5.dp, color = accent)
                Text("Translating…", style = MaterialTheme.typography.labelMedium, color = muted)
            }
            turn.stage == Stage.Failed -> {
                Text(turn.error ?: "Translation failed", style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.error,
                    modifier = Modifier.weight(1f, fill = false))
                TextButton(onClick = { onRetry(turn.id) }, contentPadding = PaddingValues(horizontal = 8.dp)) { Text("Retry") }
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
    val colors = LocalCallColors.current
    val accent = if (mine) colors.me else colors.peer
    Column(Modifier.fillMaxWidth(), horizontalAlignment = if (mine) Alignment.End else Alignment.Start) {
        Row(
            Modifier.clip(RoundedCornerShape(18.dp)).background(if (mine) colors.meContainer else colors.peerContainer)
                .padding(horizontal = 14.dp, vertical = 10.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Waveform(accent, Modifier.size(28.dp, 18.dp))
            Spacer(Modifier.width(10.dp))
            Text(label, style = MaterialTheme.typography.labelLarge, color = accent)
        }
    }
}

@Composable
fun FullScreenCentered(content: @Composable ColumnScope.() -> Unit) {
    Column(Modifier.fillMaxSize().padding(24.dp), verticalArrangement = Arrangement.Center, horizontalAlignment = Alignment.CenterHorizontally, content = content)
}

@Composable
fun scaledSp(base: Float, scale: Float): TextUnit = (base * scale).sp
