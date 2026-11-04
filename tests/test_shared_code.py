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


# Shared project code that sits at a *different* relative path in each
# project, so the same-path walk below cannot pair it. Found by comparing
# content rather than paths: twelve files are byte-identical to a peer's at a
# different path, and nine of them are vendored libraries (molstar, plotly,
# d3, tabulator, the fonts) that neither project owns and D-NOB-007 therefore
# does not reach. These three are project code.
#
# All three are identical today, which is the point of writing them down. The
# rule is not "they happen to match", it is that a local edit to shared code
# is a fork; and the two largest are the easiest to edit by accident.
# `molstar-bridge.js` is 39 KB of BINMAN's viewer filed under NOBBLE's
# `vendor/`, where the directory name says third-party and every sweep,
# including this test's own `SKIP_PARTS`, stays away. `depot.css` is BINMAN's
# stylesheet under a different name, which is what "the design system is
# inherited from BINMAN" means in practice (F124).
SHARED_AT_A_DIFFERENT_PATH = {
    "nobble/app/static/vendor/molstar-bridge.js":
        ("BINMAN", "app/static/js/molstar-bridge.js",
         "D-NOB-031: the Mol* presentation is BINMAN's, taken whole. Widen "
         "BINMAN's copy and re-vendor rather than editing this one"),
    "nobble/app/static/css/depot.css":
        ("BINMAN", "app/static/css/binman.css",
         "CLAUDE.md: the Depot design system is inherited from BINMAN. The "
         "name differs and the bytes do not"),
    "elementor-widget-markdown.css":
        ("BoltzMaker", "wordpress/elementor-widget-markdown.css",
         "the WordPress widget stylesheet the house pages use, shared with "
         "BoltzMaker"),
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


def test_the_polished_readme_is_in_step_with_the_readme():
    """`README.polished.md` is generated from `README.md` by
    `tools/readme_forge.py`, and the two are byte-identical today because
    the polish step is idempotent once the badges are in place: it checks
    `already_branded` and leaves a branded document alone.

    Identical is not the same as in step. The next edit to `README.md`
    makes the generated copy stale, and nothing would say so, which is the
    pattern that produced three copies of a timestamp format and two theme
    colours. This regenerates in memory and compares (F71).
    """
    readme = ROOT / "README.md"
    polished = ROOT / "README.polished.md"
    if not polished.exists():
        pytest.skip("no polished README on this checkout")

    sys.path.insert(0, str(ROOT / "tools"))
    import json

    import readme_forge

    meta_all = {}
    meta_file = ROOT / "tools" / readme_forge.META_FILE
    if not meta_file.exists():
        meta_file = ROOT / readme_forge.META_FILE
    if meta_file.exists():
        meta_all = json.loads(meta_file.read_text())

    crude = readme.read_text()
    expected = readme_forge.polish(crude, str(readme),
                                   meta_all.get("README.md", {}))
    if not expected.endswith("\n"):
        expected += "\n"
    assert polished.read_text() == expected, (
        "README.polished.md is not what the forge would produce from "
        "README.md: regenerate it with tools/readme_forge.py README.md"
    )


def test_polishing_a_branded_readme_changes_nothing():
    """The property that makes the check above meaningful. If polish() were
    not idempotent the two files would differ by design and the comparison
    would have to be against a stored copy instead."""
    polished = ROOT / "README.polished.md"
    if not polished.exists():
        pytest.skip("no polished README on this checkout")

    sys.path.insert(0, str(ROOT / "tools"))
    import readme_forge

    once = polished.read_text()
    twice = readme_forge.polish(once, str(polished), {})
    if not twice.endswith("\n"):
        twice += "\n"
    assert twice == once, "polish() is not idempotent on its own output"


def test_shared_code_at_a_different_path_is_still_identical():
    """The same-path walk above cannot see these, and `SKIP_PARTS` skips
    `app` anyway, so the largest shared file in the project sat outside the
    check that exists to protect shared code, twice over (F124)."""
    checked = 0
    for mine, (peer, theirs, reason) in SHARED_AT_A_DIFFERENT_PATH.items():
        here = ROOT / mine
        there = paths.PORTFOLIO / peer / theirs
        if not there.exists():
            continue
        assert here.exists(), f"{mine} is gone; update the map"
        assert _digest(here) == _digest(there), (
            f"{mine} has diverged from {peer}/{theirs}. {reason}"
        )
        checked += 1
    if not checked:
        pytest.skip("no peer checkout to compare against")
    assert checked == len(SHARED_AT_A_DIFFERENT_PATH), checked


def test_the_map_names_only_files_that_exist_here():
    """An entry for a file NOBBLE no longer holds would pass by skipping."""
    for mine in SHARED_AT_A_DIFFERENT_PATH:
        assert (ROOT / mine).exists(), mine


def test_vendored_libraries_are_not_in_the_map():
    """They are byte-identical to the peers' copies too, and that is not a
    fork: neither project owns molstar or plotly. Listing them would turn a
    rule about shared code into a rule about pinned dependencies."""
    for mine in SHARED_AT_A_DIFFERENT_PATH:
        assert "/molstar/" not in mine, mine
        assert "/plotly/" not in mine, mine
        assert "/d3/" not in mine, mine
        assert "/tabulator/" not in mine, mine


def test_the_bridge_is_project_code_rather_than_a_library():
    """Why it belongs in the map at all. A vendored library carries no
    reference to this project's own vocabulary; this one opens by naming the
    spec section it implements."""
    bridge = ROOT / "nobble" / "app" / "static" / "vendor" / "molstar-bridge.js"
    if not bridge.exists():
        pytest.skip("no bridge on this checkout")
    head = bridge.read_text()[:400]
    assert "spec 6.4" in head, head[:120]
    assert "mountViewer" in bridge.read_text()
