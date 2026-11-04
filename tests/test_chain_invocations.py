"""Every command the chain runs must be one the code accepts.

tools/run_chain.sh runs seven stages unattended over roughly sixty hours.
A flag argparse does not know, or a module path that has moved, fails at
the moment that stage starts, which may be two days in. None of it is
caught by importing anything: the invocations live in shell strings.

So the shell is parsed for `-m nobble.<module> <args>` and each one is
handed to that module's own parser. Nothing is executed; the parser is
intercepted once it has accepted or rejected the arguments.

This exists because checking it by hand found no defect and took four
attempts to get right: I tried `--campaign` against tier2, which takes a
positional, and read the rejection as a bug in the chain.
"""
from __future__ import annotations

import argparse
import contextlib
import importlib
import io
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

SCRIPTS = sorted((ROOT / "tools").glob("*.sh")) + sorted((ROOT / "deploy").glob("*.sh"))
INVOCATION = re.compile(r"-m\s+(nobble\.[A-Za-z0-9_.]+)([^|&;\n]*)")

# Shell expansions, stubbed with something a parser will accept. A campaign
# path is never opened here because nothing runs.
SUBSTITUTIONS = {
    '"$CAMPAIGN"': "campaigns/x",
    '"$CORRECTED"': "campaigns/x",
    '"$BASELINE"': "campaigns/x",
    '"$DESIGN"': "campaigns/x",
    '"$@"': "",
}


def _invocations():
    found = []
    for script in SCRIPTS:
        text = script.read_text()
        for match in INVOCATION.finditer(text):
            module, raw = match.group(1), match.group(2)
            raw = raw.split("2>")[0]
            for needle, replacement in SUBSTITUTIONS.items():
                raw = raw.replace(needle, replacement)
            if "$" in raw:                  # an expansion we cannot resolve
                continue
            argv = [token for token in raw.split() if token]
            found.append((script.name, module, argv))
    return found


def test_the_shell_actually_invokes_python_modules():
    """A guard on the guard: if the chain stops using `-m nobble.…` this
    file would pass by finding nothing to check."""
    found = _invocations()
    assert len(found) >= 8, f"only {len(found)} invocation(s) parsed out of the shell"
    assert {module for _s, module, _a in found} >= {
        "nobble.score.run", "nobble.execute.runner", "nobble.execute.tier2",
    }


@pytest.mark.parametrize(
    "script,module,argv",
    _invocations(),
    ids=lambda value: value if isinstance(value, str) else "-".join(value) or "noargs",
)
def test_every_chain_invocation_parses(script, module, argv):
    target = importlib.import_module(module)
    assert hasattr(target, "main"), f"{module} has no main() for {script} to call"

    accepted = argparse.ArgumentParser.parse_args
    sentinel = RuntimeError("arguments accepted")

    def intercept(self, args=None, namespace=None):
        accepted(self, argv, namespace)      # raises SystemExit if rejected
        raise sentinel

    argparse.ArgumentParser.parse_args = intercept
    original_argv = sys.argv
    sys.argv = [module, *argv]
    try:
        with contextlib.redirect_stdout(io.StringIO()), \
             contextlib.redirect_stderr(io.StringIO()) as captured:
            target.main()
    except RuntimeError as problem:
        if problem is not sentinel:
            raise
    except SystemExit as problem:
        pytest.fail(
            f"{script} runs `-m {module} {' '.join(argv)}` and its parser "
            f"rejects it (exit {problem.code}): {captured.getvalue().strip()[:200]}"
        )
    finally:
        argparse.ArgumentParser.parse_args = accepted
        sys.argv = original_argv
