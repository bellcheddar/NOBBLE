"""D-NOB-007: shared code is widened in place, never forked.

    Shared code is widened in place in BINMAN or BoltzMaker, never forked.

Stated in CLAUDE.md and checked by nothing. This enumerates every file
NOBBLE holds at the same relative path as one of its two peers and requires
them to be byte-identical, so a local edit to a shared file is caught as the
fork it is rather than discovered later as a divergence.

Two files differ and both are recorded below as decisions rather than
exceptions of convenience. The rest are identical, which is what makes the
rule worth checking (F71).
"""
from __future__ import annotations

import hashlib
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from nobble import paths  # noqa: E402

PEERS = ("BINMAN", "BoltzMaker")

# Directories that are each project's own by definition: generated output,
# environments, campaign data, its published atlas.
SKIP_PARTS = {".git", "node_modules", "__pycache__", ".pixi", ".venv",
              "campaigns", "data", "deploy", "app", "logs", "qc"}

SUFFIXES = (".py", ".sh", ".mjs", ".css", ".js")

# Same path, different file, with the reason. Anything not named here must
# match its peer exactly.
ALLOWED_TO_DIFFER = {
    "wsgi.py":
        "each project's WSGI entry point imports its own application; the "
        "shared name is a convention, not shared code",
    "tools/hwprobe.py":
        "independent implementations rather than a fork: NOBBLE's writes the "
        "campaign tuning this project needs (token caps, recycle counts, "
        "diffusion samples) which BINMAN has no concept of, so widening "
        "BINMAN's would move NOBBLE's vocabulary into it. The hardware half "
        "is duplicated and recorded as such in F71",
}


def _digest(path: Path) -> str:
    return hashlib.md5(path.read_bytes()).hexdigest()


def _shared() -> dict[str, list[tuple[str, Path, Path]]]:
    """Files present at the same relative path in NOBBLE and in a peer."""
    found: dict[str, list[tuple[str, Path, Path]]] = {}
    for name in PEERS:
        peer = paths.PORTFOLIO / name
        if not peer.exists():
            continue
        pairs = []
        for path in sorted(ROOT.rglob("*")):
            if not path.is_file():
                continue
            relative = path.relative_to(ROOT)
            if any(part in SKIP_PARTS for part in relative.parts):
                continue
            if path.suffix not in SUFFIXES:
                continue
            twin = peer / relative
            if twin.exists():
                pairs.append((str(relative), path, twin))
        found[name] = pairs
    return found


def test_at_least_one_peer_is_present():
    """The premise. With neither checked out this file would pass by
    finding nothing, which is the vacuous-control shape from F67."""
    shared = _shared()
    if not shared:
        pytest.skip("no peer project is checked out beside this one")
    assert any(pairs for pairs in shared.values()), (
        "no shared file was found in any peer, so this sweep is not "
        "evidence of anything"
    )


def test_no_shared_file_has_been_forked():
    shared = _shared()
    if not shared:
        pytest.skip("no peer project is checked out beside this one")
    forked = []
    for peer, pairs in shared.items():
        for relative, mine, theirs in pairs:
            if relative in ALLOWED_TO_DIFFER:
                continue
            if _digest(mine) != _digest(theirs):
                forked.append(f"{relative} differs from {peer}'s copy")
    assert not forked, (
        "shared file(s) edited locally instead of being widened in the peer "
        "(D-NOB-007):\n" + "\n".join(forked)
    )


def test_every_allowance_still_names_a_file_that_differs():
    """An allowlist that outlives what it allows is a hole. If a file here
    comes back into agreement, the entry should go rather than sit as
    standing permission to fork it later."""
    shared = _shared()
    if not shared:
        pytest.skip("no peer project is checked out beside this one")
    present = {}
    for pairs in shared.values():
        for relative, mine, theirs in pairs:
            present[relative] = _digest(mine) != _digest(theirs)
    stale = [relative for relative in ALLOWED_TO_DIFFER
             if present.get(relative) is False]
    assert not stale, (
        f"these are allowed to differ and no longer do: {stale}"
    )


def test_every_allowance_gives_a_reason():
    for relative, reason in ALLOWED_TO_DIFFER.items():
        assert len(reason) > 40, (
            f"{relative} is allowed to differ without a reason worth reading"
        )


def test_the_decision_is_recorded():
    decisions = (ROOT / "DECISIONS.md").read_text()
    assert "D-NOB-007" in decisions
