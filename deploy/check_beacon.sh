#!/usr/bin/env bash
# Does the beacon actually count? Not "is it logged" but "would the counter
# see it": the stats script filters bots and its own health pings, so a logged
# beacon is necessary and not sufficient.
set -euo pipefail
cd "$(dirname "$0")/.."
set -a; source .env; set +a
KEY_PATH="${SSH_KEY/#\~/$HOME}"
SSH=(ssh -i "$KEY_PATH" -o BatchMode=yes -o IdentitiesOnly=yes
     -o ControlMaster=auto -o ControlPath="$HOME/.ssh/cm-nobble-%C"
     -o ControlPersist=120 -o ConnectTimeout=20)
trap '"${SSH[@]}" -O exit "$DROPLET_SSH" >/dev/null 2>&1 || true' EXIT
"${SSH[@]}" "$DROPLET_SSH" DOMAIN="$PUBLIC_DOMAIN" bash -s <<'REMOTE'
echo "--- beacon hits in the shared log, by user agent ---"
grep "$DOMAIN" /var/log/nginx/access.log 2>/dev/null \
  | grep '/api/status' \
  | sed 's/.*" "\([^"]*\)" "'"$DOMAIN"'".*/\1/' \
  | sort | uniq -c | sort -rn | head -5
echo "--- total beacon lines ---"
grep "$DOMAIN" /var/log/nginx/access.log 2>/dev/null | grep -c '/api/status' || echo 0
echo "--- what the counter computes right now ---"
python3 /usr/local/bin/mdeller-stats.py >/dev/null 2>&1 || true
python3 -c "
import json
d = json.load(open('/var/www/mdeller/stats.json'))
apps = d.get('apps', d)
apps = list(apps.values()) if isinstance(apps, dict) else apps
for a in apps:
    if isinstance(a, dict) and a.get('id') == 'nobble':
        print('   ', json.dumps(a))
"
REMOTE
