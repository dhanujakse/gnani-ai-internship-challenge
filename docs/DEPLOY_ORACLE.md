# Free hosting on Oracle Cloud (Always Free)

Run the Sarvagyan server for free, always on, with HTTPS, a permanent address and its own TURN relay. About
30–45 minutes the first time. Nothing here costs money if you stay inside the Always Free limits.

**What you need:** a debit/credit card (Oracle uses it only to check you are a real person; Always Free resources are
not charged), your Gnani API key, and this repository.

**What you get:** `https://<your-name>.duckdns.org`. Build the app once with that address and it keeps working, even
when your PC is off.

## Limits to know (checked November 2026)

- Oracle's free Arm allowance is now **2 CPU cores and 12 GB of memory** in total (older guides say 4 and 24). This
  guide uses 1 core and 6 GB, well inside it. ([Oracle free tier changes 2026](https://terminalbytes.com/oracle-cloud-free-tier-changes-2026/))
- Your home region may have no free Arm capacity on the day you try. If creating the server fails with "Out of
  capacity", try again later or another availability domain. ([Oracle Always Free review](https://space-node.net/blog/oracle-vps-free-tier-review-2026))
- Oracle may **reclaim Always Free servers that sit idle** for a week. A small app with few users can look idle.
  Upgrading the account to "Pay As You Go" stops that and still costs nothing while you stay inside the free limits;
  set a budget alert at 1 rupee/dollar so you'd be told of any charge.
- Your home region cannot be changed later. For India, pick **Mumbai** or **Hyderabad** (lower delay for calls).

## 1. Create the Oracle account

1. Go to <https://www.oracle.com/cloud/free/> → **Start for free**.
2. Choose your home region (Mumbai or Hyderabad), enter your details and card. Wait for the "account ready" email.

## 2. Create the server

1. Oracle Cloud console → ☰ → **Compute → Instances → Create instance**.
2. **Name:** `sarvagyan`.
3. **Image:** *Change image* → **Canonical Ubuntu 24.04** (pick the one that says *aarch64* / Arm).
4. **Shape:** *Change shape* → **Ampere** → `VM.Standard.A1.Flex`, **1 OCPU, 6 GB memory**. It should say *Always Free-eligible*.
5. **Networking:** keep the default new network, and make sure **Assign a public IPv4 address** is on.
6. **SSH keys:** *Generate a key pair for me* → **Save private key**. Keep that file safe (e.g. `C:\Users\you\.ssh\sarvagyan.key`).
7. **Create.** When it shows *Running*, copy its **Public IP address**.

## 3. Open the ports in Oracle's network

Instance page → **Subnet** link → **Security lists** → *Default security list* → **Add ingress rules**, all with source
`0.0.0.0/0`:

| Protocol | Destination port | For |
|---|---|---|
| TCP | 80 | HTTPS certificate check |
| TCP | 443 | The app (HTTPS) |
| UDP | 3478 | TURN relay |
| TCP | 3478 | TURN relay (networks that block UDP) |
| UDP | 49160-49200 | TURN relay audio |

(The setup script opens the same ports in the server's own firewall.)

## 4. Get a free address (DuckDNS)

1. Go to <https://www.duckdns.org>, sign in (Google or GitHub).
2. Add a sub-domain, e.g. `sarvagyan-siva` → you get `sarvagyan-siva.duckdns.org`.
3. Copy the **token** shown at the top. (The setup script points the address at your server and keeps it updated.)

## 5. Deploy with one command (from your PC)

In PowerShell on your PC:
```
powershell -ExecutionPolicy Bypass -File D:\inten_hackthon\deploy\deploy-from-pc.ps1
```
It asks for the server's public IP, the SSH user name (type `ubuntu`), the SSH key file you saved, your DuckDNS
name and token, and whether to allow guest sign-in. Your Gnani key is taken from this repository's `.env`. Then, with no more questions, it:

1. uploads the server code straight from your PC (nothing needs pushing to GitHub),
2. sets up the server (HTTPS, TURN relay, firewall, DuckDNS, backups, auto-restart), about 5 minutes,
3. waits until `https://<name>.duckdns.org/health` answers,
4. builds the APK for that address: `android\app\build\outputs\apk\debug\app-debug.apk`.

Uninstall the old app on the phones and install the new APK. The address never changes, so you won't need to
rebuild for a new tunnel again.

**After changing the code**, put it on the server with:
```
powershell -ExecutionPolicy Bypass -File D:\inten_hackthon\deploy\deploy-from-pc.ps1 -Update
```
Add `-NoApk` when only the server changed. Users stay signed in.

If Windows says the key file's permissions are too open, run (with your key path):
```
icacls C:\Users\you\.ssh\sarvagyan.key /inheritance:r /grant:r "$($env:USERNAME):(R)"
```

**By hand instead** (on the server, after `ssh -i <key> ubuntu@<IP>`): copy or `git clone` the repository to
`~/sarvagyan`, then `cd ~/sarvagyan && bash deploy/setup.sh`; it asks for the same settings. Then build the app on
your PC in `android` with `.\gradlew :app:assembleDebug -PserverUrl=https://<name>.duckdns.org`.

## Everyday

| Task | Command (on the server) |
|---|---|
| Update to the latest code | From your PC: `deploy-from-pc.ps1 -Update` (or on the server: `cd ~/sarvagyan && bash deploy/update.sh`) |
| Is it running? | `sudo systemctl status sarvagyan` |
| Recent server log (no conversation content is ever logged) | `sudo journalctl -u sarvagyan -n 100` |
| Restart | `sudo systemctl restart sarvagyan` |
| Change a setting (Gnani key, guest sign-in…) | `sudo nano /etc/sarvagyan/sarvagyan.env`, then restart |
| Backups | `/var/lib/sarvagyan/backups/` (one per weekday, so 7 kept) |

## Where things are

| What | Where |
|---|---|
| Code | `/opt/sarvagyan` |
| Database, chat voice clips, backups | `/var/lib/sarvagyan` |
| Secrets (Gnani key, signing secret, TURN secret) | `/etc/sarvagyan/sarvagyan.env` (root and the service only) |
| HTTPS | Caddy, `/etc/caddy/Caddyfile`; the certificate renews by itself |
| TURN relay | coturn, `/etc/turnserver.conf` |

## Still not free

- **Google Play:** a one-time 25 USD developer fee. Until then, share the APK directly (e.g. GitHub Releases).
- **Gnani:** speech recognition and voice use your Gnani credits, wherever the server runs.
