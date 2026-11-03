"""Routes for the six tabs, plus the JSON endpoints the pages read.

Every page renders from `nobble.app.data`, which reads the campaign's scored
output. Nothing is computed here: spec 4.8 fits the composite weights in Phase 3
and the app's weights panel only re-weights components that were already
measured, which is why re-ranking can happen in the browser with no server
round trip.
"""
from __future__ import annotations

import json

from pathlib import Path

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
        weight_fit=data.weight_fit(),
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


@bp.route("/structure/<path:job_id>.cif")
def structure(job_id: str):
    """Serve one predicted mmCIF from the campaign directory.

    Structures are deliberately not in version control and not in the published
    atlas, so they are served from the local campaign only. The job identifier
    is matched against the campaign's own records rather than used to build a
    path, so a crafted identifier cannot escape the directory.
    """
    from flask import Response

    for row in data.results():
        if row.get("job_id") != job_id:
            continue
        path = row.get("structure")
        if not path:
            abort(404, description="no structure recorded for this job")
        resolved = Path(path).resolve()
        campaign = data.campaign_dir()
        if campaign is None or not str(resolved).startswith(str(campaign.resolve())):
            abort(404, description="structure is outside the campaign directory")
        if not resolved.exists():
            abort(404, description="structure file is missing")
        return Response(resolved.read_text(), mimetype="chemical/x-mmcif")
    abort(404, description=f"no completed job {job_id}")


@bp.route("/crystal/<pdb_id>.cif")
def crystal(pdb_id: str):
    """Serve a deposited assembly from BINMAN's cache, for superposition."""
    from flask import Response

    from nobble.curate import structures as structure_module

    if not pdb_id.isalnum() or len(pdb_id) != 4:
        abort(404, description="not a PDB identifier")
    path = structure_module.assembly_path(pdb_id)
    if not path.exists():
        abort(404, description=f"{pdb_id} is not in the assembly cache")
    import gzip

    with gzip.open(path, "rt", errors="replace") as handle:
        return Response(handle.read(), mimetype="chemical/x-mmcif")


@bp.route("/api/pair/<pair_id>/structures")
def api_pair_structures(pair_id: str):
    """Every completed structure for a pair, for the seed-overlay toggle."""
    from nobble.validate.layers import RECOVERY_TARGETS

    rows = [row for row in data.results() if row.get("pair_id") == pair_id]
    target = RECOVERY_TARGETS.get(pair_id, {})
    return jsonify({
        "pair_id": pair_id,
        "crystal": target.get("pdb_id"),
        "structures": [
            {
                "job_id": row["job_id"],
                "complex_type": row.get("complex_type"),
                "conditioning": row.get("conditioning"),
                "seed": row.get("seed"),
                "url": f"/structure/{row['job_id']}.cif",
            }
            for row in rows if row.get("structure")
        ],
    })


@bp.route("/api/ask", methods=["POST"])
def api_ask():
    """Natural-language question to a query object, executed deterministically.

    The model never produces a number: it proposes a query, the executor runs
    it over the scored records, and every figure returned was computed by the
    pipeline. An unconfigured or unreachable model is a normal state.
    """
    from nobble.app import lm as lm_module

    payload = request.get_json(silent=True) or {}
    question = str(payload.get("question") or "").strip()
    if not question:
        return jsonify({"status": "rejected", "explanation": "no question supplied"}), 400
    return jsonify(lm_module.ask(question, data.scores()).to_dict())


@bp.route("/api/schema")
def api_schema():
    """The query schema the model is given. Published so it can be checked."""
    from nobble.app import lm as lm_module

    return jsonify(lm_module.QUERY_SCHEMA)


@bp.route("/healthz")
def healthz():
    state = data.campaign_state()
    return jsonify({"ok": True, "campaign": state["campaign_id"], "jobs_done": state["jobs_done"]})
