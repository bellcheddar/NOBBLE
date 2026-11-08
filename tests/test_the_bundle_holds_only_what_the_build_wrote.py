"""Nothing in the published bundle that the build did not put there (F303).

The 2026-11-07 rebuild left 2,014 files in `deploy/atlas/structures` and
`deploy/atlas/crystals` whose names were a sibling's with " 2" inserted
before the extension, each one beside the real file, about 150 MB of
unreferenced copies in a bundle built for a droplet with 3.8 GB of RAM. 706
of them reached a commit before it was reversed.

Nothing in `build_atlas.py` can produce such a name: `shutil.copy` writes the
name it is given, and a job id and a PDB id contain no spaces. They came from
outside the build and the cause is not established (F300). What is in the
project's hands is refusing to ship them.

Checked by name against what the build recorded itself writing, not by
pattern. A pattern catches the shape seen once; this catches anything that
turns up in those directories, which is the property a bundle that gets
rsynced to a public host needs.
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

SOURCE = (ROOT / "deploy" / "build_atlas.py").read_text()


def test_the_build_records_what_it_writes():
    """Both published directories, or the check covers one of them."""
    assert "intended_structures.add(published)" in SOURCE
    assert 'intended_crystals.add(f"{pdb_id}.cif.gz")' in SOURCE


def test_the_check_refuses_rather_than_warns():
    """A warning in a forty-hour log is not a gate. The build must return
    non-zero, which is what deploy.sh and refresh.sh key on."""
    tree = ast.parse(SOURCE)
    refusals = [node for node in ast.walk(tree)
                if isinstance(node, ast.If)
                and isinstance(node.test, ast.Name)
                and node.test.id == "extra"]
    assert refusals, "no `if extra:` branch in the build"
    returns = [node for node in ast.walk(refusals[0])
               if isinstance(node, ast.Return)]
    assert returns, "the refusal does not return"
    assert any(isinstance(node.value, ast.Constant) and node.value.value == 1
               for node in returns), "the refusal does not return non-zero"


def test_both_directories_are_scanned():
    """The leak was in both, and a check on one would have passed while
    1,314 files sat in the other."""
    tree = ast.parse(SOURCE)
    assignment = next(
        node for node in ast.walk(tree)
        if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == "unexpected"
                for target in node.targets))
    keys = {key.value for key in assignment.value.keys
            if isinstance(key, ast.Constant)}
    assert keys == {"structures", "crystals"}


def test_every_conflict_copy_in_the_bundle_is_provably_a_copy():
    """The invariant, not the count.

    This asserted the bundle holds no name with a space in it, which is true
    the moment a build finishes and false for the hour after. Measured on
    2026-11-07: zero immediately after the rebuild, 336 twenty minutes later,
    zero after cleaning, then 586 and 991 over the following minutes, all
    climbing toward the bundle's 2,509 structures. iCloud is restoring its
    copy of the version the rebuild replaced, file by file, and it converges
    and stops.

    A test that is red for an hour after every rebuild trains you to ignore
    the suite, which is the same argument that made the cleaner remove
    rather than refuse. So the count is not asserted. What is asserted is
    the property that makes them harmless and that does not drift: every
    conflict-shaped name has a plain sibling, so every one is removable
    without losing anything. A name without a sibling is the real hazard,
    because it might be the only copy of a file, and the cleaner refuses on
    exactly that.

    The publish path is where cleanliness is enforced:
    `deploy/deploy.sh` clears the provable copies and then refuses on
    anything left (F310).
    """
    import sys as _sys

    _sys.path.insert(0, str(ROOT / "tools"))
    import clean_sync_conflicts as cleaner

    bundle = ROOT / "deploy" / "atlas"
    if not bundle.exists():
        import pytest
        pytest.skip("no published bundle on this checkout")

    unmatched = [path for path in bundle.rglob("*")
                 if path.is_file()
                 and cleaner.CONFLICT.search(path.name)
                 and cleaner.plain_sibling(path) is None]
    assert not unmatched, (
        f"{len(unmatched)} conflict-shaped name(s) in the bundle have no "
        "plain sibling, so each one may be the only copy of a file rather "
        f"than a restored duplicate: {[str(p) for p in unmatched[:3]]}"
    )


def test_every_published_structure_is_named_for_a_job():
    """The invariant behind the check, on the real bundle: a structure's
    name is its job id, so an unmatched name is not a job's output."""
    import pytest

    from nobble import paths

    bundle = ROOT / "deploy" / "atlas" / "structures"
    campaign = ROOT / "deploy" / "atlas"
    if not bundle.exists() or not (campaign / "results.jsonl").exists():
        pytest.skip("no published bundle on this checkout")

    job_ids = set()
    for name in ("results.jsonl", "results_tier2.jsonl"):
        path = campaign / name
        if path.exists():
            job_ids |= {row["job_id"] for row
                        in paths.read_jsonl(path, tolerate_torn=True)
                        if row.get("job_id")}
    assert job_ids, "the published bundle names no jobs"
    # Conflict-shaped names are excluded: they are covered by the invariant
    # above, and while iCloud reconciles a rebuilt bundle there are hundreds
    # of them, none of which is a published structure the site would serve
    # under that name.
    import sys as _sys

    _sys.path.insert(0, str(ROOT / "tools"))
    import clean_sync_conflicts as cleaner

    orphans = sorted(path.name for path in bundle.iterdir()
                     if path.stem not in job_ids
                     and not cleaner.CONFLICT.search(path.name))
    assert not orphans, (
        f"{len(orphans)} published structure(s) are not named for any job in "
        f"the bundle's own results: {orphans[:3]}"
    )


# --------------------------------------------------------------------------- #
# And nothing referenced that is absent (F309)
# --------------------------------------------------------------------------- #

def test_the_build_refuses_on_a_referenced_file_it_did_not_publish():
    """The other direction, which nothing checked at build or deploy time.

    F196 found `/crystal/<id>.cif` 404ing in production because the
    assemblies were never published, and on 2026-11-07 the build recorded
    seven crystals while three were on disk. Both of today's other checks
    look for files that should not be there.
    """
    tree = ast.parse(SOURCE)
    # Across every `if absent:` branch, not the first one. F315 added a
    # restore branch above the refusal, both testing `absent`, and keying on
    # `refusals[0]` made this fail on the restore: a test that assumed there
    # was only ever one branch.
    branches = [node for node in ast.walk(tree)
                if isinstance(node, ast.If)
                and isinstance(node.test, ast.Name)
                and node.test.id == "absent"]
    assert branches, "no `if absent:` branch in the build"
    returns = [node for branch in branches for node in ast.walk(branch)
               if isinstance(node, ast.Return)]
    assert any(isinstance(node.value, ast.Constant) and node.value.value == 1
               for node in returns), "no `if absent:` branch returns non-zero"


def test_both_kinds_of_referenced_file_are_checked():
    """A crystal and a structure 404 the same way, and checking one would
    have passed on 2026-11-07 while four crystals were missing."""
    assert 'crystal_by_pair' in SOURCE
    assert 'row.get("structure")' in SOURCE
    assert "results_tier2.jsonl" in SOURCE


def test_the_check_reads_the_bundle_rather_than_the_build_s_intent():
    """Asking what the build meant to publish would have said seven on the
    day three were there. The question is what the bundle promises."""
    position = SOURCE.index("absent = []")
    tail = SOURCE[position:position + 2000]
    assert "benchmark_path.read_text()" in tail
    assert "paths.read_jsonl" in tail


def test_the_live_bundle_promises_nothing_it_lacks():
    """The state right now, which is what the build would have refused on
    earlier today."""
    import json

    import pytest

    bundle = ROOT / "deploy" / "atlas"
    benchmark = bundle / "benchmark.json"
    if not benchmark.exists():
        pytest.skip("no published bundle on this checkout")

    from nobble import paths

    missing = []
    mapping = json.loads(benchmark.read_text()).get("crystal_by_pair") or {}
    for pair_id, pdb_id in sorted(mapping.items()):
        if pdb_id and not (bundle / "crystals" / f"{pdb_id}.cif.gz").exists():
            missing.append(f"crystals/{pdb_id}.cif.gz for {pair_id}")
    for name in ("results.jsonl", "results_tier2.jsonl"):
        path = bundle / name
        if not path.exists():
            continue
        for row in paths.read_jsonl(path, tolerate_torn=True):
            published = row.get("structure")
            if published and not (bundle / published).exists():
                missing.append(f"{published} for {row.get('job_id')}")
    assert not missing, (
        f"{len(missing)} file(s) the bundle references and does not contain, "
        f"each one a 404 on the site: {missing[:3]}")


# --------------------------------------------------------------------------- #
# Restore once, then refuse (F315)
# --------------------------------------------------------------------------- #

def test_a_missing_referenced_file_is_copied_again_before_refusing():
    """A file removed in the seconds after it was published is not a build
    that failed. On 2026-11-07 one published structure went missing between
    the build that wrote it and a check minutes later, and four crystals went
    the same way between two builds. Refusing the whole bundle for that would
    stop a publish at the end of fifty hours over something a second copy
    fixes.
    """
    tree = ast.parse(SOURCE)
    restores = [node for node in ast.walk(tree)
                if isinstance(node, ast.Assign)
                and any(isinstance(target, ast.Name) and target.id == "restored"
                        for target in node.targets)]
    assert restores, "the build has no restore step"
    assert "sources.get(published)" in SOURCE, (
        "the restore does not look up where the file was copied from, so it "
        "cannot copy it again"
    )


def test_the_restore_runs_before_the_refusal_and_not_after():
    """After the refusal it would never run, which is the F271 shape: a step
    placed below the thing that exits."""
    assert SOURCE.index("restored = []") < SOURCE.index(
        "REFUSING: {len(absent)} file(s) the bundle references")


def test_what_the_restore_cannot_fix_is_still_refused():
    """The case the guard exists for: a file the bundle promises and the
    build never had. A restore that swallowed that would turn the guard into
    a tidy-up."""
    position = SOURCE.index("restored = []")
    tail = SOURCE[position:position + 2600]
    assert "still.append(entry)" in tail
    assert "absent = still" in tail
    assert "return 1" in tail


def test_the_restore_is_counted_in_the_summary():
    """A silent restore hides that something is removing published files,
    which is the thing worth knowing even once the build succeeds."""
    assert 'summary["referenced_files_restored"]' in SOURCE


def test_every_published_path_has_a_recorded_source():
    """The restore can only work for paths the build knows the origin of,
    and both kinds of referenced file have to be in that map or one of them
    is refused where the other is restored."""
    assert 'sources[f"structures/{published}"] = origin' in SOURCE
    assert 'sources[f"crystals/{pdb_id}.cif.gz"] = source' in SOURCE
