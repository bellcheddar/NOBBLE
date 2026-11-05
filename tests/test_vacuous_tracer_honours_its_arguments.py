"""A diagnostic that took file paths and traced the whole suite anyway.

`tools/vacuous_tests.py` finds assertions that never run, by tracing the
suite under `sys.settrace` and comparing the lines that executed against
every `assert` in `tests/`. Under settrace the whole suite takes minutes, so
passing it the two files just written is the obvious way to use it.

It accepted the paths and discarded them. I passed two files, waited past
the timeout, and stopped it on the assumption it was doing what I asked. A
tool that ignores an argument is worse than one that refuses it: the refusal
is information and the silence is a wrong answer delivered slowly.

The paths now select both halves of what it does, the AST sweep and the
pytest run, and a path that does not exist is refused rather than ignored.

One constraint on this file, which the first draft of it broke. The gate
runs the tracer bare, which traces all of `tests/`, which includes this
file. So nothing here may point the tool at this file or at the suite: the
tool would run pytest, which would run this file, which would run the tool.
The first draft used this file as its sample and hung. Every subprocess
below targets a file generated for the test, whose own run reaches nothing
further.
"""
from __future__ import annotations

import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
TESTS = ROOT / "tests"
TOOL = ROOT / "tools" / "vacuous_tests.py"
sys.path.insert(0, str(ROOT / "tools"))

import vacuous_tests as tracer  # noqa: E402

# A file with one assertion that runs and one that cannot, so a single
# generated target exercises both sides of the report.
SAMPLE = (
    "import pytest\n\n\n"
    "def test_runs():\n"
    "    assert True\n\n\n"
    "def test_skipped():\n"
    "    pytest.skip('deliberate')\n"
    "    assert False\n"
)


def _sample(tmp_path: pathlib.Path) -> pathlib.Path:
    target = tmp_path / "test_generated_sample.py"
    target.write_text(SAMPLE)
    return target


def _run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(TOOL), *args],
                          cwd=ROOT, capture_output=True, text=True,
                          timeout=300)


def test_the_sweep_narrows_to_the_files_it_is_given(tmp_path):
    """The AST half. No subprocess, so this one may name a real test file."""
    everything = tracer.assertion_lines()
    assert len(everything) > 1, "the suite has one test file, so nothing to narrow"
    target = _sample(tmp_path)
    one = tracer.assertion_lines([target])
    assert len(one) == 1, sorted(one)
    assert str(target) in one
    assert len(one[str(target)]) == 2, one


def test_no_argument_still_means_the_whole_suite():
    """The gate runs it bare and must keep getting everything."""
    assert len(tracer.assertion_lines()) == len(list(TESTS.glob("test_*.py")))


def test_a_path_that_does_not_exist_is_refused_rather_than_ignored():
    result = _run("tests/test_no_such_file_exists.py")
    assert result.returncode == 2, result.stdout + result.stderr
    assert "no such test file" in result.stderr


def test_running_it_on_one_file_traces_only_that_file(tmp_path):
    """End to end, which is the only check that would have caught this: the
    old code read as though the paths were used, and did use them for
    nothing."""
    result = _run(str(_sample(tmp_path)))
    assert "in 1 test file(s)" in result.stdout, result.stdout + result.stderr


def test_it_reports_the_assertion_that_could_not_run(tmp_path):
    """Red-green for the tracer itself and not only for its arguments. The
    generated file skips before its second assertion, so a tracer that
    reported nothing would be the failure this tool exists to catch."""
    result = _run(str(_sample(tmp_path)))
    assert "1 assertion(s) never ran" in result.stdout, result.stdout
    assert "test_skipped" in result.stdout
    assert "test_runs" not in result.stdout.split("never ran:")[-1], (
        "the assertion that did run is listed as one that did not"
    )
    assert result.returncode != 0


def test_every_subprocess_target_is_a_generated_file():
    """The constraint in this module's docstring, pinned rather than
    remembered: pointing the tool at this file or at the suite makes the
    gate's bare run recurse.

    Checked structurally. The first version of this check listed the
    forbidden spellings and searched its own source for them, so it matched
    the list it was written with and failed against clean code: the defect
    this session has found six times, now in the guard against it. An AST
    walk reads the call sites instead of the file's text.
    """
    import ast

    tree = ast.parse(pathlib.Path(__file__).read_text())
    calls = [node for node in ast.walk(tree)
             if isinstance(node, ast.Call)
             and isinstance(node.func, ast.Name) and node.func.id == "_run"]
    assert calls, "no subprocess call sites found, so this checks nothing"
    for call in calls:
        for argument in call.args:
            if isinstance(argument, ast.Constant):
                # A literal path that does not exist, for the refusal case.
                assert not (ROOT / str(argument.value)).exists(), argument.value
                continue
            # Anything else must be str(_sample(...)): a file this test made.
            assert isinstance(argument, ast.Call), ast.dump(argument)
            inner = argument.args[0] if argument.args else None
            assert isinstance(inner, ast.Call) and inner.func.id == "_sample", (
                f"line {call.lineno} passes the tool something other than a "
                "generated file"
            )
