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


def relocate_queue_paths(campaign: Path) -> dict:
    """Point a copied campaign's queues at the copy's own YAML files (F339).

    A queue row names its YAML by absolute path, so copying a campaign
    directory does not copy that reference: the copy's queue still names the
    original's files. A copy is therefore isolated for anything writing to
    paths it derives from the copy's root, and not isolated at all for
    anything following a queue row.

    I found that out by writing into the live Tier B campaign from a script
    whose whole purpose was to tamper with a throwaway copy. The guard said
    `if not y.is_absolute(): y = copy / y`, and the paths were absolute.

    So this makes the copy mean what it looks like. A row whose YAML lives
    under this campaign already is left alone; one pointing elsewhere is
    repointed at the file of the same name under this campaign's `yaml/`;
    one with no such file is counted in `missing` rather than rewritten to a
    path that is not there.

    Returns counts rather than nothing, because "every row already pointed
    inside" and "there were no rows" are the same silence otherwise.
    """
    campaign = Path(campaign).resolve()
    yaml_dir = campaign / "yaml"
    moved = inside = missing = rows = 0
    for queue in queues(campaign):
        out = []
        changed = False
        for line in queue.read_text().splitlines():
            if not line.strip():
                continue
            rows += 1
            row = json.loads(line)
            named = str(row.get("yaml") or "")
            if not named:
                out.append(line)
                continue
            path = Path(named)
            if path.is_absolute() and campaign in path.parents:
                inside += 1
                out.append(line)
                continue
            if not path.is_absolute():
                inside += 1
                out.append(line)
                continue
            candidate = yaml_dir / path.name
            if not candidate.is_file():
                missing += 1
                out.append(line)
                continue
            row["yaml"] = str(candidate)
            moved += 1
            changed = True
            out.append(json.dumps(row))
        if changed:
            queue.write_text("\n".join(out) + "\n")
    return {"rows": rows, "relocated": moved, "already_inside": inside,
            "missing_in_the_copy": missing,
            "queues": len(queues(campaign))}


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
        # is_file, not exists. A row with no `yaml` field gives Path(""),
        # and `campaign / ""` is the campaign directory, which exists: the
        # row sailed past this branch and crashed on read_text() with
        # IsADirectoryError, from inside the atlas build, which is the
        # unattended publish step. The branch below is what should have
        # caught it. The current selector copies the whole job dict so it
        # always writes `yaml`, and this is unreachable from it; a row from
        # an older build or a torn write is what it guards (F208).
        if not path.is_file():
            # Two cases, and they are not the same fault. A row naming a
            # file that is missing is a campaign whose inputs were moved or
            # deleted; a row naming nothing cannot be checked at all, and
            # saying its YAML "is not on disk" describes a file it never
            # claimed to have.
            stale.append({
                "job_id": row.get("job_id"), "pair_id": row.get("pair_id"),
                "queue_file": queue.name,
                "reason": ("the queue row names no YAML, so the input it "
                           "was run on cannot be checked")
                          if not row.get("yaml") else
                          "the YAML the queue row names is not on disk",
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
    return _superseded_scan(campaign)[0]


def superseded_status(campaign: Path) -> str:
    """Whether the comparison above could be made at all.

    "compared" or "unavailable: <reason>". The plan comes from an InterPro
    lookup and a swallowed failure used to return an empty list, which
    `tools/provenance.py` printed as "no substrate differs from the current
    plan": a positive claim about every pair, made from an exception. Same
    shape as F222 and as the featurisation guard's silent skips, so the same
    treatment, and the same one-pass idiom.
    """
    return _superseded_scan(campaign)[1]


def _superseded_scan(campaign: Path) -> tuple[list[dict], str]:
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
    except Exception as problem:                        # noqa: BLE001
        # Unknown, not clean. The plan is an InterPro lookup and this is the
        # only place that resolves it, so a failure here means no pair was
        # compared against anything.
        return [], f"unavailable: {type(problem).__name__}: {problem}"

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
    return sorted(seen.values(), key=lambda row: row["pair_id"]), "compared"


def _regenerated_scan(campaign: Path) -> tuple[list[dict], str]:
    """Jobs whose YAML on disk is not what the current code would write.

    The provenance chain for an input has three links and only two were
    checked. `stale_inputs` compares a YAML against the job record that
    describes it, and `tools/stale_featurisation.py` compares the cached
    featurisation against the YAML (F219). Nothing compared the YAML against
    the code that emits it, which is the link F262 broke: the ligand
    resolution dropped a SMILES-only glue, so the YAML was wrong from the
    moment it was written and agreed with its own record and its own cache
    the whole way down.

    Costs about two seconds for a 2,360-job campaign, almost all of it the
    manifest build, because `regenerate_pair` writes nothing and the
    documents are plain dicts.

    `([], "unavailable: ...")` when the comparison cannot be made, never
    `([], "clean")`: a failed manifest build means no job was compared
    against anything, which is F216's mistake in whichever file repeats it.
    """
    campaign = Path(campaign)
    queue = campaign / "queue.jsonl"
    if not queue.exists():
        return [], f"unavailable: no queue.jsonl in {campaign.name}"
    # Only the campaign assembler's own output. `regenerate_all` reproduces
    # `assemble_campaign`, and a Tier B, design or corrected campaign comes
    # from a different builder, so comparing one against this manifest
    # reports every pair it has as work the code would not emit: a confident
    # answer to a question nobody asked. The benchmark campaign's job ids
    # happen to coincide with the main manifest's and so compared clean,
    # which is luck rather than design and not a basis for a check.
    #
    # `not_applicable`, not `unavailable`, and the difference decides whether
    # the publish gate refuses. "The comparison failed" is an unknown and
    # must refuse; "there is no comparison to make" is neither a pass nor a
    # failure. Reported as `unavailable` it refused a legitimate build from
    # the benchmark campaign, which `test_redaction_count` caught at once.
    # Which assembler produced this campaign decides which regenerator can
    # answer for it. Tier B was `not_applicable` until F340, which left the
    # one arm whose own comment warns that it "depends on the form and the
    # library and both can change between runs" as the one arm this skipped:
    # 1,540 jobs and about 33 hours with this link unverified. The renderer
    # is now shared with `assemble_tier_b` rather than copied, so the two
    # cannot drift, and regenerating the arm on disk reproduced all 1,540
    # YAMLs byte for byte.
    regenerators = {"campaign_": "regenerate_all",
                    "tier_b_": "regenerate_tier_b",
                    "design_": "regenerate_design"}
    chosen = next((name for prefix, name in regenerators.items()
                   if campaign.name.startswith(prefix)), None)
    if chosen is None:
        return [], (f"not_applicable: {campaign.name} comes from none of the "
                    f"three assemblers this compares against "
                    f"({', '.join(sorted(regenerators))})")
    # Initialised outside the try, because they are read after it: a failure
    # part way through the scan would otherwise raise NameError here, which
    # is a worse report than the one the handler is there to give.
    out: list[dict] = []
    compared = 0
    try:
        from nobble import paths
        from nobble.execute import campaign as assembler

        rows = paths.read_jsonl(queue, tolerate_torn=True)
        # One manifest for the whole campaign. Asking per pair rebuilt it 158
        # times and turned a two-second scan into twenty-three.
        if chosen == "regenerate_design":
            # The design regenerator needs the parent and the generator,
            # which are not derivable from the queue: the scan's parent is
            # chosen by measured Delta-ipTM at assembly time and the
            # campaign records it. Regenerating against today's ranked
            # choice instead would answer a different question, which is
            # F338's and is asked by `tools/run_design.sh`.
            from nobble.design import assemble as design_assembler

            meta_path = campaign / "campaign.json"
            if not meta_path.exists():
                return [], (f"unavailable: no campaign.json in "
                            f"{campaign.name}, so the parent to regenerate "
                            "this scan from is unknown")
            meta = json.loads(meta_path.read_text())
            parent = meta.get("parent")
            if not parent:
                return [], (f"unavailable: {campaign.name} records no "
                            "parent, so there is nothing to regenerate from")
            fresh = design_assembler.regenerate_design(
                parent, meta.get("generator") or "alanine_scan")
        else:
            fresh = getattr(assembler, chosen)()
        for row in rows:
            job_id = row.get("job_id")
            path = Path(row.get("yaml") or "")
            text = fresh.get(job_id)
            if text is None:
                # A job the current manifest no longer emits. Reported rather
                # than skipped: the campaign holds work the code would not
                # produce today, which is the same class of disagreement one
                # step larger.
                out.append({"pair_id": row.get("pair_id"), "job_id": job_id,
                            "problem": "the current manifest emits no such "
                                       "job"})
                continue
            if not path.exists():
                continue
            compared += 1
            if path.read_text() != text:
                out.append({"pair_id": row.get("pair_id"), "job_id": job_id,
                            "problem": "the YAML on disk is not what the "
                                       "current code emits"})
    except Exception as problem:                        # noqa: BLE001
        return [], f"unavailable: {type(problem).__name__}: {problem}"
    if not compared:
        return out, "unavailable: no job could be compared"
    if out:
        return out, (f"{len(out)} job(s) of {compared} compared hold a YAML "
                     "the current code would not write")
    return [], f"clean: all {compared} YAML(s) match what the code emits"


def regenerated_status(campaign: Path) -> str:
    """One line for the status page, distinguishing clean from unknown.

    No `regenerated_disagreements` beside it, unlike `superseded_substrates`
    and `superseded_status`. I wrote one in F266 and nothing called it: the
    only consumer of the rows is `deploy/build_atlas.py`, which needs the
    rows and the status from one pass and so calls `_regenerated_scan`
    directly rather than scanning twice at two seconds each. A public
    accessor kept for symmetry with a sibling is the unused affordance
    `tests/test_unused_affordances.py` exists to find, so it is gone (F291).
    """
    return _regenerated_scan(campaign)[1]
