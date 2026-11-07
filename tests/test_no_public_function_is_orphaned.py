"""F250's sweep, as a test, because F291 is what happens without one.

F250 swept every public module-level function in `nobble/` for references
anywhere and found three orphans, keeping two deliberately. It left no test,
so on 7 November I ran the same sweep again without knowing it had been done
(F291), and the only thing it caught was a public accessor I had added that
morning and nothing called.

That is F295's lesson in its cheapest form: a sweep is worth less than the
test it should have left behind. This is the sweep (F296).

Two limitations F250 documented and this inherits. A name scan cannot see a
decorator, so Flask route handlers are excluded by being decorated rather
than by being listed. And a function called only from a shell script or named
in the README is referenced in text this does not parse, so both are searched
as text.
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# Orphans kept on purpose, with F250's reasons. An entry here is a claim that
# the function should exist while nothing calls it, which is a claim worth
# writing down rather than a line to add when the test complains.
ALLOWED = {
    "has_model":
        "a one-line wrapper over model_path(accession).exists(), kept as the "
        "readable form of a check callers currently spell out (F250)",
    "ligand_chains":
        "the sole consumer of LIGAND_MIN_HEAVY_ATOMS, which the cutoff sweep "
        "asserts is read from config: deleting it would leave a threshold "
        "reading as live with nothing using it (F250)",
}


def _public_functions() -> dict[str, tuple[str, int]]:
    found = {}
    for path in sorted((ROOT / "nobble").rglob("*.py")):
        tree = ast.parse(path.read_text())
        for node in tree.body:
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if node.name.startswith("_") or node.decorator_list:
                continue
            found[node.name] = (str(path.relative_to(ROOT)), node.lineno)
    return found


def _names_referenced() -> set[str]:
    names: set[str] = set()
    for folder in ("nobble", "tools", "deploy", "tests"):
        for path in (ROOT / folder).rglob("*.py"):
            try:
                tree = ast.parse(path.read_text())
            except SyntaxError:
                continue
            for node in ast.walk(tree):
                if isinstance(node, ast.Name):
                    names.add(node.id)
                elif isinstance(node, ast.Attribute):
                    names.add(node.attr)
    return names


def _text_of_scripts_and_docs() -> str:
    parts = []
    for folder in ("tools", "deploy"):
        parts += [p.read_text() for p in (ROOT / folder).glob("*.sh")]
    for doc in ("README.md", "CLAUDE.md"):
        path = ROOT / doc
        if path.exists():
            parts.append(path.read_text())
    return "\n".join(parts)


def test_every_public_function_is_called_somewhere():
    functions = _public_functions()
    assert len(functions) > 150, f"only {len(functions)} found: the scan narrowed"
    referenced = _names_referenced()
    text = _text_of_scripts_and_docs()
    orphans = {
        name: where for name, where in functions.items()
        if name not in referenced and name not in text and name not in ALLOWED
    }
    assert not orphans, (
        "public function(s) nothing names, in code, scripts or docs: "
        + "; ".join(f"{name} at {where[0]}:{where[1]}"
                    for name, where in sorted(orphans.items()))
        + ". Call it, delete it, or add it to ALLOWED with the reason it "
          "should exist uncalled.")


def test_the_allow_list_still_describes_orphans():
    """An allowed name that acquires a caller should leave the list.

    Otherwise the list grows into a reason not to look, which is the failure
    mode of every exception list in this project (F276).
    """
    functions = _public_functions()
    referenced = _names_referenced()
    text = _text_of_scripts_and_docs()
    stale = [name for name in ALLOWED
             if name in functions and (name in referenced or name in text)]
    assert not stale, (
        f"{stale} are in ALLOWED and now referenced: remove them from the list")


def test_the_allow_list_has_no_entries_for_absent_functions():
    functions = _public_functions()
    gone = [name for name in ALLOWED if name not in functions]
    assert not gone, f"{gone} are allow-listed and no longer exist"
