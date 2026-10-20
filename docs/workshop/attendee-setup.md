# Workshop Attendee Setup Guide

This guide gets you completely set up to participate in the **Gemini + Google ADK Multi-Agent Study Coach** workshop across **macOS, Linux, and Windows**.

---

## 1. System Prerequisites

| Tool | Version | Purpose | Installation Link |
| :--- | :--- | :--- | :--- |
| **Python** | 3.12+ | Core runtime | [python.org](https://www.python.org/downloads/) |
| **uv** | Latest | Fast Python package & environment manager | [astral.sh/uv](https://docs.astral.sh/uv/getting-started/installation/) |
| **Git** | 2.30+ | Source version control | [git-scm.com](https://git-scm.com/) |
| **Gemini API Key** | Free tier | LLM model inference | [Google AI Studio](https://aistudio.google.com/) |
| **Docker Desktop** *(Optional)* | Recent | Running Grafana/Tempo observability stack | [docker.com](https://www.docker.com/products/docker-desktop/) |

> **Note on Docker**: Docker is **100% optional**. The core Study Coach learning application runs natively with pure Python. Docker is only needed if you wish to run the full local Grafana/Prometheus/Tempo telemetry cluster.

---

## 2. Platform Installation Instructions

### macOS & Linux

1. Install `uv` (recommended):
   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```
2. Verify Python and uv:
   ```bash
   uv --version
   python3 --version
   ```

### Windows (PowerShell)

1. Install `uv`:
   ```powershell
   powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
   ```
2. Ensure `uv` is in your environment PATH, then open a new PowerShell window:
   ```powershell
   uv --version
   ```

---

## 3. Workshop Launch Options

### Option A: Zero-Clone Execution via `uvx` (PyPI)

📦 **PyPI Package**: [https://pypi.org/project/gemini-adk-study-coach-lab/](https://pypi.org/project/gemini-adk-study-coach-lab/)

```bash
# Configure API Key
export GEMINI_API_KEY="your-gemini-api-key"

# Run immediately without cloning repository
uvx gemini-adk-study-coach-lab
```

For pre-publication local wheel testing:
```bash
uv tool install dist/gemini_adk_study_coach_lab-*.whl
gemini-adk-study-coach-lab doctor
gemini-adk-study-coach-lab start
```

### Option B: Clone and Developer Environment Setup (From Source)

1. Clone the repository:
   ```bash
   git clone https://github.com/hastimal/gemini-adk-study-coach-lab.git
   cd gemini-adk-study-coach-lab
   ```

2. Synchronize project dependencies into an isolated virtual environment:
   ```bash
   uv sync
   ```

3. Configure your API credentials:
   ```bash
   cp .env.example .env
   ```

4. Edit `.env` with your preferred editor and insert your Gemini API Key:
   ```env
   GOOGLE_GENAI_USE_VERTEXAI=FALSE
   GOOGLE_API_KEY=AIzaSy...your_actual_key_here...
   GEMINI_MODEL=gemini-3.8-flash
   ```

> **Security Reminder**: Never commit your `.env` file or share your API key. The `.gitignore` is preconfigured to ignore `.env`.

---

## 4. Run the Verification Tests

Confirm your environment passes all deterministic unit tests before the workshop:

```bash
uv run pytest -q
```

Expected output:
```text
........................................................................ [ 46%]
........................................................................ [ 92%]
............                                                             [100%]
156 passed in 3.14s
```

---

## 5. Starting the Application

### Option 1: Native Streamlit Workshop UI (Primary Workshop Mode)

```bash
uv run streamlit run ui/app.py
```

Open your browser to:
👉 **http://localhost:8501**

### Option 2: Unified Developer Lab Launcher

If you want a single navigation dashboard to open all lab components:

```bash
./scripts/run_local.sh
```

Access launcher at:
👉 **http://localhost:8500**

### Option 3: Optional Docker Observability Stack (Advanced)

If Docker Desktop is installed and you want live metrics and traces:

```bash
# Start observability cluster
docker compose --profile observability up -d --build

# Verify healthy containers
docker compose --profile observability ps
```

Services exposed:
- **Streamlit UI**: `http://localhost:8501`
- **Grafana Dashboard**: `http://localhost:3000` (User/Pass: `admin` / `admin`)
- **Tempo Trace Explorer**: `http://localhost:3000/explore`
- **Prometheus TSDB**: `http://localhost:9090`
- **Application Metrics**: `http://localhost:8000/metrics`

To stop containers safely:
```bash
docker compose --profile observability down
```

---

## 6. Port Architecture Reference

To avoid port conflicts during the workshop, understand the configured ports:

| Port | Service | Notes |
| :--- | :--- | :--- |
| **8501** | Streamlit Study Coach Web UI | Main student interactive interface |
| **8500** | Developer Lab Launcher | One-click launcher dashboard |
| **8000** | Prometheus Metrics / ADK Web | Application metrics (or standalone `adk web`) |
| **3000** | Grafana | Pre-provisioned dashboards & Tempo Explorer |
| **9090** | Prometheus | Scraper & time-series database |
| **3200** | Grafana Tempo | Distributed trace backend |
| **4317 / 4318** | OpenTelemetry Collector | gRPC and HTTP OTLP receiver ports |
