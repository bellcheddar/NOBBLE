"""Does the input on disk still match the job that describes it?

A campaign holds two descriptions of every job: the queue row, which says
what the job is, and the YAML, which is what Boltz is actually given. They
are written by the same assembly and so normally agree. They stopped
agreeing once, and nothing noticed.

F47 fixed a modification rule that keyed on the E3 rather than on the
degron class, which had put a hydroxyproline on BRD4 Pro379. The rule was
fixed and the queue reassembled, so the queue row for
`bench02_BRD4_VHL` correctly says no modification is required. The fifteen
YAML files were already on disk and were not regenerated, so they still
carry `ccd: HYP`, and fifteen jobs ran on an input the current code would
not emit.

Nothing in the pipeline compared the two. The YAML is what Boltz reads and
the queue row is what everything downstream reads, so a disagreement
between them is invisible from either side: the results look like results
for the job the queue describes.

This is the comparison. It is cheap, because both are already on disk, and
it is general, because it asks whether the two agree rather than looking
for a hydroxyproline (F59).
"""
from __future__ import annotations

import json
import re
from pathlib import Path

# The YAML writer emits modifications as a block of position/ccd pairs under
# the chain they apply to. Read rather than parsed with a YAML library
# because this runs inside the atlas build, which must not acquire a
# dependency the droplet does not have.
MODIFICATION = re.compile(
    r"modifications:\s*\n(?:\s*- position:\s*\d+\s*\n\s*ccd:\s*(\w+)\s*\n?)+")
MODIFICATION_ENTRY = re.compile(r"-\s*position:\s*(\d+)\s*\n\s*ccd:\s*(\w+)")

# How many offending jobs the refusal lists before summarising the rest.
# A display limit, not a cutoff: every stale job refuses the publish
# whether or not it is printed, and the count is always stated.
REFUSAL_EXAMPLES = 5


def yaml_modifications(text: str) -> list[tuple[int, str]]:
    """Every (position, ccd) the YAML actually asks for."""
    found: list[tuple[int, str]] = []
    for block in MODIFICATION.finditer(text):
        for entry in MODIFICATION_ENTRY.finditer(block.group(0)):
            position, ccd = entry.groups()
            found.append((int(position), ccd))
    return found


def _required(row: dict) -> list[tuple[int, str]]:
    """What the queue row says the job needs, in the same shape."""
    value = row.get("required_modification")
    if not value:
        return []
    if isinstance(value, dict):
        position = value.get("position")
        ccd = value.get("ccd")
        return [(int(position), ccd)] if ccd and position is not None else []
    if isinstance(value, list):
        out = []
        for item in value:
            if isinstance(item, dict) and item.get("ccd") is not None:
                out.append((int(item.get("position", 0)), item["ccd"]))
        return out
    return []


def stale_inputs(campaign: Path) -> list[dict]:
    """Jobs whose YAML disagrees with the queue row describing them.

    Reported whether the job has run or not. An unrun stale job is not
    harmless: running it produces a number for an input the code would not
    emit, which is the same defect arriving later.
    """
    campaign = Path(campaign)
    queue = campaign / "queue.jsonl"
    if not queue.exists():
        return []
    stale: list[dict] = []
    for line in queue.read_text().splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        path = Path(row.get("yaml", ""))
        if not path.is_absolute():
            path = campaign / path
        if not path.exists():
            stale.append({
                "job_id": row.get("job_id"), "pair_id": row.get("pair_id"),
                "reason": "the YAML the queue row names is not on disk",
                "queue": _required(row), "yaml": None,
            })
            continue
        on_disk = yaml_modifications(path.read_text())
        wanted = _required(row)
        if sorted(on_disk) != sorted(wanted):
            stale.append({
                "job_id": row.get("job_id"), "pair_id": row.get("pair_id"),
                "reason": "the YAML and the queue row disagree about "
                          "which residues are modified",
                "queue": wanted, "yaml": on_disk,
            })
    return stale


def refusal(stale: list[dict]) -> str:
    """What to print, and what to do about it."""
    pairs = sorted({row["pair_id"] for row in stale if row.get("pair_id")})
    lines = [
        f"REFUSING TO PUBLISH: {len(stale)} job(s) across {len(pairs)} pair(s) "
        "ran on an input the current code would not emit.",
    ]
    for row in stale[:REFUSAL_EXAMPLES]:
        lines.append(f"  {row['job_id']}: yaml={row['yaml']} "
                     f"queue={row['queue']}")
    if len(stale) > REFUSAL_EXAMPLES:
        lines.append(f"  and {len(stale) - REFUSAL_EXAMPLES} more")
    for pair in pairs:
        lines.append(
            f"  correct it with: python tools/rerun_pair.py {pair} "
            "--campaign <campaign> --apply, then rerun tools/run_queue.sh")
    return "\n".join(lines)
