# Deployment

**Live: https://nobble.mdeller.com** (TLS, HTTP redirects to HTTPS).

Gate G3 is closed. The certificate was issued on 2026-11-03 and expires
2027-02-01; certbot's scheduled renewal handles it from here.

## What runs where

| Piece | Where |
|---|---|
| Application | `/opt/nobble`, service user `nobble`, `nobble-web.service` |
| Server | gunicorn, 2 workers, 4 threads, bound to 127.0.0.1:8015 |
| Proxy | nginx vhost `nobble`, TLS by certbot |
| Data | `/opt/nobble/deploy/atlas`, a precomputed read-only slice |

Conventions were read off the host rather than assumed, which mattered: the
other applications use `/opt/<name>` with a dedicated service user and a
`<name>-web` unit, not `/srv` and `www-data`, and port 8013 (the first choice)
was already taken.

## The droplet computes nothing

It serves the scored records and the predicted structures and imports no
scientific stack at request time. That is spec Phase 4's requirement and the
deployment proved why it is a requirement rather than a preference: `/benchmark`
and `/about` imported `nobble.curate` to render, passed every local check, and
returned 500 in production because the droplet has no gemmi.

`tests/test_deployed_app.py` now blocks gemmi, pandas, freesasa, rdkit, sklearn,
torch and transformers from importing and asserts every page still serves. It
found a second instance of the same fault immediately, in the structures
endpoint, which would have left the Pose viewer unable to load anything.

## What is not published

`deploy/build_atlas.py` withholds the PROTAC-DB chemistry and verifies the
redaction before writing the bundle: publishing to a public site is
redistribution exactly as a public repository is. CCD codes and their SMILES
are unaffected, being public PDB data.

## Verification

Both on every deploy:

- `deploy/deploy.sh` fetches all eight pages and fails loudly on anything that
  is not 200, because `/healthz` has answered `{"ok": true}` while every real
  page returned 500.
- `NOBBLE_BASE=https://nobble.mdeller.com npx node qc/qc.mjs` drives the live
  site in a browser: 12 captures at 1440x900 and 390x844, zero non-200, zero
  console errors, zero serious or critical axe-core violations.

One accessibility fix belongs to a dependency rather than to NOBBLE: Mol*
injects an unlabelled logo link, which is labelled from NOBBLE's own code
rather than by patching the vendored bundle, since editing a pinned dependency
would be undone by the next version bump and would make the copy differ from
BINMAN's.

## Scripts

| Script | Does |
|---|---|
| `deploy/survey.sh`, `survey2.sh` | Read-only survey of the host |
| `deploy/provision.sh` | One-time, idempotent: user, unit, vhost |
| `deploy/certbot.sh` | TLS, separate because it is rate-limited |
| `deploy/build_atlas.py` | Builds and redacts the published slice |
| `deploy/deploy.sh` | Sync, chown before pip, restart, verify every page |
| `deploy/repair_perms.sh` | When every page 500s but `/healthz` is fine |
| `deploy/logs.sh` | Tail the service log |
