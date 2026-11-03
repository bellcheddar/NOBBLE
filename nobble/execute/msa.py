"""MSA precomputation (spec 1.3).

One MSA per trimmed receptor construct segment, generated once before the
campaign and cached as .a3m under data/msa/. Every YAML references the cached
file. No MSA server is contacted during a campaign: that is the whole point of
the policy, because a multi-day queue that makes a network call per job fails
in a way that is both slow and non-reproducible.

Peptide and ligand chains get no MSA at all. For the peptide that is deliberate:
a 15-mer degron has no meaningful homology signal, and Boltz accepts the literal
string "empty" for a chain that should carry none.

The MMseqs2 client is Boltz's own `run_mmseqs2`, reused rather than
reimplemented (D-NOB-007). It talks to the ColabFold server, which is why this
runs as a one-off precompute step and not inside the queue.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

from nobble import paths

CACHE = paths.MSA
INDEX = CACHE / "index.json"
EMPTY = "empty"          # Boltz's sentinel for a chain with no MSA


def sequence_key(sequence: str) -> str:
    """Content-addressed name, so identical segments share one MSA.

    DDB1's BPC propeller appears in two different constructs, and ElonginB and
    ElonginC will reappear in any future VHL construct. Keying on the sequence
    rather than the construct means each distinct sequence is aligned once.
    """
    return hashlib.sha1(sequence.encode()).hexdigest()[:16]


def a3m_path(sequence: str) -> Path:
    return CACHE / f"{sequence_key(sequence)}.a3m"


def is_cached(sequence: str) -> bool:
    path = a3m_path(sequence)
    return path.exists() and path.stat().st_size > 0


def load_index() -> dict:
    if INDEX.exists():
        return json.loads(INDEX.read_text())
    return {}


def save_index(index: dict) -> None:
    INDEX.write_text(json.dumps(index, indent=2, sort_keys=True))


def required_sequences() -> list[dict]:
    """Every distinct receptor segment sequence the constructs need."""
    from nobble.curate import constructs as C

    wanted: dict[str, dict] = {}
    for construct in C.CONSTRUCTS.values():
        for segment in construct.segments:
            try:
                sequence = segment.sequence()
            except Exception as problem:            # noqa: BLE001
                wanted.setdefault(f"error:{segment.accession}", {
                    "error": f"{type(problem).__name__}: {problem}",
                    "accession": segment.accession,
                    "construct": construct.name,
                })
                continue
            if not sequence:
                continue
            key = sequence_key(sequence)
            record = wanted.setdefault(key, {
                "key": key,
                "sequence": sequence,
                "length": len(sequence),
                "accession": segment.accession,
                "label": segment.label,
                "constructs": [],
            })
            record["constructs"].append(construct.name)
    return list(wanted.values())


def fetch(sequence: str, label: str = "") -> dict:
    """Generate and cache one MSA. Idempotent: a cached file is never refetched."""
    key = sequence_key(sequence)
    path = a3m_path(sequence)
    if is_cached(sequence):
        return {"key": key, "status": "cached", "path": str(path),
                "bytes": path.stat().st_size, "label": label}

    # Imported here, not at module scope: this module is read by the curation
    # environment, which has no boltz installed, and only the precompute step
    # needs the client.
    from boltz.data.msa.mmseqs2 import run_mmseqs2

    scratch = CACHE / f".work_{key}"
    scratch.mkdir(parents=True, exist_ok=True)
    try:
        # run_mmseqs2 returns the list of a3m strings directly, one per input
        # sequence. Its own type annotation claims a 2-tuple, which is stale:
        # the templates element is not returned at all on this code path, and
        # unpacking two values raises "not enough values to unpack".
        result = run_mmseqs2(
            [sequence], prefix=str(scratch), use_env=True, use_filter=True,
            use_pairing=False,
        )
        lines = list(result[0]) if isinstance(result, tuple) else list(result)
    except Exception as problem:                    # noqa: BLE001
        return {"key": key, "status": f"failed: {type(problem).__name__}: {problem}",
                "path": None, "label": label}

    if not lines or not lines[0].strip():
        return {"key": key, "status": "failed: empty alignment returned",
                "path": None, "label": label}

    path.write_text(lines[0])
    depth = sum(1 for row in lines[0].splitlines() if row.startswith(">"))
    return {"key": key, "status": "generated", "path": str(path),
            "bytes": path.stat().st_size, "depth": depth, "label": label}


def precompute() -> dict:
    """Generate every missing receptor MSA, writing progress as it goes.

    Resumable by construction: the cache is content-addressed and checked before
    each fetch, so a killed run picks up exactly where it stopped.
    """
    needed = required_sequences()
    index = load_index()
    results = []

    for record in needed:
        if "error" in record:
            results.append({"status": record["error"], "accession": record["accession"]})
            continue
        label = f"{record['accession']} {record['label']}"
        outcome = fetch(record["sequence"], label=label)
        outcome.update({
            "accession": record["accession"],
            "length": record["length"],
            "constructs": record["constructs"],
        })
        results.append(outcome)
        index[record["key"]] = {
            key: value for key, value in outcome.items() if key != "sequence"
        }
        save_index(index)
        print(f"  {outcome['status']:12s} {label} ({record['length']} aa)", flush=True)

    generated = sum(1 for item in results if item.get("status") == "generated")
    cached = sum(1 for item in results if item.get("status") == "cached")
    failed = [item for item in results if str(item.get("status", "")).startswith("failed")]
    return {
        "required": len(needed),
        "generated": generated,
        "cached": cached,
        "failed": failed,
        "results": results,
    }


def main() -> int:
    summary = precompute()
    print(json.dumps(
        {key: value for key, value in summary.items() if key != "results"},
        indent=2,
    ))
    return 1 if summary["failed"] else 0


if __name__ == "__main__":
    sys.exit(main())


def substrate_domain_sequences() -> list[dict]:
    """Substrate domains that need their own MSA (D-NOB-027).

    Spec 1.3 gives peptide chains no MSA, and that is right for a peptide: a
    15-mer degron has no meaningful homology signal. A substrate submitted as a
    **folded domain** is not a peptide, though. It is a protein chain like any
    other, it has to fold for the prediction to mean anything, and co-folding
    it without an MSA would handicap exactly the arm of the experiment meant to
    show that the whole domain does better than the fragment. Running that
    comparison with one side starved of evolutionary signal would confound it.

    So folded-domain substrates get an MSA and 15-mer substrates do not, which
    follows spec 1.3's reasoning rather than its literal wording.
    """
    from nobble.curate import numbering
    from nobble.curate import peptides as peptide_module

    wanted: dict[str, dict] = {}
    for plan in peptide_module.benchmark_substrate_constructs():
        substrate = plan["substrate"]
        if substrate["mode"] != "folded_domain":
            continue
        sequence = numbering.canonical_sequence(substrate["accession"])[
            substrate["start"] - 1 : substrate["end"]
        ]
        if not sequence:
            continue
        key = sequence_key(sequence)
        record = wanted.setdefault(key, {
            "key": key,
            "sequence": sequence,
            "length": len(sequence),
            "accession": substrate["accession"],
            "label": f"{plan['gene']} {substrate.get('interpro', 'domain')}",
            "members": [],
        })
        record["members"].append(plan["member"])
    return list(wanted.values())


def precompute_substrate_domains() -> dict:
    """Generate the MSAs the corrected substrate constructs need."""
    needed = substrate_domain_sequences()
    index = load_index()
    results = []
    for record in needed:
        outcome = fetch(record["sequence"], label=record["label"])
        outcome.update({"accession": record["accession"], "length": record["length"],
                        "members": record["members"]})
        results.append(outcome)
        index[record["key"]] = {k: v for k, v in outcome.items() if k != "sequence"}
        save_index(index)
        print(f"  {outcome['status']:12s} {record['label']} ({record['length']} aa)", flush=True)
    failed = [item for item in results if str(item.get("status", "")).startswith("failed")]
    return {"required": len(needed), "failed": failed, "results": results}
