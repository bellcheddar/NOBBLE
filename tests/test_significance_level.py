"""One significance level, read from one place.

`config/thresholds.toml` says `significance_alpha = 0.05` is "the only
significance level this project applies", and D-NOB-047 put it there because
`benchmark.html` had styled a correlation on a literal `p < 0.05`: "a reader
changing what the project counts as significant should not have to know it is
written in markup."

The same reader should not have to know it is written in arithmetic. The
matched-control ROC's bootstrap took its bounds from `int(0.025 * rounds)`
and `int(0.975 * rounds)` and reported "not distinguishable from chance at 95
per cent confidence" as a string, with two more copies in `about.html` and in
the design caveat. Four literals, agreeing with the configured value by
coincidence, and the cutoff sweep does not look inside an expression (F80).

Changing alpha used to restyle one chart and leave the headline result's
interval at 95 per cent while the prose said so. Now every one of them
derives from it (F119).
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from nobble import paths  # noqa: E402
from nobble.validate import layers  # noqa: E402


def _alpha() -> float:
    return float(paths.thresholds()["scoring"]["significance_alpha"])


def test_the_level_is_computed_from_the_configured_alpha():
    assert layers.confidence_level() == pytest.approx(100.0 * (1.0 - _alpha()))


def test_changing_alpha_moves_the_interval(monkeypatch):
    """The property the four literals prevented. A wider alpha must give a
    narrower interval, on the same data and the same seed."""
    positives = [0.9, 0.8, 0.85, 0.95, 0.7, 0.88]
    negatives = [0.3, 0.4, 0.2, 0.5, 0.35, 0.45, 0.25, 0.55]

    def with_alpha(alpha: float):
        thresholds = paths.thresholds()
        patched = {
            **thresholds,
            "scoring": {**thresholds["scoring"], "significance_alpha": alpha},
        }
        monkeypatch.setattr(paths, "thresholds", lambda: patched)
        return layers._bootstrap_interval(positives, negatives)

    wide = with_alpha(0.20)
    narrow = with_alpha(0.01)
    assert (narrow[1] - narrow[0]) >= (wide[1] - wide[0]), (narrow, wide)


def test_changing_alpha_moves_the_reported_level(monkeypatch):
    thresholds = paths.thresholds()
    patched = {
        **thresholds,
        "scoring": {**thresholds["scoring"], "significance_alpha": 0.01},
    }
    monkeypatch.setattr(paths, "thresholds", lambda: patched)
    assert layers.confidence_level() == pytest.approx(99.0)


def test_no_percentile_literal_is_left_in_the_bootstrap():
    source = (ROOT / "nobble" / "validate" / "layers.py").read_text()
    block = source[source.index("def _bootstrap_interval"):
                   source.index("ROC_ARM =")]
    for literal in ("0.025", "0.975"):
        assert literal not in block, (literal, "the percentile is hard-coded again")
    assert 'significance_alpha' in block


def test_no_surface_prints_a_hard_coded_ninety_five():
    """The prose and the markup, which is where D-NOB-047's reasoning
    started."""
    import re

    offenders = []
    for relative in ("nobble/validate/layers.py", "nobble/design/report.py",
                     "nobble/app/templates/about.html"):
        text = (ROOT / relative).read_text()
        # Docstrings and comments are prose about the fix and mention the old
        # literals on purpose. Blanked rather than skipped by prefix, because
        # a continuation line inside a docstring starts with neither a quote
        # nor a hash, which is how the first version of this failed on its
        # own explanation.
        text = re.sub(r'"""(?:.|\n)*?"""', lambda m: "\n" * m.group(0).count("\n"), text)
        text = re.sub(r"\{#(?:.|\n)*?#\}", lambda m: "\n" * m.group(0).count("\n"), text)
        for number, line in enumerate(text.splitlines(), 1):
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            if "95 per cent" in stripped or "95%" in stripped:
                # `default(95, true)` is a fallback for an atlas built before
                # the field existed, not a second copy of the level.
                if "default(95" in stripped:
                    continue
                offenders.append(f"{relative}:{number}: {stripped[:60]}")
    assert not offenders, offenders


def test_the_rounds_came_out_of_the_signature():
    source = (ROOT / "nobble" / "validate" / "layers.py").read_text()
    assert "rounds: int = 2000" not in source
    assert "bootstrap_rounds" in source
    assert "bootstrap_rounds" in (ROOT / "config" / "thresholds.toml").read_text()


def test_the_bounds_are_the_order_statistics_they_claim(monkeypatch):
    """A percentile bootstrap's bounds are the alpha/2 and 1 - alpha/2 order
    statistics. Checked against a distribution whose answer is known: the
    AUC of n identical draws is deterministic, so a degenerate case pins the
    indexing rather than the sampling."""
    thresholds = paths.thresholds()
    patched = {
        **thresholds,
        "scoring": {**thresholds["scoring"], "significance_alpha": 0.05,
                    "bootstrap_rounds": 1000},
    }
    monkeypatch.setattr(paths, "thresholds", lambda: patched)

    # Perfectly separated: every resample gives AUC 1.0, so both bounds are 1.
    low, high = layers._bootstrap_interval([1.0] * 5, [0.0] * 5)
    assert (low, high) == (1.0, 1.0)

    # Perfectly tied: every resample gives 0.5.
    low, high = layers._bootstrap_interval([0.5] * 5, [0.5] * 5)
    assert (low, high) == (0.5, 0.5)


def test_the_summary_states_the_level_it_used():
    """So a reader of the atlas does not have to know what alpha was when it
    was built."""
    source = (ROOT / "nobble" / "validate" / "layers.py").read_text()
    assert '"confidence_level": confidence_level()' in source
    template = (ROOT / "nobble" / "app" / "templates" / "about.html").read_text()
    assert "roc.summary.confidence_level" in template
