"""The published bundle must not carry local filesystem paths.

`build_atlas` verifies that no PROTAC-DB chemistry reaches the bundle, which
is the licensing constraint spec 2.1 names. Nothing checked the other thing a
build can leak by accident: the absolute path of the machine that built it.

It is not hypothetical. F105 added a diagnostic recording which file a status
was read from, and recorded the resolved path, which published
`/Users/<name>/Documents/...` into `design.json` whenever the build was
invoked with an absolute campaign path. The chain passes a relative one and
the drift check passes an absolute one, so the same campaign produced two
different bundles and the drift check could never settle.

Two failures in one: a home directory on a public page, and a value that
depends on how the build was called rather than on what it describes.
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from nobble.execute.campaign import latest_or_absent as _newest  # noqa: E402

PUBLISHED = ROOT / "deploy" / "atlas"

# Shapes that only ever appear by accident.
LOCAL = (
    re.compile(r"/Users/[^/\"\s]+"),
    re.compile(r"/home/[^/\"\s]+"),
    re.compile(r"/private/(tmp|var)/"),
    re.compile(r"/var/folders/"),
)


def _files():
    """Every published text file, not one extension of it.

    This globbed `*.json` and the bundle also holds `results.jsonl` and
    `scores.jsonl`, which carried 307 build-machine paths between them:
    `yaml`, `output_dir`, the nested `seed_records[].structure` and
    `plip.conect.pdb_path`. `build_atlas`'s own PROTAC-DB leak check already
    scanned both extensions; this one did not, so the test written to catch a
    published home directory could not see the files holding most of them
    (F128).
    """
    if not PUBLISHED.exists():
        pytest.skip("no published atlas")
    return sorted(
        path for path in PUBLISHED.rglob("*")
        if path.is_file() and path.suffix in (".json", ".jsonl", ".txt", ".csv")
    )


def test_no_published_json_carries_an_absolute_local_path():
    offenders = []
    for path in _files():
        text = path.read_text()
        for pattern in LOCAL:
            for found in pattern.findall(text):
                offenders.append(f"{path.name}: {pattern.pattern} -> {found}")
    assert not offenders, offenders[:8]


def test_the_project_root_itself_is_not_in_the_bundle():
    """The most likely form, and the one F105 produced: a path resolved
    against the project root rather than recorded relative to it."""
    root = str(ROOT)
    for path in _files():
        assert root not in path.read_text(), path.name


def test_structure_paths_are_relative_to_the_campaign():
    """A published atlas records structure paths relative to itself while a
    local campaign records absolute ones, and `/structure/<job>.cif` resolves
    them against the campaign directory before checking containment. An
    absolute path from the build machine would not resolve on the droplet."""
    results = PUBLISHED / "campaign.json"
    if not results.exists():
        pytest.skip("no campaign.json in the bundle")
    text = results.read_text()
    for pattern in LOCAL:
        assert not pattern.search(text), (results.name, pattern.pattern)


def test_the_diagnostic_that_caused_this_is_stable_under_both_invocations():
    """Relative and absolute campaign arguments must give the same bundle.
    This is what made the drift check unsettleable: the chain and the drift
    check disagreed about a value neither of them was describing."""
    from nobble.design import report

    campaign = _newest("benchmark")
    if not (campaign / "validation.json").exists():
        pytest.skip("no benchmark validation to read")

    relative = os.path.relpath(campaign, ROOT)
    one = report.build(campaign=Path(relative))["score_validation"]
    two = report.build(campaign=campaign)["score_validation"]
    assert one["read_from"] == two["read_from"], (one, two)
    assert one["searched"] == two["searched"]
    for pattern in LOCAL:
        assert not pattern.search(json.dumps(one)), (pattern.pattern, one)


def test_the_scan_covers_the_jsonl_records():
    """Non-vacuous on purpose. The glob that missed them looked right, and
    the only thing that would have caught it is naming the files."""
    names = {path.name for path in _files()}
    assert "results.jsonl" in names, sorted(names)
    assert "scores.jsonl" in names, sorted(names)
    assert any(name.endswith(".json") for name in names), sorted(names)


def test_the_published_structure_paths_still_point_inside_the_bundle():
    """The fix must not relativise the one field that has a published copy.
    `structure` names a file beside it in `structures/`; everything else is
    provenance pointing back into the campaign."""
    import json

    results = PUBLISHED / "results.jsonl"
    if not results.exists():
        pytest.skip("no published results")
    checked = 0
    for line in results.read_text().splitlines():
        if not line.strip():
            continue
        structure = json.loads(line).get("structure")
        if not structure:
            continue
        assert structure.startswith("structures/"), structure
        assert (PUBLISHED / structure).exists(), structure
        checked += 1
    assert checked > 50, checked


def test_the_provenance_paths_are_project_relative():
    """Kept rather than dropped, because which YAML produced a record is
    worth having; what is not worth having is the name of the directory it
    was built in."""
    import json

    results = PUBLISHED / "results.jsonl"
    if not results.exists():
        pytest.skip("no published results")
    row = json.loads(results.read_text().splitlines()[0])
    for field in ("yaml", "output_dir"):
        value = row.get(field)
        if not value:
            continue
        assert not value.startswith("/"), (field, value)
        assert value.startswith("campaigns/"), (field, value)
