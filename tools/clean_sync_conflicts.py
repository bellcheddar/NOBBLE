"""Remove iCloud sync-conflict copies, and refuse on any that is not a copy.

The project root is iCloud-backed. When iCloud holds a copy of a file that a
rebuild or a re-run has just replaced, it restores that copy beside the new
one under a " 2" suffix, with the earlier timestamp (F173, F186). Nothing
references them. `deploy/deploy.sh` refuses to ship them and
`tests/test_no_sync_conflict_files.py` names the class, and neither runs
between a rebuild and the next `git add -A`: the 2026-11-07 rebuild left
2,014 and 706 were committed and pushed hours later (F303, F304).

So this runs in `tools/refresh.sh`, straight after the build, and it removes
rather than refuses. Two reasons it is a removal and not a gate:

  * The project already concluded that it should be. The class's own test
    says "Cheap, because the answer is always the same: delete it."
  * They reappear whenever an output directory is rewritten, which during a
    forty-hour run is constantly. A gate there stops the run; a gate that
    fires repeatedly on a known-harmless artefact is a gate that gets
    disabled.

**What it will not remove.** A conflict-shaped name with no plain sibling is
not demonstrably a copy of anything, so it is reported and the command exits
non-zero. Deleting the only copy of a file to tidy up a name is the one
outcome worse than leaving the name alone.

The content is not compared. iCloud restores an *older* copy, so a conflict
file routinely differs from its sibling, and that is the normal case rather
than a reason to keep it: the sibling is what the build or the runner just
wrote and the conflict file is what was there before. Comparing bytes and
keeping the differing ones would keep exactly the stale ones (F300: a
conflict copy of a featurisation made the staleness guard read the old
input and refuse an atlas build for hours).
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# A space, digits, then the extension. The same pattern
# `tests/test_no_sync_conflict_files.py` and `deploy/deploy.sh` use,
# deliberately: one spelling of what a conflict copy looks like. An ordinary
# name ending in a number has no space before it, and `_v2` has no space
# either.
# One or more extension segments, so a gzipped crystal is caught too.
# `5FQD 2.cif.gz` does not match a pattern that wants " <digits>." directly
# before the final extension, and seven of them sat in the published bundle
# until a hand-written cleanup removed them: the project's guard had never
# been able to see a compound extension (F310).
CONFLICT = re.compile(r" \d+(\.[A-Za-z0-9]+)+$")

# Where to look. Not the whole root: `.git` holds packed objects whose names
# this pattern could in principle match, and no sync artefact in there is
# this tool's business.
SCANNED = ("deploy", "campaigns", "nobble", "tools", "tests", "data")


def plain_sibling(path: Path) -> Path | None:
    """The file this one is a conflict copy of, if it is there.

    `x 2.cif` -> `x.cif`. Replacing only the matched tail, so a name with a
    space elsewhere is not mangled.
    """
    match = CONFLICT.search(path.name)
    if not match:
        return None
    # The whole extension, however many segments: ` 2.cif.gz` -> `.cif.gz`.
    extension = match.group(0).split(".", 1)[1]
    base = path.name[: match.start()] + "." + extension
    candidate = path.with_name(base)
    return candidate if candidate.exists() else None


def find(root: Path | None = None) -> tuple[list[Path], list[Path]]:
    """(removable, unmatched): conflict copies with and without a sibling."""
    root = root or ROOT
    removable, unmatched = [], []
    for name in SCANNED:
        directory = root / name
        if not directory.is_dir():
            continue
        for path in directory.rglob("*"):
            if not path.is_file() or not CONFLICT.search(path.name):
                continue
            (removable if plain_sibling(path) else unmatched).append(path)
    return sorted(removable), sorted(unmatched)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=None)
    parser.add_argument("--dry-run", action="store_true",
                        help="list what would go and remove nothing")
    args = parser.parse_args(argv)

    root = args.root or ROOT
    removable, unmatched = find(root)

    if removable:
        verb = "would remove" if args.dry_run else "removed"
        for path in removable:
            if not args.dry_run:
                path.unlink()
        print(f"sync conflicts: {verb} {len(removable)} copy(ies), each "
              f"beside the file it is a copy of; first "
              f"{removable[0].relative_to(root)}")
    else:
        print("sync conflicts: none")

    if unmatched:
        print(f"REFUSING: {len(unmatched)} conflict-shaped name(s) have no "
              "plain sibling, so they are not demonstrably a copy of "
              "anything and are left alone. Look at them:", file=sys.stderr)
        for path in unmatched:
            print(f"  {path.relative_to(root)}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
