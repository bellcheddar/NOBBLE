"""Phase 1 gate tests. These are the spec's own acceptance criteria, executable."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

from nobble import paths
from nobble.curate import benchmark, binman_store, constructs, degron_gate, numbering


def test_binman_store_present_with_expected_row_counts():
    """The spec's section 2.1 row counts, as a check that we read the right store."""
    assert binman_store.bridge_reference_count() == 285996
    assert len(binman_store.dataset("sievers_zf_screen")) == 5663
    assert len(binman_store.dataset("mgtbind_complexes")) == 3924
    assert len(binman_store.dataset("protacdb_protacs")) == 15502


def test_unavailable_sources_raise_rather_than_return_empty():
    """D-NOB-010: a missing source must never look like a negative result."""
    for name in binman_store.UNAVAILABLE:
        with pytest.raises(binman_store.BinmanUnavailable):
            binman_store.dataset(name)


def test_all_seven_benchmark_pairs_resolve():
    """Phase 1 gate: every panel member resolves to a deposited structure."""
    report = benchmark.gate_report(benchmark.resolve_panel())
    assert report["passes"], f"unresolved panel members: {report['unresolved_indices']}"
    assert report["resolved"] == 7


def test_gspt1_numbering_frame_offset_is_138():
    """D-NOB-012. If this changes, every GSPT1 residue number downstream moves."""
    frame = numbering.resolve_frame("5HXB", "X", "P15170")
    assert frame.offset == 138
    assert frame.mismatches == 0
    assert frame.to_canonical(575) == 437


def test_other_panel_substrates_share_the_canonical_frame():
    """The offset is GSPT1-specific, which is what makes it easy to miss."""
    for pdb_id, chain, accession in (
        ("6H0F", "C", "Q13422"),
        ("5FQD", "C", "P48729"),
        ("6Q0W", "D", "Q14498"),
        ("6TD3", "C", "O75909"),
        ("5T35", "A", "O60885"),
    ):
        assert numbering.resolve_frame(pdb_id, chain, accession).offset == 0


def test_degron_scan_recovers_both_reference_degrons():
    """Phase 1 gate: GSPT1 domain II hairpin and IKZF1 ZF2, from structure."""
    result = degron_gate.run()
    assert result["passes"], result["references"]
    for reference in result["references"]:
        assert reference["degron_amino_acid"] == "G"
        matched = reference["matched_degron"]
        assert matched is not None
        assert matched["tip_res"] == reference["degron_residue_canonical"]


def test_every_construct_is_within_cap_or_a_declared_exception():
    """Phase 1 gate: token cap of 400, with only the two declared exceptions."""
    report = constructs.budget_report()
    assert all(item["error"] is None for item in report), report
    for item in report:
        assert item["acceptable"], item
    exceptions = {item["name"] for item in report if item["declared_exception"]}
    assert exceptions == {"VHL_VCB", "DCAF15_DDB1_DDA1"}


def test_ddb1_benchmark_construct_needs_no_exception():
    """D-NOB-013: BPC alone fits, measured from the CR-8 contacts in 6TD3."""
    report = {item["name"]: item for item in constructs.budget_report()}
    ddb1 = report["DDB1_BPC"]
    assert ddb1["within_cap"]
    assert not ddb1["declared_exception"]


def test_thresholds_and_tuning_exist_and_carry_no_hardcoded_hardware():
    tuning = paths.tuning()
    assert tuning["compute"]["cpu_workers"] >= 2
    assert tuning["compute"]["model_device"] in {"mps", "cpu"}
    assert paths.thresholds()["manifest"]["token_cap_tier1"] == 400
