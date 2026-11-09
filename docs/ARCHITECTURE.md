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
- Auth: email + scrypt password, or demo guests when `DEMO_MODE=true`. Each sign-in creates a server-side session.
  Access tokens (HMAC-signed) last 15 minutes and name their session, so ending a session cuts access at once.
  Refresh tokens are random, stored only as SHA-256 hashes, replaced on every use; a replaced token presented again
  ends the whole session (stolen copy). Settings lists signed-in devices; sign out one or all others.
  Both tokens are encrypted on the phone with an Android Keystore AES-GCM key and sent in headers, never URLs
  (sockets included).
- Rate limits (in memory, per server process): sign-in 5/min per account and 60/min per IP, 10 failures lock the
  account for 15 min; sign-up 20/h and guest 30/h per IP; refresh, username check and search 60/min per IP.
  Behind Cloudflare set `TRUST_PROXY_HEADERS=true` so limits use the real client IP.
- Access: every route except sign-in, health, languages and username check needs a valid session (a test walks all
  routes); chat voice clips, voicemail and conversations also check ownership or membership.
- Calls: only the creator and the person with the 6-character invite code can join (max 2); the socket rejects others (4404).
- Data: no audio is stored anywhere; the server stores users and call metadata (times, languages, counts);
  live-call transcripts are kept only on the phone when the user opts in, and can be deleted. The one exception is
  voicemail text (below), which must wait on the server for the recipient.
- Voicemail: by email address (anyone who knows it) or to someone you have called; 30 per sender per day.
- Network: release builds allow https/wss only and trust only system certificates; debug builds also allow plain
  http (local Wi-Fi testing) and user-installed certificates.
- Retention (hourly clean-up job): voicemail text 7 days; chat messages and voice clips 30 days
  (`CHAT_RETENTION_DAYS`); ended sessions after 1 day.
- Logs: ids, durations and status codes only — never transcripts, translations, audio or keys.

## Contacts and direct calls
Contacts are added by @username (`/v1/contacts`); people can be blocked (`/v1/contacts/blocked`), which hides them from
search and stops their calls, voicemail and new chats. "Who can call me" (`allow_calls`) is `contacts` by default:
a person may ring you if they are in your contacts, if you have had a call together, or if you chose `everyone`.

`POST /v1/calls/direct {to}` creates a call and sends `incoming_call` to every open app socket of the callee
(`/v1/chat/ws`, kept open by the app while signed in). The callee answers (`/v1/calls/{id}/answer`, other phones of
theirs stop ringing) or declines; the caller can cancel, or just hang up. After `RING_TIMEOUT_S` (30 s) it is missed.
The caller is told `call_declined` / `call_missed` and offered to leave a voicemail. A ringing call cannot be joined
with its invite code. Not yet: push notifications (Firebase), so a phone rings only while the app is running.

TURN: with `TURN_SECRET` set, `/v1/ice-servers` and the call socket hand each user coturn REST credentials
(`<expiry>:<user id>`, HMAC-SHA1) that expire after 24 h.

## Account, app lock, release
- Settings is a hub of nine groups (Account, Privacy and security, Language and voice, Calls, Chats, Notifications,
  Storage and data, Appearance, Help and about).
- Account deletion (`DELETE /v1/me`, typing DELETE, plus the password for email accounts) removes at once the
  profile, sessions, contacts, blocks, favourites, call participation, voicemail, the user's chat messages and voice
  clips, and chats left with no members. Other people keep the messages they sent.
- App lock uses Android's BiometricPrompt (fingerprint, face or the phone's PIN/pattern); no app PIN is stored. It
  locks on start and after 30 s in the background. "Block screenshots" sets FLAG_SECURE.
- Release builds are signed from `android/keystore.properties` (git-ignored); see docs/PLAY_STORE.md. The privacy
  policy is docs/PRIVACY.md (web) and the same text in the app.

## Chat
Messages are translated per reader and cached per language. Each of my messages carries a status: `sent`,
`delivered` (it reached one of their phones, or they opened the chat) or `read`. Read receipts are mutual: a person who
turns them off is never reported as having read, and sees no "read" on their own messages. The sender can delete a
message for everyone (its text, translations and voice clip are removed; a "deleted" marker stays); anyone can delete
one for themselves. Each message gets an expiry when sent: the shortest "keep chat history" setting (7, 30 or 365
days) among the chat's members; the hourly clean-up deletes it then. New messages, reads and deletions are pushed
over the app socket; the chat screen also refreshes every 2.5 s.

On the phone, saved call transcripts are encrypted with an AES-GCM key in the Android Keystore (as are the tokens);
app backups are disabled.

## Voicemail
`voicemail.py`. The sender records up to 60 s (16 kHz PCM, in memory on the phone) and uploads it to
`POST /v1/voicemails`. The server answers 202 at once and, in the background, streams the audio to Prisma at real-time
cadence (in the sender's language, or `indic-auto`), then drops the audio. The recognised text is translated with
MyMemory into the recipient's preferred language (`users.language`, kept in step with the app's "my language").
Only the text is stored: original + translation, deleted when either person deletes it or after 7 days.
When the recipient presses play, `GET /v1/voicemails/{id}/audio` creates the voice with Timbre and streams it; it is
never stored. Processing takes about the recording's length plus a few seconds, because Prisma must be fed in real time.

## Limits and known gaps
- WebRTC needs a TURN server for some networks (symmetric NAT, many mobile carriers). Configure `TURN_URLS` etc.
  Without it, translation still works through the server, but the original voice may not connect.
- MyMemory free quota: 5,000 chars/day (50,000 with `MYMEMORY_EMAIL`). Swap in another `Translator` for production.
- Prisma has no partial transcripts: text appears when the speaker pauses (VAD), not word by word.
- Calls are inside Sarvagyan only; Android does not allow capturing other apps' or cellular call audio.
- No push notifications yet: the other person joins with the invite code (no ringing).
