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


def test_the_live_bundle_is_clean():
    """The state the cleanup left, asserted rather than assumed: if a
    rebuild reintroduces them, this fails here as well as refusing there."""
    bundle = ROOT / "deploy" / "atlas"
    if not bundle.exists():
        import pytest
        pytest.skip("no published bundle on this checkout")
    spaced = sorted(str(path.relative_to(bundle))
                    for path in bundle.rglob("* *"))
    assert not spaced, (
        f"{len(spaced)} file(s) in the bundle have a space in the name, which "
        f"this build never writes: {spaced[:3]}"
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
    orphans = sorted(path.name for path in bundle.iterdir()
                     if path.stem not in job_ids)
    assert not orphans, (
        f"{len(orphans)} published structure(s) are not named for any job in "
        f"the bundle's own results: {orphans[:3]}"
    )
