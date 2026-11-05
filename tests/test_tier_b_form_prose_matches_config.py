"""The form's prose quotes config, and cannot drift from it (F187).

`config/tier_b_constructs.toml` explains the candidate range in words:
"between 60 residues and 326, which is the tier-1 token cap of 400 less a
15-mer peptide and a glue at the recall set's median of 59 heavy atoms".

Every one of those five numbers also lives in `config/thresholds.toml`, where
the code reads them. They agree today. Nothing made them agree, and this is
the third time in two days the same duplication has come up: F181 had one of
two sibling budgets in config and the other in a test, and F183 had a cutoff
in a tool and the same number in this file's prose.

The remedy that worked for the copy budget is the one used here. That test
reads 40 and 150 out of CLAUDE.md, which is the file stating the rule, and
requires the tool to compare against them. This reads the five numbers out of
`thresholds.toml`, which is the file the code reads, and requires the prose to
quote them. A reader who changes a threshold and not the sentence beside it is
told, rather than leaving a file whose explanation describes the previous
behaviour.

Deliberately not solved by deleting the prose. The sentence is why the range
is what it is, which no config value carries, and a form nobody can read is
worse than one whose header needs keeping in step.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from nobble import paths  # noqa: E402

FORM = ROOT / "config" / "tier_b_constructs.toml"


def header() -> str:
    """The comment block above `[constructs]`, which is the prose at issue."""
    text = FORM.read_text()
    return text.split("[constructs]", 1)[0]


def configured() -> dict[str, int]:
    thresholds = paths.thresholds()
    tier_b, manifest = thresholds["tier_b"], thresholds["manifest"]
    peptide = int(tier_b["construct_peptide_residues"])
    glue = int(tier_b["construct_glue_heavy_atoms"])
    token_cap = int(manifest["token_cap_tier1"])
    return {
        "minimum": int(tier_b["construct_min_residues"]),
        "token_cap": token_cap,
        "peptide": peptide,
        "glue": glue,
        "cap": token_cap - peptide - glue,
    }


def test_the_prose_quotes_every_configured_number():
    prose, values = header(), configured()
    missing = {name: value for name, value in values.items()
               if not re.search(rf"\b{value}\b", prose)}
    assert not missing, (
        f"the form's header does not mention {missing}. A threshold changed "
        "and the sentence explaining the range still describes the previous "
        "one."
    )


def test_the_arithmetic_in_the_prose_is_the_arithmetic_in_the_code():
    """The sentence states a subtraction; it has to be the right one."""
    values = configured()
    assert values["cap"] == values["token_cap"] - values["peptide"] - values["glue"]
    prose = header()
    # The claim as written: cap of <token_cap> less a <peptide>-mer peptide
    # and a glue at <glue> heavy atoms, giving <cap>.
    assert re.search(rf"token cap of {values['token_cap']}", prose), prose[:0]
    assert re.search(rf"{values['peptide']}-mer", prose)
    assert re.search(rf"median of {values['glue']} heavy atoms", prose)
    assert re.search(rf"between {values['minimum']}\s*#?\s*\n?#?\s*residues "
                     rf"and {values['cap']}", prose), (
        "the range in the prose is not the configured minimum and cap"
    )


def test_the_listing_tool_and_the_prose_describe_one_range():
    """The tool reads config; the prose must describe what the tool will do."""
    sys.path.insert(0, str(ROOT / "tools"))
    import tier_b_candidates as tool

    values = configured()
    assert tool.cap() == values["cap"]
    assert tool.floor() == values["minimum"]
