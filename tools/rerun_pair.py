#!/usr/bin/env python3
"""Restore one pair's YAMLs from a known-good campaign and clear its results.

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

It copies the pair's YAMLs from another campaign that holds exactly one copy
of each, drops its rows from state.jsonl and results.jsonl, and leaves the
running to `tools/run_queue.sh`, which skips every job already in state and so
runs exactly the ones this removed.

**It does not regenerate from code**, and this docstring said twice that it
did. The difference decides whether the tool can fix a given pair at all. F47
is correctable here because the corrected YAML exists in another campaign; a
pair whose YAML was wrong in every campaign, because the assembler that wrote
it was wrong, has no reference to copy and this refuses by design (F146). That
is the case for `scr_bench03_BRD4_CRBN`, whose ternary YAMLs were written
without their glue (F262): the fix is in the assembler, so the correct YAML
has never existed on disk anywhere. See `--regenerate` below (F265).
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


def _belongs(row: dict, pair_id: str) -> bool:
    """Is this row one of `pair_id`'s?

    One predicate, used by the rewrite and by the dry run that predicts it.
    Two copies of this test would be two things to keep in step, and a dry
    run that counts rows by a different rule than the rewrite drops them by
    is a rehearsal of a different operation.
    """
    job_id = row.get("job_id") or ""
    return row.get("pair_id") == pair_id or job_id.startswith(pair_id + "__")


def _would_drop(path: Path, pair_id: str) -> int:
    """How many rows `_rewrite_without` would drop, without dropping them."""
    if not path.exists():
        return 0
    dropped = 0
    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if _belongs(row, pair_id):
            dropped += 1
    return dropped


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
        if _belongs(row, pair_id):
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


def _cached_outputs(campaign: Path, jobs: list[dict]) -> list[str]:
    """Which of these jobs still has a Boltz output directory on disk."""
    return [row["job_id"] for row in jobs
            if (campaign / "outputs" / row["job_id"]).exists()]


def _folded_disagreements(campaign: Path, pair_id: str) -> list[str] | None:
    """Jobs of `pair_id` whose cached featurisation disagrees with the YAML.

    None when the comparison could not be made, which is not the same as
    none found: a caller that reads a failed import as a clean campaign is
    the F216 mistake in a different file.
    """
    sys.path.insert(0, str(ROOT / "tools"))
    try:
        import stale_featurisation as featurisation
    except ImportError:
        return None
    try:
        rows = featurisation.disagreements(campaign)
    except OSError:
        return None
    return sorted(row["job_id"] for row in rows
                  if row["job_id"].startswith(pair_id + "__"))


def _rehearse(campaign: Path, pair_id: str, jobs: list[dict],
              references: dict[str, Path | None], unverified: list[str]) -> int:
    """Say what --apply would do, including the parts that are destructive.

    The first version of this reported the state rows and the YAMLs and
    stopped there, which left out the cached featurised inputs: the one step
    whose absence made the 6 November correction re-fold the molecule it was
    correcting (F219). A rehearsal that omits the step that failed rehearses
    the wrong operation, and reading it would have given exactly the
    confidence that was misplaced the first time.
    """
    if unverified:
        print(f"\nWOULD REFUSE: {len(unverified)} of {len(jobs)} job(s) have "
              "no known-good reference, so --apply would correct nothing and "
              "exit 2 rather than clear results and re-run the same input "
              "(F146).", file=sys.stderr)
        for job_id in unverified[:3]:
            print(f"  {job_id}", file=sys.stderr)
        if len(unverified) > 3:
            print(f"  and {len(unverified) - 3} more", file=sys.stderr)
        return 2

    differ = sum(1 for row in jobs
                 if references[row["job_id"]].read_text()
                 != Path(row["yaml"]).read_text())
    print(f"  {differ} of {len(jobs)} YAML(s) differ from their known-good "
          f"reference and would be rewritten; {len(jobs) - differ} already "
          "match")

    for name in ("state.jsonl", "results.jsonl", "scores.jsonl"):
        print(f"  {_would_drop(campaign / name, pair_id)} row(s) would be "
              f"dropped from {name}")

    cached = _cached_outputs(campaign, jobs)
    print(f"  {len(cached)} cached output directory/ies would be removed, so "
          "the re-run featurises the corrected YAML instead of reusing the "
          "old one")

    folded = _folded_disagreements(campaign, pair_id)
    if folded is None:
        print("  cannot say what was folded: the featurisation comparison "
              "could not be run, so whether the cache matches the YAML is "
              "unknown rather than fine")
    elif folded:
        print(f"  {len(folded)} of those hold a featurisation that disagrees "
              "with the YAML today, which is what this removes")
    else:
        print("  none of those disagrees with its YAML today, so there is no "
              "stale featurisation left to clear")

    print("  rerun with --apply to do it")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pair_id")
    parser.add_argument("--campaign", required=True)
    parser.add_argument("--apply", action="store_true",
                        help="without this, report what would change and stop")
    parser.add_argument("--regenerate", action="store_true",
                        help="rebuild the YAMLs from the current code instead "
                             "of copying them from another campaign, for a "
                             "pair whose correct YAML has never existed on "
                             "disk anywhere")
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

    # Resolved before the --apply branch, not inside it, because the dry run
    # exists to say what the real run will do and this is the thing it most
    # often will not do. `--apply` refuses outright when any job has no
    # known-good reference (F146), so a dry run that skips the lookup can
    # promise fifteen corrected YAMLs where the real run corrects none and
    # exits 2. Under F145 that was every invocation.
    if args.regenerate:
        # The verification F146 asks for, by the thing it is actually about.
        # A known-good reference is a proxy for "the input will change"; the
        # direct test is whether the regenerated document differs from what
        # is on disk. Both refuse to clear results and re-run an identical
        # input, which is the whole point of the guard, and this one also
        # works for a pair whose correct YAML has never existed anywhere
        # because the assembler that wrote it was wrong (F262, F265).
        from nobble.execute.campaign import regenerate_pair

        fresh = regenerate_pair(args.pair_id)
        missing = sorted(row["job_id"] for row in jobs
                         if row["job_id"] not in fresh)
        if missing:
            print(f"the current code emits no YAML for {len(missing)} of "
                  f"{len(jobs)} job(s) of this pair, so regenerating would "
                  "silently leave them as they are: "
                  f"{missing[:3]}", file=sys.stderr)
            return 2
        rewrites = {row["job_id"]: fresh[row["job_id"]] for row in jobs
                    if fresh[row["job_id"]] != Path(row["yaml"]).read_text()}
        if not rewrites:
            print(f"\nREFUSING: the current code regenerates all "
                  f"{len(jobs)} YAML(s) byte-identical to what is on disk, so "
                  "there is nothing to correct and clearing the results would "
                  "re-run the same input (F146).", file=sys.stderr)
            return 2
        print(f"  {len(rewrites)} of {len(jobs)} YAML(s) differ from what the "
              "current code emits and would be rewritten")
        if not args.apply:
            for job_id in sorted(rewrites):
                print(f"    {job_id}")
            for name in ("state.jsonl", "results.jsonl", "scores.jsonl"):
                print(f"  {_would_drop(campaign / name, args.pair_id)} row(s) "
                      f"would be dropped from {name}")
            cached = _cached_outputs(campaign, jobs)
            print(f"  {len(cached)} cached output directory/ies would be "
                  "removed, so the re-run featurises the corrected YAML")
            print("  rerun with --apply --regenerate to do it")
            return 0
        for job_id, text in sorted(rewrites.items()):
            target = Path(next(row["yaml"] for row in jobs
                               if row["job_id"] == job_id))
            shutil.copy(target, target.with_suffix(".yaml.bak"))
            target.write_text(text)
        print(f"  regenerated {len(rewrites)} YAML(s) from the current code")
        references = {row["job_id"]: Path(row["yaml"]) for row in jobs}
        unverified = []
    else:
        references = {row["job_id"]: _known_good(Path(row["yaml"]).name, campaign)
                      for row in jobs}
        unverified = sorted(job_id for job_id, source in references.items()
                            if source is None)

    if not args.apply:
        return _rehearse(campaign, args.pair_id, jobs, references, unverified)

    corrected = 0
    for row in jobs:
        target = Path(row["yaml"])
        source = references[row["job_id"]]
        if source is None:
            print(f"  ! no known-good copy of {target.name}; left alone")
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
        # One path component, for the reason the runner states: an empty id
        # makes this the whole outputs directory, and this tool is run by
        # hand with --apply.
        job_id = row["job_id"]
        if (not job_id or job_id in (".", "..")
                or Path(job_id).parts != (job_id,)):
            print(f"REFUSING: job id {job_id!r} is not a single path "
                  "component, so the directory it names cannot be removed "
                  "safely", file=sys.stderr)
            return 2
        output = campaign / "outputs" / job_id
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
