"""What was folded, against what the YAML asks for (F219).

Every stale-input check this project had read the YAML. Boltz caches the
featurised input in `boltz_results_<job>/processed/` and reuses it on a
re-run, so on 6 November `tools/rerun_pair.py` replaced fifteen YAMLs,
cleared their results, and the re-run folded the hydroxyproline again from
cache. The campaign then passed every stale-input check it had, and the atlas
built for the first time in two days because the guard had been satisfied
rather than because the defect was gone.

The evidence that settled it is what these tests reproduce: the cached
`processed/structures/*.npz` holds chain P residue 1 as HYP while the
corrected YAML says PRO.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import stale_featurisation as SF  # noqa: E402


def _npz(path: Path, chains: dict[str, list[str]]) -> None:
    """A minimal Boltz-shaped processed structure."""
    residue_names, chain_rows, index = [], [], 0
    for name, residues in chains.items():
        chain_rows.append((name.encode(), index, len(residues)))
        residue_names.extend(residues)
        index += len(residues)
    residues_array = np.array([(n.encode(),) for n in residue_names],
                              dtype=[("name", "S8")])
    chains_array = np.array(chain_rows,
                            dtype=[("name", "S8"), ("res_idx", "i4"),
                                   ("res_num", "i4")])
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez(path, residues=residues_array, chains=chains_array)


def _job(campaign: Path, job_id: str, *, yaml_text: str,
         folded: dict[str, list[str]]) -> None:
    yaml_path = campaign / "yaml" / f"{job_id}.yaml"
    yaml_path.parent.mkdir(parents=True, exist_ok=True)
    yaml_path.write_text(yaml_text)
    with (campaign / "queue.jsonl").open("a") as queue:
        queue.write(json.dumps({"job_id": job_id,
                                "yaml": str(yaml_path)}) + "\n")
    _npz(campaign / "outputs" / job_id
         / f"boltz_results_{job_id}" / "processed" / "structures"
         / f"{job_id}.npz", folded)


PLAIN = """sequences:
- protein:
    id: P
    sequence: PVDVEALGLHDYCDI
"""

MODIFIED = """sequences:
- protein:
    id: P
    sequence: PVDVEALGLHDYCDI
    modifications:
    - position: 1
      ccd: HYP
"""


def test_a_cache_predating_the_correction_is_caught(tmp_path):
    """The live case, reproduced: YAML says PRO, the cache folded HYP."""
    campaign = tmp_path / "campaign_x"
    campaign.mkdir()
    _job(campaign, "j1", yaml_text=PLAIN, folded={"P": ["HYP", "VAL"]})
    found = SF.disagreements(campaign)
    assert len(found) == 1, found
    assert found[0]["folded"] == "HYP"
    assert found[0]["yaml_asks"] == "unmodified PRO"
    assert found[0]["reading"] == "the cache predates the YAML"


def test_agreement_is_silent(tmp_path):
    campaign = tmp_path / "campaign_x"
    campaign.mkdir()
    _job(campaign, "j1", yaml_text=PLAIN, folded={"P": ["PRO", "VAL"]})
    assert SF.disagreements(campaign) == []


def test_a_modification_the_yaml_asks_for_and_got_is_silent(tmp_path):
    """The other direction: asking for HYP and folding HYP is correct."""
    campaign = tmp_path / "campaign_x"
    campaign.mkdir()
    _job(campaign, "j1", yaml_text=MODIFIED, folded={"P": ["HYP", "VAL"]})
    assert SF.disagreements(campaign) == []


def test_a_modification_the_yaml_asks_for_and_did_not_get_is_caught(tmp_path):
    """The case that would mean Boltz dropped the block, which is what I
    wrongly concluded from the bit-identical ipTM before reading the cache."""
    campaign = tmp_path / "campaign_x"
    campaign.mkdir()
    _job(campaign, "j1", yaml_text=MODIFIED, folded={"P": ["PRO", "VAL"]})
    found = SF.disagreements(campaign)
    assert len(found) == 1, found
    assert found[0]["reading"] == "the modification was not applied"


def test_only_the_parent_codes_it_knows_are_read_as_modified(tmp_path):
    """An ordinary residue is not a modification, and a ligand CCD is not
    one either: chain L's `759` must not be reported."""
    campaign = tmp_path / "campaign_x"
    campaign.mkdir()
    _job(campaign, "j1", yaml_text=PLAIN,
         folded={"P": ["PRO"], "L": ["759"], "A": ["ARG"]})
    assert SF.disagreements(campaign) == []


def test_a_job_with_no_cache_is_not_a_disagreement(tmp_path):
    """A job that has not run yet says nothing about what was folded."""
    campaign = tmp_path / "campaign_x"
    campaign.mkdir()
    (campaign / "yaml").mkdir()
    (campaign / "yaml" / "j1.yaml").write_text(PLAIN)
    (campaign / "queue.jsonl").write_text(json.dumps(
        {"job_id": "j1", "yaml": str(campaign / "yaml" / "j1.yaml")}) + "\n")
    assert SF.disagreements(campaign) == []
    assert SF.cached_first_residues(campaign / "outputs" / "j1") is None


def test_the_live_campaign_reports_whatever_is_stale(tmp_path):
    """Not a synthetic: the state that is actually on disk.

    The campaign is resolved rather than named, because a test that pins a
    directory stops being a test of the project the moment that campaign is
    superseded.
    """
    found_campaigns = sorted((ROOT / "campaigns").glob("campaign_*/queue.jsonl"))
    if not found_campaigns:
        pytest.skip("no main campaign on this checkout")
    campaign = found_campaigns[-1].parent
    found = SF.disagreements(campaign)
    if not found:
        pytest.skip("the F47 correction has been re-run against the cache, "
                    "so there is nothing stale left to find")
    # Whatever is stale, the report has to name a job, a chain, what the
    # YAML asks for and what was folded. Asserting which pair is stale would
    # pin today's defect rather than the instrument.
    for row in found:
        assert row["job_id"] and row["chain"]
        assert row["yaml_asks"] != row["folded"]
        assert row["reading"] in ("the cache predates the YAML",
                                  "the modification was not applied")


def test_the_build_refuses_on_a_stale_featurisation():
    source = (ROOT / "deploy" / "build_atlas.py").read_text()
    assert "featurisation_check.disagreements(campaign)" in source
    assert "F219" in source
    # After the YAML check, because the YAML check is the cheaper one and
    # because a YAML that is itself stale makes this comparison meaningless.
    assert source.index("stale_inputs(campaign)") < \
        source.index("featurisation_check.disagreements(campaign)")


def test_rerun_pair_removes_the_cached_output():
    """The fix, pinned where it has to happen: after the rows are dropped and
    before the tool tells anyone to re-run."""
    source = (ROOT / "tools" / "rerun_pair.py").read_text()
    assert "shutil.rmtree(output)" in source
    drop = source.index('for name in ("state.jsonl", "results.jsonl"')
    remove = source.index("shutil.rmtree(output)")
    advise = source.index("Now run: bash tools/run_queue.sh")
    assert drop < remove < advise, (
        "the cached output is not removed between dropping the rows and "
        "advising the re-run"
    )


def test_the_runner_clears_a_job_output_before_running_it():
    """The fix at the point where it is knowable (F219).

    tools/rerun_pair.py was the path that exposed the cache, not the only one
    that reaches it: anything that edits a YAML and re-runs the job inherits
    the old featurisation. The runner is the one place that knows it is about
    to run this job against this YAML.
    """
    source = (ROOT / "nobble" / "execute" / "runner.py").read_text()
    assert "shutil.rmtree(output_dir)" in source, (
        "the runner reuses a job's output directory, so Boltz reuses its "
        "cached featurisation"
    )
    clear = source.index("shutil.rmtree(output_dir)")
    run = source.index("status, returncode, stdout, stderr = _run_boltz(")
    assert clear < run, "the output is cleared after Boltz has already run"
    # Once per job, not once per attempt: a retry runs the same command
    # against the same YAML and must not pay to featurise it again.
    loop = source.index("while attempts <= RETRIES:")
    assert clear < loop, "the output is cleared inside the retry loop"


def test_clearing_is_not_an_alternative_to_the_check():
    """Both, deliberately.

    The runner clearing its own output fixes every future run. It does
    nothing for a campaign already on disk whose poses were folded from an
    input since replaced, which is the state F219 found, so the build still
    has to refuse on the comparison.
    """
    build = (ROOT / "deploy" / "build_atlas.py").read_text()
    assert "featurisation_check.disagreements(campaign)" in build


def test_the_runner_actually_removes_the_stale_cache(tmp_path, monkeypatch):
    """Behaviour, not the source text.

    The assertions above read runner.py, which pins that the call is there and
    in the right place and would keep passing if `shutil.rmtree` were handed
    the wrong path. This runs `run_job` against a stubbed Boltz and looks at
    the directory afterwards.
    """
    from nobble.execute import runner

    campaign = tmp_path / "campaign_x"
    job_id = "pair__ternary__conditioned__seed1"
    output = campaign / "outputs" / job_id
    stale = output / f"boltz_results_{job_id}" / "processed" / "structures"
    stale.mkdir(parents=True)
    (stale / f"{job_id}.npz").write_bytes(b"the previous featurisation")
    witness = output / "left_from_the_last_run.txt"
    witness.write_text("still here")

    seen = {}

    def fake_boltz(command, env, timeout):
        # Called after the clear, so the directory state here is what Boltz
        # itself would find.
        seen["cache_present"] = (stale / f"{job_id}.npz").exists()
        seen["witness_present"] = witness.exists()
        return "ok", 0, "", ""

    monkeypatch.setattr(runner, "_run_boltz", fake_boltz)
    monkeypatch.setattr(runner, "boltz_environment", lambda: {})
    monkeypatch.setattr(runner, "_read_outputs",
                        lambda directory, name: (None, None, None,
                                                 "stubbed: no outputs"))

    job = {"job_id": job_id, "yaml": str(tmp_path / "pair.yaml"),
           "tokens": 100, "seed": 1}
    settings = {"recycles": 3, "diffusion_samples": 1, "device": "cpu",
                "potentials": False, "job_timeout_seconds": 60}
    runner.run_job(job, campaign, settings)

    assert seen, "the stubbed Boltz was never reached"
    assert seen["cache_present"] is False, (
        "Boltz was run with the previous featurisation still in place"
    )
    assert seen["witness_present"] is False, (
        "the output directory was not cleared, only part of it"
    )
    assert output.exists(), "the output directory was removed and not recreated"


def _campaign_with_cache(tmp_path, *, keys=("chains", "residues"),
                         write_npz=True, run=True):
    """A one-job campaign whose cache can be made absent or unreadable."""
    import numpy as np

    campaign = tmp_path / "campaign_synthetic"
    (campaign / "yaml").mkdir(parents=True)
    job = "pairX__ternary__unconstrained__seed1"
    yaml_path = campaign / "yaml" / f"{job}.yaml"
    yaml_path.write_text(
        "version: 1\nsequences:\n- protein:\n    id: P\n    sequence: PVD\n")
    (campaign / "queue.jsonl").write_text(json.dumps({
        "job_id": job, "pair_id": "pairX", "yaml": str(yaml_path)}) + "\n")

    if run:
        cache = campaign / "outputs" / job / "boltz_results_x" / "processed" / "structures"
        cache.mkdir(parents=True)
        if write_npz:
            arrays = {}
            if "chains" in keys:
                arrays["chains"] = np.array(
                    [("P", 0)], dtype=[("name", "S8"), ("res_idx", "i4")])
            if "residues" in keys:
                arrays["residues"] = np.array(
                    [("PRO",)], dtype=[("name", "S8")])
            if not arrays:
                arrays["something_else"] = np.array([1])
            np.savez(cache / "s.npz", **arrays)
    return campaign, job


def test_a_job_that_ran_with_no_cache_is_counted_blind(tmp_path):
    """Not agreement. The job ran and there was nothing to compare."""
    campaign, _ = _campaign_with_cache(tmp_path, write_npz=False)
    seen = SF.coverage(campaign)
    assert seen["no_cache"] == 1, seen
    assert seen["checked"] == 0, seen
    assert seen["blind"] == 1, seen
    assert SF.disagreements(campaign) == []


def test_a_cache_without_the_expected_arrays_is_counted_blind(tmp_path):
    """What a change in Boltz's cache format would look like.

    Every job in the campaign would return None, `disagreements` would be
    empty, and the guard the atlas build refuses on would report success over
    a campaign it had not compared. F219 re-enabled by a passing check.
    """
    campaign, _ = _campaign_with_cache(tmp_path, keys=())
    seen = SF.coverage(campaign)
    assert seen["unreadable_cache"] == 1, seen
    assert seen["checked"] == 0, seen
    assert seen["blind"] == 1, seen
    assert SF.disagreements(campaign) == []


def test_an_unrun_job_is_not_blind(tmp_path):
    """The honest skip: no output directory means it has not run."""
    campaign, _ = _campaign_with_cache(tmp_path, run=False)
    seen = SF.coverage(campaign)
    assert seen["no_output"] == 1, seen
    assert seen["blind"] == 0, seen


def test_a_readable_cache_is_checked(tmp_path):
    campaign, _ = _campaign_with_cache(tmp_path)
    seen = SF.coverage(campaign)
    assert seen["checked"] == 1, seen
    assert seen["blind"] == 0, seen
    assert seen["queued"] == 1, seen


def test_the_live_campaigns_are_fully_covered():
    """The refusal added to the build costs nothing today, and this says so.

    If this starts failing, the guard has gone blind somewhere and the build
    will refuse, which is the intended behaviour and not a regression here.
    """
    from nobble import paths as nobble_paths

    for campaign in sorted(nobble_paths.CAMPAIGNS.glob("*")):
        if not (campaign / "queue.jsonl").exists():
            continue
        seen = SF.coverage(campaign)
        assert seen["blind"] == 0, (campaign.name, seen)
        assert seen["checked"] + seen["no_output"] == seen["queued"], (
            campaign.name, seen)
