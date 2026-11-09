# Play Store release kit

Everything needed to publish Sarvagyan on Google Play. Items marked **[you]** need a decision or an account
only the team can provide.

## Before the first upload

1. **Package name [you].** Today it is `ai.mack.sarvagyan`. It can never change after the first upload. Decide now.
2. **Signing key [you].** Create one upload key and keep it safe (losing it means asking Google to reset it):
   ```
   keytool -genkeypair -v -keystore sarvagyan-upload.jks -keyalg RSA -keysize 4096 -validity 10000 -alias upload
   ```
   Then create `android/keystore.properties` (git-ignored, never commit it):
   ```
   storeFile=D:/keys/sarvagyan-upload.jks
   storePassword=...
   keyAlias=upload
   keyPassword=...
   ```
   `./gradlew :app:bundleRelease -PserverUrl=https://your-server` then builds a signed `app-release.aab`.
   Without `keystore.properties` the release build is signed with the debug key and Play will reject it.
3. **A real server [you].** Release builds only talk to an `https://` address. A cloudflared quick tunnel changes
   address on every restart, so it cannot be used for a store build. Host the server for free with
   [DEPLOY_ORACLE.md](DEPLOY_ORACLE.md) (HTTPS, TURN included), or on any VM with HTTPS, and set
   `DEMO_MODE=false`, `AUTH_SECRET`, `TRUST_PROXY_HEADERS` if behind Cloudflare, and a TURN relay.
4. **Privacy policy URL [you].** Publish `docs/PRIVACY.md` (after filling in the operator and contact) at a public
   address, e.g. GitHub Pages, and enter it in Play Console.
5. Bump `versionCode` / `versionName` in `android/app/build.gradle.kts` for every upload.

## Store listing

- **App name:** Sarvagyan: Translated Calls
- **Short description (80 chars max):** Call, chat and leave voicemail in your language. They hear it in theirs.
- **Full description:**

  > Sarvagyan lets two people who don't share a language talk naturally. Speak Tamil, they hear English, and the other
  > way round, with live subtitles on both phones. 10 Indian languages: Tamil, English, Hindi, Telugu, Kannada,
  > Malayalam, Marathi, Bengali, Gujarati and Punjabi.
  >
  > • Translated calls: each person speaks their own language and hears the other in theirs, with subtitles.
  > • Voicemail: record a message in your language; they read it and hear it in theirs.
  > • Chat and groups: everyone reads every message in their own language. Voice messages too.
  > • Contacts by @username, ringing calls, block, "who can call me".
  > • Private by design: calls are never recorded; chat history is deleted after 7 days, 30 days or a year, your choice;
  >   delete your account and all its data at any time.
  >
  > Translation quality depends on speaking clearly in full sentences. Sarvagyan works between Sarvagyan users only;
  > it cannot translate ordinary phone calls.

- **Category:** Communication · **Tags:** translation, calling, chat
- **Graphics [you]:** 512×512 icon, 1024×500 feature graphic, at least 2 phone screenshots (call with subtitles,
  chat, voicemail, contacts).

## Data safety form

| Question | Answer |
|---|---|
| Does the app collect or share user data? | Yes, collects |
| Encrypted in transit? | Yes |
| Can users request deletion? | Yes, in the app (Settings → Account → Delete account) |
| Personal info: name, email, user IDs | Collected · required · app functionality, account management · not shared |
| Messages: other in-app messages (chat, voicemail text) | Collected · required for these features · app functionality · **shared** with translation processors (Gnani, MyMemory) for processing only |
| Audio: voice or sound recordings | Collected (processed, not stored) · app functionality · **shared** with Gnani for speech recognition |
| Device or other IDs | No (the phone model name is shown in "Signed-in devices"; declare under "Other" if Play's reviewer asks) |
| Location, contacts, photos, financial, health, web history | Not collected |
| Ads or analytics | None |

Processing by Gnani and MyMemory counts as "shared" unless they act strictly as service providers under contract;
check with them and update the answers.

## Permissions to declare

| Permission | Why (text for Play Console) |
|---|---|
| `RECORD_AUDIO` | Your voice is needed for calls, voicemail and voice messages. Only used while you are in a call or recording. |
| `FOREGROUND_SERVICE_MICROPHONE` | Keeps a call going when you switch apps; a notification shows while the microphone is on. Play asks for a short video of this. |
| `USE_FULL_SCREEN_INTENT` | Shows the incoming-call screen when someone calls you. Allowed for calling apps; declare the app as a calling app. |
| `POST_NOTIFICATIONS`, `VIBRATE` | Incoming calls and the active-call notification |

## Content rating

User-to-user communication: yes (calls, chat, voicemail with other users). Users can block and the app has no
public feeds. Expect a "Teen" / "12+" style rating. Target audience: 13 and older.

## Release checklist

- [ ] Package name decided
- [ ] Upload key created and `keystore.properties` filled in (kept out of git)
- [ ] Server hosted on HTTPS with a permanent address; `DEMO_MODE=false`
- [ ] TURN relay running (calls on mobile data)
- [ ] Privacy policy filled in and published; URL in Play Console
- [ ] Data safety form and permission declarations filled in
- [ ] Two-phone test of calls, voicemail, chat, contacts and app lock on the release build
- [ ] `versionCode` bumped; `./gradlew :app:bundleRelease` signed with the upload key
- [ ] Internal testing track first, then production
