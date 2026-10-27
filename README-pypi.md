# Gemini + Google ADK Multi-Agent Study Coach

[![PyPI version](https://img.shields.io/pypi/v/gemini-adk-study-coach-lab.svg)](https://pypi.org/project/gemini-adk-study-coach-lab/)
[![Python versions](https://img.shields.io/pypi/pyversions/gemini-adk-study-coach-lab.svg)](https://pypi.org/project/gemini-adk-study-coach-lab/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://github.com/hastimal/gemini-adk-study-coach-lab/blob/main/LICENSE)
[![Google ADK](https://img.shields.io/badge/Google%20ADK-0.1.0-blue.svg)](https://github.com/google/adk)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.42.0-FF4B4B.svg)](https://streamlit.io/)

Production-grade agentic AI study coach for technical certification preparation, combining **Google Agent Development Kit (ADK)** multi-agent orchestration, **Google Gemini 3.8 Flash**, deterministic Python validation, and an interactive **Streamlit** user interface.

Ground-truth anchored to the **Google Cloud Generative AI Leader** certification curriculum.

---

## Architecture

![Gemini ADK Study Coach Architecture](https://raw.githubusercontent.com/hastimal/gemini-adk-study-coach-lab/main/docs/images/architecture-diagram.png)

*For comprehensive architecture specifications, see the [Architecture Documentation](https://github.com/hastimal/gemini-adk-study-coach-lab/blob/main/docs/architecture.md).*

---

## Quick Start (Zero-Clone)

Run the full interactive application instantly with [`uvx`](https://docs.astral.sh/uv/):

```bash
# Set your Google Gemini API key
export GEMINI_API_KEY="your-gemini-api-key"

# Launch Study Coach immediately in your default browser
uvx gemini-adk-study-coach-lab
```

Or install with [`pipx`](https://pipx.pypa.io/):

```bash
pipx install gemini-adk-study-coach-lab
gemini-adk-study-coach-lab
```

Or install using standard `pip`:

```bash
pip install gemini-adk-study-coach-lab
gemini-adk-study-coach-lab start
```

---

## CLI Commands

The `gemini-adk-study-coach-lab` command-line interface provides utilities for running, diagnosing, and inspecting the application:

```bash
# Verify your local environment and Gemini API credentials
gemini-adk-study-coach-lab doctor

# Start the Streamlit application (default port 8501)
gemini-adk-study-coach-lab start

# Or start on a custom port
gemini-adk-study-coach-lab start --port 8501

# Allow external access (e.g., inside Docker or cloud instances)
gemini-adk-study-coach-lab start --address 0.0.0.0 --port 8501

# Inspect package version
gemini-adk-study-coach-lab version
```

> **Note on Docker**: Docker is completely optional. The full interactive Study Coach runs locally with pure Python. Docker Compose is only needed if you wish to run the local OpenTelemetry, Prometheus, and Grafana telemetry stack.

For full CLI documentation, see [CLI Reference](https://github.com/hastimal/gemini-adk-study-coach-lab/blob/main/docs/cli.md).

---

## Key Capabilities

- **ADK Multi-Agent Orchestration**: A root **Study Coach Coordinator** coordinates three specialist sub-agents using official Google ADK primitives:
  - **Study Planner Agent**: Constructs sequential study schedules adhering strictly to daily time budgets (≤ N min).
  - **Topic Expert Agent**: Delivers structured lessons with beginner/intermediate/advanced depth, architecture diagrams, and runnable Python examples.
  - **Quiz Generator Agent**: Generates 4-choice grounded multiple-choice questions anchored in the curriculum.
- **Deterministic Python Verification**: Scoring, answer evaluation, and time calculations run in 100% pure Python—eliminating LLM hallucination in quantitative grading.
- **Client-Side Answer Masking**: Private answer keys and explanations remain securely on the server until student submission.
- **Adaptive Remediation**: Scoring below 70% automatically triggers weak-topic identification and offers dynamic study plan rebalancing.
- **Curated Learning Resources**: Topic-specific documentation and tutorials featuring 19 vector SVG brand logomarks across technical providers.
- **Enterprise Observability**: Integrated OpenTelemetry tracing (`OTel`), Prometheus metric scrapers, and Grafana dashboard configurations.

---

## Docker & Full Observability Stack (Optional)

> **Docker is completely optional!** The core Study Coach application runs natively without Docker via `uvx` or `pipx`.

If you wish to run the full OpenTelemetry distributed tracing and metrics stack locally:

```bash
# Clone the repository
git clone https://github.com/hastimal/gemini-adk-study-coach-lab.git
cd gemini-adk-study-coach-lab

# Start the observability services (Prometheus, Tempo, Grafana, OTel Collector)
docker compose --profile observability up -d

# Run both the Study Coach UI and Developer Launcher in one command
./scripts/run_local.sh --full-demo
```

Configurable host ports (`HOST_PROMETHEUS_PORT`, `HOST_GRAFANA_PORT`, `HOST_APP_METRICS_PORT`) allow running alongside existing container stacks without port collisions.

---

## Screenshots

### Personalized Study Planner
![Study Coach personalized certification study plan](https://raw.githubusercontent.com/hastimal/gemini-adk-study-coach-lab/main/docs/images/study-coach-personalized-study-plan.png)

### Topic Learning & Formative Quick Check
![Study Coach topic learning and quick knowledge check](https://raw.githubusercontent.com/hastimal/gemini-adk-study-coach-lab/main/docs/images/study-coach-learn-topic-quick-check.png)

### Production Observability Dashboard
![Grafana Study Coach observability dashboard](https://raw.githubusercontent.com/hastimal/gemini-adk-study-coach-lab/main/docs/images/grafana-study-coach-observability-dashboard.png)

---

## Workshop & Documentation Links

- **GitHub Repository**: [https://github.com/hastimal/gemini-adk-study-coach-lab](https://github.com/hastimal/gemini-adk-study-coach-lab)
- **Full Demo Runbook**: [Full Demo Runbook](https://github.com/hastimal/gemini-adk-study-coach-lab/blob/main/docs/workshop/full-demo-runbook.md)
- **Hands-On Workshop Guide**: [Workshop Walkthrough](https://github.com/hastimal/gemini-adk-study-coach-lab/tree/main/docs/workshop)
- **Architecture Deep-Dive**: [Architecture Specifications](https://github.com/hastimal/gemini-adk-study-coach-lab/blob/main/docs/architecture.md)
- **Observability Setup**: [Observability Guide](https://github.com/hastimal/gemini-adk-study-coach-lab/blob/main/docs/observability.md)
- **License**: [MIT License](https://github.com/hastimal/gemini-adk-study-coach-lab/blob/main/LICENSE)
