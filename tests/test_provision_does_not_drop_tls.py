"""Provisioning twice must not take HTTPS off a live site.

`deploy/provision.sh` writes the nginx vhost from scratch. certbot adds its
TLS lines into that same file in place, which is why
`deploy/enable_gzip.sh` exists as a separate script that splices rather than
regenerates, and says so in its header. Nothing in provision checked: it was
`cat >` straight over the top, so a second run would replace an HTTPS vhost
with an HTTP-only one, pass `nginx -t` because that is valid configuration,
reload, and serve the site over port 80.

The guard region is extracted from the script and run against a fixture, the
same way `tests/test_enable_gzip_splices_safely.py` runs the splice, so what
is tested is the text the script actually carries.
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "deploy" / "provision.sh"

TLS_VHOST = """server {
    server_name nobble.mdeller.com;
    client_max_body_size 8m;
    listen 443 ssl; # managed by Certbot
    ssl_certificate /etc/letsencrypt/live/nobble.mdeller.com/fullchain.pem;
}
"""
PLAIN_VHOST = """server {
    server_name nobble.mdeller.com;
    listen 80;
}
"""


def _guard_region() -> str:
    """The lines between the vhost heading and the write itself."""
    text = SCRIPT.read_text()
    start = text.index('echo "==> nginx vhost"')
    end = text.index('cat > "$VHOST_PATH" <<VHOST')
    return text[start:end]


def _run(region: str, tmp_path: Path, vhost: str | None, *, force: str = "0"):
    path = tmp_path / "nobble"
    if vhost is not None:
        path.write_text(vhost)
    script = tmp_path / "guard.sh"
    script.write_text("set -euo pipefail\n" + region)
    completed = subprocess.run(
        ["bash", str(script)], capture_output=True, text=True, timeout=60,
        env={**os.environ, "NOBBLE_VHOST_PATH": str(path),
             "NOBBLE_PROVISION_FORCE": force},
    )
    return completed, path


def test_a_vhost_carrying_tls_is_refused(tmp_path):
    completed, path = _run(_guard_region(), tmp_path, TLS_VHOST)
    assert completed.returncode == 1, completed.stdout + completed.stderr
    assert "already carries TLS lines" in completed.stderr, completed.stderr
    assert path.read_text() == TLS_VHOST, "the guard altered the live vhost"


def test_the_refusal_says_what_to_do_instead(tmp_path):
    completed, _ = _run(_guard_region(), tmp_path, TLS_VHOST)
    assert "enable_gzip.sh" in completed.stderr, completed.stderr
    assert "NOBBLE_PROVISION_FORCE=1" in completed.stderr, completed.stderr


def test_a_fresh_host_provisions(tmp_path):
    """No vhost yet, which is what provisioning is for."""
    completed, _ = _run(_guard_region(), tmp_path, None)
    assert completed.returncode == 0, completed.stdout + completed.stderr


def test_a_vhost_without_tls_is_backed_up_and_allowed(tmp_path):
    completed, path = _run(_guard_region(), tmp_path, PLAIN_VHOST)
    assert completed.returncode == 0, completed.stdout + completed.stderr
    backups = sorted(tmp_path.glob("nobble.bak.*"))
    assert len(backups) == 1, backups
    assert backups[0].read_text() == PLAIN_VHOST


def test_forcing_it_is_possible_and_still_backs_up(tmp_path):
    """A deliberate rewrite stays available, and keeps the original."""
    completed, _ = _run(_guard_region(), tmp_path, TLS_VHOST, force="1")
    assert completed.returncode == 0, completed.stdout + completed.stderr
    backups = sorted(tmp_path.glob("nobble.bak.*"))
    assert len(backups) == 1, backups
    assert backups[0].read_text() == TLS_VHOST


def test_the_guard_precedes_the_write():
    """Ordering is the whole guard: after the write it would be a post-mortem."""
    text = SCRIPT.read_text()
    assert text.index("already carries TLS lines") < text.index(
        'cat > "$VHOST_PATH" <<VHOST'), "the guard runs after the overwrite"
    assert 'cat > "/etc/nginx/sites-available/nobble"' not in text, (
        "the vhost path is hard-coded at the write again, so the guard can be "
        "pointed somewhere else than the file being overwritten")
