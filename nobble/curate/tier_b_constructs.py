"""Receptor constructs for the Tier B ligases, from config (F163).

Spec 1.1 names a construct for each Tier A ligase, because which domain of a
ligase binds its substrate is science knowledge and not a lookup. Spec 3.3
selects fifteen Tier B ligases and names no construct for any of them, so
Tier B is selected, frozen, gate-passed and unrunnable: every pair needs a
receptor that does not exist.

This module is the mechanism for closing that, and deliberately not the
judgement. `config/tier_b_constructs.toml` is the form; it ships empty with
the candidate domains listed, and until it has entries `missing()` names
every ligase still without one. The two mechanical ways to fill it in are
both ruled out by decisions already taken, the longest annotated domain by
F41 and the frozen `best_window` because it states which part of the model is
confident rather than which part binds substrate.

A filled-in entry is validated rather than trusted: the accession has to
carry the entry, the entry has to be unambiguous or say which occurrence it
means, and the construct has to fit the tier-1 token cap unless it declares
itself an exception, which is what spec 1.1 does for VHL and DCAF15.
"""
from __future__ import annotations

import tomllib
from pathlib import Path

from nobble import paths
from nobble.curate.constructs import Construct, Segment

FORM = paths.ROOT / "config" / "tier_b_constructs.toml"

# What a receptor segment has to fit inside, for a construct that does not
# declare itself an exception: the tier-1 cap less a 15-mer peptide and a
# glue at the recall set's median heavy-atom count. From config, because the
# cutoff sweep is right that a number deciding an acceptance is a threshold
# and not an incidental literal.
PEPTIDE_RESIDUES = int(paths.thresholds()["tier_b"]["construct_peptide_residues"])
GLUE_HEAVY_ATOMS = int(paths.thresholds()["tier_b"]["construct_glue_heavy_atoms"])


def _tier_b_genes() -> list[str]:
    """The frozen selection's genes, which is what needs covering."""
    try:
        import duckdb

        rows = duckdb.sql(
            f"select gene from '{paths.TIER_B_SELECTION}'").fetchall()
    except Exception:                                   # noqa: BLE001
        return []
    return sorted(str(row[0]) for row in rows if row[0])


def load() -> dict[str, Construct]:
    """Every construct the form defines, as `Construct` objects."""
    if not FORM.exists():
        return {}
    document = tomllib.loads(FORM.read_text())
    out: dict[str, Construct] = {}
    for name, entry in (document.get("constructs") or {}).items():
        segments = tuple(
            Segment(
                accession=str(item["accession"]),
                label=str(item.get("label") or name),
                interpro_entry=item.get("interpro_entry"),
                note=str(item.get("note") or ""),
                interpro_occurrence=item.get("occurrence"),
            )
            for item in (entry.get("segments") or [])
        )
        out[name] = Construct(
            name=name,
            e3_gene=str(entry.get("e3_gene") or ""),
            segments=segments,
            exception=bool(entry.get("exception")),
            rationale=str(entry.get("rationale") or ""),
        )
    return out


def exclusions() -> dict[str, str]:
    """Tier B genes deliberately left without a construct, and why.

    The form was built assuming all fifteen would get one. Four cannot.
    KCNC1 and KCND2 are voltage-gated potassium channels that passed spec
    3.3's filters on pocket druggability and model confidence rather than on
    having a substrate interface, and their only ordered non-BTB domain
    transports potassium. RAG1 is a recombinase whose every ordered domain
    binds DNA or catalyses, and whose ligase activity is on histones. RNF175
    annotates nothing but its RING and its membrane span.

    Recorded rather than left missing, because "no construct was named" and
    "no construct can be named, for this reason" are different states and
    only the second is an answer. A reason is required: without one this
    would be a way to make the gate pass by deleting the genes that fail it.
    """
    if not FORM.exists():
        return {}
    document = tomllib.loads(FORM.read_text())
    return {str(gene): str(entry.get("reason") or "")
            for gene, entry in (document.get("exclusions") or {}).items()}


def missing() -> list[str]:
    """Tier B genes with neither a construct nor a reasoned exclusion."""
    covered = {construct.e3_gene for construct in load().values()}
    excluded = {gene for gene, reason in exclusions().items() if reason}
    return [gene for gene in _tier_b_genes()
            if gene not in covered and gene not in excluded]


def problems() -> list[dict]:
    """What is wrong with the constructs the form does define.

    Checked rather than trusted, because an entry here decides what gets
    submitted to Boltz for fifteen receptors nobody has modelled before.
    """
    cap = int(paths.thresholds()["manifest"]["token_cap_tier1"])
    found: list[dict] = []
    for name, construct in sorted(load().items()):
        if not construct.e3_gene:
            found.append({"construct": name, "problem": "no e3_gene"})
        if not construct.segments:
            found.append({"construct": name, "problem": "no segments"})
            continue
        if not construct.rationale:
            found.append({
                "construct": name,
                "problem": "no rationale: which domain binds the substrate is "
                           "the one thing this file exists to record",
            })
        try:
            residues = construct.residue_count()
        except Exception as problem:                    # noqa: BLE001
            found.append({
                "construct": name,
                "problem": f"{type(problem).__name__}: {problem}",
            })
            continue
        tokens = residues + PEPTIDE_RESIDUES + GLUE_HEAVY_ATOMS
        if tokens > cap and not construct.exception:
            found.append({
                "construct": name,
                "problem": f"{tokens} tokens against a cap of {cap} and no "
                           "declared exception",
                "residues": residues,
            })
    return found


def report() -> dict:
    """Whether Tier B can be assembled, and what is stopping it."""
    defined = load()
    absent = missing()
    wrong = problems()
    excluded = exclusions()
    unreasoned = sorted(gene for gene, reason in excluded.items() if not reason)
    floor = int(paths.thresholds()["tier_b"]["min_ligases_for_gate"])
    if unreasoned:
        wrong = wrong + [{"exclusion": gene, "problem": "excluded with no reason"}
                         for gene in unreasoned]
    # Spec 3.3's floor, checked here rather than left implicit: excluding
    # genes shrinks the arm, and an arm below the floor answers a narrower
    # question than the one the gate was written for.
    #
    # Capped at the size of the selection being judged. A bare `< floor`
    # demanded ten ligases from a one-gene fixture, which broke
    # test_a_filled_form_reports_ready: the floor is a statement about the
    # real selection of fifteen, and asking it of a selection of one is a
    # category error rather than a strict check.
    required = min(floor, len(_tier_b_genes()) or floor)
    if defined and len(defined) < required:
        wrong = wrong + [{
            "problem": f"{len(defined)} construct(s) against spec 3.3's "
                       f"floor of {floor} ligases",
        }]
    return {
        "tier_b_genes": len(_tier_b_genes()),
        "constructs_defined": len(defined),
        "genes_without_a_construct": absent,
        "excluded": excluded,
        "ligase_floor": floor,
        "problems": wrong,
        "assemblable": not absent and not wrong and bool(defined),
        # Project-relative where it can be, absolute otherwise.
        # `relative_to` raises for a path outside the root, which a test
        # pointing at a temporary form is, and a report that raises while
        # describing a blocked state is worse than the blocked state.
        "form": str(FORM.relative_to(paths.ROOT))
                 if FORM.is_relative_to(paths.ROOT) else str(FORM),
        "status": (
            "ready" if (not absent and not wrong and defined)
            else f"blocked: {len(absent)} gene(s) without a construct, "
                 f"{len(wrong)} problem(s) in the {len(defined)} defined"
        ),
    }
