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


def test_a_scored_campaign_still_exits_zero(tmp_path):
    """The change must not make every refresh fail.

    **On a copy, never the live campaign (F326e).** The first version of this
    pointed `--limit 1` at `latest("campaign")`, so running it replaced 158
    scored pairs with one, and then passed on every later run precisely
    because the file was already truncated. A test that damages the thing it
    reads and is then satisfied by the damage is worse than no test.

    The copy carries `results.jsonl` only, which is what the scorer reads.
    `--limit` and a few rows keep it quick, and the point is the exit code,
    not the scoring.
    """
    import json
    import shutil

    import pytest

    from nobble.execute.campaign import latest

    source = latest("campaign") or latest("benchmark")
    if source is None or not (source / "results.jsonl").exists():
        pytest.skip("no campaign with results on this checkout")

    campaign = tmp_path / "campaign_copy"
    campaign.mkdir()
    rows = [line for line in
            (source / "results.jsonl").read_text().splitlines() if line.strip()]
    # One pair's worth is enough to score. Taken by pair id so the rows
    # belong together rather than being the first N of a mixed set.
    first_pair = json.loads(rows[0]).get("pair_id")
    kept = [line for line in rows
            if json.loads(line).get("pair_id") == first_pair]
    assert kept, "no row carried a pair id"
    (campaign / "results.jsonl").write_text("\n".join(kept) + "\n")
    shutil.copy(source / "queue.jsonl", campaign / "queue.jsonl")

    done = subprocess.run(
        [str(SCI), "-m", "nobble.score.run", "--campaign", str(campaign),
         "--tier", "1", "--no-plip"],
        capture_output=True, text=True, cwd=ROOT,
        env={"PYTHONPATH": str(ROOT), "KMP_DUPLICATE_LIB_OK": "TRUE",
             "PATH": "/usr/bin:/bin"})
    assert done.returncode == 0, done.stderr[-400:]
    # And the live campaign is untouched, which is the property that failed.
    assert (source / "scores.jsonl").exists()


def test_no_test_in_this_file_scores_the_live_campaign():
    """The property, asserted rather than remembered.

    Every subprocess call here must name a path under `tmp_path`. One that
    names `latest(...)` directly is how F326e happened, and the damage is
    silent: the scorer writes what it scores and says nothing about what it
    replaced.
    """
    import re

    source = Path(__file__).read_text()
    body = source[source.index("def test_"):]
    # `latest(` may appear only where a copy is made from it.
    for match in re.finditer(r'"--campaign",\s*str\((\w+)\)', body):
        name = match.group(1)
        assert name in ("campaign",), (
            f"a scorer call takes --campaign str({name}); it must be a "
            "tmp_path copy bound to `campaign`")


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


# --------------------------------------------------------------------------- #
# The same question of the preflight (F323)
# --------------------------------------------------------------------------- #

def test_an_empty_queue_is_a_preflight_refusal(tmp_path):
    """`jobs: 0, pairs: 0, ok: true` was the answer, and the chain gates a
    52-hour run on that flag. Every check iterates the jobs, so with none
    there are no errors and `ok: not errors` came out true: a campaign whose
    queue failed to assemble read as one that had passed every check."""
    campaign = tmp_path / "campaign_empty"
    campaign.mkdir()
    (campaign / "queue.jsonl").write_text("")
    done = subprocess.run(
        [str(SCI), str(ROOT / "tools" / "preflight.py"), str(campaign)],
        capture_output=True, text=True, cwd=ROOT,
        env={"PYTHONPATH": str(ROOT), "KMP_DUPLICATE_LIB_OK": "TRUE",
             "PATH": "/usr/bin:/bin"})
    assert done.returncode != 0, done.stdout
    payload = json.loads(done.stdout)
    assert payload["ok"] is False
    assert payload["jobs"] == 0
    assert "examining nothing" in json.dumps(payload["errors"])


def test_a_missing_queue_and_an_empty_one_are_told_apart(tmp_path):
    """Different remedies: assemble the campaign, against find out why its
    assembler emitted no jobs."""
    missing = tmp_path / "no_queue"
    missing.mkdir()
    empty = tmp_path / "empty_queue"
    empty.mkdir()
    (empty / "queue.jsonl").write_text("")

    sys.path.insert(0, str(ROOT / "tools"))
    import preflight as P

    assert "no queue" in P.preflight(missing)["status"]
    assert "empty queue" in P.preflight(empty)["status"]


def test_the_real_campaigns_still_pass():
    """The change must not refuse a campaign that is fine, and three are on
    disk to check it against."""
    import pytest

    sys.path.insert(0, str(ROOT / "tools"))
    import preflight as P

    checked = 0
    for name in ("campaign_", "design_", "tier_b_"):
        found = sorted((ROOT / "campaigns").glob(f"{name}*"))
        if not found or not (found[-1] / "queue.jsonl").exists():
            continue
        report = P.preflight(found[-1])
        assert report["ok"] is True, (found[-1].name, report.get("errors", [])[:2])
        assert report["jobs"] > 0
        checked += 1
    if not checked:
        pytest.skip("no campaign with a queue on this checkout")


# --------------------------------------------------------------------------- #
# --limit is a truncating flag (F326)
# --------------------------------------------------------------------------- #

def test_limit_refuses_to_shrink_an_existing_scores_file(tmp_path):
    """The flag that cost 157 rows. The scorer writes what it scores, so
    narrowing what it scores narrows the file, and `--limit` reads as a
    sampling flag."""
    campaign = tmp_path / "campaign_x"
    campaign.mkdir()
    (campaign / "scores.jsonl").write_text(
        "\n".join(json.dumps({"pair_id": f"p{i}"}) for i in range(5)) + "\n")
    done = subprocess.run(
        [str(SCI), "-m", "nobble.score.run", "--campaign", str(campaign),
         "--tier", "1", "--no-plip", "--limit", "1"],
        capture_output=True, text=True, cwd=ROOT,
        env={"PYTHONPATH": str(ROOT), "KMP_DUPLICATE_LIB_OK": "TRUE",
             "PATH": "/usr/bin:/bin"})
    assert done.returncode == 4, done.stdout + done.stderr
    assert "would replace the 5 scored pair(s)" in done.stderr, done.stderr
    # And it did not write.
    assert len((campaign / "scores.jsonl").read_text().strip().splitlines()) == 5


def test_limit_is_allowed_when_it_cannot_shrink_anything(tmp_path):
    """A scratch campaign with no scores, or a limit at least as large as
    what is held, is what the flag is for."""
    campaign = tmp_path / "campaign_y"
    campaign.mkdir()
    (campaign / "queue.jsonl").write_text("")
    done = subprocess.run(
        [str(SCI), "-m", "nobble.score.run", "--campaign", str(campaign),
         "--tier", "1", "--no-plip", "--limit", "1"],
        capture_output=True, text=True, cwd=ROOT,
        env={"PYTHONPATH": str(ROOT), "KMP_DUPLICATE_LIB_OK": "TRUE",
             "PATH": "/usr/bin:/bin"})
    # Reaches the scorer, which then refuses for F322's reason instead.
    assert done.returncode == 3, done.stdout + done.stderr
    assert "wrote nothing" in done.stderr


def test_the_refusal_is_confined_to_the_limit_branch():
    """The chain never passes --limit, so this must not be reachable
    without it: a change outside that branch would touch a 50-hour run."""
    import ast

    source = (ROOT / "nobble" / "score" / "run.py").read_text()
    tree = ast.parse(source)
    main = next(node for node in ast.walk(tree)
                if isinstance(node, ast.FunctionDef) and node.name == "main")
    guards = [node for node in ast.walk(main)
              if isinstance(node, ast.If)
              and isinstance(node.test, ast.Attribute)
              and node.test.attr == "limit"]
    assert guards, "the refusal is not inside an `if args.limit:` branch"
    returns = [node.value.value for node in ast.walk(guards[0])
               if isinstance(node, ast.Return)
               and isinstance(node.value, ast.Constant)]
    assert 4 in returns
