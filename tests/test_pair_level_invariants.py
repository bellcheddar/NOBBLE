"""Choices taken by list order, correct only while an invariant holds.

F41 found a construct boundary selected by InterPro's ordering. The same
shape appears twice more, in both cases on an invariant that does hold and
that nothing checked.

`metrics.aggregate` reads a pair's construct, peptide, label, tier,
modality and six other fields off `pair_jobs[0]`, on the understanding
that these describe the pair rather than the job. They do. And
`ligand_key` is already taken differently, from the first job that has
one, because the binary arm has none: so one field was known to vary and
the rest were taken on trust.

`assemble.build_manifest` derives one pocket for a whole design scan from
`pairs[0]`'s ligand, with a comment saying every pair shares the parent's
receptor and glue by construction. Also true, also unchecked.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from nobble.score import metrics  # noqa: E402


def _job(**overrides):
    base = {
        "job_id": "j1", "pair_id": "p1", "seed": 1, "tokens": 400,
        "tier_setting": 1, "complex_type": "binary",
        "conditioning": "unconstrained", "construct": "CRBN_CULT",
        "e3_gene": "CRBN", "peptide_id": "pep1", "peptide_gene": "GSPT1",
        "peptide_label": "degraded", "modality": "glue", "tier": "benchmark",
        "peptide_sequence": "ACDEFGHIKLMNPQR",
        "confidence": {"pair_chains_iptm": {"0": {"1": 0.5}, "1": {"0": 0.5}}},
    }
    base.update(overrides)
    return base


def _aggregate(tmp_path, jobs):
    path = tmp_path / "results.jsonl"
    path.write_text("\n".join(json.dumps(j) for j in jobs) + "\n")
    pairs = metrics.aggregate(path)
    assert len(pairs) == 1
    return pairs[0]


def test_a_consistent_pair_carries_no_disagreement(tmp_path):
    pair = _aggregate(tmp_path, [
        _job(job_id="j1", seed=1),
        _job(job_id="j2", seed=2, complex_type="ternary",
             conditioning="conditioned", ligand_key="85C"),
    ])
    assert pair.pair_level_disagreements == {}
    # Narrow: an unrelated note already says "conditioning disagreement
    # not computable", so matching on "disagree" alone catches that too.
    assert not [n for n in pair.notes if "not one pair" in n]


def test_a_pair_whose_jobs_name_two_peptides_says_so(tmp_path):
    """Taking the first would report the pair as whichever job was read
    first, and nothing downstream could tell."""
    pair = _aggregate(tmp_path, [
        _job(job_id="j1", seed=1, peptide_sequence="ACDEFGHIKLMNPQR"),
        _job(job_id="j2", seed=2, peptide_sequence="WWWWWWWWWWWWWWW"),
    ])
    assert "peptide_sequence" in pair.pair_level_disagreements
    assert pair.pair_level_disagreements["peptide_sequence"] == [
        "ACDEFGHIKLMNPQR", "WWWWWWWWWWWWWWW",
    ]
    note = next(n for n in pair.notes if "not one pair" in n)
    assert "not one pair" in note


def test_a_pair_whose_jobs_name_two_labels_says_so(tmp_path):
    """The worst of the twelve: a pair half degraded and half not would sit
    on whichever side of the matched-control curve it was read into."""
    pair = _aggregate(tmp_path, [
        _job(job_id="j1", seed=1, peptide_label="degraded"),
        _job(job_id="j2", seed=2, peptide_label="not_degraded"),
    ])
    assert pair.pair_level_disagreements["peptide_label"] == [
        "degraded", "not_degraded",
    ]


def test_the_fields_that_vary_by_design_are_not_flagged(tmp_path):
    """complex_type, conditioning, seed and job_id differ across a pair's
    jobs by construction, and ligand_key is absent from the binary arm. A
    check that flagged those would fire on every pair in every campaign."""
    pair = _aggregate(tmp_path, [
        _job(job_id="j1", seed=1, complex_type="binary"),
        _job(job_id="j2", seed=2, complex_type="ternary",
             conditioning="conditioned", ligand_key="85C"),
        _job(job_id="j3", seed=3, complex_type="ternary",
             conditioning="unconstrained", ligand_key="85C"),
    ])
    assert pair.pair_level_disagreements == {}
    for excluded in ("complex_type", "conditioning", "seed", "job_id",
                     "ligand_key"):
        assert excluded not in metrics.PAIR_LEVEL_FIELDS, excluded


def test_the_real_campaigns_have_no_pair_level_disagreement():
    """The invariant as it stands. Both finished campaigns are clean, which
    is why taking the first job was never wrong, only unchecked."""
    import glob

    checked = 0
    for results in sorted(glob.glob(str(ROOT / "campaigns" / "*" / "results.jsonl"))):
        pairs = metrics.aggregate(Path(results))
        if not pairs:
            continue
        checked += 1
        bad = {p.pair_id: p.pair_level_disagreements
               for p in pairs if p.pair_level_disagreements}
        assert not bad, f"{Path(results).parent.name}: {bad}"
    if not checked:
        pytest.skip("no scored campaign on this checkout")


def test_a_design_scan_whose_pairs_split_across_two_glues_is_refused(monkeypatch):
    """One pocket cannot describe two glues, and the pocket was derived from
    pairs[0] regardless."""
    from nobble.design import assemble as A

    def two_glues(*args, **kwargs):
        return {
            "pairs": [
                {"pair_id": "a", "role": "parent", "ligand": {"ccd": "85C"},
                 "peptide_id": "pep1", "cofactor": {}},
                {"pair_id": "b", "role": "variant", "ligand": {"ccd": "Y70"},
                 "peptide_id": "pep2", "cofactor": {}},
            ],
            "jobs": [], "errors": 0, "warnings": 0,
            "peptides": {"pep1": {}}, "parent": {"peptide_id": "pep1"},
        }

    monkeypatch.setattr(A, "build_manifest", two_glues)
    with pytest.raises(RuntimeError, match="do not share one glue"):
        A.assemble("pep1")
