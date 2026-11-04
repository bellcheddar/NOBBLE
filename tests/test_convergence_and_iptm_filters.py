"""Two numeric filters that used `is not None`, where a NaN is not None.

F76 swept `isinstance(value, (int, float))`, which admits NaN. It did not
sweep the other idiom, `value is not None`, which admits it too. Most sites
are safe because F78 made `_rmsd` refuse a non-finite result, but that makes
the guarantee a property of one upstream function rather than of the filter.

`_receptor_peptide_iptm` looked unsafe and is not. It filters ipTM values
with `is not None` and takes the minimum, and `min` with a NaN present is
order-dependent: `min([0.9, nan])` is 0.9 and `min([nan, 0.9])` is nan, so
the order of the construct's receptor segments would decide whether a NaN
survived into Delta-ipTM. But `_pair_iptm` already requires `finite` on
each cell, which was one of F76's fourteen sites, so a NaN becomes None one
level up and never reaches the minimum.

I claimed that as a gap and the mutation harness disagreed: reverting the
filter failed no test. What the tests below actually establish is F76's
guarantee at the cell, and that a None segment is dropped from the minimum
rather than making it None.

The convergence score had the other shape from F80: `mean_rmsd / 10.0`, a
scale deciding a published component of the composite, written inside the
expression. The cutoff sweep looks in comparisons, module constants, default
arguments and templates (F87).
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from nobble import paths  # noqa: E402
from nobble.score import metrics, poses  # noqa: E402

NAN = float("nan")


def test_min_with_a_nan_is_order_dependent():
    """The premise, stated because it is the reason a type check is not
    enough: the bug is not that a NaN wins, it is that whether it wins
    depends on the order of the chains."""
    assert min([0.9, NAN]) == 0.9
    import math

    assert math.isnan(min([NAN, 0.9]))


def _confidence(values: dict[tuple[int, int], float]) -> dict:
    matrix: dict[str, dict[str, float]] = {}
    for (a, b), value in values.items():
        matrix.setdefault(str(a), {})[str(b)] = value
        matrix.setdefault(str(b), {}).setdefault(str(a), value)
    return {"pair_chains_iptm": matrix}


def test_a_non_finite_cell_becomes_none_before_the_minimum():
    """Where the guarantee actually lives: `_pair_iptm`, not the filter
    below it. A multi-segment construct, so there is more than one value to
    minimise over and the order would have mattered if it got that far."""
    from nobble.curate import constructs as C

    name = next((key for key, value in C.CONSTRUCTS.items()
                 if len(value.substrate_receptor_chains()) > 1), None)
    if name is None:
        pytest.skip("no multi-segment substrate receptor is configured")

    chains = C.CONSTRUCTS[name].substrate_receptor_chains()
    peptide = metrics.peptide_chain_index(name)
    good = {(chain, peptide): 0.80 + index * 0.05
            for index, chain in enumerate(chains)}
    clean, _used, _first = metrics._receptor_peptide_iptm(
        _confidence(good), name)
    assert clean == 0.80

    # The first segment's value is now non-finite. Without the filter the
    # answer depends on which chain comes first.
    poisoned = dict(good)
    poisoned[(chains[0], peptide)] = NAN
    # The poisoned cell becomes None in `_pair_iptm`, so the minimum is
    # taken over the remaining segment. Reverting the filter below it does
    # not change this, which is how the mutation harness caught my claim.
    assert metrics._pair_iptm(_confidence(poisoned), chains[0], peptide) is None
    value, _used, _first = metrics._receptor_peptide_iptm(
        _confidence(poisoned), name)
    # approx, because the fixture builds 0.80 + 0.05 and that is not
    # exactly 0.85. My arithmetic, not the code's.
    assert value == pytest.approx(0.85), (
        f"the minimum came back {value}, so the NaN was kept or the "
        "remaining values were dropped"
    )


def test_every_value_non_finite_gives_no_minimum():
    """Absent rather than zero or NaN: the pair has no measurable ipTM."""
    from nobble.curate import constructs as C

    name = "CRBN_CULT"
    peptide = metrics.peptide_chain_index(name)
    chains = C.CONSTRUCTS[name].substrate_receptor_chains()
    value, _used, _first = metrics._receptor_peptide_iptm(
        _confidence({(chain, peptide): NAN for chain in chains}), name)
    assert value is None


def test_the_convergence_scale_comes_from_config():
    configured = float(paths.thresholds()["scoring"]["convergence_scale_a"])
    assert poses.CONVERGENCE_SCALE_A == configured
    source = (ROOT / "nobble" / "score" / "poses.py").read_text()
    assert "/ 10.0)" not in source, (
        "the convergence scale is a literal in the expression again"
    )


def test_the_convergence_score_follows_the_configured_scale(monkeypatch):
    """The only check that would catch the scale being read and ignored."""
    jobs = [{"pair_id": "p", "seed": seed, "complex_type": "ternary",
             "conditioning": "unconstrained"} for seed in (1, 2)]

    monkeypatch.setattr(poses, "peptide_rmsd_between", lambda a, b: 5.0)
    monkeypatch.setattr(poses, "CONVERGENCE_SCALE_A", 10.0)
    assert poses.convergence(jobs).convergence_score == 0.5

    monkeypatch.setattr(poses, "CONVERGENCE_SCALE_A", 20.0)
    assert poses.convergence(jobs).convergence_score == 0.75


def test_the_score_floors_at_zero_rather_than_going_negative(monkeypatch):
    jobs = [{"pair_id": "p", "seed": seed, "complex_type": "ternary",
             "conditioning": "unconstrained"} for seed in (1, 2)]
    monkeypatch.setattr(poses, "peptide_rmsd_between", lambda a, b: 40.0)
    monkeypatch.setattr(poses, "CONVERGENCE_SCALE_A", 10.0)
    assert poses.convergence(jobs).convergence_score == 0.0


def test_an_unmeasurable_pose_pair_is_dropped_not_scored(monkeypatch):
    """`max(0.0, 1.0 - nan/scale)` returns 0.0, because `nan > 0.0` is
    false, so a non-finite mean would have become the worst possible
    convergence rather than no convergence: F77's clamp in reverse."""
    jobs = [{"pair_id": "p", "seed": seed, "complex_type": "ternary",
             "conditioning": "unconstrained"} for seed in (1, 2, 3)]
    monkeypatch.setattr(poses, "peptide_rmsd_between",
                        lambda a, b: NAN if a["seed"] == 1 else 2.0)
    result = poses.convergence(jobs)
    assert result.pairwise_rmsd == [2.0], result.pairwise_rmsd
    assert result.mean_rmsd == 2.0
