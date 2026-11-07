"""A recursive chown needs its directory to be a directory.

`deploy/repair_perms.sh` runs, on the droplet:

    cd "$REMOTE_DIR"
    find . -maxdepth 1 ... | xargs -0 -r chown -R "$SERVICE_USER":...
    find . ... -type f -print0 | xargs -0 chmod 644

Its remote block is an unquoted heredoc, so those variables expand locally
before anything is sent. `set -u` aborts on an *unset* variable and says
nothing about an *empty* one, and `cd ""` succeeds in bash and leaves the
shell where it already was. So an empty REMOTE_DIR would have run a recursive
chown and chmod over the ssh login directory, which on that host is root's
home, on a box serving 22 other sites.

`:?` is the operator that rejects empty as well as unset, which is why these
tests ask for it by name rather than for any guard.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# The variables whose emptiness reaches a destructive command, per script.
DESTRUCTIVE = {
    "repair_perms.sh": ("REMOTE_DIR", "SERVICE_USER", "SERVICE",
                        "DROPLET_SSH", "SSH_KEY"),
    "deploy.sh": ("DROPLET_SSH", "SSH_KEY"),
    "provision.sh": ("DROPLET_SSH", "SSH_KEY"),
    "enable_gzip.sh": ("DROPLET_SSH",),
}


def test_cd_to_an_empty_string_succeeds():
    """The premise, pinned, so the guards cannot be argued away.

    If this ever stops being true the guards are still right, but the reason
    recorded for them would be wrong.
    """
    import tempfile

    # A real directory, resolved, because macOS reports /tmp as /private/tmp
    # and the claim is "cd did not move", not "cd is in a named place".
    with tempfile.TemporaryDirectory() as here:
        resolved = str(Path(here).resolve())
        completed = subprocess.run(
            ["bash", "-c", 'set -euo pipefail; cd ""; pwd -P'],
            capture_output=True, text=True, cwd=resolved, timeout=30)
    assert completed.returncode == 0, (
        "cd to an empty string failed, so the guards are still right but the "
        f"reason recorded for them is not: {completed.stderr}")
    assert completed.stdout.strip() == resolved, (
        completed.stdout, resolved)


def test_the_destructive_scripts_reject_empty_as_well_as_unset():
    missing = []
    for name, variables in sorted(DESTRUCTIVE.items()):
        text = (ROOT / "deploy" / name).read_text()
        for variable in variables:
            if f'"${{{variable}:?}}"' not in text:
                missing.append(f"{name}: {variable}")
    assert not missing, (
        "these reach a command that writes, moves or changes ownership, and "
        f"an empty value would aim it somewhere else: {missing}")


def test_repair_perms_guards_before_it_connects():
    """A guard after the ssh has already run the chown is a post-mortem."""
    text = (ROOT / "deploy" / "repair_perms.sh").read_text()
    assert text.index('"${REMOTE_DIR:?}"') < text.index("DROPLET_SSH\" bash -s") \
        if 'DROPLET_SSH" bash -s' in text else True
    assert text.index('"${REMOTE_DIR:?}"') < text.index("chown -R"), text[:0]
