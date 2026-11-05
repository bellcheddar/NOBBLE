"""The F47 correction corrected nothing, on every invocation (F144-F146).

`tools/rerun_pair.py` regenerates one pair's YAMLs from a known-good copy in
another campaign and clears its results so the jobs re-run. The chain runs it
between the main campaign and scoring, and the atlas build refuses to publish
while the pair is stale, so this step is on the publish path.

`_known_good` excluded the campaign being corrected from its own search with
`candidate.parent.parent != exclude`. `ROOT.glob` yields absolute paths and
the chain passes `campaigns/campaign_<stamp>`, which `newest_complete`
prints relative. An absolute path never equals a relative one, so the
campaign was not excluded from its own search, every YAML name was found
twice, "exactly one" was never true, and the function returned None for
every job (F145).

It then dropped the state and results rows anyway, so the fifteen jobs would
have re-run on the hydroxyproline YAML they were meant to replace: twenty
minutes of GPU, the campaign exactly as stale, and the publish still refused
(F146).

And the writes follow the absolute path in each queue row, so `--campaign`
pointed at a copy of a campaign rewrites the original's files (F144). Which
is how anyone would test a destructive tool, and what I was about to do.
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest
from nobble.execute.campaign import latest_or_absent as _newest  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


def _module():
    spec = importlib.util.spec_from_file_location(
        "rerun_pair", ROOT / "tools" / "rerun_pair.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


GOOD = "sequences:\n- protein:\n    id: A\n    sequence: AAA\n"
STALE = GOOD + "    modifications:\n    - position: 1\n      ccd: HYP\n"


def _tree(root: Path, *, reference_campaigns: int = 1):
    """A campaigns/ tree with one stale campaign and N references."""
    (root / "campaigns").mkdir(parents=True)
    target = root / "campaigns" / "campaign_20260101T000000Z"
    (target / "yaml").mkdir(parents=True)
    job = "benchXX_GENE_E3__ternary__conditioned__seed1"
    (target / "yaml" / f"{job}.yaml").write_text(STALE)
    (target / "queue.jsonl").write_text(json.dumps({
        "job_id": job, "pair_id": "benchXX_GENE_E3",
        "yaml": str(target / "yaml" / f"{job}.yaml"),
    }) + "\n")
    (target / "state.jsonl").write_text(json.dumps(
        {"job_id": job, "status": "done"}) + "\n")
    (target / "results.jsonl").write_text(json.dumps(
        {"job_id": job, "pair_id": "benchXX_GENE_E3", "seconds": 1.0}) + "\n")
    (target / "scores.jsonl").write_text("")
    for index in range(reference_campaigns):
        other = root / "campaigns" / f"benchmark_2026010{index + 2}T000000Z"
        (other / "yaml").mkdir(parents=True)
        (other / "yaml" / f"{job}.yaml").write_text(GOOD)
    return target, job


def _apply(module, campaign: Path, monkeypatch) -> int:
    monkeypatch.setattr(sys, "argv",
                        ["rerun_pair.py", "benchXX_GENE_E3",
                         "--campaign", str(campaign), "--apply"])
    return module.main()


def test_a_relative_campaign_path_still_finds_the_reference(tmp_path, monkeypatch):
    """The defect, in the spelling the chain actually uses."""
    module = _module()
    target, job = _tree(tmp_path)
    monkeypatch.setattr(module, "ROOT", tmp_path)
    monkeypatch.chdir(tmp_path)
    relative = Path("campaigns") / target.name
    source = module._known_good(f"{job}.yaml", relative)
    assert source is not None, (
        "a relative --campaign excludes nothing, so the campaign's own stale "
        "copy counts as a second candidate and the reference is never found"
    )
    assert source.read_text() == GOOD


def test_every_spelling_of_the_same_path_agrees(tmp_path, monkeypatch):
    module = _module()
    target, job = _tree(tmp_path)
    monkeypatch.setattr(module, "ROOT", tmp_path)
    monkeypatch.chdir(tmp_path)
    found = {
        str(module._known_good(f"{job}.yaml", Path(spelling)))
        for spelling in (
            str(target),
            f"campaigns/{target.name}",
            f"./campaigns/{target.name}",
        )
    }
    assert len(found) == 1, f"the spellings disagree: {found}"


def test_two_references_are_still_refused(tmp_path, monkeypatch):
    """The rule the fix must not loosen.

    Two copies that could disagree cannot both be the reference, and
    silently taking the first is how F41 and F42 happened.
    """
    module = _module()
    target, job = _tree(tmp_path, reference_campaigns=2)
    monkeypatch.setattr(module, "ROOT", tmp_path)
    monkeypatch.chdir(tmp_path)
    assert module._known_good(f"{job}.yaml", target) is None


def test_the_correction_actually_replaces_the_yaml(tmp_path, monkeypatch):
    module = _module()
    target, job = _tree(tmp_path)
    monkeypatch.setattr(module, "ROOT", tmp_path)
    monkeypatch.chdir(tmp_path)
    assert _apply(module, target, monkeypatch) == 0
    written = (target / "yaml" / f"{job}.yaml").read_text()
    assert written == GOOD, "the stale YAML was not replaced"
    assert "HYP" not in written
    backup = target / "yaml" / f"{job}.yaml.bak"
    assert backup.exists() and "HYP" in backup.read_text(), (
        "the original was overwritten with no backup"
    )


def test_the_results_are_cleared_only_once_the_yaml_is_verified(tmp_path, monkeypatch):
    module = _module()
    target, job = _tree(tmp_path)
    monkeypatch.setattr(module, "ROOT", tmp_path)
    monkeypatch.chdir(tmp_path)
    _apply(module, target, monkeypatch)
    assert (target / "state.jsonl").read_text().strip() == "", (
        "the state row survived, so run_queue.sh will skip the job"
    )


def test_it_refuses_to_clear_results_it_could_not_verify(tmp_path, monkeypatch):
    """F146: clearing results without correcting the input repeats it."""
    module = _module()
    target, job = _tree(tmp_path, reference_campaigns=0)
    monkeypatch.setattr(module, "ROOT", tmp_path)
    monkeypatch.chdir(tmp_path)
    before = (target / "state.jsonl").read_text()
    assert _apply(module, target, monkeypatch) == 2
    assert (target / "state.jsonl").read_text() == before, (
        "the results were cleared although no YAML was corrected, so the "
        "jobs would re-run on the same input"
    )
    assert "HYP" in (target / "yaml" / f"{job}.yaml").read_text()


def test_it_refuses_a_queue_whose_paths_leave_the_campaign(tmp_path, monkeypatch):
    """F144: --campaign scopes the read and not the writes.

    Arranged so the containment check is the only thing that can stop the
    write. The first version of this put the queue's target inside
    `campaigns/`, which gave `_known_good` two candidates, so F146's
    refusal fired first and the test passed with the containment check
    disabled: it asserted the right outcome for the wrong reason, and the
    mutation sweep said so.

    Here the target sits outside `campaigns/` altogether, which is what an
    archived or relocated campaign looks like, so exactly one reference
    exists and `_known_good` succeeds. Then the only reason the original is
    not rewritten is that it is outside the campaign named on the command
    line.
    """
    module = _module()
    monkeypatch.setattr(module, "ROOT", tmp_path)
    monkeypatch.chdir(tmp_path)
    job = "benchXX_GENE_E3__ternary__conditioned__seed1"

    # The file the queue names, outside campaigns/ and so outside any
    # campaign directory.
    archived = tmp_path / "archive" / "yaml"
    archived.mkdir(parents=True)
    victim = archived / f"{job}.yaml"
    victim.write_text(STALE)

    # Exactly one reference, so _known_good returns a source.
    reference = tmp_path / "campaigns" / "benchmark_20260102T000000Z" / "yaml"
    reference.mkdir(parents=True)
    (reference / f"{job}.yaml").write_text(GOOD)

    campaign = tmp_path / "campaigns" / "campaign_20260101T000000Z"
    campaign.mkdir(parents=True)
    (campaign / "queue.jsonl").write_text(json.dumps({
        "job_id": job, "pair_id": "benchXX_GENE_E3", "yaml": str(victim),
    }) + "\n")
    (campaign / "state.jsonl").write_text(json.dumps(
        {"job_id": job, "status": "done"}) + "\n")
    (campaign / "results.jsonl").write_text("")
    (campaign / "scores.jsonl").write_text("")

    assert module._known_good(f"{job}.yaml", campaign) is not None, (
        "the fixture does not reach the containment check"
    )
    assert _apply(module, campaign, monkeypatch) == 2
    assert victim.read_text() == STALE, (
        "a YAML outside the campaign named on the command line was rewritten"
    )
    assert (campaign / "state.jsonl").read_text().strip(), (
        "the results were cleared for a campaign it refused to correct"
    )


def test_the_chain_handles_a_refusal():
    chain = (ROOT / "tools" / "run_chain.sh").read_text()
    section = chain[chain.index("correcting the F47 pair"):]
    section = section[:section.index("scoring, validating")]
    assert "else" in section and "refuses" in section, (
        "the chain does not say what a failed correction means for the "
        "publish, so a refusal would scroll past"
    )


def test_the_live_correction_has_exactly_one_reference():
    """The precondition F145 restored, checked on the real layout (F169).

    `_known_good` returns a reference only when exactly one other campaign
    holds the same job's YAML. On this checkout that holds for all fifteen of
    `bench02_BRD4_VHL`'s files: the benchmark campaign has them, the
    corrected campaign does not because it prefixes its jobs `corr01_` rather
    than `bench01_`, and the two scratch directories hold no `yaml/` at all.

    Fragile in a nameable way. A future campaign that reused the `bench`
    prefix would give three copies and the correction would find no
    reference. F146 makes that a refusal rather than a silent no-op, so the
    failure is visible, and this says so before the chain does.
    """
    module = _module()
    main = _newest("campaign")
    if not (main / "queue.jsonl").exists():
        return

    jobs = [json.loads(line) for line
            in (main / "queue.jsonl").read_text().splitlines() if line.strip()]
    pair = [job for job in jobs if job["pair_id"] == "bench02_BRD4_VHL"]
    if not pair:
        return
    unresolved = []
    for job in pair:
        name = Path(job["yaml"]).name
        if module._known_good(name, main) is None:
            holders = sorted(
                path.parent.parent.name
                for path in ROOT.glob(f"campaigns/*/yaml/{name}"))
            unresolved.append(f"{name} held by {holders}")
    assert not unresolved, (
        "the F47 correction has no unambiguous reference for these, so it "
        f"will refuse when the chain reaches it: {unresolved[:3]}"
    )
    assert len(pair) == 15, f"{len(pair)} jobs for the pair, expected 15"
