"""The facts that answer "are these two numbers about the same thing".

Five times in one day I compared a figure against another that looked
comparable and was not: a pre-filter manifest against a post-filter queue,
an atlas preview against an assembled scan, a cost against a different
parent, a grep against a split f-string, a field name against one that has
never existed. Every answer was already recorded somewhere in the project.
The failure was not reading, and the remedy is not more care but fewer
greps, so `tools/status.sh` prints them together (F92).

Three facts, each of which was a false alarm of mine:

- what the assembler dropped and why, because the manifest emits both
  conditionings for every ternary and the assembler drops the conditioned
  ones with no pocket, which is the ten jobs I counted as missing;
- whether any input is stale, because that is why the atlas build refuses
  and a refusal discovered rather than expected reads as a failure;
- which degron the design ranking chooses against which the site publishes,
  because those disagreed for the whole project's life (F89).
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

PYTHON = str(ROOT.parent / "BINMAN" / ".pixi" / "envs" / "default" / "bin" / "python")


def _provenance(extra_env: dict | None = None) -> str:
    completed = subprocess.run(
        [PYTHON, "tools/provenance.py"], cwd=str(ROOT),
        capture_output=True, text=True, timeout=300,
        env={**os.environ, "PYTHONPATH": str(ROOT),
             "KMP_DUPLICATE_LIB_OK": "TRUE", **(extra_env or {})},
    )
    assert completed.returncode == 0, completed.stderr[-800:]
    return completed.stdout


def test_it_reports_what_the_assembler_dropped():
    """The ten jobs I counted as missing from the queue. The manifest emits
    both conditionings and the assembler drops the ones with no pocket."""
    out = _provenance()
    assert "job(s) emitted" in out, out
    assert "conditioned dropped for having no pocket" in out, out


def test_it_reports_whether_any_input_is_stale():
    """Why the atlas build refuses, stated before it refuses."""
    out = _provenance()
    assert "stale inputs" in out, out
    assert ("the atlas build refuses" in out
            or "nothing to refuse" in out), out


def test_it_reports_both_design_targets():
    """The pair of values F89 was about: what the ranking chooses and what
    the site says. Printing one without the other is what let them differ
    for the whole project's life."""
    out = _provenance()
    assert "design target" in out, out
    assert "ranking says" in out and "site says" in out, out


def test_the_disagreement_is_marked_when_they_differ(tmp_path):
    """The negative control. The line is only worth printing if a
    disagreement is visible in it, and today they agree, so this feeds it a
    published design file naming a different parent."""
    import json
    import shutil

    source = ROOT / "deploy" / "atlas"
    if not (source / "design.json").exists():
        pytest.skip("no published atlas")

    # A copy, pointed at through NOBBLE_ATLAS_PUBLISHED. This used to
    # perturb the published design.json and restore it in a `finally`,
    # which works until a run is killed in between and leaves the live
    # bundle naming a parent that is not the ranked one (F154).
    atlas = tmp_path / "atlas"
    shutil.copytree(source, atlas,
                    ignore=shutil.ignore_patterns("structures"))
    (atlas / "structures").mkdir(exist_ok=True)
    env = {"NOBBLE_ATLAS_PUBLISHED": str(atlas)}
    design = atlas / "design.json"

    payload = json.loads(design.read_text())
    preview = payload.setdefault("preview", {})
    parent = preview.setdefault("parent", {})
    parent["peptide_id"] = "benchmark_not_the_ranked_one"
    design.write_text(json.dumps(payload))
    out = _provenance(env)
    assert "the site and the ranking disagree" in out, out

    # And the marker is gone once the copy agrees again, which is what makes
    # the line above a statement about the disagreement rather than about
    # this test having run at all.
    shutil.copy(source / "design.json", design)
    assert "the site and the ranking disagree" not in _provenance(env)


def test_the_status_script_calls_it():
    """The wiring (F40). A module nothing runs is the shape this finding is
    about."""
    source = (ROOT / "tools" / "status.sh").read_text()
    assert "tools/provenance.py" in source
    assert source.index("-- provenance") < source.index("tools/provenance.py")


def test_the_recomputed_cost_count_reaches_the_report():
    """F101 split atlas drift into values that need explaining and costs
    that move with new timings. The split is only useful if the second
    number is visible: a report saying "in step" while sixty-odd costs
    await the next rebuild tells the operator less than it knows, which is
    the shape of F79, F91 and F96."""
    source = (ROOT / "tools" / "provenance.py").read_text()
    assert 'report_.get("recomputed")' in source, (
        "provenance computes the atlas drift and drops the recomputed count"
    )
    assert "recomputed from new timings" in source
