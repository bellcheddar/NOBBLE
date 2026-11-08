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


def _stale_check(campaign: Path, errors: list) -> dict:
    """Are these inputs the ones the code would write (F339)?

    Both checks already existed and both ran in the wrong place relative to
    their cost. `deploy/build_atlas.py` refuses on each of them, correctly,
    as the last stage of the chain: a Tier B campaign whose YAML the
    assembler would no longer produce runs its 1,540 jobs over about 33
    hours and the refusal arrives after all of it. The chain's own comment
    says the arm "depends on the form and the library and both can change
    between runs", and `assemble_tier_b` reuses a complete campaign by
    default, so the reuse that comment warns about is the default path.

    This is F327's reasoning across stages rather than within one script: a
    refusal that can be decided from the inputs belongs before the work.
    Measured first, and the answer was negative, which is why this is a
    guard and not an incident: all five campaigns on disk were clean when it
    was written.

    Two checks, because they are two links of the three in the provenance
    chain `_regenerated_scan`'s docstring sets out:

    - `stale_inputs` compares a YAML against the queue row describing it,
      which in practice means the modifications each says it wants. Narrower
      than it sounds, and I wrote this function's first docstring claiming it
      compared the YAML against what the code would emit, which is the next
      check along and not this one. Found by tampering with a YAML and
      watching a different check catch it.
    - `_regenerated_scan` compares the YAML against the code that emits it,
      which is the link F262 broke and the one a changed form would break.
      Called directly, as `deploy/build_atlas.py` does: it needs rows and
      status from one pass, a public accessor kept for symmetry was removed
      as an unused affordance in F291, and two direct callers do not need
      one. About two seconds for a 2,360-job campaign.

    `rows_checked` is reported beside the result because `stale_inputs`
    returns `[]` both for a campaign whose every YAML agrees and for one
    where nothing was examined. `tools/stale_featurisation.py` counting
    `blind` apart from `checked` is what this looks like done right, and
    CLAUDE.md says so.
    """
    try:
        from nobble.validate import inputs

        queues = inputs.queues(campaign)
        rows = 0
        for queue in queues:
            rows += sum(1 for line in queue.read_text().splitlines()
                        if line.strip())
        stale = inputs.stale_inputs(campaign)
        regenerated, regenerated_status = inputs._regenerated_scan(campaign)
    except Exception as problem:                        # noqa: BLE001
        # Not silence. A check that could not run is not a check that
        # passed, and these gate 33 hours.
        errors.append({
            "job": campaign.name,
            "problem": f"the input-provenance checks could not run "
                       f"({type(problem).__name__}: {problem}), so whether "
                       "these YAMLs are the ones the code would write is "
                       "unknown rather than fine",
        })
        return {"stale_inputs": None, "regenerated_disagreements": None,
                "regenerated_status": "could not run",
                "stale_rows_checked": 0, "stale_queues": 0}

    for item in stale[:20]:
        errors.append({
            "job": item.get("job_id") or campaign.name,
            "problem": f"YAML disagrees with its queue row: "
                       f"{item.get('reason') or item}",
        })
    for item in regenerated[:20]:
        errors.append({
            "job": item.get("job_id") or campaign.name,
            "problem": f"YAML is not what the current code would write: "
                       f"{item.get('problem') or item}",
        })
    # "unavailable" means the comparison could not be made, which the atlas
    # build also refuses on rather than reading as agreement.
    if str(regenerated_status).startswith("unavailable"):
        errors.append({
            "job": campaign.name,
            "problem": f"{regenerated_status}, so whether the inputs on disk "
                       "are the ones the code would write is unknown rather "
                       "than fine",
        })
    if queues and not rows:
        errors.append({
            "job": campaign.name,
            "problem": f"{len(queues)} queue(s) hold no rows, so the input "
                       "checks examined nothing and their clean answer means "
                       "only that",
        })
    return {"stale_inputs": len(stale),
            "regenerated_disagreements": len(regenerated),
            "regenerated_status": regenerated_status,
            "stale_rows_checked": rows, "stale_queues": len(queues)}


def preflight(campaign: Path) -> dict:
    import yaml

    queue_path = campaign / "queue.jsonl"
    if not queue_path.exists():
        return {"status": f"no queue at {queue_path}", "ok": False,
                "errors": [{"job": campaign.name, "problem": "no queue.jsonl"}]}

    jobs = paths.read_jsonl(queue_path)
    # An empty queue is a refusal, not a clean bill of health (F323).
    #
    # Every check below iterates the jobs, so with none of them there are no
    # errors and `ok: not errors` came out true: `jobs: 0, pairs: 0, ok:
    # true`. The chain gates a 52-hour run on exactly that flag and prints
    # "refusing to start a 52-hour run on it" when it is false, so a
    # campaign whose queue failed to assemble read as one that had passed
    # every check. A verdict over nothing is not a pass, which is the rule
    # F152 and F293 are both about, here on the project's most consequential
    # gate.
    if not jobs:
        return {"status": f"empty queue at {queue_path}", "ok": False,
                "jobs": 0,
                "errors": [{"job": campaign.name,
                            "problem": "queue.jsonl holds no jobs, so every "
                                       "check below would pass by examining "
                                       "nothing"}]}
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
        has_ligand = False
        for entry in document.get("sequences", []):
            kind = next(iter(entry))
            body = entry[kind]
            ids.append(body.get("id"))
            if kind == "protein":
                cached = body.get("msa") not in ("empty", None)
                is_peptide = body.get("id") == "P"
                if is_peptide:
                    # The sequence folded against the sequence recorded. If
                    # these disagree, every number the job produces is about
                    # a different peptide from the one the manifest, the
                    # scores and the site all name, and nothing downstream
                    # could tell. Swept across 4,340 jobs in five campaigns
                    # and clean, which is worth keeping that way rather than
                    # re-establishing by hand (F263).
                    # Not `declared`: that name is already the token-cap
                    # exception list from line 93, and shadowing it here made
                    # the cap check ask whether a construct name appears
                    # inside a peptide sequence, which fired on 50 jobs that
                    # are declared exceptions. One of the two checks was
                    # wrong from the moment the other was written.
                    declared_peptide = job.get("peptide_sequence")
                    if declared_peptide and (
                            body.get("sequence") != declared_peptide):
                        errors.append({
                            "job": job_id,
                            "problem": "the YAML peptide differs from the "
                                       "record: folding "
                                       f"{(body.get('sequence') or '')[:24]} "
                                       f"and reporting "
                                       f"{declared_peptide[:24]}"})
                    # A declared modification absent from the block is F47's
                    # shape one level up from F219's: that one was the cached
                    # featurisation disagreeing with a corrected YAML, this
                    # is the YAML disagreeing with its own record.
                    if job.get("required_modification") and (
                            "modifications" not in body):
                        errors.append({
                            "job": job_id,
                            "problem": f"declares modification "
                                       f"{job['required_modification']} and "
                                       "its YAML peptide has no "
                                       "modifications block"})
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
            elif kind == "ligand":
                has_ligand = True

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

        # The queue record says there is a glue; the YAML is what gets folded.
        #
        # scr_bench03_BRD4_CRBN went through a whole campaign with
        # ligand_key dBET57 on all ten of its records and no ligand block in
        # any of its five ternary YAMLs, so its ternary arm was a second
        # binary arm. Its Delta-ipTM came out at exactly 0.0, which for a
        # scramble control reads as the cleanest possible result, and its
        # bridge rate was unmeasurable with no_ligand_chain_in_output on
        # every seed. The cause was an assembler falling back to a CCD
        # lookup for a SMILES-only degrader (F262).
        #
        # Checked against the record rather than against the complex type
        # alone: a ternary job with no declared ligand is a different
        # question, and this is the disagreement between what the campaign
        # wrote down and what it would fold.
        # The reverse of the above: a glue in the YAML that no record names.
        # Less harmful, since what was folded is what the ternary arm is for,
        # but it is still the record and the input disagreeing, and whichever
        # way round that is it means one of them is wrong.
        if has_ligand and not job.get("ligand_key"):
            errors.append({
                "job": job_id,
                "problem": "its YAML carries a ligand chain and the record "
                           "names no ligand, so the campaign cannot say what "
                           "was folded"})

        if (job.get("complex_type") == "ternary"
                and job.get("ligand_key") and not has_ligand):
            errors.append({
                "job": job_id,
                "problem": f"declares ligand {job['ligand_key']} "
                           f"({job.get('ligand_encoding')}) and its YAML has no "
                           "ligand chain, so this ternary arm is a second "
                           "binary arm and delta_iptm would come out at 0.0"})

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

    # What the stage costs, from the queue it just checked.
    #
    # The docstring above opens with "before spending days of GPU on it" and
    # every caller's refusal says so in as many words: run_design.sh prints
    # "refusing to spend 240 jobs on it", run_chain.sh "refusing to start a
    # 52-hour run on it". The report named the jobs and never the hours, so
    # the one number the refusal is about had to be looked up somewhere else.
    #
    # Through `projected_hours`, which prices each job in its own token band.
    # A single rate understates a mixed queue whenever the large jobs are a
    # minority of the jobs and a majority of the cost, which is F45 and is
    # already written down in `thresholds.toml` beside `token_bands`. I
    # reproduced it by hand anyway in F225, which is the other half of why
    # this belongs in the report rather than in the reader.
    #
    # Reporting only. A projection never contributes to `ok`: Gate G1 is
    # decided by `budget.gate_g1` against `max_compute_hours`, and a
    # preflight that refused on cost would be a second, quieter gate with no
    # decision recorded.
    cost: dict | None = None
    tokens = [job["tokens"] for job in jobs if isinstance(job.get("tokens"), int)]
    if tokens:
        from nobble.curate.diversity import projected_hours

        projection = projected_hours(len(cofactor_by_pair),
                                     total_tokens=sum(tokens),
                                     job_tokens=tokens)
        cost = {
            "projected_hours": projection.get("projected_hours"),
            "priced_jobs": len(tokens),
            "unpriced_jobs": len(jobs) - len(tokens),
            "basis": projection.get("basis"),
        }

    # Before the result is assembled, because it appends to `errors` and
    # `ok` is read off that list.
    stale = _stale_check(campaign, errors)
    return {
        "campaign": campaign.name,
        "jobs": len(jobs),
        "pairs": len(cofactor_by_pair),
        "chain_layouts": {" ".join(str(i) for i in k): v for k, v in layouts.most_common()},
        "pairs_with_asymmetric_cofactor": len(asymmetric),
        "ternary_jobs_missing_their_ligand": sum(
            1 for item in errors
            if "has no ligand chain" in item.get("problem", "")),
        "cost": cost,
        **stale,
        "errors": errors,
        # Last, and after `_stale_check` has had its say. A dict literal
        # evaluates its values in order, so with the check spread in after
        # this line `ok` was computed from the errors as they stood before
        # it ran: a stale YAML appended an error and the verdict still read
        # `ok: true`. A guard that reports a pass over the problem it just
        # found is the whole shape this session has been clearing out, and
        # it was in the guard added to catch it.
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
