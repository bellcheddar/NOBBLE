"""Check an assembled campaign before spending days of GPU on it.

A 158-pair campaign is about 52 hours. Everything here is free and runs in
seconds, and each check exists because the failure it catches would
otherwise surface somewhere between an hour and two days in:

* a missing or unparseable YAML stops the queue at whichever job reaches it
* a duplicate chain id is accepted by the writer and rejected by Boltz
* a receptor chain pointing at `empty` means the MSA cache missed, and spec
  1.3's whole point is that no campaign contacts an MSA server
* a peptide chain pointing at a cached MSA means the opposite mistake
* a job over the token cap fails late, after the cheap jobs have run
* an asymmetric cofactor is the one that does not fail at all: the run
  completes and Delta-ipTM quietly reports the cofactor instead of the glue
  (D-NOB-034)

The last one is why this exists as a tool rather than a checklist. The
others announce themselves. That one does not.
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from nobble import paths


_MSA_QUERY_CACHE: dict[str, str | None] = {}


def _msa_query_mismatch(msa_path: str, sequence: str) -> str | None:
    """The a3m's query sequence, against the chain it is attached to.

    Cached by path: a 2,360-job campaign references the same eleven
    alignments over and over, and these files run to thirty thousand lines.
    """
    if msa_path not in _MSA_QUERY_CACHE:
        query = None
        try:
            with open(msa_path, errors="replace") as handle:
                seen_header = False
                for line in handle:
                    line = line.strip()
                    if not line:
                        continue
                    if line.startswith(">"):
                        if seen_header:
                            break
                        seen_header = True
                        continue
                    if seen_header:
                        query = line
                        break
        except OSError as problem:
            return f"cached MSA unreadable: {msa_path}: {problem}"
        _MSA_QUERY_CACHE[msa_path] = query

    query = _MSA_QUERY_CACHE[msa_path]
    if query is None:
        return f"cached MSA has no query sequence: {msa_path}"
    gapless = query.replace("-", "").replace(".", "").upper()
    if gapless != sequence.upper():
        return (
            f"cached MSA is not this chain's alignment: {msa_path} queries "
            f"{len(gapless)} residues, the chain has {len(sequence)}"
            if len(gapless) != len(sequence) else
            f"cached MSA is not this chain's alignment: {msa_path} queries a "
            f"different sequence of the same length"
        )
    return None


def preflight(campaign: Path) -> dict:
    import yaml

    queue_path = campaign / "queue.jsonl"
    if not queue_path.exists():
        return {"status": f"no queue at {queue_path}", "ok": False,
                "errors": [{"job": campaign.name, "problem": "no queue.jsonl"}]}

    jobs = paths.read_jsonl(queue_path)
    cap = int(paths.thresholds()["manifest"]["token_cap_tier1"])
    # Constructs that declared themselves over the cap are not violations:
    # DCAF15_DDB1_DDA1 is 1,223 tokens by construction. Mirror the manifest's
    # own rule rather than inventing a stricter one here, or preflight
    # disagrees with the validation the manifest already passed.
    from nobble.curate import constructs as C

    declared = C.declared_exceptions()

    errors: list[dict] = []
    layouts: Counter = Counter()
    cofactor_by_pair: dict[str, dict[str, bool]] = {}

    for job in jobs:
        job_id = job["job_id"]
        path = Path(job["yaml"])
        if not path.exists():
            errors.append({"job": job_id, "problem": "yaml missing"})
            continue
        try:
            document = yaml.safe_load(path.read_text())
        except Exception as exc:                      # noqa: BLE001
            errors.append({"job": job_id, "problem": f"yaml unparseable: {exc}"})
            continue

        ids: list[str] = []
        has_zinc = False
        for entry in document.get("sequences", []):
            kind = next(iter(entry))
            body = entry[kind]
            ids.append(body.get("id"))
            if kind == "protein":
                cached = body.get("msa") not in ("empty", None)
                is_peptide = body.get("id") == "P"
                if is_peptide and cached:
                    errors.append({"job": job_id,
                                   "problem": "peptide chain carries an MSA (spec 1.3)"})
                if not is_peptide and not cached:
                    errors.append({"job": job_id,
                                   "problem": "receptor chain has no cached MSA: "
                                              "the campaign would call a server"})
                elif cached and not Path(body["msa"]).exists():
                    # The YAML naming a cached file is not the same as the
                    # file being there. A missing a3m fails at whichever job
                    # reaches it, hours into a run.
                    errors.append({"job": job_id,
                                   "problem": f"cached MSA missing on disk: "
                                              f"{body['msa']}"})
                elif cached:
                    # And the file being there is not the same as it being
                    # this chain's alignment. The name is content-addressed,
                    # so it matches by construction; the contents are written
                    # by a separate step and could belong to another protein.
                    # An a3m for the wrong receptor is worse than none: Boltz
                    # would fold confidently against someone else's
                    # conservation (F40).
                    problem = _msa_query_mismatch(body["msa"], body["sequence"])
                    if problem:
                        errors.append({"job": job_id, "problem": problem})
            elif body.get("ccd") == "ZN":
                has_zinc = True

        layouts[tuple(ids)] += 1
        if len(set(ids)) != len(ids):
            errors.append({"job": job_id, "problem": f"duplicate chain id in {ids}"})
        if "P" not in ids:
            errors.append({"job": job_id, "problem": "no peptide chain"})
        if job.get("tokens", 0) > cap and job.get("construct") not in declared:
            errors.append({"job": job_id,
                           "problem": f"{job['tokens']} tokens over the {cap} cap "
                                      f"and {job.get('construct')} is not a declared "
                                      "exception"})

        cofactor_by_pair.setdefault(job["pair_id"], {})[job["complex_type"]] = has_zinc

    # The silent one: a structural cofactor must be in both arms or neither,
    # or Delta-ipTM reports the cofactor rather than the glue.
    asymmetric = [
        {"pair": pair_id, "arms": arms}
        for pair_id, arms in cofactor_by_pair.items()
        if len(arms) > 1 and len(set(arms.values())) > 1
    ]
    for item in asymmetric:
        errors.append({"job": item["pair"],
                       "problem": "zinc present in one arm only: delta_iptm would "
                                  "report the cofactor, not the glue"})

    return {
        "campaign": campaign.name,
        "jobs": len(jobs),
        "pairs": len(cofactor_by_pair),
        "chain_layouts": {" ".join(str(i) for i in k): v for k, v in layouts.most_common()},
        "pairs_with_asymmetric_cofactor": len(asymmetric),
        "errors": errors,
        "ok": not errors,
    }


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Preflight an assembled campaign.")
    parser.add_argument("campaign", nargs="?", default=None)
    args = parser.parse_args()

    campaign = args.campaign
    if campaign is None:
        from nobble.execute.campaign import latest
        campaign = latest("campaign")
    if campaign is None:
        print("no campaign found", file=sys.stderr)
        return 2

    report = preflight(Path(campaign))
    printable = dict(report)
    printable["errors"] = report["errors"][:20]
    print(json.dumps(printable, indent=2))
    if not report["ok"]:
        print(f"PREFLIGHT FAILED: {len(report['errors'])} problem(s)", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
