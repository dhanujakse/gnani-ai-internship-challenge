package ai.mack.sarvagyan

import android.app.Application
import android.content.Context
import ai.mack.sarvagyan.call.CallSession
import ai.mack.sarvagyan.data.ApiClient
import ai.mack.sarvagyan.data.AppSettings
import ai.mack.sarvagyan.data.CallInfo
import ai.mack.sarvagyan.data.FallbackLanguages
import ai.mack.sarvagyan.data.Language
import ai.mack.sarvagyan.data.SettingsStore
import ai.mack.sarvagyan.data.TokenStore
import ai.mack.sarvagyan.data.TranscriptStore
import ai.mack.sarvagyan.data.User
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.launch
import kotlinx.serialization.json.Json
import okhttp3.OkHttpClient
import java.util.concurrent.TimeUnit

/** Manual dependency container: one instance per process, created by [SarvagyanApp]. */
class AppContainer(private val context: Context) {
    val scope = CoroutineScope(SupervisorJob() + Dispatchers.Default)
    val json = Json { ignoreUnknownKeys = true; explicitNulls = false }
    val http: OkHttpClient = OkHttpClient.Builder()
        .connectTimeout(10, TimeUnit.SECONDS)
        .readTimeout(30, TimeUnit.SECONDS)
        .pingInterval(15, TimeUnit.SECONDS) // keeps the call socket alive through NATs and detects drops
        .build()
    val settingsStore = SettingsStore(context)
    val settings: StateFlow<AppSettings> = settingsStore.settings.stateIn(scope, SharingStarted.Eagerly, AppSettings())
    val tokens = TokenStore(context)
    val transcripts = TranscriptStore(context, json)
    val api = ApiClient(http, json, baseUrl = { settings.value.serverUrl }, token = { tokens.get() })

    val user = MutableStateFlow<User?>(null)
    val languages = MutableStateFlow(FallbackLanguages)
    val activeCall = MutableStateFlow<CallSession?>(null)

    init {
        scope.launch { settingsStore.cachedLanguages(json)?.let { languages.value = it } }
    }

    suspend fun refreshLanguages() {
        runCatching { api.languages().languages }.onSuccess {
            if (it.isNotEmpty()) {
                languages.value = it
                settingsStore.cacheLanguages(json, it)
            }
        }
    }

    fun language(code: String): Language? = languages.value.firstOrNull { it.code == code }

    /** Keeps the server's copy of my language in step, so voicemails to me are translated into it. */
    suspend fun syncLanguage() {
        val mine = settings.value.myLanguage
        val me = user.value ?: runCatching { api.me() }.getOrNull()?.also { user.value = it } ?: return
        if (me.language != mine) runCatching { api.updateMe(language = mine) }.onSuccess { user.value = it }
    }

    fun signOut() {
        tokens.set(null)
        user.value = null
    }

    suspend fun startCall(info: CallInfo, myLanguage: String): CallSession {
        activeCall.value?.end(notifyServer = true)
        val session = CallSession(context, api, http, json, transcripts, info, settings.value, myLanguage)
        activeCall.value = session
        CallService.start(context)
        session.start()
        return session
    }
}

class SarvagyanApp : Application() {
    lateinit var container: AppContainer
        private set

    override fun onCreate() {
        super.onCreate()
        container = AppContainer(this)
    }
}

val Context.container: AppContainer get() = (applicationContext as SarvagyanApp).container
