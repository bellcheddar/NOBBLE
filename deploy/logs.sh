#!/usr/bin/env bash
# Tail the service log. Read-only.
set -euo pipefail
cd "$(dirname "$0")/.."
set -a; source .env; set +a
KEY_PATH="${SSH_KEY/#\~/$HOME}"
SSH=(ssh -i "$KEY_PATH" -o BatchMode=yes -o IdentitiesOnly=yes
     -o ControlMaster=auto -o ControlPath="$HOME/.ssh/cm-nobble-%C"
     -o ControlPersist=120 -o ConnectTimeout=20)
trap '"${SSH[@]}" -O exit "$DROPLET_SSH" >/dev/null 2>&1 || true' EXIT
"${SSH[@]}" "$DROPLET_SSH" "journalctl -u ${SERVICE} -n ${1:-40} --no-pager"
