"""A campaign's substrate domain against the one the plan now specifies.

The corrected campaign exists to test one claim: that a folded domain
recovers the pose better than a 15-mer fragment. Its substrate boundaries
come from an InterPro lookup, so a fix to how an ambiguous entry is resolved
moves them, and nothing recorded which domain each job actually used.

One has moved. `corr05_CSNK1A1_CRBN` submitted a 269-residue domain and the
plan now specifies 219, P48729 17-235, with the shorter sequence a strict
substring of the longer. CSNK1A1 is one of the six pairs in the published
`improved` list, 12.24 angstrom to 6.189, so the headline conclusion
includes a pair whose whole domain is not the one the plan beside it gives.

`stale_inputs` cannot see this. It compares a YAML against the queue row
beside it and both were written by one assembly, so they agree about a
boundary that has since moved. This compares the YAML against the plan
(F93).
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from nobble.validate import inputs  # noqa: E402

CORRECTED = ROOT / "campaigns" / "corrected_20261103T214331Z"


def test_the_substrate_is_found_by_chain_id_not_by_length():
    """The receptor is usually the longest chain, so taking the longest
    sequence reads the receptor for most pairs. That mistake made five of
    seven look as though no current domain matched them."""
    yaml_text = (
        "sequences:\n"
        "- protein:\n"
        "    id: A\n"
        "    sequence: AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA\n"
        "- protein:\n"
        "    id: P\n"
        "    sequence: PPPPPPPPPP\n"
        "- ligand:\n"
        "    id: L\n"
        "    ccd: Y70\n"
    )
    assert inputs.substrate_sequence(yaml_text) == "PPPPPPPPPP"


def test_a_yaml_with_no_substrate_chain_returns_nothing():
    assert inputs.substrate_sequence("sequences:\n- protein:\n    id: A\n"
                                     "    sequence: AAAA\n") is None


def test_the_corrected_campaign_has_exactly_one_superseded_substrate():
    """Measured, not assumed. Five of its pairs match the plan, IKZF1 is a
    15-mer control by design, and CSNK1A1 is the one that moved."""
    if not CORRECTED.exists():
        pytest.skip("no corrected campaign on this checkout")
    rows = inputs.superseded_substrates(CORRECTED)
    assert [row["pair_id"] for row in rows] == ["corr05_CSNK1A1_CRBN"], rows
    (row,) = rows
    assert row["submitted_length"] == 269
    assert row["planned_length"] == 219
    assert row["accession"] == "P48729"


def test_the_other_campaigns_have_none():
    """The benchmark panel submits 15-mers and the main campaign was
    assembled after the lookup changed, so a finding in either would mean
    something different from this one."""
    from nobble.execute.campaign import latest

    for campaign in (latest("benchmark"), latest("campaign")):
        if campaign is None:
            continue
        assert inputs.superseded_substrates(campaign) == [], campaign.name


def test_a_fifteen_mer_substrate_is_not_reported():
    """IKZF1 keeps its 15-mer in both campaigns deliberately, as the
    control that nothing else changed. Reporting it as superseded would
    bury the one real case in a false one."""
    if not CORRECTED.exists():
        pytest.skip("no corrected campaign on this checkout")
    rows = inputs.superseded_substrates(CORRECTED)
    assert not any("IKZF1" in row["pair_id"] for row in rows), rows


def test_the_comparison_conclusion_says_so():
    """Where it matters. The per-pair table is not what gets quoted, and
    CSNK1A1 is in the improved list."""
    from nobble.validate import compare

    baseline = ROOT / "campaigns" / "benchmark_20261103T192126Z"
    if not (baseline.exists() and CORRECTED.exists()):
        pytest.skip("both campaigns are needed")
    report = compare.run(baseline, CORRECTED)
    assert report["superseded_substrates"], report.keys()
    assert "no longer specifies" in report["conclusion"]
    assert "CSNK1A1" in report["conclusion"]
    assert "the measurement stands" in report["conclusion"], (
        "the caveat reads as though the number were wrong, which it is not"
    )
