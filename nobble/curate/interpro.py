"""InterPro domain boundaries, cached to disk.

Spec 1.1 sizes every receptor construct by its substrate-binding domain, and
spec 3.1 forbids hardcoded residue ranges. Boundaries therefore come from
InterPro at build time and are cached so a campaign needs no network.
"""
from __future__ import annotations

import json
import urllib.request

from nobble import paths

CACHE = paths.DATA / "cache" / "interpro"
CACHE.mkdir(parents=True, exist_ok=True)
URL = "https://www.ebi.ac.uk/interpro/api/entry/all/protein/uniprot/{acc}/?page_size=200"
KEEP_TYPES = {"domain", "family", "homologous_superfamily"}


class AmbiguousEntry(KeyError):
    """An entry annotated at more than one place, with no occurrence given."""


def _fetch(accession: str) -> dict:
    cached = CACHE / f"{accession}.json"
    if cached.exists():
        return json.loads(cached.read_text())
    request = urllib.request.Request(
        URL.format(acc=accession), headers={"Accept": "application/json"}
    )
    with urllib.request.urlopen(request, timeout=120) as response:
        payload = json.load(response)
    cached.write_text(json.dumps(payload))
    return payload


def domains(accession: str) -> list[dict]:
    """Flattened domain annotations: one record per entry per location."""
    payload = _fetch(accession)
    records = []
    for result in payload.get("results", []):
        metadata = result.get("metadata", {})
        if metadata.get("type") not in KEEP_TYPES:
            continue
        for protein in result.get("proteins", []):
            for location in protein.get("entry_protein_locations", []):
                fragments = location.get("fragments") or []
                if not fragments:
                    continue
                # min and max rather than first and last. A discontinuous
                # domain's extent is what a construct boundary needs, and
                # taking the ends by position does not depend on InterPro
                # returning fragments in order. It does today: 345
                # multi-fragment locations across the 1,197 cached
                # accessions, none out of order. Relying on that would be
                # relying on an undocumented property of someone else's
                # API, and getting it wrong moves a construct boundary
                # without anything failing.
                start = min(f["start"] for f in fragments)
                end = max(f["end"] for f in fragments)
                records.append(
                    {
                        "accession": metadata.get("accession"),
                        "database": metadata.get("source_database"),
                        "type": metadata.get("type"),
                        "name": metadata.get("name"),
                        "start": start,
                        "end": end,
                        "length": end - start + 1,
                    }
                )
    # Deterministic order, for the same reason the fragments above are taken
    # by min and max rather than by position: an entry can be annotated at
    # several places on one protein, and which one a caller gets should not
    # depend on the order InterPro happened to list them. FEM1B carries the
    # ankyrin superfamily twice, at 5-301 and at 424-610.
    records.sort(key=lambda record: (record["start"], record["end"],
                                     record["accession"] or ""))
    return records


def domain_by_accession(accession: str, entry: str,
                        occurrence: int | None = None) -> dict:
    """One named InterPro or member-database entry, by its accession.

    Named entries rather than "the longest domain" because which domain binds
    the substrate is science knowledge; where that domain starts and ends is a
    lookup, and only the lookup belongs in the code.

    An entry can be annotated at several places on one protein, and then the
    lookup alone does not answer the question. FEM1B carries IPR036770, the
    ankyrin repeat superfamily, at 5-301 and again at 424-610, so asking for
    "the ankyrin domain" of FEM1B has two answers. This used to return
    whichever InterPro listed first, which is both the wrong 187 or 297
    residues depending on an ordering nobody controls, and a boundary that
    could move without anything failing (F41).

    So an ambiguous entry raises unless the caller says which occurrence it
    means, counted from the N-terminus. Which one is the substrate-binding
    region is science knowledge, like the entry itself, and belongs in the
    construct rather than here.
    """
    matches = [record for record in domains(accession)
               if record["accession"] == entry]
    if not matches:
        raise KeyError(f"{entry} not annotated on {accession}")
    if len(matches) == 1:
        return matches[0]
    if occurrence is None:
        places = ", ".join(f"{m['start']}-{m['end']}" for m in matches)
        raise AmbiguousEntry(
            f"{entry} is annotated {len(matches)} times on {accession} "
            f"({places}): say which occurrence the construct means"
        )
    try:
        return matches[occurrence]
    except IndexError:
        raise KeyError(
            f"{entry} is annotated {len(matches)} times on {accession}, so "
            f"occurrence {occurrence} does not exist"
        ) from None
