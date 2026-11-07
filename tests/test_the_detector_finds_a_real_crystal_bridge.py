"""The bridge detector against deposited coordinates, not against itself.

`test_geometry_real_bridge.py` runs the filter on a prediction the campaign
scored as bridging, so it checks that the filter still agrees with its own
earlier verdict. That is a regression test and it cannot say whether the
filter is right, because the label came from the filter.

These put the independent question. Each benchmark deposition is titled as a
glue or degrader ternary, so a bridge is there as a matter of experimental
record, and a deposition the filter does not call bridging is a false
negative of the instrument.
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

from nobble.validate.layers import RECOVERY_TARGETS      # noqa: E402


@pytest.fixture(scope="module")
def crystals():
    from nobble.curate import structures

    missing = [target["pdb_id"] for target in RECOVERY_TARGETS.values()
               if not structures.is_cached(target["pdb_id"])]
    if missing:
        pytest.skip(f"depositions not cached on this checkout: {missing}")
    try:
        import bridge_on_crystals
    except ImportError as problem:
        pytest.skip(f"geometry stack not importable here: {problem}")
    try:
        return bridge_on_crystals.crystal_rows()
    except ImportError as problem:          # freesasa or BINMAN's pipeline
        pytest.skip(f"geometry stack not importable here: {problem}")


def test_the_scan_covers_every_benchmark_pair(crystals):
    """The denominator is what was intended, not what came back (F293)."""
    assert {row["pair_id"] for row in crystals} == set(RECOVERY_TARGETS)


def test_every_deposited_glue_is_found_to_bridge(crystals):
    """The assertion nothing in the suite was making.

    A miss here is a false negative of spec 4.1's primary signal, and every
    bridge-formation rate of zero in the campaign would then be unreadable:
    it could mean the prediction did not bridge or that the filter cannot
    see a bridge that is there.
    """
    measurable = [row for row in crystals if row["measurable"]]
    assert measurable, "no deposition was measurable, so nothing was asked"
    missed = [(row["pair_id"], row["reject_reason"])
              for row in measurable if not row["found"]]
    assert not missed, (
        f"the filter missed a bridge present in deposited coordinates: {missed}"
    )


def test_a_found_crystal_bridge_carries_its_numbers(crystals):
    """found=True with null halves would be worse than a miss, because every
    consumer reads found as permission to use them."""
    for row in crystals:
        if not row["found"]:
            continue
        assert row["dsasa_receptor"] and row["dsasa_receptor"] > 0
        assert row["dsasa_peptide"] and row["dsasa_peptide"] > 0
        assert row["dsasa_total"] and row["dsasa_total"] > 0
        assert 0.0 <= row["bridge_percentile"] <= 100.0


def test_a_deposition_without_its_glue_is_refused_not_missed(crystals):
    """6BNB is titled "bound to dBET57 PROTAC" and its coordinates carry no
    dBET57, only a zinc. An unmodelled glue is a missing measurement, not a
    crystal in which a PROTAC fails to bridge, and the two must not land in
    the same count."""
    from nobble.score import geometry

    by_pdb = {row["pdb_id"]: row for row in crystals}
    row = by_pdb.get("6BNB")
    assert row is not None, "6BNB is no longer a benchmark reference"
    assert row["measurable"] is False
    assert row["reject_reason"] == "glue_not_modelled_in_deposition"
    assert row["reject_reason"] in geometry.MEASUREMENT_FAILURES
    assert row["notes"], "the refusal carries no explanation"


def test_the_receptor_comparator_is_derived_from_the_construct(crystals):
    """Comparing a multi-segment prediction against one deposited chain
    understates the crystal, which is F293 in a geometry: the comparator has
    to be the surface the prediction actually offered."""
    import bridge_on_crystals
    from nobble.curate import constructs as C

    multi, single = [], []
    for pair_id, target in RECOVERY_TARGETS.items():
        chain, _why = bridge_on_crystals.receptor_side(pair_id, target)
        construct = bridge_on_crystals.construct_of(pair_id)
        if construct is None:
            continue
        accessions = {segment.accession
                      for segment in C.by_name(construct).segments}
        (multi if len(accessions) > 1 else single).append((pair_id, chain))
    assert multi and single, (
        "every benchmark construct now has the same arity, so this test no "
        f"longer distinguishes anything: {multi} against {single}"
    )
    for pair_id, chain in multi:
        assert chain is None, f"{pair_id} is multi-segment but reads one chain"
    for pair_id, chain in single:
        assert chain == RECOVERY_TARGETS[pair_id]["receptor_chain"]


def test_the_crystal_and_the_prediction_go_through_one_filter_call():
    """The F154 guard, on the one thing this control could be defeated by.

    A crystal control routed through its own copy of the `find_bridges` call
    would be testing that copy: the waiver, the chain labelling and the
    percentile basis could all drift from what the campaign ran and the
    control would still pass. So the module is allowed exactly one call, and
    both entry points must reach it.
    """
    source = (ROOT / "nobble" / "score" / "geometry.py").read_text()
    tree = ast.parse(source)
    called = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef):
            continue
        names = {child.func.id for child in ast.walk(node)
                 if isinstance(child, ast.Call)
                 and isinstance(child.func, ast.Name)}
        called[node.name] = names

    assert "bridge_from_groups" in called.get("score_structure", set())
    assert "bridge_from_groups" in called.get("score_deposition", set())
    assert "find_bridges" in called.get("bridge_from_groups", set())
    elsewhere = sorted(name for name, names in called.items()
                       if "find_bridges" in names
                       and name != "bridge_from_groups")
    assert not elsewhere, (
        f"find_bridges is called outside bridge_from_groups, in {elsewhere}: "
        "the crystal control and the campaign would no longer share a filter"
    )
