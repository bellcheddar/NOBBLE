"""Two implementations of the ROC's AUC, compared by running both (F204).

The Delta tab shows the AUC twice. The sentence above the chart carries
`roc_summary.auc`, computed in Python from the rank statistic and landing in
`validation.json`. The chart's own title carries a trapezoid the browser
integrates over points the browser built from `PAIRS`. Both are on screen at
once, four decimals and three.

They agree: 0.7747 and 0.775 on the fixture below, which is the same number.
Nothing compared them. `tests/test_composite_agreement.py` exists for exactly
this pair one statistic down, and its reasoning applies here without
alteration: two implementations of one formula agree until they do not, and a
change to tie handling or to the threshold set on one side would put a
different number in the title from the one in the sentence, on the page where
the project's headline result is read.

The JavaScript is run rather than transcribed, through `qc/roc_harness.mjs`,
because transcribing the formula into Python would test the transcription
(F123).
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

from nobble import paths  # noqa: E402
from nobble.validate.layers import matched_control_roc  # noqa: E402

HARNESS = ROOT / "qc" / "roc_harness.mjs"
TEMPLATE = ROOT / "nobble" / "app" / "templates" / "delta.html"


def _both(tmp_path: Path) -> tuple[float, float]:
    """Python's AUC and the browser's, from the same rows."""
    if not shutil.which("node"):
        pytest.skip("node is not available")
    from test_roc_verdict_is_beside_its_curve import _scored_sievers_campaign

    campaign = _scored_sievers_campaign(tmp_path)
    outcome = matched_control_roc(campaign)
    if outcome.status != "computed":
        pytest.skip(f"the fixture's ROC did not compute: {outcome.status}")

    rows = [json.loads(line) for line
            in (campaign / "scores.jsonl").read_text().splitlines() if line.strip()]
    payload = tmp_path / "pairs.json"
    payload.write_text(json.dumps(rows))

    minimum = paths.thresholds()["validation"]["roc_minimum_per_side"]
    done = subprocess.run(
        ["node", str(HARNESS), str(TEMPLATE), str(payload), str(minimum)],
        capture_output=True, text=True, timeout=60,
    )
    assert done.returncode == 0, done.stderr
    result = json.loads(done.stdout.strip().splitlines()[-1])
    assert "empty" not in result, (
        f"the browser drew no curve on a fixture whose ROC computes: {result}"
    )
    assert result.get("auc") is not None, result
    return float(outcome.summary["auc"]), float(result["auc"])


def test_the_two_aucs_agree(tmp_path):
    python_auc, browser_auc = _both(tmp_path)
    # The title rounds to three decimals, so agreement is to that precision.
    assert round(python_auc, 3) == pytest.approx(browser_auc, abs=1e-9), (
        f"the sentence says {python_auc} and the chart title says "
        f"{browser_auc}: one page, one curve, two numbers"
    )


def test_both_are_a_plausible_auc(tmp_path):
    """So the test cannot pass by both being zero or both being nonsense."""
    python_auc, browser_auc = _both(tmp_path)
    for value in (python_auc, browser_auc):
        assert 0.0 < value < 1.0, value
    assert python_auc > 0.5, (
        "the fixture is built to separate, so an AUC at or below chance means "
        "the fixture changed rather than the implementations disagreeing"
    )


def test_the_harness_runs_the_pages_own_function():
    """Not a copy of it, which is F123's point."""
    harness = HARNESS.read_text()
    assert "function buildRoc" in harness, (
        "the harness no longer extracts buildRoc, so it may be testing a "
        "transcription rather than the page"
    )
    assert "readFileSync(templatePath" in harness


def test_the_harness_takes_the_threshold_rather_than_carrying_one():
    """A cutoff in the harness would be a second copy of a config value."""
    harness = HARNESS.read_text()
    code = "\n".join(line for line in harness.splitlines()
                     if not line.strip().startswith(("*", "/*")))
    assert "minimumPerSide" in code
    minimum = paths.thresholds()["validation"]["roc_minimum_per_side"]
    assert f"= {minimum}" not in code, (
        "the harness carries the minimum as a literal, so it can drift from "
        "config/thresholds.toml"
    )
