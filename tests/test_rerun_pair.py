"""The correction step that has to run on a live campaign, and had no test.

`tools/rerun_pair.py bench02_BRD4_VHL --apply` is the F47 fix: the pair's
jobs were emitted with a hydroxyproline on BRD4 Pro379, the rule is fixed and
the YAMLs on disk are not. It regenerates that pair's YAMLs and drops its
rows from `state.jsonl` and `results.jsonl` so the queue runs them again.

It runs once, by hand, when the GPU is free, against a campaign holding days
of compute, and it rewrites the file that records which of 2,360 jobs are
done. Nothing exercised it: the only mentions of it in the suite were
comments in other tests saying it was pending.

So its matching rule, its backup and its atomicity are checked here. The
atomicity mattered: it wrote the rewritten state in place with `write_text`,
which truncates first, so a kill inside that window left a partial record of
what had run (F109).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

import rerun_pair  # noqa: E402

PAIR = "bench02_BRD4_VHL"


def _state(tmp_path: Path, rows: list[dict], name="state.jsonl") -> Path:
    path = tmp_path / name
    path.write_text("\n".join(json.dumps(row) for row in rows) + "\n")
    return path


def test_it_drops_the_pair_and_keeps_everything_else(tmp_path):
    path = _state(tmp_path, [
        {"job_id": f"{PAIR}__ternary__conditioned__seed1", "pair_id": PAIR},
        {"job_id": f"{PAIR}__binary__unconstrained__seed2", "pair_id": PAIR},
        {"job_id": "bench01_GSPT1_CRBN__ternary__conditioned__seed1",
         "pair_id": "bench01_GSPT1_CRBN"},
        {"job_id": "sv_neg_ZN346_d5063d__binary__unconstrained__seed1",
         "pair_id": "sv_neg_ZN346_d5063d"},
    ])
    assert rerun_pair._rewrite_without(path, PAIR) == 2
    kept = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    assert [row["pair_id"] for row in kept] == [
        "bench01_GSPT1_CRBN", "sv_neg_ZN346_d5063d"]


def test_a_pair_whose_id_is_a_prefix_of_another_is_not_dropped(tmp_path):
    """The separator is what makes the match safe. `bench02_BRD4_VHL` against
    a hypothetical `bench02_BRD4_VHL_variant` would take both without it, and
    dropping a pair that had finished is hours of recompute."""
    path = _state(tmp_path, [
        {"job_id": f"{PAIR}__ternary__conditioned__seed1", "pair_id": PAIR},
        {"job_id": f"{PAIR}_variant__ternary__conditioned__seed1",
         "pair_id": f"{PAIR}_variant"},
    ])
    assert rerun_pair._rewrite_without(path, PAIR) == 1
    kept = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    assert [row["pair_id"] for row in kept] == [f"{PAIR}_variant"]


def test_a_row_matched_by_job_id_alone_is_dropped(tmp_path):
    """`state.jsonl` carries a "running" row written before the result, and
    those have no pair_id."""
    path = _state(tmp_path, [
        {"job_id": f"{PAIR}__ternary__conditioned__seed1", "status": "running"},
        {"job_id": "bench01_GSPT1_CRBN__ternary__conditioned__seed1"},
    ])
    assert rerun_pair._rewrite_without(path, PAIR) == 1


def test_a_torn_final_line_is_kept_rather_than_discarded(tmp_path):
    """A kill mid-append leaves one unparseable line. Dropping it would be
    this tool deciding that a job it cannot read did not happen."""
    path = tmp_path / "state.jsonl"
    path.write_text(
        json.dumps({"job_id": f"{PAIR}__ternary__conditioned__seed1",
                    "pair_id": PAIR}) + "\n"
        + json.dumps({"job_id": "bench01_x", "pair_id": "bench01_GSPT1_CRBN"}) + "\n"
        + '{"job_id": "bench03_tor\n')
    assert rerun_pair._rewrite_without(path, PAIR) == 1
    text = path.read_text()
    assert '{"job_id": "bench03_tor' in text, "the torn line was discarded"
    assert "bench01_x" in text


def test_nothing_is_written_when_nothing_matches(tmp_path):
    path = _state(tmp_path, [
        {"job_id": "bench01_GSPT1_CRBN__ternary__conditioned__seed1",
         "pair_id": "bench01_GSPT1_CRBN"},
    ])
    before = path.read_text()
    assert rerun_pair._rewrite_without(path, PAIR) == 0
    assert path.read_text() == before
    assert not path.with_suffix(path.suffix + ".bak").exists(), (
        "a backup was taken for a rewrite that did not happen"
    )


def test_the_backup_holds_what_was_there(tmp_path):
    rows = [
        {"job_id": f"{PAIR}__ternary__conditioned__seed1", "pair_id": PAIR},
        {"job_id": "bench01_x", "pair_id": "bench01_GSPT1_CRBN"},
    ]
    path = _state(tmp_path, rows)
    original = path.read_text()
    rerun_pair._rewrite_without(path, PAIR)
    backup = path.with_suffix(path.suffix + ".bak")
    assert backup.exists() and backup.read_text() == original


def test_a_second_run_does_not_overwrite_the_first_backup(tmp_path):
    """The first backup is the one that predates any of this."""
    path = _state(tmp_path, [
        {"job_id": f"{PAIR}__a", "pair_id": PAIR},
        {"job_id": "keep", "pair_id": "other"},
    ])
    original = path.read_text()
    rerun_pair._rewrite_without(path, PAIR)
    # Append another row for the same pair and rewrite again.
    with path.open("a") as handle:
        handle.write(json.dumps({"job_id": f"{PAIR}__b", "pair_id": PAIR}) + "\n")
    rerun_pair._rewrite_without(path, PAIR)
    backup = path.with_suffix(path.suffix + ".bak")
    assert backup.read_text() == original, (
        "the second run's backup replaced the original state"
    )


def test_a_kill_during_the_rewrite_leaves_the_original_intact(tmp_path, monkeypatch):
    """The reason this is an atomic replace. `write_text` truncates before it
    writes, so a kill inside that window left a partial `state.jsonl`, which
    is how a 2,360-job campaign knows what it has already run."""
    rows = [{"job_id": f"{PAIR}__a", "pair_id": PAIR}] + [
        {"job_id": f"bench01_{index}", "pair_id": "bench01_GSPT1_CRBN"}
        for index in range(200)
    ]
    path = _state(tmp_path, rows)
    original = path.read_text()

    real_replace = rerun_pair.os.replace

    def killed(src, dst):
        raise KeyboardInterrupt("killed between write and rename")

    monkeypatch.setattr(rerun_pair.os, "replace", killed)
    with pytest.raises(KeyboardInterrupt):
        rerun_pair._rewrite_without(path, PAIR)

    assert path.read_text() == original, (
        "the live state file was damaged by an interrupted rewrite"
    )
    monkeypatch.setattr(rerun_pair.os, "replace", real_replace)


def test_the_rewrite_is_a_rename_and_not_an_in_place_write():
    source = (ROOT / "tools" / "rerun_pair.py").read_text()
    assert "os.replace(" in source, (
        "the rewrite is back to writing the live file in place"
    )
    assert 'path.write_text("\\n".join(kept)' not in source


def test_a_dry_run_changes_nothing(tmp_path):
    """Without --apply it reports and stops, which is what makes it safe to
    run against a live campaign to see what it would do."""
    campaign = tmp_path / "campaign_dry"
    (campaign / "yaml").mkdir(parents=True)
    rows = [{"job_id": f"{PAIR}__ternary__conditioned__seed1", "pair_id": PAIR}]
    (campaign / "state.jsonl").write_text(json.dumps(rows[0]) + "\n")
    (campaign / "results.jsonl").write_text(json.dumps(rows[0]) + "\n")
    (campaign / "queue.jsonl").write_text(json.dumps(
        {**rows[0], "yaml": str(campaign / "yaml" / "x.yaml")}) + "\n")
    before = ((campaign / "state.jsonl").read_text(),
              (campaign / "results.jsonl").read_text())

    rerun_pair.main([PAIR, "--campaign", str(campaign)])
    assert ((campaign / "state.jsonl").read_text(),
            (campaign / "results.jsonl").read_text()) == before
