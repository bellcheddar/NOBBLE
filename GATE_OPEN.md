# Gate G3 open: deploy to nobble.mdeller.com

Opened 2026-11-03. Everything that does not depend on this gate is still being
built; this is not a stop.

## What is needed

Two things, in this order. The first is Marc's, on the droplet. The second is a
Claude Code permission.

### 1. The subdomain is not yet serving anything (root actions on the droplet)

`nobble.mdeller.com` resolves to 45.55.102.228, the same host as BINMAN, and
answers HTTP 200 on port 80, but with **nginx's default welcome page**: there is
no NOBBLE vhost. HTTPS fails certificate verification because the only
certificate presented covers `alphabetti.mdeller.com`. So the DNS half of "live"
is done and the server half is not.

Needed on the droplet:

```bash
# an nginx server block for the subdomain, proxying to the gunicorn socket
#   server_name nobble.mdeller.com;
#   location / { proxy_pass http://127.0.0.1:<port>; ... }
certbot --nginx -d nobble.mdeller.com
# and a systemd unit named to match SERVICE in .env, running:
#   gunicorn wsgi:app
systemctl enable --now nobble
```

### 2. Approve the deploy scripts in Claude Code

The unattended permissions deny `ssh`, `scp` and `rsync` deliberately, and
approving these two rules **is** the G3 decision, which is why they are not
pre-approved in `.claude/settings.json`:

```
/permissions
  allow  Bash(bash deploy/deploy.sh)
  allow  Bash(bash deploy/repair_perms.sh)
```

Then: `! bash deploy/deploy.sh`

## What is already done

- `deploy/deploy.sh` and `deploy/repair_perms.sh` are written, parse cleanly and
  follow every rule in the deploy playbook: one multiplexed SSH connection for
  the whole deploy, no retry loop, no `nc` probe, no
  `StrictHostKeyChecking=no`, `--chmod=Du=rwx,Dgo=rx,Fu=rw,Fgo=r` on every
  rsync, ownership fixed **before** pip, and a final check that fetches every
  page rather than only `/healthz`.
- `.env.example` names `DROPLET_SSH` and `SSH_KEY`; a deploy that relies on an
  agent key fails in Claude Code, which has no `SSH_AUTH_SOCK`.
- The application passes local QC: 12 Playwright captures at 1440x900 and
  390x844, zero non-200, zero console errors, zero serious or critical
  axe-core violations.

## What happens next, without this gate

The benchmark campaign is still running and nothing about it depends on
deployment. Scoring, validation and the remaining application work continue.
Nothing has been run against the droplet: no `ssh`, no `rsync`, no connection
attempt of any kind.
