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


# Inline integer comparisons. The float sweep missed these and so did the
# constant sweep, which is how `len(labelled) < 25` decided whether the
# weights are published as "indicative" and `len(positives) < 3` decided
# whether the headline curve is drawn at all.
#
# Comparisons against 0 and 1 are not swept: they are emptiness and sign
# checks rather than cutoffs, and sweeping them would mean allowlisting
# twenty-eight of them to catch nothing. That is a stated limit of this
# guard, not an oversight.
#
# Everything above 1 is either read from config or listed here as a fact
# about the data rather than a choice about it.
ALLOWED_INT_COMPARISONS = {
    # Arity of a parsed clause, label or identifier: not a tunable quantity.
    "len(clause) != 3": "query clause is field, operator, value",
    "len(sort) != 2": "sort clause is field, direction",
    'len(parts) >= 3': "pair ids are tier_gene_e3",
    "len(substitution) >= 3": "a substitution label is at least wild, position, mutant",
    'len(token.strip(" ,.?;:()[]")) >= 3': "shortest token worth matching on",
    # Facts about the identifiers themselves.
    "len(pdb_id) != 4": "a PDB accession is four characters",
    "len(token) == 4": "a PDB accession is four characters",
    # Identity, not magnitude.
    "tier == 2": "names the second sampling tier, it is not a threshold",
    # The definition of the domain class, not a choice about it.
    "cysteines < 2": "C2H2 means two cysteines and two histidines",
    "histidines < 2": "C2H2 means two cysteines and two histidines",
    # Mathematical minima for the geometry to be defined at all.
    "len(moving_anchor) < 3": "three points are the fewest that fix a rigid body",
    "len(selected) < 2": "two points are the fewest that define a direction",
    # An API response cap, not a threshold applied to data.
    "limit > 100": "caps how many rows one query may return",
}


def _int_cutoff_comparisons() -> dict[str, list[str]]:
    """Comparisons against an integer literal above 1."""
    found: dict[str, list[str]] = {}
    for path in sorted((ROOT / "nobble").rglob("*.py")):
        source = path.read_text()
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if not isinstance(node, ast.Compare):
                continue
            for operand in [node.left, *node.comparators]:
                value = operand
                if isinstance(value, ast.UnaryOp) and isinstance(value.op, ast.USub):
                    value = value.operand
                if (isinstance(value, ast.Constant)
                        and isinstance(value.value, int)
                        and not isinstance(value.value, bool)
                        and abs(value.value) > 1):
                    text = " ".join(
                        (ast.get_source_segment(source, node) or "").split()
                    )
                    found.setdefault(text, []).append(
                        f"{path.relative_to(ROOT)}:{node.lineno}"
                    )
                    break
    return found


def test_no_integer_cutoff_is_hard_coded_either():
    found = _int_cutoff_comparisons()
    unexplained = {
        text: where for text, where in found.items()
        if text not in ALLOWED_INT_COMPARISONS
    }
    assert not unexplained, (
        "integer cutoff(s) that should read from config/thresholds.toml: "
        f"{unexplained}"
    )


def test_the_integer_allowances_are_all_still_real():
    found = _int_cutoff_comparisons()
    stale = [text for text in ALLOWED_INT_COMPARISONS if text not in found]
    assert not stale, f"ALLOWED_INT_COMPARISONS lists comparisons that are gone: {stale}"


def test_the_moved_integer_cutoffs_resolve_from_config():
    from nobble import paths
    from nobble.curate import peptides
    from nobble.score import metrics, weights
    from nobble.validate import layers

    t = paths.thresholds()
    assert peptides.FOLDED_DOMAIN_EXCEPTION_MIN_LENGTH == int(
        t["manifest"]["folded_domain_exception_min_length"])
    assert metrics.COLLAPSE_MINIMUM_SEEDS == int(t["scoring"]["collapse_minimum_seeds"])
    assert layers.ROC_MINIMUM_PER_SIDE == int(t["validation"]["roc_minimum_per_side"])
    assert weights.INDICATIVE_BELOW_LABELLED == int(
        t["weights"]["indicative_below_labelled"])
    assert weights.WIDE_BOUNDS_BELOW_PER_SIDE == int(
        t["weights"]["wide_bounds_below_per_side"])


# Numeric default arguments. The fourth place a cutoff can hide, and the
# quietest: a signature reads as configuration, so `fraction: float = 0.1`
# looked settled while deciding how much of the campaign's compute tier 2
# spends. A default is also shared, which is how one 5.0 in
# structures.contacts_to_ligand answered three different questions.
ALLOWED_DEFAULTS = {
    # Tier identity. Naming the sampling tier, not thresholding anything.
    "settings_from_config.tier": "names the sampling tier",
    "tier_files.tier": "names the sampling tier",
    "run_campaign.tier": "names the sampling tier",
    "hard_bound_seconds.tier": "names the sampling tier",
    "stall_report.tier": "names the sampling tier",
    "aggregate.sampling_tier": "names the sampling tier",
    "score_campaign.sampling_tier": "names the sampling tier",
    # Procedure parameters: precision and reproducibility, not data cutoffs.
    "_bootstrap_interval.rounds": "resampling count, a precision and compute "
                                  "trade-off rather than a cutoff on data",
    "_bootstrap_interval.seed": "fixed seed for reproducibility",
    "embed.batch_size": "how many sequences go to the model at once, a memory "
                        "trade-off with no effect on any result",
    # A what-if calculator's illustrative inputs, printed rather than applied.
    "budget_report.peptide_length": "an example length for the printed budget",
    "budget_report.ligand_heavy_atoms": "an example size for the printed budget",
    "campaign_budget.default_pairs": "an example pair count for the printed budget",
}


def _numeric_defaults() -> dict[str, list[str]]:
    """Function parameters whose default is a bare number."""
    found: dict[str, list[str]] = {}
    for path in sorted((ROOT / "nobble").rglob("*.py")):
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            args = node.args
            positional = args.posonlyargs + args.args
            pairs = []
            if args.defaults:
                pairs += list(zip([a.arg for a in positional][-len(args.defaults):],
                                  args.defaults))
            pairs += list(zip([a.arg for a in args.kwonlyargs], args.kw_defaults))
            for name, default in pairs:
                if default is None:
                    continue
                value = default
                if isinstance(value, ast.UnaryOp) and isinstance(value.op, ast.USub):
                    value = value.operand
                if (isinstance(value, ast.Constant)
                        and isinstance(value.value, (int, float))
                        and not isinstance(value.value, bool)):
                    found.setdefault(f"{node.name}.{name}", []).append(
                        f"{path.relative_to(ROOT)}:{node.lineno}"
                    )
    return found


def test_no_cutoff_hides_in_a_default_argument():
    found = _numeric_defaults()
    unexplained = {
        name: where for name, where in found.items() if name not in ALLOWED_DEFAULTS
    }
    assert not unexplained, (
        "numeric default(s) that should read from config: "
        f"{unexplained}"
    )


def test_the_default_allowances_are_all_still_real():
    found = _numeric_defaults()
    stale = [name for name in ALLOWED_DEFAULTS if name not in found]
    assert not stale, f"ALLOWED_DEFAULTS lists parameters that are gone: {stale}"


def test_a_shared_contact_cutoff_has_no_default_at_all():
    """Three callers meant three measurements by one 5.0.

    degron_gate read the configured value and passed it; peptides and
    yaml_gen each passed a bare literal. Changing the config would have moved
    one of the three. Removing the default makes every caller say which
    question it is asking.
    """
    import inspect

    from nobble.curate import structures

    signature = inspect.signature(structures.contacts_to_ligand)
    assert signature.parameters["cutoff"].default is inspect.Parameter.empty, (
        "contacts_to_ligand has a default cutoff again, so a caller can omit "
        "it and get someone else's measurement"
    )


def test_the_moved_defaults_resolve_from_config():
    from nobble import paths
    from nobble.curate import peptides, structures
    from nobble.execute import runner, tier2, yaml_gen

    t = paths.thresholds()
    assert tier2.DECILE_FRACTION == float(t["tier2"]["decile_fraction"])
    assert peptides.NEGATIVES_PER_POSITIVE == int(t["peptide"]["negatives_per_positive"])
    assert structures.LIGAND_MIN_HEAVY_ATOMS == int(
        t["geometry"]["ligand_min_heavy_atoms"])
    assert yaml_gen.POCKET_CONTACT_CUTOFF == float(
        t["geometry"]["pocket_contact_cutoff_a"])
    assert runner.settings_from_config(tier=1)["job_timeout_seconds"] == int(
        paths.tuning()["campaign"]["job_timeout_seconds"])


def test_hwprobe_writes_the_job_timeout_it_is_read_from():
    """tuning.toml is machine-written, so a key added only by hand is a key
    the next hardware probe silently drops."""
    source = (ROOT / "tools" / "hwprobe.py").read_text()
    assert '"job_timeout_seconds"' in source, (
        "hwprobe no longer writes job_timeout_seconds, so the next probe would "
        "produce a tuning.toml that settings_from_config cannot read"
    )


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
