"""The conditioned and unconstrained arms must actually differ.

Conditioning is the control that separates "Boltz found this pose" from
"Boltz was told where to put the ligand". If a job labelled unconstrained
carried a pocket constraint anyway, every unconstrained result would be
quietly conditioned and the comparison would mean nothing, while all the
labels, counts and tabs went on looking right.

Nothing checked it. `conditioning` appeared in the test suite only as
fixture data, never as an assertion, so the invariant lived entirely in
one `if` in yaml_gen.build_yaml.
"""
from __future__ import annotations

import glob
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def _fixture():
    from nobble.curate import ligands as L, library as LM, manifest as M
    from nobble.curate import peptides as P
    from nobble.execute import yaml_gen as Y

    lib = LM.load()
    if lib is None:
        pytest.skip("library manifest missing: run nobble.curate.library")
    rows = {r["peptide_id"]: r for r in lib["peptides"]}
    manifest = M.build_campaign_manifest(library=lib["peptides"])

    pair = next(p for p in manifest["pairs"] if p.get("ligand", {}).get("ccd"))
    jobs = [j for j in manifest["jobs"] if j.pair_id == pair["pair_id"]]
    peptide = P.Peptide(**{k: v for k, v in rows[pair["peptide_id"]].items()
                           if k != "length"})
    ligand = L.by_ccd(pair["ligand"]["ccd"], modality="glue")
    pocket = Y.PocketConstraint(
        chain="A", positions=[118, 119, 120], max_distance=6.0,
        provenance="test",
    )
    return Y, jobs, peptide, ligand, pocket


def test_only_a_conditioned_ternary_job_gets_a_pocket_constraint():
    Y, jobs, peptide, ligand, pocket = _fixture()

    def constrained(complex_type: str, conditioning: str) -> bool:
        job = next((j for j in jobs if j.complex_type == complex_type
                    and j.conditioning == conditioning), None)
        if job is None:
            pytest.skip(f"no {conditioning} {complex_type} job in the manifest")
        # The pocket is supplied in every case, so presence can only come
        # from the conditioning flag and not from the pocket being absent.
        return "constraints" in Y.build_yaml(job, peptide, ligand, pocket)

    assert constrained("ternary", "conditioned") is True
    assert constrained("ternary", "unconstrained") is False
    # A binary complex has no ligand, so there is no pocket to condition on
    # even when a pocket was measured for the pair.
    assert constrained("binary", "unconstrained") is False


def test_a_conditioned_job_with_no_measured_pocket_carries_no_constraint():
    """It must not silently fall back to an unconstrained run wearing the
    conditioned label. campaign.py drops these jobs; this pins that
    build_yaml cannot invent one either."""
    Y, jobs, peptide, ligand, _pocket = _fixture()
    job = next((j for j in jobs if j.complex_type == "ternary"
                and j.conditioning == "conditioned"), None)
    if job is None:
        pytest.skip("no conditioned ternary job in the manifest")
    assert "constraints" not in Y.build_yaml(job, peptide, ligand, None)


@pytest.mark.parametrize("queue_path", sorted(glob.glob("campaigns/*/queue.jsonl")))
def test_every_written_yaml_matches_its_declared_conditioning(queue_path):
    """The invariant as it actually stands on disk.

    The unit tests above cover the generator. This covers the files Boltz
    is really being handed, including campaigns written by earlier versions
    of the generator that are still queued to run.
    """
    rows = [json.loads(line) for line in open(queue_path) if line.strip()]
    if not rows:
        pytest.skip("empty queue")

    mismatched = []
    for row in rows:
        try:
            text = Path(row["yaml"]).read_text()
        except OSError:
            continue
        has_pocket = "pocket:" in text
        should = row["conditioning"] == "conditioned"
        if has_pocket != should:
            mismatched.append((row["job_id"], row["conditioning"], has_pocket))

    assert not mismatched, (
        f"{len(mismatched)} job(s) in {queue_path} disagree with their YAML, "
        f"first: {mismatched[:3]}"
    )
