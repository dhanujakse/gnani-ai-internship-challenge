# Sarvagyan privacy policy

**Draft, 7 November 2026: have it reviewed before publishing.** Fill in the operator's name and contact address
below; the Play Store needs this page at a public web address.

Sarvagyan lets two people who speak different languages call, leave voicemail and chat, each in their own language.
To translate, the words have to be processed by our server and by the speech and translation services named below.
We keep as little as possible, for as short a time as possible.

Operator: **[name of the person or company running the service]** · Contact: **[email address]**

## What we collect and why

| Data | Why | Kept for |
|---|---|---|
| Account: display name, @username, email (or a guest account with no email), chosen language | To sign you in, let people find you, and translate into your language | Until you delete your account |
| Password | To sign you in. Stored only as a scrypt hash; we cannot read it | Until you change it or delete your account |
| Signed-in devices: phone model, when last used | So you can see and sign out your devices | 30 days after last use, or until signed out |
| Contacts you add, people you block, favourites | To let contacts call you and keep blocked people away | Until you remove them or delete your account |
| Call records: who, when, how long, which languages | Call history in the app | Until you delete your account |
| Voicemail: the recognised text and its translation | So it can wait until the other person opens it | Until either of you deletes it, at most 7 days |
| Chat messages, their translations, voice messages | To deliver them to the other members | 7 days, 30 days (default) or 1 year: the shortest setting among the chat's members |

**Never stored:** the audio of calls. Voicemail recordings are held in memory only while they are turned into text,
then discarded. The translated voice you hear is generated when you press play and is not kept.

**On your phone only:** call transcripts, if you turn on "Save transcripts" (off by default). They are encrypted on
the phone and you can delete them at any time. Your sign-in is also stored encrypted on the phone.

## Who else processes your words

To translate, the words you speak or type are sent, without your name or account details, to:

- **Gnani.ai** (speech recognition and the translated voice), in India
- **MyMemory / Translated** (text translation), in Italy
- **Google Firebase Cloud Messaging** (wakes your phone for an incoming call when the app is closed). It carries only the call id, the caller's name, username and language, never what is said.

They process the text and audio to return a result. Their own privacy terms apply to that processing.
Calls' original voices travel directly between the two phones, encrypted (WebRTC), and may pass through a relay
server only to connect them.

## What we don't do

- No advertising, no selling of data, no tracking across other apps or websites.
- No access to your phone's contacts, photos, location or ordinary phone calls.
- We do not log what you say or write: our server logs only technical details (ids, durations, error codes).

## Your choices and rights

- **Delete your account:** Settings → Account → Delete account. Everything the server holds about you is deleted at
  once: your profile, devices, contacts, call records, voicemail, and your chat messages and voice messages
  (other people keep the messages they sent). Backups, if any, are overwritten within 7 days.
- **Read receipts, chat history length, who can call you, blocking:** in Settings.
- **Sign out other devices:** Settings → Account → Signed-in devices.
- Questions or requests about your data: the contact address above.

## Security

All connections are encrypted (HTTPS). Sign-ins expire after 15 minutes of no use and renew automatically; a
stolen sign-in can be ended from Settings. Repeated wrong passwords lock sign-in for 15 minutes.

## Children

Sarvagyan is not meant for children under 13, and we do not knowingly collect their data.

## Changes

If this policy changes, the app will show the new version before it applies.
