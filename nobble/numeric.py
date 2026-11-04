"""What counts as a number when a number is going to be compared.

`isinstance(value, (int, float))` is the obvious test and it is wrong twice
over. NaN is a float, and a bool is an int.

Neither mistake raises. A NaN that reaches a comparison loses every one of
them, because NaN is neither greater than nor equal to anything, so it is
silently scored as the worst possible value rather than as missing data. A
NaN inside `sorted()` is worse: comparisons against it are all false, so it
settles wherever the sort leaves it and a median taken by index can come
back as the NaN itself or as an arbitrary neighbour. A bool compares as 1 or
0 against real measurements.

F74 found this in `matched_control_roc`, where one NaN among three positives
moved the headline AUC from 1.0 to 0.667, towards the null result, which is
the direction a sceptical reader would not question. The same idiom appeared
in fourteen places, including the one that decides which pairs tier 2
refines. Fixing one of fourteen copies of a rule is the shape this project
keeps finding, so the rule lives here now and the call sites import it
(F76).

Python's `json` writes NaN as a bare `NaN` literal and reads it back, so
these values travel through the pipeline's own files without anything
objecting. No record in any campaign carries one today: 22,500 float values
checked.
"""
from __future__ import annotations

import math

__all__ = ["finite", "finite_values", "median_of", "mann_whitney_auc"]


def finite(value) -> bool:
    """True for a real number that can be meaningfully compared."""
    return (isinstance(value, (int, float)) and not isinstance(value, bool)
            and math.isfinite(value))


def finite_values(values) -> list[float]:
    """Just the comparable numbers, in the order given."""
    return [value for value in values if finite(value)]


def median_of(values) -> float | None:
    """Lower median of the comparable values, or None if there are none.

    The lower median rather than the mean of the middle two, because that
    is what the call sites it replaces computed: `sorted(...)[len // 2]`.
    Keeping the same estimator means this cannot move a published figure,
    which is the point of introducing it mid-campaign.
    """
    present = sorted(finite_values(values))
    if not present:
        return None
    return present[len(present) // 2]


def mann_whitney_auc(positives, negatives) -> float:
    """ROC area as the Mann-Whitney statistic, with ties at half a win.

    Raises on an empty side or on any non-finite input, so the two callers
    can each decide what an absent curve should return: the validation
    layer reports NaN and refuses to publish, the weight fitter returns
    None and declines that point on its grid. Sharing the estimator and
    splitting the contract is deliberate; sharing neither is how one copy
    came to be hardened against NaN and the other did not (F77).
    """
    if not positives or not negatives:
        raise ValueError("both sides are needed for an AUC")
    offenders = [v for v in list(positives) + list(negatives) if not finite(v)]
    if offenders:
        raise ValueError(f"non-finite value(s) in the ROC inputs: {offenders[:5]}")
    wins = 0.0
    for positive in positives:
        for negative in negatives:
            if positive > negative:
                wins += 1.0
            elif positive == negative:
                wins += 0.5
    return wins / (len(positives) * len(negatives))
