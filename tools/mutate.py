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

Usage:
    python tools/mutate.py                 # every mutation in MUTATIONS
    python tools/mutate.py --only msa      # those whose label matches
    python tools/mutate.py --list
"""
from __future__ import annotations

import argparse
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


def _check(paths: set[str] | None = None) -> tuple[bool, str]:
    """Whether the files this tool may have written are clean.

    Scoped to `paths` on the way out rather than looking at the whole tree.
    The first version compared everything, so an unrelated edit made
    somewhere else during the sweep, a PROGRESS.md note in the case that
    found this, was reported as "the sweep left a mutation behind". A
    false alarm about the thing the check exists to catch is worse than no
    check: it trains you to ignore it.

    On the way in the check is deliberately unscoped, because a leftover
    from a previous run could be in any file and should stop this one.
    """
    dirty = _dirty_files()
    if paths is not None:
        dirty &= paths
    return (not dirty), "\n".join(sorted(dirty))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--only", default=None,
                        help="run only mutations whose label contains this")
    parser.add_argument("--list", action="store_true")
    args = parser.parse_args(argv)

    chosen = [m for m in MUTATIONS
              if args.only is None or args.only.lower() in m[1].lower()]
    if args.list:
        for path, label, _f, _r in chosen:
            print(f"  {path:32s} {label}")
        return 0
    if not chosen:
        print("no mutation matched", file=sys.stderr)
        return 2

    clean, dirty = _check()
    if not clean:
        print("refusing to start: the working tree has uncommitted changes to "
              "tracked files, and this tool restores by rewriting them.\n"
              f"{dirty}", file=sys.stderr)
        return 2

    signal.signal(signal.SIGINT, _on_signal)
    signal.signal(signal.SIGTERM, _on_signal)

    global _active
    missed = 0
    touched = {relative for relative, _l, _f, _r in chosen}
    try:
        for relative, label, find, replace in chosen:
            path = ROOT / relative
            original = path.read_text()
            if original.count(find) != 1:
                print(f"  {label:52s} SKIPPED (anchor appears "
                      f"{original.count(find)} times)")
                continue
            _active = (path, original)
            path.write_text(original.replace(find, replace))
            try:
                result = subprocess.run(PYTEST, cwd=ROOT, capture_output=True,
                                        text=True, timeout=1800)
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
    print(f"\n{len(chosen) - missed} of {len(chosen)} caught; "
          f"the {len(touched)} file(s) it touched are clean")
    return 1 if missed else 0


if __name__ == "__main__":
    raise SystemExit(main())
