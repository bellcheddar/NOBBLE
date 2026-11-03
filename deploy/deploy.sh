#!/usr/bin/env bash
# Deploy NOBBLE to the droplet.
#
# Every rule below was written after a real failure, and none of them is
# optional:
#
# - ONE ssh connection for the whole deploy, multiplexed. The droplet bans IPs
#   that open several connections in quick succession, and a deploy that makes
#   a port probe, a login test and two rsyncs has already made four.
# - NO retry loop. A failed login is diagnosed locally, never retried: repeated
#   failures get the Mac's IP banned, which then looks exactly like a port-22
#   timeout and sends the next hour down the wrong path.
# - rsync carries --chmod. ~/Documents/Vibe_Coding is iCloud-backed and
#   owner-only, and `rsync -a` copies those modes verbatim, which leaves the
#   service user unable to read its own application: every page returns 500.
# - chown runs BEFORE pip. A chown placed after pip never runs when pip fails,
#   under `set -e`.
# - The final check fetches every page, not just /healthz. /healthz has
#   answered {"ok": true} while every real page returned 500.
set -euo pipefail
cd "$(dirname "$0")/.."

if [[ ! -f .env ]]; then
  echo "deploy: .env is missing. Copy .env.example and fill it in." >&2
  exit 2
fi
# shellcheck disable=SC1091
set -a; source .env; set +a

: "${DROPLET_SSH:?set DROPLET_SSH in .env}"
: "${SSH_KEY:?set SSH_KEY in .env}"
: "${REMOTE_DIR:?set REMOTE_DIR in .env}"
: "${SERVICE:?set SERVICE in .env}"
: "${SERVICE_USER:?set SERVICE_USER in .env}"
: "${PUBLIC_HOST:?set PUBLIC_HOST in .env}"

KEY_PATH="${SSH_KEY/#\~/$HOME}"
HOST="${DROPLET_SSH#*@}"

echo "==> pre-flight"
# 1. the key file exists
[[ -f "$KEY_PATH" ]] || { echo "deploy: no key at $KEY_PATH" >&2; exit 2; }
# 2. a known_hosts entry exists for this exact host string. Never
#    StrictHostKeyChecking=no, and never trust a fingerprint Marc has not seen.
if ! ssh-keygen -F "$HOST" >/dev/null 2>&1; then
  echo "deploy: no known_hosts entry for '$HOST'." >&2
  echo "        Add it by copying the already-trusted line for the other host" >&2
  echo "        string after checking the fingerprint matches. Do not use" >&2
  echo "        StrictHostKeyChecking=no." >&2
  exit 2
fi

mkdir -p "$HOME/.ssh/cm" && chmod 700 "$HOME/.ssh/cm"
SSH=(ssh -i "$KEY_PATH" -o BatchMode=yes -o IdentitiesOnly=yes
     -o ControlMaster=auto -o ControlPath="$HOME/.ssh/cm-nobble-%C"
     -o ControlPersist=120 -o ConnectTimeout=20
     -o ServerAliveInterval=30 -o ServerAliveCountMax=4)
trap '"${SSH[@]}" -O exit "$DROPLET_SSH" >/dev/null 2>&1 || true' EXIT

# 3. exactly ONE login test, which doubles as the reachability check. No nc
#    probe: that is another connection, and it is not a reliable probe anyway.
if ! "${SSH[@]}" "$DROPLET_SSH" true; then
  echo "deploy: ssh login failed. Do NOT retry: repeated failures get this IP" >&2
  echo "        banned and the symptom becomes a port-22 timeout." >&2
  echo "        Diagnose locally first (key, known_hosts, ~/.ssh/config), and" >&2
  echo "        control for the network with: ssh -T git@github.com" >&2
  exit 1
fi
echo "    ssh ok, multiplexed"

echo "==> sync code"
rsync -rlpt --delete \
  --chmod=Du=rwx,Dgo=rx,Fu=rw,Fgo=r \
  -e "${SSH[*]}" \
  --exclude '.git/' --exclude '.env' --exclude '.venv/' --exclude '.pixi/' \
  --exclude '__pycache__/' --exclude '*.pyc' --exclude 'node_modules/' \
  --exclude 'campaigns/' --exclude 'logs/' --exclude 'qc/screenshots/' \
  --exclude 'data/msa/' --exclude 'data/cache/' --exclude 'data/interim/' \
  --exclude '*.duckdb' --exclude '*.sqlite*' \
  ./ "$DROPLET_SSH:$REMOTE_DIR/"

echo "==> sync the vendored assets"
# Not in version control (they are BINMAN's, pinned), so they ship from the
# local checkout. See nobble/app/static/vendor/VENDOR.md.
if [[ -d nobble/app/static/vendor && -n "$(ls -A nobble/app/static/vendor 2>/dev/null)" ]]; then
  rsync -rlpt --chmod=Du=rwx,Dgo=rx,Fu=rw,Fgo=r -e "${SSH[*]}" \
    nobble/app/static/vendor/ "$DROPLET_SSH:$REMOTE_DIR/nobble/app/static/vendor/"
else
  echo "deploy: nobble/app/static/vendor is empty. Populate it first:" >&2
  echo "        cp -r ../BINMAN/app/static/vendor/. nobble/app/static/vendor/" >&2
  exit 2
fi

echo "==> sync the published atlas"
# The app serves a precomputed, read-only slice: scores and campaign metadata
# only, never the structures or the third-party source data.
if [[ -d deploy/atlas ]]; then
  rsync -rlpt --chmod=Du=rwx,Dgo=rx,Fu=rw,Fgo=r -e "${SSH[*]}" \
    deploy/atlas/ "$DROPLET_SSH:$REMOTE_DIR/deploy/atlas/"
fi

echo "==> remote: ownership first, then dependencies, then restart"
"${SSH[@]}" "$DROPLET_SSH" bash -s <<REMOTE
set -euo pipefail
cd "$REMOTE_DIR"

# Ownership BEFORE anything that can fail. Prune the venv and the data so this
# stays fast and does not fight the service.
chown -R "$SERVICE_USER":"$SERVICE_USER" \
  \$(find . -maxdepth 1 -mindepth 1 ! -name '.venv' ! -name 'data' ! -name '.env' -print)
find . -path ./.venv -prune -o -type d -print0 | xargs -0 chmod 755
find . -path ./.venv -prune -o -type f -print0 | xargs -0 chmod 644
chmod 755 deploy/*.sh 2>/dev/null || true

if [[ ! -d .venv ]]; then python3 -m venv .venv; fi
./.venv/bin/pip install --quiet --upgrade pip
./.venv/bin/pip install --quiet flask gunicorn

systemctl restart "$SERVICE"
sleep 3
systemctl is-active "$SERVICE"
REMOTE

echo "==> verify every page, not just /healthz"
FAILED=0
for path in /healthz / /campaign /pose /interactions /delta /benchmark /about; do
  code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 25 "$PUBLIC_HOST$path" || echo 000)
  printf '    %-16s %s\n' "$path" "$code"
  if [[ "$code" != "200" ]]; then FAILED=1; fi
done
if [[ "$FAILED" != "0" ]]; then
  echo "deploy: at least one page is not 200. Try deploy/repair_perms.sh first:" >&2
  echo "        a 500 on every page with a healthy /healthz is almost always" >&2
  echo "        file ownership." >&2
  exit 1
fi
echo "==> deployed and verified"
