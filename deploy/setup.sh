#!/usr/bin/env bash
# One-time setup of a Sarvagyan server on a fresh Ubuntu 24.04 machine (made for Oracle Cloud Always Free, Arm).
# Run from the repository folder on the server:   bash deploy/setup.sh
#
# Installs and configures:
#   - the Sarvagyan server (systemd service "sarvagyan", listening only on 127.0.0.1:8787)
#   - Caddy: HTTPS with a free Let's Encrypt certificate, forwards to the server (WebSockets included)
#   - coturn: TURN relay with short-lived per-user credentials (calls on mobile data)
#   - DuckDNS: keeps your free <name>.duckdns.org address pointing at this machine
#   - firewall rules, a daily database backup kept 7 days
# Secrets are asked for here and stored only in /etc/sarvagyan/sarvagyan.env (readable by root and the service).
set -euo pipefail

APP_DIR=/opt/sarvagyan
DATA_DIR=/var/lib/sarvagyan
CONF_DIR=/etc/sarvagyan
REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"

say() { printf '\n\033[1;32m==> %s\033[0m\n' "$*"; }
ask() { local v; read -r -p "$1" v; printf '%s' "$v"; }
ask_secret() { local v; read -r -s -p "$1" v; echo >&2; printf '%s' "$v"; }

SUDO=sudo  # works as a normal user with sudo rights (Oracle: "ubuntu") or as root
[[ -f "$REPO_DIR/server/pyproject.toml" ]] || { echo "Run this from the Sarvagyan repository (deploy/setup.sh)."; exit 1; }

say "Your settings"
# Given as environment variables (deploy-from-pc.ps1 does this), or asked for here.
# DOMAIN: the server's web address. Either a DuckDNS name (DUCK_NAME, kept up to date with DUCK_TOKEN) or a fixed
# address the cloud gives you, e.g. Azure's <label>.<region>.cloudapp.azure.com.
if [[ -z "${DOMAIN:-}" && -z "${DUCK_NAME:-}" ]]; then
  DOMAIN=$(ask "Server address (Azure: name.region.cloudapp.azure.com, or a DuckDNS name): ")
fi
if [[ -z "${DUCK_NAME:-}" && "${DOMAIN:-}" == *.duckdns.org ]]; then DUCK_NAME="${DOMAIN%.duckdns.org}"; fi
if [[ -z "${DOMAIN:-}" && -n "${DUCK_NAME:-}" && "$DUCK_NAME" != *.* ]]; then DOMAIN="${DUCK_NAME}.duckdns.org"; fi
if [[ "$DOMAIN" != *.* ]]; then DOMAIN="${DOMAIN}.duckdns.org"; DUCK_NAME="${DOMAIN%.duckdns.org}"; fi
USE_DUCK=false
if [[ "$DOMAIN" == *.duckdns.org ]]; then
  USE_DUCK=true
  [[ -n "${DUCK_TOKEN:-}" ]] || DUCK_TOKEN=$(ask_secret "DuckDNS token (from duckdns.org, hidden): ")
fi
[[ -n "${GNANI_KEY:-}" ]] || GNANI_KEY=$(ask_secret "Gnani API key (hidden): ")
[[ -n "${MYMEMORY_EMAIL+x}" ]] || MYMEMORY_EMAIL=$(ask "Email for MyMemory's higher free quota (Enter to skip): ")
if [[ -z "${DEMO_MODE:-}" ]]; then
  DEMO=$(ask "Allow 'Continue as guest' sign-in? [y/N]: ")
  [[ "$DEMO" =~ ^[Yy] ]] && DEMO_MODE=true || DEMO_MODE=false
fi
PUBLIC_IP=$(curl -fsS https://api.ipify.org)
PRIVATE_IP=$(hostname -I | awk '{print $1}')
if $USE_DUCK; then
  say "Pointing $DOMAIN at this machine"
  RESP=$(curl -fsS "https://www.duckdns.org/update?domains=${DUCK_NAME}&token=${DUCK_TOKEN}&ip=${PUBLIC_IP}")
  [[ "$RESP" == "OK" ]] || { echo "DuckDNS refused the update (check the name and token)."; exit 1; }
fi
echo "$DOMAIN should point to $PUBLIC_IP"
RESOLVED=$(getent hosts "$DOMAIN" | awk '{print $1}' | head -n1 || true)
if [[ "$RESOLVED" != "$PUBLIC_IP" ]]; then
  echo "Warning: $DOMAIN currently points to '${RESOLVED:-nothing}', not $PUBLIC_IP. HTTPS will fail until it does."
fi

# Small free servers (Azure B1s / B2ats v2: 1 GB memory) need swap to install packages safely.
if [[ ! -f /swapfile ]] && (( $(awk '/MemTotal/ {print $2}' /proc/meminfo) < 3000000 )); then
  say "Adding 2 GB of swap (this server has little memory)"
  $SUDO fallocate -l 2G /swapfile && $SUDO chmod 600 /swapfile && $SUDO mkswap /swapfile >/dev/null && $SUDO swapon /swapfile
  grep -q '^/swapfile' /etc/fstab || echo '/swapfile none swap sw 0 0' | $SUDO tee -a /etc/fstab >/dev/null
fi

say "Installing packages"
# answer install-time questions in advance, so setup never stops to ask
export DEBIAN_FRONTEND=noninteractive NEEDRESTART_MODE=a
echo "iptables-persistent iptables-persistent/autosave_v4 boolean true" | $SUDO debconf-set-selections
echo "iptables-persistent iptables-persistent/autosave_v6 boolean true" | $SUDO debconf-set-selections
APT="$SUDO env DEBIAN_FRONTEND=noninteractive NEEDRESTART_MODE=a apt-get -o Dpkg::Options::=--force-confold"
$APT update -y
$APT install -y curl git rsync sqlite3 coturn iptables-persistent debian-keyring debian-archive-keyring apt-transport-https gnupg
if ! command -v caddy >/dev/null; then
  curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | $SUDO gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
  curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | $SUDO tee /etc/apt/sources.list.d/caddy-stable.list >/dev/null
  $APT update -y && $APT install -y caddy
fi
if ! command -v uv >/dev/null; then
  curl -LsSf https://astral.sh/uv/install.sh | $SUDO env UV_INSTALL_DIR=/usr/local/bin UV_NO_MODIFY_PATH=1 sh
fi

say "Creating the service user and folders"
id sarvagyan >/dev/null 2>&1 || $SUDO useradd --system --home "$DATA_DIR" --shell /usr/sbin/nologin sarvagyan
$SUDO mkdir -p "$APP_DIR" "$DATA_DIR/backups" "$CONF_DIR"
$SUDO rsync -a --delete --exclude .git --exclude android --exclude .env --exclude 'server/.venv' --exclude 'server/data' "$REPO_DIR/" "$APP_DIR/"
$SUDO chown -R sarvagyan:sarvagyan "$APP_DIR" "$DATA_DIR"
$SUDO chmod 750 "$DATA_DIR"

say "Installing the server's Python packages"
$SUDO -u sarvagyan env UV_CACHE_DIR="$DATA_DIR/.uv-cache" UV_PYTHON_INSTALL_DIR="$DATA_DIR/.uv-python" \
  bash -c "cd $APP_DIR/server && uv sync --frozen --no-dev"

say "Writing the configuration (secrets stay on this machine)"
# keep the existing secrets when setup runs again (a new AUTH_SECRET would sign everyone out)
old() { $SUDO grep -s "^$1=" "$CONF_DIR/sarvagyan.env" | cut -d= -f2- || true; }
AUTH_SECRET=$(old AUTH_SECRET); [[ -n "$AUTH_SECRET" ]] || AUTH_SECRET=$(openssl rand -hex 32)
TURN_SECRET=$(old TURN_SECRET); [[ -n "$TURN_SECRET" ]] || TURN_SECRET=$(openssl rand -hex 32)
$SUDO tee "$CONF_DIR/sarvagyan.env" >/dev/null <<EOF
GNANI_API_KEY=$GNANI_KEY
MYMEMORY_EMAIL=$MYMEMORY_EMAIL
AUTH_SECRET=$AUTH_SECRET
DEMO_MODE=$DEMO_MODE
DATA_DIR=$DATA_DIR
TURN_URLS=turn:$DOMAIN:3478?transport=udp,turn:$DOMAIN:3478?transport=tcp
TURN_SECRET=$TURN_SECRET
TRUST_PROXY_HEADERS=false
LOG_LEVEL=INFO
EOF
$SUDO chown root:sarvagyan "$CONF_DIR/sarvagyan.env"
$SUDO chmod 640 "$CONF_DIR/sarvagyan.env"
if $USE_DUCK; then
  printf 'DUCK_NAME=%s\nDUCK_TOKEN=%s\n' "$DUCK_NAME" "$DUCK_TOKEN" | $SUDO tee "$CONF_DIR/duckdns.env" >/dev/null
  $SUDO chmod 600 "$CONF_DIR/duckdns.env"
fi

say "Server service (starts on boot, restarts if it stops)"
$SUDO tee /etc/systemd/system/sarvagyan.service >/dev/null <<EOF
[Unit]
Description=Sarvagyan translation calling server
After=network-online.target
Wants=network-online.target

[Service]
User=sarvagyan
Group=sarvagyan
WorkingDirectory=$APP_DIR/server
EnvironmentFile=$CONF_DIR/sarvagyan.env
# one process on purpose: calls live in memory. Real client addresses come from Caddy (rate limits).
ExecStart=$APP_DIR/server/.venv/bin/uvicorn sarvagyan_server.main:app --host 127.0.0.1 --port 8787 --proxy-headers --forwarded-allow-ips 127.0.0.1 --no-access-log
Restart=always
RestartSec=3
NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=true
PrivateTmp=true
ReadWritePaths=$DATA_DIR

[Install]
WantedBy=multi-user.target
EOF

say "HTTPS (Caddy gets and renews the certificate itself)"
$SUDO tee /etc/caddy/Caddyfile >/dev/null <<EOF
$DOMAIN {
	encode gzip
	header Strict-Transport-Security "max-age=31536000"
	reverse_proxy 127.0.0.1:8787
}
EOF

say "TURN relay (coturn)"
$SUDO tee /etc/turnserver.conf >/dev/null <<EOF
listening-port=3478
external-ip=$PUBLIC_IP/$PRIVATE_IP
realm=$DOMAIN
use-auth-secret
static-auth-secret=$TURN_SECRET
min-port=49160
max-port=49200
fingerprint
no-cli
no-multicast-peers
no-tlsv1
no-tlsv1_1
total-quota=100
user-quota=12
stale-nonce=600
# never relay into private networks (protects this machine and Oracle's internal network)
denied-peer-ip=0.0.0.0-0.255.255.255
denied-peer-ip=10.0.0.0-10.255.255.255
denied-peer-ip=100.64.0.0-100.127.255.255
denied-peer-ip=127.0.0.0-127.255.255.255
denied-peer-ip=169.254.0.0-169.254.255.255
denied-peer-ip=172.16.0.0-172.31.255.255
denied-peer-ip=192.168.0.0-192.168.255.255
log-file=syslog
EOF
$SUDO sed -i 's/^#\?TURNSERVER_ENABLED=.*/TURNSERVER_ENABLED=1/' /etc/default/coturn 2>/dev/null || true
$SUDO chmod 640 /etc/turnserver.conf
$SUDO chown root:turnserver /etc/turnserver.conf 2>/dev/null || true

say "Firewall on this machine (Oracle's Ubuntu blocks everything but SSH by default; Azure's allows all)"
for rule in "-p tcp --dport 80" "-p tcp --dport 443" "-p udp --dport 3478" "-p tcp --dport 3478" "-p udp --dport 49160:49200"; do
  # shellcheck disable=SC2086
  $SUDO iptables -C INPUT $rule -j ACCEPT 2>/dev/null || $SUDO iptables -I INPUT 1 $rule -j ACCEPT
done
$SUDO netfilter-persistent save

say "Scheduled jobs: database backup every day (one per weekday, 7 kept)"
{
  if $USE_DUCK; then
    echo "*/5 * * * * root . $CONF_DIR/duckdns.env && curl -fsS \"https://www.duckdns.org/update?domains=\$DUCK_NAME&token=\$DUCK_TOKEN&ip=\" >/dev/null 2>&1"
  fi
  echo "30 3 * * * sarvagyan sqlite3 $DATA_DIR/sarvagyan.sqlite3 \".backup $DATA_DIR/backups/sarvagyan-\$(date +\\%a).sqlite3\""
} | $SUDO tee /etc/cron.d/sarvagyan >/dev/null

say "Starting everything"
$SUDO systemctl daemon-reload
$SUDO systemctl enable --now sarvagyan
$SUDO systemctl restart coturn caddy
$SUDO systemctl enable coturn caddy

sleep 3
if curl -fsS http://127.0.0.1:8787/health >/dev/null; then echo "Server: running"; else echo "Server did not start: sudo journalctl -u sarvagyan -n 50"; fi
echo
echo "Done. In a minute, open https://$DOMAIN/health in a browser: it should show {\"status\":\"ok\",...}"
echo "Build the app for it on your PC:"
echo "  cd android && ./gradlew :app:assembleDebug -PserverUrl=https://$DOMAIN"
