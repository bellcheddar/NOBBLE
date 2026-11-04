"""Refinement's numbers, and which of them may be compared (F137).

Tier 2 writes `scores_tier2.jsonl`. The atlas has published it since tier 2's
output was made visible and the app never read it, so the pose catalogue
offered refined coordinates with nothing saying whether they were better.

Showing them is easy and showing the wrong ones is the risk. `iptm_min` is a
minimum over seeds, and a minimum falls as diffusion samples are added, so
tier 2's would sit below tier 1's before anything physical had changed.
Presented as a before-and-after that reads as the refinement working. So the
comparison is a whitelist, and these are the checks on it.
"""
import json
import re
import subprocess
import sys
from pathlib import Path

from nobble import sampling

ROOT = Path(__file__).resolve().parents[1]

# A name that says the quantity is a minimum over seeds, or built from one.
ORDER_STATISTIC = re.compile(r"iptm_min|^delta_iptm|^nobble_score$")


def _a_real_score_row() -> dict:
    """One row from a campaign that has actually been scored."""
    for scores in sorted((ROOT / "campaigns").glob("*/scores.jsonl")):
        for line in scores.read_text().splitlines():
            if line.strip():
                return json.loads(line)
    raise AssertionError("no scored campaign on disk to check the keys against")


def test_nothing_comparable_is_an_order_statistic():
    offending = [key for key in sampling.COMPARABLE if ORDER_STATISTIC.search(key)]
    assert not offending, (
        f"{offending} are minima over seeds or built from them, so tier 2's "
        "value is lower than tier 1's before any physical change"
    )


def test_the_two_sets_do_not_overlap():
    assert not set(sampling.COMPARABLE) & set(sampling.WITHHELD)


def test_every_comparable_key_exists_in_a_real_score_row():
    """Otherwise the panel is empty whatever runs.

    A whitelist of keys that scoring does not emit fails silently: `compare`
    skips a key absent from both sides, so a renamed field leaves a panel
    that renders nothing and reports no error.
    """
    row = _a_real_score_row()
    missing = [key for key in sampling.COMPARABLE if key not in row]
    assert not missing, (
        f"{missing} are whitelisted for comparison and absent from "
        "scores.jsonl, so the refinement panel would never show them"
    )


def test_every_order_statistic_in_a_real_row_is_named_as_withheld():
    """The honesty check on the withheld list.

    The whitelist already keeps a new order statistic out of the panel, so
    this is not what stops one being shown. It is what stops the withheld
    list quietly becoming a partial account of what is being held back,
    which is what a reader of the panel is relying on it to be.
    """
    row = _a_real_score_row()
    found = {key for key in row if ORDER_STATISTIC.search(key)}
    missing = sorted(found - set(sampling.WITHHELD))
    assert not missing, (
        f"{missing} are order statistics in scores.jsonl that the panel does "
        "not list as withheld"
    )


def test_compare_skips_what_neither_side_has():
    report = sampling.compare({"bridge_percentile": 50.0}, {"bridge_percentile": 70.0})
    assert [row["key"] for row in report["rows"]] == ["bridge_percentile"]
    assert report["rows"][0]["change"] == 20.0


def test_compare_withholds_the_change_rather_than_inventing_one():
    """A change against a missing value is not zero."""
    report = sampling.compare({}, {"bridge_percentile": 70.0})
    assert len(report["rows"]) == 1
    assert report["rows"][0]["tier1"] is None
    assert report["rows"][0]["change"] is None


def test_compare_does_not_subtract_a_string():
    report = sampling.compare(
        {"bridge_formation_rate": "n/a"}, {"bridge_formation_rate": 0.5})
    assert report["rows"][0]["change"] is None


def test_sampling_imports_nothing():
    """The app serves a precomputed atlas on a droplet with no scoring stack.

    An import of nobble.score here would take the Pose tab down on the
    droplet, which is where this is read.
    """
    source = (ROOT / "nobble" / "sampling.py").read_text()
    imports = re.findall(r"^\s*(?:from|import)\s+(\S+)", source, re.MULTILINE)
    assert set(imports) <= {"__future__"}, imports


def test_the_pose_template_renders_the_comparison():
    page = (ROOT / "nobble" / "app" / "templates" / "pose.html").read_text()
    assert 'id="refinement-rows"' in page
    assert "noteRefinement(data);" in page, (
        "the renderer is defined and never called, so the panel stays hidden"
    )


def test_the_api_returns_null_for_a_pair_that_was_not_refined():
    """Run in a subprocess with the campaign pinned at creation.

    `data.configure()` on a directory with no campaign falls back to the
    newest real one, so an in-process check here would answer about whatever
    campaign happens to be on disk (F122).
    """
    campaign = next((path for path in sorted((ROOT / "campaigns").glob("*"))
                     if (path / "scores.jsonl").exists()
                     and not (path / "scores_tier2.jsonl").exists()), None)
    if campaign is None:
        return          # no unrefined scored campaign to check against
    script = (
        "import json, sys\n"
        "from nobble.app import create_app\n"
        f"app = create_app({str(campaign)!r})\n"
        "client = app.test_client()\n"
        "rows = [json.loads(l) for l in "
        f"open({str(campaign / 'scores.jsonl')!r}) if l.strip()]\n"
        "pair = rows[0]['pair_id']\n"
        "body = client.get('/api/pair/' + pair + '/structures').get_json()\n"
        "print(json.dumps({'refinement': body['refinement']}))\n"
    )
    done = subprocess.run([sys.executable, "-c", script], cwd=ROOT,
                          capture_output=True, text=True)
    assert done.returncode == 0, done.stderr[-2000:]
    assert json.loads(done.stdout.strip().splitlines()[-1])["refinement"] is None
