"""Phase 4: the NOBBLE Flask application.

Six tabs over one campaign, sharing a single pinned selection, built on the
Depot design system inherited from BINMAN (spec Phase 4). NOBBLE is served as a
fifth BINMAN module, so the stylesheet and the vendored Mol*, Plotly, D3 and
Tabulator builds are BINMAN's, pinned, not a second set of choices.
"""
from __future__ import annotations

from flask import Flask


def create_app(campaign: str | None = None) -> Flask:
    app = Flask(__name__, static_folder="static", template_folder="templates")
    app.config["CAMPAIGN"] = campaign

    from nobble.app import data as data_module
    from nobble.app.routes import bp

    data_module.configure(campaign)
    app.register_blueprint(bp)

    @app.context_processor
    def inject_globals() -> dict:
        state = data_module.campaign_state()
        return {
            "campaign_state": state,
            "tabs": [
                ("campaign", "Campaign", "The pair ledger"),
                ("pose", "Pose", "Predicted ternary in 3D"),
                ("interactions", "Interactions", "PLIP contact map"),
                ("delta", "Delta", "Glue dependence and the ROC"),
                ("benchmark", "Benchmark", "The seven panel members"),
                ("about", "About", "Pipeline, references and caveats"),
            ],
        }

    return app
