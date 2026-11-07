"""The atlas build reads files a runner appends to (F301).

F111 found seven readers of `results.jsonl` and `state.jsonl` that parsed
every line strictly, and fixed them. It did not reach `deploy/`:
`build_atlas.py` had six line-by-line readers and no use of
`paths.read_jsonl` at all. Three of them called `json.loads` per line, so a
kill at the wrong moment would have failed the build; the other three counted
`splitlines()`, so a torn line was counted as a job and inflated a total,
which is a denominator wrong in the direction that reads as more complete
than it is.

The build runs straight after a runner in `tools/refresh.sh`, so a torn final
line is an ordinary state and not a reason to fail.
"""
from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from nobble import paths                                    # noqa: E402

ROW = {"job_id": "j1", "pair_id": "p1", "status": "done", "tokens": 100}


def test_no_reader_in_the_build_parses_a_line_by_hand():
    source = (ROOT / "deploy" / "build_atlas.py").read_text()
    assert "read_text().splitlines()" not in source, (
        "a line-by-line reader is back in the atlas build: a torn final line "
        "from a kill mid-write would fail the build or inflate a total"
    )
    assert source.count("paths.read_jsonl") >= 4


def test_every_jsonl_read_is_torn_tolerant():
    """Not just present: `read_jsonl` without the flag raises on a torn
    line, which is the whole hazard."""
    source = (ROOT / "deploy" / "build_atlas.py").read_text()
    tree = ast.parse(source)
    calls = [node for node in ast.walk(tree)
             if isinstance(node, ast.Call)
             and isinstance(node.func, ast.Attribute)
             and node.func.attr == "read_jsonl"]
    assert calls, "no read_jsonl call to check"
    for call in calls:
        flags = {keyword.arg for keyword in call.keywords}
        assert "tolerate_torn" in flags, (
            f"a read_jsonl call on line {call.lineno} omits tolerate_torn"
        )


def test_a_torn_line_is_skipped_and_not_counted(tmp_path):
    """The behaviour the build now relies on, asserted on the reader itself
    rather than inferred from its name."""
    path = tmp_path / "state.jsonl"
    path.write_text(json.dumps(ROW) + "\n"
                    + json.dumps(dict(ROW, job_id="j2")) + "\n"
                    + json.dumps(dict(ROW, job_id="torn"))[:20])
    rows = paths.read_jsonl(path, tolerate_torn=True)
    assert [row["job_id"] for row in rows] == ["j1", "j2"]


def test_the_strict_reader_still_raises(tmp_path):
    """So the tolerant flag is doing something, and a file that should be
    whole is still checked as whole somewhere."""
    import pytest

    path = tmp_path / "scores.jsonl"
    path.write_text(json.dumps(ROW)[:10])
    with pytest.raises(Exception):
        paths.read_jsonl(path)
