"""Compare what Boltz folded against what the YAML asked for (F219).

Every check this project had for a stale input read the YAML. Boltz caches
the featurised input in `boltz_results_<job>/processed/` and reuses it when
the job runs again, so a corrected YAML beside a stale cache reads as
corrected from every angle except the one that matters: the residues actually
folded.

This reads them. `processed/structures/<job>.npz` carries a `residues` record
array with a `name` field and a `chains` array giving each chain's first
residue index, so the first residue of the peptide chain is readable without
re-running anything.

Scoped to the first residue of each chain rather than to the whole sequence
deliberately. A modification anywhere would be worth catching, but the
positions in a YAML's `modifications` block are 1-based within the chain and
resolving every one of them against the cache means reimplementing Boltz's
tokenisation, which would be a second thing to be wrong. The first residue is
where this project's modifications land (spec 2.3's degron classes are
N-terminal) and it needs no tokenisation at all.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from nobble import paths  # noqa: E402

# Boltz names a chain's residues with the CCD code it folded, so an applied
# modification is visible as the modified code and an unapplied one as the
# parent. Only the mapping from a modification's CCD to the parent it
# replaces is needed, and only for the codes spec 2.3 uses.
PARENT_OF = {"HYP": "PRO", "SEP": "SER", "TPO": "THR"}


def cached_first_residues(job_output: Path) -> dict[str, str] | None:
    """Each chain's first folded residue, or None if there is no cache."""
    import numpy as np

    found = list(job_output.glob("boltz_results_*/processed/structures/*.npz"))
    if not found:
        return None
    data = np.load(found[0], allow_pickle=True)
    if "chains" not in data.files or "residues" not in data.files:
        return None
    residues = data["residues"]
    out = {}
    for chain in data["chains"]:
        name = chain["name"]
        name = name.decode() if isinstance(name, bytes) else str(name)
        first = residues[int(chain["res_idx"])]["name"]
        first = first.decode() if isinstance(first, bytes) else str(first)
        out[name] = first
    return out


def yaml_first_modifications(yaml_path: Path) -> dict[str, str]:
    """Each chain's position-1 modification CCD, as the YAML asks for it.

    An empty mapping means the YAML asks for no modification at position 1 on
    any chain, which is a claim about the YAML and is what gets compared.
    """
    import yaml as yaml_module

    document = yaml_module.safe_load(yaml_path.read_text())
    wanted: dict[str, str] = {}
    for entry in (document or {}).get("sequences", []):
        if not isinstance(entry, dict):
            continue
        for _kind, body in entry.items():
            if not isinstance(body, dict):
                continue
            chain = str(body.get("id", ""))
            for modification in body.get("modifications") or []:
                if int(modification.get("position", 0)) == 1:
                    wanted[chain] = str(modification.get("ccd"))
    return wanted


def disagreements(campaign: Path) -> list[dict]:
    """Jobs whose cached featurisation does not match their YAML."""
    out = []
    for row in paths.read_jsonl(campaign / "queue.jsonl", tolerate_torn=True):
        job_id = row.get("job_id")
        yaml_path = Path(row.get("yaml", ""))
        output = campaign / "outputs" / str(job_id)
        if not yaml_path.exists() or not output.exists():
            continue
        cached = cached_first_residues(output)
        if cached is None:
            continue
        wanted = yaml_first_modifications(yaml_path)
        for chain, folded in cached.items():
            asked = wanted.get(chain)
            if asked is not None:
                # The YAML asks for a modification here.
                if folded != asked:
                    out.append({"job_id": job_id, "chain": chain,
                                "yaml_asks": asked, "folded": folded,
                                "reading": "the modification was not applied"})
            elif folded in PARENT_OF:
                # The YAML asks for none and a modified residue was folded.
                out.append({"job_id": job_id, "chain": chain,
                            "yaml_asks": f"unmodified {PARENT_OF[folded]}",
                            "folded": folded,
                            "reading": "the cache predates the YAML"})
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("campaign", nargs="?", default=None)
    args = parser.parse_args(argv)

    targets = ([Path(args.campaign)] if args.campaign
               else sorted(paths.CAMPAIGNS.glob("*")))
    worst = 0
    for campaign in targets:
        if not (campaign / "queue.jsonl").exists():
            continue
        found = disagreements(campaign)
        if not found:
            print(f"   ok       {campaign.name}: every cached featurisation "
                  "matches its YAML")
            continue
        worst = 1
        print(f"   STALE    {campaign.name}: {len(found)} job(s) folded "
              "something the YAML does not ask for")
        for row in found[:10]:
            print(f"     {row['job_id']} chain {row['chain']}: YAML asks "
                  f"{row['yaml_asks']}, folded {row['folded']} "
                  f"({row['reading']})")
        print("     Fix with tools/rerun_pair.py, which now removes the "
              "cached output so the re-run featurises the YAML.")
    return worst


if __name__ == "__main__":
    raise SystemExit(main())
