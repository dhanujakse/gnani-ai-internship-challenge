# Sarvagyan Web Client (Secondary Companion)

A lightweight Next.js companion web app for **Sarvagyan (सर्वज्ञान)**.
This allows anyone to:
1. Download the native **Android APK** directly.
2. Join a live multilingual voice call directly from any browser via invite link/code (`/join?code=XXXXXX`) without installing the app.
3. See live synchronized bilingual transcripts and translations powered by Gnani AI.

---

## 🚀 How to Deploy on Vercel

When importing this repository into [Vercel](https://vercel.com):

1. **Import the repository** `sarvagyan_call_transulater`
2. In the project setup screen, expand **"Root Directory"**
3. Click **Edit** and select the **`web`** folder (or type `web`)
4. Framework Preset will automatically detect **Next.js**
5. Click **Deploy**!

That's it! Vercel will build and host only the `web` folder without interfering with `android/` or `server/`.

Once deployed, you will get a URL like `https://sarvagyan.vercel.app`.
