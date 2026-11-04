#!/usr/bin/env bash
# One-time provisioning for nobble.mdeller.com. Idempotent: safe to re-run.
#
# Follows the convention the droplet already uses for its other Flask apps,
# which was read off the host rather than assumed: /opt/<name>, a dedicated
# service user, a .venv inside the app directory, a <name>-web.service, and an
# nginx vhost proxying to a loopback port. An earlier draft of this used
# /srv/nobble, www-data and port 8013; all three were wrong, and 8013 is in use
# by another app.
#
# Twenty-two other sites run on this host. Every nginx change is validated with
# `nginx -t` before a reload, and a failed validation aborts without reloading.
set -euo pipefail
cd "$(dirname "$0")/.."
# shellcheck disable=SC1091
set -a; source .env; set +a

: "${DROPLET_SSH:?}"; : "${SSH_KEY:?}"; : "${REMOTE_DIR:?}"; : "${SERVICE:?}"
: "${SERVICE_USER:?}"; : "${PUBLIC_DOMAIN:?}"; : "${GUNICORN_PORT:?}"

KEY_PATH="${SSH_KEY/#\~/$HOME}"
HOST="${DROPLET_SSH#*@}"
[[ -f "$KEY_PATH" ]] || { echo "provision: no key at $KEY_PATH" >&2; exit 2; }
ssh-keygen -F "$HOST" >/dev/null 2>&1 || { echo "provision: '$HOST' not in known_hosts" >&2; exit 2; }

mkdir -p "$HOME/.ssh/cm" && chmod 700 "$HOME/.ssh/cm"
SSH=(ssh -i "$KEY_PATH" -o BatchMode=yes -o IdentitiesOnly=yes
     -o ControlMaster=auto -o ControlPath="$HOME/.ssh/cm-nobble-%C"
     -o ControlPersist=120 -o ConnectTimeout=20)
trap '"${SSH[@]}" -O exit "$DROPLET_SSH" >/dev/null 2>&1 || true' EXIT

"${SSH[@]}" "$DROPLET_SSH" true || {
  echo "provision: ssh login failed. Do NOT retry: repeated failures get this" >&2
  echo "           IP banned and the symptom becomes a port-22 timeout." >&2
  exit 1; }
echo "==> ssh ok"

"${SSH[@]}" "$DROPLET_SSH" \
  REMOTE_DIR="$REMOTE_DIR" SERVICE="$SERVICE" SERVICE_USER="$SERVICE_USER" \
  PUBLIC_DOMAIN="$PUBLIC_DOMAIN" GUNICORN_PORT="$GUNICORN_PORT" bash -s <<'REMOTE'
set -euo pipefail

echo "==> service user and directory"
id -u "$SERVICE_USER" >/dev/null 2>&1 || useradd --system --home "$REMOTE_DIR" --shell /usr/sbin/nologin "$SERVICE_USER"
mkdir -p "$REMOTE_DIR"
chown "$SERVICE_USER":"$SERVICE_USER" "$REMOTE_DIR"

echo "==> check the port is free"
if ss -lnt | awk '{print $4}' | grep -q ":$GUNICORN_PORT\$"; then
  echo "provision: port $GUNICORN_PORT is already in use by another app" >&2
  exit 2
fi

echo "==> systemd unit"
cat > "/etc/systemd/system/${SERVICE}.service" <<UNIT
# NOBBLE (gunicorn behind nginx). Matches the convention the other apps on this
# host use: /opt/<name>, a dedicated user, a .venv inside, <name>-web.service.
[Unit]
Description=NOBBLE glue-dependence atlas (gunicorn)
After=network.target

[Service]
Type=simple
User=${SERVICE_USER}
Group=${SERVICE_USER}
WorkingDirectory=${REMOTE_DIR}
EnvironmentFile=-${REMOTE_DIR}/.env
Environment="PYTHONUNBUFFERED=1"
# The droplet serves a precomputed, read-only slice: scored records and
# predicted structures, no compute at request time.
Environment="NOBBLE_CAMPAIGN=${REMOTE_DIR}/deploy/atlas"
# Two workers and four threads, matching the other apps here. The host has
# roughly 4 GB available across twenty-odd services and NOBBLE reads JSON from
# disk, so threads carry concurrency more cheaply than processes.
ExecStart=${REMOTE_DIR}/.venv/bin/gunicorn \\
  --workers 2 \\
  --threads 4 \\
  --bind 127.0.0.1:${GUNICORN_PORT} \\
  --timeout 90 \\
  --access-logfile - \\
  --error-logfile - \\
  wsgi:app
Restart=on-failure
RestartSec=3

NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=full
ProtectHome=true
ReadWritePaths=${REMOTE_DIR}

[Install]
WantedBy=multi-user.target
UNIT
systemctl daemon-reload

echo "==> nginx vhost"
cat > "/etc/nginx/sites-available/nobble" <<VHOST
# nginx site for NOBBLE (${PUBLIC_DOMAIN}).
server {
    server_name ${PUBLIC_DOMAIN};

    # Shared access log in the vhost format so the mdeller.com launcher's hit
    # counter sees it: a private log or the default format reads a flat zero.
    access_log /var/log/nginx/access.log vhost;

    client_max_body_size 8m;

    # Compression. nginx's http-level default is \`gzip_types text/html\`, so
    # the proxied pages were compressed and nothing served from /static/ was:
    # measured on the live site, a first visitor pulled 10.1 MB of JavaScript
    # and CSS, of which molstar is 5.1 MB and plotly 4.45 MB, both at full
    # size. They are vendored and pinned, so they are served exactly once per
    # cache lifetime and then never change, which is the best case for
    # compressing them (F132).
    #
    # Level 5 rather than 9: the last levels cost noticeably more CPU on a
    # 3.8 GB droplet for a percent or two of size, and this box also runs
    # gunicorn. min_length skips the small files where the header costs more
    # than the saving.
    gzip on;
    gzip_vary on;
    gzip_proxied any;
    gzip_comp_level 5;
    gzip_min_length 1024;
    gzip_types
        text/plain
        text/css
        text/javascript
        application/javascript
        application/json
        application/manifest+json
        image/svg+xml;

    location /static/js/ {
        alias ${REMOTE_DIR}/nobble/app/static/js/;
        add_header Cache-Control "no-cache" always;
        access_log off;
    }

    location /static/ {
        alias ${REMOTE_DIR}/nobble/app/static/;
        add_header Cache-Control "public, max-age=3600" always;
        access_log off;
    }

    location / {
        proxy_pass http://127.0.0.1:${GUNICORN_PORT};
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        # Mol* pulls whole mmCIF files; a cold page cache can take a moment.
        proxy_read_timeout 90s;
    }

    listen 80;
}
VHOST
ln -sfn /etc/nginx/sites-available/nobble /etc/nginx/sites-enabled/nobble

echo "==> validate nginx before reloading (22 other sites run here)"
nginx -t
systemctl reload nginx
echo "==> nginx reloaded"
REMOTE

echo "==> provisioned. TLS is a separate step: deploy/certbot.sh"
