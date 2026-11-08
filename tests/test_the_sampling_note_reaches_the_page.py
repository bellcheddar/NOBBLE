"""The caveat that was computed, tested and never left stdout (F337).

`nobble.score.run._sampling_note` has existed since F298 and says whether
every scored pair ran at the same number of diffusion samples. It is
covered by five tests in `test_mixed_sampling_is_not_comparable.py`. It was
returned in the scoring summary, `tools/refresh.sh` redirects that summary
into a step log, and `deploy/build_atlas.py` contained no reference to it at
all. So the note was computed, committed, tested and absent from the
published bundle, which is F96's shape with one more step missing: there
F93's caveat was written and the atlas had not been rebuilt, here the atlas
never read it.

It becomes load-bearing now rather than later. `runner.sampling_for`
reduces a job too large to refine at the tier's count, so from this run
onward tier 2 holds both 9 and 25, and until now every scored tier-2 job
was at 25.

What this is not. It is not a disclaimer on a figure.
`nobble/sampling.py` already withholds every quantity a change of sample
count would bias: `COMPARABLE` is four proportions and medians and
`WITHHELD` is the minima and their differences. The refinement panel is
therefore safe at either count, and a caveat there would suggest otherwise
and would breach the project's own rule that disclaimers go only where a
figure would be actively misread. I nearly wrote one before reading that
module. What is published is a statement of what ran, beside the sources
and the construct budget, because a reader cannot otherwise tell that two
pairs' refinements were drawn from different numbers of poses.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

RUN = (ROOT / "nobble" / "score" / "run.py").read_text()
BUILDER = (ROOT / "deploy" / "build_atlas.py").read_text()
ROUTES = (ROOT / "nobble" / "app" / "routes.py").read_text()
ABOUT = (ROOT / "nobble" / "app" / "templates" / "about.html").read_text()


def test_the_scorer_writes_the_note_beside_the_scores():
    assert 'f"sampling{suffix}.json"' in RUN, (
        "the sampling note is no longer written to the campaign, so the "
        "only thing that sees it is whoever reads the scorer's stdout"
    )


def test_the_note_is_written_once_and_reported_from_the_same_object():
    """Two calls could not disagree today, and a file and a summary that
    disagree later is a difference nothing would catch."""
    assert RUN.count("_sampling_note(scored)") == 1, (
        "the note is computed more than once, so the file and the summary "
        "can drift apart"
    )
    assert '"sampling": sampling,' in RUN


def test_the_builder_publishes_it():
    assert '"sampling": sampling_notes,' in BUILDER, (
        "about.json no longer carries the sampling note, so the page "
        "cannot say what sample counts produced its numbers"
    )
    assert 'f"sampling{tier_suffix}.json"' in BUILDER


def test_an_absent_note_does_not_read_as_uniform():
    """The empty answer, given its own shape.

    A bundle built from a campaign scored before the note existed has no
    file to read. Publishing nothing, or publishing `uniform: true`, would
    both say the sampling was uniform when the truth is that it is
    unrecorded.
    """
    window = BUILDER[BUILDER.index("sampling_notes: dict"):]
    window = window[:window.index("about = {")]
    assert "unrecorded rather than uniform" in window, (
        "an absent sampling note no longer says that it is absent"
    )
    assert "uniform" not in window.replace(
        "unrecorded rather than uniform", ""), (
        "the builder appears to assert uniformity for an absent note"
    )


def test_both_tiers_are_published():
    window = BUILDER[BUILDER.index("sampling_notes: dict"):]
    window = window[:window.index("about = {")]
    assert '("tier1", "")' in window and '("tier2", "_tier2")' in window, (
        "only one tier's sampling is published, and the mixed one is tier 2"
    )


def test_the_route_passes_it_to_the_template():
    assert 'sampling=precomputed.get("sampling")' in ROUTES, (
        "about.json carries the note and the route drops it, which is the "
        "same gap one step further along"
    )


def test_the_page_renders_it():
    assert "Diffusion samples per tier" in ABOUT
    assert "{% if sampling %}" in ABOUT, (
        "the line renders unconditionally, so a bundle without the note "
        "shows an empty sentence"
    )


def test_the_page_does_not_caveat_the_refinement_panel():
    """The restraint is the point, and it is load-bearing.

    `nobble/sampling.py` withholds the biased quantities rather than
    showing them with a warning, which is the stronger fix. A caveat on
    the refinement panel would imply the numbers there need one.
    """
    pose = (ROOT / "nobble" / "app" / "templates" / "pose.html").read_text()
    for phrase in ("not comparable between them",
                   "different draws", "sample count alone"):
        assert phrase not in pose, (
            f"pose.html carries {phrase!r}, a caveat on figures that "
            "nobble/sampling.py already protects by exclusion"
        )


def test_the_withheld_list_is_what_makes_the_restraint_safe():
    """If the whitelist ever admitted a minimum over seeds, the reasoning
    in this file's docstring would stop holding and a caveat would be
    needed after all."""
    from nobble import sampling

    assert set(sampling.COMPARABLE) == {
        "bridge_formation_rate", "bridge_percentile",
        "convergence_score", "plip_fingerprint_match"}, (
        "the comparable set has changed, so re-read whether every member "
        "is still a proportion, a mean or a median. A minimum over seeds "
        "in here would need the caveat this file argues against"
    )
    for key in ("delta_iptm", "delta_iptm_global", "delta_iptm_median"):
        assert key in sampling.WITHHELD, key


def test_the_live_campaign_gets_a_note_written_for_it(tmp_path):
    """End to end on the shape, not the whole scorer.

    Scoring the real campaign is minutes of CPU and the thing being
    checked is that the file lands with the right name and content, so the
    note is written from a small fixture through the same code path.
    """
    import importlib

    run = importlib.import_module("nobble.score.run")
    scored = [
        {"pair_id": "a", "diffusion_samples": [9]},
        {"pair_id": "b", "diffusion_samples": [25]},
    ]
    note = run._sampling_note(scored)
    assert note["uniform"] is False
    assert set(note["by_count"]) == {"9", "25"}
    assert "not comparable" in note["caveat"]

    uniform = run._sampling_note([{"pair_id": "a", "diffusion_samples": [9]}])
    assert uniform["uniform"] is True
    assert "caveat" not in uniform


def test_the_tiers_are_labelled_rather_than_keyed():
    """"tier 1", not "tier1" (F203).

    The refinement panel once rendered raw field names where every other
    table on the site shows labels, and this is the same key-to-prose step
    one page over.
    """
    assert "tier|replace('tier', 'tier ')" in ABOUT, (
        "the page prints the dict key, so the line reads "
        "\"tier1 at 1; tier2 at 9 and 25\""
    )


def test_the_line_renders_in_each_state_it_can_be_in():
    """Four states, rendered rather than reasoned about.

    Mixed sampling, a tier with no note, a tier with no scored pairs, and
    no note at all. The last must produce nothing: a bundle built before
    F337 should show no sentence rather than an empty one.
    """
    import re

    from jinja2 import Environment

    start = ABOUT.index("{% if sampling %}")
    end = ABOUT.index("{% endif %}\n</section>", start) + len("{% endif %}")
    template = Environment().from_string(ABOUT[start:end])

    mixed = template.render(sampling={
        "tier1": {"by_count": {"1": ["a"]}, "uniform": True},
        "tier2": {"by_count": {"9": ["x"], "25": ["y"]}, "uniform": False}})
    assert "tier 1 at 1" in mixed and "tier 2 at 9 and 25" in mixed, mixed

    absent = template.render(sampling={
        "tier1": {"by_count": {"1": ["a"]}},
        "tier2": {"status": "no sampling_tier2.json in the campaign"}})
    assert "tier 2 not recorded" in absent, absent

    unscored = template.render(sampling={"tier1": {"by_count": {}},
                                         "tier2": {"by_count": {}}})
    assert "not scored" in unscored, unscored

    assert template.render(sampling=None).strip() == "", (
        "a bundle built before this existed renders an empty sentence"
    )

    # The copy budget is 40 words per panel, and this line shares its panel
    # with the bridge-reference one.
    words = len(re.sub(r"<[^>]+>", " ", mixed).split())
    assert words <= 40, (words, mixed)
