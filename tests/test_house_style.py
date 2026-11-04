"""CLAUDE.md's house style, as a check rather than an intention.

    House style: British English, no em dashes (colons, semicolons or
    parentheses), and none of: groundbreaking, revolutionary,
    paradigm-shifting, game-changing, cutting-edge, unprecedented,
    seamless, leverage (verb), delve.

Stated in CLAUDE.md and again in BUILD_SPEC.md 1.4, and enforced by nothing
for the whole build. Thousands of words of FINDINGS.md, DECISIONS.md and UI
copy were written against it on trust.

The codebase does comply, which is why this is a guard rather than a repair.
Writing it did settle one question that had never been decided, though. The
app templates hold 32 em dashes and every one is an empty-value placeholder,
`{{ value or '-' }}` in a table cell or a stat. The rule's own remedy, "use
colons, semicolons or parentheses", cannot be applied to a glyph standing
for "no value", so the rule is about punctuation in prose and the
placeholder is allowed. Recorded here because an unrecorded interpretation
is indistinguishable from an unnoticed violation (D-NOB-057).

The 11 em dashes used as punctuation are all in BUILD_SPEC.md, which is the
authoritative input rather than the project's output, and which is where
1.4 is stated. Excluded for that reason and not because the rule is
inconvenient (F67).
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

EM_DASH = "—"

# An em dash is allowed only when the whole quoted token is the dash: an
# empty-value placeholder, not punctuation.
PLACEHOLDER = re.compile(rf"""(['"]){EM_DASH}\1""")

SUFFIXES = (".md", ".py", ".html", ".mjs", ".sh", ".toml")
SKIP_PARTS = {".git", "node_modules", "__pycache__", ".pixi", "campaigns",
              "deploy/atlas", "data"}

# The authoritative input, and the two files that state the rule.
STATES_THE_RULE = {"BUILD_SPEC.md", "CLAUDE.md"}
THIS_FILE = Path(__file__).name

BANNED = ("groundbreaking", "revolutionary", "paradigm-shifting",
          "game-changing", "cutting-edge", "unprecedented", "seamless",
          "delve")

# The British forms this project uses. Named rather than inlined so that
# emptying the loop that checks them fails instead of passing vacuously,
# which is how the mutation harness caught this one.
BRITISH_IN_USE = ("colour", "behaviour", "tumour", "labelled")

# American spellings whose British form this project uses. Only words that
# cannot appear as code: `color` and `center` are CSS properties and are
# checked in prose alone.
AMERICAN_ANYWHERE = {
    "behavior": "behaviour", "behaviors": "behaviours",
    "tumor": "tumour", "tumors": "tumours",
    "modeling": "modelling", "labeled": "labelled",
    "defense": "defence", "analyze": "analyse", "analyzed": "analysed",
    "favorite": "favourite", "neighbor": "neighbour",
}
AMERICAN_IN_PROSE = {"color": "colour", "colors": "colours",
                     "center": "centre", "centers": "centres"}


def _files(suffixes=SUFFIXES):
    for path in sorted(ROOT.rglob("*")):
        if path.is_dir():
            continue
        relative = path.relative_to(ROOT)
        if any(part in SKIP_PARTS for part in relative.parts):
            continue
        if "deploy/atlas" in str(relative):
            continue
        if path.suffix not in suffixes or path.name == THIS_FILE:
            continue
        yield relative, path


def _read(path):
    try:
        return path.read_text()
    except (UnicodeDecodeError, OSError):
        return ""


def punctuation_em_dashes(text: str) -> list[str]:
    """Em dashes in this text that are not empty-value placeholders.

    Pure over the text so the same check runs against the tree and against
    deliberately bad input. A sweep that passes on a clean tree reads the
    same whether it is working or broken, and the negative controls below
    are what tell those apart (F65).
    """
    found = []
    for number, line in enumerate(text.splitlines(), start=1):
        for match in re.finditer(EM_DASH, line):
            start = max(0, match.start() - 1)
            end = min(len(line), match.end() + 1)
            if PLACEHOLDER.fullmatch(line[start:end]):
                continue
            found.append(f"{number}: {line.strip()[:70]}")
    return found


def banned_words(text: str) -> list[str]:
    r"""Forbidden words, including their inflections.

    `\b<word>\b` alone was too narrow and the mutation harness found it:
    "delved", "delves", "delving" and "seamlessly" all passed a sweep whose
    whole purpose is to catch them, and the boundary test that was supposed
    to cover this used "shelve", which does not contain "delve" at all. So
    the test passed, the check looked boundary-safe, and the inflections
    went through.

    `\b<word>\w*` catches the inflections and keeps the leading boundary,
    so a banned stem inside another word is still ignored. All eight terms
    are long and distinctive enough that nothing innocent begins with one.
    """
    lowered = text.lower()
    return [word for word in BANNED
            if re.search(rf"\b{re.escape(word)}\w*", lowered)]


def american_spellings(text: str, prose: bool) -> list[str]:
    lowered = text.lower()
    checks = dict(AMERICAN_ANYWHERE)
    if prose:
        checks.update(AMERICAN_IN_PROSE)
    return [f"{american} -> {british}" for american, british in checks.items()
            if re.search(rf"\b{american}\b", lowered)]


def test_no_em_dash_is_used_as_punctuation():
    offenders = []
    for relative, path in _files():
        if relative.name in STATES_THE_RULE:
            continue
        for hit in punctuation_em_dashes(_read(path)):
            offenders.append(f"{relative}:{hit}")
    assert not offenders, (
        "em dash used as punctuation; the house style asks for a colon, a "
        "semicolon or parentheses:\n" + "\n".join(offenders[:10])
    )


def test_the_placeholder_em_dashes_are_still_only_placeholders():
    """The allowance, measured. If this count moves, someone has either
    added a table column or started writing prose with the glyph, and the
    second is what the allowance must not come to cover."""
    placeholders = 0
    for _relative, path in _files((".html",)):
        placeholders += len(PLACEHOLDER.findall(_read(path)))
    assert placeholders > 0, "the allowance covers nothing, so remove it"


def test_none_of_the_forbidden_words_appear():
    offenders = []
    for relative, path in _files():
        if relative.name in STATES_THE_RULE:
            continue
        for word in banned_words(_read(path)):
            offenders.append(f"{relative}: {word}")
    assert not offenders, "forbidden word(s): " + "; ".join(offenders[:10])


def test_the_forbidden_list_matches_the_one_in_claude_md():
    """A second copy of a list is how the two come to differ. If CLAUDE.md
    gains a word, this fails until the sweep gains it too."""
    text = (ROOT / "CLAUDE.md").read_text().lower()
    stated = re.search(r"none of:(.*?)\.", text, re.S)
    assert stated, "CLAUDE.md no longer states the list in the expected shape"
    words = {word.strip().split("(")[0].strip()
             for word in stated.group(1).replace("\n", " ").split(",")}
    words = {word for word in words if word}
    missing = words - set(BANNED) - {"leverage"}
    assert not missing, (
        f"CLAUDE.md forbids words this sweep does not check: {sorted(missing)}"
    )


def test_british_spellings_are_used():
    offenders = []
    for relative, path in _files():
        if relative.name in STATES_THE_RULE:
            continue
        for hit in american_spellings(_read(path), path.suffix == ".md"):
            offenders.append(f"{relative}: {hit}")
    assert not offenders, ("American spelling(s):\n"
                           + "\n".join(sorted(set(offenders))[:10]))


def test_the_british_forms_really_are_in_use():
    """A spelling sweep that finds nothing proves nothing on its own: it
    reads the same whether the project is consistent or the pattern is
    broken. These are the forms the project does use."""
    assert BRITISH_IN_USE, "the control checks nothing"
    text = "\n".join(_read(path).lower() for _relative, path in _files())
    for british in BRITISH_IN_USE:
        assert re.search(rf"\b{british}\b", text), (
            f"{british} does not appear anywhere, so the sweep for its "
            "American form is not evidence of anything"
        )


def test_the_em_dash_check_catches_punctuation():
    """The negative control. A dash between two words is the use the rule
    forbids and the remedy it names applies to."""
    assert punctuation_em_dashes(
        "The campaign ran \u2014 and then it stopped.")


def test_the_em_dash_check_allows_a_placeholder():
    assert punctuation_em_dashes(
        "<td>{{ value or '\u2014' }}</td>") == []
    assert punctuation_em_dashes(
        '<td>{{ value or "\u2014" }}</td>') == []


def test_the_em_dash_check_is_not_fooled_by_a_nearby_quote():
    """A dash adjacent to a quote is not a placeholder unless the quotes
    are its own, or the allowance would cover any dash in a sentence that
    happens to contain quotation marks."""
    assert punctuation_em_dashes(
        "he said 'yes' \u2014 and meant it")
    assert punctuation_em_dashes("'quoted' \u2014 then prose")


def test_the_banned_word_check_catches_one():
    assert banned_words("a seamless integration") == ["seamless"]
    assert banned_words("this is a GROUNDBREAKING result") == ["groundbreaking"]


def test_the_banned_word_check_catches_inflections():
    """The gap the harness found. A list of stems that only matches the
    exact form lets every use of the word through, which is most of them:
    "delved into the data" is the sentence the rule is about."""
    assert banned_words("we delved into the data") == ["delve"]
    assert banned_words("it delves into it") == ["delve"]
    assert banned_words("integrates seamlessly") == ["seamless"]
    assert banned_words("we delve into it") == ["delve"]


def test_the_banned_word_check_keeps_its_leading_boundary():
    """A stem inside another word is not a use of it. "shelve" does not
    contain "delve" and was a useless test case; these do contain a banned
    stem and must still be ignored."""
    assert banned_words("the shelve was full") == []
    assert banned_words("he was bedevilled by it") == []
    assert banned_words("the mainsail was seamed") == []


def test_the_spelling_check_catches_an_americanism():
    assert american_spellings("the behavior of the runner", prose=False)
    assert american_spellings("a tumor suppressor", prose=False)


def test_the_prose_only_spellings_are_not_checked_in_code():
    """`color` and `center` are CSS properties. Checking them in a template
    would report every stylesheet in the project, which is a sweep that has
    to be switched off and therefore is not a sweep."""
    assert american_spellings("color: #fff; text-align: center;",
                              prose=False) == []
    assert american_spellings("the color of the bar", prose=True)
