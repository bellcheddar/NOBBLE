"""The one script that is run by hand, as root, against production.

`deploy/enable_gzip.sh` edits the live nginx vhost. It is deliberately not
part of `deploy.sh`, because certbot owns lines in that file and
regenerating it would take HTTPS off the site, so the script splices into
what is already there. A direct ssh to the vhost is declined to me, which is
why the script is written to be read before it is run.

Read is weaker than run. The splice, the idempotency, the anchor refusal and
the restore-on-refusal are all testable without a droplet: the remote half is
a self-contained heredoc, and with the vhost path and the block path taken
from the environment it can be run against a fixture with a fake nginx on
PATH. That is what this does.

The block is extracted from the script rather than copied into the test, so
the test cannot pass against a version of the splice the script no longer
holds.
"""
from __future__ import annotations

import os
import re
import stat
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "deploy" / "enable_gzip.sh"

VHOST = """server {
    listen 443 ssl;
    server_name nobble.mdeller.com;
    client_max_body_size 32m;

    location /static/ {
        alias /srv/nobble/static/;
    }
}
"""


def _heredoc(name: str) -> str:
    """The body of the script's `<<'NAME' ... NAME` heredoc."""
    text = SCRIPT.read_text()
    match = re.search(rf"<<'{name}'\n(.*?)\n{name}\n", text, re.S)
    assert match, f"no {name} heredoc in {SCRIPT.name}"
    return match.group(1)


def _fake(directory: Path, name: str, body: str) -> None:
    path = directory / name
    path.write_text("#!/usr/bin/env bash\n" + body + "\n")
    path.chmod(path.stat().st_mode | stat.S_IEXEC)


@pytest.fixture
def splice(tmp_path):
    """Run the script's remote half against a fixture vhost."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    reloads = tmp_path / "reloads"
    _fake(bin_dir, "systemctl", f'echo "$@" >> {reloads}')

    vhost = tmp_path / "nobble"
    vhost.write_text(VHOST)
    block = tmp_path / "block.conf"
    block.write_text(_heredoc("GZIP"))
    remote = tmp_path / "remote.sh"
    remote.write_text(_heredoc("REMOTE"))

    def run(*, nginx_ok: bool = True, vhost_text: str | None = None):
        if vhost_text is not None:
            vhost.write_text(vhost_text)
        _fake(bin_dir, "nginx", "exit 0" if nginx_ok else "exit 1")
        completed = subprocess.run(
            ["bash", str(remote)], capture_output=True, text=True, timeout=60,
            env={**os.environ,
                 "PATH": f"{bin_dir}:{os.environ['PATH']}",
                 "NOBBLE_VHOST": str(vhost),
                 "NOBBLE_GZIP_BLOCK": str(block)},
        )
        return completed

    run.vhost = vhost
    run.block = block
    run.reloads = reloads
    run.directory = tmp_path
    return run


def test_it_splices_the_block_after_the_anchor(splice):
    assert splice().returncode == 0
    spliced = splice.vhost.read_text()
    assert "gzip_types" in spliced
    assert "chemical/x-mmcif" in spliced

    # Inside the server block and after the anchor, not inside the location:
    # that is the whole reason the anchor is client_max_body_size.
    anchor = spliced.index("client_max_body_size")
    assert spliced.index("gzip on;") > anchor
    assert spliced.index("gzip on;") < spliced.index("location /static/")


def test_running_it_twice_changes_nothing(splice):
    assert splice().returncode == 0
    once = splice.vhost.read_text()
    second = splice()
    assert second.returncode == 0
    assert "already present" in second.stdout, second.stdout
    assert splice.vhost.read_text() == once


def test_it_reloads_nginx_once_and_only_after_a_passing_test(splice):
    assert splice().returncode == 0
    assert splice.reloads.read_text().split() == ["reload", "nginx"]


def test_a_vhost_with_no_anchor_is_refused_and_left_alone(splice):
    without = VHOST.replace("    client_max_body_size 32m;\n", "")
    completed = splice(vhost_text=without)
    assert completed.returncode == 1
    assert "not guessing" in completed.stderr, completed.stderr
    assert splice.vhost.read_text() == without
    assert not splice.reloads.exists(), "reloaded a vhost it refused to edit"


def test_a_configuration_nginx_rejects_is_restored_and_not_reloaded(splice):
    completed = splice(nginx_ok=False)
    assert completed.returncode == 1
    assert "REFUSED by nginx -t" in completed.stderr, completed.stderr
    assert splice.vhost.read_text() == VHOST, (
        "the vhost was left spliced after nginx rejected it")
    assert not splice.reloads.exists(), "reloaded a configuration nginx rejected"


def test_the_original_vhost_is_kept(splice):
    assert splice().returncode == 0
    backups = sorted(splice.directory.glob("nobble.bak.*"))
    assert len(backups) == 1, backups
    assert backups[0].read_text() == VHOST


def test_the_block_it_splices_is_the_one_the_script_sends(splice):
    """One block, defined once. A test carrying its own copy would pass
    against a splice the script no longer performs."""
    sent = _heredoc("GZIP")
    assert "gzip_comp_level 5;" in sent
    assert splice().returncode == 0
    for line in sent.strip().splitlines():
        assert line in splice.vhost.read_text(), line
