# Sarvagyan architecture

## Overview

```
 Phone A (speaks Tamil)                    Sarvagyan server (FastAPI)                     Phone B (speaks English)
 ───────────────────────                   ──────────────────────────                     ────────────────────────
 mic ─► WebRTC audio module ──────── original voice, peer-to-peer (WebRTC, STUN/TURN) ──────► speaker (quieter)
          │ samples callback
          ▼ 16 kHz, 1,024-byte frames
 echo gate ─► call WebSocket ──► SpeakerPipeline(A) ─► Prisma streaming STT (ta-IN)
                                     │ final transcript
                                     ▼
                                 MyMemory  ta → en
                                     │ translation
                                     ▼
                                 PlaybackDispatcher(B) ─► Timbre streaming TTS (en-IN, B's voice)
                                     │ PCM chunks
 subtitles ◄── utterance events ◄────┴──────────────── call WebSocket ──► TranslatedAudioPlayer ─► speaker
                                                                       └► subtitles
 (Replies from B follow the mirror path: B's mic → STT en-IN → en → ta → Timbre ta-IN → only A hears it.)
```

**Why this shape**
- **Original voices stay peer-to-peer.** WebRTC gives low-latency, echo-cancelled call audio and keeps natural
  turn-taking (you hear tone and timing). It is played quieter (35% by default) under the translation.
- **Translation runs on the server.** The Gnani key never reaches a phone, the server can enforce limits, and a phone
  only uploads 32 KB/s of 16 kHz PCM. It also means translation still works when a strict network blocks the
  direct WebRTC connection (no TURN configured): subtitles and translated voice still flow through the server.
- **Separate media paths.** Translated speech is a different stream (server → listener WebSocket → its own AudioTrack),
  so it is never sent back to the speaker and never enters the other person's speech recogniser.

## Components

| Piece | File | Responsibility |
|---|---|---|
| Call socket | `server/sarvagyan_server/main.py` (`/v1/calls/{id}/ws`) | Auth (Bearer token), hello, signalling relay, mic frames, events |
| CallRoom | `realtime.py` | Two participants max, reconnect grace (30 s), offer/answer roles, per-call state |
| SpeakerPipeline | `realtime.py` | One Prisma stream per speaker, started only while both are connected; reconnect with backoff; 14-min rotation |
| PlaybackDispatcher | `realtime.py` | One per listener; plays translations in order, one at a time; skips audio older than 12 s (subtitle still shown) |
| EchoGuard | `realtime.py` | Drops transcripts that match translated speech the listener heard in the last 20 s |
| Providers | `providers/*.py` | `SpeechRecognizer`, `Translator`, `SpeechSynthesizer` protocols; Gnani Prisma, MyMemory, Gnani Timbre |
| CallSession | `android/.../call/CallSession.kt` | Client state machine: socket, WebRTC, player, mic pipeline, reconnect |
| WebRtcEngine | `WebRtcEngine.kt` | PeerConnection, offer/answer/ICE, ICE restart, stats → quality |
| MicPipeline + EchoGate | `AudioFrames.kt` | Mono 16 kHz 1,024-byte frames; silence while translated speech plays |
| Conversation | `Conversation.kt` | Forward-only, id-keyed turn state (no duplicates, no stale overwrites) |

## Turn lifecycle (one utterance)

`speech_activity(active)` → **Listening** (waveform bubble) → Prisma VAD closes the segment →
`recognized` (original text shown) → `translating` → `translated` (subtitle) → `speaking` (listener's player) → `done`.
Failures: `failed` (translation error, Retry button) or `skipped` (audio too late; subtitle kept).
Every event carries `rev`; the client ignores anything older than what it shows.

## Latency (measured live, 29 Oct 2026, Tamil ↔ English, home broadband)

| Stage | Tamil → English | English → Tamil |
|---|---|---|
| Prisma STT after the speaker pauses (`stt_ms`) | 0.7–2.7 s | 0.8 s |
| MyMemory translation (`translate_ms`) | 1.2–1.3 s | 0.6 s |
| Timbre first audio chunk (`tts_first_ms`) | 0.75–0.9 s | 0.6 s |
| End of transcript → first translated audio leaves server (`server_total_ms`) | 2.0–2.2 s | 1.2 s |

Plus ~0.6 s of silence the VAD waits for before closing a sentence. Every subtitle shows its own delay, and
translations slower than 3 s are marked. Per-stage metrics are in each `utterance` event.

## Security and privacy
- Keys: server environment only (`.env`, git-ignored). The APK contains no key, secret or provider URL (verified).
- Auth: email + scrypt password, or demo guests when `DEMO_MODE=true`; HMAC-signed tokens; token on the phone encrypted
  with an Android Keystore AES-GCM key; tokens sent in headers, never URLs.
- Calls: only the creator and the person with the 6-character invite code can join (max 2); the socket rejects others (4404).
- Data: no audio is stored anywhere; the server stores users and call metadata (times, languages, counts) only;
  transcripts are kept only on the phone when the user opts in, and can be deleted.
- Network: release builds allow https/wss only; debug builds allow http to the emulator host for development.
- Logs: ids, durations and status codes only — never transcripts, translations, audio or keys.

## Limits and known gaps
- WebRTC needs a TURN server for some networks (symmetric NAT, many mobile carriers). Configure `TURN_URLS` etc.
  Without it, translation still works through the server, but the original voice may not connect.
- MyMemory free quota: 5,000 chars/day (50,000 with `MYMEMORY_EMAIL`). Swap in another `Translator` for production.
- Prisma has no partial transcripts: text appears when the speaker pauses (VAD), not word by word.
- Calls are inside Sarvagyan only; Android does not allow capturing other apps' or cellular call audio.
- No push notifications yet: the other person joins with the invite code (no ringing).
