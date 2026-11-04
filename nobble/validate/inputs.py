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


# Every queue a campaign holds, not the one that was in front of me. Tier 2
# writes `queue_tier2.jsonl` beside `queue.jsonl` and points it at the same
# YAML files, so a pair selected into the top decile is refined from
# whatever its tier-1 YAML says. Checking one queue would have cleared a
# campaign whose refinement queue was the stale half.
QUEUE_GLOB = "queue*.jsonl"


def queues(campaign: Path) -> list[Path]:
    return sorted(Path(campaign).glob(QUEUE_GLOB))


def stale_inputs(campaign: Path) -> list[dict]:
    """Jobs whose YAML disagrees with the queue row describing them.

    Every queue in the campaign, because a campaign has more than one and
    they share their YAML files.

    Reported whether the job has run or not. An unrun stale job is not
    harmless: running it produces a number for an input the code would not
    emit, which is the same defect arriving later.
    """
    campaign = Path(campaign)
    stale: list[dict] = []
    for queue in queues(campaign):
        stale.extend(_stale_in(campaign, queue))
    return stale


def _stale_in(campaign: Path, queue: Path) -> list[dict]:
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
                "queue_file": queue.name,
                "reason": "the YAML the queue row names is not on disk",
                "queue": _required(row), "yaml": None,
            })
            continue
        on_disk = yaml_modifications(path.read_text())
        wanted = _required(row)
        if sorted(on_disk) != sorted(wanted):
            stale.append({
                "job_id": row.get("job_id"), "pair_id": row.get("pair_id"),
                "queue_file": queue.name,
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
        lines.append(f"  {row.get('queue_file', 'queue.jsonl')} "
                     f"{row['job_id']}: yaml={row['yaml']} "
                     f"queue={row['queue']}")
    if len(stale) > REFUSAL_EXAMPLES:
        lines.append(f"  and {len(stale) - REFUSAL_EXAMPLES} more")
    for pair in pairs:
        lines.append(
            f"  correct it with: python tools/rerun_pair.py {pair} "
            "--campaign <campaign> --apply, then rerun tools/run_queue.sh")
    return "\n".join(lines)


# The chain the substrate occupies in every emitted YAML.
SUBSTRATE_CHAIN = "P"
CHAIN_BLOCK = re.compile(r"\n(?=- )")
CHAIN_ID = re.compile(r"id:\s*([A-Za-z])\b")
CHAIN_SEQUENCE = re.compile(r"sequence:\s*([A-Z]+)")


def substrate_sequence(yaml_text: str) -> str | None:
    """The sequence submitted as the substrate, by chain id rather than length.

    By id because the receptor is usually the longest chain, so taking the
    longest sequence reads the receptor for most pairs and the substrate for
    the rest. That mistake made five of seven pairs look as though no
    current domain matched them (F93).
    """
    for block in CHAIN_BLOCK.split(yaml_text):
        found = CHAIN_ID.search(block)
        if found and found.group(1) == SUBSTRATE_CHAIN:
            sequence = CHAIN_SEQUENCE.search(block)
            return sequence.group(1) if sequence else None
    return None


def superseded_substrates(campaign: Path) -> list[dict]:
    """Pairs whose submitted substrate is not what the plan now specifies.

    A campaign records which jobs it ran and, until F93, not which substrate
    domain each one used. The boundaries come from an InterPro lookup, so a
    fix to how an ambiguous entry is resolved moves them, and a campaign run
    before that fix holds a different input from the one the code would emit
    today.

    `stale_inputs` cannot see this. It compares a YAML against the queue row
    beside it, and both were written by the same assembly, so they agree
    about a boundary that has since moved. This compares the YAML against
    the plan instead.

    Reported rather than refused. A moved boundary does not make the
    campaign's number wrong, it makes it a measurement of something else,
    and which of the two is right is a question about the domain rather than
    about the code.
    """
    campaign = Path(campaign)
    try:
        from nobble.curate import numbering
        from nobble.curate import peptides as peptide_module

        wanted = []
        for plan in peptide_module.benchmark_substrate_constructs():
            substrate = plan["substrate"]
            if substrate.get("mode") != "folded_domain":
                continue
            sequence = numbering.canonical_sequence(substrate["accession"])[
                substrate["start"] - 1:substrate["end"]]
            if sequence:
                wanted.append((substrate, sequence))
        # The fragment arm submits the curated 15-mer, and a degron is a
        # slice of the domain it sits in, so every one of those is a
        # substring of some planned domain and would be reported as
        # superseded. They are not: they are the other arm of the
        # experiment.
        #
        # Identified by matching the curated sequences rather than by a
        # length threshold. The first version of this used `len < 30`,
        # which the cutoff sweep caught on its next run: a number in an
        # expression deciding what counts as a domain.
        fragments = {item.sequence for item
                     in peptide_module.benchmark_peptides() if item.sequence}
    except Exception:                                   # noqa: BLE001
        return []

    seen: dict[str, dict] = {}
    for path in sorted((campaign / "yaml").glob("*ternary*.yaml")):
        pair = path.name.split("__")[0]
        if pair in seen:
            continue
        submitted = substrate_sequence(path.read_text())
        if not submitted or submitted in fragments:
            continue        # the fragment arm, not a superseded domain
        match = next((s for s, seq in wanted if seq == submitted), None)
        if match is not None:
            continue
        overlap = next(((s, seq) for s, seq in wanted
                        if seq in submitted or submitted in seq), None)
        if overlap is None:
            continue        # no plan entry describes this chain at all
        substrate, sequence = overlap
        seen[pair] = {
            "pair_id": pair,
            "submitted_length": len(submitted),
            "planned_length": len(sequence),
            "accession": substrate["accession"],
            "planned_range": f"{substrate['start']}-{substrate['end']}",
            "reason": ("the submitted substrate is not the domain the plan "
                       "now specifies, so this pair measures a different "
                       "construct from the one the plan describes"),
        }
    return sorted(seen.values(), key=lambda row: row["pair_id"])
