"""The Tier B arm: eleven unproven ligases against seven proven pairs.

Spec 3.3 selected fifteen ligandable-unproven ligases and named no receptor
construct for any of them, so the arm was selected, frozen, gate-passed and
unrunnable. D-NOB-072 named eleven and excluded four; D-NOB-073 is the
design this builds.

A pair holds a known-working glue and degron together and swaps only the
receptor: lenalidomide with the IKZF1 zinc finger it actually degrades,
against ASB8 instead of CRBN. The benchmark panel therefore contains the
same glue and degron with its proven receptor, which is a matched positive
control that costs no jobs. Each pair also gets its degron's
composition-matched scramble, which the library already carried.

Counts are derived here, never quoted. 11 receptors times 7 glue-degron
pairs times 2 roles is 154 pairs, and at 5 seeds over 2 arms that is 1,540
jobs, but this file computes each from the inputs so that changing the form
changes the expectation rather than failing the test.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from nobble.curate import constructs as C  # noqa: E402
from nobble.curate import manifest as M  # noqa: E402
from nobble.curate import tier_b_constructs as T  # noqa: E402
from nobble.execute.campaign import latest_or_absent  # noqa: E402


@pytest.fixture(scope="module")
def arm():
    manifest = M.build_tier_b_manifest()
    if not manifest.get("pairs"):
        pytest.skip(f"no Tier B arm: {manifest.get('status')}")
    return manifest


def test_the_arm_is_every_receptor_against_every_proven_pair(arm):
    receptors = len(T.load())
    glues = len(arm["glue_degron_pairs"])
    assert receptors and glues
    assert len(arm["pairs"]) == receptors * glues * 2, (
        f"{len(arm['pairs'])} pairs for {receptors} receptors and {glues} "
        "glue-degron pairs, with a scramble each"
    )
    roles = {}
    for pair in arm["pairs"]:
        roles[pair["role"]] = roles.get(pair["role"], 0) + 1
    assert roles == {"positive": receptors * glues,
                     "scramble": receptors * glues}, roles


def test_every_scramble_matches_the_degron_it_controls(arm):
    """A scramble run against a different receptor or drug than its positive
    is not a control for anything, which is the rule the main campaign's
    scrambles already follow."""
    positives = {(p["e3_gene"], p["borrowed_from"]): p
                 for p in arm["pairs"] if p["role"] == "positive"}
    assert positives
    for pair in arm["pairs"]:
        if pair["role"] != "scramble":
            continue
        twin = positives.get((pair["e3_gene"], pair["borrowed_from"]))
        assert twin is not None, pair["pair_id"]
        assert pair["ligand"] == twin["ligand"], pair["pair_id"]
        assert pair["construct"] == twin["construct"], pair["pair_id"]
        assert pair["scramble_of"] == twin["peptide_id"], pair["pair_id"]
        assert pair["peptide_id"] != twin["peptide_id"]


def test_the_composition_is_actually_matched(arm):
    """A scramble is a permutation of its parent, so the two must agree on
    length and on amino-acid composition and differ in order."""
    import collections

    by_id = {p["peptide_id"]: p for p in arm["pairs"]}
    for pair in arm["pairs"]:
        if pair["role"] != "scramble":
            continue
        parent = by_id.get(pair["scramble_of"])
        assert parent is not None, pair["pair_id"]
        assert (collections.Counter(pair["peptide_sequence"])
                == collections.Counter(parent["peptide_sequence"])), pair["pair_id"]
        assert pair["peptide_sequence"] != parent["peptide_sequence"]


def test_no_job_is_conditioned(arm):
    """Conditioning places the ligand in a pocket derived from the
    receptor's own deposited structure. A Tier B receptor has none, and the
    pocket in the benchmark pair it borrows from belongs to a different
    protein."""
    conditioned = [job.job_id for job in arm["jobs"]
                   if job.conditioning != "unconstrained"]
    assert not conditioned, conditioned[:4]


def test_the_job_count_follows_the_axes(arm):
    seeds = len(arm["seeds"])
    assert arm["jobs_per_pair"] == seeds * len(M.COMPLEXES)
    assert len(arm["jobs"]) == len(arm["pairs"]) * arm["jobs_per_pair"]


def test_pair_ids_are_unique(arm):
    ids = [p["pair_id"] for p in arm["pairs"]]
    assert len(ids) == len(set(ids)), "duplicate pair ids"
    job_ids = [job.job_id for job in arm["jobs"]]
    assert len(job_ids) == len(set(job_ids)), "duplicate job ids"


def test_the_error_count_is_derived_rather_than_asserted(arm):
    """I wrote `"errors": 0` into this builder and it was false: ten
    token_cap_exceeded errors on DCAF8L1 against the largest glue. A
    hard-coded zero would have carried them past assemble_tier_b's refusal,
    which keys on this field."""
    counted = sum(1 for issue in arm["issues"] if issue["severity"] == "error")
    assert arm["errors"] == counted
    assert arm["errors"] == 0, [i for i in arm["issues"]
                                if i["severity"] == "error"][:3]


def test_a_cap_overrun_would_be_reported(arm):
    """Red-green on that field, because the interesting value is non-zero
    and the arm is currently clean."""
    jobs = list(arm["jobs"])
    over = jobs[0]
    cap = int(__import__("nobble").paths.thresholds()["manifest"]["token_cap_tier1"])
    import dataclasses

    inflated = dataclasses.replace(over, tokens=cap + 1, construct="NOT_DECLARED")
    issues = M.validate([inflated])
    assert any(i.severity == "error" and i.code == "token_cap_exceeded"
               for i in issues), issues


def test_the_declared_exception_spans_both_registries():
    """DCAF8L1_WD40 is a Tier B construct marked `exception = true`. The set
    it is checked against was built from the Tier A registry alone, in two
    places, so the marking changed nothing in either (F211)."""
    declared = C.declared_exceptions()
    assert "DCAF8L1_WD40" in declared, sorted(declared)
    assert {"VHL_VCB", "DCAF15_DDB1_DDA1"} <= declared, sorted(declared)
    for source in ("nobble/curate/manifest.py", "tools/preflight.py"):
        text = (ROOT / source).read_text()
        assert "C.declared_exceptions()" in text, source
        assert "item.exception" not in text, (
            f"{source} rebuilds the exception set instead of asking for it"
        )


def test_every_receptor_sequence_has_a_cached_msa():
    """Without this the arm runs single-sequence while the panel it is
    compared against ran with MSAs, which is not a comparison."""
    from nobble.execute import msa

    for name, construct in sorted(T.load().items()):
        for segment in construct.segments:
            assert msa.is_cached(segment.sequence()), name


def test_the_assembled_arm_matches_the_manifest(arm):
    directory = latest_or_absent("tier_b")
    if not directory.exists():
        pytest.skip("the Tier B arm has not been assembled on this checkout")
    summary = json.loads((directory / "campaign.json").read_text())
    assert summary["pairs"] == len(arm["pairs"])
    assert summary["jobs_emitted"] == len(arm["jobs"])
    assert summary["jobs_per_pair"] == arm["jobs_per_pair"]
    queued = sum(1 for line in (directory / "queue.jsonl").read_text().splitlines()
                 if line.strip())
    assert queued == summary["jobs_emitted"]
    assert len(list((directory / "yaml").glob("*.yaml"))) == queued


def test_the_assembler_refuses_an_unassemblable_form(monkeypatch):
    from nobble.execute import campaign as Cm

    monkeypatch.setattr(T, "report", lambda: {"assemblable": False,
                                              "status": "blocked: deliberate"})
    with pytest.raises(RuntimeError, match="not assemblable"):
        Cm.assemble_tier_b(reuse_latest=False)


def test_the_chain_runs_the_arm():
    chain = (ROOT / "tools" / "run_chain.sh").read_text()
    assert "assemble_tier_b" in chain
    assert "newest_complete tier_b" in chain
    assert "tools/preflight.py" in chain
    # Scoring is checked rather than swallowed: the scores are the arm's
    # only output.
    stage = chain.split("4b. Tier B")[1].split("5. publish")[0]
    assert "score.run --campaign" in stage
    assert "rerun the scorer" in stage
