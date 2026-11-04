"""Every configured key a module reads must exist in the file it reads from.

Read with `["key"]` a missing key raises on the first call, which is loud
and gets fixed. Read with `.get("key")` it returns None, and None then flows
into whatever the value was for: a threshold that is None compares false
against everything, a scale that is None raises somewhere else entirely, and
a device that is None is passed to Boltz as a string.

Both forms are checked here against the actual TOML, because the point is
not which form is used but that the key is real. 89 chains resolve today, so
this is a guard rather than a repair (F95).

Related, and the reason it is worth the file: `tuning.campaign.seeds` was a
key the TOML had and nothing read, which F91 found. This is the other
direction, a key Python reads and the TOML might not have.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from nobble import paths  # noqa: E402

CALL = re.compile(r"paths\.(thresholds|tuning)\(\)")
KEY = re.compile(r'\A\s*(?:\[\s*"([^"]+)"\s*\]|\.get\(\s*"([^"]+)")')
SKIP_PARTS = {".git", "__pycache__", ".pixi", "node_modules", ".venv"}


def _chains() -> list[tuple[str, str, list[str], bool]]:
    """Every (where, document, key chain, used_get) in the project."""
    found = []
    for path in sorted(ROOT.rglob("*.py")):
        if any(part in SKIP_PARTS for part in path.parts):
            continue
        text = path.read_text()
        for match in CALL.finditer(text):
            rest = text[match.end():]
            keys, used_get = [], False
            while True:
                key = KEY.match(rest)
                if not key:
                    break
                keys.append(key.group(1) or key.group(2))
                used_get = used_get or bool(key.group(2))
                rest = rest[key.end():]
            if keys:
                line = text[:match.start()].count("\n") + 1
                found.append((f"{path.relative_to(ROOT)}:{line}",
                              match.group(1), keys, used_get))
    return found


def _exists(document: dict, keys: list[str]) -> bool:
    node = document
    for key in keys:
        if not isinstance(node, dict) or key not in node:
            return False
        node = node[key]
    return True


def test_every_configured_key_read_in_python_exists():
    documents = {"thresholds": paths.thresholds(), "tuning": paths.tuning()}
    missing = [
        f"{where}: {document}{keys} via {'get' if used_get else 'index'}"
        for where, document, keys, used_get in _chains()
        if not _exists(documents[document], keys)
    ]
    assert not missing, (
        "configured key(s) read in Python that the file does not hold:\n"
        + "\n".join(missing)
    )


def test_the_sweep_finds_the_chains_it_is_meant_to():
    """A sweep that matched nothing would pass whatever the config held.
    The count is asserted loosely: exactly is brittle, zero is useless."""
    chains = _chains()
    assert len(chains) > 50, (
        f"only {len(chains)} config reads found, so the pattern has stopped "
        "matching the way the project reads configuration"
    )
    documents = {document for _where, document, _keys, _get in chains}
    assert documents == {"thresholds", "tuning"}, documents


def test_the_sweep_would_catch_a_typo():
    """The negative control, in memory. A key one letter wrong is the whole
    failure mode, and with `.get` it is silent."""
    document = {"scoring": {"rmsd_breakpoints": [1.0]}}
    assert _exists(document, ["scoring", "rmsd_breakpoints"])
    assert not _exists(document, ["scoring", "rmsd_breakpoint"])
    assert not _exists(document, ["scorring", "rmsd_breakpoints"])
    assert not _exists(document, ["scoring", "rmsd_breakpoints", "deeper"])
