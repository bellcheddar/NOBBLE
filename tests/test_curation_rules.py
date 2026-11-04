"""The curation rules as functions, not as the artefacts they produced.

tests/test_curation_frozen.py checks the committed library and Tier B
selection against the rules, which catches an artefact that has drifted
from the rules. It does not catch a rule that has changed, because nothing
reruns the derivation: the fifth mutation sweep still caught one of five
after that file was added.

These substitute the inputs instead, so the rules run without BINMAN's
triage table, an ESM checkpoint or the AlphaFold cache, and a changed rule
fails here.

One of the four misses turned out to be mislabelled by me.
`TIER_A_NAMED` is not a selection criterion: Tier A is every validated
ligase, and the named list annotates them and reports which are absent.
Removing the membership test drops a reason string and selects exactly the
same ligases, so there was less there than the mutation's name claimed.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from nobble.curate import tiers  # noqa: E402


def _candidate(gene, status, pocket, rank=1, plddt=95.0):
    return tiers.Candidate(
        uniprot_acc=f"X{gene}", gene=gene, family="test",
        exploitation_status=status, pocket_score=pocket,
        triage_score=1.0, triage_rank=rank, tumour_enriched=0,
        expression_breadth=1, best_structure=None, pdb_entries=0,
        plddt={"mean_plddt": 70.0, "best_window_mean_plddt": plddt,
               "best_window": [1, 200], "status": "ok"},
    )


def test_tier_b_rejects_a_ligase_below_the_pocket_floor(monkeypatch):
    """Spec 3.3's second filter. Removing it admits undruggable pockets and
    fills take_top from a larger pool, so a different fifteen ligases enter
    the campaign."""
    floor = float(tiers.paths.thresholds()["tier_b"]["pocket_druggability_min"])
    pool = [
        _candidate("GOOD1", "ligandable unproven", floor + 0.05, rank=1),
        _candidate("GOOD2", "ligandable unproven", floor, rank=2),
        _candidate("BAD1", "ligandable unproven", floor - 0.01, rank=3),
        _candidate("BAD2", "ligandable unproven", 0.0, rank=4),
        _candidate("BAD3", "ligandable unproven", None, rank=5),
    ]
    monkeypatch.setattr(tiers, "_candidates", lambda where, parameters=(): list(pool))
    monkeypatch.setattr(tiers.plddt, "summary",
                        lambda accession: {"mean_plddt": 70.0,
                                           "best_window_mean_plddt": 95.0,
                                           "best_window": [1, 200],
                                           "status": "ok"})

    result = tiers.tier_b()
    genes = {row["gene"] for row in result["selected"]}
    assert "GOOD1" in genes and "GOOD2" in genes, genes
    for rejected in ("BAD1", "BAD2", "BAD3"):
        assert rejected not in genes, (
            f"{rejected} is below the {floor} pocket floor and was selected"
        )
    # The funnel has to record the rejection, not merely perform it.
    key = next(k for k in result["funnel"] if k.startswith("pocket_score_ge_"))
    assert result["funnel"][key] == 2, result["funnel"]
    assert result["funnel"]["ligandable_unproven"] == 5


def test_a_missing_pocket_score_is_not_treated_as_a_passing_one(monkeypatch):
    """`(item.pocket_score or 0.0)` makes a null score zero rather than
    waving it through, which is the conservative reading and the one a
    funnel can explain."""
    floor = float(tiers.paths.thresholds()["tier_b"]["pocket_druggability_min"])
    pool = [_candidate("NOSCORE", "ligandable unproven", None)]
    monkeypatch.setattr(tiers, "_candidates", lambda where, parameters=(): list(pool))
    monkeypatch.setattr(tiers.plddt, "summary",
                        lambda accession: {"status": "ok",
                                           "best_window_mean_plddt": 95.0})
    result = tiers.tier_b()
    assert not result["selected"], "a ligase with no pocket score was selected"
    assert floor > 0


def test_tier_a_annotates_the_named_ligases_and_reports_the_absent(monkeypatch):
    """Not a selection criterion, which is the finding. Tier A is every
    validated ligase; the named list annotates them and names the gaps."""
    pool = [
        _candidate("CRBN", "validated", 0.9),
        _candidate("NOTNAMED", "validated", 0.9),
    ]
    monkeypatch.setattr(tiers, "_candidates", lambda where, parameters=(): list(pool))
    monkeypatch.setattr(tiers.plddt, "summary", lambda accession: {"status": "ok"})

    result = tiers.tier_a()
    by_gene = {row["gene"]: row for row in result["selected"]}
    assert set(by_gene) == {"CRBN", "NOTNAMED"}, "selection changed"
    assert any("named in spec 3.2" in r for r in by_gene["CRBN"]["reasons"])
    assert not any("named in spec 3.2" in r for r in by_gene["NOTNAMED"]["reasons"])
    # Every other named ligase is absent from this pool and must be reported.
    absent = result["named_but_absent_from_binman_triage"]
    assert "VHL" in absent and "CRBN" not in absent, absent
    assert result["named_in_spec"] == list(tiers.TIER_A_NAMED)


def test_the_library_persists_the_reduction_and_nothing_else(monkeypatch, tmp_path):
    """The worst of the four misses. With the reduction's selection ignored,
    every candidate is written: 25,519 peptides instead of 158, and a
    campaign of 383,000 jobs instead of 2,360.

    reduce_library is substituted rather than run, because it loads an ESM
    checkpoint, and MANIFEST is redirected so the frozen library is not
    touched."""
    from nobble.curate import library as library_module
    from nobble.curate import peptides as P

    def peptide(peptide_id):
        return P.Peptide(
            peptide_id=peptide_id, sequence="ACDEFGHIKLMNPQR", source="benchmark",
            label="degraded", accession=None, gene=peptide_id,
            start_res=None, end_res=None,
        )

    candidates = [peptide(f"p{index}") for index in range(10)]
    keep = ["p3", "p7"]

    class _Reduction:
        selected_ids = keep
        summary = {"selected": len(keep), "candidates": len(candidates)}

        def to_dict(self):
            return dict(self.summary)

    monkeypatch.setattr(library_module, "MANIFEST", tmp_path / "library.jsonl")
    monkeypatch.setattr(library_module, "SUMMARY", tmp_path / "library.summary.json")
    monkeypatch.setattr(library_module.P, "build",
                        lambda *a, **k: {"peptides": candidates})
    monkeypatch.setattr(library_module, "reduce_library",
                        lambda peptides, budget: _Reduction())
    monkeypatch.setattr(library_module, "projected_hours",
                        lambda *a, **k: {"status": "within_max_compute"})

    library_module.build(force=True, budget=2)

    written = [json.loads(line) for line
               in (tmp_path / "library.jsonl").read_text().splitlines() if line.strip()]
    ids = [row["peptide_id"] for row in written]
    assert ids == keep, (
        f"the manifest holds {len(ids)} peptides; the reduction selected "
        f"{len(keep)}"
    )
