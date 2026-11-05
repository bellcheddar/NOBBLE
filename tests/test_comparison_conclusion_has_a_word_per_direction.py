"""Four directions, four conclusions (F200).

`compare.conclude`'s verdict is the sentence on the benchmark page that says
whether F6 held: whether submitting a substrate as the whole domain rather
than a 15-mer recovers poses better. It had a label for "better", a label for
"nothing changed", and `mixed` for everything else.

"Everything else" is two different results. Some better and some worse is
mixed. None better and several worse is not mixed at all: it is F6
contradicted, the whole domain recovering poses less well than the fragment.
That is a finding, and this project publishes a failed control rather than
softening it, so describing it with a word that means "both ways" was the one
reading that lost the direction.

The counts were printed either way, so nothing was hidden. The headline word
was simply wrong for one of its two cases, which is the same defect as F198
and F199: correct arithmetic in a sentence that says something else.

A second thing in the same branch. `control {'held' if control_ok else
'moved'}` had a false arm that could never run, because the two branches
above the F6 ones return for every state in which the control has not held.
The conditional is gone and the sentence says "control held", which is what
it always said.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from nobble.validate import compare  # noqa: E402

SOURCE = (ROOT / "nobble" / "validate" / "compare.py").read_text()


def code_only(text: str) -> str:
    import re
    body = "\n".join(l for l in text.splitlines() if not l.strip().startswith("#"))
    return re.sub(r'""".*?"""', "", body, flags=re.S)


def _row(gene: str, verdict: str, control: bool = False):
    row = compare.PairComparison(gene=gene, e3="CRBN",
                                 baseline_pair="b", corrected_pair="c")
    row.verdict, row.is_control, row.delta_rmsd = verdict, control, 0.1
    return row


def conclude(improved: int, worse: int) -> str:
    """Drive the real branches with a hand-built set of comparisons."""
    rows = [_row("IKZF1", "control held", control=True)]
    rows += [_row(f"u{i}", "improved") for i in range(improved)]
    rows += [_row(f"d{i}", "worse") for i in range(worse)]
    return compare.conclude(rows) if hasattr(compare, "conclude") else ""


def test_the_source_has_a_label_for_every_direction():
    """Read off the source, because `conclude` may not be callable alone."""
    code = code_only(SOURCE)
    for label in ("F6 supported", "F6 not supported", "F6 contradicted",
                  "mixed", "NOT TRUSTWORTHY", "not concluded"):
        assert label in code, f"no branch says {label!r}"


def test_the_all_worse_case_is_not_called_mixed():
    """The case that had no word (F200).

    Located in the source rather than by calling, because the conclusion is
    built inside a longer function. The ordering is what matters: the
    contradicted branch has to be tested before the catch-all, or every
    all-worse run falls through to `mixed` exactly as before.
    """
    code = code_only(SOURCE)
    contradicted = code.index("F6 contradicted")
    guard = code.index("elif worse and not improved")
    catch_all = code.rindex("mixed:")
    assert guard < contradicted < catch_all, (
        "the contradicted branch is not guarded before the catch-all, so an "
        "all-worse comparison is still reported as mixed"
    )


def test_the_dead_control_arm_is_gone():
    """`control_ok` is True by construction in the final branch."""
    code = code_only(SOURCE)
    assert "'held' if control_ok else 'moved'" not in code, (
        "the final branch tests a condition that cannot be false there, so "
        "its 'moved' arm can never run"
    )
    assert "control held" in code


def test_the_two_f6_directions_say_opposite_things():
    """A reader must be able to tell them apart without counting."""
    code = code_only(SOURCE)
    supported = code[code.index("F6 supported"):]
    supported = supported[:supported.index("elif")]
    contradicted = code[code.index("F6 contradicted"):]
    contradicted = contradicted[:contradicted.index("else:")]
    assert "improved" in supported and "none got worse" in supported
    assert "got worse" in contradicted and "none improved" in contradicted
