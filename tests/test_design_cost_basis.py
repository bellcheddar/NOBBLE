"""F45 added a parameter and nobody ever passed it.

F45's finding was that sizing a campaign from a "representative job" taken
from whichever campaign was measured last is wrong, because the per-token
rate transfers between campaigns and the job size does not. It opened Gate
G1 falsely at 104.3 hours against a real 54.

The fix added `tokens_per_pair` to `cost_of` and `total_tokens` to
`projected_hours`. F61 added `job_tokens` for per-band pricing. The design
arm, the only caller of `cost_of`, passed none of them, so it kept taking
the fallback that the finding was about.

It gave the right answer by coincidence. Throughput is measured on the main
campaign, whose median job is 144 tokens, and the design scan's jobs are 144
and 124. Measured on the corrected campaign instead, whose median job is
397, the same unchanged scan would have been projected at 11.5 hours against
a real 4.4 (F79).
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from unittest import mock

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from nobble import paths  # noqa: E402
from nobble.curate import diversity  # noqa: E402
from nobble.design import report  # noqa: E402
from nobble.execute.campaign import latest_or_absent as _newest  # noqa: E402

PARENT = "benchmark_888fd2c63e"


def _throughput(representative_tokens: int, campaign: str):
    """A throughput file measured on a campaign with this median job."""
    real = json.loads(paths.THROUGHPUT.read_text())
    altered = dict(real)
    altered["representative_tokens"] = representative_tokens
    altered["seconds_per_representative_job"] = round(
        real["median_seconds_per_token"] * representative_tokens, 1)
    altered["campaign"] = campaign
    path = Path(tempfile.mkdtemp()) / "throughput.json"
    path.write_text(json.dumps(altered))
    return path


def _requires_throughput():
    if not paths.THROUGHPUT.exists():
        pytest.skip("no measured throughput yet")


def test_the_scan_is_priced_on_the_jobs_it_would_emit():
    """The preview's cost must be the cost of the thing previewed. 240 jobs
    totalling 32,960 tokens is what the assembler emits for this parent."""
    _requires_throughput()
    tokens = report._scan_job_tokens(PARENT)
    assert tokens, "the assembler reported no jobs for this parent"
    assert len(tokens) == 240
    assert sum(tokens) == 32960
    assert set(tokens) == {124, 144}


def test_the_cost_matches_the_assembled_campaign():
    """The same figure the real design campaign projects, because it is the
    same job list."""
    _requires_throughput()
    cost = report.cost_of(16, job_tokens=report._scan_job_tokens(PARENT))
    assert "each priced in its own token band" in cost["basis"]
    assert "32,960 tokens" in cost["basis"]


def test_the_projection_no_longer_depends_on_which_campaign_was_measured():
    """The defect, as a property. The design scan does not change when
    throughput is remeasured elsewhere, so neither should its cost."""
    _requires_throughput()
    tokens = report._scan_job_tokens(PARENT)
    costs = {}
    for representative, name in ((144, "main"), (397, "corrected"),
                                 (1223, "large")):
        path = _throughput(representative, name)
        with mock.patch.object(paths, "THROUGHPUT", path), \
             mock.patch.object(diversity.paths, "THROUGHPUT", path):
            costs[name] = report.cost_of(16, job_tokens=tokens)["projected_hours"]
    assert len(set(costs.values())) == 1, (
        f"the same scan was priced differently per measuring campaign: {costs}"
    )


def test_the_old_call_did_depend_on_it():
    """The control. Without the job tokens the figure moves by 2.6x on a
    scan that has not changed, which is what makes this a finding rather
    than a tidy-up."""
    _requires_throughput()
    without = {}
    for representative, name in ((144, "main"), (397, "corrected")):
        path = _throughput(representative, name)
        with mock.patch.object(paths, "THROUGHPUT", path), \
             mock.patch.object(diversity.paths, "THROUGHPUT", path):
            without[name] = report.cost_of(16)["projected_hours"]
    assert without["corrected"] > without["main"] * 2, (
        f"the fallback no longer varies with the measuring campaign: {without}"
    )


def test_the_preview_passes_the_tokens():
    """The wiring, not the helper (F40). cost_of accepting a parameter is
    not the same as build() supplying one."""
    _requires_throughput()
    from nobble.app import data

    campaign = _newest("campaign")
    if not campaign.exists():
        pytest.skip("no main campaign on this checkout")
    data.configure(str(campaign))
    preview = report.build().get("preview") or {}
    cost = preview.get("cost") or {}
    assert cost.get("projected_hours") is not None
    assert "each priced in its own token band" in cost.get("basis", ""), (
        "the preview is still taking the representative-job fallback"
    )


def test_a_parent_the_assembler_cannot_route_is_not_fatal():
    """The preview must still render. An unknown parent gives no tokens and
    the cost falls back rather than raising."""
    assert report._scan_job_tokens("not_a_real_peptide") is None
    _requires_throughput()
    cost = report.cost_of(16, job_tokens=None)
    assert cost.get("projected_hours") is not None
