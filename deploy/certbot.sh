#!/usr/bin/env bash
# Obtain and install the TLS certificate. Separate from provision.sh because
# it talks to Let's Encrypt, is rate-limited, and should not be re-run casually.
set -euo pipefail
cd "$(dirname "$0")/.."
# shellcheck disable=SC1091
set -a; source .env; set +a
KEY_PATH="${SSH_KEY/#\~/$HOME}"
mkdir -p "$HOME/.ssh/cm" && chmod 700 "$HOME/.ssh/cm"
SSH=(ssh -i "$KEY_PATH" -o BatchMode=yes -o IdentitiesOnly=yes
     -o ControlMaster=auto -o ControlPath="$HOME/.ssh/cm-nobble-%C"
     -o ControlPersist=120 -o ConnectTimeout=20)
trap '"${SSH[@]}" -O exit "$DROPLET_SSH" >/dev/null 2>&1 || true' EXIT

"${SSH[@]}" "$DROPLET_SSH" PUBLIC_DOMAIN="$PUBLIC_DOMAIN" bash -s <<'REMOTE'
set -euo pipefail
if certbot certificates 2>/dev/null | grep -q "Certificate Name: ${PUBLIC_DOMAIN}"; then
  echo "certificate for ${PUBLIC_DOMAIN} already exists, nothing to do"
  exit 0
fi
certbot --nginx -d "${PUBLIC_DOMAIN}" --non-interactive --agree-tos \
  --email marc@marcdeller.com --redirect
nginx -t && systemctl reload nginx
REMOTE
