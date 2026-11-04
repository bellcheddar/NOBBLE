"""The project root is iCloud-backed, and iCloud writes behind the build (F173).

`deploy/build_atlas.py` clears `deploy/atlas` before it writes, so the builder
cannot leave a stale structure behind. iCloud can: when it holds a copy of a
file that the rebuild has just replaced, it restores that copy alongside the
new one under a " 2" suffix, with its own earlier timestamp and owner-only
permissions. One arrived in `deploy/atlas/structures` that way, and `git add
-A` in the F171 commit tracked it into the published bundle.

F148 caught it, as a structure on the droplet that no row names, and that is
the check that matters. This one only gives the class of file its own name, so
the next one is read off a test name rather than diagnosed from a byte compare
and a `git log` walk. Cheap, because the answer is always the same: delete it.

Two places are checked. Everything git tracks, because a conflict copy that
gets committed is published and deployed. And everything under `deploy/atlas`
whether tracked or not, because that directory is what rsync sends.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# "name 2.cif", "name 3.json": a space, digits, then the extension. Distinct
# from an ordinary name that happens to end in a number, which has no space
# before it, and from a versioned name like "_v2", which has no space either.
CONFLICT = re.compile(r" \d+\.[A-Za-z0-9]+$")


def _tracked() -> list[str]:
    done = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=ROOT, capture_output=True, text=True, check=True,
    )
    return [name for name in done.stdout.split("\0") if name]


def test_no_tracked_file_is_a_sync_conflict_copy():
    found = [name for name in _tracked() if CONFLICT.search(Path(name).name)]
    assert found == [], (
        "iCloud sync-conflict copies are tracked in git, so they ship to the "
        f"droplet: {found}. Remove them with `git rm`."
    )


def test_no_file_in_the_published_bundle_is_a_sync_conflict_copy():
    atlas = ROOT / "deploy" / "atlas"
    if not atlas.exists():
        return
    found = sorted(
        str(path.relative_to(ROOT))
        for path in atlas.rglob("*")
        if path.is_file() and CONFLICT.search(path.name)
    )
    assert found == [], (
        "sync-conflict copies are sitting in the bundle rsync publishes, "
        f"where nothing references them: {found}"
    )


def test_the_pattern_tells_a_conflict_copy_from_an_ordinary_name():
    assert CONFLICT.search("bench01_GSPT1_CRBN__binary__unconstrained__seed5 2.cif")
    assert CONFLICT.search("validation 3.json")
    # Names the project actually uses, none of which may trip the check.
    for ordinary in (
        "bench01_GSPT1_CRBN__binary__unconstrained__seed5.cif",
        "nobble_icon_300.png",
        "scores.jsonl",
        "molstar-bridge.js",
        "thresholds.toml",
        "peptide_pose_explorer_v2.html",
    ):
        assert not CONFLICT.search(ordinary), ordinary
