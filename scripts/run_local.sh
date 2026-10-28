#!/usr/bin/env bash
set -e

# Default ports
LAUNCHER_PORT="${LAUNCHER_PORT:-8500}"
APP_PORT="${APP_PORT:-8501}"
ADK_PORT="${ADK_PORT:-8000}"

# Help message
if [ "$1" = "--help" ] || [ "$1" = "-h" ]; then
    echo "Usage: ./scripts/run_local.sh [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  --launcher          Launch the Developer Lab Launcher GUI (default, port 8500)"
    echo "  --full-demo         Start both Streamlit Study Coach (8501) and Developer Launcher (8500)"
    echo "  --app-only          Launch only the Streamlit Study Coach UI (port 8501)"
    echo "  --adk-only          Launch only the standalone Google ADK Developer UI (port 8000)"
    echo "  --port <PORT>       Specify a custom port for the launcher (default: 8500)"
    echo "  -h, --help          Show this help message"
    echo ""
    echo "Examples:"
    echo "  ./scripts/run_local.sh               # Starts Developer Lab Launcher at http://localhost:8500"
    echo "  ./scripts/run_local.sh --full-demo   # Starts Study Coach (8501) + Launcher (8500)"
    echo "  ./scripts/run_local.sh --app-only    # Starts Study Coach UI directly at http://localhost:8501"
    echo "  ./scripts/run_local.sh --adk-only    # Starts Google ADK Developer UI directly at http://127.0.0.1:8000"
    exit 0
fi

# ADK-only standalone workflow
if [ "$1" = "--adk-only" ]; then
    echo "Starting Google ADK Developer UI on port ${ADK_PORT}..."
    exec uv run adk web --port "${ADK_PORT}"
fi

# App-only standalone workflow
if [ "$1" = "--app-only" ]; then
    echo "Starting Streamlit Study Coach on port ${APP_PORT}..."
    exec uv run streamlit run ui/app.py --server.port "${APP_PORT}"
fi

# Full-demo workflow: launches Study Coach in background, then Launcher in foreground
if [ "$1" = "--full-demo" ]; then
    echo "================================================================================"
    echo "🚀 STARTING FULL GEMINI ADK STUDY COACH DEMO LAB"
    echo "================================================================================"
    
    # Check if Study Coach is already running on APP_PORT
    if lsof -Pi :${APP_PORT} -sTCP:LISTEN -t >/dev/null 2>&1 ; then
        echo "ℹ️  Streamlit Study Coach is already listening on port ${APP_PORT}."
    else
        echo "Starting Streamlit Study Coach (port ${APP_PORT}) in background..."
        uv run streamlit run ui/app.py --server.port "${APP_PORT}" --server.headless true &
        STUDY_COACH_PID=$!
        trap "echo 'Stopping background Study Coach...'; kill ${STUDY_COACH_PID} 2>/dev/null || true" EXIT INT TERM
        
        # Wait briefly for startup
        sleep 2
    fi
    
    echo "Starting Developer Lab Launcher (port ${LAUNCHER_PORT})..."
    exec uv run streamlit run ui/launcher_app.py --server.port "${LAUNCHER_PORT}" --server.headless true
fi

# Parse custom port if provided
if [ "$1" = "--port" ] && [ -n "$2" ]; then
    LAUNCHER_PORT="$2"
fi

echo "================================================================================"
echo "🚀 STARTING GEMINI ADK DEVELOPER LAB LAUNCHER"
echo "================================================================================"
echo "Launcher URL: http://localhost:${LAUNCHER_PORT}"
echo ""
echo "From this launcher GUI, you can access and monitor:"
echo "  1. Google ADK Developer UI       (http://127.0.0.1:8000)"
echo "  2. Streamlit Study Coach         (http://localhost:8501)"
echo "  3. Streamlit Agent Ops Tab       (http://localhost:8501/?tab=ops)"
echo "  4. Streamlit Evaluations Tab     (http://localhost:8501/?tab=eval)"
echo "  5. Application Metrics Scrape    (http://localhost:8001/metrics)"
echo "  6. Grafana Dashboard             (http://localhost:3000)"
echo "  7. Grafana Tempo Explore         (http://localhost:3000/explore)"
echo "  8. Prometheus Scraper & TSDB     (http://localhost:9090)"
echo ""
echo "Tip: For full one-command startup of both app and launcher, run:"
echo "      ./scripts/run_local.sh --full-demo"
echo "================================================================================"

exec uv run streamlit run ui/launcher_app.py --server.port "${LAUNCHER_PORT}" --server.headless true
