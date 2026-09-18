"""Plotly Dash dashboard entry point."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dash import Dash

from config.env import get, load_env
from dashboard.callbacks import register_callbacks
from dashboard.data_loader import DashboardData
from dashboard.layout import build_layout


def create_app() -> Dash:
    load_env()
    data = DashboardData.load()
    app = Dash(
        __name__,
        suppress_callback_exceptions=True,
        assets_folder=str(Path(__file__).resolve().parent / "assets"),
    )
    app.title = "Network Graph Intelligence"
    app.layout = build_layout(data)
    if data.ready:
        register_callbacks(app, data)
    return app


def main() -> int:
    load_env()
    host = get("DASH_HOST", "127.0.0.1") or "127.0.0.1"
    port = int(get("DASH_PORT", "8050") or 8050)
    app = create_app()
    print(f"Dashboard starting at http://{host}:{port}")
    app.run(host=host, port=port, debug=get("DEBUG", "false").lower() == "true")
    return 0


if __name__ == "__main__":
    sys.exit(main())
