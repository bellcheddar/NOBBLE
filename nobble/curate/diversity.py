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
from dataclasses import dataclass

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

    def to_dict(self) -> dict:
        return {
            "selected": len(self.selected_ids),
            "mandatory": len(self.mandatory_ids),
            "diverse": len(self.diverse_ids),
            "scrambles": len(self.scramble_ids),
            "candidates": self.candidate_count,
            "reduction_ratio": round(self.reduction_ratio, 4),
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
    return Reduction(
        selected_ids=selected,
        mandatory_ids=mandatory_ids,
        diverse_ids=diverse_ids,
        scramble_ids=scramble_ids,
        candidate_count=len(peptides),
        reduction_ratio=len(selected) / len(peptides) if peptides else 0.0,
        parameters=parameters,
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
