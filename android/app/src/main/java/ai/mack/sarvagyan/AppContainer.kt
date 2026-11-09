package ai.mack.sarvagyan

import android.app.Application
import android.content.Context
import ai.mack.sarvagyan.call.AppSocket
import ai.mack.sarvagyan.call.CallSession
import ai.mack.sarvagyan.call.CallStatus
import ai.mack.sarvagyan.call.IncomingCall
import ai.mack.sarvagyan.call.Ringer
import ai.mack.sarvagyan.data.int
import ai.mack.sarvagyan.data.objOrNull
import ai.mack.sarvagyan.data.str
import kotlinx.coroutines.flow.collectLatest
import kotlinx.coroutines.flow.distinctUntilChanged
import kotlinx.coroutines.flow.map
import kotlinx.serialization.json.JsonObject
import ai.mack.sarvagyan.data.ApiClient
import ai.mack.sarvagyan.data.ApiException
import ai.mack.sarvagyan.data.Session
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
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
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
    val api = ApiClient(http, json, baseUrl = { settings.value.serverUrl }, token = { tokens.get() },
        refresh = { stale -> refreshSession(stale) })
    private val refreshLock = Mutex()

    val user = MutableStateFlow<User?>(null)
    val languages = MutableStateFlow(FallbackLanguages)
    val activeCall = MutableStateFlow<CallSession?>(null)
    val incomingCall = MutableStateFlow<IncomingCall?>(null)
    val appSocket = AppSocket(http, json, api)
    private val ringer = Ringer(context)

    init {
        // the always-on connection runs while someone is signed in; incoming calls arrive through it
        scope.launch { user.map { it?.id }.distinctUntilChanged().collectLatest { id -> if (id != null) appSocket.run() } }
        scope.launch { appSocket.events.collect { onAppEvent(it) } }
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

    fun saveSession(session: Session) {
        tokens.set(session.token)
        tokens.setRefresh(session.refreshToken.ifEmpty { null })
        user.value = session.user
    }

    /** Swaps the refresh token for a new pair. One refresh at a time; a refresh another caller just did counts. */
    suspend fun refreshSession(stale: String?): Boolean = refreshLock.withLock {
        val now = tokens.get()
        if (now != null && now != stale) return@withLock true
        val refreshToken = tokens.getRefresh() ?: return@withLock false
        try {
            saveSession(api.refreshTokens(refreshToken))
            true
        } catch (e: ApiException) {
            if (e.isAuth) { tokens.clear(); user.value = null } // session ended (signed out elsewhere)
            false
        }
    }

    /** After the account was deleted: forget it on this phone (the server session is already gone). */
    fun forgetAccount() {
        tokens.clear()
        user.value = null
    }

    fun signOut() {
        val token = tokens.get()
        tokens.clear()
        user.value = null
        if (token != null) scope.launch { runCatching { api.logout(token) } } // ends the session on the server too
    }

    private fun inCall(): Boolean = activeCall.value?.state?.value?.status?.let { it != CallStatus.Ended && it != CallStatus.Failed } == true

    private fun onAppEvent(ev: JsonObject) {
        val callId = ev.str("call_id") ?: return
        when (ev.str("type")) {
            "incoming_call" -> {
                if (inCall()) { scope.launch { runCatching { api.declineCall(callId) } }; return } // busy
                val from = ev.objOrNull("from") ?: return
                val call = IncomingCall(callId, from.str("id") ?: return, from.str("name") ?: "Someone", from.str("username"),
                    from.str("language") ?: "en-IN", ev.int("expires_in") ?: 30)
                incomingCall.value = call
                ringer.start(call.fromName, call.expiresInS * 1000L)
            }
            "call_cancelled" -> if (incomingCall.value?.callId == callId) {
                incomingCall.value = null
                ringer.stop()
            }
            "call_declined", "call_missed" -> activeCall.value?.takeIf { it.info.callId == callId }?.let { session ->
                val name = ev.str("peer_name") ?: session.info.peerName ?: "They"
                session.markUnanswered(if (ev.str("type") == "call_declined") "$name declined the call." else "$name didn't answer.")
            }
        }
    }

    /** Rings a person; the call screen shows "Ringing" until they answer, decline or miss it. */
    suspend fun callPerson(id: String, name: String): CallSession {
        val lang = settings.value.myLanguage
        return startCall(api.callPerson(id, lang), lang)
    }

    suspend fun answerIncoming(): CallSession {
        val call = incomingCall.value ?: throw ApiException(404, "The call has ended.")
        ringer.stop()
        incomingCall.value = null
        val lang = settings.value.myLanguage
        return startCall(api.answerCall(call.callId, lang), lang)
    }

    suspend fun declineIncoming() {
        val call = incomingCall.value ?: return
        ringer.stop()
        incomingCall.value = null
        runCatching { api.declineCall(call.callId) }
    }

    suspend fun startCall(info: CallInfo, myLanguage: String, initialRoute: ai.mack.sarvagyan.call.AudioRoute? = null): CallSession {
        activeCall.value?.end(notifyServer = true)
        val session = CallSession(context, api, http, json, transcripts, info, settings.value, myLanguage)
        activeCall.value = session
        CallService.start(context)
        session.start(initialRoute)
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
