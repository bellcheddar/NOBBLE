"""Refinement has to be priced against the gate it can blow (F135).

Gate G1 is judged against `max_compute_hours`, and the projection it was
judged on priced tier 1 only. `tier2.py` mentioned no budget: each job got a
timeout, which bounds one job and not a queue, and a decile of the main
campaign is 150 jobs at a six-hour timeout.

Nothing had gone wrong because tier 2 has never run. The chain runs it as
soon as tier 1 finishes, so these are the checks that stop it starting
something that cannot finish inside the budget.
"""
import json

from nobble import paths
from nobble.execute import budget, tier2


def _campaign(root, *, pairs=3, seconds=600.0, tier2_seconds=None):
    """A campaign with a ternary queue and completed tier-1 results."""
    directory = root / "campaign_fixture"
    directory.mkdir(parents=True, exist_ok=True)
    queue, results = [], []
    for index in range(pairs):
        pair = f"p{index:02d}"
        for arm, complex_type in (("binary", "binary"), ("ternary", "ternary")):
            job = f"{pair}__{arm}__seed1"
            queue.append({"job_id": job, "pair_id": pair,
                          "complex_type": complex_type, "tokens": 200})
            results.append({"job_id": job, "pair_id": pair,
                            "complex_type": complex_type, "status": "done",
                            "seconds": seconds})
    (directory / "queue.jsonl").write_text(
        "".join(json.dumps(row) + "\n" for row in queue))
    (directory / "results.jsonl").write_text(
        "".join(json.dumps(row) + "\n" for row in results))
    if tier2_seconds is not None:
        rows = [{"job_id": f"p00__ternary__seed1{budget.TIER2_SUFFIX}",
                 "pair_id": "p00", "complex_type": "ternary",
                 "status": "done", "seconds": tier2_seconds}]
        (directory / "results_tier2.jsonl").write_text(
            "".join(json.dumps(row) + "\n" for row in rows))
    return directory


def test_only_the_ternary_jobs_are_priced():
    """Tier 2 refines ternary jobs only, so pricing the binary ones too would
    overstate the queue by the binary arm."""
    import tempfile
    from pathlib import Path
    with tempfile.TemporaryDirectory() as temporary:
        directory = _campaign(Path(temporary), pairs=4)
        projection = budget.tier2_projection(directory)
        assert projection["jobs"] == 4, projection


def test_the_range_brackets_the_two_possible_splits():
    low, high = budget.scaling_range()
    settings = paths.tuning()["campaign"]
    recycles = (int(settings["tier2_recycles"])
                / int(settings["tier1_recycles"]))
    samples = (int(settings["tier2_diffusion_samples"])
               / int(settings["tier1_diffusion_samples"]))
    assert low == min(recycles, samples)
    assert high == max(recycles, samples)
    assert low < high, (
        "a single factor would be an estimate of a split nobody has measured"
    )


def test_the_gate_is_judged_on_the_upper_bound(tmp_path):
    """A budget judged on its optimistic end is how a budget is overrun."""
    # Sized against the real budget: three ternary jobs of two hours each at
    # the high factor is 150 hours, over the 96-hour gate, and at the low
    # factor is 20 hours, under it. The two ends disagree, which is the case
    # the choice of end decides.
    directory = _campaign(tmp_path, pairs=3, seconds=7200.0)
    report = budget.gate_g1(directory)
    assert report["judged_on"] == "upper bound"
    assert report["tier2"]["hours_low"] < report["hours_remaining"]
    assert report["tier2"]["hours_high"] > report["tier2"]["hours_low"]
    assert report["gate_g1_open"] is True, report["verdict"]
    assert "measured factor" in report["verdict"], (
        "a refusal on a bound has to say what would replace the bound"
    )


def test_one_refinement_collapses_the_range(tmp_path):
    """The range exists because nothing has run. One result ends it."""
    directory = _campaign(tmp_path, pairs=3, seconds=600.0,
                          tier2_seconds=600.0 * 4)
    observed = budget.measured_scaling(directory)
    assert observed["jobs"] == 1
    assert observed["factor"] == 4.0, observed
    low, high = budget.scaling_range(campaign=directory)
    assert low == high == 4.0
    report = budget.gate_g1(directory)
    assert report["judged_on"] == "measured factor"
    assert report["tier2"]["hours_low"] == report["tier2"]["hours_high"]


def test_the_measured_factor_pairs_by_job_not_by_pair(tmp_path):
    """The tier-2 job id is the tier-1 one plus a suffix.

    If the suffix here and the suffix `build_tier2_queue` writes ever
    disagree, nothing raises: the pairing finds nothing and the factor stays
    unmeasured, so the gate keeps judging on a bound forever.
    """
    import inspect
    source = inspect.getsource(tier2.build_tier2_queue)
    assert f'"{budget.TIER2_SUFFIX}"' in source or \
           f"'{budget.TIER2_SUFFIX}'" in source, (
        "build_tier2_queue no longer builds the job id with "
        f"{budget.TIER2_SUFFIX!r}, so measured_scaling pairs nothing"
    )
    directory = _campaign(tmp_path, pairs=2, tier2_seconds=1200.0)
    assert budget.measured_scaling(directory)["factor"] == 2.0


def test_reduction_drops_pairs_from_the_bottom_of_the_ranking(tmp_path):
    directory = _campaign(tmp_path, pairs=6, seconds=3600.0)
    ranked = [f"p{index:02d}" for index in range(6)]
    outcome = budget.affordable_pairs(directory, ranked)
    assert outcome["affordable"] == ranked[:len(outcome["affordable"])], (
        "the affordable set must be a prefix of the ranking, not a subset"
    )
    assert outcome["dropped"] == ranked[len(outcome["affordable"]):]


def test_an_unpriced_job_is_not_a_free_job(tmp_path):
    """A projection that gets cheaper the less of the campaign has run would
    pass the gate at the start of every campaign."""
    directory = _campaign(tmp_path, pairs=4, seconds=600.0)
    full = budget.tier2_projection(directory)
    # Remove three of the four tier-1 ternary timings.
    rows = [json.loads(line) for line
            in (directory / "results.jsonl").read_text().splitlines() if line]
    kept = [r for r in rows if r["complex_type"] == "binary"
            or r["pair_id"] == "p00"]
    (directory / "results.jsonl").write_text(
        "".join(json.dumps(r) + "\n" for r in kept))
    partial = budget.tier2_projection(directory)
    assert partial["unpriced_jobs"] == 3
    assert partial["hours_high"] == full["hours_high"], (
        f"{partial['hours_high']} against {full['hours_high']}: an unpriced "
        "job was charged nothing"
    )


def test_run_refuses_rather_than_queueing_an_unaffordable_decile(tmp_path, monkeypatch):
    """Gate G1 opens only when nothing is affordable, and then no queue is
    written: a queue on disk is a queue the chain will run."""
    directory = _campaign(tmp_path, pairs=2, seconds=3600.0 * 200)
    selection = tier2.Selection(
        campaign=str(directory), ranking_key="delta_iptm",
        decile_fraction=1.0, pairs_considered=2, pairs_selected=2,
        selected=[{"pair_id": "p00"}, {"pair_id": "p01"}], status="selected",
    )
    monkeypatch.setattr(tier2, "select_top_decile",
                        lambda campaign, fraction=None: selection)
    report = tier2.run(directory)
    assert report["selection"]["status"] == "refused: gate G1"
    assert "queue" not in report
    assert not (directory / "queue_tier2.jsonl").exists()
    assert any("GATE G1 OPEN" in note
               for note in report["selection"]["notes"])


def test_run_reduces_and_says_so(tmp_path, monkeypatch):
    # Six ternary jobs of an hour each: 150 hours at the high factor against
    # a 96-hour gate, so three of the six are affordable.
    directory = _campaign(tmp_path, pairs=6, seconds=3600.0)
    ranked = [f"p{index:02d}" for index in range(6)]
    selection = tier2.Selection(
        campaign=str(directory), ranking_key="delta_iptm",
        decile_fraction=1.0, pairs_considered=6, pairs_selected=6,
        selected=[{"pair_id": pair} for pair in ranked], status="selected",
    )
    monkeypatch.setattr(tier2, "select_top_decile",
                        lambda campaign, fraction=None: selection)
    report = tier2.run(directory)
    kept = report["selection"]["pairs_selected"]
    assert kept < 6, "nothing was reduced, so the fixture is not over budget"
    assert kept == len(report["budget"]["affordable"])
    assert report["queue"]["jobs"] == kept, (
        "the queue was built from the unreduced selection"
    )
    assert any("to fit the compute budget" in note
               for note in report["selection"]["notes"])


def test_hours_spent_is_measured_over_both_tiers(tmp_path):
    directory = _campaign(tmp_path, pairs=2, seconds=1800.0,
                          tier2_seconds=3600.0)
    spent = budget.hours_spent(tmp_path)
    # Four tier-1 jobs at half an hour, one tier-2 job at an hour.
    assert spent["hours"] == 3.0, spent
    assert spent["jobs"] == 5


def test_the_chain_stops_on_an_open_gate():
    """tools/tier2.sh must key on exit 3 before it reaches the refiner.

    Without that the refiner runs with no queue to read, which does nothing
    and prints the same lines as a refinement that happened.
    """
    from pathlib import Path
    script = Path("tools/tier2.sh").read_text()
    select = script.index("select the top decile")
    refine = script.index('echo "--- refine"')
    guard = script[select:refine]
    assert "-eq 3" in guard, (
        "tier2.sh does not check the selection's exit code before refining"
    )
    assert "exit 3" in guard


def test_the_projection_counts_exactly_the_jobs_the_queue_builds(tmp_path):
    """Two filters for the same set, in two modules.

    `budget.tier2_projection` decides what to price and
    `tier2.build_tier2_queue` decides what to queue, and each spells the
    filter itself. If they ever disagree the queue is priced as something
    other than what it is, and nothing fails: the projection is a number and
    the queue is a file.
    """
    directory = _campaign(tmp_path, pairs=5)
    ranked = [f"p{index:02d}" for index in range(3)]
    selection = tier2.Selection(
        campaign=str(directory), ranking_key="delta_iptm",
        decile_fraction=0.6, pairs_considered=5, pairs_selected=3,
        selected=[{"pair_id": pair} for pair in ranked], status="selected",
    )
    built = tier2.build_tier2_queue(directory, selection)
    projection = budget.tier2_projection(directory, ranked)
    assert built["jobs"] == projection["jobs"], (
        f"queue builds {built['jobs']} job(s), projection prices "
        f"{projection['jobs']}"
    )
    queued = paths.read_jsonl(directory / "queue_tier2.jsonl")
    assert len(queued) == projection["jobs"]
