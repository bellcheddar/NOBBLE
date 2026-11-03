"""Read-only access to everything BINMAN already curated.

NOBBLE never re-acquires a source and never writes to BINMAN. The atlas is
opened with mode=ro so a bug here cannot corrupt it. See DECISIONS.md D-NOB-008
for why this is SQLite plus TSV rather than the DuckDB the spec assumed.
"""
from __future__ import annotations

import csv
import sqlite3
from functools import lru_cache
from pathlib import Path

from nobble import paths

# Datasets BINMAN resolved (its Gate G7 note records 11 of 13), keyed by the
# name the NOBBLE spec uses in section 2.1.
VALIDATION_TSV = {
    "sievers_zf_screen": "sievers_zf_screen.tsv",
    "mgtbind_ternary": "mgtbind_ternary.tsv",
    "mgtbind_compounds": "mgtbind_compounds.tsv",
    "mgdb_glues": "mgdb_glues.tsv",
    "molgluedb_glues": "molgluedb_glues.tsv",
    "ubibrowser_literature_e3": "ubibrowser_literature_e3.tsv",
    "ubibrowser_predicted_e3": "ubibrowser_predicted_e3.tsv",
    "protacdb_protacs": "protacdb_protacs.tsv",
    "digly_sites": "digly_sites.tsv",
    "biolip2_annotations": "biolip2_annotations.tsv",
    "biolip2_artefacts": "biolip2_artefacts.tsv",
    "assayed_ubiquitylation": "assayed_ubiquitylation.tsv",
}

# Richer raw files, used where BINMAN's parse dropped columns NOBBLE needs.
# mgtbind_complexes carries the sequences, chain identifiers, phosphosites and
# domain types that the parsed mgtbind_ternary.tsv does not.
VALIDATION_RAW = {
    "mgtbind_complexes": "raw/mgtbind_complexes.csv",
    "mgtbind_compounds_raw": "raw/mgtbind_compounds.csv",
}

# Recorded by BINMAN's Gate G7 as unobtainable. Anything depending on these is
# reported as not computed, never as a negative result. See D-NOB-010.
UNAVAILABLE = ("degronopedia", "protcid_interfaces")


class BinmanUnavailable(RuntimeError):
    """BINMAN's store is missing, which is a build-stopping condition."""


def atlas() -> sqlite3.Connection:
    """Open BINMAN's serve-time atlas read-only."""
    if not paths.BINMAN_ATLAS.exists():
        raise BinmanUnavailable(f"BINMAN atlas not found at {paths.BINMAN_ATLAS}")
    connection = sqlite3.connect(f"file:{paths.BINMAN_ATLAS}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    return connection


def atlas_rows(sql: str, parameters: tuple = ()) -> list[dict]:
    with atlas() as connection:
        return [dict(row) for row in connection.execute(sql, parameters)]


def _resolve(name: str) -> Path:
    if name in VALIDATION_TSV:
        return paths.BINMAN_VALIDATION / VALIDATION_TSV[name]
    if name in VALIDATION_RAW:
        return paths.BINMAN_VALIDATION / VALIDATION_RAW[name]
    if name in UNAVAILABLE:
        raise BinmanUnavailable(
            f"{name} was never acquired (BINMAN Gate G7). Callers must degrade, "
            "not substitute. See DECISIONS.md D-NOB-010."
        )
    raise KeyError(f"unknown BINMAN dataset: {name}")


@lru_cache(maxsize=None)
def dataset(name: str) -> tuple[dict, ...]:
    """Load a curated dataset as a tuple of dicts, cached for the process.

    Delimiter is inferred from the suffix: BINMAN's parsed outputs are TSV and
    its raw downloads are CSV.
    """
    path = _resolve(name)
    if not path.exists():
        raise BinmanUnavailable(f"{name} expected at {path} and not found")
    delimiter = "," if path.suffix.lower() == ".csv" else "\t"
    with path.open(newline="", encoding="utf-8", errors="replace") as handle:
        return tuple(csv.DictReader(handle, delimiter=delimiter))


def available() -> dict[str, bool]:
    """Report which spec section 2.1 sources are present, for the About page."""
    report = {}
    for name in list(VALIDATION_TSV) + list(VALIDATION_RAW):
        try:
            report[name] = _resolve(name).exists()
        except BinmanUnavailable:
            report[name] = False
    for name in UNAVAILABLE:
        report[name] = False
    return report


def bridge_reference_count() -> int:
    """Size of the empirical bridge distribution the geometry percentile uses."""
    return atlas_rows("select count(*) as n from bridge where status = 'ok'")[0]["n"]
