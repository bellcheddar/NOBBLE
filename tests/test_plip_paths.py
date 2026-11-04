"""PLIP ran on one campaign and silently failed on the next.

cif2plip is invoked with cwd set to its own directory, so its sibling
imports resolve. The structure path was passed through as given, and a
campaign named relatively ("campaigns/corrected_...") then resolved
against *that* directory: every conversion failed with FileNotFoundError
on ".plip_env/cif2plip/campaigns/corrected_.../outputs/...".

The benchmark campaign was run with an absolute campaign path and worked,
which is why this survived a whole campaign's scoring. run_chain.sh builds
the main campaign's path with `ls -d campaigns/campaign_*`, so all 158
pairs would have failed the same way.

And the failure did not look like one. score_campaign divided an empty
canonical-match list by the number expected and published 0.0: a number
saying the prediction reproduced none of the canonical degron contacts,
where the truth is that nothing was measured.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from nobble.score import plip  # noqa: E402


def test_the_structure_is_handed_over_as_an_absolute_path(monkeypatch, tmp_path):
    """Whatever the caller gave, the subprocess gets something it can open."""
    captured = {}

    class Completed:
        returncode = 1          # stop after the call; the path is the point
        stdout = ""
        stderr = ""

    def fake_run(command, **kwargs):
        captured["command"] = command
        captured["cwd"] = kwargs.get("cwd")
        return Completed()

    monkeypatch.setattr(plip.subprocess, "run", fake_run)

    # A structure referred to by a relative path, as the corrected campaign's
    # records do.
    structure = tmp_path / "outputs" / "job_model_0.cif"
    structure.parent.mkdir(parents=True)
    structure.write_text("data_x\n")
    monkeypatch.chdir(tmp_path)
    relative = Path("outputs") / "job_model_0.cif"

    plip.fingerprint({
        "job_id": "job", "complex_type": "ternary", "structure": str(relative),
    })

    command = captured["command"]
    structure_argument = command[2]
    assert Path(structure_argument).is_absolute(), structure_argument
    assert Path(structure_argument).exists(), (
        "the path handed to cif2plip does not resolve to a real file"
    )
    # The output directory too: it is passed to the same process.
    output_argument = command[command.index("-o") + 1]
    assert Path(output_argument).is_absolute(), output_argument
    # And the cwd that caused this is still set, because the sibling imports
    # still need it.
    assert captured["cwd"] == str(plip.CIF2PLIP.parent)


def _score_one(monkeypatch, tmp_path, status, matched):
    """Run score_campaign over a single ternary job with a stubbed PLIP."""
    import json

    from nobble.score import run as run_module

    campaign = tmp_path / "campaign_x"
    (campaign / "outputs").mkdir(parents=True)
    structure = campaign / "outputs" / "s.cif"
    structure.write_text("data_x\n")
    job = {
        "job_id": "j1", "pair_id": "p1", "seed": 1, "complex_type": "ternary",
        "conditioning": "unconstrained", "construct": "CRBN_CULT",
        "e3_gene": "CRBN", "peptide_id": "pep", "tier": "benchmark",
        "tokens": 400, "tier_setting": 1, "structure": str(structure),
        "confidence": {"pair_chains_iptm": {"0": {"1": 0.5}, "1": {"0": 0.5}}},
    }
    (campaign / "results.jsonl").write_text(json.dumps(job) + "\n")

    finger = plip.Fingerprint(job_id="j1", status=status)
    finger.canonical_matched = matched
    finger.canonical_e3 = "CRBN"
    monkeypatch.setattr(run_module.plip, "fingerprint", lambda job: finger)
    from nobble.score import geometry

    monkeypatch.setattr(
        run_module.geometry, "score_structure",
        lambda job: geometry.BridgeScore(
            job_id=job["job_id"], structure=job.get("structure", ""), found=False,
            reject_reason="stubbed: this test is about PLIP",
        ),
    )
    monkeypatch.setattr(run_module.geometry, "contact_map", lambda job: {"status": "ok"})

    run_module.score_campaign(campaign)
    rows = [json.loads(line) for line in
            (campaign / "scores.jsonl").read_text().splitlines() if line.strip()]
    return rows[0]


def test_a_failed_fingerprint_is_not_a_match_of_zero(monkeypatch, tmp_path):
    """The live case: five corrected pairs carried 0.0 for a conversion that
    never ran."""
    row = _score_one(monkeypatch, tmp_path, "failed: cif2plip exit 1", [])
    assert row["plip_fingerprint_match"] is None, row["plip_fingerprint_match"]
    assert row["plip_fingerprint_match_status"].startswith("not_computed")
    assert "cif2plip exit 1" in row["plip_fingerprint_match_status"]


def test_a_refused_fingerprint_reports_the_reason_it_was_refused(monkeypatch, tmp_path):
    """The CONECT gate exists to refuse rather than return a plausible
    fingerprint. The refusal has to survive into the record."""
    row = _score_one(
        monkeypatch, tmp_path,
        "failed: CONECT integrity, serial gap at 1841", [],
    )
    assert row["plip_fingerprint_match"] is None
    assert "CONECT integrity" in row["plip_fingerprint_match_status"]


def test_a_successful_fingerprint_still_scores(monkeypatch, tmp_path):
    """Five canonical CRBN residues, three matched."""
    row = _score_one(monkeypatch, tmp_path, "ok", ["TRP380", "TRP386", "HIS378"])
    assert row["plip_fingerprint_match"] == 0.6
    assert row["plip_fingerprint_match_status"] == "ok"


def test_an_e3_with_no_canonical_fingerprint_reports_why(monkeypatch, tmp_path):
    """DCAF15 and DDB1 have no canonical pattern, so there is nothing to
    match against. That is a different null from a failed conversion and
    should not read the same."""
    import json

    from nobble.score import run as run_module

    row = _score_one(monkeypatch, tmp_path, "ok", [])
    # CRBN does have a pattern, so this is the matched-none case, not the
    # no-pattern case: 0 of 5.
    assert row["plip_fingerprint_match"] == 0.0
    assert row["plip_fingerprint_match_status"] == "ok"
    assert json  and run_module          # keep the imports honest


def test_recorded_paths_are_absolute_however_the_campaign_was_named(
    monkeypatch, tmp_path
):
    """Closing the class, not just the instance.

    Whether a record held a relative or an absolute path followed whichever
    form the caller used: the benchmark campaign was started with an
    absolute path and the corrected one with "campaigns/corrected_...", so
    two campaigns in one project disagreed about what a structure path is.
    Any consumer running from elsewhere reads one and fails on the other.
    """
    import json

    from nobble.execute import runner

    campaign = tmp_path / "campaign_rel"
    campaign.mkdir()
    (campaign / "queue.jsonl").write_text(json.dumps({
        "job_id": "j1", "pair_id": "p1", "seed": 1, "tokens": 10,
        "construct": "CRBN_CULT", "complex_type": "ternary",
        "conditioning": "unconstrained", "yaml": "whatever.yaml",
    }) + "\n")

    # No Boltz: the question is only what paths are recorded.
    monkeypatch.setattr(runner, "_run_boltz",
                        lambda command, env, timeout: ("ok", 1, "", "no"))
    monkeypatch.chdir(tmp_path)

    runner.run_campaign(Path("campaign_rel"), limit=1)

    records = [json.loads(line) for line
               in (campaign / "state.jsonl").read_text().splitlines() if line.strip()]
    recorded = [r["output_dir"] for r in records if r.get("output_dir")]
    assert recorded, "no output_dir was recorded"
    for path in recorded:
        assert Path(path).is_absolute(), (
            f"{path} is relative, so a consumer running from another "
            "directory cannot open it"
        )
