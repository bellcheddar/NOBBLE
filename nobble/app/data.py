"""Read-only access to a campaign's scored output, for the app.

The app never computes a score. Everything it shows is produced by
`nobble.score.run` and read from disk here, so a number on screen can always be
traced to the record that produced it. Spec Phase 4's tooltip requirement
depends on that: every value carries its own provenance.

Loaded lazily and cached by file modification time, so the app can be left
running while a campaign is still executing and will pick up new results
without a restart.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from nobble import paths

_CAMPAIGN: Path | None = None
_CACHE: dict = {}


def configure(campaign: str | None = None) -> Path | None:
    """Pin the app to a campaign directory, or the most recent one.

    NOBBLE_CAMPAIGN points the deployed app at the published atlas, which has
    the same layout as a campaign directory but holds only the scored records
    and the predicted structures: the droplet serves a precomputed slice and
    does no compute at request time.
    """
    global _CAMPAIGN
    import os

    if campaign:
        _CAMPAIGN = Path(campaign)
    elif os.environ.get("NOBBLE_CAMPAIGN"):
        _CAMPAIGN = Path(os.environ["NOBBLE_CAMPAIGN"])
    else:
        try:
            from nobble.execute.campaign import latest
            _CAMPAIGN = latest("benchmark")
        except Exception:                        # noqa: BLE001
            _CAMPAIGN = None
    return _CAMPAIGN


def campaign_dir() -> Path | None:
    return _CAMPAIGN


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


def _cached(key: str, path: Path, loader):
    """Cache by (path, mtime) so a live campaign refreshes without a restart."""
    if not path.exists():
        return loader(path) if False else ([] if key != "campaign" else {})
    stamp = path.stat().st_mtime
    entry = _CACHE.get(key)
    if entry and entry[0] == stamp:
        return entry[1]
    value = loader(path)
    _CACHE[key] = (stamp, value)
    return value


def scores() -> list[dict]:
    if _CAMPAIGN is None:
        return []
    return _cached("scores", _CAMPAIGN / "scores.jsonl", _read_jsonl)


def queue() -> list[dict]:
    if _CAMPAIGN is None:
        return []
    return _cached("queue", _CAMPAIGN / "queue.jsonl", _read_jsonl)


def results() -> list[dict]:
    if _CAMPAIGN is None:
        return []
    return _cached("results", _CAMPAIGN / "results.jsonl", _read_jsonl)


def campaign_meta() -> dict:
    if _CAMPAIGN is None:
        return {}
    path = _CAMPAIGN / "campaign.json"
    return _cached("campaign", path, lambda p: json.loads(p.read_text()))


def precomputed(name: str) -> dict:
    """A document precomputed into the atlas by deploy/build_atlas.py.

    The app never imports the curation pipeline at request time: the droplet
    has no gemmi, no pandas and no BINMAN checkout, and two routes that did
    import it returned 500 there while working locally.
    """
    if _CAMPAIGN is None:
        return {}
    path = _CAMPAIGN / name
    if not path.exists():
        return {}
    return _cached(f"pre:{name}", path, lambda p: json.loads(p.read_text()))


def weight_fit() -> dict:
    """The fitted composite weights, or the refusal and its reason."""
    if _CAMPAIGN is None:
        return {}
    path = _CAMPAIGN / "weights.json"
    if not path.exists():
        return {}
    return _cached("weights", path, lambda p: json.loads(p.read_text()))


def throughput() -> dict:
    if not paths.THROUGHPUT.exists():
        return {}
    return json.loads(paths.THROUGHPUT.read_text())


@dataclass
class CampaignState:
    """What the app can and cannot show, so every tab can say so honestly."""

    campaign_id: str | None
    present: bool
    pairs_total: int
    pairs_scored: int
    jobs_total: int
    jobs_done: int
    running: bool

    def to_dict(self) -> dict:
        return {
            "campaign_id": self.campaign_id,
            "present": self.present,
            "pairs_total": self.pairs_total,
            "pairs_scored": self.pairs_scored,
            "jobs_total": self.jobs_total,
            "jobs_done": self.jobs_done,
            "running": self.running,
            "percent": round(100 * self.jobs_done / self.jobs_total, 1)
            if self.jobs_total else 0.0,
        }


def campaign_state() -> dict:
    meta = campaign_meta()
    queue_rows = queue()
    done = results()
    scored = scores()
    state = CampaignState(
        campaign_id=meta.get("campaign_id") or (_CAMPAIGN.name if _CAMPAIGN else None),
        present=bool(_CAMPAIGN and _CAMPAIGN.exists()),
        pairs_total=meta.get("pairs", 0) or len({row.get("pair_id") for row in queue_rows}),
        pairs_scored=len(scored),
        jobs_total=len(queue_rows),
        jobs_done=len(done),
        running=len(done) < len(queue_rows),
    )
    return state.to_dict()


# Component metadata for the weights panel and the tooltips. Each entry carries
# what the number is, its units, and whether it is measured, predicted or
# model-derived, which is what spec Phase 4's tooltip requirement asks for.
COMPONENTS = {
    "bridge_percentile": {
        "label": "Bridge percentile",
        "units": "percentile",
        "source": "measured against 285,996 observed bridges",
        "trust": "primary",
        "default_weight": 0.35,
        "note": "Buried surface of the glue against both chains, as a percentile "
                "of the experimentally observed distribution. Compares a "
                "prediction to real interfaces rather than to the model's own "
                "confidence.",
    },
    "delta_iptm": {
        "label": "Delta-ipTM",
        "units": "ipTM difference",
        "source": "model-derived",
        "trust": "headline",
        "default_weight": 0.25,
        "note": "Ternary minus binary interface confidence on the "
                "receptor-to-peptide chain pair, minimum across seeds. A "
                "collapsed seed can dominate it: the median is shown alongside.",
    },
    "convergence_score": {
        "label": "Pose convergence",
        "units": "0 to 1, from mean pairwise RMSD",
        "source": "measured from the predictions",
        "trust": "high",
        "default_weight": 0.25,
        "note": "Pairwise peptide backbone RMSD across seeds after superposing "
                "on the receptor. Tracks reality better than confidence for "
                "peptides.",
    },
    "plip_fingerprint_match": {
        "label": "PLIP fingerprint match",
        "units": "fraction of canonical contacts",
        "source": "measured from the predictions",
        "trust": "high",
        "default_weight": 0.15,
        "note": "Fraction of the canonical degron contacts for that E3 class "
                "that the prediction reproduces.",
    },
    "lysine_reach": {
        "label": "Lysine geometry",
        "units": "not validated",
        "source": "measured, but not a validated predictor",
        "trust": "not validated",
        "default_weight": 0.0,
        "note": "BINMAN's reach window is deliberately unfitted: Cb-Cb AUC 0.42 "
                "to 0.48 on 369 assayed lysines, at or below chance and slightly "
                "inverted. Reported as a measurement only.",
    },
}
