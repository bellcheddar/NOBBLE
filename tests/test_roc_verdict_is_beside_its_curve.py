"""The ROC's verdict belongs next to the ROC (F159).

The Delta tab computes an AUC in JavaScript and puts it in the chart title.
The bootstrap interval and the interpretation are computed in Python, land in
`validation.json`, and were rendered on the About tab. So a reader looking at
the curve saw one number and had to infer what it meant.

That matters most in the case spec 4.3 asks to be reported rather than
hidden: an interval entirely below 0.5, where the statistic separates the two
classes in the opposite direction to the prediction. F120 wrote that sentence
and nothing put it beside the figure.

Found by pointing browser QC at a campaign whose ROC computes, which had
never been done: every QC run so far has been against the benchmark
campaign, where the ROC is `not_computed` and the panel is an empty state.
"""
from __future__ import annotations

import json
import random
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BENCHMARK = ROOT / "campaigns" / "benchmark_20261103T192126Z"


def _scored_sievers_campaign(root: Path) -> Path:
    """A campaign whose matched-control ROC computes."""
    directory = root / "campaign"
    directory.mkdir(parents=True)
    for name in ("campaign.json", "queue.jsonl", "state.jsonl",
                 "results.jsonl", "weights.json"):
        shutil.copy(BENCHMARK / name, directory / name)
    rows = [json.loads(line) for line
            in (BENCHMARK / "scores.jsonl").read_text().splitlines()
            if line.strip()]
    chance = random.Random(20261104)
    for index in range(24):
        rows.append(_pair(f"sv_pos_{index:03d}", "degraded", chance, True))
    for index in range(96):
        rows.append(_pair(f"sv_neg_{index:03d}", "not_degraded", chance, False))
    (directory / "scores.jsonl").write_text(
        "".join(json.dumps(row) + "\n" for row in rows))

    from nobble.validate import layers
    (directory / "validation.json").write_text(
        json.dumps(layers.run(directory), indent=2, default=str))
    return directory


def _pair(pair_id: str, label: str, chance: random.Random, good: bool) -> dict:
    return {
        "pair_id": pair_id, "peptide_id": pair_id, "peptide_label": label,
        "tier": "sievers_zf", "e3_gene": "CRBN", "construct": "CRBN_CULT",
        "ligand_key": "Y70", "modality": "glue",
        "seeds_binary": 5, "seeds_ternary": 10,
        "delta_iptm": round(chance.gauss(-0.04 if good else -0.09, 0.05), 4),
        "bridge_percentile": round(chance.gauss(70 if good else 45, 15), 2),
    }


def test_the_layer_computes_on_the_fixture(tmp_path):
    """Otherwise everything below passes against an empty state."""
    from nobble.validate import layers

    campaign = _scored_sievers_campaign(tmp_path)
    outcome = layers.matched_control_roc(campaign)
    assert outcome.status == "computed", outcome.status
    assert outcome.summary["interpretation"]
    assert outcome.summary["ci95"][0] < outcome.summary["auc"] < \
        outcome.summary["ci95"][1]


def test_the_verdict_and_the_interval_render_beside_the_curve(tmp_path):
    campaign = _scored_sievers_campaign(tmp_path)
    from nobble.app import create_app

    page = create_app(str(campaign)).test_client().get("/delta")
    assert page.status_code == 200
    body = page.get_data(as_text=True)
    assert 'id="roc-verdict"' in body, (
        "the Delta tab shows a curve and no verdict, so the interpretation "
        "lives only on the About tab"
    )
    from nobble.validate import layers
    summary = layers.matched_control_roc(campaign).summary
    assert summary["interpretation"] in body
    assert f"{summary['confidence_level']}" in body
    for bound in summary["ci95"]:
        assert f"{bound:.4f}" in body, (
            "the interval is not shown, so the AUC stands alone"
        )


def test_it_is_absent_rather_than_empty_when_the_roc_has_not_computed():
    """An empty verdict line reads as a verdict of nothing."""
    from nobble.app import create_app

    body = create_app(str(BENCHMARK)).test_client().get("/delta").get_data(
        as_text=True)
    assert 'id="roc-verdict"' not in body


def test_the_verdict_is_pipeline_output_and_marked_as_such():
    """Every word of it is computed, so the copy budget excludes it.

    Marked `mono`, which is what the budget tool already treats as machine
    output. Unmarked it pushed the panel over 40 words the moment the ROC
    computed, which is the state the whole campaign exists to reach.
    """
    template = (ROOT / "nobble" / "app" / "templates" / "delta.html").read_text()
    line = template[template.index('id="roc-verdict"') - 200:
                    template.index('id="roc-verdict"') + 40]
    assert 'class="mono"' in line, line


def test_the_caption_class_the_budget_filters_is_actually_used():
    """`chart__caption` was in the filter and on nothing (F159).

    The marginal chart's caption is counts the pipeline produces and was
    marked `panel__hint`, so the budget counted it as prose and the Delta
    page read 71 words once the campaign grew enough to omit a pair.
    """
    templates = sorted((ROOT / "nobble" / "app" / "templates").glob("*.html"))
    used = any("chart__caption" in path.read_text() for path in templates)
    tool = (ROOT / "qc" / "copy_budget.mjs").read_text()
    assert "chart__caption" in tool
    assert used, (
        "the budget tool filters chart__caption and no template carries it, "
        "so the filter is dead and a chart caption counts as prose"
    )
