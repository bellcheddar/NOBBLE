"""The harness that mutation checks have to go through.

`tools/mutate.py` was built after a sweep left a mutation in the working
tree. Two later lapses came from not using it, and both were hand-rolled
shell loops that mutated a file, ran pytest and restored with a trap.

One removed the atlas build's stale-input refusal, to confirm the test
caught its removal; the test then ran the real build and rebuilt the
published atlas from a campaign with 54 of 2360 jobs scored. The other
rewrote a live campaign's `queue.jsonl` while the runner was reading it.
Neither did lasting harm, because the atlas is tracked and the queue came
back byte-identical, but both were luck rather than method.

They were hand-rolled because the harness only ran a fixed list, so a
one-off was easier in the shell than as an entry here. Convenience is the
whole reason the safe path was bypassed, so `--file/--find/--replace` is
the first fix.

The second is the lesson both lapses share. A mutation removes a safety on
purpose, so the tests run under it can reach things no test should touch,
and which file was edited does not predict what gets written. Live state is
fingerprinted before and after and any change is reported (F66).
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import mutate  # noqa: E402

PYTHON = str(ROOT.parent / "BINMAN" / ".pixi" / "envs" / "default" / "bin" / "python")


def _run(*arguments):
    return subprocess.run([PYTHON, "tools/mutate.py", *arguments],
                          cwd=str(ROOT), capture_output=True, text=True,
                          timeout=600)


def _needs_clean(completed, path: str):
    """Skip rather than fail when the harness refuses a dirty baseline.

    The harness will not start on a file with uncommitted changes, which is
    correct: it reads that file as its baseline and a leftover mutation
    would be carried forward. But a test that drives the success path then
    fails for anyone with work in progress, which is most of the time
    during development. The refusal is the harness working, so it is a skip
    and it names the file.
    """
    if completed.returncode == 2 and "refusing to start" in completed.stderr:
        pytest.skip(f"{path} has uncommitted changes, so the harness "
                    "refuses to use it as a baseline")


def test_a_live_campaign_file_may_not_be_mutated():
    """The second lapse, as a refusal."""
    reason = mutate._refuse_protected(
        "campaigns/campaign_20261104T004632Z/queue.jsonl")
    assert reason == "live state, not source"


def test_every_protected_kind_is_refused():
    for relative in ("campaigns/c/results.jsonl", "campaigns/c/state.jsonl",
                     "campaigns/c/queue_tier2.jsonl", "campaigns/c/scores.jsonl",
                     "campaigns/c/campaign.json", "deploy/atlas/ATLAS.json",
                     "data/throughput.json"):
        assert mutate._refuse_protected(relative), f"{relative} was allowed"


def test_source_files_are_allowed():
    for relative in ("nobble/validate/inputs.py", "tools/preflight.py",
                     "deploy/build_atlas.py", "qc/qc.mjs"):
        assert mutate._refuse_protected(relative) is None, relative


def test_test_files_are_mutable():
    """Several of this project's checks live in test files, so verifying
    one still fires means mutating where it lives."""
    assert mutate._refuse_protected("tests/test_house_style.py") is None


def test_documents_and_configuration_are_not_mutable():
    """Not because editing them is dangerous but because a mutation there
    is not testing code, and the sweep reports "not caught" for a change no
    test could have been expected to notice."""
    assert mutate._refuse_protected("PROGRESS.md")
    assert mutate._refuse_protected("config/thresholds.toml")


def test_nothing_outside_the_project_is_mutable():
    assert mutate._refuse_protected("/etc/hosts")
    assert mutate._refuse_protected("../BINMAN/nobble/x.py")


def test_the_refusal_happens_before_any_file_is_touched():
    completed = _run("--file", "campaigns/x/queue.jsonl",
                     "--find", "a", "--replace", "b")
    assert completed.returncode == 2
    assert "live state" in completed.stderr
    assert "watching" not in completed.stdout, (
        "it started the run before refusing"
    )


def test_live_state_changes_are_detected(monkeypatch, tmp_path):
    """The check both lapses needed. Whatever the mutation was, a protected
    file that moves between the two fingerprints is reported."""
    monkeypatch.setattr(mutate, "ROOT", tmp_path)
    atlas = tmp_path / "deploy" / "atlas"
    atlas.mkdir(parents=True)
    (atlas / "ATLAS.json").write_text('{"campaign": "benchmark"}')

    before = mutate._fingerprint()
    assert "deploy/atlas/ATLAS.json" in before
    assert mutate._live_state_changes(before) == []

    (atlas / "ATLAS.json").write_text('{"campaign": "rebuilt from 54 of 2360"}')
    changed = mutate._live_state_changes(before)
    assert len(changed) == 1
    assert "deploy/atlas/ATLAS.json" in changed[0]


def test_a_protected_file_appearing_is_also_a_change(monkeypatch, tmp_path):
    """A build that writes a file which was not there is as much a change as
    one that rewrites it, and `--delete` on the published atlas means a
    missing file matters too."""
    monkeypatch.setattr(mutate, "ROOT", tmp_path)
    (tmp_path / "deploy" / "atlas").mkdir(parents=True)
    before = mutate._fingerprint()
    assert before == {}
    (tmp_path / "deploy" / "atlas" / "campaign.json").write_text("{}")
    changed = mutate._live_state_changes(before)
    assert len(changed) == 1
    assert "absent ->" in changed[0]


def test_a_protected_file_disappearing_is_a_change(monkeypatch, tmp_path):
    monkeypatch.setattr(mutate, "ROOT", tmp_path)
    (tmp_path / "deploy" / "atlas").mkdir(parents=True)
    target = tmp_path / "deploy" / "atlas" / "campaign.json"
    target.write_text("{}")
    before = mutate._fingerprint()
    target.unlink()
    changed = mutate._live_state_changes(before)
    assert len(changed) == 1
    assert "-> absent" in changed[0]


def test_an_ad_hoc_mutation_needs_all_three_arguments():
    completed = _run("--file", "nobble/validate/inputs.py")
    assert completed.returncode == 2
    assert "go together" in completed.stderr


def test_an_ad_hoc_mutation_runs_and_restores(tmp_path):
    """End to end on real source, with the suite scoped to one file so it
    is quick. The tree being clean afterwards is the part that matters."""
    target = ROOT / "nobble" / "validate" / "inputs.py"
    before = target.read_text()
    completed = _run("--file", "nobble/validate/inputs.py",
                     "--find", "if sorted(on_disk) != sorted(wanted):",
                     "--replace", "if False:",
                     "--tests", "tests/test_stale_inputs.py")
    assert target.read_text() == before, "the mutation was left behind"
    _needs_clean(completed, "nobble/validate/inputs.py")
    assert "caught" in completed.stdout, completed.stdout[-500:]
    assert "watching" in completed.stdout
    assert completed.returncode == 0, completed.stdout[-800:]


def test_the_fixed_list_still_lists():
    completed = _run("--list")
    assert completed.returncode == 0
    assert "nobble/" in completed.stdout


def test_a_skipped_mutation_is_not_counted_as_caught():
    """The harness reported a false all-clear.

    A mutation whose anchor does not appear exactly once is skipped: the
    file is never changed and the suite is never run. That `continue` fell
    through to a summary computed as `len(chosen) - missed`, and `missed`
    was only incremented for a mutation that actually ran. So a sweep whose
    anchors had all gone stale printed "N of N caught" and exited zero.

    That is a false all-clear from the tool whose entire purpose is to find
    false all-clears, and it is the exact shape it exists to catch: correct
    and incorrect behaviour producing the same observable result. Found when
    an identical find/replace pair reported itself caught (F84).
    """
    completed = _run("--file", "nobble/score/metrics.py",
                     "--find", "PAIR_LEVEL_FIELDS",
                     "--replace", "PAIR_LEVEL_FIELDS",
                     "--tests", "tests/test_numeric_rule.py")
    _needs_clean(completed, "nobble/score/metrics.py")
    assert "SKIPPED" in completed.stdout, completed.stdout
    assert "of 0 attempted caught" in completed.stdout, (
        "a skipped mutation is still being counted among the attempts"
    )
    assert "nothing was tested" in completed.stdout
    assert completed.returncode != 0, (
        "a sweep that tested nothing exited zero, which is the all-clear it "
        "has no basis for"
    )


def test_a_real_mutation_still_reports_and_exits_cleanly():
    """The other side: a mutation that runs and is caught must still be a
    success, or the fix above would make every sweep look broken."""
    completed = _run("--file", "nobble/validate/layers.py",
                     "--find", 'ROC_ARM = "sievers_zf"',
                     "--replace", 'ROC_ARM = "benchmark"',
                     "--tests", "tests/test_queue_priority.py")
    _needs_clean(completed, "nobble/validate/layers.py")
    assert "1 of 1 attempted caught" in completed.stdout, completed.stdout
    assert "SKIPPED" not in completed.stdout
    assert completed.returncode == 0, completed.stdout[-600:]
