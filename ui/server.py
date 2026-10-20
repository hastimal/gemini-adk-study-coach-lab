"""Entrypoint for running Study Coach with OpenTelemetry and Prometheus instrumentation."""

import sys
from pathlib import Path

from dotenv import load_dotenv
from streamlit.web import bootstrap

from study_coach.observability import setup_tracing, start_metrics_server


def main() -> None:
    """Initializes observability and starts the Streamlit application server."""
    load_dotenv()
    setup_tracing()
    start_metrics_server()
    app_path = str(Path(__file__).resolve().parent / "app.py")
    bootstrap.run(
        app_path,
        False,
        sys.argv[1:],
        {"server_port": 8501, "server_address": "0.0.0.0"},
    )


if __name__ == "__main__":
    main()
