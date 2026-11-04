"""The zinc's chain index must sit beyond the peptide's, not before it.

Delta-ipTM is the receptor-to-peptide ipTM, taken as a minimum across the
substrate receptor's segments. Which chain index the peptide occupies is
derived from the construct: receptor segments take 0 upward, then the
peptide, then the structural ion if there is one, then the glue.

The ion makes that arithmetic load-bearing in a way the three-chain jobs
never did, and the matrix is asymmetric in a way worth being precise about.
In a real Sievers prediction `pair_chains_iptm[i]["2"]` is 0.0 for every
row, the ion being a target no other chain has an interface with, while
row "2" carries ordinary values: 0.995 to the receptor, 0.953 to the
peptide. So the danger is not reading the ion as a source, which gives a
plausible number, but reading it as the *target* where the peptide should
be. That returns 0.0, and Delta-ipTM becomes the difference of two zeros on
the arm the headline ROC is computed on.

A first version of this file asserted the ion's row was zero as well. It is
not, and the test said so.

Checked against the real thing. `campaigns/smoke_sievers` holds both arms
of `sv_neg_ZN346_d5063d`, and the aggregated pair gives iptm_min_ternary
0.952 and iptm_min_binary 0.856, which are the receptor-to-peptide values
rather than the ion's zeros.

The arithmetic holds because every zinc-bearing job in the campaign uses a
one-segment construct, so the peptide is chain 1 and the ion chain 2. That
is a property of the current queue rather than of the code, so it is
asserted here: a Sievers pair on a multi-segment receptor would move both
indices, and the reasoning would need redoing rather than assuming (F83).
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from nobble.curate import constructs as C  # noqa: E402
from nobble.execute.campaign import latest  # noqa: E402

ZINC_CHAIN = re.compile(r"id:\s*Z\b")


def _queue():
    campaign = latest("campaign")
    if campaign is None or not (campaign / "queue.jsonl").exists():
        pytest.skip("no main campaign assembled")
    return campaign, [json.loads(line) for line
                      in (campaign / "queue.jsonl").read_text().splitlines()
                      if line.strip()]


def _carries_zinc(job) -> bool:
    path = Path(job["yaml"])
    return path.exists() and ZINC_CHAIN.search(path.read_text()) is not None


def test_the_ion_always_sits_beyond_the_peptide():
    """The invariant that makes the minimum safe. Receptor segments take 0
    upward, the peptide takes the next index, and the ion the one after,
    so no receptor-to-peptide pair can reach it."""
    _campaign, queue = _queue()
    checked = 0
    for job in queue:
        if not _carries_zinc(job):
            continue
        segments = len(C.CONSTRUCTS[job["construct"]].segments)
        peptide_index = segments
        ion_index = segments + 1
        assert ion_index > peptide_index
        assert peptide_index not in C.CONSTRUCTS[
            job["construct"]].substrate_receptor_chains()
        checked += 1
    assert checked > 0, "no zinc-bearing job was examined"


def test_no_zinc_job_uses_a_multi_segment_receptor():
    """A property of this queue, not of the code. Every zinc-bearing job
    is CRBN_CULT with one receptor segment, which is why the peptide is
    chain 1 and the ion chain 2 in the prediction this was verified
    against. A Sievers pair on VHL or DCAF15 would shift both, and the
    verification would not carry over."""
    _campaign, queue = _queue()
    offenders = {}
    for job in queue:
        if not _carries_zinc(job):
            continue
        segments = len(C.CONSTRUCTS[job["construct"]].segments)
        if segments != 1:
            offenders[job["construct"]] = segments
    assert not offenders, (
        "zinc-bearing job(s) on a multi-segment receptor: "
        f"{offenders}. The chain arithmetic still holds, but it was only "
        "verified on a one-segment construct, so recheck before trusting "
        "Delta-ipTM on these"
    )


def test_the_ion_is_a_zero_target_and_not_a_zero_source():
    """The premise, stated the way the data actually is.

    Reading the ion where the peptide belongs returns 0.0, which is the
    catastrophic direction. Reading it where a receptor segment belongs
    returns a plausible 0.99, which is the quiet one. The asymmetry is why
    the peptide index matters more than the receptor set.
    """
    import glob

    files = sorted(glob.glob(
        str(ROOT / "campaigns" / "smoke_sievers" / "**" / "confidence*.json"),
        recursive=True))
    if not files:
        pytest.skip("no Sievers smoke prediction on this checkout")

    examined = 0
    for path in files:
        matrix = (json.loads(Path(path).read_text()).get("pair_chains_iptm")
                  or {})
        if len(matrix) < 3:
            continue
        examined += 1
        # The ion as a target: zero from every chain, including itself.
        for source, row in matrix.items():
            assert float(row["2"]) == 0.0, (source, row)
        # The ion as a source: ordinary values, which is why a minimum that
        # includes it in the receptor set would not look wrong.
        ion_row = matrix["2"]
        assert any(float(value) > 0.5 for key, value in ion_row.items()
                   if key != "2"), ion_row
    assert examined > 0, "no multi-chain confidence matrix was examined"


def test_the_aggregated_pair_uses_the_peptide_and_not_the_ion():
    """End to end on the real prediction: both arms through aggregate, and
    the result must be the receptor-to-peptide values rather than zeros."""
    import glob
    import tempfile

    from nobble.score import metrics

    files = sorted(glob.glob(
        str(ROOT / "campaigns" / "smoke_sievers" / "**" / "confidence*.json"),
        recursive=True))
    if len(files) < 2:
        pytest.skip("both arms of a Sievers smoke pair are needed")

    rows = []
    for path in files:
        arm = "ternary" if "ternary" in path else "binary"
        rows.append({
            "job_id": f"sv_smoke__{arm}__x__seed1", "pair_id": "sv_smoke",
            "seed": 1, "tokens": 300, "tier_setting": 1, "complex_type": arm,
            "conditioning": "conditioned" if arm == "ternary" else "unconstrained",
            "construct": "CRBN_CULT", "e3_gene": "CRBN",
            "peptide_id": "sv_smoke", "tier": "sievers_zf",
            "peptide_label": "not_degraded",
            "ligand_key": "Y70" if arm == "ternary" else None,
            "confidence": json.loads(Path(path).read_text()), "status": "done",
        })
    results = Path(tempfile.mkdtemp()) / "results.jsonl"
    results.write_text("\n".join(json.dumps(r) for r in rows) + "\n")

    (pair,) = metrics.aggregate(results)
    assert pair.iptm_min_ternary is not None
    assert pair.iptm_min_binary is not None
    assert pair.iptm_min_ternary > 0.5, (
        f"the ternary minimum is {pair.iptm_min_ternary}, which is what "
        "including the ion's zero column would give"
    )
    assert pair.iptm_min_binary > 0.5, pair.iptm_min_binary
    assert pair.delta_iptm is not None
