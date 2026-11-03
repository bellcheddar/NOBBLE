#!/usr/bin/env bash
set -uo pipefail
cd "$(dirname "$0")/.."
set -a; source .env; set +a
KEY_PATH="${SSH_KEY/#\~/$HOME}"
SSH=(ssh -i "$KEY_PATH" -o BatchMode=yes -o IdentitiesOnly=yes
     -o ControlMaster=auto -o ControlPath="$HOME/.ssh/cm-nobble-%C"
     -o ControlPersist=120 -o ConnectTimeout=20)
trap '"${SSH[@]}" -O exit "$DROPLET_SSH" >/dev/null 2>&1 || true' EXIT
"${SSH[@]}" "$DROPLET_SSH" bash -s <<'REMOTE'
set -uo pipefail
echo "=== all listening ports 8000-8100 ==="
ss -lnt 2>/dev/null | awk '{print $4}' | grep -oE ':(80[0-9][0-9])$' | tr -d ':' | sort -n | tr '\n' ' '; echo
echo "=== binman-web.service ==="
cat /etc/systemd/system/binman-web.service 2>/dev/null || systemctl cat binman-web 2>/dev/null | head -25
echo "=== binman vhost (full) ==="
cat /etc/nginx/sites-available/binman 2>/dev/null
echo "=== where do the apps live ==="
ls -d /opt/* /var/www/* 2>/dev/null | head -20
REMOTE
