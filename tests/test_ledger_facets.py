"""Spec Phase 4 facets the pair ledger on flags, and two were missing.

    Campaign -- the pair ledger. Sortable, filterable table over every
    (receptor, peptide, ligand) triple. Faceted on modality (glue /
    PROTAC), tier (benchmark / A / B), and flags (furniture, forced,
    affinity_unavailable).

modality and tier were there. None of the three flags was.

Two of the three are now offered. `furniture` is not, deliberately:
ProtCID was never acquired, so the field is null on every pair and its
status is permanently "not_computed: protcid_unavailable" (D-NOB-010). A
control that can never match anything is worse than no control, and the
About page already says the veto is not computed.

`affinity_unavailable` needed the same one-join fix as F51 before a facet
was possible at all: `affinity_available` was on the queue row and was
dropped when scoring aggregated jobs into pairs, so there was nothing for
a filter to read (F53).
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

TEMPLATE = ROOT / "nobble" / "app" / "templates" / "campaign.html"


def _job(job_id, affinity_available, **extra):
    row = {
        "job_id": job_id, "pair_id": "p1", "seed": 1, "tokens": 400,
        "tier_setting": 1, "complex_type": "ternary",
        "conditioning": "unconstrained", "construct": "CRBN_CULT",
        "e3_gene": "CRBN", "peptide_id": "pep", "tier": "benchmark",
        "ligand_key": "85C", "ligand_encoding": "ccd",
        "affinity_available": affinity_available,
        "confidence": {"pair_chains_iptm": {"0": {"1": 0.5}, "1": {"0": 0.5}}},
    }
    row.update(extra)
    return row


def _aggregate(tmp_path, jobs):
    from nobble.score import metrics

    path = tmp_path / "results.jsonl"
    path.write_text("\n".join(json.dumps(j) for j in jobs) + "\n")
    pairs = metrics.aggregate(path)
    assert len(pairs) == 1
    return pairs[0]


def test_affinity_availability_reaches_the_pair(tmp_path):
    """The join the facet needs. A string "False" from a JSONL row is not a
    falsy Python value, so it is parsed rather than passed through."""
    assert _aggregate(tmp_path, [_job("j1", "False")]).affinity_available is False
    assert _aggregate(tmp_path, [_job("j2", "True")]).affinity_available is True
    assert _aggregate(tmp_path, [_job("j3", False)]).affinity_available is False
    assert _aggregate(tmp_path, [_job("j4", True)]).affinity_available is True


def test_an_unrecorded_availability_stays_unknown(tmp_path):
    """None is not False. A pair whose jobs never recorded it must not be
    filtered as "affinity unavailable", which would be a claim."""
    row = _job("j1", None)
    del row["affinity_available"]
    assert _aggregate(tmp_path, [row]).affinity_available is None


def test_the_ledger_offers_the_two_meaningful_flag_facets():
    source = TEMPLATE.read_text()
    for facet in ("f-forced", "f-no-affinity"):
        assert f'id="{facet}"' in source, f"{facet} is not in the markup"
        assert f"'{facet}'" in source, f"{facet} is never wired to a redraw"


def test_the_furniture_facet_is_absent_and_the_reason_recorded():
    """Not an oversight. The field is permanently null, so the control
    could never match; the template says why, beside where it would go."""
    source = TEMPLATE.read_text()
    assert 'id="f-furniture"' not in source
    assert "protcid_unavailable" in source, (
        "the furniture facet is absent with no reason beside it, which is "
        "indistinguishable from forgetting it"
    )


def _run_filter(rows, forced_only=False, no_affinity_only=False):
    """Run the ledger's own filter predicate under node (F50).

    Lifted from the template by name so the test exercises the condition
    rather than matching its source.
    """
    source = TEMPLATE.read_text()
    match = re.search(r"rows = rows\.filter\((p => .*?)\);\n", source, re.S)
    assert match, "the ledger's filter is no longer a single expression"
    predicate = match.group(1)
    script = (
        "const modality = '', tier = '';\n"
        "const bridgedOnly = false, pinnedOnly = false, completeOnly = false;\n"
        f"const forcedOnly = {str(forced_only).lower()};\n"
        f"const noAffinityOnly = {str(no_affinity_only).lower()};\n"
        "const NOBBLE = { pins: { matches: () => true } };\n"
        f"const predicate = {predicate};\n"
        f"console.log(JSON.stringify({json.dumps(rows)}"
        ".filter(predicate).map(p => p.pair_id)));"
    )
    completed = subprocess.run(["node", "-e", script], capture_output=True,
                               text=True, timeout=30)
    assert completed.returncode == 0, completed.stderr
    return json.loads(completed.stdout)


ROWS = [
    {"pair_id": "plain", "forced": False, "affinity_available": True,
     "composite_complete": True},
    {"pair_id": "forced", "forced": True, "affinity_available": True,
     "composite_complete": True},
    {"pair_id": "no_affinity", "forced": False, "affinity_available": False,
     "composite_complete": True},
    {"pair_id": "unknown", "composite_complete": True},
]


def test_the_filters_are_off_by_default():
    assert _run_filter(ROWS) == ["plain", "forced", "no_affinity", "unknown"]


def test_the_forced_facet_keeps_only_forced_pairs():
    assert _run_filter(ROWS, forced_only=True) == ["forced"]


def test_the_affinity_facet_keeps_only_pairs_over_the_cap():
    """And not the pair whose availability was never recorded: None is not
    False, and filtering it in would assert something unknown."""
    assert _run_filter(ROWS, no_affinity_only=True) == ["no_affinity"]


def test_the_two_facets_compose():
    """A forced pair that is also over the cap, and nothing else."""
    rows = ROWS + [{"pair_id": "both", "forced": True,
                    "affinity_available": False, "composite_complete": True}]
    assert _run_filter(rows, forced_only=True, no_affinity_only=True) == ["both"]
