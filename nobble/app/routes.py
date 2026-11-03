"""Routes for the six tabs, plus the JSON endpoints the pages read.

Every page renders from `nobble.app.data`, which reads the campaign's scored
output. Nothing is computed here: spec 4.8 fits the composite weights in Phase 3
and the app's weights panel only re-weights components that were already
measured, which is why re-ranking can happen in the browser with no server
round trip.
"""
from __future__ import annotations

import json

from flask import Blueprint, abort, jsonify, render_template, request

from nobble.app import data

bp = Blueprint("nobble", __name__)


def _pair_or_404(pair_id: str) -> dict:
    for row in data.scores():
        if row.get("pair_id") == pair_id:
            return row
    abort(404, description=f"no scored pair {pair_id}")


@bp.route("/")
@bp.route("/campaign")
def campaign():
    return render_template(
        "campaign.html",
        page_title="Campaign",
        active="campaign",
        pairs=data.scores(),
        components=data.COMPONENTS,
        meta=data.campaign_meta(),
        throughput=data.throughput(),
    )


@bp.route("/pose")
def pose():
    pair_id = request.args.get("pair")
    pairs = data.scores()
    selected = None
    if pair_id:
        selected = next((row for row in pairs if row.get("pair_id") == pair_id), None)
    elif pairs:
        selected = pairs[0]
    return render_template(
        "pose.html", page_title="Pose", active="pose",
        pairs=pairs, selected=selected,
    )


@bp.route("/interactions")
def interactions():
    pair_id = request.args.get("pair")
    pairs = data.scores()
    selected = None
    if pair_id:
        selected = next((row for row in pairs if row.get("pair_id") == pair_id), None)
    elif pairs:
        selected = pairs[0]
    return render_template(
        "interactions.html", page_title="Interactions", active="interactions",
        pairs=pairs, selected=selected,
    )


@bp.route("/delta")
def delta():
    return render_template(
        "delta.html", page_title="Delta", active="delta",
        pairs=data.scores(), components=data.COMPONENTS,
    )


@bp.route("/benchmark")
def benchmark():
    from nobble.curate import peptides as peptide_module

    members = {
        f"bench{item['index']:02d}_{item['gene']}_{item['e3']}": item
        for item in peptide_module.BENCHMARK_CHAINS
    }
    scored = {row["pair_id"]: row for row in data.scores()}
    cards = []
    for pair_id, member in sorted(members.items()):
        cards.append({
            "pair_id": pair_id,
            "member": member,
            "scores": scored.get(pair_id),
            "pending": pair_id not in scored,
        })
    return render_template(
        "benchmark.html", page_title="Benchmark", active="benchmark",
        cards=cards, meta=data.campaign_meta(),
    )


@bp.route("/about")
def about():
    from nobble.curate import binman_store, constructs
    from nobble.score import lysine

    return render_template(
        "about.html", page_title="About", active="about",
        sources=binman_store.available(),
        unavailable=binman_store.UNAVAILABLE,
        bridge_reference=binman_store.bridge_reference_count(),
        construct_budget=constructs.budget_report(),
        reach_auc=lysine.BINMAN_REACH_AUC,
        throughput=data.throughput(),
        components=data.COMPONENTS,
    )


# --------------------------------------------------------------------------- #
# JSON endpoints
# --------------------------------------------------------------------------- #

@bp.route("/api/pairs")
def api_pairs():
    return jsonify(data.scores())


@bp.route("/api/pair/<pair_id>")
def api_pair(pair_id: str):
    return jsonify(_pair_or_404(pair_id))


@bp.route("/api/state")
def api_state():
    return jsonify(data.campaign_state())


@bp.route("/api/components")
def api_components():
    return jsonify(data.COMPONENTS)


@bp.route("/healthz")
def healthz():
    state = data.campaign_state()
    return jsonify({"ok": True, "campaign": state["campaign_id"], "jobs_done": state["jobs_done"]})
