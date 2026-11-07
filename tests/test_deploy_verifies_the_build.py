"""A deploy has to check that the droplet serves what was shipped (F140).

`deploy/deploy.sh` ends by fetching every page and requiring 200, and the
comment above it records why: /healthz has answered {"ok": true} while every
real page returned 500. That check is right and it is not enough. An rsync
that excluded a file, a gunicorn that restarted on a stale import, a worker
that outlived the restart: each answers 200 on every page with the previous
build.

Which is the hole F138 found in browser QC, one layer down. The same
fingerprint closes it.
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEPLOY = (ROOT / "deploy" / "deploy.sh").read_text()


def test_the_shipped_fingerprint_is_taken_before_the_rsync():
    """Taken after the sync it would describe the Mac, not the bundle.

    They are the same thing unless the tree changes during a deploy, which
    is exactly when this check matters.
    """
    assert "tools/app_fingerprint.py" in DEPLOY
    shipped = DEPLOY.index("SHIPPING=$(")
    sync = DEPLOY.index('rsync -rlpt --delete \\')
    assert shipped < sync, (
        "the fingerprint is taken after the rsync, so it describes the tree "
        "as it is now rather than the tree that was sent"
    )


def test_the_check_runs_after_the_pages_are_verified():
    """Order matters for the diagnosis, not for correctness.

    A build mismatch on a site whose pages are 500 is a confusing thing to
    be told: the page check names the usual cause, file ownership, and should
    get there first.
    """
    pages = DEPLOY.index("verify every page")
    build = DEPLOY.index("is the droplet serving the tree that was shipped")
    assert pages < build


def test_a_missing_fingerprint_fails_the_deploy():
    """The loophole worth refusing.

    A server from before this check reports no fingerprint. Treating that as
    "cannot tell, carry on" would pass every deploy that failed to take
    effect, which is the case the check exists for.
    """
    section = DEPLOY[DEPLOY.index("is the droplet serving the tree that was shipped"):]
    assert '-z "$SERVING"' in section, (
        "an absent fingerprint is not treated as a failure"
    )
    guard = section[:section.index("$SERVING\" != \"$SHIPPING")]
    assert "exit 1" in guard


def test_a_mismatch_fails_the_deploy_and_says_how_to_compare():
    section = DEPLOY[DEPLOY.index("is the droplet serving the tree that was shipped"):]
    assert '"$SERVING" != "$SHIPPING"' in section
    assert "--detail" in section, (
        "a mismatch stops the deploy without saying how to find which file "
        "differs"
    )
    assert section.count("exit 1") >= 2


def test_the_fingerprint_sources_are_all_rsynced():
    """The digest compares like with like only if the droplet has the files.

    An excluded path would be hashed on the Mac and absent on the droplet,
    so the two could never agree and every deploy would refuse.
    """
    from nobble.app import fingerprint

    # Several excludes per line, so every one on the line is parsed.
    excludes = []
    for line in DEPLOY.splitlines():
        parts = line.split("--exclude '")[1:]
        excludes += [part.split("'")[0] for part in parts]
    assert excludes, "the rsync no longer has excludes, so this test is vacuous"
    for path in fingerprint.files():
        relative = str(path.relative_to(ROOT))
        for pattern in excludes:
            bare = pattern.rstrip("/")
            if bare.startswith("*"):
                assert not relative.endswith(bare.lstrip("*")), \
                    f"{relative} is hashed and excluded by {pattern}"
            else:
                assert not relative.startswith(bare + "/"), \
                    f"{relative} is hashed and excluded by {pattern}"


def test_the_drift_gate_is_asked_before_the_atlas_is_sent():
    """The order is what makes the gate a gate.

    `deploy.sh` rsyncs the application code first, excluding
    `deploy/atlas/`, and sends the atlas in a second rsync further down.
    Between them it asks `tools/atlas_drift.py` whether the published bundle
    is what the current code builds, and exits 1 if not. A reader skimming
    the script sees an rsync above the gate and could reasonably conclude
    the bundle has already gone; it has not, and this pins that.

    It matters now rather than in principle: `deploy/atlas` holds a bundle
    built before the featurisation guard existed, so the rebuild refuses and
    `atlas_drift.py` exits 1 (F224). The gate is the thing standing between
    that bundle and the site, alongside the publication hold.
    """
    gate = DEPLOY.index("tools/atlas_drift.py")
    atlas_rsync = DEPLOY.index("deploy/atlas/ \"$DROPLET_SSH:")
    assert gate < atlas_rsync, (
        "the atlas is sent before the drift gate is asked, so a bundle the "
        "current code would refuse to build can still reach the site")

    # And the code rsync above it does not carry the atlas with it.
    code_rsync = DEPLOY.index("==> sync application code")
    assert code_rsync < gate
    assert "--exclude 'deploy/atlas/'" in DEPLOY[code_rsync:gate]


def test_the_hold_is_asked_before_anything_opens_a_connection():
    """A held atlas should not reach the droplet at all, not even to look."""
    hold = DEPLOY.index("tools/publication_hold.py")
    for outbound in ("rsync -rlpt", "==> sync application code"):
        assert hold < DEPLOY.index(outbound), outbound
