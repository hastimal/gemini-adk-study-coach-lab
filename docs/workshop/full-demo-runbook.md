# Full Demo Runbook: Gemini ADK Multi-Agent Study Coach

This runbook guides workshop presenters, instructors, and attendees through the end-to-end full demo flow of the **Gemini + Google ADK Multi-Agent Study Coach**.

---

## 1. Quick Reference & Service Port Map

The application ecosystem uses clear, separated ports to ensure Google ADK Web UI, Streamlit, and the optional Docker observability stack run without collisions:

| Component | Default Port | Configurable Env Var | URL | Purpose |
| :--- | :--- | :--- | :--- | :--- |
| **Streamlit Study Coach** | `8501` | `HOST_STREAMLIT_PORT` | `http://localhost:8501` | Main interactive student UI |
| **Google ADK Web UI** | `8000` | `ADK_PORT` | `http://127.0.0.1:8000` | Google ADK Developer Inspector |
| **Developer Lab Launcher** | `8500` | `LAUNCHER_PORT` | `http://localhost:8500` | Central service status and demo launcher |
| **Application Metrics** | `8001` | `HOST_APP_METRICS_PORT` | `http://localhost:8001/metrics` | Prometheus metrics scrape endpoint |
| **Prometheus TSDB** | `9090` | `HOST_PROMETHEUS_PORT` | `http://localhost:9090` | Prometheus metric targets and queries |
| **Grafana Dashboards** | `3000` | `HOST_GRAFANA_PORT` | `http://localhost:3000` | Metrics dashboards and Tempo trace exploration |
| **Grafana Tempo** | `3200` | `HOST_TEMPO_PORT` | `http://localhost:3200` | Distributed trace ingestion and search |
| **OTel Collector (HTTP)** | `4318` | `HOST_OTEL_HTTP_PORT` | `http://localhost:4318` | OpenTelemetry HTTP OTLP receiver |
| **OTel Collector (gRPC)** | `4317` | `HOST_OTEL_GRPC_PORT` | `http://localhost:4317` | OpenTelemetry gRPC OTLP receiver |

---

## 2. Prerequisites & Environment Setup

1. **Python Runtime**: Python 3.12 or newer.
2. **Package Manager**: [`uv`](https://github.com/astral-sh/uv) installed.
3. **Google Gemini API Key**:
   ```bash
   export GEMINI_API_KEY="your-gemini-api-key"
   # or create a local .env file
   echo "GEMINI_API_KEY=your-gemini-api-key" > .env
   ```
4. **Docker Desktop** *(Optional, only needed for Grafana, Tempo, and Prometheus)*:
   - Ensure Docker is running.
   - Note: The core Study Coach application runs independently of Docker!

---

## 3. Starting the Full Demo

### Option A: The One-Command Full Demo (Recommended for Presenters)

To launch the background services, Docker observability stack, and interactive UIs:

```bash
# 1. Start Docker observability services (if Docker is available)
docker compose --profile observability up -d

# 2. Launch Streamlit Study Coach and the Developer Lab Launcher
./scripts/run_local.sh --full-demo
```

### Option B: Zero-Clone Runner (For Quick Attendee Testing)

Attendees who do not wish to clone the git repository can run the published package instantly with `uvx`:

```bash
# Verify environment and dependencies
uvx gemini-adk-study-coach-lab doctor

# Launch the interactive Study Coach directly
uvx gemini-adk-study-coach-lab start
```

---

## 4. The 15-Minute Workshop Demo Sequence

### Step 1: Initial Health & Diagnostics (Minute 0–2)
1. Open the **Developer Lab Launcher** at `http://localhost:8500`.
2. Verify all service indicators:
   - Streamlit Study Coach: `ONLINE` (Port 8501)
   - Application Metrics: `ONLINE` (Port 8001)
   - Prometheus / Grafana / Tempo: `ONLINE` (Ports 9090, 3000, 3200)
3. Click **Launch Study Coach** or open `http://localhost:8501`.

### Step 2: Personalized Study Planning (Minute 2–5)
1. In the sidebar, select:
   - **Certification**: `Google Cloud Generative AI Leader`
   - **Experience Level**: `Beginner`
   - **Days until Exam**: `14`
   - **Daily Study Minutes**: `90`
2. Click **Start / Reset Session**, then navigate to **Tab 1: 📅 Study Plan**.
3. Click **Generate Initial Plan**.
4. **Talking Point**: Point out that the ADK Study Planner agent uses structured JSON outputs validated against strict Pydantic models. Show that the daily study ceiling (90 min) is mathematically enforced in pure Python without hallucinated over-allocation.

### Step 3: Deep Topic Explanation & Knowledge Check (Minute 5–8)
1. Navigate to **Tab 2: 📖 Learn Topic**.
2. Select Topic: `genai_concepts` (Generative AI Concepts) and click **Teach This Topic**.
3. Inspect the sub-tabs:
   - **Architecture Diagram**: Inspect the rendered Mermaid diagram.
   - **Step-by-Step Lesson**: Real-world GCP scenario (Cymbal Retail).
   - **Hands-On Python**: Runnable Vertex AI / Gemini API snippets.
   - **Verified Resources**: Resource cards with official provider logos.
4. Go to **Practice & Share** and take the 3-question **Quick Knowledge Check**. Submit answers to demonstrate instant, deterministic scoring.

### Step 4: Practice Quiz & Adaptive Replanning (Minute 8–11)
1. Click **Launch Formal Practice Quiz** (or switch to **Tab 3: 📝 Practice Quiz**).
2. Generate a 5-question quiz on `genai_concepts`.
3. Intentionally answer 3 questions incorrectly and submit.
4. Review the diagnostic breakdown: Score is 40.0% (< 70%), automatically diagnosing `genai_concepts` as a **Weak Topic**.
5. Switch to **Tab 4: 🔄 Adaptive Plan**:
   - Set **Completed Days**: `1`.
   - Click **Generate Adapted Plan**.
   - **Talking Point**: Observe how the agent reschedules the remaining 13 days to prioritize revision blocks for `genai_concepts` while strictly respecting the 90-minute daily budget.

### Step 5: Distributed Traces & Metrics in Grafana (Minute 11–15)
1. Switch to **Tab 5: 🔭 Agent Ops** inside Streamlit.
2. Click **Open Grafana Dashboard** (`http://localhost:3000`).
3. Show the **Study Coach Workshop Observability** dashboard:
   - Total requests counter incrementing.
   - Agent call breakdown (`study_planner`, `topic_expert`, `quiz_generator`).
   - Latency histograms and tool execution distributions.
4. Click **Explore Traces in Tempo** (`http://localhost:3000/explore`):
   - Select the **Tempo** datasource.
   - Search for recent traces or paste a trace ID.
   - Expand the trace span waterfall showing:
     `study_coach.create_initial_plan` -> `adk.agent.study_planner` -> `call_llm` -> `generate_content gemini-3.8-flash` -> `execute_tool`.
   - Show how sensitive credentials (`[REDACTED_API_KEY]`) are safeguarded across all spans.

---

## 5. Troubleshooting & Clean Shutdown

### Port Conflicts
- If port `9090` or `3000` is already in use by another local project, configure alternative host ports in `.env`:
  ```bash
  HOST_PROMETHEUS_PORT=9091
  HOST_GRAFANA_PORT=3001
  HOST_APP_METRICS_PORT=8002
  ```
  Then restart Docker: `docker compose --profile observability up -d`.

### Streamlit Showing Offline
- Verify that `ui/server.py` is running on port 8501:
  ```bash
  curl -I http://localhost:8501/_stcore/health
  ```
- If port 8501 is occupied by an old process, terminate it cleanly:
  ```bash
  lsof -ti:8501 | xargs kill -9
  ```

### Clean Shutdown
To safely shut down the demo environment without deleting any persistent Docker volumes:
```bash
# Stop background Python processes (handled automatically if using Ctrl+C on run_local.sh)
pkill -f "streamlit run ui" || true

# Stop Docker observability containers cleanly (preserves volumes)
docker compose --profile observability stop
```
