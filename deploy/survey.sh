#!/usr/bin/env bash
# Read-only survey of the droplet, in ONE multiplexed connection.
# Nothing here changes anything: it answers what provisioning will need.
set -uo pipefail
cd "$(dirname "$0")/.."
# shellcheck disable=SC1091
set -a; source .env; set +a
KEY_PATH="${SSH_KEY/#\~/$HOME}"
HOST="${DROPLET_SSH#*@}"

[[ -f "$KEY_PATH" ]] || { echo "survey: no key at $KEY_PATH" >&2; exit 2; }
ssh-keygen -F "$HOST" >/dev/null 2>&1 || { echo "survey: '$HOST' not in known_hosts" >&2; exit 2; }

mkdir -p "$HOME/.ssh/cm" && chmod 700 "$HOME/.ssh/cm"
SSH=(ssh -i "$KEY_PATH" -o BatchMode=yes -o IdentitiesOnly=yes
     -o ControlMaster=auto -o ControlPath="$HOME/.ssh/cm-nobble-%C"
     -o ControlPersist=120 -o ConnectTimeout=20)
trap '"${SSH[@]}" -O exit "$DROPLET_SSH" >/dev/null 2>&1 || true' EXIT

"${SSH[@]}" "$DROPLET_SSH" bash -s <<'REMOTE'
set -uo pipefail
echo "=== host ==="; hostname; uptime | tr -s ' '
echo "=== memory and disk ==="; free -m 2>/dev/null | head -2; df -h / | tail -1
echo "=== nginx sites enabled ==="; ls /etc/nginx/sites-enabled/ 2>/dev/null
echo "=== is there a nobble vhost? ==="; ls -la /etc/nginx/sites-available/ 2>/dev/null | grep -i nobble || echo "(none)"
echo "=== certbot certificates ==="; certbot certificates 2>/dev/null | grep -E 'Certificate Name|Domains|Expiry' || echo "(certbot not available or no certs)"
echo "=== systemd services matching binman or nobble ==="; systemctl list-units --type=service --all --no-pager 2>/dev/null | grep -Ei 'binman|nobble' || echo "(none)"
echo "=== ports in use (listening) ==="; ss -lntp 2>/dev/null | awk 'NR==1 || /LISTEN/' | head -15
echo "=== /srv ==="; ls -la /srv 2>/dev/null || echo "(no /srv)"
echo "=== python ==="; python3 --version 2>&1; python3 -m venv --help >/dev/null 2>&1 && echo "venv ok" || echo "venv MISSING"
echo "=== how is binman served? ==="; cat /etc/nginx/sites-available/binman* 2>/dev/null | grep -E 'server_name|proxy_pass|listen' | head -10 || echo "(no binman vhost found)"
REMOTE
