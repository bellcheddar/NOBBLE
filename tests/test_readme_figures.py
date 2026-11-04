"""The three numbers the README leads with, recomputed.

The README is the first thing a reader sees and it makes specific claims:
submitting the whole domain instead of a 15-residue window moves GSPT1 / CRBN
from 29.22 angstrom median pose RMSD to 1.17 and BRD4 / VHL from 19.23 to
1.71, while the IKZF1 control keeps its 15-mer in both runs and moves by
exactly 0.00.

That last one is the argument. Two pairs improving could be two pairs
improving for any reason; a control that does not move is what makes the
change attributable to the construct.

Nothing pinned them. They come out of `recovery_against_crystal`, which F103
changed, so a published claim rested on a function being edited with no test
between the two. Recomputed here from both campaigns' own results (F114).
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from nobble.numeric import finite_values, median_of  # noqa: E402
from nobble.score import poses  # noqa: E402
from nobble.validate.layers import RECOVERY_TARGETS  # noqa: E402

FRAGMENT = ROOT / "campaigns" / "benchmark_20261103T192126Z"
DOMAIN = ROOT / "campaigns" / "corrected_20261103T214331Z"


def _median(campaign: Path, pair: str) -> float | None:
    results = campaign / "results.jsonl"
    if not results.exists():
        return None
    target = RECOVERY_TARGETS[pair]
    values = []
    for line in results.read_text().splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if (row.get("complex_type") != "ternary" or row.get("status") != "done"
                or not row.get("structure")):
            continue
        if row.get("pair_id", "").split("_")[1:3] != pair.split("_")[1:3]:
            continue
        outcome = poses.recovery_against_crystal(
            row, target["pdb_id"], target["substrate_chain"],
            target["substrate_acc"], target["receptor_chain"],
            target["receptor_acc"],
        )
        if outcome.rmsd is not None:
            values.append(outcome.rmsd)
    ordered = sorted(finite_values(values))
    return median_of(ordered) if ordered else None


def _require_both():
    if not (FRAGMENT / "results.jsonl").exists() or not (DOMAIN / "results.jsonl").exists():
        pytest.skip("both campaigns are needed")


@pytest.mark.parametrize("pair,fragment,domain", [
    ("bench01_GSPT1_CRBN", 29.22, 1.17),
    ("bench02_BRD4_VHL", 19.23, 1.71),
])
def test_the_improvement_the_readme_claims(pair, fragment, domain):
    _require_both()
    assert _median(FRAGMENT, pair) == pytest.approx(fragment, abs=0.01)
    assert _median(DOMAIN, pair) == pytest.approx(domain, abs=0.01)


def test_the_control_does_not_move_at_all():
    """The claim that makes the other two mean something. IKZF1 keeps its
    15-mer in both campaigns, so if its recovery moved, something other than
    the construct changed."""
    _require_both()
    before = _median(FRAGMENT, "bench04_IKZF1_CRBN")
    after = _median(DOMAIN, "bench04_IKZF1_CRBN")
    assert before is not None and after is not None
    assert after == before, (before, after)
    assert round(abs(after - before), 2) == 0.00


def test_the_readme_still_says_what_this_checks():
    """A pinned number is only useful while the document still quotes it.
    If the README is reworded, this test should be updated with it rather
    than quietly guarding a sentence nobody reads."""
    text = (ROOT / "README.md").read_text()
    for figure in ("29.22", "1.17", "19.23", "1.71"):
        assert figure in text, f"the README no longer quotes {figure}"
    assert re.search(r"exactly\s+\*\*0\.00", text) or "exactly 0.00" in text, (
        "the README no longer makes the control claim"
    )


def test_the_bridge_reference_count_is_the_one_quoted():
    """285,996 appears twice in the README and is the reference distribution
    every bridge percentile is taken against."""
    text = (ROOT / "README.md").read_text()
    assert "285,996" in text

    # Counted in the atlas, which is where the figure comes from.
    #
    # This used to search `thresholds.toml` for a key containing "bridge"
    # with an integer value over 100,000. There is no such key: the count is
    # a property of BINMAN's atlas, not a configured cutoff, so `quoted` was
    # always None and the comparison behind `if quoted is not None` never
    # ran. The README's figure was never checked against anything, which the
    # never-executed-assertion sweep is how I found out (F152).
    from nobble.curate import binman_store as store

    counted = store.atlas_rows(
        "select count(*) n from bridge where status = 'ok'")[0]["n"]
    assert f"{counted:,}" in text, (
        f"the atlas holds {counted:,} bridges with status ok and the README "
        "quotes a different figure"
    )
    # And the spec's own statement of it, so the three agree rather than two
    # of them agreeing with each other.
    spec = (ROOT / "BUILD_SPEC.md").read_text()
    assert f"{counted:,} experimentally observed bridges" in spec, (
        f"spec 4.1 no longer states the population as {counted:,}"
    )


def test_the_readme_does_not_call_a_finished_comparison_provisional():
    """The corrected-construct comparison completed and the README said it
    was still provisional while CDK12 ran (F157).

    Checked against the published `comparison.json`, which records both the
    count and the flag, so this fails in whichever direction the two drift:
    a provisional comparison described as complete, or a complete one still
    carrying the caveat.
    """
    import json

    text = (ROOT / "README.md").read_text()
    published = ROOT / "deploy" / "atlas" / "comparison.json"
    if not published.exists():
        pytest.skip("no published comparison")
    payload = json.loads(published.read_text())
    provisional = bool(payload.get("provisional")) or bool(
        payload.get("pairs_incomplete"))

    says_provisional = "comparison\nis provisional" in text or \
        "comparison is provisional" in text
    assert says_provisional == provisional, (
        f"comparison.json says provisional={provisional} "
        f"(pairs_incomplete={payload.get('pairs_incomplete')}) and the README "
        f"{'says' if says_provisional else 'does not say'} it is provisional"
    )
    if not provisional:
        assert f"{payload['pairs_compared']} pairs compared" in text, (
            "the README does not state how many pairs the finished "
            "comparison covers"
        )
