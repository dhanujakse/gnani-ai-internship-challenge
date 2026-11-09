# Free hosting on Azure for Students (no credit card)

Run the Sarvagyan server always on, with HTTPS, a permanent address and its own TURN relay, on the
Azure for Students free allowance. No credit card: you verify with your college email or student ID. About 30 minutes
the first time.

**What you get:** `https://<your-name>.<region>.cloudapp.azure.com`. Build the app once with that address and it keeps
working, even when your PC is off.

## Limits to know (checked November 2026)

- Azure for Students gives free credit for 12 months plus 750 hours a month of a small Linux server (B1s, B2ats v2 or
  B2pts v2), which is enough to run one server all month. Renew every year while you're a student.
  ([Azure for Students](https://azure.microsoft.com/en-us/free/students))
- Those servers have **1 GB of memory**. That is enough for this server; the setup script adds 2 GB of swap.
- Only small things (public IP address, extra traffic) may use a little of the credit. Credit is never turned into a
  charge; when it runs out, the server stops. Check **Cost Management** after a few days.
- Student subscriptions may allow only some regions. Pick **Central India** or **South India** if offered (lower delay
  for calls), otherwise any region it allows.

## 1. Create the account

1. Go to <https://azure.microsoft.com/free/students> → **Start free**.
2. Sign in with a Microsoft account and verify with your **college email** (or the student verification it offers).
   No card is asked for.
3. You land in the Azure portal: <https://portal.azure.com>.

## 2. Create the server

Portal → search **Virtual machines** → **Create → Azure virtual machine**.

**Basics tab**
| Field | Choose |
|---|---|
| Subscription | Azure for Students |
| Resource group | Create new → `sarvagyan` |
| Virtual machine name | `sarvagyan` |
| Region | Central India / South India (or one that is allowed) |
| Availability options | No infrastructure redundancy required |
| Image | **Ubuntu Server 24.04 LTS – x64 Gen2** |
| Size | *See all sizes* → **B2ats_v2** (or **B1s**). Pick one marked *Free services eligible* |
| Authentication type | SSH public key |
| Username | `azureuser` |
| SSH public key source | Generate new key pair, name `sarvagyan` |
| Public inbound ports | Allow selected ports → **SSH (22)** |

**Disks tab:** OS disk type **Premium SSD**, size **64 GiB** (the free allowance is two 64 GB SSDs).

**Networking tab:** keep the defaults (new network, new public IP). Tick *Delete public IP and NIC when VM is deleted*.

**Management tab:** make sure **Auto-shutdown** is **off**.

**Review + create → Create.** A pop-up asks you to **Download private key and create resource**. Do it, then move the
downloaded `sarvagyan.pem` to `C:\Users\sivas\.ssh\sarvagyan.pem`.

## 3. Address and ports

When it says *Your deployment is complete* → **Go to resource**.

1. **Public IP address**: copy it (on the Overview page).
2. **Free fixed address**: on the Overview page, next to *DNS name*, click **Not configured** → *DNS name label*, enter
   e.g. `sarvagyan-siva` → **Save**. Your address is shown below it, like
   `sarvagyan-siva.centralindia.cloudapp.azure.com`. Copy it.
   (On the same page, *Assignment* should be **Static**, so the IP never changes.)
3. **Open the ports**: VM → **Networking → Network settings → Create port rule → Inbound port rule**. Add these
   (source *Any*, action *Allow*), one rule each:

| Destination port ranges | Protocol | Name | For |
|---|---|---|---|
| 80 | TCP | http | HTTPS certificate check |
| 443 | TCP | https | The app (HTTPS) |
| 3478 | Any | turn | TURN relay (UDP and TCP) |
| 49160-49200 | UDP | turn-media | TURN relay audio |

## 4. Deploy with one command (from your PC)

In PowerShell on your PC:
```
powershell -ExecutionPolicy Bypass -File D:\inten_hackthon\deploy\deploy-from-pc.ps1 -Key C:\Users\sivas\.ssh\sarvagyan.pem
```
It asks for:
- the public IP,
- the SSH user name (press Enter for `azureuser`),
- the web address from step 3 (`…cloudapp.azure.com`),
- whether to allow guest sign-in.

Your Gnani key is taken from this repository's `.env`. Then, with no more questions, it:

1. uploads the server code straight from your PC (nothing needs pushing to GitHub),
2. sets up the server (swap, HTTPS, TURN relay, firewall, backups, auto-restart), about 5–10 minutes,
3. waits until `https://<address>/health` answers,
4. builds the APK for that address: `android\app\build\outputs\apk\debug\app-debug.apk`.

Uninstall the old app on the phones and install the new APK.

If Windows says the key file's permissions are too open, run:
```
icacls C:\Users\sivas\.ssh\sarvagyan.pem /inheritance:r /grant:r "$($env:USERNAME):(R)"
```

**After changing the code:**
```
powershell -ExecutionPolicy Bypass -File D:\inten_hackthon\deploy\deploy-from-pc.ps1 -Update
```
Add `-NoApk` when only the server changed. Users stay signed in.

## Everyday

Connect with `ssh -i C:\Users\sivas\.ssh\sarvagyan.pem azureuser@<IP>`, then:

| Task | Command (on the server) |
|---|---|
| Is it running? | `sudo systemctl status sarvagyan` |
| Recent server log (no conversation content is ever logged) | `sudo journalctl -u sarvagyan -n 100` |
| Restart | `sudo systemctl restart sarvagyan` |
| Change a setting (Gnani key, guest sign-in…) | `sudo nano /etc/sarvagyan/sarvagyan.env`, then restart |
| Backups | `/var/lib/sarvagyan/backups/` (one per weekday, so 7 kept) |

Where things are on the server: same as in [DEPLOY_ORACLE.md](DEPLOY_ORACLE.md#where-things-are).

## Still not free

- **Google Play:** a one-time 25 USD developer fee. Until then, share the APK directly.
- **Gnani:** speech recognition and voice use your Gnani credits, wherever the server runs.
