# Sarvagyan web app

The web version of the Sarvagyan Android app (Next.js 16, React 19, Tailwind CSS 4). Same account, same server,
same screens: sign in or create an account, start or join a translated call with an invitation code, call
contacts directly (their phone or browser rings), and manage your profile, language and contacts.

On the web you hear the other person's **translated voice** and read **live subtitles**. Their original voice
(the WebRTC path) is carried in the Android app only.

## Run locally

```bash
cd web
npm install
NEXT_PUBLIC_SERVER_URL=http://localhost:8787 npm run dev   # http://localhost:3000
```

Without `NEXT_PUBLIC_SERVER_URL` the app talks to `https://sarvagyan-server.onrender.com`.
The server must allow the site's address in `WEB_ORIGINS` (it already allows `http://localhost:3000` and the
Vercel address below).

## Deploy on Vercel

1. Import the repository `dhanujakse/gnani-ai-internship-challenge`.
2. Set **Root Directory** to `web`. Framework preset: Next.js.
3. Optional: add the environment variable `NEXT_PUBLIC_SERVER_URL` if the server is not the default one.
4. Deploy.
5. If the site's address is not `https://gnani-ai-internship-challenge.vercel.app`, add it to the server's
   `WEB_ORIGINS` (comma-separated) and redeploy the server, or the browser will block every request.

## How it talks to the server

| | |
|---|---|
| REST | `src/lib/api.ts`: the same endpoints as the app's `ApiClient.kt`; 15-minute access tokens are refreshed automatically |
| Calls | `src/lib/callEngine.ts`: `/v1/calls/{id}/ws`, 16 kHz 1,024-byte mic frames, echo gate while translated speech plays, ordered playback |
| Ringing | `src/lib/appSocket.ts`: `/v1/chat/ws` for incoming calls, answered / declined / missed |
| Sign-in on sockets | browsers can't set headers on a WebSocket, so the token is sent as the subprotocol `auth.<token>` (never in the URL) |
| Invitation links | `/join?code=ABC234` forwards to `/?code=ABC234`: sign in and the code is ready to join |
