"""A scorer that wrote nothing exits non-zero (F322).

Three guards in this project wrap the scorer and act on its exit code.
`tools/tier2.sh` and `tools/run_chain.sh` both use `if ! ...` with comments
citing F194 and F195, one of which says in as many words that "a silent
scoring failure would leave 39 hours of inference unread".
`tools/refresh.sh` gates publication on the same code, because a failed score
leaves `scores.jsonl` holding the previous run's values and the atlas build
copies them.

None of the three could fire on the case they were written for.
`score_campaign` returns a summary carrying a `status` when it wrote no
scores, and `main` returned 0 regardless, so the silence reported itself as
success.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

SCI = ROOT / ".." / "BINMAN" / ".pixi" / "envs" / "default" / "bin" / "python"


def _score(campaign: Path, tier: int = 1):
    return subprocess.run(
        [str(SCI), "-m", "nobble.score.run", "--campaign", str(campaign),
         "--tier", str(tier), "--no-plip"],
        capture_output=True, text=True, cwd=ROOT,
        env={"PYTHONPATH": str(ROOT), "KMP_DUPLICATE_LIB_OK": "TRUE",
             "PATH": "/usr/bin:/bin"})


def test_a_campaign_with_no_results_exits_non_zero(tmp_path):
    campaign = tmp_path / "campaign_empty"
    campaign.mkdir()
    (campaign / "queue.jsonl").write_text("")
    done = _score(campaign)
    assert done.returncode != 0, done.stdout
    assert "wrote nothing" in done.stderr, done.stderr


def test_the_summary_still_prints_so_the_reason_is_in_the_log(tmp_path):
    """Exiting non-zero without saying why would move the problem rather
    than fix it: the three callers print the code and the operator needs the
    status."""
    campaign = tmp_path / "campaign_empty"
    campaign.mkdir()
    (campaign / "queue.jsonl").write_text("")
    done = _score(campaign)
    payload = json.loads(done.stdout)
    assert payload.get("status"), payload


def test_the_status_key_is_the_discriminator_not_a_string_match():
    """`score_campaign`'s success path has `pairs_scored` and no status, so
    presence is the test. A string match on "no results" would miss the
    tier-specific message and any added later."""
    source = (ROOT / "nobble" / "score" / "run.py").read_text()
    assert 'if "status" in summary:' in source
    assert "no results yet" not in source.split("def main")[1]


def test_a_scored_campaign_still_exits_zero():
    """The change must not make every refresh fail."""
    import pytest

    from nobble.execute.campaign import latest

    campaign = latest("campaign") or latest("benchmark")
    if campaign is None or not (campaign / "results.jsonl").exists():
        pytest.skip("no campaign with results on this checkout")
    done = subprocess.run(
        [str(SCI), "-m", "nobble.score.run", "--campaign", str(campaign),
         "--tier", "1", "--no-plip", "--limit", "1"],
        capture_output=True, text=True, cwd=ROOT,
        env={"PYTHONPATH": str(ROOT), "KMP_DUPLICATE_LIB_OK": "TRUE",
             "PATH": "/usr/bin:/bin"})
    assert done.returncode == 0, done.stderr[-400:]


def test_the_three_guards_that_depend_on_this_still_read_the_code():
    """If a caller stops checking, the exit code is decoration."""
    tier2 = (ROOT / "tools" / "tier2.sh").read_text()
    chain = (ROOT / "tools" / "run_chain.sh").read_text()
    refresh = (ROOT / "tools" / "refresh.sh").read_text()
    assert "nobble.score.run" in tier2 and "SCORE" in tier2.upper()
    assert "nobble.score.run" in chain
    assert "SCORE_CODE=$?" in refresh
    assert '"$SCORE_CODE" -ne 0' in refresh


def test_no_campaign_at_all_is_a_different_code():
    """2 means no campaign found and 3 means a campaign that scored
    nothing, because the remedies differ: assemble one, against look at why
    its jobs produced no rows."""
    source = (ROOT / "nobble" / "score" / "run.py").read_text()
    tail = source.split("def main")[1]
    assert "return 2" in tail
    assert "return 3" in tail
