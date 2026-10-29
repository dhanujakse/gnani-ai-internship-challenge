# Sarvagyan test report

Status as of 30 Oct 2026. "Verified" means it was actually run; nothing below is claimed from code reading alone.

## Automated tests

| Suite | Command | Result |
|---|---|---|
| Server, offline (fake AI providers) | `cd server && uv run pytest -q` | **43 passed** |
| Server, live (real Gnani + MyMemory) | `cd server && uv run pytest -m live -s` | **passed** (two-way Tamil ↔ English) |
| Android JVM unit tests | `cd android && ./gradlew :app:testDebugUnitTest` | **12 passed** |
| Android build | `./gradlew :app:assembleDebug` | **builds** (52 MB debug APK) |

## Required scenarios

| # | Scenario | Status | How |
|---|---|---|---|
| 1 | Launch the application | **Verified on emulator** | Android 15 emulator, debug APK |
| 2 | Navigate between screens | **Verified on emulator** | splash → onboarding → sign-in → home → call setup → active call → summary |
| 3 | Select Tamil and English | Partly | language chips in UI; server validates codes (tests) |
| 4 | Request microphone permission | Partly | in-app request + rationale implemented; on the emulator it was pre-granted via adb, so the system dialog itself was not exercised |
| 5 | Create a call | **Verified on emulator** | invite code WQMYST shown with Copy/Share; server tests too |
| 6 | Join a call from a second device | Verified with the test peer as second participant; **not with two physical phones** | `tools/test_peer.py`, `test_call_flow.py` |
| 7 | Transcribe Tamil speech | **Verified live** | real Tamil recording → Prisma v3.0 streaming: "நாளை பள்ளிக்கு விடுமுறை." |
| 8 | Translate Tamil into English | **Verified live** | → "the tution will remain closed tomorrow" (MyMemory) |
| 9 | Play translated English speech to the recipient | **Verified live (server → listener audio stream)** | 1.8 s of English PCM delivered to the listener only |
| 10 | Translate English responses into Tamil | **Verified live** | "Okay, I will call you back in 5 minutes." → "சரி, நான் உங்களை 5 நிமிடங்களில் திரும்ப அழைப்பேன்." + 3.4 s Tamil audio |
| 11 | Display live subtitles | **Verified on emulator** | English speech from the test peer appeared as Tamil subtitles with the original English and per-turn delay |
| 12 | Mute and unmute | Verified (server tests) | `test_mute_stops_translation_input`; button present in the app, not tapped in the emulator run |
| 13 | End the call | **Verified on emulator** (peer left → grace → summary) and server tests | the End button + confirm dialog were not tapped in the emulator run |
| 14 | Recover from a temporary network interruption | Verified (server) | socket drop keeps the seat 30 s, peer told "reconnecting", rejoin re-offers WebRTC with ICE restart |
| 15 | Handle an invalid API key | Verified | Gnani 401 → `auth` error with a clear message, call stays up (`test_stt_auth_failure_is_reported`, status mapping tests) |
| 16 | Handle unsupported languages | Verified | 422 on create/join, `unsupported_language` error mid-call |
| 17 | API secrets not exposed in the app | **Verified** | APK scanned: no Gnani key, no AUTH_SECRET, no `vach_` key pattern, not even provider URLs |
| 18 | Original audio not reprocessed as translated speech | Verified | separate media paths; client echo gate (unit test); server EchoGuard (`test_echo_of_translated_speech_is_not_retranslated`) |
| 19 | Both participants receive the correct translation | **Verified live + offline** | each listener gets the translation into *their* language with *their* voice; the speaker never receives synthetic audio |
| 20 | The project builds | **Verified** | Gradle 9.7.1, AGP 9.5.0, Kotlin 2.4.21, compileSdk 37.2 |

## Measured latency (live)

See [ARCHITECTURE.md](ARCHITECTURE.md#latency-measured-live-29-oct-2026-tamil--english-home-broadband). In short:
2.0–2.2 s (Tamil → English) and 1.2 s (English → Tamil) from the end of the transcript to the first translated
audio leaving the server, plus ~0.6 s VAD pause and speech-recognition time.

## Emulator run

Android 15 (AOSP x86_64) emulator, 2 GB RAM, on the development PC; server on the same PC; the second
participant was `tools/test_peer.py` (no WebRTC). Walkthrough on 30 Oct 2026:

1. Splash → onboarding (3 steps, Next / Get Started) → sign-in screen render correctly in the dark theme.
2. **Continue as guest (demo)** → home: "Connected", "Demo account" badge, Start a call, join-by-code, Tamil ⇄ English,
   honest empty states for favourites and recent calls. Server log: demo sign-in, languages, history, favourites all 200.
3. **Start a call → Create call** → active call in "waiting" state with invite code, link, Copy/Share, privacy notice,
   controls; Android's mic-in-use indicator on (foreground service running).
4. Test peer joined as "Ben" (English) and spoke twice. The phone showed both turns as **Tamil subtitles** with the English
   original and latency ("9.0 s · translation was slow", then "1.3 s"); the server streamed 3.4 s and 3.2 s of Tamil speech
   to the phone. Second turn: STT 0.3 s, translation 0.7 s, first voice audio 0.3 s.
5. Test peer exited → "Ben lost connection — waiting for them…" → after the 30 s grace the call ended → **Call summary**
   (2:24, 2 utterances, Tamil ↔ English, bilingual transcript, "not saved" note, Copy/Delete). Mic indicator went off.

Bugs found and fixed during this run: headings rendered black on the dark background (missing Surface content colour) and
dark status-bar icons on the dark theme.

Not covered by the emulator run: the original-voice WebRTC path (the test peer has no WebRTC, so the header correctly shows
"No direct audio"), hearing the translated audio (emulator started with `-no-audio`), the app user's own speech being
translated (needs a microphone), tapping Mute/End buttons.

## Not yet tested / known gaps

- **Two physical phones on different networks**, including the WebRTC original-voice path end to end on real
  hardware. The WebRTC code builds and follows the documented API, but peer-to-peer audio between two devices has
  not been exercised here (only one emulator could run on this machine). On mobile data a TURN server is likely needed.
- Bluetooth/headset routing and acoustic echo on real speakers (hardware echo cancellation varies by phone).
- Long calls (> 15 min Prisma session rotation is implemented and unit-covered, not soak-tested).
- MyMemory translation quality is modest for colloquial Tamil; the `Translator` interface allows swapping providers.
