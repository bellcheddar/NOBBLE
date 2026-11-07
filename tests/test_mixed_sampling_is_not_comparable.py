"""A campaign whose pairs ran at different sample counts says so (F298).

Tier 2 asked for 25 diffusion samples on every job until F298 gave an
over-size job fewer, which is the right trade for a job that otherwise
writes nothing. It also breaks a comparison the project makes: `best_rmsd`
in the pose-recovery layer is a minimum over poses, and a best-of-9 and a
best-of-25 are different draws from the same distribution with the second
winning on sample count alone. Tier 2 already withholds the
minimum-over-seeds quantities for that reason; this is the same hazard one
layer over.

So the count is carried on each scored pair and the campaign says once
whether they agree. `unknown` is kept apart from agreement: a campaign
scored before the count was recorded has no counts at all and must not read
as uniform.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from nobble.score.run import _sampling_note                # noqa: E402


def test_one_count_everywhere_is_uniform():
    note = _sampling_note([
        {"pair_id": "a", "diffusion_samples": [25]},
        {"pair_id": "b", "diffusion_samples": [25]},
    ])
    assert note["uniform"] is True
    assert "caveat" not in note
    assert note["by_count"] == {"25": ["a", "b"]}


def test_two_counts_are_not_comparable_and_name_the_pairs():
    note = _sampling_note([
        {"pair_id": "bench06", "diffusion_samples": [9]},
        {"pair_id": "bench04", "diffusion_samples": [25]},
        {"pair_id": "bench05", "diffusion_samples": [25]},
    ])
    assert note["uniform"] is False
    assert "minimum over poses" in note["caveat"]
    assert note["by_count"] == {"25": ["bench04", "bench05"], "9": ["bench06"]}


def test_a_pair_with_no_recorded_count_is_not_agreement():
    """The F293 shape: a campaign scored before the count existed has no
    counts, which is unknown rather than uniform."""
    note = _sampling_note([
        {"pair_id": "old1"},
        {"pair_id": "old2", "diffusion_samples": None},
    ])
    assert note["uniform"] is False
    assert note["pairs_without_a_recorded_count"] == ["old1", "old2"]
    assert note["by_count"] == {}


def test_one_known_count_beside_an_unknown_one_is_not_uniform():
    """The case that would slip through a check on the number of distinct
    counts alone."""
    note = _sampling_note([
        {"pair_id": "a", "diffusion_samples": [25]},
        {"pair_id": "b"},
    ])
    assert note["uniform"] is False
    assert note["pairs_without_a_recorded_count"] == ["b"]


def test_a_pair_whose_own_jobs_disagree_is_its_own_count():
    """Should not happen, since every job of a pair has the same token count,
    so a pair spanning two sample counts means something else is wrong and
    the note must not flatten it to one of them."""
    note = _sampling_note([
        {"pair_id": "odd", "diffusion_samples": [9, 25]},
        {"pair_id": "normal", "diffusion_samples": [25]},
    ])
    assert note["uniform"] is False
    assert "9,25" in note["by_count"]
    assert note["by_count"]["9,25"] == ["odd"]


def test_the_note_is_attached_to_the_scoring_result():
    """Computed and then not returned would be the F85 shape."""
    import ast

    source = (ROOT / "nobble" / "score" / "run.py").read_text()
    tree = ast.parse(source)
    scorer = next(node for node in ast.walk(tree)
                  if isinstance(node, ast.FunctionDef)
                  and node.name == "score_campaign")
    called = {child.func.id for child in ast.walk(scorer)
              if isinstance(child, ast.Call) and isinstance(child.func, ast.Name)}
    assert "_sampling_note" in called
