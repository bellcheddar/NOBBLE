#!/usr/bin/env bash
# Deploy NOBBLE to the droplet.
#
# Every rule below was written after a real failure, and none is optional:
#
# - ONE multiplexed ssh connection for the whole deploy. The droplet bans IPs
#   that open several connections in quick succession.
# - NO retry loop. A failed login is diagnosed locally, never retried:
#   repeated failures get the Mac's IP banned, which then looks exactly like a
#   port-22 timeout.
# - rsync carries --chmod. ~/Documents/Vibe_Coding is iCloud-backed and
#   owner-only, and `rsync -a` copies those modes verbatim, which leaves the
#   service user unable to read its own application: every page returns 500.
# - chown runs BEFORE pip. A chown placed after pip never runs when pip fails
#   under `set -e`.
# - The final check fetches every page, not just /healthz. /healthz has
#   answered {"ok": true} while every real page returned 500.
set -euo pipefail
cd "$(dirname "$0")/.."
# shellcheck disable=SC1091
set -a; source .env; set +a

: "${DROPLET_SSH:?}"; : "${SSH_KEY:?}"; : "${REMOTE_DIR:?}"; : "${SERVICE:?}"
: "${SERVICE_USER:?}"; : "${PUBLIC_HOST:?}"

KEY_PATH="${SSH_KEY/#\~/$HOME}"
HOST="${DROPLET_SSH#*@}"

echo "==> pre-flight"
[[ -f "$KEY_PATH" ]] || { echo "deploy: no key at $KEY_PATH" >&2; exit 2; }
ssh-keygen -F "$HOST" >/dev/null 2>&1 || {
  echo "deploy: no known_hosts entry for '$HOST'. Add it by copying the" >&2
  echo "        already-trusted line after checking the fingerprint. Never" >&2
  echo "        StrictHostKeyChecking=no." >&2; exit 2; }

if [[ ! -d nobble/app/static/vendor ]] || [[ -z "$(ls -A nobble/app/static/vendor 2>/dev/null)" ]]; then
  echo "deploy: nobble/app/static/vendor is empty. Populate it first:" >&2
  echo "        cp -r ../BINMAN/app/static/vendor/. nobble/app/static/vendor/" >&2
  exit 2
fi
if [[ ! -d deploy/atlas ]]; then
  echo "deploy: deploy/atlas is missing. Build it first:" >&2
  echo "        python deploy/build_atlas.py" >&2
  exit 2
fi

mkdir -p "$HOME/.ssh/cm" && chmod 700 "$HOME/.ssh/cm"
SSH=(ssh -i "$KEY_PATH" -o BatchMode=yes -o IdentitiesOnly=yes
     -o ControlMaster=auto -o ControlPath="$HOME/.ssh/cm-nobble-%C"
     -o ControlPersist=120 -o ConnectTimeout=20
     -o ServerAliveInterval=30 -o ServerAliveCountMax=4)
trap '"${SSH[@]}" -O exit "$DROPLET_SSH" >/dev/null 2>&1 || true' EXIT

"${SSH[@]}" "$DROPLET_SSH" true || {
  echo "deploy: ssh login failed. Do NOT retry: repeated failures get this IP" >&2
  echo "        banned. Diagnose locally (key, known_hosts, ~/.ssh/config) and" >&2
  echo "        control for the network with: ssh -T git@github.com" >&2
  exit 1; }
echo "    ssh ok, multiplexed"

echo "==> sync application code"
rsync -rlpt --delete \
  --chmod=Du=rwx,Dgo=rx,Fu=rw,Fgo=r \
  -e "${SSH[*]}" \
  --exclude '.git/' --exclude '.env' --exclude '.venv/' --exclude '.pixi/' \
  --exclude '__pycache__/' --exclude '*.pyc' --exclude 'node_modules/' \
  --exclude 'campaigns/' --exclude 'logs/' --exclude 'qc/' \
  --exclude 'data/msa/' --exclude 'data/cache/' --exclude 'data/interim/' \
  --exclude 'deploy/atlas/' \
  --exclude '*.duckdb' --exclude '*.sqlite*' \
  ./ "$DROPLET_SSH:$REMOTE_DIR/"

# Is the bundle about to be published what the current code builds?
#
# F93's superseded-substrate caveat was written, tested and committed, and
# was not on the page: comparison.json is built by the atlas and the atlas
# had not been rebuilt, so the published conclusion ended before the
# caveat and a deploy carried it to the droplet unchanged. Nothing noticed,
# because nothing compared the two (F96).
#
# Refusing rather than rebuilding here. A deploy that silently rebuilds is
# a deploy that publishes something nobody looked at, and the rebuild is
# one command whose output the operator should see.
echo "==> is the atlas in step with the code"
# deploy.sh has no interpreter variable of its own: it is a shell script
# that rsyncs and restarts, and this is the one Python it needs.
ATLAS_PY="${ATLAS_PY:-../BINMAN/.pixi/envs/default/bin/python}"
if ! PYTHONPATH=. KMP_DUPLICATE_LIB_OK=TRUE "$ATLAS_PY" tools/atlas_drift.py; then
  echo "    REFUSING TO DEPLOY: the published atlas is not what the current" >&2
  echo "    code builds. Rebuild it first:" >&2
  echo "      PYTHONPATH=. python deploy/build_atlas.py <campaign>" >&2
  exit 1
fi

echo "==> sync the published atlas"
# Built and redacted by deploy/build_atlas.py: PROTAC-DB chemistry is withheld,
# because publishing to a public site is redistribution.
rsync -rlpt --delete --chmod=Du=rwx,Dgo=rx,Fu=rw,Fgo=r -e "${SSH[*]}" \
  deploy/atlas/ "$DROPLET_SSH:$REMOTE_DIR/deploy/atlas/"

echo "==> remote: ownership first, then dependencies, then restart"
"${SSH[@]}" "$DROPLET_SSH" \
  REMOTE_DIR="$REMOTE_DIR" SERVICE="$SERVICE" SERVICE_USER="$SERVICE_USER" bash -s <<'REMOTE'
set -euo pipefail
cd "$REMOTE_DIR"

# Ownership BEFORE anything that can fail.
find . -maxdepth 1 -mindepth 1 ! -name '.venv' ! -name '.env' -print0 \
  | xargs -0 -r chown -R "$SERVICE_USER":"$SERVICE_USER"
find . -path ./.venv -prune -o -type d -print0 | xargs -0 -r chmod 755
find . -path ./.venv -prune -o -type f -print0 | xargs -0 -r chmod 644
chmod 755 deploy/*.sh 2>/dev/null || true

if [[ ! -d .venv ]]; then
  python3 -m venv .venv
  chown -R "$SERVICE_USER":"$SERVICE_USER" .venv
fi
./.venv/bin/pip install --quiet --upgrade pip
./.venv/bin/pip install --quiet flask gunicorn
chown -R "$SERVICE_USER":"$SERVICE_USER" .venv

systemctl enable --now "$SERVICE" >/dev/null 2>&1 || true
systemctl restart "$SERVICE"
sleep 4
systemctl is-active "$SERVICE"
REMOTE

echo "==> verify every page, not just /healthz"
# PUBLIC_HOST is https once the certificate exists. Until then, verifying over
# https reports 000 for every page and says nothing about whether the app
# works, so the check falls back to http and says which scheme it used.
if ! curl -s -o /dev/null --max-time 10 "${PUBLIC_HOST}/healthz"; then
  PUBLIC_HOST="${PUBLIC_HOST/https:/http:}"
  echo "    (no TLS yet: verifying over http)"
fi
FAILED=0
for path in /healthz / /campaign /pose /interactions /delta /benchmark /design /about; do
  code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 30 "${PUBLIC_HOST}${path}") || code=000
  printf '    %-16s %s\n' "$path" "$code"
  [[ "$code" == "200" ]] || FAILED=1
done
if [[ "$FAILED" != "0" ]]; then
  echo "deploy: at least one page is not 200. Try deploy/repair_perms.sh first:" >&2
  echo "        a 500 on every page with a healthy /healthz is almost always" >&2
  echo "        file ownership." >&2
  exit 1
fi
echo "==> deployed and verified"
