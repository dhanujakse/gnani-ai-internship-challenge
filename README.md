# Sarvagyan — Real-Time Translation Calling

**Speak Naturally. Understand Everyone.** · by MACK AI

Sarvagyan is an Android calling app for two people who don't share a language. Each person speaks their own
language; the other hears a natural translated voice and reads live subtitles — both ways, continuously,
without pressing a translate button. Tamil ↔ English first; Hindi, Telugu, Kannada, Malayalam, Marathi,
Bengali, Gujarati and Punjabi also work.

Built on **Gnani Prisma** (streaming speech-to-text), **Gnani Timbre** (streaming text-to-speech) and
**MyMemory** (translation), with **WebRTC** for the call itself.

- How it works: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)
- What is tested, what works, what remains: [docs/TESTING.md](docs/TESTING.md)

## Repository

```
android/   Android app (Kotlin, Jetpack Compose, Material 3, WebRTC)
server/    Backend (Python 3.11, FastAPI): auth, calls, signalling, translation pipeline
docs/      Architecture and test report
.env.example   Server configuration template (placeholders only)
```

## 1. Run the server

Requirements: Python 3.11 and [uv](https://docs.astral.sh/uv/).

```bash
cp .env.example .env          # then fill in GNANI_API_KEY and AUTH_SECRET
cd server
uv sync
uv run pytest -q              # 43 offline tests (no API calls)
uv run pytest -m live -s      # optional: one real two-way Tamil<->English call through the pipeline
uv run uvicorn sarvagyan_server.main:app --host 0.0.0.0 --port 8787
```

### Environment configuration (`.env`, never committed)

| Variable | Required | Purpose |
|---|---|---|
| `GNANI_API_KEY` | yes | Gnani Speech APIs key (Prisma STT + Timbre TTS) |
| `AUTH_SECRET` | yes in production | Signs login tokens; long random string. Without it, tokens reset on restart. |
| `MYMEMORY_EMAIL` | recommended | Raises MyMemory's free quota from 5,000 to 50,000 chars/day |
| `DEMO_MODE` | – | `true` allows "Continue as guest". Set `false` in production. |
| `STUN_URLS` | – | Default `stun:stun.l.google.com:19302` |
| `TURN_URLS`, `TURN_USERNAME`, `TURN_CREDENTIAL` | for mobile networks | A TURN relay (e.g. coturn, or a hosted TURN service) so WebRTC connects behind strict NATs |
| `DATA_DIR` | – | SQLite location (users and call metadata only) |

For phones on another network, deploy the server behind **HTTPS** (any host that supports WebSockets — e.g. a VM with
Caddy/nginx, Fly.io, Render, Railway) and build the app with `-PserverUrl=https://your-server`.

## 2. Build and run the app

Requirements: JDK 17+ (21 works), Android SDK with platform **android-37.2** (the current AndroidX/Compose releases
require it; `sdkmanager "platforms;android-37.2"`), a phone or emulator on Android 8.0+.

```bash
cd android
./gradlew :app:testDebugUnitTest          # 12 JVM unit tests
./gradlew :app:assembleDebug              # app/build/outputs/apk/debug/app-debug.apk
# emulator talking to a server on this PC (default):   http://10.0.2.2:8787
# phones on your Wi-Fi: ./gradlew :app:assembleDebug -PserverUrl=http://<your-pc-ip>:8787  (debug builds only)
# release (https only): ./gradlew :app:assembleRelease -PserverUrl=https://your-server
```

The server address can also be changed in the app: **Settings → Connection and diagnostics** (or "Server settings"
on the sign-in screen). **Run diagnostics** there checks the server, the Gnani key, speech recognition, translation
and whether a TURN server is configured.

## 3. Make a call

1. Phone A: sign in (or **Continue as guest** in demo mode) → pick *I speak: Tamil* → **Start a call** → share the code.
2. Phone B: sign in → *I speak: English* → **Join with an invitation code**.
3. Talk. A's Tamil is heard by B in English (plus subtitles); B's English reply is heard by A in Tamil.

**Only one phone?** Use the development test peer, which joins as the second participant and speaks a recorded clip:

```bash
cd server
uv run python tools/test_peer.py --join <CODE> --language en-IN --say tests/fixtures/en_call_back_pranav.wav
```

## Features

- Two-person calls inside the app: create, join by code or link (`sarvagyan://join/CODE`), reconnect after network
  drops (30 s grace, ICE restart), clean hang-up and call timeouts.
- Continuous translation in both directions with live subtitles that show each turn's state: *listening →
  translating → translated → playing* (and *failed — Retry* / *skipped*), with per-turn latency.
- Controls: mute, speaker/earpiece/headset/Bluetooth, translated voice on/off (subtitles only), original-voice volume,
  subtitle size, focus vs full transcript, mid-call language change, automatic language detection.
- Email accounts or clearly labelled demo guests; recent calls and favourites from real call history only.
- Privacy: no recording; transcripts only on the phone and only if you opt in; copy/delete in the call summary.
- Dark theme by default (deep navy, neon blue and teal), light/system themes, accessible labels.

## Licence

MIT — see [LICENSE](LICENSE). Gnani, MyMemory and WebRTC are used under their own terms.
