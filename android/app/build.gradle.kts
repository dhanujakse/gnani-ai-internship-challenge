import java.util.Properties

plugins {
    alias(libs.plugins.android.application)
    alias(libs.plugins.kotlin.compose)
    alias(libs.plugins.kotlin.serialization)
}
if (file("google-services.json").exists()) {
    apply(plugin = "com.google.gms.google-services")
}

// Backend address. Default set to Render cloud server so physical phones connect immediately.
// Override without editing code:  ./gradlew assembleDebug -PserverUrl=https://your-server.example
val serverUrl: String = (project.findProperty("serverUrl") as String?) ?: "https://sarvagyan-server.onrender.com"
// shown in the in-app privacy policy:  -PprivacyContact=privacy@your-domain
val privacyContact: String = (project.findProperty("privacyContact") as String?) ?: ""

// Release signing: android/keystore.properties (git-ignored) with storeFile, storePassword, keyAlias, keyPassword.
// See docs/PLAY_STORE.md. Without it, release builds fall back to the debug key (fine for testing, rejected by Play).
val keystore = Properties().apply {
    rootProject.file("keystore.properties").takeIf { it.exists() }?.inputStream()?.use { load(it) }
}

android {
    namespace = "ai.mack.sarvagyan"
    compileSdk = 36

    defaultConfig {
        applicationId = "ai.mack.sarvagyan"
        minSdk = 26
        targetSdk = 36
        versionCode = 1
        versionName = "1.0.0"
        testInstrumentationRunner = "androidx.test.runner.AndroidJUnitRunner"
        buildConfigField("String", "DEFAULT_SERVER_URL", "\"$serverUrl\"")
        buildConfigField("String", "PRIVACY_CONTACT", "\"$privacyContact\"")
        // phones (arm64, older 32-bit arm) and x86_64 emulators; drops unused WebRTC binaries
        ndk { abiFilters += listOf("arm64-v8a", "armeabi-v7a", "x86_64") }
    }

    signingConfigs {
        if (!keystore.isEmpty) create("upload") {
            storeFile = file(keystore.getProperty("storeFile"))
            storePassword = keystore.getProperty("storePassword")
            keyAlias = keystore.getProperty("keyAlias")
            keyPassword = keystore.getProperty("keyPassword")
        }
    }

    buildTypes {
        debug {
            applicationIdSuffix = ".debug"
            resValue("string", "app_name", "Sarvagyan (dev)")
        }
        release {
            isMinifyEnabled = true
            proguardFiles(getDefaultProguardFile("proguard-android-optimize.txt"), "proguard-rules.pro")
            resValue("string", "app_name", "Sarvagyan")
            // release builds must talk to an https/wss server (cleartext is blocked in release anyway)
            buildConfigField("String", "DEFAULT_SERVER_URL", "\"${if (serverUrl.startsWith("https://")) serverUrl else "https://sarvagyan.example"}\"")
            signingConfig = signingConfigs.getByName(if (keystore.isEmpty) "debug" else "upload")
        }
    }

    compileOptions {
        sourceCompatibility = JavaVersion.VERSION_17
        targetCompatibility = JavaVersion.VERSION_17
    }

    buildFeatures {
        compose = true
        buildConfig = true
        resValues = true
    }

    testOptions {
        unitTests.isReturnDefaultValues = true
    }
}

tasks.matching { it.name.startsWith("check") && it.name.endsWith("AarMetadata") }.configureEach {
    enabled = false
}

dependencies {
    implementation(libs.androidx.core.ktx)
    implementation(libs.androidx.activity.compose)
    implementation(libs.androidx.lifecycle.runtime.compose)
    implementation(libs.androidx.lifecycle.viewmodel.compose)
    implementation(libs.androidx.lifecycle.service)
    implementation(libs.androidx.navigation.compose)
    implementation(libs.androidx.datastore.preferences)
    implementation(libs.androidx.core.splashscreen)
    implementation(libs.androidx.biometric)
    implementation(platform(libs.compose.bom))
    implementation(libs.compose.ui)
    implementation(libs.compose.ui.tooling.preview)
    implementation(libs.compose.material3)
    implementation(libs.compose.icons.extended)
    implementation(libs.okhttp)
    implementation(libs.kotlinx.serialization.json)
    implementation(libs.kotlinx.coroutines.android)
    implementation(libs.webrtc)
    implementation("com.google.firebase:firebase-messaging:24.1.0")
    debugImplementation(libs.compose.ui.tooling)

    testImplementation(libs.junit)
    testImplementation(libs.kotlinx.coroutines.test)
}
