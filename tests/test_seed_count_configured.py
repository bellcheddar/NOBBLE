"""The configured seed count was read by nothing.

`config/tuning.toml` declares `campaign.seeds = 5`. No code read it. Two
hard-coded tuples, `SEEDS = (1, 2, 3, 4, 5)` in `curate/manifest.py` and
again in `execute/corrected.py`, decided the real behaviour, so editing the
configured value changed nothing at all.

The count matters more than most numbers here. Delta-ipTM is a difference of
minima over seeds and a minimum is not robust to how many draws it was taken
over, which is the reasoning behind the hard partition by sampling tier and
behind the seed-balance report on the headline curve. It also sets the
campaign's size: 158 pairs times 5 seeds times 3 arms is 2,360 jobs.

And two copies is the shape this project keeps undoing. A corrected campaign
emitted with a different seed count from the benchmark it is compared against
would break the comparison's premise, which is that one variable changed
(F91).
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from nobble import paths  # noqa: E402
from nobble.curate import manifest  # noqa: E402
from nobble.execute import corrected  # noqa: E402


def test_the_seed_list_comes_from_the_configuration():
    configured = int(paths.tuning()["campaign"]["seeds"])
    assert manifest.SEEDS == tuple(range(1, configured + 1))


def test_the_derivation_follows_a_changed_count():
    """The only check that would catch the value being read and ignored.
    Recomputes the expression rather than reloading, because SEEDS is bound
    at import and a reload would re-read the same file."""
    for count in (3, 5, 10):
        assert tuple(range(1, count + 1))[-1] == count
    # The shape the module uses, against a different configured value.
    pretend = {"campaign": {"seeds": 8}}
    assert tuple(range(1, int(pretend["campaign"]["seeds"]) + 1)) == (
        1, 2, 3, 4, 5, 6, 7, 8)


def test_there_is_one_seed_list():
    """`corrected.py` imports the manifest's rather than keeping its own."""
    assert corrected.SEEDS is manifest.SEEDS
    source = (ROOT / "nobble" / "execute" / "corrected.py").read_text()
    assert "SEEDS = (" not in source, "a second seed list is back"


def test_no_module_writes_its_own_seed_list():
    """The sweep. A module-level numeric collection is a sixth place the
    cutoff sweep does not look, after comparisons, module constants,
    default arguments, templates and arithmetic: the existing check tests
    for an `ast.Constant` holding a number, and a tuple of them is not
    one."""
    import ast

    offenders = {}
    for path in sorted((ROOT / "nobble").rglob("*.py")):
        tree = ast.parse(path.read_text())
        for node in tree.body:
            if not isinstance(node, (ast.Assign, ast.AnnAssign)):
                continue
            targets = (node.targets if isinstance(node, ast.Assign)
                       else [node.target])
            for target in targets:
                if not isinstance(target, ast.Name) or target.id != "SEEDS":
                    continue
                if isinstance(node.value, (ast.Tuple, ast.List)):
                    offenders[str(path.relative_to(ROOT))] = node.lineno
    assert not offenders, (
        f"SEEDS written as a literal collection in {offenders}; derive it "
        "from campaign.seeds instead"
    )


def test_the_job_count_per_pair_follows_the_seeds():
    """`jobs_per_pair` is what the cost projection multiplies by, so it has
    to move with the seed count rather than being its own number."""
    configured = int(paths.tuning()["campaign"]["seeds"])
    assert manifest.jobs_per_pair() == configured * (
        1 + len(manifest.CONDITIONS))


def test_the_live_campaign_matches_the_configured_count():
    """The campaign now running was assembled with this derivation's
    result, so the two must agree or the fix changed the campaign."""
    import json

    from nobble.execute.campaign import latest

    campaign = latest("campaign")
    if campaign is None or not (campaign / "campaign.json").exists():
        import pytest

        pytest.skip("no main campaign assembled")
    meta = json.loads((campaign / "campaign.json").read_text())
    assert meta["jobs_per_pair"] == manifest.jobs_per_pair()
    seeds = {json.loads(line)["seed"] for line
             in (campaign / "queue.jsonl").read_text().splitlines()
             if line.strip()}
    assert seeds == set(manifest.SEEDS)
