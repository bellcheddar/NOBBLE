"""24 positives and 96 negatives is the whole arm. 6 and 24 would look alike.

The ROC layer counted what it found in `scores.jsonl` and reported those
counts, with nothing to say what the arm should hold. The headline of this
project is that curve reading as a null, so whether it was drawn from the
whole Sievers arm or from a quarter of it is part of the claim.

A curve over a partial arm is still a real estimate with a wider interval,
which is why this reports coverage rather than refusing to compute: F258's
vacuous confirmation and a small sample are different problems (F259).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from nobble.validate import layers


def _write(path: Path, rows: list[dict]) -> None:
    path.write_text("".join(json.dumps(row) + "\n" for row in rows))


def _campaign(root: Path, queued: int, scored: int) -> Path:
    """`queued` pairs per side in the queue, `scored` of them in the scores."""
    directory = root / "campaign_roc"
    directory.mkdir(exist_ok=True)
    queue, scores = [], []
    for label, delta in (("degraded", 0.2), ("not_degraded", 0.1)):
        for index in range(queued):
            pair = f"sv_{label}_{index}"
            queue.append({"job_id": f"{pair}__j", "pair_id": pair,
                          "tier": layers.ROC_ARM, "peptide_label": label,
                          "complex_type": "ternary", "tokens": 150})
            if index < scored:
                scores.append({"pair_id": pair, "tier": layers.ROC_ARM,
                               "peptide_label": label,
                               "delta_iptm": delta + index * 0.01,
                               "seed_records": []})
    _write(directory / "queue.jsonl", queue)
    _write(directory / "scores.jsonl", scores)
    return directory


def test_a_complete_arm_says_so(tmp_path):
    layer = layers.matched_control_roc(_campaign(tmp_path, 12, 12))
    assert layer.summary["positives_expected"] == 12, layer.summary
    assert layer.summary["coverage"].startswith("complete"), layer.summary


def test_a_partial_arm_is_named_as_partial(tmp_path):
    """And still computes, because a small sample is not a missing one."""
    layer = layers.matched_control_roc(_campaign(tmp_path, 12, 6))
    assert layer.summary["positives"] == 6, layer.summary
    assert layer.summary["positives_expected"] == 12, layer.summary
    assert layer.summary["coverage"].startswith("partial"), layer.summary
    assert "6 of 12" in layer.summary["coverage"], layer.summary


def test_a_missing_queue_is_unknown_coverage_not_full_coverage(tmp_path):
    """A zero denominator would make any coverage look complete.

    This is the direction that matters. `expected.get("degraded")` returning
    0 and being compared with `>=` reads as complete for any number of
    scored pairs, so the absence of a queue has to be its own answer.
    """
    directory = _campaign(tmp_path, 12, 6)
    (directory / "queue.jsonl").unlink()
    layer = layers.matched_control_roc(directory)
    assert layer.summary["coverage"].startswith("unknown"), layer.summary
    assert layer.summary["positives_expected"] is None, layer.summary


def test_the_expected_count_is_per_pair_not_per_job(tmp_path):
    """The curve has one point per pair, so the denominator is in pairs.

    Counting queue rows would give the job count, fifteen times larger on
    this campaign, and a complete arm would read as 6 per cent covered.
    """
    directory = tmp_path / "campaign_seeds"
    directory.mkdir()
    rows = []
    for label in ("degraded", "not_degraded"):
        for index in range(3):
            for seed in range(5):
                rows.append({"job_id": f"sv_{label}_{index}__seed{seed}",
                             "pair_id": f"sv_{label}_{index}",
                             "tier": layers.ROC_ARM, "peptide_label": label,
                             "seed": seed})
    _write(directory / "queue.jsonl", rows)
    assert layers._arm_expected(directory)[0] == {"degraded": 3,
                                                  "not_degraded": 3}


def test_pairs_outside_the_arm_do_not_inflate_the_denominator(tmp_path):
    """The benchmark panel is also labelled `degraded`.

    It is excluded from the curve for the reasons the layer already states,
    so counting it in the expected total would make a complete arm read as
    partial for ever.
    """
    directory = _campaign(tmp_path, 12, 12)
    with (directory / "queue.jsonl").open("a") as queue:
        queue.write(json.dumps(
            {"job_id": "bench04__j", "pair_id": "bench04_IKZF1_CRBN",
             "tier": "benchmark", "peptide_label": "degraded"}) + "\n")
    layer = layers.matched_control_roc(directory)
    assert layer.summary["positives_expected"] == 12, layer.summary
    assert layer.summary["coverage"].startswith("complete"), layer.summary


def test_the_page_says_nothing_when_the_arm_is_complete():
    """One short line when partial, no line at all when complete.

    A caveat beside every number reads as a lack of confidence in the
    numbers rather than as rigour, which is why this is conditional in the
    template rather than always rendered.
    """
    template = (ROOT / "nobble" / "app" / "templates" / "about.html").read_text()
    assert "roc.summary.coverage" in template, (
        "the page cannot show a partial arm at all")
    guard = template[template.index("roc.summary.interpretation"):
                     template.index("roc.summary.coverage")]
    assert "startswith('partial')" in guard, guard


def test_the_partial_line_actually_renders(monkeypatch):
    """The branch no fixture reaches otherwise.

    The published bundle's validation.json predates this field, so the walk
    in test_every_route_answers.py renders the panel with `coverage` absent
    and exercises only the silent path. A Jinja error inside the conditional
    would pass every test in the suite, which is F260's lesson one file over:
    a check that never enters a branch says nothing about it.
    """
    from nobble.app import create_app, data

    atlas = ROOT / "deploy" / "atlas"
    if not (atlas / "validation.json").exists():
        pytest.skip("no published bundle to serve")

    real = data.precomputed

    def partial(name):
        payload = real(name)
        if name != "validation.json":
            return payload
        import copy

        payload = copy.deepcopy(payload)
        layer = (payload.get("layers") or {}).get("matched_control_roc")
        if not layer or not layer.get("summary"):
            pytest.skip("the bundle has no computed ROC layer to adjust")
        layer["summary"]["coverage"] = (
            "partial: 6 of 24 positive(s) and 24 of 96 matched negative(s)")
        return payload

    monkeypatch.setattr(data, "precomputed", partial)
    app = create_app(str(atlas))
    app.config["TESTING"] = True
    page = app.test_client().get("/about")
    assert page.status_code == 200, page.status_code
    text = page.get_data(as_text=True)
    assert "partial: 6 of 24" in text, "the partial coverage line did not render"


def test_a_campaign_with_no_arm_is_not_applicable_rather_than_unreadable(tmp_path):
    """A readable queue with no Sievers pairs is not a file problem.

    Run against the corrected campaign, whose queue is perfectly readable and
    holds seven whole-domain pairs and no Sievers ones, the coverage line said
    "the campaign's queue could not be read". That sends a reader looking for
    a missing file. It is F266's `unavailable` against `not_applicable`
    distinction, in the code written for F259 the same morning (F278).
    """
    directory = tmp_path / "campaign_no_arm"
    directory.mkdir()
    _write(directory / "queue.jsonl", [
        {"job_id": "j1", "pair_id": "corr01_GSPT1_CRBN", "tier": "corrected",
         "peptide_label": "degraded", "complex_type": "ternary"},
    ])
    _write(directory / "scores.jsonl", [])
    expected, queue_was_read = layers._arm_expected(directory)
    assert queue_was_read is True
    line = layers._arm_coverage(0, 0, expected, queue_was_read)
    assert line.startswith("not_applicable"), line
    assert layers.ROC_ARM in line, line


def test_an_absent_queue_is_still_unknown(tmp_path):
    """The other side of the distinction, so one message cannot serve both."""
    expected, queue_was_read = layers._arm_expected(tmp_path / "gone")
    assert queue_was_read is False
    line = layers._arm_coverage(0, 0, expected, queue_was_read)
    assert line.startswith("unknown"), line


def test_the_expected_mapping_does_not_leak_its_own_bookkeeping(tmp_path):
    """`_queue_was_read` is how the two cases are told apart, not a label.

    It is carried in the same mapping as the per-label counts, so a caller
    iterating the mapping would otherwise find a key that is not a peptide
    label and count it as one.
    """
    directory = tmp_path / "campaign_arm"
    directory.mkdir()
    _write(directory / "queue.jsonl", [
        {"job_id": f"j{i}", "pair_id": f"sv_{label}_{i}",
         "tier": layers.ROC_ARM, "peptide_label": label,
         "complex_type": "ternary"}
        for label in ("degraded", "not_degraded") for i in range(3)])
    expected, _ = layers._arm_expected(directory)
    assert expected == {"degraded": 3, "not_degraded": 3}, expected
