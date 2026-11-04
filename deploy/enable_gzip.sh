#!/usr/bin/env bash
# Turn on compression for the static assets on the live vhost (F132).
#
# Why this is its own script rather than part of deploy.sh or provision.sh:
#
# - provision.sh writes the vhost from scratch, and certbot edits that file in
#   place to add the TLS lines. Regenerating it would take HTTPS off the site.
#   So this inserts the directives into the file that is already there.
# - deploy.sh syncs content and restarts the app. Changing nginx's
#   configuration is a different kind of act and belongs somewhere a reader
#   can see it whole before running it.
#
# Order of operations: copy the block up, back the vhost up, splice the block
# in after one directive that is certainly in the server block and certainly
# not inside a location, ask nginx whether the result is valid, and reload
# only if it says yes. A failed test restores the backup and reloads nothing,
# so the worst case is the configuration it started with. Running it twice is
# a no-op.
#
# Measured before writing it: a first visitor to the site pulls 10.1 MB of
# JavaScript and CSS, molstar at 5.1 MB and plotly at 4.45 MB, both
# uncompressed, while the proxied HTML is compressed. nginx's http-level
# default is `gzip_types text/html`, which is exactly that split.
set -euo pipefail
cd "$(dirname "$0")/.."
# shellcheck disable=SC1091
set -a; source .env; set +a
: "${DROPLET_SSH:?}"; : "${SSH_KEY:?}"; : "${PUBLIC_HOST:?}"
KEY_PATH="${SSH_KEY/#\~/$HOME}"
[[ -f "$KEY_PATH" ]] || { echo "no key at $KEY_PATH" >&2; exit 2; }
SSH=(ssh -i "$KEY_PATH" -o BatchMode=yes -o ConnectTimeout=20)

BLOCK_LOCAL="$(mktemp)"
trap 'rm -f "$BLOCK_LOCAL"' EXIT
cat > "$BLOCK_LOCAL" <<'GZIP'

    # Static assets are served from this vhost by alias, and nginx's
    # http-level default compresses text/html only, so everything under
    # /static/ went out at full size: 10.1 MB to a first visitor, of which
    # molstar is 5.1 MB and plotly 4.45 MB. They are vendored and pinned, so
    # they are fetched once per cache lifetime and never change, which is the
    # best case for compressing them (F132).
    #
    # Level 5 rather than 9: the last levels cost noticeably more CPU on a
    # 3.8 GB droplet for a percent or two of size, and this box also runs
    # gunicorn.
    gzip on;
    gzip_vary on;
    gzip_proxied any;
    gzip_comp_level 5;
    gzip_min_length 1024;
    gzip_types text/plain text/css text/javascript application/javascript application/json application/manifest+json image/svg+xml;
GZIP

echo "==> sending the block"
"${SSH[@]}" "$DROPLET_SSH" "cat > /tmp/nobble_gzip.conf" < "$BLOCK_LOCAL"

echo "==> splicing, testing, reloading"
"${SSH[@]}" "$DROPLET_SSH" 'bash -s' <<'REMOTE'
set -euo pipefail
VHOST=/etc/nginx/sites-available/nobble
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"

if grep -q 'gzip_types' "$VHOST"; then
  echo "    gzip_types already present, nothing to do"
  rm -f /tmp/nobble_gzip.conf
  exit 0
fi
if ! grep -q 'client_max_body_size' "$VHOST"; then
  echo "    no client_max_body_size to anchor to; not guessing" >&2
  exit 1
fi

cp "$VHOST" "$VHOST.bak.$STAMP"
# sed's `r` appends a file's contents after the matching line. One anchor,
# one insertion, nothing generated.
sed -i "/client_max_body_size/r /tmp/nobble_gzip.conf" "$VHOST"

if nginx -t; then
  systemctl reload nginx
  echo "    valid, reloaded; backup at $VHOST.bak.$STAMP"
else
  echo "    REFUSED by nginx -t: restoring, nothing reloaded" >&2
  cp "$VHOST.bak.$STAMP" "$VHOST"
  exit 1
fi
rm -f /tmp/nobble_gzip.conf
REMOTE

echo "==> measuring"
for path in /static/vendor/plotly/plotly.min.js /static/vendor/molstar/molstar.js /campaign; do
  raw=$(curl -s -o /dev/null -w '%{size_download}' "https://${PUBLIC_HOST}${path}")
  gz=$(curl -s -H 'Accept-Encoding: gzip' -o /dev/null -w '%{size_download}' "https://${PUBLIC_HOST}${path}")
  printf '    %-44s raw %8d  gzip %8d\n' "$path" "$raw" "$gz"
done
echo "==> done"
