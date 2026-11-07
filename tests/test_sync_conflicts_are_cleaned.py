"""The conflict copies are removed where a rebuild can see them (F304).

`tests/test_no_sync_conflict_files.py` names the class and scans what git
tracks and what `deploy/atlas` holds. `deploy/deploy.sh` refuses before it
sends anything. Neither runs between a rebuild and the next `git add -A`,
and that is the whole window: the 2026-11-07 rebuild left 2,014 copies and
706 were committed and pushed hours later.

`tools/clean_sync_conflicts.py` runs inside `tools/refresh.sh`, straight
after the build. It removes rather than refuses, because the copies reappear
whenever an output directory is rewritten and a gate that fires constantly on
a known-harmless artefact is a gate that gets turned off. It refuses only for
a conflict-shaped name with no plain sibling, which is not demonstrably a
copy of anything: deleting the only copy of a file to tidy up its name is the
one outcome worse than leaving the name alone.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import clean_sync_conflicts as cleaner                     # noqa: E402


def _tree(tmp_path: Path, names: dict[str, str]) -> Path:
    for name, text in names.items():
        path = tmp_path / "campaigns" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
    return tmp_path


def test_a_copy_beside_its_original_goes(tmp_path):
    root = _tree(tmp_path, {"a.cif": "new", "a 2.cif": "old"})
    assert cleaner.main(["--root", str(root)]) == 0
    assert (root / "campaigns" / "a.cif").exists()
    assert not (root / "campaigns" / "a 2.cif").exists()


def test_the_differing_content_is_not_a_reason_to_keep_it(tmp_path):
    """iCloud restores an older copy, so a conflict file routinely differs
    from its sibling. Keeping the ones that differ would keep exactly the
    stale ones, which is what made the F219 guard refuse for hours."""
    root = _tree(tmp_path, {"a.cif": "new content", "a 2.cif": "quite "
                            "different old content"})
    assert cleaner.main(["--root", str(root)]) == 0
    assert not (root / "campaigns" / "a 2.cif").exists()


def test_a_name_with_no_sibling_is_refused_and_left(tmp_path):
    """The one case where removing is worse than keeping."""
    root = _tree(tmp_path, {"orphan 2.cif": "only copy"})
    assert cleaner.main(["--root", str(root)]) == 1
    assert (root / "campaigns" / "orphan 2.cif").exists()


def test_a_dry_run_removes_nothing(tmp_path):
    root = _tree(tmp_path, {"a.cif": "new", "a 2.cif": "old"})
    assert cleaner.main(["--root", str(root), "--dry-run"]) == 0
    assert (root / "campaigns" / "a 2.cif").exists()


def test_an_ordinary_name_ending_in_a_digit_is_not_touched(tmp_path):
    """`model_2.cif` and `peptide_v2.json` are names this project writes.
    The pattern needs a space, which is what distinguishes them."""
    root = _tree(tmp_path, {"x_model_2.cif": "real", "y_v2.json": "real",
                            "z2.cif": "real"})
    assert cleaner.main(["--root", str(root)]) == 0
    for name in ("x_model_2.cif", "y_v2.json", "z2.cif"):
        assert (root / "campaigns" / name).exists(), name


def test_one_spelling_of_the_pattern():
    """Three places describe a conflict copy. If they drift, one of them
    starts missing files the others catch."""
    tool = (ROOT / "tools" / "clean_sync_conflicts.py").read_text()
    test = (ROOT / "tests" / "test_no_sync_conflict_files.py").read_text()
    deploy = (ROOT / "deploy" / "deploy.sh").read_text()
    assert r" \d+\.[A-Za-z0-9]+$" in tool
    assert r" \d+\.[A-Za-z0-9]+$" in test
    assert r" [0-9]+\.[A-Za-z0-9]+$" in deploy


def test_the_refresh_runs_it_after_the_build():
    """Before it, and it would scan the previous build's leftovers."""
    refresh = (ROOT / "tools" / "refresh.sh").read_text()
    assert "clean_sync_conflicts.py" in refresh
    assert refresh.index("build_atlas.py") < refresh.index(
        "clean_sync_conflicts.py")


def test_git_is_not_scanned():
    """Packed object names could match the pattern, and no sync artefact in
    there is this tool's business."""
    assert ".git" not in cleaner.SCANNED
