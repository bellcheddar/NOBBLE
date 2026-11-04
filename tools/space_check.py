#!/usr/bin/env python3
"""Will the bundle about to be shipped fit on the droplet (F175)?

`deploy.sh` rsyncs `deploy/atlas` with `--delete` and has never asked how
much room is on the far side. On the benchmark atlas that was 25 MB and the
question did not arise. The running campaign projects to 265 MB of
structures, and rsync running out of space part way through leaves a
half-written atlas behind a live site: pages that resolve, structures that
404, and a catalogue that lists poses the viewer cannot open.

The arithmetic is here rather than in the shell for the usual reason, that a
number deciding an acceptance should be testable, and because the one thing
this cannot do is try itself out: the check is only exercised against a real
droplet by a real deploy.

Two points worth stating about the sum. It compares the whole incoming
bundle against free space, not the difference from what is already there,
because `--delete` removes the old files after the transfer rather than
before, so the peak is the old copy plus the new one. And the margin is
what must remain free afterwards, not a fudge factor: the same deploy pip
installs into a venv and the service writes logs, and a deploy should not be
the thing that fills the disk.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from nobble import paths  # noqa: E402


def bundle_kilobytes(bundle: Path) -> int:
    """Apparent size of everything under `bundle`, in kibibytes.

    Apparent size rather than blocks on disk: what matters is how much the
    far side has to store, and the two filesystems need not agree about
    block size. Rounded up per file, because each one occupies at least a
    block wherever it lands.
    """
    total = 0
    for path in bundle.rglob("*"):
        if path.is_file() and not path.is_symlink():
            total += -(-path.stat().st_size // 1024) or 1
    return total


def judge(free_kb: int, bundle_kb: int, margin_mb: int) -> dict:
    margin_kb = margin_mb * 1024
    remaining_kb = free_kb - bundle_kb
    return {
        "free_mb": round(free_kb / 1024, 1),
        "bundle_mb": round(bundle_kb / 1024, 1),
        "margin_mb": margin_mb,
        "remaining_after_mb": round(remaining_kb / 1024, 1),
        "fits": remaining_kb >= margin_kb,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--free-kb", type=int, required=True,
                        help="free kibibytes on the droplet, from df -Pk")
    parser.add_argument("--bundle", type=Path, default=paths.ROOT / "deploy" / "atlas")
    parser.add_argument("--margin-mb", type=int, default=None,
                        help="override the configured margin; for testing")
    args = parser.parse_args(argv)

    if not args.bundle.is_dir():
        print(f"space_check: no bundle at {args.bundle}", file=sys.stderr)
        return 2

    margin = args.margin_mb
    if margin is None:
        margin = int(paths.thresholds()["deploy"]["droplet_free_margin_mb"])

    verdict = judge(args.free_kb, bundle_kilobytes(args.bundle), margin)
    print(f"    bundle {verdict['bundle_mb']} MB, free {verdict['free_mb']} MB, "
          f"{verdict['remaining_after_mb']} MB would remain "
          f"(margin {verdict['margin_mb']} MB)")
    if not verdict["fits"]:
        print("deploy: not enough room on the droplet. Sending this bundle would",
              file=sys.stderr)
        print(f"        leave {verdict['remaining_after_mb']} MB free against a "
              f"{verdict['margin_mb']} MB margin, and rsync running out of space",
              file=sys.stderr)
        print("        part way through leaves a half-written atlas behind a live",
              file=sys.stderr)
        print("        site. Prune the droplet or reduce the bundle first.",
              file=sys.stderr)
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
