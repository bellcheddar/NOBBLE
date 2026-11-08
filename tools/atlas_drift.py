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
# Overridable for the same reason `build_atlas.py` takes NOBBLE_ATLAS_OUT:
# a reporting tool should be pointable at a bundle other than the live one.
# Two negative-control tests perturb a published file, run this, and restore
# it in a `finally`, which leaves a window where a killed run publishes a
# truncated conclusion. With this they work on a copy (F154).
PUBLISHED = Path(os.environ.get("NOBBLE_ATLAS_PUBLISHED")
                 or ROOT / "deploy" / "atlas")

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



def _refresh_derived(campaign: Path) -> None:
    """Recompute the documents the atlas copies rather than derives.

    `validation.json` is produced by `nobble.validate.layers.run` and copied
    into the bundle verbatim. If the campaign's copy predates a change to
    those layers, so does the published one, and comparing the two says
    nothing. Recomputing here makes the comparison answer the question the
    check is named for: is the published atlas what the current code builds.

    Written into the campaign, which is where `build_atlas.py` reads it from,
    and which is also where `refresh.sh` writes it in the normal flow. This
    is not a side effect the check invents: it is the step the normal flow
    already performs before publishing, and skipping it is what let the
    staleness hide.
    """
    try:
        from nobble.validate.layers import run as run_layers

        payload = run_layers(campaign)
    except Exception as problem:                        # noqa: BLE001
        print(f"   could not recompute validation.json: "
              f"{type(problem).__name__}: {problem}")
    else:
        (campaign / "validation.json").write_text(
            json.dumps(payload, indent=2, default=str))

    # `weights.json` is copied too, and was equally stale: the rebuild that
    # exposed this showed it growing from 475 bytes to 893. Recomputed for
    # the same reason and at no cost, since the fit reads `scores.jsonl` and
    # returns in milliseconds. My first version of this recomputed only
    # validation, which is the narrower-than-the-problem shape five times
    # over today (F172).
    try:
        from nobble.score.weights import fit as fit_weights

        result = fit_weights(campaign)
    except Exception as problem:                        # noqa: BLE001
        print(f"   could not recompute weights.json: "
              f"{type(problem).__name__}: {problem}")
    else:
        payload = result.to_dict() if hasattr(result, "to_dict") else result
        (campaign / "weights.json").write_text(
            json.dumps(payload, indent=2, default=str))

    # `scores.jsonl` is not recomputed, and that is a stated limit rather
    # than an oversight. Scoring runs PLIP and the geometry filter over every
    # structure and takes minutes, which a check the deploy waits on cannot
    # afford. So a stale `scores.jsonl` in a campaign is invisible here, and
    # the thing that keeps it current is `refresh.sh`, which scores before it
    # publishes. `campaign.json` is not recomputed either, because it records
    # what an assembler built and there is nothing to recompute it from.


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
        # The derived documents are refreshed in the copy before the
        # rebuild, because `build_atlas.py` copies them rather than
        # recomputing them, and a rebuild that copies a stale file produces
        # a stale file that matches the stale published one. So this check
        # reported "in step" while the published atlas lacked four fields
        # the code had been producing since F52, F74 and F103: it was
        # comparing stale against stale, and only a rescore of the campaign
        # made the difference visible (F171).
        _refresh_derived(campaign)

        completed = subprocess.run(
            [sys.executable, "deploy/build_atlas.py", str(campaign)],
            cwd=str(ROOT), capture_output=True, text=True, timeout=1800,
            env={**os.environ, "PYTHONPATH": str(ROOT),
                 "KMP_DUPLICATE_LIB_OK": "TRUE",
                 # A directory inside the temporary one, not the
                 # temporary one itself. The build stages into a sibling
                 # of what this names and renames it into place (F327),
                 # so passing `workdir` would stage 798 MB at
                 # `<workdir>_staging`: outside the TemporaryDirectory
                 # that cleans up, and outside the project root.
                 "NOBBLE_ATLAS_OUT": str(Path(workdir) / "atlas")},
        )
        if completed.returncode != 0:
            # The first line of a refusal, not the last 160 characters of
            # stderr. A tail slice cut mid-word and reported "the rebuild
            # refused: ML asks unmodified PRO", which names neither the
            # refusal nor the job: build_atlas prints the reason first and
            # the offending records after it.
            lines = [line.strip() for line in (completed.stderr or "").splitlines()
                     if line.strip()]
            headline = next((line for line in lines if "REFUSED" in line),
                            lines[0] if lines else "no reason printed")
            if len(headline) > 200:
                headline = headline[:197] + "..."
            return {"status": "the rebuild refused: " + headline,
                    "moved": [], "campaign": campaign.name}
        here, rebuilt = _leaves(PUBLISHED), _leaves(Path(workdir) / "atlas")

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
