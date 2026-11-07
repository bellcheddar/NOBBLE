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
import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from nobble import paths  # noqa: E402


def _known_good(yaml_name: str, exclude: Path) -> Path | None:
    """The same job's YAML from another campaign, if exactly one has it.

    Exactly one, because two copies that disagree with each other cannot
    both be the reference, and silently taking the first is how F41 and F42
    happened.

    Both sides of the exclusion are resolved, and that is the whole of F145.
    `ROOT.glob` yields absolute paths, so `candidate.parent.parent` is
    absolute; `exclude` is whatever the caller passed, and the chain passes
    `campaigns/campaign_<stamp>` because that is what `newest_complete`
    prints. An absolute path never equals a relative one, so the campaign
    being corrected was not excluded from its own search, every name was
    found twice, and "exactly one" was never true: this returned None for
    every job, on every invocation the chain has ever made.

    The same comparison between two spellings of one path is F32, which this
    file's own call site cites.
    """
    try:
        excluded = exclude.resolve()
    except OSError:
        excluded = exclude
    found = [
        candidate for candidate in sorted(ROOT.glob("campaigns/*/yaml/" + yaml_name))
        if candidate.parent.parent.resolve() != excluded
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
        backup = path.with_suffix(path.suffix + ".bak")
        if not backup.exists():
            # Not overwritten on a second run: the first backup is the one
            # that predates any of this, and that is the one worth keeping.
            shutil.copy(path, backup)

        # Written to a sibling and renamed, not written in place. `state.jsonl`
        # is how a campaign knows which of its 2,360 jobs are done, and
        # `write_text` truncates before it writes: a kill in that window
        # leaves a partial file, and the project's own rule is to assume the
        # process can be killed at any moment. os.replace is atomic within a
        # directory, so a reader sees either the old file or the new one
        # (F109).
        temporary = path.with_suffix(path.suffix + ".rewriting")
        temporary.write_text("\n".join(kept) + ("\n" if kept else ""))
        os.replace(temporary, path)
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

    rows = paths.read_jsonl(queue)
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
    # Every YAML this is about to rewrite has to be inside the campaign
    # named on the command line (F144).
    #
    # `--campaign` chooses which queue to read, and the writes follow the
    # absolute path recorded in each queue row, which is absolute by
    # construction since F32. So pointing this at a copy of a campaign
    # rewrites the original's files, and the copy is left untouched. That is
    # how anyone would test a destructive tool, and it is what I was about
    # to do: a fixture assembled from `cp campaigns/<live>/*.jsonl` carries
    # the live campaign's paths, and `--apply` against the fixture would
    # have edited the running campaign's inputs.
    #
    # Refusing the whole run rather than skipping the offending rows. A
    # queue whose paths point elsewhere is a campaign that has been copied
    # or moved, and the right answer is to say so, not to correct part of
    # something and part of something else.
    outside = []
    root = campaign.resolve()
    for row in jobs:
        resolved = Path(row["yaml"]).resolve()
        if root not in resolved.parents:
            outside.append(str(resolved))
    if outside:
        print(f"REFUSING: {len(outside)} of {len(jobs)} YAML path(s) in this "
              f"queue are outside {root}:", file=sys.stderr)
        for path in outside[:3]:
            print(f"  {path}", file=sys.stderr)
        if len(outside) > 3:
            print(f"  and {len(outside) - 3} more", file=sys.stderr)
        print("This campaign directory holds another campaign's paths, so "
              "correcting it would rewrite that one's inputs. Re-assemble or "
              "rewrite the queue's yaml paths first.", file=sys.stderr)
        return 2

    corrected = 0
    unverified = []
    for row in jobs:
        target = Path(row["yaml"])
        source = _known_good(target.name, campaign)
        if source is None:
            print(f"  ! no known-good copy of {target.name}; left alone")
            unverified.append(target.name)
            continue
        if source.read_text() == target.read_text():
            continue
        shutil.copy(target, target.with_suffix(".yaml.bak"))
        shutil.copy(source, target)
        corrected += 1
    print(f"  corrected {corrected} YAML(s) from a known-good campaign")

    # Dropping the results is what makes the jobs re-run, so it must not
    # happen for a job whose input could not be verified (F146).
    #
    # The two halves of this tool are "regenerate the YAMLs" and "clear the
    # results so they re-run", and the second only makes sense if the first
    # worked. With no known-good copy the input is whatever it already was,
    # so clearing the results re-runs the same jobs on the same bad YAML:
    # the GPU time is spent, the campaign is exactly as stale as before, and
    # `stale_inputs` refuses the publish either way.
    #
    # That is not hypothetical. Under F145 every job returned no known-good
    # copy on every invocation, so the live chain's correction step would
    # have dropped thirty state rows and re-run fifteen jobs on the
    # hydroxyproline YAML it was meant to replace.
    #
    # A job skipped because its YAML already matched the reference is a
    # different case and is not counted here: that input is verified, and
    # re-running it is a legitimate request.
    if unverified:
        print(f"\nREFUSING to clear results: {len(unverified)} of {len(jobs)} "
              "job(s) have no known-good reference, so their YAML is "
              "unchanged and re-running them would repeat the same input.",
              file=sys.stderr)
        print("A reference is another campaign under campaigns/ holding "
              "exactly one copy of the same job's YAML. Check that one "
              "exists and that no scratch directory under campaigns/ is "
              "adding a second.", file=sys.stderr)
        return 2

    for name in ("state.jsonl", "results.jsonl", "scores.jsonl"):
        dropped = _rewrite_without(campaign / name, args.pair_id)
        print(f"  dropped {dropped} row(s) from {name}"
              + (f" (backup at {name}.bak)" if dropped else ""))

    # And the featurised input, which is the half of this that was missing.
    #
    # Boltz writes `boltz_results_<job>/processed/` beside its predictions and
    # reuses it when the job runs again, so replacing the YAML and clearing
    # the result rows is not enough: the re-run reads the old featurisation,
    # spends the full GPU time, writes fresh structures and reports success,
    # while folding exactly the input the correction was meant to remove.
    #
    # That is not hypothetical either. The 6 November chain ran this tool,
    # re-ran all fifteen bench02_BRD4_VHL jobs, and returned ipTM
    # bit-identical to sixteen significant figures. The cached
    # `processed/structures/*.npz` still held chain P residue 1 as HYP while
    # the corrected YAML said PRO (F219). Every check the project had looked
    # at the YAML, so the campaign read as corrected for as long as nobody
    # looked at what was actually folded.
    #
    # The whole output directory goes, not just `processed/`: the structures
    # under it were folded from the input being removed, and keeping them
    # would leave the scorer able to read poses that no longer correspond to
    # any input on disk.
    removed = 0
    for row in jobs:
        output = campaign / "outputs" / row["job_id"]
        if output.exists():
            shutil.rmtree(output)
            removed += 1
    print(f"  removed {removed} cached output directory/ies, so the re-run "
          "featurises the corrected YAML instead of reusing the old one")

    print("\nNow run: bash tools/run_queue.sh --campaign " + str(campaign))
    print("It skips every job already in state, so it runs exactly these.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
