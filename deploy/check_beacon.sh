#!/usr/bin/env bash
# Confirm the hit beacon actually reaches nginx's shared access log in the
# vhost format the mdeller.com counter reads. A beacon under an access_log off
# location, or logged in the default format, reads a flat zero forever.
set -euo pipefail
cd "$(dirname "$0")/.."
set -a; source .env; set +a
KEY_PATH="${SSH_KEY/#\~/$HOME}"
SSH=(ssh -i "$KEY_PATH" -o BatchMode=yes -o IdentitiesOnly=yes
     -o ControlMaster=auto -o ControlPath="$HOME/.ssh/cm-nobble-%C"
     -o ControlPersist=120 -o ConnectTimeout=20)
trap '"${SSH[@]}" -O exit "$DROPLET_SSH" >/dev/null 2>&1 || true' EXIT
"${SSH[@]}" "$DROPLET_SSH" bash -s <<REMOTE
echo "--- recent nobble lines in the shared access log ---"
grep -c "${PUBLIC_DOMAIN}" /var/log/nginx/access.log 2>/dev/null || echo 0
echo "--- beacon path (/api/status) seen? ---"
grep "${PUBLIC_DOMAIN}" /var/log/nginx/access.log 2>/dev/null | grep -c "/api/status" || echo 0
echo "--- a sample line, to confirm the vhost format carries the host ---"
grep "${PUBLIC_DOMAIN}" /var/log/nginx/access.log 2>/dev/null | tail -1
REMOTE
