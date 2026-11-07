#!/usr/bin/env bash
# Re-apply ownership and modes on the droplet, then restart and report.
#
# The one to reach for when every page returns 500 but /healthz is fine: that
# combination is almost always the service user being unable to read its own
# application, because rsync carried the Mac's owner-only modes across.
set -euo pipefail
cd "$(dirname "$0")/.."
# shellcheck disable=SC1091
set -a; source .env; set +a

# Required, and required to be non-empty, which `set -u` does not give.
#
# The remote block below is an unquoted heredoc, so these expand here before
# anything is sent. `set -u` aborts on an unset variable and says nothing
# about an empty one, and `cd ""` succeeds in bash and leaves you where you
# are. So an empty REMOTE_DIR would send `cd ""` followed by a recursive
# chown and a recursive chmod over `.`, which on the droplet is the ssh login
# directory rather than the application. This is the most destructive script
# in deploy/ and it was the only one with no guards at all (F241).
: "${DROPLET_SSH:?}"
: "${SSH_KEY:?}"
: "${REMOTE_DIR:?}"
: "${SERVICE_USER:?}"
: "${SERVICE:?}"
: "${PUBLIC_HOST:?}"

KEY_PATH="${SSH_KEY/#\~/$HOME}"
mkdir -p "$HOME/.ssh/cm" && chmod 700 "$HOME/.ssh/cm"
SSH=(ssh -i "$KEY_PATH" -o BatchMode=yes -o IdentitiesOnly=yes
     -o ControlMaster=auto -o ControlPath="$HOME/.ssh/cm-nobble-%C"
     -o ControlPersist=120 -o ConnectTimeout=20)
trap '"${SSH[@]}" -O exit "$DROPLET_SSH" >/dev/null 2>&1 || true' EXIT

"${SSH[@]}" "$DROPLET_SSH" bash -s <<REMOTE
set -euo pipefail
cd "$REMOTE_DIR"
find . -maxdepth 1 -mindepth 1 ! -name '.venv' ! -name '.env' -print0 \
  | xargs -0 -r chown -R "$SERVICE_USER":"$SERVICE_USER"
find . -path ./.venv -prune -o -type d -print0 | xargs -0 chmod 755
find . -path ./.venv -prune -o -type f -print0 | xargs -0 chmod 644
chmod 755 deploy/*.sh 2>/dev/null || true
systemctl restart "$SERVICE"
sleep 3
systemctl is-active "$SERVICE"
REMOTE

for path in /healthz / /campaign /pose /interactions /delta /benchmark /about; do
  code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 25 "$PUBLIC_HOST$path" || echo 000)
  printf '%-16s %s\n' "$path" "$code"
done
