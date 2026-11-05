#!/usr/bin/env python3
"""Per-candidate evidence for the fifteen Tier B construct choices (F182).

`config/tier_b_constructs.toml` is a form, and D-NOB-068 is explicit about
why: which domain of a ligase binds its substrate is science knowledge, the
two mechanical routes are both ruled out, and no amount of code closes the
gap. What code can do is make answering cheap.

The form already lists each ligase's InterPro candidates with their ranges
and lengths. That is enough to see which domains fit the tier-1 token cap
and not enough to choose between them, because it says nothing about whether
a candidate is folded. A 224-residue annotation over a stretch the model
places at pLDDT 48 is a poor receptor construct whatever the annotation
says, and ruling it out is a modelling fact rather than a biology claim, so
it is a thing this may legitimately report.

So this adds two measured columns per candidate:

  pLDDT   the mean over the candidate's own range, from the cached AlphaFold
          model, by the same reader the Tier B selection used
  window  how much of the candidate falls inside the frozen selection's
          best_window, the highest-mean-pLDDT 200-residue window

What it deliberately does not do is rank, score or recommend. F41 settled
that in `domain_by_accession`'s docstring and D-NOB-068 restates it: picking
the longest domain, or the most confident one, is the mechanical route that
was rejected. The columns are evidence beside each option, in the order the
form already lists them, and the choice stays with the reader.

    PYTHONPATH=. python tools/tier_b_candidates.py
    PYTHONPATH=. python tools/tier_b_candidates.py --gene CCNF
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from nobble import paths                                      # noqa: E402
from nobble.curate import interpro, plddt                     # noqa: E402
from nobble.curate import tier_b_constructs as form           # noqa: E402

UNREADABLE = "n/a"


def cap() -> int:
    """The residue budget a non-exception segment has, from config.

    Read the same way `form.problems()` reads it rather than recomputed, so
    the listing and the validator cannot disagree about what fits.
    """
    token_cap = int(paths.thresholds()["manifest"]["token_cap_tier1"])
    return token_cap - form.PEPTIDE_RESIDUES - form.GLUE_HEAVY_ATOMS


def floor() -> int:
    """Shortest annotation worth listing, from config.

    Was a bare 60 in the comparison below. The form's header states the same
    number in prose, so there were two copies and the tool's was the one a
    reader would not find: exactly the inconsistency F181 recorded, in a tool
    written an hour after it (F183).
    """
    return int(paths.thresholds()["tier_b"]["construct_min_residues"])


def selection() -> list[dict]:
    """The frozen Tier B rows: gene, accession and the best window."""
    import duckdb

    rows = duckdb.sql(
        "select gene, uniprot_acc, mean_plddt, best_window_mean_plddt, "
        f"best_window from '{paths.TIER_B_SELECTION}' order by gene"
    ).fetchall()
    out = []
    for gene, accession, mean, window_mean, window in rows:
        out.append({
            "gene": str(gene),
            "accession": str(accession),
            "mean_plddt": None if mean is None else float(mean),
            "best_window_mean_plddt": None if window_mean is None else float(window_mean),
            "best_window": _window(window),
        })
    return out


def _window(value) -> list[int] | None:
    """The frozen best_window as two integers.

    The parquet column is text, `"[302, 501]"`, not a list. `list(value)` on
    it yields ten single characters, which is what the first run of this
    tool printed into the window column: every row read `n/a` because an
    overlap against `['[', '3', '0', ...]` is not computable. A string that
    iterates without complaining is the same shape as F130's NaN passing a
    truthiness test.
    """
    if value is None:
        return None
    if isinstance(value, (list, tuple)):
        pair = list(value)
    else:
        import re

        pair = [int(n) for n in re.findall(r"-?\d+", str(value))]
    if len(pair) != 2:
        return None
    try:
        return [int(pair[0]), int(pair[1])]
    except (TypeError, ValueError):
        return None


def window_mean_plddt(accession: str, start: int, end: int) -> float | None:
    """Mean pLDDT over [start, end], 1-based inclusive, or None.

    None rather than zero when the model is missing or the range falls
    outside it: an absent measurement and a measurement of nothing are
    different answers, and a zero here would read as a disordered domain.
    """
    profile = plddt.plddt_profile(accession)
    if not profile:
        return None
    lo, hi = max(1, int(start)), min(len(profile), int(end))
    if hi < lo:
        return None
    span = profile[lo - 1:hi]
    return sum(span) / len(span) if span else None


def overlap_fraction(candidate: tuple[int, int], window: list | None) -> float | None:
    """Fraction of the candidate that lies inside the frozen best window."""
    if not window or len(window) != 2:
        return None
    start, end = candidate
    low, high = int(window[0]), int(window[1])
    shared = max(0, min(end, high) - max(start, low) + 1)
    length = end - start + 1
    return shared / length if length > 0 else None


def candidates(accession: str, limit: int) -> list[dict]:
    """InterPro entries on the accession that fit the cap, longest first.

    Duplicates of one region under several member databases are collapsed on
    the range, which is what the form's own listing does: the same domain
    annotated three times is one choice, not three.
    """
    try:
        found = interpro.domains(accession)
    except Exception:                                   # noqa: BLE001
        return []
    seen: dict[tuple[int, int], dict] = {}
    for domain in found:
        start, end = domain.get("start"), domain.get("end")
        if start is None or end is None:
            continue
        # InterPro entries only. `interpro.domains` returns the member
        # database signatures too (G3DSA:, PF, cd, SM), and those are the
        # "member database duplicates" the form says it collapsed: the same
        # cyclin box arrives four times under four accessions. Listing all
        # of them turned CCNF's seven choices into thirteen rows describing
        # the same handful of regions, which is the opposite of making the
        # decision cheap.
        entry = str(domain.get("entry") or domain.get("accession") or "")
        if not entry.startswith("IPR"):
            continue
        start, end = int(start), int(end)
        length = end - start + 1
        if length < floor() or length > limit:
            continue
        key = (start, end)
        if key not in seen:
            seen[key] = {
                "entry": domain.get("entry") or domain.get("accession") or "?",
                "label": (domain.get("name") or domain.get("label") or "")[:44],
                "start": start,
                "end": end,
                "length": length,
            }
    return _collapse(sorted(seen.values(), key=lambda row: -row["length"]))


# How far two boundaries may differ and still be the same region. InterPro
# annotates a domain and the superfamily containing it as separate entries
# over all but a residue or two of the same range: CCNF carries IPR004367 at
# 408-531 and IPR036915 at 407-530. Listing both offers a choice that is not
# one, and the form this tool exists to help fill in collapsed them, so a
# listing that did not would disagree with the file beside it.
SAME_REGION_SLACK = 3


def _collapse(rows: list[dict]) -> list[dict]:
    """One row per region, preferring the entry that names the domain.

    "Superfamily" is InterPro's word for the containing homologous
    superfamily rather than the domain itself, so where two entries describe
    one region the more specific label is the one worth reading. The other is
    recorded as an alias rather than dropped silently, because an entry
    number that vanished would look like missing data to anyone comparing
    this against InterPro directly.
    """
    kept: list[dict] = []
    for row in rows:
        for other in kept:
            if (abs(other["start"] - row["start"]) <= SAME_REGION_SLACK
                    and abs(other["end"] - row["end"]) <= SAME_REGION_SLACK):
                specific = "superfamily" not in row["label"].lower()
                vague = "superfamily" in other["label"].lower()
                if specific and vague:
                    row["aliases"] = other.get("aliases", []) + [other["entry"]]
                    kept[kept.index(other)] = row
                else:
                    other.setdefault("aliases", []).append(row["entry"])
                break
        else:
            kept.append(row)
    return kept


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gene", help="one gene instead of all fifteen")
    args = parser.parse_args(argv)

    limit = cap()
    rows = selection()
    if args.gene:
        rows = [row for row in rows if row["gene"].upper() == args.gene.upper()]
        if not rows:
            print(f"{args.gene} is not in the frozen Tier B selection", file=sys.stderr)
            return 2
    if not rows:
        print("no frozen Tier B selection to read", file=sys.stderr)
        return 2

    filled = set(form.load())
    print(f"Tier B construct candidates, {limit} residues or fewer "
          f"({paths.thresholds()['manifest']['token_cap_tier1']} token cap "
          f"less a {form.PEPTIDE_RESIDUES}-mer peptide and a "
          f"{form.GLUE_HEAVY_ATOMS}-heavy-atom glue)\n")
    print("pLDDT is the mean over the candidate's own range; window is how")
    print("much of it sits in the frozen best 200-residue window. Neither")
    print("chooses: a disordered range is ruled out, the rest is science.\n")

    for row in rows:
        mean = row["mean_plddt"]
        answered = " [answered]" if any(
            key for key in filled
            if key.upper().startswith(row["gene"].upper())) else ""
        print(f"{row['gene']} ({row['accession']}), whole-model pLDDT "
              f"{'%.1f' % mean if mean is not None else UNREADABLE}, "
              f"best window {row['best_window']}{answered}")
        found = candidates(row["accession"], limit)
        if not found:
            print("    no InterPro entry within the cap: an exception is "
                  "needed, as spec 1.1 makes for VHL and DCAF15")
            print()
            continue
        print(f"    {'entry':<12} {'range':>12} {'aa':>5} {'pLDDT':>7} {'window':>7}  label")
        for candidate in found:
            local = window_mean_plddt(row["accession"], candidate["start"], candidate["end"])
            share = overlap_fraction((candidate["start"], candidate["end"]),
                                      row["best_window"])
            print(f"    {candidate['entry']:<12} "
                  f"{str(candidate['start']) + '-' + str(candidate['end']):>12} "
                  f"{candidate['length']:>5} "
                  f"{('%.1f' % local) if local is not None else UNREADABLE:>7} "
                  f"{('%.0f%%' % (100 * share)) if share is not None else UNREADABLE:>7}"
                  f"  {candidate['label']}"
                  + (f"  (also {', '.join(candidate['aliases'])})"
                     if candidate.get("aliases") else ""))
        print()

    outstanding = form.missing()
    print(f"{len(outstanding)} of {len(rows) if not args.gene else 15} "
          f"still without a construct"
          + (f": {', '.join(outstanding)}" if outstanding else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
