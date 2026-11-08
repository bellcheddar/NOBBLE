"""Tier B is 1,540 jobs and nothing publishes them (F348).

`deploy/build_atlas.py` contains no reference to Tier B and neither does
`nobble/app/`. So when the arm finishes, its scores are scored, read by
`check_registered.py` for F253, and go no further: not into the published
bundle, not onto the site. About 33 hours of compute whose only product is a
file on the Mac Studio, which is the thing
`tests/test_atlas_is_read.py` was written about one level in: "a file goes
into the published atlas so that the app can serve it, and one with no
reader in the app is compute whose only product is a file on a droplet".

**This test does not fix that, and deliberately does not.** How Tier B
publishes is an open item in BUILD_SPEC.md section 408, a ranked list or an
abstention-heavy list where Head C declines below a confidence floor, and
DECISIONS.md records it as explicitly Marc's: "that would be writing spec
content into the build when BUILD_SPEC.md is authoritative and the question
is explicitly Marc's". Choosing one and building it would answer his
question for him.

What that decision deferred on was the constructs, which were unfilled at
the time: "the two questions arrive together, so the presentation decision
is best made when the constructs are chosen rather than now". They are
chosen (D-NOB-072), the arm is assembled as `tier_b_20261105T202811Z` and it
is queued as stage 4b. The condition has been met and the decision is ripe.

So this is a tripwire rather than a feature. It passes while Tier B has no
scores, and fails the moment it has them and nothing publishes them, which
is the only moment at which the gap costs anything and the moment it would
otherwise pass unnoticed. A successful chain run would end with the atlas
rebuilt, 33 hours on disk, and nobody told.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
BUILDER = (ROOT / "deploy" / "build_atlas.py").read_text()


def _tier_b():
    found = sorted(ROOT.glob("campaigns/tier_b_*"))
    found = [d for d in found if (d / "campaign.json").exists()]
    return found[-1] if found else None


def test_the_gap_is_real_and_recorded():
    """Asserted, so that closing it also retires this file.

    If the builder gains a Tier B reader, this fails and whoever added it
    is sent here to delete the tripwire rather than leaving a test that
    describes a gap that has gone.
    """
    assert "tier_b" not in BUILDER, (
        "deploy/build_atlas.py now mentions Tier B, so the gap F348 is "
        "about may be closed. Check whether it publishes the arm's scores, "
        "and if so delete this file: a tripwire for a gap that has gone is "
        "the stale allowance F119 is about"
    )


def test_tier_b_scores_are_published_once_they_exist():
    """The tripwire. Passes until the arm is scored, then fails.

    Scored and unpublished is the state this exists to catch, and it is the
    state a successful chain run would reach.
    """
    campaign = _tier_b()
    if campaign is None:
        pytest.skip("no Tier B campaign on this checkout")
    scores = campaign / "scores.jsonl"
    if not scores.exists():
        pytest.skip(
            "Tier B is assembled and queued as stage 4b and has not been "
            "scored, so there is nothing to publish yet. This test becomes "
            "live the moment it has been")
    rows = [line for line in scores.read_text().splitlines() if line.strip()]
    if not rows:
        pytest.skip("Tier B's scores.jsonl is empty")

    pytest.fail(
        f"Tier B has {len(rows)} scored pair(s) and nothing publishes them: "
        "deploy/build_atlas.py has no Tier B reader and nobble/app/ has no "
        "Tier B route. That is about 33 hours of compute with no path to "
        "the site. How it should publish is BUILD_SPEC.md item 3, a ranked "
        "list or an abstention-heavy one, and DECISIONS.md records that as "
        "Marc's decision rather than this build's. The constructs it was "
        "waiting on are chosen, so the decision is ripe: ask, then publish. "
        "See F348."
    )


def test_the_arm_is_queued_so_the_tripwire_will_fire():
    """A tripwire on a stage that never runs is decoration.

    This is the part that makes the test above worth having: the arm is
    assembled, queued in the chain, and its preflight passes, so it will
    produce scores.
    """
    campaign = _tier_b()
    if campaign is None:
        pytest.skip("no Tier B campaign on this checkout")
    chain = (ROOT / "tools" / "run_chain.sh").read_text()
    assert "assemble_tier_b" in chain, (
        "the chain no longer assembles Tier B, so this arm may have been "
        "dropped and this file should go with it"
    )
    assert 'run_queue.sh --campaign "$TIERB"' in chain
    assert "nobble.score.run --campaign \"$TIERB\"" in chain, (
        "the chain no longer scores Tier B, which is a larger problem than "
        "the publishing gap: the arm would run and never be read at all"
    )
    queue = campaign / "queue.jsonl"
    assert queue.exists(), "the assembled arm has no queue"
    jobs = [line for line in queue.read_text().splitlines() if line.strip()]
    assert len(jobs) > 1000, (
        f"only {len(jobs)} job(s) queued, where D-NOB-073 specifies 1,540: "
        "check the arm is intact before trusting the gap this file names"
    )


def test_the_arms_internal_control_is_what_makes_publishing_meaningful():
    """Recorded here because it bears on the open decision.

    D-NOB-073 gave the arm a composition-matched scramble per positive, so
    a Tier B result does not need a cross-arm comparison or a confidence
    floor to mean something: each positive has its own negative. That is a
    fact about the data rather than a presentation choice, and it is the
    fact the open item should be decided against.
    """
    campaign = _tier_b()
    if campaign is None:
        pytest.skip("no Tier B campaign on this checkout")
    rows = [json.loads(line) for line
            in (campaign / "queue.jsonl").read_text().splitlines()
            if line.strip()]
    pairs = {row["pair_id"] for row in rows}
    positives = {p for p in pairs if p.startswith("tb_pos_")}
    scrambles = {p for p in pairs if p.startswith("tb_neg_")}
    assert positives and scrambles, (sorted(pairs)[:3],)
    unmatched = {p for p in positives
                 if "tb_neg_" + p[len("tb_pos_"):] not in scrambles}
    assert unmatched == set(), (
        f"{len(unmatched)} positive(s) have no matched scramble, so the "
        "arm's internal control is incomplete and publishing it would need "
        "the cross-arm comparison D-NOB-073 avoided"
    )
    assert len(positives) == len(scrambles) == 77, (
        len(positives), len(scrambles))


def test_tier_b_is_the_only_arm_with_no_reader_in_the_builder():
    """Which is what makes F348 a gap rather than a policy.

    If the project published no arms, Tier B's absence would be
    consistency. Measured on `deploy/build_atlas.py`, it is the exception:

        benchmark   15 mentions, published as benchmark.json
        corrected    5 mentions, published as comparison.json
        design       9 mentions, published as design.json
        campaign    63 mentions, published as results, scores, structures
        tier_b       0 mentions

    Every assembled arm reaches the bundle except this one.
    """
    counts = {arm: BUILDER.count(arm)
              for arm in ("benchmark", "corrected", "design", "campaign",
                          "tier_b")}
    silent = sorted(arm for arm, n in counts.items() if n == 0)
    assert silent == ["tier_b"], (
        "the set of arms with no reader in the builder has changed, so "
        f"re-read F348 against it: {counts}"
    )
    # And each of the others publishes a named document, so "mentions" is
    # not mistaken for "handles".
    for document in ("benchmark.json", "comparison.json", "design.json"):
        assert f'(OUT / "{document}")' in BUILDER, document


def test_each_arm_that_is_published_is_also_assembled_somewhere():
    """The converse, so this file does not only argue one direction.

    A builder reading an arm nothing assembles would be the mirror defect:
    a publish path for compute that never happens.
    """
    assemblers = ""
    for name in ("nobble/execute/campaign.py", "nobble/design/assemble.py"):
        assemblers += (ROOT / name).read_text()
    for arm, expected in (("benchmark", "benchmark"),
                          ("design", "design"),
                          ("tier_b", "tier_b")):
        assert f'fresh_campaign("{expected}")' in assemblers or \
               f"latest(\"{expected}\")" in assemblers or \
               f"'{expected}'" in assemblers, (
            f"{arm} is referenced by the builder or this test and nothing "
            "assembles it"
        )


def test_the_dropped_positives_note_is_still_there_to_be_read():
    """The explanation of F349's ceiling, which has no consumer (F349b).

    `sievers_matched_set` returns `dropped_positives` and a `note` saying
    why those eight cannot simply be run under pomalidomide: "running them
    under pomalidomide regardless would put a zinc finger the screen calls
    undegraded by that drug on the positive side of the ROC". Nothing in
    `nobble/`, `tools/`, `deploy/` or the app reads either.

    Not surfaced here, because where it belongs is a presentation question
    and F349 now carries the reasoning where the recommendation is. This
    asserts the note still exists and still says that, so the one place the
    reasoning lives cannot be deleted silently: it is the answer to the
    first objection anyone will raise against recovering the eight, and
    getting it wrong would manufacture eight positives out of eight
    negatives.
    """
    source = (ROOT / "nobble" / "curate" / "peptides.py").read_text()
    assert '"dropped_positives": dropped,' in source, (
        "the curation no longer reports which positives it dropped, so the "
        "ceiling F349 measured has no record of its cause"
    )
    assert "undegraded by that drug on the" in source, (
        "the note explaining why the dropped eight cannot be run under "
        "pomalidomide is gone. It is the answer to the obvious shortcut and "
        "F349 quotes it"
    )
    findings = (ROOT / "FINDINGS.md").read_text()
    assert "would manufacture eight positives out of eight negatives" in \
        findings, (
        "F349 no longer carries the reasoning, which leaves it only in a "
        "return value nothing reads"
    )
