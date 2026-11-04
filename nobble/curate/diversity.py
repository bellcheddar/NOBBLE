"""ESM-2 embedding and diversity reduction (spec 3.4).

The candidate library runs to tens of thousands of peptides and a 48-hour
campaign affords a few hundred. Spec 3.4 is explicit that the reduction is by
diversity rather than by random sampling, because random sampling at a few
hundred wastes a large fraction of the run on near-duplicates.

Three properties the reduction has to preserve, and does:

1. **Mandatory members survive.** The benchmark panel degrons and the full
   Sievers matched set are pinned before diversity selection touches anything.
   The headline Delta-ipTM ROC is computed on the Sievers split, so losing any of
   its 32 positives to a clustering decision would cost the campaign its
   headline result.
2. **Matched pairs stay together.** A composition-matched scramble is only a
   control for its own parent. Scrambles are therefore attached after selection,
   following whichever positives were chosen, never selected on their own.
3. **Selection is reproducible.** Fixed seed, and the embedding is a pure
   function of the sequence.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field

from nobble import paths

MODEL_NAME = "facebook/esm2_t12_35M_UR50D"
EMBEDDING_CACHE = paths.DATA / "cache" / "esm2"
EMBEDDING_CACHE.mkdir(parents=True, exist_ok=True)
SEED = 20261103


@dataclass
class Reduction:
    selected_ids: list[str]
    mandatory_ids: list[str]
    diverse_ids: list[str]
    scramble_ids: list[str]
    candidate_count: int
    reduction_ratio: float
    parameters: dict
    budget: int = 0
    over_budget_by: int = 0
    status: str = "within_budget"
    notes: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "selected": len(self.selected_ids),
            "mandatory": len(self.mandatory_ids),
            "diverse": len(self.diverse_ids),
            "scrambles": len(self.scramble_ids),
            "candidates": self.candidate_count,
            "reduction_ratio": round(self.reduction_ratio, 4),
            "budget": self.budget,
            "over_budget_by": self.over_budget_by,
            "status": self.status,
            "notes": self.notes,
            "parameters": self.parameters,
            "selected_ids": self.selected_ids,
        }


def _torch_environment() -> dict:
    settings = paths.tuning().get("env", {})
    return dict(os.environ, **{key: str(value) for key, value in settings.items()})


def embed(sequences: list[str], batch_size: int = 256) -> "object":
    """Mean-pooled ESM-2 embeddings, L2-normalised, as a numpy array.

    Mean pooling over the unpadded positions rather than the CLS token: for a
    15-mer the CLS representation of a small ESM-2 carries much less about
    composition and order than the token mean does, and this embedding is used
    only to spread the selection across sequence space.
    """
    import numpy
    import torch
    from transformers import AutoModel, AutoTokenizer

    tuning = paths.tuning()["compute"]
    device = tuning["model_device"]

    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
    model = AutoModel.from_pretrained(MODEL_NAME).eval().to(device)

    vectors = []
    with torch.no_grad():
        for start in range(0, len(sequences), batch_size):
            chunk = sequences[start : start + batch_size]
            batch = tokenizer(chunk, return_tensors="pt", padding=True, truncation=True)
            batch = {key: value.to(device) for key, value in batch.items()}
            hidden = model(**batch).last_hidden_state
            mask = batch["attention_mask"].unsqueeze(-1).to(hidden.dtype)
            pooled = (hidden * mask).sum(1) / mask.sum(1).clamp(min=1)
            vectors.append(pooled.float().cpu().numpy())

    matrix = numpy.concatenate(vectors, axis=0)
    norms = numpy.linalg.norm(matrix, axis=1, keepdims=True)
    return matrix / numpy.clip(norms, 1e-9, None)


def reduce_library(
    peptides: list,
    budget: int,
    mandatory_sources: tuple[str, ...] = ("benchmark", "sievers_zf"),
) -> Reduction:
    """Select `budget` peptides: mandatory members, then maximally diverse others."""
    import numpy
    from sklearn.cluster import KMeans

    by_id = {peptide.peptide_id: peptide for peptide in peptides}

    mandatory = [
        peptide for peptide in peptides
        if peptide.source in mandatory_sources and peptide.source != "scramble"
    ]
    scrambles = [peptide for peptide in peptides if peptide.source == "scramble"]
    optional = [
        peptide for peptide in peptides
        if peptide.source != "scramble" and peptide not in mandatory
    ]

    mandatory_ids = [peptide.peptide_id for peptide in mandatory]

    # The budget bounds the whole selection, scrambles included, because every
    # peptide that reaches the manifest costs inference time whether it is a
    # positive or its control. Each selected positive that has a scramble brings
    # exactly one, so the headroom for diverse positives is half what is left
    # after the mandatory members and their own scrambles are paid for.
    scramble_parents = {
        peptide.parent_peptide_id for peptide in scrambles if peptide.parent_peptide_id
    }
    mandatory_scrambles = sum(
        1 for identifier in mandatory_ids if identifier in scramble_parents
    )
    headroom = budget - len(mandatory_ids) - mandatory_scrambles
    remaining = max(0, headroom // 2)

    diverse_ids: list[str] = []
    parameters = {
        "model": MODEL_NAME,
        "pooling": "masked token mean, L2 normalised",
        "seed": SEED,
        "budget": budget,
        "mandatory_sources": list(mandatory_sources),
        "clustering": None,
    }

    if remaining and optional:
        clusters = min(remaining, len(optional))
        embeddings = embed([peptide.sequence for peptide in optional])
        kmeans = KMeans(n_clusters=clusters, random_state=SEED, n_init=4)
        assignments = kmeans.fit_predict(embeddings)
        parameters["clustering"] = {
            "algorithm": "k-means",
            "clusters": clusters,
            "n_init": 4,
            "embedding_dimension": int(embeddings.shape[1]),
            "inertia": float(kmeans.inertia_),
        }
        # One representative per cluster: the member closest to its centroid.
        for cluster in range(clusters):
            members = numpy.where(assignments == cluster)[0]
            if not len(members):
                continue
            centroid = kmeans.cluster_centers_[cluster]
            distances = numpy.linalg.norm(embeddings[members] - centroid, axis=1)
            diverse_ids.append(optional[members[int(numpy.argmin(distances))]].peptide_id)

    selected_positives = set(mandatory_ids) | set(diverse_ids)

    # Attach each selected positive's own scramble, so every positive keeps its
    # matched negative. Sievers non-degraded members are already experimental
    # negatives and were deliberately given no scramble.
    scramble_ids = [
        peptide.peptide_id for peptide in scrambles
        if peptide.parent_peptide_id in selected_positives
    ]

    # Priority order, so a run that is cut short by the 48-hour budget still
    # yields the headline figures rather than an arbitrary prefix. Spec 1.2 and
    # the Mac Studio rules both ask for positive controls first, then the
    # headline set, then discovery.
    priority = {"benchmark": 0, "sievers_zf": 1, "curated_degron": 2, "c_degron": 3}

    def rank(identifier: str) -> tuple[int, str]:
        peptide = by_id[identifier]
        if peptide.source == "scramble":
            parent = by_id.get(peptide.parent_peptide_id)
            # A scramble sits immediately behind its parent: a control that runs
            # without its positive, or a positive whose control was trimmed off
            # the end of the queue, measures nothing.
            base = priority.get(parent.source, 9) if parent else 9
            return (base, f"{peptide.parent_peptide_id}~scramble")
        return (priority.get(peptide.source, 9), peptide.peptide_id)

    selected = sorted(set(selected_positives) | set(scramble_ids), key=rank)

    # The mandatory set is never trimmed to fit. Dropping Sievers members to
    # reach a number would silently shrink the matched split the headline ROC
    # is computed on, and a ROC over a quietly truncated control set is worse
    # than no ROC. So the overrun is reported instead of absorbed, and the
    # priority ordering above is what makes that safe: a run cut short by the
    # wall clock yields the benchmark panel, then the Sievers split, and loses
    # discovery from the tail rather than losing a control from the middle.
    notes: list[str] = []
    over = max(0, len(selected) - budget)
    status = "within_budget"
    if over:
        status = "over_budget: mandatory members alone exceed the measured budget"
        notes.append(
            f"{len(selected)} peptides selected against a budget of {budget}, "
            f"over by {over}. The mandatory sources ({', '.join(mandatory_sources)}) "
            f"contribute {len(mandatory_ids)} peptides and are not trimmed: the "
            "Sievers matched split is the headline ROC's control set, and "
            "truncating it to hit a number would quietly weaken the measurement "
            "it exists to support. The queue is priority-ordered, so a run cut "
            "short loses discovery from the tail, not a control from the middle."
        )
    if headroom < 0:
        notes.append(
            f"no headroom for diverse discovery peptides: the mandatory members "
            f"and their scrambles cost {len(mandatory_ids) + mandatory_scrambles} "
            f"against a budget of {budget}. This campaign is calibration only."
        )

    return Reduction(
        selected_ids=selected,
        mandatory_ids=mandatory_ids,
        diverse_ids=diverse_ids,
        scramble_ids=scramble_ids,
        candidate_count=len(peptides),
        reduction_ratio=len(selected) / len(peptides) if peptides else 0.0,
        parameters=parameters,
        budget=budget,
        over_budget_by=over,
        status=status,
        notes=notes,
    )


def campaign_budget(default_pairs: int = 220) -> int:
    """Peptide budget, sized from the measured throughput when Phase 2 has run.

    Spec 1.2 is explicit that the manifest generator sizes itself from the
    measured rate rather than the spec's estimate, so this reads
    data/throughput.json and only falls back to the estimate when Phase 2 has
    not run yet.
    """
    if paths.THROUGHPUT.exists():
        measured = json.loads(paths.THROUGHPUT.read_text())
        pairs = measured.get("affordable_pairs")
        if pairs:
            return int(pairs)
    return default_pairs


def _token_band(tokens: int, edges: list[int]) -> tuple[int, int]:
    """Imported from the writer so one definition decides the bands.

    Two copies of a binning rule is how a rate measured in one set of bands
    comes to be applied in another, which would be the same defect as F61
    arriving by duplication.
    """
    from nobble.execute.runner import token_band

    return token_band(tokens, edges)


def projected_hours(pairs: int, total_tokens: int | None = None,
                    job_tokens: list[int] | None = None) -> dict:
    """Wall-clock hours a selection of `pairs` would take at measured rate.

    Two budgets exist and they are not the same thing, which matters because
    only one of them is a Gate. `wall_clock_budget_hours` (48) is the target
    for a single unattended run and is what `affordable_pairs` is sized
    against. `max_compute_hours` (96) is the Gate G1 threshold. A selection
    that overruns the first is a scheduling fact the priority ordering already
    handles; a selection that overruns the second has to stop and ask.

    Evaluating that in code rather than by eye, because the two numbers are
    close enough to talk yourself across.

    `total_tokens` is the token count of the campaign being sized, and should
    be given whenever it is known. Without it the projection multiplies the
    job count by a "representative job" taken from whichever campaign was
    measured last, which is only right when the two campaigns have the same
    job-size distribution.

    They did not. Throughput measured on the corrected campaign, whose median
    job is 397 tokens, projected the main campaign, whose median job is 124,
    at 104.3 hours and opened Gate G1. A false gate stops an unattended build,
    which is the most expensive thing this function can do (F45).

    `job_tokens` is the token count of each job being sized, and is better
    than `total_tokens` for the same reason `total_tokens` is better than a
    job count. F45's fix replaced a representative job with one median
    seconds-per-token rate, and this docstring claimed the result was
    reached by "summing the real tokens at the rate measured for jobs of
    each size". It was not: the code multiplied every token by one median.

    That rate is not a property of the model. Measured on the main
    campaign it runs from 0.21 to 0.66 s/token across the configured token
    bands, because attention cost does not grow linearly with sequence
    length, and one median understates any campaign whose large jobs are a
    minority of the jobs and a majority of the cost. On the main campaign's
    own remaining queue the flat rate gives 48.6 hours and the banded rate
    51.4 (F61).

    Given `job_tokens` each job is priced in its own band. A band with no
    measurement is priced at the slowest rate observed, which is the
    pessimistic choice, and `unmeasured_jobs` says how many were.

    Token count is the only factor, and that was tested rather than
    assumed. Pocket conditioning looked like a second one: a conditioned
    job measured 0.7375 s/token beside unconstrained jobs at 0.6630. It was
    a size confound, the conditioned job being 1223 tokens and the others
    1199. Controlling for token count across 276 timed jobs, the two
    conditionings agree to the fourth decimal at every size where both
    exist, 0.5075 against 0.5049 at 143 tokens and 0.7313 against 0.7324 at
    1223. Binary jobs look cheaper per token for the same reason: they are
    smaller, not structurally faster.

    Recorded so the projection is not "refined" later by a factor the data
    does not support. Not a test, because asserting a tolerance between two
    medians of live measurements is the kind of check that fails for
    reasons unrelated to the thing it protects (F75).
    """
    tuning = paths.tuning()["campaign"]
    budget_hours = float(tuning["wall_clock_budget_hours"])
    max_hours = float(tuning["max_compute_hours"])

    if not paths.THROUGHPUT.exists():
        return {"status": "not_computed: no measured throughput yet",
                "pairs": pairs}

    measured = json.loads(paths.THROUGHPUT.read_text())
    seconds_per_job = measured.get("seconds_per_representative_job")
    per_pair = measured.get("jobs_per_pair")
    if not seconds_per_job or not per_pair:
        return {"status": "not_computed: throughput file is incomplete",
                "pairs": pairs}

    rate = measured.get("median_seconds_per_token")
    bands = measured.get("seconds_per_token_by_band") or []
    unmeasured = 0
    if job_tokens and bands:
        # Each job at the rate measured for jobs of its size, which is what
        # this function has always claimed to do.
        edges = [int(edge) for edge in
                 paths.thresholds()["throughput"]["token_bands"]]
        measured_rate = {
            (int(band["min_tokens"]), int(band["max_tokens"] or 0)):
                float(band["median_seconds_per_token"]) for band in bands
        }
        slowest = max(measured_rate.values())
        seconds = 0.0
        for tokens in job_tokens:
            band = _token_band(int(tokens), edges)
            if band in measured_rate:
                seconds += tokens * measured_rate[band]
            else:
                seconds += tokens * slowest
                unmeasured += 1
        hours = seconds / 3600.0
        basis = (
            f"{len(job_tokens):,} jobs totalling {sum(job_tokens):,} tokens, "
            f"each priced in its own token band across {len(bands)} measured "
            f"band(s) spanning "
            f"{min(float(b['median_seconds_per_token']) for b in bands)} to "
            f"{slowest} s/token"
        )
        if unmeasured:
            basis += (f"; {unmeasured} job(s) fall in a band with no "
                      f"measurement and are priced at {slowest} s/token")
    elif total_tokens and rate:
        # Per-token rate transfers between campaigns; a representative job
        # does not. One rate for every job size does not either, which is
        # why this is now the fallback rather than the method.
        hours = (total_tokens * float(rate)) / 3600.0
        basis = (f"{total_tokens:,} tokens at the measured {rate} s/token, "
                 "one rate for every job size because the per-job token "
                 "counts were not supplied")
    else:
        hours = (pairs * per_pair * seconds_per_job) / 3600.0
        basis = (
            f"{pairs * per_pair} jobs at {seconds_per_job} s for a "
            f"{measured.get('representative_tokens')}-token job, which is the "
            f"median job of {measured.get('campaign')} and not necessarily of "
            "the campaign being sized"
        )
    gate_open = hours > max_hours
    return {
        "status": "gate_g1_open" if gate_open else "within_max_compute",
        "pairs": pairs,
        "jobs": pairs * per_pair,
        "projected_hours": round(hours, 1),
        "basis": basis,
        "unmeasured_jobs": unmeasured,
        "wall_clock_budget_hours": budget_hours,
        "max_compute_hours": max_hours,
        "over_wall_clock_target": round(max(0.0, hours - budget_hours), 1),
        "gate_g1_open": gate_open,
        "note": (
            "Gate G1 is defined against max_compute_hours, not the 48-hour "
            "per-run target. Overrunning the target is a scheduling fact the "
            "priority ordering absorbs: the run yields the benchmark panel, "
            "then the Sievers split, and loses discovery off the tail. "
            "Overrunning max_compute_hours is what opens the gate."
        ),
    }
