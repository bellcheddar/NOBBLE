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


def missing() -> list[str]:
    """Tier B genes with no construct, which is what blocks the arm."""
    covered = {construct.e3_gene for construct in load().values()}
    return [gene for gene in _tier_b_genes() if gene not in covered]


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
    return {
        "tier_b_genes": len(_tier_b_genes()),
        "constructs_defined": len(defined),
        "genes_without_a_construct": absent,
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
