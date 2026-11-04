"""A kill mid-append must not stop the next stage.

`results.jsonl` and `state.jsonl` are appended one row at a time by a runner
that may be killed at any moment, which the project states as a rule: assume
the process can be killed at any moment. `scores.jsonl` is written in one
pass, and a kill truncates it. In all three, the last line can be a fragment
and every line before it is good.

The runner's `completed()` has always known this, with the comment "a torn
final line from a kill mid-write: ignore it and re-run that job". Seven other
readers of those same files built their rows in a list comprehension with no
guard, so a kill at the wrong moment made the next stage raise
`JSONDecodeError` rather than process the 2,359 complete records. Scoring,
validation, the weight fit, the tier-2 selection and the throughput
measurement were all in that set.

`queue.jsonl` and the library manifest are deliberately strict. They are
written once, before anything runs, and nothing appends to them: a line that
will not parse there is a damaged input, not a torn tail, and skipping it
would run 2,359 of 2,360 jobs without saying so (F111).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from nobble import paths  # noqa: E402

GOOD = {"job_id": "a", "pair_id": "p", "status": "done", "seconds": 1.0,
        "tokens": 10}


def _torn(tmp_path: Path, name="results.jsonl", rows=3) -> Path:
    path = tmp_path / name
    path.write_text(
        "".join(json.dumps({**GOOD, "job_id": f"j{index}"}) + "\n"
                for index in range(rows))
        + '{"job_id": "j9", "pair_i'
    )
    return path


def test_the_tolerant_reader_keeps_everything_before_the_tear(tmp_path):
    path = _torn(tmp_path)
    rows = paths.read_jsonl(path, tolerate_torn=True)
    assert [row["job_id"] for row in rows] == ["j0", "j1", "j2"]


def test_the_strict_reader_raises_on_the_same_file(tmp_path):
    """Two behaviours, chosen per file rather than globally."""
    path = _torn(tmp_path)
    with pytest.raises(json.JSONDecodeError):
        paths.read_jsonl(path)


def test_a_missing_file_is_empty_rather_than_an_error(tmp_path):
    assert paths.read_jsonl(tmp_path / "absent.jsonl") == []
    assert paths.read_jsonl(tmp_path / "absent.jsonl", tolerate_torn=True) == []


def test_blank_lines_are_not_tears(tmp_path):
    path = tmp_path / "results.jsonl"
    path.write_text(json.dumps(GOOD) + "\n\n   \n" + json.dumps(GOOD) + "\n")
    assert len(paths.read_jsonl(path)) == 2
    assert paths.torn_lines(path) == 0


def test_the_tear_can_be_counted_rather_than_only_skipped(tmp_path):
    """So a stage that tolerates one can say how many it skipped. Skipping in
    silence is the shape of F99 and F103."""
    path = _torn(tmp_path)
    assert paths.torn_lines(path) == 1
    assert paths.torn_lines(tmp_path / "absent.jsonl") == 0


def test_every_reader_of_an_append_only_file_tolerates_a_tear():
    """The rule, not the seven instances. A reader added later with a bare
    comprehension is the same defect again."""
    offenders = []
    for relative in ("nobble/validate/layers.py", "nobble/design/lift.py",
                     "nobble/score/weights.py", "nobble/score/metrics.py",
                     "nobble/score/run.py", "nobble/execute/tier2.py",
                     "nobble/execute/runner.py"):
        for number, line in enumerate(
                (ROOT / relative).read_text().splitlines(), start=1):
            if "json.loads(line) for line in" not in line:
                continue
            # The queue readers are strict on purpose.
            if "queue" in line or "source_queue" in line:
                continue
            offenders.append(f"{relative}:{number}")
    assert not offenders, offenders


def test_the_queue_readers_stay_strict():
    """A damaged queue must be loud. Running 2,359 of 2,360 jobs because one
    line would not parse is worse than stopping.

    The count at the end is not decoration. The first version of this
    inspected only lines containing `read_jsonl(`, and at the time the queue
    readers were still bare comprehensions, so nothing matched and the test
    passed without asserting anything. That is the second vacuous test I
    wrote today, and this is what stops a third.
    """
    checked = []
    for relative in ("nobble/execute/runner.py", "tools/preflight.py",
                     "nobble/execute/tier2.py", "tools/rerun_pair.py",
                     "nobble/curate/library.py"):
        source = (ROOT / relative).read_text()
        for line in source.splitlines():
            stripped = line.strip()
            if stripped.startswith("#") or "read_jsonl(" not in stripped:
                continue
            if not any(word in stripped for word in
                       ("queue", "source_queue", "MANIFEST")):
                continue
            assert "tolerate_torn" not in stripped, (relative, stripped)
            checked.append(f"{relative}: {stripped}")
    assert len(checked) >= 5, checked


def test_a_damaged_queue_actually_raises(tmp_path):
    """The behaviour, not the source text. A queue reader that silently
    dropped a job would emit a campaign one job short and say nothing."""
    from nobble.execute.runner import run_campaign

    campaign = tmp_path / "campaign_bad_queue"
    campaign.mkdir()
    (campaign / "queue.jsonl").write_text(
        json.dumps({"job_id": "a", "pair_id": "p", "tokens": 10, "seed": 1,
                    "yaml": "a.yaml"}) + "\n"
        + '{"job_id": "b", "pair_i')

    with pytest.raises(json.JSONDecodeError):
        run_campaign(campaign)


def test_scoring_survives_a_torn_results_file(tmp_path):
    """End to end on the stage that would have raised. The campaign is the
    shape `metrics.aggregate` expects, with its last line cut."""
    from nobble.score import metrics

    # Built from real rows rather than invented, because aggregate() reads
    # fields a hand-written fixture keeps missing: the first attempt at this
    # died on `e3_gene`, which is the ninth field name I have guessed wrong
    # in this build.
    from nobble.execute.campaign import latest

    live = latest("campaign")
    if live is None or not (live / "results.jsonl").exists():
        pytest.skip("no campaign results to build a fixture from")
    real = [json.loads(line) for line
            in (live / "results.jsonl").read_text().splitlines() if line.strip()]
    one_pair = [row for row in real
                if row.get("pair_id") == real[0].get("pair_id")][:4]
    if not one_pair:
        pytest.skip("no completed pair in the live results")

    path = tmp_path / "results.jsonl"
    path.write_text("".join(json.dumps(row) + "\n" for row in one_pair)
                    + '{"job_id": "torn__ternary__conditioned__seed9", "pair_i')

    scored = metrics.aggregate(path)
    assert scored, "scoring returned nothing from a torn results file"
    wanted = one_pair[0]["pair_id"]
    assert any((row.get("pair_id") if isinstance(row, dict) else row.pair_id) == wanted
               for row in scored), wanted


def test_the_throughput_measurement_survives_it_too(tmp_path, monkeypatch):
    from nobble.execute.runner import write_throughput

    monkeypatch.setattr(paths, "THROUGHPUT", tmp_path / "throughput.json")
    campaign = tmp_path / "campaign_torn"
    campaign.mkdir()
    (campaign / "results.jsonl").write_text(
        json.dumps({**GOOD, "tier": "benchmark"}) + "\n"
        + '{"job_id": "b", "tok')

    payload = write_throughput(campaign)
    assert payload.get("jobs_timed") == 1, payload
