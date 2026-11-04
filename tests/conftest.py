"""Shared fixtures, and one definition of what "the published bundle" means.

F128 found the build machine's absolute paths in `deploy/atlas/results.jsonl`
and `scores.jsonl`, and found that the test written to catch exactly that
globbed `*.json`. Two more of the tests added the same day do the same thing:
the licensing check and the strict-JSON check both enumerate the bundle
themselves, and both miss the two files that hold the records.

Nothing is wrong in either case today. `redact()` is applied to the JSONL
rows, so the only `smiles` tokens there are the encoding label and the
`smiles_fallback` flag rather than chemistry, and both files parse strictly.
What is wrong is three tests each deciding separately what the bundle is,
which is the duplication F106 was about one layer down: the fix is one
definition, not three corrected globs (F129).
"""
from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PUBLISHED = ROOT / "deploy" / "atlas"

# Everything in the bundle that is text a reader or a browser parses. The
# structures themselves are mmCIF and are checked by being served, not by
# being read here.
PUBLISHED_SUFFIXES = (".json", ".jsonl", ".txt", ".csv")


def published_files(suffixes: tuple[str, ...] = PUBLISHED_SUFFIXES) -> list[Path]:
    """Every published text file, by suffix set rather than by one glob."""
    if not PUBLISHED.exists():
        return []
    return sorted(
        path for path in PUBLISHED.rglob("*")
        if path.is_file() and path.suffix in suffixes
    )


@pytest.fixture(scope="session")
def published() -> list[Path]:
    files = published_files()
    if not files:
        pytest.skip("no published atlas on this checkout")
    return files


@pytest.fixture(scope="session")
def published_records() -> list[Path]:
    """Just the JSONL record files, which are the ones most often missed."""
    files = published_files((".jsonl",))
    if not files:
        pytest.skip("no published JSONL records on this checkout")
    return files


def published_documents(suffixes: tuple[str, ...] = (".json", ".jsonl")):
    """Every JSON document in the bundle, from either layout.

    A `.json` file is one document; a `.jsonl` file is one per line. Widening
    a scan from the first to the second is not a glob change, it is a parsing
    change, and the licensing tests failed with a decode error the moment
    their glob was corrected. Yielded as (path, index, document) so a failure
    can name the line (F129).
    """
    import json

    for path in published_files(suffixes):
        text = path.read_text()
        if path.suffix == ".jsonl":
            for number, line in enumerate(text.splitlines(), start=1):
                if line.strip():
                    yield path, number, json.loads(line)
        else:
            yield path, 0, json.loads(text)
