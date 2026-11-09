package ai.mack.sarvagyan.call

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.media.AudioAttributes
import android.media.AudioDeviceCallback
import android.media.AudioDeviceInfo
import android.media.AudioFocusRequest
import android.media.AudioManager
import android.os.Build
import android.os.Handler
import android.os.Looper

enum class AudioRoute(val label: String) { Speaker("Speaker"), Earpiece("Phone"), Headset("Headset"), Bluetooth("Bluetooth") }

/**
 * Puts the device in communication mode, manages audio focus, and routes audio between
 * speaker, earpiece, wired headsets, and Bluetooth SCO/BLE devices across Android versions.
 */
class AudioRouter(private val context: Context, private val onRoutesChanged: ((AudioRouter) -> Unit)? = null) {
    private val am = context.getSystemService(Context.AUDIO_SERVICE) as AudioManager
    private val mainHandler = Handler(Looper.getMainLooper())
    private var previousMode = AudioManager.MODE_NORMAL
    private var focusRequest: AudioFocusRequest? = null
    private var desiredRoute: AudioRoute? = null
    private var isScoStarted = false

    private val deviceCallback = if (Build.VERSION.SDK_INT >= 23) {
        object : AudioDeviceCallback() {
            override fun onAudioDevicesAdded(addedDevices: Array<out AudioDeviceInfo>?) {
                handleDevicesChanged()
            }

            override fun onAudioDevicesRemoved(removedDevices: Array<out AudioDeviceInfo>?) {
                handleDevicesChanged()
            }
        }
    } else null

    private val wiredHeadsetReceiver = object : BroadcastReceiver() {
        override fun onReceive(c: Context?, intent: Intent?) {
            if (intent?.action == Intent.ACTION_HEADSET_PLUG) {
                handleDevicesChanged()
            }
        }
    }

    private fun handleDevicesChanged() {
        mainHandler.post {
            val avail = available()
            // If the desired route is no longer available, fall back to Speaker or Earpiece
            val current = desiredRoute
            if (current != null && !avail.contains(current)) {
                val fallback = if (avail.contains(AudioRoute.Earpiece)) AudioRoute.Earpiece else AudioRoute.Speaker
                select(fallback)
            } else if (current != null) {
                // Reapply in case Android shifted the default
                reapply()
            }
            onRoutesChanged?.invoke(this@AudioRouter)
        }
    }

    fun begin() {
        previousMode = am.mode
        requestAudioFocus()
        am.mode = AudioManager.MODE_IN_COMMUNICATION

        if (Build.VERSION.SDK_INT >= 23 && deviceCallback != null) {
            am.registerAudioDeviceCallback(deviceCallback, mainHandler)
        }
        try {
            val filter = IntentFilter(Intent.ACTION_HEADSET_PLUG)
            context.registerReceiver(wiredHeadsetReceiver, filter)
        } catch (_: Exception) {}
    }

    private fun requestAudioFocus() {
        try {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                val attrs = AudioAttributes.Builder()
                    .setUsage(AudioAttributes.USAGE_VOICE_COMMUNICATION)
                    .setContentType(AudioAttributes.CONTENT_TYPE_SPEECH)
                    .build()
                val req = AudioFocusRequest.Builder(AudioManager.AUDIOFOCUS_GAIN_TRANSIENT)
                    .setAudioAttributes(attrs)
                    .setAcceptsDelayedFocusGain(true)
                    .setOnAudioFocusChangeListener { /* maintain communication focus */ }
                    .build()
                focusRequest = req
                am.requestAudioFocus(req)
            } else {
                @Suppress("DEPRECATION")
                am.requestAudioFocus(
                    null,
                    AudioManager.STREAM_VOICE_CALL,
                    AudioManager.AUDIOFOCUS_GAIN_TRANSIENT
                )
            }
        } catch (_: Exception) {}
    }

    fun available(): List<AudioRoute> {
        val list = mutableListOf(AudioRoute.Speaker)
        if (Build.VERSION.SDK_INT >= 31) {
            val commDevices = am.availableCommunicationDevices
            for (d in commDevices) {
                val r = routeOf(d)
                if (r != null && !list.contains(r)) list.add(r)
            }
        } else if (Build.VERSION.SDK_INT >= 23) {
            val devices = am.getDevices(AudioManager.GET_DEVICES_OUTPUTS)
            var hasEarpiece = false
            var hasHeadset = false
            var hasBt = false
            for (d in devices) {
                when (d.type) {
                    AudioDeviceInfo.TYPE_BUILTIN_EARPIECE -> hasEarpiece = true
                    AudioDeviceInfo.TYPE_WIRED_HEADSET, AudioDeviceInfo.TYPE_WIRED_HEADPHONES, AudioDeviceInfo.TYPE_USB_HEADSET -> hasHeadset = true
                    AudioDeviceInfo.TYPE_BLUETOOTH_SCO, AudioDeviceInfo.TYPE_BLE_HEADSET, AudioDeviceInfo.TYPE_BLUETOOTH_A2DP -> hasBt = true
                }
            }
            if (hasEarpiece) list.add(AudioRoute.Earpiece)
            if (hasHeadset) list.add(AudioRoute.Headset)
            if (hasBt) list.add(AudioRoute.Bluetooth)
        } else {
            list.add(AudioRoute.Earpiece)
        }
        return list.sortedBy { it.ordinal }
    }

    fun current(): AudioRoute? {
        if (Build.VERSION.SDK_INT >= 31) {
            val dev = am.communicationDevice
            if (dev != null) return routeOf(dev)
        }
        @Suppress("DEPRECATION")
        if (am.isBluetoothScoOn) return AudioRoute.Bluetooth
        @Suppress("DEPRECATION")
        if (am.isSpeakerphoneOn) return AudioRoute.Speaker
        return desiredRoute ?: AudioRoute.Earpiece
    }

    fun select(route: AudioRoute): Boolean {
        desiredRoute = route
        return applyRoute(route)
    }

    fun reapply() {
        desiredRoute?.let { applyRoute(it) }
    }

    private fun applyRoute(route: AudioRoute): Boolean {
        if (Build.VERSION.SDK_INT >= 31) {
            val target = am.availableCommunicationDevices.firstOrNull { routeOf(it) == route }
            if (target != null) {
                val ok = am.setCommunicationDevice(target)
                @Suppress("DEPRECATION")
                am.isSpeakerphoneOn = (route == AudioRoute.Speaker)
                return ok
            }
            // Fallback for speaker on API 31+ if not found in communication devices
            if (route == AudioRoute.Speaker) {
                @Suppress("DEPRECATION")
                am.isSpeakerphoneOn = true
                return true
            }
            return false
        }

        // Pre-Android 12
        return when (route) {
            AudioRoute.Speaker -> {
                stopSco()
                @Suppress("DEPRECATION")
                am.isSpeakerphoneOn = true
                true
            }
            AudioRoute.Earpiece -> {
                stopSco()
                @Suppress("DEPRECATION")
                am.isSpeakerphoneOn = false
                true
            }
            AudioRoute.Headset -> {
                stopSco()
                @Suppress("DEPRECATION")
                am.isSpeakerphoneOn = false
                true
            }
            AudioRoute.Bluetooth -> {
                @Suppress("DEPRECATION")
                am.isSpeakerphoneOn = false
                startSco()
                true
            }
        }
    }

    private fun startSco() {
        try {
            if (!isScoStarted) {
                @Suppress("DEPRECATION")
                am.startBluetoothSco()
                @Suppress("DEPRECATION")
                am.isBluetoothScoOn = true
                isScoStarted = true
            }
        } catch (_: Exception) {}
    }

    private fun stopSco() {
        try {
            if (isScoStarted) {
                @Suppress("DEPRECATION")
                am.isBluetoothScoOn = false
                @Suppress("DEPRECATION")
                am.stopBluetoothSco()
                isScoStarted = false
            }
        } catch (_: Exception) {}
    }

    fun end() {
        stopSco()
        try {
            if (Build.VERSION.SDK_INT >= 23 && deviceCallback != null) {
                am.unregisterAudioDeviceCallback(deviceCallback)
            }
            context.unregisterReceiver(wiredHeadsetReceiver)
        } catch (_: Exception) {}

        if (Build.VERSION.SDK_INT >= 31) {
            am.clearCommunicationDevice()
        } else {
            @Suppress("DEPRECATION")
            am.isSpeakerphoneOn = false
        }

        try {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O && focusRequest != null) {
                am.abandonAudioFocusRequest(focusRequest!!)
            } else {
                @Suppress("DEPRECATION")
                am.abandonAudioFocus(null)
            }
        } catch (_: Exception) {}

        am.mode = previousMode
    }

    private fun routeOf(d: AudioDeviceInfo): AudioRoute? = when (d.type) {
        AudioDeviceInfo.TYPE_BUILTIN_SPEAKER -> AudioRoute.Speaker
        AudioDeviceInfo.TYPE_BUILTIN_EARPIECE -> AudioRoute.Earpiece
        AudioDeviceInfo.TYPE_WIRED_HEADSET, AudioDeviceInfo.TYPE_WIRED_HEADPHONES, AudioDeviceInfo.TYPE_USB_HEADSET, AudioDeviceInfo.TYPE_USB_DEVICE -> AudioRoute.Headset
        AudioDeviceInfo.TYPE_BLUETOOTH_SCO, AudioDeviceInfo.TYPE_BLE_HEADSET, AudioDeviceInfo.TYPE_BLUETOOTH_A2DP -> AudioRoute.Bluetooth
        else -> null
    }
}
