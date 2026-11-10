package ai.mack.sarvagyan.ui.screens

import android.widget.Toast
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import ai.mack.sarvagyan.container
import ai.mack.sarvagyan.data.ApiException
import ai.mack.sarvagyan.ui.components.AppCard
import ai.mack.sarvagyan.ui.components.PrimaryButton
import kotlinx.coroutines.launch

/**
 * "Your phone number": lets friends who have you in their phone contacts find you in Discover from Phone.
 * Only a SHA-256 fingerprint of the number leaves the phone (the server seals it again with its own secret);
 * the number itself is never sent or stored.
 */
@Composable
fun MyNumberCard() {
    val context = LocalContext.current
    val c = context.container
    val scope = rememberCoroutineScope()
    val user by c.user.collectAsStateWithLifecycle()
    var number by remember { mutableStateOf("") }
    var busy by remember { mutableStateOf(false) }
    val added = user?.phoneAdded == true

    fun save(hash: String, done: String) {
        busy = true
        scope.launch {
            try {
                c.user.value = c.api.updateMe(phoneHash = hash)
                number = ""
                Toast.makeText(context, done, Toast.LENGTH_SHORT).show()
            } catch (e: ApiException) {
                Toast.makeText(context, e.message, Toast.LENGTH_LONG).show()
            } finally { busy = false }
        }
    }

    AppCard {
        Text("Your phone number", style = MaterialTheme.typography.titleMedium)
        Spacer(Modifier.height(4.dp))
        if (added) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text("Added. Friends who have your number can find you here.", Modifier.weight(1f),
                    style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
                Spacer(Modifier.width(8.dp))
                TextButton(onClick = { save("", "Your number was removed.") }, enabled = !busy) { Text("Remove") }
            }
        } else {
            Text("Add it so friends who have you in their contacts can find you. Only a scrambled fingerprint of it is sent, never the number.",
                style = MaterialTheme.typography.bodyMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
            Spacer(Modifier.height(8.dp))
            OutlinedTextField(number, { number = it.filter { ch -> ch.isDigit() || ch in "+ -" }.take(20) },
                label = { Text("Mobile number, e.g. 98765 43210") }, singleLine = true, modifier = Modifier.fillMaxWidth(),
                keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Phone))
            Spacer(Modifier.height(8.dp))
            PrimaryButton("Add my number", {
                val e164 = normalizePhoneE164(number, "+91")
                if (e164 == null) Toast.makeText(context, "Enter a full mobile number.", Toast.LENGTH_SHORT).show()
                else save(sha256Hex(e164), "Added. Friends can now find you.")
            }, Modifier.fillMaxWidth(), enabled = !busy)
        }
    }
}
