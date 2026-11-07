"""Nothing credential-shaped is committed, asserted rather than swept once.

F128 checked this by hand before considering a push and found the repository
clean: the deploy takes `DROPLET_SSH`, `SSH_KEY`, `REMOTE_DIR` and `SERVICE`
from the environment with `${VAR:?}` so it fails rather than defaults, no key
or `.env` is tracked, and no PEM block or credential-shaped assignment appears
in any tracked file. What that finding fixed was a different leak, the build
machine's absolute paths, and it left a test behind for that one.

The credential half was never asserted, so it held by inspection on one day
in November and by nothing afterwards. I re-ran the same sweep on 7 November
without reading F128, which had appeared in my own search results (F295).

CLAUDE.md puts it as a gate: G2 opens when a credential is needed, and the
secret arrives via environment variable, never written into files. This is
that rule as a test.

Values are never printed. A failure names the file and the shape it matched,
because a test that reports a secret to prove it found one has published it.
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

# Shapes rather than values, and deliberately narrow: a pattern loose enough
# to catch everything catches `password = "changeme"` in a comment and gets
# switched off.
SHAPES = {
    "private key block": re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    "ssh public key material": re.compile(r"ssh-(rsa|ed25519) AAAA"),
    "github token": re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}"),
    "aws access key id": re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    "credential-shaped assignment": re.compile(
        r"(?i)\b(api[_-]?key|secret|passwd|password|token)\b\s*[:=]\s*"
        r"['\"][A-Za-z0-9/+=_-]{16,}['\"]"),
    "provider-prefixed secret": re.compile(
        r"\b(xox[baprs]-|sk_live_)[A-Za-z0-9-]{10,}"),
}

SKIP_SUFFIXES = {".cif", ".npz", ".png", ".ico", ".a3m", ".pkl", ".gz"}


def _tracked() -> list[str]:
    out = subprocess.run(["git", "ls-files"], capture_output=True, text=True,
                         cwd=ROOT)
    if out.returncode != 0:
        pytest.skip("not a git repository")
    return out.stdout.split()


def test_no_tracked_file_matches_a_credential_shape():
    tracked = _tracked()
    assert len(tracked) > 100, f"only {len(tracked)} tracked file(s) found"
    offenders = []
    for name in tracked:
        path = ROOT / name
        if not path.is_file() or path.suffix in SKIP_SUFFIXES:
            continue
        try:
            text = path.read_text(errors="ignore")
        except OSError:
            continue
        for label, pattern in SHAPES.items():
            if pattern.search(text):
                # The label and the path, never the match.
                offenders.append(f"{name}: {label}")
    assert not offenders, (
        "tracked file(s) carry credential-shaped content: "
        + "; ".join(sorted(offenders)))


def test_the_environment_file_is_ignored_and_untracked():
    """The deploy sources `.env`; publishing it would hand over the droplet."""
    ignored = subprocess.run(["git", "check-ignore", ".env"],
                             capture_output=True, cwd=ROOT).returncode == 0
    assert ignored, ".env is not ignored, so an editor could stage it"
    assert ".env" not in _tracked(), ".env is tracked"


def test_the_deploy_refuses_rather_than_defaulting():
    """G2's shape in the scripts: no credential has a fallback value.

    `${VAR:?}` fails on unset and on empty, which is the guard F241 added to
    the most destructive script in deploy/ after finding it had none.
    """
    for name in ("deploy.sh", "repair_perms.sh"):
        path = ROOT / "deploy" / name
        if not path.exists():
            continue
        text = path.read_text()
        for variable in ("DROPLET_SSH", "SSH_KEY", "REMOTE_DIR"):
            if variable not in text:
                continue
            assert re.search(rf'\$\{{{variable}:\?|: "\$\{{{variable}:\?\}}"',
                             text), (
                f"{name} uses {variable} without a `:?` guard, so an unset "
                "or empty value would default rather than fail")


def test_the_shapes_catch_a_planted_example(tmp_path):
    """The patterns are checked against text, so they can silently narrow."""
    # Assembled rather than written out. A planted example spelled in full
    # is a tracked file matching a credential shape, so the first version of
    # this file failed its own sweep: the private-key marker in the dict
    # below was the match.
    planted = {
        "private key block": "-----BEGIN OPENSSH PRIVATE " + "KEY-----\nabc\n",
        "github token": "token = ghp_" + "a" * 36,
        "aws access key id": "AKIA" + "A" * 16,
        "credential-shaped assignment": 'api_key = "' + "x" * 24 + '"',
    }
    for label, text in planted.items():
        assert SHAPES[label].search(text), f"{label} no longer matches its own example"
