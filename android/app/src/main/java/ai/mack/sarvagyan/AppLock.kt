package ai.mack.sarvagyan

import android.content.Context
import android.os.Build
import androidx.biometric.BiometricManager
import androidx.biometric.BiometricManager.Authenticators.BIOMETRIC_STRONG
import androidx.biometric.BiometricManager.Authenticators.BIOMETRIC_WEAK
import androidx.biometric.BiometricManager.Authenticators.DEVICE_CREDENTIAL
import androidx.biometric.BiometricPrompt
import androidx.core.content.ContextCompat
import androidx.fragment.app.FragmentActivity

/**
 * App lock: the phone's own fingerprint, face or screen-lock PIN/pattern guards Sarvagyan. No separate PIN is
 * stored by the app; Android does the checking.
 */
object AppLock {
    const val RELOCK_AFTER_MS = 30_000L

    // strong biometrics or the device PIN on Android 11+; older versions only accept "weak" with the device PIN
    private val authenticators = if (Build.VERSION.SDK_INT >= 30) BIOMETRIC_STRONG or DEVICE_CREDENTIAL else BIOMETRIC_WEAK or DEVICE_CREDENTIAL

    /** True when the phone has a screen lock or enrolled biometrics, so the lock can be turned on. */
    fun available(context: Context): Boolean =
        BiometricManager.from(context).canAuthenticate(authenticators) == BiometricManager.BIOMETRIC_SUCCESS

    fun prompt(activity: FragmentActivity, onUnlocked: () -> Unit) {
        val prompt = BiometricPrompt(activity, ContextCompat.getMainExecutor(activity), object : BiometricPrompt.AuthenticationCallback() {
            override fun onAuthenticationSucceeded(result: BiometricPrompt.AuthenticationResult) = onUnlocked()
        })
        prompt.authenticate(
            BiometricPrompt.PromptInfo.Builder()
                .setTitle("Unlock Sarvagyan")
                .setSubtitle("Use your fingerprint, face or phone PIN")
                .setAllowedAuthenticators(authenticators)
                .build(),
        )
    }
}
