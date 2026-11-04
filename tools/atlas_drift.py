#!/usr/bin/env python3
"""Is the published atlas what the current code builds?

F96: F93's superseded-substrate caveat was written, tested and committed,
and was not on the page. `comparison.json` is built by the atlas and the
atlas had not been rebuilt, so the published conclusion ended before the
caveat. Nothing noticed, because nothing compares the published bundle
against what the code would produce.

F88 did that comparison by hand after a day of scoring changes, diffing
11,002 leaf values and finding two deliberate moves. This is that, as a
command: rebuild from the campaign the published atlas names, into a
temporary directory, and compare leaf by leaf.

    python tools/atlas_drift.py            # report, exit 1 on drift
    python tools/atlas_drift.py --quiet    # exit status only

Two categories come back. `moved` is drift that needs explaining and fails
the check. `recomputed` is the design previews' cost, which is a function of
the token-band timings and so moves after every completed job while a
campaign is running: reported, counted, and not a failure. Keeping them
apart is what stops a real difference from arriving as "and 57 more".

Build-time facts are excluded, listed in VOLATILE below. They move every
build by design: when it ran, how many bytes it holds, how far the other
campaigns had got. Everything else should be identical, and a difference
means the published atlas predates a change to the code that produced it.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PUBLISHED = ROOT / "deploy" / "atlas"

# Facts about the build rather than about the science.
VOLATILE = ("built_at", "measured_at", "bytes", "atlas_bytes", "jobs_done",
            "outstanding", "note", "throughput", "measured_at")

# Leaves that are functions of measured throughput, reported separately
# rather than excluded.
#
# VOLATILE excluded `throughput` and not the values computed from it, which
# is the same mistake as F74, F78 and F89: the source was handled and its
# consumers were not. A running campaign remeasures its token bands after
# every job, so every design preview's cost moves with them. Thirteen jobs
# after F97 was committed, the check reported 63 drifted values, all of them
# these, and printed six with "and 57 more": a genuine drift in
# `comparison.json.conclusion`, which is what F96 was, would have been
# somewhere in the 57. A check that fires continuously is the failure F97's
# own write-up warned about, one line away from the exclusion list.
#
# Not excluded, because a cost that moved for a reason other than new
# timings is worth seeing. Matched on the full leaf name rather than on a
# substring, so the category cannot widen quietly: "cost" alone would
# swallow anything with cost in its path.
RECOMPUTED = (".cost.basis", ".cost.projected_hours")


def _leaves(root: Path) -> dict[str, object]:
    out: dict[str, object] = {}
    for path in sorted(root.glob("*.json")):
        try:
            data = json.loads(path.read_text())
        except (OSError, ValueError):
            continue

        def walk(value, trail):
            if isinstance(value, dict):
                for key, item in value.items():
                    walk(item, f"{trail}.{key}")
            elif isinstance(value, list):
                for index, item in enumerate(value):
                    walk(item, f"{trail}[{index}]")
            else:
                out[f"{path.name}{trail}"] = value

        walk(data, "")
    return out


def drift() -> dict:
    """Leaf values that differ between the published atlas and a rebuild."""
    if not (PUBLISHED / "ATLAS.json").exists():
        return {"status": "no published atlas", "moved": [], "campaign": None}
    summary = json.loads((PUBLISHED / "ATLAS.json").read_text())
    campaign = ROOT / "campaigns" / str(summary.get("campaign") or "")
    if not campaign.exists():
        return {"status": f"the published campaign {campaign.name} is gone",
                "moved": [], "campaign": campaign.name}

    with tempfile.TemporaryDirectory() as workdir:
        completed = subprocess.run(
            [sys.executable, "deploy/build_atlas.py", str(campaign)],
            cwd=str(ROOT), capture_output=True, text=True, timeout=1800,
            env={**os.environ, "PYTHONPATH": str(ROOT),
                 "KMP_DUPLICATE_LIB_OK": "TRUE",
                 "NOBBLE_ATLAS_OUT": workdir},
        )
        if completed.returncode != 0:
            return {"status": "the rebuild refused: " +
                              (completed.stderr or "").strip()[-160:],
                    "moved": [], "campaign": campaign.name}
        here, rebuilt = _leaves(PUBLISHED), _leaves(Path(workdir))

    shared = set(here) & set(rebuilt)
    differing = [
        {"key": key, "published": here[key], "rebuilt": rebuilt[key]}
        for key in sorted(shared)
        if here[key] != rebuilt[key]
        and not any(field in key for field in VOLATILE)
    ]
    moved = [row for row in differing
             if not row["key"].endswith(RECOMPUTED)]
    recomputed = [row for row in differing
                  if row["key"].endswith(RECOMPUTED)]
    return {
        "status": "drifted" if moved else "in step",
        "campaign": campaign.name,
        "compared": len(shared),
        "moved": moved,
        "recomputed": recomputed,
        "only_published": sorted(set(here) - set(rebuilt))[:10],
        "only_rebuilt": sorted(set(rebuilt) - set(here))[:10],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)

    report = drift()
    if not args.quiet:
        recomputed = report.get("recomputed") or []
        print(f"   atlas         {report['status']}"
              + (f", {report.get('compared')} leaf value(s) compared"
                 if report.get("compared") else "")
              + (f", {len(recomputed)} recomputed from new timings"
                 if recomputed else ""))
        for row in report["moved"][:6]:
            print(f"      {row['key']}: {row['published']!r} -> {row['rebuilt']!r}")
        if len(report["moved"]) > 6:
            print(f"      and {len(report['moved']) - 6} more")
        if report.get("only_rebuilt"):
            print(f"      the rebuild adds: {report['only_rebuilt']}")
    return 1 if report["moved"] or report["status"].startswith("the rebuild") else 0


if __name__ == "__main__":
    raise SystemExit(main())
