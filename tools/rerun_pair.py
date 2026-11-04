#!/usr/bin/env python3
"""Regenerate one pair's YAMLs and clear its results so it reruns.

Written for F47. The main campaign's `bench02_BRD4_VHL` jobs were emitted
with a hydroxyproline on BRD4 Pro379, because the modification rule keyed
on the E3 rather than on the degron class. The rule is fixed; the YAMLs
already on disk are not, and four of the pair's fifteen jobs had run
before it was found.

Regenerating mid-run would be worse than leaving it: the eleven unrun jobs
would take the corrected YAML and the four finished ones would keep the
old result, so one pair would hold two different inputs. So this is a
deliberate, separate step, to be run when the GPU is free and before the
final atlas rebuild.

    python tools/rerun_pair.py bench02_BRD4_VHL --campaign campaigns/campaign_...

It regenerates the pair's YAMLs from the current code, drops its rows from
state.jsonl and results.jsonl, and leaves the running to
`tools/run_queue.sh`, which skips every job already in state and so runs
exactly the ones this removed.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def _known_good(yaml_name: str, exclude: Path) -> Path | None:
    """The same job's YAML from another campaign, if exactly one has it.

    Exactly one, because two copies that disagree with each other cannot
    both be the reference, and silently taking the first is how F41 and F42
    happened.
    """
    found = [
        candidate for candidate in sorted(ROOT.glob("campaigns/*/yaml/" + yaml_name))
        if candidate.parent.parent != exclude
    ]
    if len(found) != 1:
        return None
    return found[0]


def _rewrite_without(path: Path, pair_id: str) -> int:
    """Drop every row of `pair_id`, keeping a .bak of what was there."""
    if not path.exists():
        return 0
    rows = [line for line in path.read_text().splitlines() if line.strip()]
    kept, dropped = [], 0
    for line in rows:
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            kept.append(line)
            continue
        job_id = row.get("job_id") or ""
        if row.get("pair_id") == pair_id or job_id.startswith(pair_id + "__"):
            dropped += 1
            continue
        kept.append(line)
    if dropped:
        shutil.copy(path, path.with_suffix(path.suffix + ".bak"))
        path.write_text("\n".join(kept) + ("\n" if kept else ""))
    return dropped


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pair_id")
    parser.add_argument("--campaign", required=True)
    parser.add_argument("--apply", action="store_true",
                        help="without this, report what would change and stop")
    args = parser.parse_args(argv)

    campaign = Path(args.campaign).resolve()
    queue = campaign / "queue.jsonl"
    if not queue.exists():
        print(f"no queue at {queue}", file=sys.stderr)
        return 2

    rows = [json.loads(line) for line in queue.read_text().splitlines() if line.strip()]
    jobs = [row for row in rows if row.get("pair_id") == args.pair_id]
    if not jobs:
        print(f"{args.pair_id} is not in {queue.name}", file=sys.stderr)
        return 2

    print(f"{args.pair_id}: {len(jobs)} job(s) in the queue")
    if not args.apply:
        state = campaign / "state.jsonl"
        done = sum(1 for line in state.read_text().splitlines()
                   if line.strip() and json.loads(line).get("job_id", "").startswith(
                       args.pair_id + "__")) if state.exists() else 0
        print(f"  {done} row(s) in state.jsonl would be dropped")
        print(f"  {len(jobs)} YAML(s) would be regenerated")
        print("  rerun with --apply to do it")
        return 0

    # Corrected against a known-good copy of the same job from another
    # campaign, rather than re-derived.
    #
    # Re-deriving means calling assemble_campaign, which writes a whole new
    # campaigns/campaign_<stamp> directory, and both the chain and status.sh
    # select their campaign with `ls -d campaigns/campaign_* | tail -1`. A
    # scratch assembly would become "the latest campaign" and the chain's
    # remaining stages would target it. Factoring the emission path out so one
    # pair can be regenerated in place is the right fix and not one to make
    # while a 42-hour run is reading those files.
    #
    # The comparison copy is independently trustworthy: it predates the bug,
    # and diffing the two showed one difference, the modifications block.
    corrected = 0
    for row in jobs:
        target = Path(row["yaml"])
        source = _known_good(target.name, campaign)
        if source is None:
            print(f"  ! no known-good copy of {target.name}; left alone")
            continue
        if source.read_text() == target.read_text():
            continue
        shutil.copy(target, target.with_suffix(".yaml.bak"))
        shutil.copy(source, target)
        corrected += 1
    print(f"  corrected {corrected} YAML(s) from a known-good campaign")

    for name in ("state.jsonl", "results.jsonl", "scores.jsonl"):
        dropped = _rewrite_without(campaign / name, args.pair_id)
        print(f"  dropped {dropped} row(s) from {name}"
              + (f" (backup at {name}.bak)" if dropped else ""))

    print("\nNow run: bash tools/run_queue.sh --campaign " + str(campaign))
    print("It skips every job already in state, so it runs exactly these.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
