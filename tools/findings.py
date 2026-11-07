#!/usr/bin/env python3
"""Look up a finding, list them, or check the file's numbering.

FINDINGS.md is 14,000 lines and 291 findings, and the rest of the project
cites them constantly: a code comment says F219 and expects the reader to
find it. Until now that meant grepping, and on 7 November I re-ran a sweep
whose finding was four hours old because I did not think to look (F291).

Nothing is written. The index is computed from the file on every call, so it
cannot go stale, which is the whole reason it is a tool rather than a section
at the top of the document.

    python tools/findings.py 262          one finding, in full
    python tools/findings.py --list       every finding, one line each
    python tools/findings.py --grep ROC   findings whose body matches
    python tools/findings.py --check      numbering integrity
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FINDINGS = ROOT / "FINDINGS.md"

# `## F255`, `## F82. The four-chain case`, `### F261, continued: ...`, and
# `### F6a.` which is a lettered sub-finding. The letter is kept out of the
# number so F6a indexes under 6 and says so.
HEADING = re.compile(r"^(#{2,3})\s*F(\d+)([a-z]?)[.,:]?\s*(.*)$")


def entries() -> list[dict]:
    """Every finding heading, with its line number and body span."""
    lines = FINDINGS.read_text().splitlines()
    found = []
    for number, line in enumerate(lines, start=1):
        match = HEADING.match(line)
        if match:
            found.append({
                "level": len(match.group(1)),
                "number": int(match.group(2)),
                "letter": match.group(3),
                "title": match.group(4).strip(),
                "line": number,
            })
    for index, entry in enumerate(found):
        entry["ends"] = (found[index + 1]["line"] - 1 if index + 1 < len(found)
                         else len(lines))
    return found


def body(entry: dict) -> str:
    lines = FINDINGS.read_text().splitlines()
    return "\n".join(lines[entry["line"] - 1:entry["ends"]]).rstrip()


def _label(entry: dict) -> str:
    return f"F{entry['number']}{entry['letter']}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("number", nargs="?", help="a finding number, e.g. 262")
    parser.add_argument("--list", action="store_true")
    parser.add_argument("--grep", metavar="PATTERN")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)

    found = entries()
    if not found:
        print("no findings parsed: the heading pattern has stopped matching",
              file=sys.stderr)
        return 2

    if args.check:
        # Keyed by the full label, not the number. F2b and F4a are lettered
        # sub-findings at the same heading level as F2 and F4, so grouping by
        # number alone reported both pairs as repeats on this tool's first
        # run. The file was right and the check was wrong (F292).
        numbers = [entry["number"] for entry in found if entry["level"] == 2]
        labels = [_label(entry) for entry in found if entry["level"] == 2]
        seen: dict[str, int] = {}
        for label in labels:
            seen[label] = seen.get(label, 0) + 1
        # A repeat is not automatically wrong: F82 keeps its superseded text
        # under "## F82 (original text)", which is the project preferring a
        # correction on the record to a tidy file.
        repeats = {label: count for label, count in seen.items() if count > 1}
        annotated = {_label(entry) for entry in found
                     if entry["level"] == 2 and "original text" in entry["title"]}
        print(f"{len(found)} heading(s), {len(set(labels))} distinct label(s) "
              f"over {len(set(numbers))} number(s)")
        for label, count in sorted(repeats.items()):
            note = (" (one is marked as superseded text, which is deliberate)"
                    if label in annotated else "  <- unexplained repeat")
            print(f"  {label}: {count} headings{note}")
        missing = sorted(set(range(1, max(numbers) + 1)) - set(numbers))
        print(f"highest F{max(numbers)}; {len(missing)} number(s) with no "
              f"heading{': ' + str(missing[:12]) if missing else ''}")
        unexplained = [label for label in repeats if label not in annotated]
        return 1 if (missing or unexplained) else 0

    if args.list:
        for entry in found:
            mark = "  " if entry["level"] == 2 else "    "
            print(f"{mark}{_label(entry):>6}  line {entry['line']:>5}  "
                  f"{entry['title'][:88]}")
        return 0

    if args.grep:
        pattern = re.compile(args.grep, re.I)
        hits = [entry for entry in found if pattern.search(body(entry))]
        for entry in hits:
            print(f"  {_label(entry):>6}  line {entry['line']:>5}  "
                  f"{entry['title'][:88]}")
        print(f"\n{len(hits)} of {len(found)} finding(s) match {args.grep!r}")
        return 0 if hits else 1

    if args.number is None:
        parser.print_help()
        return 2
    wanted = args.number.lstrip("Ff")
    matches = [entry for entry in found
               if f"{entry['number']}{entry['letter']}" == wanted
               or str(entry["number"]) == wanted]
    if not matches:
        print(f"no finding F{wanted}", file=sys.stderr)
        return 1
    for entry in matches:
        print(body(entry))
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
