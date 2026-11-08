"""Routes for the seven tabs, plus the JSON endpoints the pages read.

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

from nobble import sampling
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
    pairs = data.scores_for_pages()
    return render_template(
        "campaign.html",
        page_title="Campaign",
        active="campaign",
        pairs=pairs,
        # The arms the payload actually carries, for the ledger's Tier
        # facet. Offered `benchmark`, `A` and `B` and compared against
        # `row["tier"]`, which holds the arm and never a curation tier, so
        # `A` and `B` matched nothing on the live site and `sievers_zf`,
        # `scramble` and `design` could not be selected at all (F191).
        #
        # Derived here rather than in Jinja: `map(attribute='tier')` yields
        # Undefined for a row without the key and `reject('none')` does not
        # filter that, so a sparse row would put an empty option in the list.
        tiers=sorted({row["tier"] for row in pairs if row.get("tier")}),
        components=data.COMPONENTS,
        meta=data.campaign_meta(),
        throughput=data.throughput(),
        weight_fit=data.weight_fit(),
        lm_available=_lm_available(),
        # One definition of how a UI component key maps to the fitter's name
        # for it, read by the Jinja that renders each slider's initial value
        # and by the JavaScript that sets it (F106).
        fitted_aliases=data.FITTED_ALIASES,
        fitted_weight=data.fitted_weight,
        component_auc=data.component_auc,
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
    # The ROC panel refuses below the same floor the Python layer refuses
    # below, and the floor is passed in rather than written twice. Its own
    # comment says "this filter and the Python one have to agree, because the
    # figure here and the number in the validation report are supposed to be
    # the same curve", and F28 moved the Python side to thresholds.toml
    # without noticing the literal in the template (F54).
    from nobble import paths

    # The Python layer's own verdict, beside the curve it is about (F159).
    #
    # The chart title carries an AUC the page computes in JavaScript, and the
    # interval and the interpretation existed only in `validation.json`,
    # rendered on the About tab. So a reader looking at the curve saw a
    # single number and had to infer what it meant. That matters most in the
    # case spec 4.3 asks to be reported rather than hidden: an interval
    # entirely below 0.5, where the statistic separates the two classes in
    # the opposite direction to the prediction. F120 wrote that sentence and
    # nothing put it next to the figure.
    roc = ((data.precomputed("validation.json").get("layers") or {})
           .get("matched_control_roc") or {})
    return render_template(
        "delta.html", page_title="Delta", active="delta",
        pairs=data.scores_for_pages(), components=data.COMPONENTS,
        roc_summary=roc.get("summary") or {},
        roc_status=roc.get("status") or "",
        roc_minimum_per_side=int(
            paths.thresholds()["validation"]["roc_minimum_per_side"]
        ),
    )


@bp.route("/benchmark")
def benchmark():
    # Read the precomputed members rather than importing the curation stack:
    # the droplet has no gemmi and this route used to 500 there. Locally the
    # atlas may be absent, so fall back to computing it.
    precomputed = data.precomputed("benchmark.json")
    if precomputed.get("members"):
        member_list = precomputed["members"]
    else:
        from nobble.curate import peptides as peptide_module
        member_list = [dict(item) for item in peptide_module.BENCHMARK_CHAINS]

    members = {
        f"bench{item['index']:02d}_{item['gene']}_{item['e3']}": item
        for item in member_list
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
    # The time split is carried even when the layer is not_computed, which is
    # the case that matters: it is not_computed precisely when every target
    # predates the training cutoff, and that is what the recovery numbers need
    # said about them.
    validation = data.precomputed("validation.json")
    time_split = (
        ((validation.get("layers") or {}).get("time_split") or {}).get("summary") or {}
    )

    # The chart's first colour band is the success-rate curve's last
    # breakpoint, which its own comment says it is "banded on". It was a
    # literal 5 beside a configured [1, 2, 3, 5], so a changed breakpoint
    # would have left the chart colouring recovered what the curve no longer
    # counted (F55). The near-miss bands past it are the chart's own.
    from nobble import paths

    breakpoints = paths.thresholds()["scoring"]["rmsd_breakpoints"]

    return render_template(
        "benchmark.html", page_title="Benchmark", active="benchmark",
        cards=cards, meta=data.campaign_meta(),
        comparison=data.precomputed("comparison.json"),
        recovery_vs_bridge=data.precomputed("recovery_vs_bridge.json"),
        time_split=time_split,
        rmsd_recovered_a=float(max(breakpoints)),
        significance_alpha=float(
            paths.thresholds()["scoring"]["significance_alpha"]
        ),
    )


@bp.route("/design")
def design():
    # Read the precomputed document, exactly as /benchmark does. The fallback
    # imports the generator, which pulls in the curation stack, so it is
    # guarded: the droplet always has the atlas and never reaches it, while
    # locally the atlas may be absent. Two routes have already returned 500
    # in production by importing that stack unconditionally.
    document = data.precomputed("design.json")
    if not document.get("parents"):
        from nobble.design import report as design_report
        document = design_report.build()

    # Switching parent reads the precomputed previews rather than generating
    # on request: the droplet has no curation stack, and a route that works
    # locally and 500s in production has already happened twice here.
    wanted = request.args.get("parent")
    if wanted:
        chosen = (document.get("previews") or {}).get(wanted)
        if chosen:
            document = dict(document)
            document["preview"] = chosen
            # The scan profile belongs to whichever parent was actually
            # scored. Showing it beside a different parent's variants would
            # caption one degron's result with another's sequence.
            scored_parent = (document.get("lifts") or {}).get("parent")
            if scored_parent != wanted:
                document["profile"] = {}
    return render_template(
        "design.html", page_title="Design", active="design",
        design=document,
        # Computed after the parent switch above, because that switch can
        # blank the profile, and a heading claiming a scan the table does
        # not show is the defect this closes (F206).
        scan=data.scan_state(document),
    )


@bp.route("/about")
def about():
    # As for /benchmark: precomputed first, live computation only as a local
    # fallback. Importing nobble.curate here is what made this route 500 on the
    # droplet while passing every local check.
    precomputed = data.precomputed("about.json")
    if not precomputed:
        from nobble.curate import binman_store, constructs
        from nobble.score import lysine

        precomputed = {
            "sources": binman_store.available(),
            "unavailable": list(binman_store.UNAVAILABLE),
            "bridge_reference": binman_store.bridge_reference_count(),
            "construct_budget": constructs.budget_report(),
            "reach_auc": lysine.BINMAN_REACH_AUC,
        }

    return render_template(
        "about.html", page_title="About", active="about",
        sources=precomputed.get("sources", {}),
        unavailable=precomputed.get("unavailable", []),
        bridge_reference=precomputed.get("bridge_reference", 0),
        construct_budget=precomputed.get("construct_budget", []),
        reach_auc=precomputed.get("reach_auc", {}),
        # The bridging filter against deposited coordinates (F297). Absent
        # from a bundle built before it existed, and the panel then says so
        # rather than rendering an empty table as a clean result.
        crystal_control=precomputed.get("crystal_control"),
        # The paired parent-versus-scramble test (F316). Absent from a
        # bundle built before it existed, and the panel says so.
        paired_scrambles=precomputed.get("paired_scrambles"),
        # The same matched arm, analysed as the matched design it is (F317).
        matched_blocks=precomputed.get("matched_blocks"),
        # What sample counts produced the published numbers, per tier
        # (F337). A statement of what ran rather than a caveat on a
        # figure: `nobble/sampling.py` withholds every quantity a sample
        # count would bias, so nothing on these pages needs defending. It
        # is here because the scorer computed it, nothing published it, and
        # a reader cannot otherwise tell that two pairs' refinements were
        # drawn from different numbers of poses. Absent from a bundle built
        # before it existed, and the line then says so.
        sampling=precomputed.get("sampling"),
        crystal_counts=data.crystal_control_counts(
            precomputed.get("crystal_control")),
        weight_fit=data.weight_fit(),
        validation=data.precomputed("validation.json"),
        # Each component's matched-arm curve, keyed by component, so the
        # composite table can put it beside that component's in-sample
        # standalone AUC. Computed by the validation layer and carried in
        # validation.json; an older bundle has no such key and the template
        # renders the column as not computed (F287).
        arm_curves={
            row.get("component"): row
            for row in ((((data.precomputed("validation.json").get("layers")
                           or {}).get("matched_control_roc") or {})
                         .get("summary") or {}).get("component_curves") or [])
        },
        throughput=data.throughput(),
        components=data.COMPONENTS,
        # Which Boltz produced the coordinates. Read from the published
        # campaign record rather than measured here: the droplet's
        # environment is not the one that ran the jobs, so measuring on the
        # server would report the wrong thing confidently (F185).
        software=(data.campaign_meta() or {}).get("software") or {},
        # The depositions the bundle redistributes, named on the page that
        # records where things come from. PDB content is CC0 so nothing is
        # required, and the viewer already labels each overlay "deposited
        # <id>", but the bundle began carrying seven assemblies in F196 and
        # this page credits every other source it draws on (F197).
        # Read from the bundle rather than from the mapping. The mapping
        # says which deposition a pair refers to; this panel says which
        # files are redistributed, and they differ when an assembly is
        # missing from the cache, in which case build_atlas warns and
        # publishes nothing for it. Crediting a structure the bundle does
        # not carry would be the wrong claim. Deduplicated because two
        # pairs may name one deposition: BRD4 appears twice here, on VHL
        # and on CRBN.
        crystals=sorted(
            path.name[: -len(".cif.gz")]
            for path in ((data.campaign_dir() or Path(".")) / "crystals").glob("*.cif.gz")
        ),
    )


# --------------------------------------------------------------------------- #
# JSON endpoints
# --------------------------------------------------------------------------- #

@bp.route("/api/pairs")
def api_pairs():
    """Every scored pair, whole. Deliberately unbounded (F176).

    The two consumers that render a few fields from a record set are
    bounded: the campaign and Delta pages drop the per-seed detail they
    never read, and an `/api/ask` answer defaults to the published schema.
    This one is the full-fidelity export, 3.1 MB at campaign scale, and it
    stays that way. The client never calls it, and a bulk route that
    quietly truncated would be worse than a large one.
    """
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

    # Both tiers. The catalogue offers refined poses, so serving tier 1
    # alone would hand the viewer a URL that 404s for every structure tier
    # 2 produced: the refinement would be listed and unopenable, which is
    # worse than not listing it.
    for row in [*data.results(), *data.results_tier2()]:
        if row.get("job_id") != job_id:
            continue
        path = row.get("structure")
        if not path:
            abort(404, description="no structure recorded for this job")
        campaign = data.campaign_dir()
        if campaign is None:
            abort(404, description="no campaign configured")
        # A published atlas records paths relative to itself; a local campaign
        # records absolute ones. Both are resolved against the campaign
        # directory and then checked to be inside it, so neither form can
        # escape.
        candidate = Path(path)
        resolved = (candidate if candidate.is_absolute() else campaign / candidate).resolve()
        if not str(resolved).startswith(str(campaign.resolve())):
            abort(404, description="structure is outside the campaign directory")
        if not resolved.exists():
            abort(404, description="structure file is missing")
        return Response(resolved.read_text(), mimetype="chemical/x-mmcif")
    abort(404, description=f"no completed job {job_id}")


@bp.route("/crystal/<pdb_id>.cif")
def crystal(pdb_id: str):
    """Serve a deposited assembly from BINMAN's cache, for superposition."""
    import gzip

    from flask import Response

    if not pdb_id.isalnum() or len(pdb_id) != 4:
        abort(404, description="not a PDB identifier")

    # From the published bundle, never from BINMAN's cache. This imported
    # `nobble.curate.structures`, which imports gemmi at module level, and
    # the droplet's virtualenv holds flask and gunicorn: the route returned
    # 500 there for every pair while passing every local check, and
    # `pose.html` loads it to superpose a prediction on its crystal. Four
    # sibling routes already import that stack only behind `if not
    # precomputed`, and two of them carry comments saying why (F196).
    campaign = data.campaign_dir()
    path = (campaign / "crystals" / f"{pdb_id}.cif.gz") if campaign else None
    if path is None or not path.exists():
        abort(404, description=f"{pdb_id} is not in the published bundle")

    # The stored gzip, when the client will take it: 6H0F is 965 KB
    # compressed against the 4,127,262 bytes it expands to. A client that
    # sends no Accept-Encoding gets it expanded, which is not hypothetical,
    # since plain curl sends none and that is how the 500 was found.
    if request.accept_encodings["gzip"]:
        return Response(path.read_bytes(), mimetype="chemical/x-mmcif",
                        headers={"Content-Encoding": "gzip"})
    with gzip.open(path, "rt", errors="replace") as handle:
        return Response(handle.read(), mimetype="chemical/x-mmcif")


@bp.route("/api/pair/<pair_id>/structures")
def api_pair_structures(pair_id: str):
    """Every completed structure for a pair, for the seed-overlay toggle.

    404 on a pair the campaign has no record of. This returned 200 with
    `{"pair_id": "nope", "crystal": null, "structures": []}`, asserting that
    a pair exists and produced nothing, and those are two different states:
    a pair whose jobs all failed is a real and visible outcome, and the
    viewer would have rendered one for a pair that does not exist (F122).

    Existence is judged on the campaign's *results*, not on `data.scores()`
    the way the sibling `/api/pair/<pair_id>` does, and the difference
    matters. Scoring runs after the campaign, so for the whole length of a
    run every completed pair is in `results.jsonl` and none are in
    `scores.jsonl`. Using the sibling's check here 404s every pair while the
    campaign is still going, which is exactly when the viewer is used. The
    tier-2 catalogue tests caught that within a minute of my writing it.
    """
    known = {row.get("pair_id") for row in data.results()}
    known |= {row.get("pair_id") for row in data.results_tier2()}
    if known and pair_id not in known:
        abort(404, description=f"no pair {pair_id} in this campaign")

    # Read the crystal mapping from the atlas rather than importing
    # nobble.validate, which pulls in gemmi. This endpoint feeds the Pose
    # viewer, so importing the scoring stack here would have left the viewer
    # unable to load any structure on the droplet.
    crystal_map = data.precomputed("benchmark.json").get("crystal_by_pair") or {}
    if not crystal_map:
        try:
            from nobble.validate.layers import RECOVERY_TARGETS
            crystal_map = {k: v["pdb_id"] for k, v in RECOVERY_TARGETS.items()}
        except Exception:                           # noqa: BLE001
            crystal_map = {}

    # Tier 1 and, where it has run, tier 2. The refined pose is the whole
    # product of a refinement run, and the viewer is the only place it can
    # be read: without this the catalogue offers the coarse pose only and
    # the refinement may as well not have happened. Marked, not merged:
    # they were sampled differently and are not interchangeable
    # (D-NOB-032).
    rows = [(row, 1) for row in data.results() if row.get("pair_id") == pair_id]
    rows += [(row, 2) for row in data.results_tier2() if row.get("pair_id") == pair_id]

    # What the refined pose measured, beside what the coarse one did. Only
    # the quantities whose shape survives a change of sample count: a
    # minimum over seeds falls as samples are added, so showing one here
    # would present arithmetic as an improvement (`nobble.sampling`).
    refined = next((row for row in data.scores_tier2()
                    if row.get("pair_id") == pair_id), None)
    coarse = next((row for row in data.scores()
                   if row.get("pair_id") == pair_id), None)
    refinement = sampling.compare(coarse, refined) if refined else None
    if refinement:
        # A label per row, so the panel reads "Bridge percentile" rather
        # than "bridge_percentile". Rendered for the first time in this
        # session, with tier-2 data, and it showed raw field names where
        # every other table on the site shows labels (F203).
        #
        # Taken from `data.COMPONENTS`, which is where the site's labels
        # live, rather than adding a second list to `nobble/sampling.py`:
        # three of the four keys are already labelled there, and a parallel
        # list is the duplication F181, F183 and F187 were each about. The
        # fourth, `bridge_formation_rate`, has no entry because it is not a
        # composite component, so it falls back to its key with the
        # underscores opened out rather than inventing a label here that
        # would then disagree with the one in campaign.html's header.
        for row in refinement.get("rows", []):
            meta = data.COMPONENTS.get(row.get("key")) or {}
            fallback = str(row.get("key", "")).replace("_", " ")
            # Capitalised to sit beside the three that are labelled, which
            # is a mechanical transformation of the key rather than a name
            # invented here. The ledger's own header abbreviates this same
            # quantity to "Bridge rate", so the two differ: the row's
            # tooltip carries `what`, "proportion of seeds whose glue
            # bridged both chains", which is the thing that identifies it.
            row["label"] = meta.get("label") or (fallback[:1].upper() + fallback[1:])

    return jsonify({
        "pair_id": pair_id,
        "crystal": crystal_map.get(pair_id),
        "refinement": refinement,
        "structures": [
            {
                "job_id": row["job_id"],
                "complex_type": row.get("complex_type"),
                "conditioning": row.get("conditioning"),
                "seed": row.get("seed"),
                "sampling_tier": tier,
                "label": "refined" if tier == 2 else "tier 1",
                "url": f"/structure/{row['job_id']}.cif",
            }
            for row, tier in rows if row.get("structure")
        ],
    })


def _lm_available() -> bool:
    """Whether a question can be asked at all.

    Asked at render time rather than left to the browser, so the panel says
    what it can do before anyone types into it. An unconfigured model is a
    normal state: the droplet serves a precomputed atlas and has no model
    behind it at all.
    """
    try:
        from nobble.app import lm as lm_module

        return bool(lm_module.available())
    except Exception:                       # noqa: BLE001
        return False


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


@bp.route("/api/status")
def api_status():
    return jsonify(data.site_status())


@bp.route("/healthz")
def healthz():
    """Liveness, plus which build is answering.

    The fingerprint is here and not in `site_status` because it is for a
    harness rather than a reader: browser QC drives a live server and used to
    have no way of telling whether that server was the working tree. One run
    reported 14 clean pages against a process started hours earlier, for a
    change that was not in it (F138).
    """
    from nobble.app import fingerprint

    state = data.campaign_state()
    return jsonify({
        "ok": True,
        "campaign": state["campaign_id"],
        "jobs_done": state["jobs_done"],
        "source_fingerprint": fingerprint.fingerprint(),
    })
