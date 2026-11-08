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
    assert r" \d+(\.[A-Za-z0-9]+)+$" in tool
    assert r" \d+(\.[A-Za-z0-9]+)+$" in test
    assert r" [0-9]+(\.[A-Za-z0-9]+)+$" in deploy


def test_a_compound_extension_is_caught(tmp_path):
    """A gzipped crystal. The single-segment pattern could not see
    `5FQD 2.cif.gz`, and seven of them sat in the published bundle while
    every guard passed (F310)."""
    root = _tree(tmp_path, {"5FQD.cif.gz": "new", "5FQD 2.cif.gz": "old"})
    assert cleaner.main(["--root", str(root)]) == 0
    assert (root / "campaigns" / "5FQD.cif.gz").exists()
    assert not (root / "campaigns" / "5FQD 2.cif.gz").exists()


def test_a_compound_extension_with_no_sibling_is_still_refused(tmp_path):
    root = _tree(tmp_path, {"6TD3 2.cif.gz": "only copy"})
    assert cleaner.main(["--root", str(root)]) == 1
    assert (root / "campaigns" / "6TD3 2.cif.gz").exists()


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


def test_the_deploy_clears_the_copies_before_it_refuses():
    """The copies arrive minutes after a build, so a chain that ends with
    build then deploy is blocked at the last step by files that did not
    exist when the build finished (F310).

    The cleaner runs first and the refusal still follows it: automating the
    `rm` the refusal asks for loses nothing, and anything without a plain
    sibling is still left alone and still refused.
    """
    script = (ROOT / "deploy" / "deploy.sh").read_text()
    assert "clean_sync_conflicts.py" in script
    assert script.index("clean_sync_conflicts.py") < script.index(
        "the bundle holds iCloud sync-conflict copies"), (
        "the deploy refuses before it clears, so the refusal fires on copies "
        "the cleaner would have removed")


def test_the_deploy_still_refuses_after_cleaning():
    """Clearing instead of refusing would turn a publish gate into a
    tidy-up, and an unmatched name has to stop the deploy."""
    script = (ROOT / "deploy" / "deploy.sh").read_text()
    tail = script[script.index("clean_sync_conflicts.py"):]
    assert "the bundle holds iCloud sync-conflict copies" in tail
    assert "exit 2" in tail


def test_a_root_holding_none_of_the_scanned_trees_is_not_clean(tmp_path):
    """The defect this file's own subject had for as long as it existed
    (F332).

    `find` takes a project root and walks `root/deploy`, `root/campaigns`
    and four more. `deploy/build_atlas.py` passed `OUT.parent`, which is
    `deploy/`, so it looked for `deploy/deploy`, `deploy/campaigns`,
    `deploy/nobble`, `deploy/tools`, `deploy/tests` and `deploy/data`,
    found none of them, and reported a clean tree. Measured against the
    real bundle: that call returned nothing while the project root returned
    5,116. The clearing step inside the atlas build had never cleared
    anything, and its comment said it was doing what `deploy.sh` does.

    The command line was always right, because it passes the default root.
    So this was invisible from the outside: the tool worked, and one caller
    was holding it wrong in a way the tool could not report.
    """
    import pytest

    empty = tmp_path / "nothing"
    empty.mkdir()
    with pytest.raises(NotADirectoryError):
        cleaner.find(empty)


def test_one_named_tree_can_be_asked_about_directly(tmp_path):
    """What the atlas build wanted, and what it now calls."""
    bundle = tmp_path / "atlas"
    (bundle / "structures").mkdir(parents=True)
    (bundle / "structures" / "job.cif").write_text("x")
    (bundle / "structures" / "job 2.cif").write_text("x")
    (bundle / "orphan 3.json").write_text("y")

    removable, unmatched = cleaner.find_under(bundle)
    assert [path.name for path in removable] == ["job 2.cif"]
    assert [path.name for path in unmatched] == ["orphan 3.json"], (
        "a conflict-shaped name with no plain sibling must be reported "
        "rather than removed: it may be the only copy of a file"
    )


def test_asking_about_a_tree_that_is_not_there_is_not_a_clean_answer(tmp_path):
    import pytest

    with pytest.raises(NotADirectoryError):
        cleaner.find_under(tmp_path / "absent")


def test_the_atlas_build_names_the_bundle_rather_than_its_parent():
    build = (ROOT / "deploy" / "build_atlas.py").read_text()
    assert "clean_sync_conflicts.find_under(OUT)" in build, (
        "the atlas build is back to passing a directory that `find` reads "
        "as a project root, so its clearing step clears nothing"
    )
    assert "clean_sync_conflicts.find(OUT.parent)" not in build
