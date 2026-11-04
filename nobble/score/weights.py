"""Composite weight fitting (spec 4.8, decision D-NOB-006).

The weights are fitted on the benchmark panel and the Sievers matched set, and
are never hand-set. Until a fit has data it is better to publish no composite
than an invented one, because a ranked column looks authoritative whatever its
provenance, which is why `nobble_score` stays null rather than defaulting.

What "fitted" has to mean here is constrained by how little data there is. Seven
benchmark pairs is not a training set: anything with more than a couple of free
parameters will fit the panel perfectly and generalise to nothing. So the fit is
deliberately a weak one, it reports how little it had to work with, and it
refuses outright below a floor.
"""
from __future__ import annotations

import itertools
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

from nobble import paths

# The components the composite may weight. Lysine geometry is a candidate so
# the fit can speak for itself, but it carries its own warning: BINMAN measured
# it at or below chance (D-NOB-024).
CANDIDATES = (
    "bridge_percentile",
    "delta_iptm",
    "convergence_score",
    "plip_fingerprint_match",
    "lysine_reach_exposed_fraction",
)

NOT_VALIDATED = {"lysine_reach_exposed_fraction"}

# Fewer labelled pairs than this and no fit is attempted at all.
MINIMUM_LABELLED = int(paths.thresholds()["weights"]["minimum_labelled"])
# Weights are searched on this grid rather than optimised continuously: with a
# handful of pairs, a continuous optimum is a fiction to three decimal places.
GRID = (0.0, 0.25, 0.5, 0.75, 1.0)


@dataclass
class FitResult:
    status: str
    weights: dict = field(default_factory=dict)
    objective: float | None = None
    labelled_pairs: int = 0
    positives: int = 0
    negatives: int = 0
    components_used: list = field(default_factory=list)
    caveats: list = field(default_factory=list)
    per_component_auc: dict = field(default_factory=dict)

    @property
    def fitted(self) -> bool:
        return self.status == "fitted"

    def to_dict(self) -> dict:
        return asdict(self) | {"fitted": self.fitted}


def _normalise(name: str, value):
    """Put every component on 0 to 1 so a weight means the same thing across them."""
    if value is None:
        return None
    if name == "bridge_percentile":
        return max(0.0, min(1.0, value / 100.0))
    if name == "delta_iptm":
        # Delta-ipTM runs about -1 to +1; map it so 0 (no glue dependence) is
        # the midpoint rather than the floor.
        return max(0.0, min(1.0, (value + 1.0) / 2.0))
    return max(0.0, min(1.0, float(value)))


def _features(row: dict) -> dict:
    lysine = row.get("lysine_reach") or {}
    count = lysine.get("peptide_lysines") or 0
    exposed = lysine.get("exposed_lysines") or 0
    values = {
        "bridge_percentile": row.get("bridge_percentile"),
        "delta_iptm": row.get("delta_iptm"),
        "convergence_score": row.get("convergence_score"),
        "plip_fingerprint_match": row.get("plip_fingerprint_match"),
        "lysine_reach_exposed_fraction": (exposed / count) if count else None,
    }
    return {name: _normalise(name, value) for name, value in values.items()}


def _auc(positives: list[float], negatives: list[float]) -> float | None:
    if not positives or not negatives:
        return None
    wins = 0.0
    for p in positives:
        for n in negatives:
            wins += 1.0 if p > n else (0.5 if p == n else 0.0)
    return wins / (len(positives) * len(negatives))


def _label(row: dict) -> str | None:
    """Positive when experimentally degraded, negative when not or a scramble.

    Deliberately not scoped to one arm, unlike `matched_control_roc`, which
    reads the same field and must exclude everything but the Sievers split.
    Spec 4.8 fits the weights "on the benchmark panel and the Sievers matched
    set", so the panel belongs here; spec 5.3 scopes the ROC to the Sievers
    split alone, so it does not belong there. The same label means different
    things to the two consumers, and narrowing this one to match the other
    would be fitting the composite on less than the spec asks for.
    """
    label = row.get("peptide_label")
    if label == "degraded":
        return "positive"
    if label in ("not_degraded", "negative_control"):
        return "negative"
    return None


def fit(campaign: Path) -> FitResult:
    scores_path = campaign / "scores.jsonl"
    if not scores_path.exists():
        return FitResult(status="not_fitted: no scores")

    rows = [json.loads(line) for line in scores_path.read_text().splitlines() if line.strip()]
    labelled = [(row, _label(row)) for row in rows if _label(row)]
    positives = [row for row, side in labelled if side == "positive"]
    negatives = [row for row, side in labelled if side == "negative"]

    result = FitResult(
        status="pending",
        labelled_pairs=len(labelled),
        positives=len(positives),
        negatives=len(negatives),
    )

    if len(labelled) < MINIMUM_LABELLED or not positives or not negatives:
        result.status = (
            f"not_fitted: {len(positives)} positive(s) and {len(negatives)} "
            f"negative(s) scored, below the floor of {MINIMUM_LABELLED} labelled "
            "pairs. Spec 4.8 fits on the benchmark panel and the Sievers matched "
            "set; the Sievers arm runs after the panel. A composite fitted on "
            "fewer pairs than it has components would be fitting noise"
        )
        return result

    # Which components actually have values on enough pairs to be fitted at all.
    usable = []
    for name in CANDIDATES:
        present = sum(
            1 for row, _ in labelled if _features(row).get(name) is not None
        )
        if present >= len(labelled) * 0.6:
            usable.append(name)
    result.components_used = usable
    if not usable:
        result.status = "not_fitted: no component has values on enough labelled pairs"
        return result

    # Single-component discrimination, reported whatever the fit decides, so a
    # weight can always be read against the component's own standalone AUC.
    for name in usable:
        p = [_features(row)[name] for row in positives if _features(row)[name] is not None]
        n = [_features(row)[name] for row in negatives if _features(row)[name] is not None]
        auc = _auc(p, n)
        if auc is not None:
            result.per_component_auc[name] = round(auc, 4)

    # Grid search maximising the composite's AUC on the labelled split.
    best = None
    for combination in itertools.product(GRID, repeat=len(usable)):
        if sum(combination) == 0:
            continue
        weights = dict(zip(usable, combination))
        scored_positive, scored_negative = [], []
        for row, side in labelled:
            features = _features(row)
            total = weight_total = 0.0
            for name, weight in weights.items():
                value = features.get(name)
                if value is None or not weight:
                    continue
                total += weight * value
                weight_total += weight
            if not weight_total:
                continue
            (scored_positive if side == "positive" else scored_negative).append(
                total / weight_total
            )
        auc = _auc(scored_positive, scored_negative)
        if auc is None:
            continue
        # Prefer the simplest weighting among ties: fewer non-zero components.
        key = (round(auc, 6), -sum(1 for w in combination if w))
        if best is None or key > best[0]:
            best = (key, weights, auc)

    if best is None:
        result.status = "not_fitted: no weighting could be scored on the labelled split"
        return result

    _key, weights, auc = best
    total = sum(weights.values())
    result.weights = {name: round(w / total, 4) for name, w in weights.items()}
    result.objective = round(auc, 4)
    result.status = "fitted"

    # The objective is in-sample: the grid search maximised this AUC on the
    # same labelled pairs the composite is then used to rank. It is a
    # description of the fit, not an estimate of how the composite performs
    # on a pair it has not seen, and it is the number most likely to be
    # quoted as if it were the latter. The matched-control ROC is the held
    # -out measurement; this is not a second opinion on it.
    result.caveats.append(
        f"AUC {result.objective} is in-sample: the grid maximised it on the "
        f"same {len(labelled)} labelled pairs. It describes the fit, not "
        "performance on unseen pairs"
    )

    if len(labelled) < 25:
        result.caveats.append(
            f"fitted on only {len(labelled)} labelled pairs: treat the weights as "
            "indicative, not as a calibrated model. They will be refitted when "
            "the Sievers matched set completes"
        )
    for name in result.weights:
        if name in NOT_VALIDATED and result.weights[name] > 0:
            result.caveats.append(
                f"{name} carries weight {result.weights[name]} despite having no "
                "validated discriminating power: BINMAN measured its reach window "
                "at or below chance (D-NOB-024). On this few pairs that weight is "
                "as likely to be noise as signal"
            )
    if result.positives < 5 or result.negatives < 5:
        result.caveats.append(
            "fewer than five on one side of the split: the AUC has very wide "
            "confidence bounds and is not a performance claim"
        )
    return result


def apply(row: dict, weights: dict) -> float | None:
    """Composite for one pair under a given weighting."""
    features = _features(row)
    total = weight_total = 0.0
    for name, weight in weights.items():
        value = features.get(name)
        if value is None or not weight:
            continue
        total += weight * value
        weight_total += weight
    return round(total / weight_total, 4) if weight_total else None
