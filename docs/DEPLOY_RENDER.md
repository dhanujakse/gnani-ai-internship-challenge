# Free hosting on Render (free plan)

Runs the Sarvagyan server on Render's free plan with HTTPS and a fixed address,
`https://sarvagyan-server-XXXX.onrender.com`. Built from the GitHub repository using [render.yaml](../render.yaml).

## Limits to know

- **Sleeps after 15 minutes with no requests;** waking takes about a minute. Fix: a free uptime pinger (step 4) keeps
  it awake. One always-awake service uses about 720 of the 750 free hours a month.
- **No lasting disk.** Accounts, contacts, chats and voicemails are wiped on every deploy or restart (and on each
  sleep, if the pinger isn't set up). People then sign up again or continue as guest. Fine for demos and testing.
- **Small machine** (0.1 CPU, 512 MB). Enough for a few calls at a time.
- **No call relay (TURN).** Same Wi-Fi and most home networks work; mobile data may need a free TURN relay
  (e.g. metered.ca's free plan, no card): put its URLs, username and password in the TURN settings.
- Render may ask for a card to verify the account; free services are not charged.

## 1. Put the code on GitHub

Render builds what is on GitHub (`main`), so the latest code, including `render.yaml`, must be committed and pushed
first.

## 2. Create the service

1. Sign up at <https://dashboard.render.com> (with GitHub is easiest).
2. **New → Blueprint** → *Public Git repository* → `https://github.com/dhanujakse/sarvagyan_call_transulater` →
   **Connect**. (Or connect your GitHub account if you have access to the repository.)
3. Render reads `render.yaml` and asks for the secret values:
   - `GNANI_API_KEY`: your Gnani key (from the repository's `.env`)
   - `MYMEMORY_EMAIL`: your email (raises MyMemory's free daily limit)
   - `TURN_URLS`, `TURN_USERNAME`, `TURN_CREDENTIAL`: leave empty unless you have a TURN relay
4. **Apply.** The first build takes about 3–5 minutes. When it says *Live*, copy the address at the top
   (`https://sarvagyan-server-….onrender.com`) and open `/health` on it: it should show `{"status":"ok",...}`.

## 3. Build the app for it

```
powershell -ExecutionPolicy Bypass -File D:\inten_hackthon\android\build-for-tunnel.ps1 -Url https://sarvagyan-server-XXXX.onrender.com
```
Uninstall the old app on the phones, then install `android\app\build\outputs\apk\debug\app-debug.apk`.

## 4. Keep it awake (free)

1. Sign up at <https://cron-job.org> (free, no card).
2. **Create cronjob** → URL `https://sarvagyan-server-XXXX.onrender.com/health` → every **10 minutes** → Save.

## Updating

Push the new code to GitHub, then in Render: the service → **Manual Deploy → Deploy latest commit**. (Automatic
deploys are off so a push never cuts live calls.) Remember a deploy wipes the data.

Change a setting: the service → **Environment** → edit → **Save, rebuild and deploy**.
