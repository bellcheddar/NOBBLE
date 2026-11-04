"""Spec 1.3's MSA policy, and spec 4.7's affinity cap.

    Generate one MSA per trimmed receptor construct, offline, once, before
    the campaign starts. Reference the cached file in every YAML. Peptide
    chains and ligand chains get no MSA.

A mutation sweep over yaml_gen found three spec requirements with no test
behind them, and these are the most consequential gaps any of the four
sweeps turned up:

  * giving the peptide an MSA, which spec 1.3 forbids outright;
  * dropping the receptor's cached MSA so every chain runs with `empty`,
    which would degrade all 2,360 predictions with nothing raising
    anywhere and no record in any manifest;
  * requesting the affinity head past the 128 heavy-atom cap Boltz-2
    imposes, which spec 4.7 and D-NOB-005 both forbid.

All three alter what Boltz is asked to compute, and none would have
produced an error: the campaign would simply have been worse, or wrong,
than the one the spec describes.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from nobble.curate import constructs as C  # noqa: E402
from nobble.execute import msa as msa_module  # noqa: E402
from nobble.execute import yaml_gen as Y  # noqa: E402


def _fixture():
    """A real benchmark pair, so the receptor's MSA is genuinely cached."""
    from nobble.curate import library as LM, ligands as L, manifest as M
    from nobble.curate import peptides as P

    lib = LM.load()
    if lib is None:
        pytest.skip("library manifest missing: run nobble.curate.library")
    rows = {row["peptide_id"]: row for row in lib["peptides"]}
    built = M.build_campaign_manifest(library=lib["peptides"])

    pair = next((p for p in built["pairs"]
                 if p["tier"] == "benchmark" and p.get("ligand", {}).get("ccd")), None)
    if pair is None:
        pytest.skip("no benchmark pair with a CCD ligand")
    job = next(j for j in built["jobs"]
               if j.pair_id == pair["pair_id"] and j.complex_type == "ternary")
    peptide = P.Peptide(**{k: v for k, v in rows[pair["peptide_id"]].items()
                           if k != "length"})
    ligand = L.by_ccd(pair["ligand"]["ccd"], modality="glue")
    return job, peptide, ligand


def _chains(document):
    """(kind, entry) for each chain in the document, in order."""
    out = []
    for item in document["sequences"]:
        for kind, entry in item.items():
            out.append((kind, entry))
    return out


def test_the_peptide_chain_is_given_no_msa():
    """Spec 1.3, stated as a prohibition rather than a default."""
    job, peptide, ligand = _fixture()
    document = Y.build_yaml(job, peptide, ligand, None)

    peptide_entries = [entry for kind, entry in _chains(document)
                       if kind == "protein" and entry["id"] == Y.PEPTIDE_CHAIN]
    assert len(peptide_entries) == 1
    assert peptide_entries[0]["msa"] == msa_module.EMPTY, (
        "the peptide chain carries an MSA, which spec 1.3 forbids"
    )


def test_the_receptor_chains_reference_their_cached_msa():
    """The one that would have degraded every prediction silently."""
    job, peptide, ligand = _fixture()
    document = Y.build_yaml(job, peptide, ligand, None)

    construct = C.CONSTRUCTS[job.construct]
    receptor_ids = set("ABCDEFGH"[: len(construct.segments)])
    receptor_entries = [entry for kind, entry in _chains(document)
                        if kind == "protein" and entry["id"] in receptor_ids]
    assert receptor_entries, "no receptor chain in the document"

    cached = [entry for entry in receptor_entries
              if msa_module.is_cached(entry["sequence"])]
    if not cached:
        pytest.skip("no receptor MSA cached on this checkout")

    for entry in cached:
        assert entry["msa"] != msa_module.EMPTY, (
            f"chain {entry['id']} has a cached MSA and the YAML says 'empty', "
            "so Boltz would fold it without one"
        )
        assert entry["msa"] == str(msa_module.a3m_path(entry["sequence"]))
        assert Path(entry["msa"]).exists(), (
            f"chain {entry['id']} points at {entry['msa']}, which is not there"
        )


def test_an_uncached_receptor_falls_back_to_empty_rather_than_a_bad_path():
    """Never an MSA server call during a campaign, and never a path that
    does not resolve: Boltz would fail the job rather than fold without."""
    job, peptide, ligand = _fixture()

    # A sequence certain not to be in the cache.
    novel = "W" * 97
    assert not msa_module.is_cached(novel)

    import nobble.execute.yaml_gen as module
    original = module.C.CONSTRUCTS[job.construct]

    class _Segment:
        accession = original.segments[0].accession
        label = "synthetic"
        interpro_entry = None

        def sequence(self):
            return novel

        def range(self):
            return 1, len(novel)

    patched = type(original)(
        name=original.name, e3_gene=original.e3_gene,
        segments=(_Segment(),), exception=original.exception,
        rationale=original.rationale,
    )
    module.C.CONSTRUCTS[job.construct] = patched
    try:
        document = Y.build_yaml(job, peptide, ligand, None)
        entry = next(e for kind, e in _chains(document)
                     if kind == "protein" and e["sequence"] == novel)
        assert entry["msa"] == msa_module.EMPTY
    finally:
        module.C.CONSTRUCTS[job.construct] = original


def test_affinity_is_requested_only_within_the_heavy_atom_cap():
    """Boltz-2 caps the affinity head at 128 heavy atoms. Spec 4.7 and
    D-NOB-005: recorded for the small-molecule chain only, never a ranking
    key, and never requested for a ligand over the cap."""
    from nobble import paths

    job, peptide, ligand = _fixture()
    cap = int(paths.thresholds()["manifest"]["affinity_heavy_atom_cap"])

    oversized = type(ligand)(**{**ligand.__dict__,
                                "heavy_atoms": cap + 1,
                                "affinity_available": False})
    document = Y.build_yaml(job, peptide, oversized, None)
    assert "properties" not in document, (
        f"affinity requested for a {cap + 1} heavy-atom ligand, over the "
        f"{cap} cap"
    )

    within = type(ligand)(**{**ligand.__dict__,
                             "heavy_atoms": cap - 1,
                             "affinity_available": True})
    document = Y.build_yaml(job, peptide, within, None)
    assert document["properties"] == [
        {"affinity": {"binder": Y.LIGAND_CHAIN}}
    ], document.get("properties")


def test_affinity_names_the_ligand_chain_and_never_the_peptide():
    """D-NOB-005: no peptide affinity is reported."""
    job, peptide, ligand = _fixture()
    document = Y.build_yaml(job, peptide, ligand, None)
    for prop in document.get("properties") or []:
        binder = prop.get("affinity", {}).get("binder")
        assert binder == Y.LIGAND_CHAIN, binder
        assert binder != Y.PEPTIDE_CHAIN
