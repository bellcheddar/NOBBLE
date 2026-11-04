"""CLAUDE.md: thresholds come from config/thresholds.toml, never Python.

The rule was being kept almost everywhere and broken in three places, one
of which was the cutoff behind the words "F6 supported": compare.py decided
"improved" and "worse" on literal 2.0s, so the number that produces the
headline conclusion could not be changed, or even found, without reading
the function. The other two decided the published `forced` flag and
whether a superposition frame is called poor, which qualifies every RMSD
measured in it.

A rule kept by habit is a rule that drifts, so this enforces it. The scan
is an AST walk rather than a regex: a float literal in a formula is fine,
and only a float literal being *compared against* is a cutoff.

Two are allowed, with their reasons. Both are constants of the method
rather than choices: neither has a value someone could sensibly tune.
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# Keyed by the comparison as it is written, so it survives the lines moving.
ALLOWED = {
    "abs(item.iptm_receptor_peptide - minimum) < 1e-9":
        "float-equality epsilon, not a cutoff: identifies which seed held the "
        "minimum without relying on exact equality",
    "low > 0.5":
        "0.5 is the definition of chance for an area under a ROC curve, not a "
        "tunable threshold",
}


def _cutoff_comparisons() -> dict[str, list[str]]:
    """Every comparison in the package against a float literal."""
    found: dict[str, list[str]] = {}
    for path in sorted((ROOT / "nobble").rglob("*.py")):
        source = path.read_text()
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if not isinstance(node, ast.Compare):
                continue
            for operand in [node.left, *node.comparators]:
                value = operand
                # -2.0 is a UnaryOp wrapping a Constant, not a Constant.
                if isinstance(value, ast.UnaryOp) and isinstance(value.op, ast.USub):
                    value = value.operand
                if isinstance(value, ast.Constant) and isinstance(value.value, float):
                    text = " ".join(
                        (ast.get_source_segment(source, node) or "").split()
                    )
                    found.setdefault(text, []).append(
                        f"{path.relative_to(ROOT)}:{node.lineno}"
                    )
                    break
    return found


# Module-level numeric constants that are not cutoffs. The first guard here
# only inspected comparisons against float literals, which is how
# MINIMUM_SEEDS = 3 in nobble/design/lift.py sat untouched: it is a cutoff
# bound to a name, and a name is where the rule is easiest to keep and
# easiest to forget. Anything not on this list must read from
# config/thresholds.toml.
ALLOWED_CONSTANTS = {
    "SEED": "a fixed random seed for reproducibility, not a cutoff applied to data",
    "LYSINE_MAX_ASA": "the reference accessible surface area of a free lysine "
                      "side chain, a physical constant rather than a choice",
    "RETRIES": "runtime control flow, not a threshold applied to data",
    "KILL_GRACE_SECONDS": "runtime control flow: how long to wait for a child "
                          "to die before abandoning it",
    "KILL_ATTEMPTS": "runtime control flow: how many kills to send inside that "
                     "window",
}


def _module_level_numeric_constants() -> dict[str, list[str]]:
    """ALL_CAPS module constants assigned a bare numeric literal."""
    found: dict[str, list[str]] = {}
    for path in sorted((ROOT / "nobble").rglob("*.py")):
        tree = ast.parse(path.read_text())
        for node in tree.body:                  # module level only
            if not isinstance(node, (ast.Assign, ast.AnnAssign)):
                continue
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for target in targets:
                if not isinstance(target, ast.Name) or not target.id.isupper():
                    continue
                value = node.value
                if isinstance(value, ast.UnaryOp) and isinstance(value.op, ast.USub):
                    value = value.operand
                if (isinstance(value, ast.Constant)
                        and isinstance(value.value, (int, float))
                        and not isinstance(value.value, bool)):
                    found.setdefault(target.id, []).append(
                        f"{path.relative_to(ROOT)}:{node.lineno}"
                    )
    return found


def test_no_cutoff_hides_in_a_module_level_constant():
    found = _module_level_numeric_constants()
    unexplained = {
        name: where for name, where in found.items() if name not in ALLOWED_CONSTANTS
    }
    assert not unexplained, (
        "numeric constant(s) that should read from config/thresholds.toml: "
        f"{unexplained}"
    )


def test_the_constant_allowances_are_all_still_real():
    found = _module_level_numeric_constants()
    stale = [name for name in ALLOWED_CONSTANTS if name not in found]
    assert not stale, f"ALLOWED_CONSTANTS lists names that no longer exist: {stale}"


def test_no_threshold_is_hard_coded_in_python():
    found = _cutoff_comparisons()
    unexplained = {text: where for text, where in found.items() if text not in ALLOWED}
    assert not unexplained, (
        "cutoff(s) compared against a float literal rather than read from "
        f"config/thresholds.toml: {unexplained}"
    )


def test_the_allowances_are_all_still_real():
    """An allowlist that outlives what it allowed is just a hole."""
    found = _cutoff_comparisons()
    stale = [text for text in ALLOWED if text not in found]
    assert not stale, f"ALLOWED lists comparisons that no longer exist: {stale}"


def test_the_moved_cutoffs_resolve_from_config():
    """Named so a reader can see which numbers these are."""
    from nobble import paths
    from nobble.score import poses, run
    from nobble.validate import compare

    scoring = paths.thresholds()["scoring"]
    assert compare.CHANGE_MARGIN_A == float(scoring["campaign_change_margin_a"])
    assert poses.FRAME_POOR_ANCHOR_A == float(scoring["frame_poor_anchor_rmsd_a"])
    assert run.FORCED_DISAGREEMENT == float(
        paths.thresholds()["conditioning"]["forced_disagreement"]
    )


def test_the_conclusion_quotes_the_configured_margin_not_a_fixed_two(monkeypatch, tmp_path):
    """The wording said "more than 2 A" while the comparison used a literal.
    Both now come from one place, so a changed threshold cannot leave the
    sentence claiming the old one.

    Tested by changing the margin and reading the sentence, not by matching
    the source. The first version of this test used a regex, which matched
    only the first fragment of a multi-part f-string and so would have
    passed with "2 A" hard-coded in any later fragment.
    """
    from nobble.validate import compare as compare_module

    def fake_recovery(campaign):
        if "corrected" in campaign.name:
            return {
                "corr01_GSPT1_CRBN": {"median_rmsd": 5.0, "poses": 10, "anchor_rmsd": 1.0},
                "corr04_IKZF1_CRBN": {"median_rmsd": 4.0, "poses": 10, "anchor_rmsd": 1.0},
            }
        return {
            "bench01_GSPT1_CRBN": {"median_rmsd": 10.0, "poses": 10, "anchor_rmsd": 1.0},
            "bench04_IKZF1_CRBN": {"median_rmsd": 4.0, "poses": 10, "anchor_rmsd": 1.0},
        }

    monkeypatch.setattr(compare_module, "_recovery_by_pair", fake_recovery)
    monkeypatch.setattr(compare_module, "CHANGE_MARGIN_A", 3.0)

    baseline = tmp_path / "benchmark_x"
    corrected = tmp_path / "corrected_x"
    baseline.mkdir()
    corrected.mkdir()
    conclusion = compare_module.compare(baseline, corrected)["conclusion"]

    assert conclusion.startswith("F6 supported"), conclusion
    assert "3 A" in conclusion, conclusion
    assert "2 A" not in conclusion, conclusion
