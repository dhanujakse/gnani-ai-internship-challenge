package ai.mack.sarvagyan.call

import android.content.Context
import android.media.AudioDeviceInfo
import android.media.AudioManager
import android.os.Build

enum class AudioRoute(val label: String) { Speaker("Speaker"), Earpiece("Phone"), Headset("Headset"), Bluetooth("Bluetooth") }

/** Puts the device in communication mode and switches between speaker, earpiece, wired and Bluetooth headsets. */
class AudioRouter(context: Context) {
    private val am = context.getSystemService(Context.AUDIO_SERVICE) as AudioManager
    private var previousMode = AudioManager.MODE_NORMAL

    fun begin() {
        previousMode = am.mode
        am.mode = AudioManager.MODE_IN_COMMUNICATION
    }

    fun available(): List<AudioRoute> {
        if (Build.VERSION.SDK_INT < 31) return listOf(AudioRoute.Speaker, AudioRoute.Earpiece)
        return am.availableCommunicationDevices.mapNotNull { routeOf(it) }.distinct().sortedBy { it.ordinal }
    }

    fun current(): AudioRoute? {
        if (Build.VERSION.SDK_INT < 31) {
            @Suppress("DEPRECATION")
            return if (am.isSpeakerphoneOn) AudioRoute.Speaker else AudioRoute.Earpiece
        }
        return am.communicationDevice?.let { routeOf(it) }
    }

    fun select(route: AudioRoute): Boolean {
        if (Build.VERSION.SDK_INT < 31) {
            @Suppress("DEPRECATION")
            am.isSpeakerphoneOn = route == AudioRoute.Speaker
            return route == AudioRoute.Speaker || route == AudioRoute.Earpiece
        }
        val device = am.availableCommunicationDevices.firstOrNull { routeOf(it) == route } ?: return false
        return am.setCommunicationDevice(device)
    }

    fun end() {
        if (Build.VERSION.SDK_INT >= 31) am.clearCommunicationDevice() else {
            @Suppress("DEPRECATION")
            am.isSpeakerphoneOn = false
        }
        am.mode = previousMode
    }

    private fun routeOf(d: AudioDeviceInfo): AudioRoute? = when (d.type) {
        AudioDeviceInfo.TYPE_BUILTIN_SPEAKER -> AudioRoute.Speaker
        AudioDeviceInfo.TYPE_BUILTIN_EARPIECE -> AudioRoute.Earpiece
        AudioDeviceInfo.TYPE_WIRED_HEADSET, AudioDeviceInfo.TYPE_WIRED_HEADPHONES, AudioDeviceInfo.TYPE_USB_HEADSET -> AudioRoute.Headset
        AudioDeviceInfo.TYPE_BLUETOOTH_SCO, AudioDeviceInfo.TYPE_BLE_HEADSET -> AudioRoute.Bluetooth
        else -> null
    }
}
