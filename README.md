# Sarvagyan — Real-Time Multilingual Communication & Live Call Translation
> **Gnani AI Internship Challenge Solution**
> *Speak Naturally. Understand Everyone.*

Sarvagyan is a real-time multilingual communication application supporting **live bi-directional call translation**, group chat with auto-translation, and translated voicemails. Each participant speaks their native tongue; the recipient hears natural synthesized speech and reads synchronized live subtitles in their chosen language—continuously, both ways, with zero manual push-to-talk gating.

Built natively on **Gnani Prisma** (streaming WebSocket STT), **Gnani Timbre** (synthesized neural TTS), **MyMemory / Google Translate fallback**, and **WebRTC** for peer media streaming.

---

## 🚀 Live Cloud Deployment & Ready APK

- **Live Server**: `https://sarvagyan-server.onrender.com` (`/health` status: `ok`)
- **Ready Android APK**: [`Sarvagyan.apk`](Sarvagyan.apk) (54.2 MB, pre-configured with Render cloud backend)
- **Install on Device**:
  ```powershell
  adb install -r Sarvagyan.apk
  ```

---

## 🛠️ Tech Stack & Architecture

```
sarvagyan_call_transulater/
├── android/            # Native Android Client (Kotlin 2.1, Jetpack Compose, Material 3, WebRTC, DataStore)
├── server/             # High-Performance Backend (Python 3.11+, FastAPI, WebSockets, SQLite, Uvicorn)
├── docs/               # System Architecture, Deployment & Security Documentation
└── Sarvagyan.apk       # Ready-to-install compiled Android application
```

- **Speech-to-Text (STT)**: Gnani Prisma v3.0 (streaming 16kHz PCM audio over WebSocket)
- **Text-to-Speech (TTS)**: Gnani Timbre v2.5 (neural multi-voice synthesis per language)
- **Translation Pipeline**: Multi-tier pipeline with curated phrasebook, Google Translate fallback, and troll-filtering translation memory
- **Audio Processing**: WebRTC AEC/NS/AGC platform effects + custom Energy VAD gating
- **Signalling & Real-Time**: FastAPI asynchronous WebSocket channels with connection failover and audio buffer flushes

---

## 🎯 Gnani AI Challenge Tasks & Solutions

| Task | Challenge | Root Cause Identified | Implemented Solution | Verification Status |
| :--- | :--- | :--- | :--- | :---: |
| **Task 1: Username Search** | Searching for another account's username returned nothing. | 1. FastAPI query param defaulted to non-optional `q: str = Query(...)`, rejecting empty queries.<br>2. SQLite had no normalized index on lowercase usernames.<br>3. Search results did not filter out the caller's own ID. | Added indexed `username_norm` with startup auto-backfill. Updated query parsing to strip `@`, trim whitespace, and support prefix & exact matching. Return only `{id, display_name, username, avatar}` and exclude self. Added "No users found" UI state. | **Verified** (`test_username_search.py`) |
| **Task 2: Contact Sync** | With 375 contacts, only part loaded/synced. | 1. `ContactsScreens.kt:395` had a hardcoded `take(50)` slice.<br>2. Phone number formatting was inconsistent across contacts.<br>3. No progress tracking or batching existed. | Removed slice limit. Implemented `normalizePhoneE164()` with `+91` default region. Added chunked matching in batches of 100 with progress UI (`"Synced X of Y"`). Send SHA-256 hashes for privacy. Added count reconciliation logging (`numbersRead == normalized + failed`). | **Verified** (`test_contact_sync.py` with 375 contacts) |
| **Task 3: Language Selection** | Tamil was hardcoded default at signup/guest. | Tamil (`ta-IN`) was hardcoded as default in schema, `Stores.kt`, and `FallbackLanguages`. | Removed default language. Added mandatory `LanguagePickerField` ("Which language do you speak?") to both Create Account and Guest Demo with **no pre-selected option**. Submit button remains disabled until choice is made. Profile saves language for calls, chat, and voicemail. Populated all 10 supported Indian languages in fallback config. | **Verified** (`test_language_selection.py`) |
| **Task 4: Mid-Call Language Switch** | Could not change speaking language during an active call. | Call UI lacked mid-call language switch control; Gnani Prisma STT requires WebSocket handshake headers with language code. | Added in-call Language button and clickable `"You: <Language> ▾"` badge. Implemented `LanguageSheet` modal. Flushes pending audio buffer, reconfigures STT stream cleanly without dropping WebRTC call, and broadcasts peer notice (`"X switched to English"`). Measured switch gap: **2 ms**. | **Verified** (`test_midcall_language_switch.py`) |
| **Task 5: Noise Reduction** | Background noise and clicks caused STT hallucinations. | Raw microphone PCM was streamed without energy gating or platform suppression filters. | Enabled Android hardware `NoiseSuppressor`, `AcousticEchoCanceler`, and `AutomaticGainControl`. Added RMS Energy VAD gate (350 RMS threshold, 200ms minimum speech duration to drop clicks/pops, 350ms hangover). Added "Noise reduction" toggle under Settings -> Calls -> Audio (ON by default). | **Verified** (`test_noise_reduction.py` with synthetic audio sample) |
| **Task 6: Translation Vandalism** | Saying `"hey"` translated to `"I love you"`. | MyMemory crowd-sourced translation memory contained a vandalized match (`"hey"` -> `"ஐ லவ் யூ டார்லிங்"`). | Added `_TROLL_PATTERNS` regex filter in `choose_translation` rejecting romantic/troll submissions when input lacks love/darling. Enforced strict length ratio for short words ($\le 5$ chars). Added prioritized phrasebook lookup mapping `"hey"` directly to `"ஹேய்"`. | **Verified** (`test_hey_translation.py`) |

---

## 🗣️ Supported Languages

Sarvagyan supports **10 Indian languages** natively across speech-to-text, translation, and neural voices:

| # | Code | English Name | Native Script | Timbre v2.5 Neural Voices |
| :-: | :--- | :--- | :--- | :--- |
| 1 | `ta-IN` | Tamil | தமிழ் | Trisha, Asmita, Brinda, Vedika, Noopur |
| 2 | `en-IN` | English | English | Kaveri, Pranav, Trupti, Devika, Shlok, Girish |
| 3 | `hi-IN` | Hindi | हिन्दी | Nalini, Deepak, Bhavna, Chitra, Roopesh, Urmila |
| 4 | `te-IN` | Telugu | తెలుగు | Lavanya, Suhana, Lehara |
| 5 | `kn-IN` | Kannada | ಕನ್ನಡ | Kavin, Saanvi |
| 6 | `ml-IN` | Malayalam | മലയാളം | Reshma, Riyaan |
| 7 | `mr-IN` | Marathi | मराठी | Ishaan |
| 8 | `bn-IN` | Bengali | বাংলা | Kirra, Dhruva |
| 9 | `gu-IN` | Gujarati | ગુજરાતી | Falak |
| 10 | `pa-IN` | Punjabi | ਪੰਜਾਬੀ | Mehuli |

---

## 🧪 Automated Test Suite

Run the complete test suite verifying all 6 challenge tasks:

```bash
cd server
python -m pytest tests/test_username_search.py \
                 tests/test_contact_sync.py \
                 tests/test_language_selection.py \
                 tests/test_midcall_language_switch.py \
                 tests/test_noise_reduction.py \
                 tests/test_hey_translation.py -v
```

**Results**: `6 passed in 5.07s` (100% pass rate).

---

## 📱 Quickstart: Running Locally

### 1. Backend Server
```bash
cp .env.example .env    # Configure GNANI_API_KEY
cd server
pip install -r requirements.txt  # Or: uv sync
python -m uvicorn sarvagyan_server.main:app --host 0.0.0.0 --port 8787
```

### 2. Android Client
```bash
cd android
./gradlew assembleDebug
# Generated APK will be at android/app/build/outputs/apk/debug/app-debug.apk
```

---

## 📄 License
MIT License — see [LICENSE](LICENSE). Gnani APIs and WebRTC libraries are used under their respective terms.
