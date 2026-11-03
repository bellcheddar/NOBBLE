# Gate G3: deployed, with one step blocked

Updated 2026-11-03. NOBBLE is **live on the droplet and serving over HTTP**.
One step remains and it is blocked by a permission rule, not by the work.

## Done

- Host surveyed read-only first, so its conventions were read rather than
  assumed. They differ from what the deploy script originally assumed in three
  ways, all of which would have failed: apps live in `/opt/<name>` not `/srv`,
  each has a dedicated service user not `www-data`, the unit is
  `<name>-web.service`, and port 8013 (the first choice) is already in use.
- Provisioned: `nobble` service user, `/opt/nobble`, `nobble-web.service`
  (2 workers, 4 threads, bound to 127.0.0.1:8015, with the same hardening the
  other apps use), and an nginx vhost. `nginx -t` validated before every
  reload, because twenty-two other sites run on this host.
- Deployed and verified: all eight pages return 200 on the live host.
- The published slice withholds the PROTAC-DB chemistry and verifies the
  redaction before writing.

## Blocked: the TLS certificate

`deploy/certbot.sh` is written, parses and is idempotent, but running it is
refused by the Claude Code permission classifier, which categorises it as a
DNS, domain or certificate change. That is a reasonable thing to gate and it
has not been worked around.

**To finish, run it yourself:**

```bash
! bash deploy/certbot.sh
```

It runs `certbot --nginx -d nobble.mdeller.com --redirect`, which both installs
the certificate and adds the HTTP-to-HTTPS redirect. It exits without doing
anything if a certificate already exists.

Until then the site answers on `http://nobble.mdeller.com` and
`https://nobble.mdeller.com` fails certificate verification, because the only
certificate the host presents for that name is the default vhost's.

## Also needs you, and cannot be scripted

A GitHub repository has no avatar of its own: it inherits the owner's. The
social preview image is settable only through the repository settings page,
which was verified rather than assumed (the repository object exposes no such
field and `gh repo edit` has no flag for it). `nobble_icon_300.png` is in the
repository, ready to upload at **Settings, General, Social preview**.
