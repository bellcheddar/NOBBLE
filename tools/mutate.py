#!/usr/bin/env python3
"""Mutation sweep: change one thing, see whether the suite notices.

Five sweeps with this found eleven real gaps, and every one was the same
shape: code whose correct and incorrect behaviours produce the same
observable result on the data at hand. A count that is zero either way, a
minimum equal to the median, a guard for a condition that has not yet
arisen, an MSA whose absence makes predictions worse rather than absent.
None of it was the complicated code.

It also left a mutation in the working tree once. The sweep was stopped
between writing a mutation and the `finally` that restores it, so
`curate/library.py` sat with its selection replaced by every candidate
(F45). This version is built around that:

  * it refuses to start on a dirty tree, so a leftover from a previous run
    is caught before it can be mistaken for real work;
  * it restores on SIGINT and SIGTERM as well as on the normal path;
  * it verifies the tree is clean before it exits, and says loudly if not.

Two later lapses came from not using it. Both were hand-rolled shell loops
that mutated a file, ran pytest and restored with a trap, and both reached
live state. One removed the atlas build's refusal, and the test that then
ran rebuilt the published atlas from a campaign with 54 of 2360 jobs
scored. The other rewrote a live campaign's `queue.jsonl` while the runner
was reading it. Neither did lasting harm, because the atlas is tracked and
the queue was restored byte-identically, but both were luck rather than
method.

The reason they were hand-rolled is that this tool only ran a fixed list,
so a one-off check was easier to write in the shell than to add here. That
is now the first thing fixed: `--file/--find/--replace` runs an ad-hoc
mutation under the same rails. The second is that mutation testing removes
a safety deliberately, so the tests run under it can reach things no test
should touch. Live state is fingerprinted before and after every run and
any change is reported, whatever caused it (F66).

Usage:
    python tools/mutate.py                 # every mutation in MUTATIONS
    python tools/mutate.py --only msa      # those whose label matches
    python tools/mutate.py --list
    python tools/mutate.py --file nobble/validate/inputs.py \
        --find 'if sorted(on_disk) != sorted(wanted):' --replace 'if False:' \
        --tests tests/test_stale_inputs.py
"""
from __future__ import annotations

import argparse
import hashlib
import signal
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PYTEST = [str(ROOT / ".." / "BINMAN" / ".pixi" / "envs" / "default" / "bin" / "python"),
          "-m", "pytest", "tests/", "-x", "-q"]

# (file, label, find, replace). `find` must appear exactly once.
MUTATIONS: list[tuple[str, str, str, str]] = [
    ("nobble/curate/tiers.py", "the named Tier A ligases stop being mandatory",
     "        if candidate.gene in TIER_A_NAMED:", "        if False:"),
    ("nobble/curate/tiers.py", "the pocket-druggability floor is removed",
     "    stage = [item for item in pool if (item.pocket_score or 0.0) >= pocket_min]",
     "    stage = list(pool)"),
    ("nobble/curate/plddt.py", "the best pLDDT window becomes the first window",
     "            if running > best_total:", "            if False:"),
    ("nobble/curate/plddt.py", "CA atoms stop being preferred for the profile",
     '            atoms = [atom for atom in residue if atom.name == "CA"] or list(residue)',
     "            atoms = list(residue)"),
    ("nobble/curate/library.py", "the diversity reduction's selection is ignored",
     "    selected = [by_id[pid] for pid in reduction.selected_ids if pid in by_id]",
     "    selected = list(by_id.values())"),
]

# Where a mutation may be written. Everything else is either live state or
# not source, and a sweep has no business in it.
#
# `tests` is included because several of this project's checks are
# implemented in test files rather than in the package: the cutoff sweeps,
# the template sweep, the house-style sweep. Verifying that one of those
# still fires means mutating the file it lives in, and the negative
# controls beside it are the coverage that makes the result mean anything.
# Mutating a test with nothing else covering it reports "not caught"
# truthfully and tells you only that you weakened the sole check.
MUTABLE_ROOTS = ("nobble", "tools", "deploy", "qc", "tests")

# Live state: campaign results and queues, the published atlas, measured
# throughput. A test run under a mutation must leave every one of these
# exactly as it found them. Fingerprinted rather than made read-only,
# because the thing to detect is a test writing them at all, and a
# permission error would be reported as a test failure and read as the
# mutation having been caught.
PROTECTED_GLOBS = (
    "campaigns/*/results.jsonl",
    "campaigns/*/queue*.jsonl",
    "campaigns/*/state.jsonl",
    "campaigns/*/campaign.json",
    "campaigns/*/scores*.jsonl",
    "deploy/atlas/*.json",
    "deploy/atlas/*.jsonl",
    "data/throughput.json",
)

_active: tuple[Path, str] | None = None     # (path, original text)


def _restore() -> None:
    global _active
    if _active is not None:
        path, original = _active
        path.write_text(original)
        _active = None


def _on_signal(signum, _frame):             # noqa: ANN001
    _restore()
    print(f"\ninterrupted by signal {signum}; the mutation was restored",
          file=sys.stderr)
    raise SystemExit(130)


def _dirty_files() -> set[str]:
    out = subprocess.run(["git", "status", "--porcelain"], cwd=ROOT,
                         capture_output=True, text=True).stdout
    return {line[3:].strip() for line in out.splitlines()
            if line and not line.startswith("??")}


def _check(paths: set[str]) -> tuple[bool, str]:
    """Whether the files this sweep touches are clean.

    Scoped on both sides, and it took three goes to get there.

    No check at all let a stopped run leave a mutation in the tree (F45).
    An unscoped exit check then reported an unrelated edit made during the
    sweep, a PROGRESS.md note, as "the sweep left a mutation behind", and a
    false alarm about the thing a check exists to catch is worse than no
    check. An unscoped entry check then refused to start because two new
    test files were staged, which were never at risk.

    The reason the scope is right is that this tool restores from an
    in-memory copy of the file rather than from git, so an uncommitted
    change elsewhere is not in danger. What is dangerous is an uncommitted
    change in a file this sweep is about to read as its "original": if a
    previous run left a mutation there, this run would restore to it and
    carry it forward.
    """
    dirty = _dirty_files() & paths
    return (not dirty), "\n".join(sorted(dirty))


def _fingerprint() -> dict[str, str]:
    """Size and mtime of every protected file, keyed by relative path.

    Hashing the campaign's results would mean reading hundreds of megabytes
    between every mutation. Size and mtime detect a rewrite, which is what
    a test writing live state does, and a rewrite that preserves both is
    not a failure mode worth the cost of hashing.
    """
    out = {}
    for pattern in PROTECTED_GLOBS:
        for path in sorted(ROOT.glob(pattern)):
            stat = path.stat()
            out[str(path.relative_to(ROOT))] = f"{stat.st_size}:{stat.st_mtime_ns}"
    return out


def _prefix_hashes() -> dict[str, str]:
    """Digest of each protected file as it stands now.

    Taken by the caller at the same moment as `_fingerprint`, and passed
    back in for the comparison. It was a module-level dict that
    `_fingerprint` filled as a side effect, which destroyed the thing it
    was for: `_live_state_changes` calls `_fingerprint` to get the "after"
    state, so the baseline hashes were overwritten with the new content's
    before any comparison happened, and every append still read as a
    rewrite. A function that looks like a measurement and quietly replaces
    the baseline is the shape of defect this project keeps finding, and I
    wrote one into the fix for another.
    """
    out = {}
    for pattern in PROTECTED_GLOBS:
        for path in sorted(ROOT.glob(pattern)):
            with path.open("rb") as handle:
                out[str(path.relative_to(ROOT))] = hashlib.sha256(
                    handle.read()).hexdigest()
    return out


def _grew_by_appending(path: Path, before_size: int, before_hash: str) -> bool:
    """Did this file only gain bytes on the end?

    The campaign runner appends a line to `results.jsonl` and `state.jsonl`
    every thirty-five seconds or so, which is its job. A test that corrupts
    live state does something else: it rewrites the file, which is what
    happened when one of mine replaced a running campaign's measurement with
    a benchmark's (F131).

    Those two are distinguishable, and the sweep could not tell them apart.
    It compared size and mtime, so any write at all exited 4, and with a
    campaign running the mutation harness's own tests failed intermittently
    for a reason that had nothing to do with the mutation (F142).

    Exact rather than heuristic: the bytes that were there are re-read and
    compared against what is there now. A pure append leaves the prefix
    identical. Only `before_size` bytes are read, so this costs the same
    whether the file is a kilobyte or a gigabyte.
    """
    try:
        stat = path.stat()
    except OSError:
        return False
    if stat.st_size < before_size:
        return False            # truncated: a rewrite, not an append
    with path.open("rb") as handle:
        prefix = handle.read(before_size)
    return hashlib.sha256(prefix).hexdigest() == before_hash


def _live_state_changes(before: dict[str, str],
                        before_hashes: dict[str, str] | None = None) -> list[str]:
    after = _fingerprint()
    changed = []
    for name in sorted(set(before) | set(after)):
        if before.get(name) == after.get(name):
            continue
        was = "absent" if name not in before else before[name]
        now = "absent" if name not in after else after[name]
        if name in before and name in after and (before_hashes or {}).get(name):
            before_size = int(before[name].split(":")[0])
            if _grew_by_appending(ROOT / name, before_size,
                                  before_hashes[name]):
                # The runner doing its job, not the sweep reaching live
                # state. Reported so the operator can see it happened.
                print(f"    {name} grew by appending while the sweep ran: "
                      "the campaign runner, not the mutation")
                continue
        changed.append(f"  {name}: {was} -> {now}")
    return changed


def _refuse_protected(relative: str) -> str | None:
    """Why this file may not be mutated, or None if it may."""
    path = Path(relative)
    if path.is_absolute() or ".." in path.parts:
        return "outside the project"
    for pattern in PROTECTED_GLOBS:
        if path.match(pattern):
            return "live state, not source"
    if not path.parts or path.parts[0] not in MUTABLE_ROOTS:
        return f"not under {'/, '.join(MUTABLE_ROOTS)}/"
    return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--only", default=None,
                        help="run only mutations whose label contains this")
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--file", default=None,
                        help="an ad-hoc mutation: the file to change")
    parser.add_argument("--find", default=None, help="text to replace, once")
    parser.add_argument("--replace", default=None, help="what to put there")
    parser.add_argument("--tests", default=None,
                        help="pytest target for an ad-hoc mutation "
                             "(default: the whole suite)")
    args = parser.parse_args(argv)

    if args.file or args.find is not None or args.replace is not None:
        if not (args.file and args.find is not None and args.replace is not None):
            print("--file, --find and --replace go together", file=sys.stderr)
            return 2
        chosen = [(args.file, f"ad hoc: {args.find.strip()[:40]}",
                   args.find, args.replace)]
    else:
        chosen = [m for m in MUTATIONS
                  if args.only is None or args.only.lower() in m[1].lower()]
    if args.list:
        for path, label, _f, _r in chosen:
            print(f"  {path:32s} {label}")
        return 0
    if not chosen:
        print("no mutation matched", file=sys.stderr)
        return 2

    refused = {relative: reason for relative in
               {r for r, _l, _f, _r in chosen}
               if (reason := _refuse_protected(relative))}
    if refused:
        for relative, reason in sorted(refused.items()):
            print(f"refusing to mutate {relative}: {reason}", file=sys.stderr)
        return 2

    touched = {relative for relative, _l, _f, _r in chosen}
    clean, dirty = _check(touched)
    if not clean:
        print("refusing to start: these files have uncommitted changes and "
              "this sweep is about to read them as its baseline, so a "
              "mutation left by an earlier run would be carried forward.\n"
              f"{dirty}", file=sys.stderr)
        return 2

    signal.signal(signal.SIGINT, _on_signal)
    signal.signal(signal.SIGTERM, _on_signal)

    pytest_command = list(PYTEST)
    if args.tests:
        pytest_command = pytest_command[:-3] + ["-q", args.tests]
    live_before = _fingerprint()
    live_hashes_before = _prefix_hashes()
    print(f"watching {len(live_before)} live-state file(s) for changes")

    global _active
    missed = 0
    skipped = 0
    try:
        for relative, label, find, replace in chosen:
            path = ROOT / relative
            original = path.read_text()
            if original.count(find) != 1:
                # Counted, not just printed. A skipped mutation used to fall
                # through to the summary as though it had been caught,
                # because `missed` was the only counter and `continue`
                # skipped it: a sweep whose anchors had all gone stale
                # reported "N of N caught". That is a false all-clear from
                # the tool whose whole purpose is to find false all-clears,
                # and it is exactly the shape it exists to catch (F84).
                skipped += 1
                print(f"  {label:52s} SKIPPED (anchor appears "
                      f"{original.count(find)} times)")
                continue
            _active = (path, original)
            path.write_text(original.replace(find, replace))
            try:
                result = subprocess.run(pytest_command, cwd=ROOT,
                                        capture_output=True, text=True,
                                        timeout=1800)
            finally:
                _restore()
            caught = result.returncode != 0
            detail = next((line.strip()[:44] for line in result.stdout.splitlines()
                           if line.startswith("FAILED")), "")
            print(f"  {label:52s} {'caught' if caught else '*** NOT CAUGHT ***'}"
                  f"  {detail}")
            missed += 0 if caught else 1
    finally:
        _restore()

    clean, dirty = _check(touched)
    if not clean:
        print(f"\nTHIS SWEEP LEFT A MUTATION BEHIND:\n{dirty}", file=sys.stderr)
        return 3

    touched_live = _live_state_changes(live_before, live_hashes_before)
    if touched_live:
        print("\nTHIS SWEEP CHANGED LIVE STATE. A mutation removes a safety, "
              "so a test run under it can reach things no test should touch:",
              file=sys.stderr)
        print("\n".join(touched_live), file=sys.stderr)
        return 4
    attempted = len(chosen) - skipped
    summary = (f"\n{attempted - missed} of {attempted} attempted caught; "
               f"the {len(touched)} file(s) it touched are clean")
    if skipped:
        summary += (f"\n{skipped} of {len(chosen)} SKIPPED: the anchor did "
                    "not appear exactly once, so nothing was tested. A stale "
                    "anchor is an unverified mutation, not a passing one")
    print(summary)
    return 1 if (missed or skipped) else 0


if __name__ == "__main__":
    raise SystemExit(main())
