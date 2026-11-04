"""Seconds per token is not one number, and the projection said it was.

F45 replaced a "representative job" with a measured seconds-per-token rate,
because the per-token rate transfers between campaigns and a job size does
not. `projected_hours`'s docstring then claimed the resulting figure came
from "summing the real tokens at the rate measured for jobs of each size".

It did not. The code multiplied every token by one median rate. And that
rate is not a property of the model: measured on the main campaign it runs
from 0.211 s/token for 200-400 token jobs to 0.663 for 800-1600 token jobs,
because attention cost does not grow linearly with sequence length.

So one median understates any campaign whose large jobs are a minority of
the jobs and a majority of the cost, which is the usual shape. On the main
campaign's own remaining queue the flat rate gives 48.6 hours and the
banded rate 51.4. Both are inside Gate G1's 96, so nothing was reported
wrongly, which is the only reason this was a measurement error rather than
a false gate (F61).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from nobble import paths  # noqa: E402
from nobble.execute import runner  # noqa: E402

EDGES = [200, 400, 800, 1600, 3200]


def _with_bands(monkeypatch, tmp_path, bands, median=0.4):
    from nobble.curate import diversity

    path = tmp_path / "throughput.json"
    path.write_text(json.dumps({
        "campaign": "synthetic",
        "median_seconds_per_token": median,
        "representative_tokens": 150,
        "seconds_per_representative_job": median * 150,
        "jobs_per_pair": 15,
        "seconds_per_token_by_band": bands,
    }))
    monkeypatch.setattr(paths, "THROUGHPUT", path)
    monkeypatch.setattr(diversity.paths, "THROUGHPUT", path)


def _band(low, high, rate, jobs=10):
    return {"min_tokens": low, "max_tokens": high,
            "median_seconds_per_token": rate, "jobs": jobs}


def test_the_band_edges_are_exclusive_at_the_top():
    assert runner.token_band(199, EDGES) == (0, 200)
    assert runner.token_band(200, EDGES) == (200, 400)
    assert runner.token_band(399, EDGES) == (200, 400)
    assert runner.token_band(400, EDGES) == (400, 800)


def test_the_top_band_is_open_ended():
    """A job larger than every edge still belongs somewhere. Returning the
    lowest band for it would price the most expensive job in the campaign
    at the rate of the cheapest."""
    assert runner.token_band(5000, EDGES) == (3200, 0)


def test_the_bands_come_from_the_configuration():
    configured = [int(edge) for edge in
                  paths.thresholds()["throughput"]["token_bands"]]
    assert configured == EDGES


def test_the_writer_records_a_rate_and_a_count_per_band():
    """The count travels with the rate: a band measured once is not the
    same evidence as a band measured fifty times."""
    timed = ([{"tokens": 100, "seconds": 50}] * 3
             + [{"tokens": 1000, "seconds": 700}])
    bands = runner.throughput_bands(timed)
    small = next(b for b in bands if b["min_tokens"] == 0)
    large = next(b for b in bands if b["min_tokens"] == 800)
    assert small["median_seconds_per_token"] == 0.5
    assert small["jobs"] == 3
    assert large["median_seconds_per_token"] == 0.7
    assert large["jobs"] == 1


def test_a_mixed_campaign_costs_more_than_one_median_says(monkeypatch, tmp_path):
    """The defect, in the shape it actually takes: many cheap jobs set the
    median, a few expensive ones carry the cost."""
    from nobble.curate.diversity import projected_hours

    _with_bands(monkeypatch, tmp_path,
                [_band(0, 200, 0.2, jobs=90), _band(800, 1600, 1.0, jobs=10)],
                median=0.2)
    job_tokens = [100] * 90 + [1000] * 10
    banded = projected_hours(10, job_tokens=job_tokens)
    flat = projected_hours(10, total_tokens=sum(job_tokens))

    # 90x100x0.2 + 10x1000x1.0 = 1800 + 10000 = 11800 s
    assert banded["projected_hours"] == round(11800 / 3600, 1)
    # One median: 19000 tokens x 0.2 = 3800 s. Under by a factor of three.
    assert flat["projected_hours"] == round(3800 / 3600, 1)
    assert banded["projected_hours"] > flat["projected_hours"] * 2


def test_a_uniform_campaign_agrees_with_the_flat_rate(monkeypatch, tmp_path):
    """When every job is the same size the two methods must not differ, or
    the banding is introducing an error of its own."""
    from nobble.curate.diversity import projected_hours

    _with_bands(monkeypatch, tmp_path, [_band(0, 200, 0.5, jobs=50)], median=0.5)
    job_tokens = [150] * 100
    banded = projected_hours(10, job_tokens=job_tokens)
    flat = projected_hours(10, total_tokens=sum(job_tokens))
    assert banded["projected_hours"] == flat["projected_hours"]


def test_an_unmeasured_band_is_priced_at_the_slowest_rate_and_counted(
        monkeypatch, tmp_path):
    """Guessing cheap would be the one error that opens a gate too late."""
    from nobble.curate.diversity import projected_hours

    _with_bands(monkeypatch, tmp_path,
                [_band(0, 200, 0.2), _band(200, 400, 0.9)], median=0.2)
    result = projected_hours(10, job_tokens=[100, 5000])
    assert result["unmeasured_jobs"] == 1
    # 100x0.2 + 5000x0.9 (the slowest observed), not 5000x0.2
    assert result["projected_hours"] == round((20 + 4500) / 3600, 1)
    assert "no measurement" in result["basis"]


def test_the_basis_says_which_method_produced_the_number(monkeypatch, tmp_path):
    """The figure is reported to a Gate. Which rate produced it is part of
    the figure, and the flat path now says plainly that it used one rate
    for every job size."""
    from nobble.curate.diversity import projected_hours

    _with_bands(monkeypatch, tmp_path, [_band(0, 200, 0.2)], median=0.2)
    assert "own token band" in projected_hours(10, job_tokens=[100] * 5)["basis"]
    flat = projected_hours(10, total_tokens=500)["basis"]
    assert "one rate for every job size" in flat


def test_a_throughput_file_without_bands_still_projects(monkeypatch, tmp_path):
    """Older measurements have no bands. Falling over would make the gate
    unevaluable, which is worse than the flat estimate it replaces."""
    from nobble.curate import diversity
    from nobble.curate.diversity import projected_hours

    path = tmp_path / "throughput.json"
    path.write_text(json.dumps({
        "campaign": "old", "median_seconds_per_token": 0.4,
        "representative_tokens": 150, "seconds_per_representative_job": 60,
        "jobs_per_pair": 15,
    }))
    monkeypatch.setattr(paths, "THROUGHPUT", path)
    monkeypatch.setattr(diversity.paths, "THROUGHPUT", path)
    result = projected_hours(10, total_tokens=1000, job_tokens=[100] * 10)
    assert result["projected_hours"] == round(1000 * 0.4 / 3600, 1)
    assert result["unmeasured_jobs"] == 0


def test_one_definition_decides_the_bands():
    """The projection imports the writer's function rather than carrying a
    copy. Two binnings is how a rate measured in one set of bands comes to
    be applied in another, which is this finding arriving by duplication."""
    source = (ROOT / "nobble" / "curate" / "diversity.py").read_text()
    assert "from nobble.execute.runner import token_band" in source
    assert "for edge in edges:" not in source, (
        "diversity.py has its own copy of the binning rule"
    )


def test_the_live_measurement_is_banded():
    """The file the Gate is actually evaluated against."""
    if not paths.THROUGHPUT.exists():
        pytest.skip("no measured throughput yet")
    measured = json.loads(paths.THROUGHPUT.read_text())
    bands = measured.get("seconds_per_token_by_band")
    if not bands:
        pytest.skip("throughput measured before banding")
    assert all(b["jobs"] >= 1 for b in bands)
    rates = [b["median_seconds_per_token"] for b in bands]
    assert min(rates) > 0
    if len(rates) > 1:
        assert max(rates) > min(rates), (
            "every band measured the same rate, which would mean the "
            "banding is not distinguishing anything"
        )
