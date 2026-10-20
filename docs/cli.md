# Gemini ADK Study Coach — CLI Reference Guide

The `gemini-adk-study-coach` command-line interface provides zero-clone execution, local application management, and environment diagnostics for the Gemini ADK Study Coach.

---

## 1. Installation & Zero-Clone Execution

### Remote Zero-Clone Invocation (Planned Post-PyPI Publication)

> **Notice**: The commands below are planned for availability following official publication to PyPI.

With `uvx` (recommended):
```bash
# Set your Gemini API key
export GEMINI_API_KEY="your-gemini-api-key"

# Launch directly without cloning
uvx gemini-adk-study-coach
```

With `pipx`:
```bash
pipx install gemini-adk-study-coach
gemini-adk-study-coach
```

### Pre-Publication Local Wheel Installation

To validate the packaged distribution prior to PyPI publication:
```bash
# 1. Build distribution wheel
uv build

# 2. Install into isolated tool environment
uv tool install dist/gemini_adk_study_coach-1.1.0-py3-none-any.whl

# 3. Execute
gemini-adk-study-coach --help
gemini-adk-study-coach doctor
gemini-adk-study-coach start
```

---

## 2. Command Reference

### Default Command
Running without arguments starts the bundled Streamlit Study Coach web application on default port 8501:
```bash
gemini-adk-study-coach
```

### `start`
Explicitly launches the Streamlit Study Coach web application:
```bash
gemini-adk-study-coach start [OPTIONS]
```

**Options**:
- `-p, --port <PORT>`: Specify local port (default: `8501`).
- `--address <ADDR>`: Specify network binding address (default: `127.0.0.1`; use `0.0.0.0` for all interfaces).
- `--headless`: Run without automatically opening a browser tab.

**Examples**:
```bash
# Run on default port (8501)
gemini-adk-study-coach start

# Run on a custom port
gemini-adk-study-coach start --port 8502

# Run headless in container or remote server
gemini-adk-study-coach start --port 8501 --headless --address 0.0.0.0
```

### `doctor`
Performs comprehensive diagnostic checks on your environment, verifying:
- Python runtime version ($\ge 3.12$)
- Package installation location and version
- Bundled resources (curriculum YAML, learning catalog, provider registry, UI app, SVG icons)
- Gemini API key configuration (with masked display for privacy)
- Default Gemini model configuration
- Local port availability (8501, 8000, 8500)
- Optional Docker availability (for telemetry stack)

```bash
gemini-adk-study-coach doctor
```

### `version`
Displays installed package version:
```bash
gemini-adk-study-coach version
# Output: gemini-adk-study-coach 1.1.0
```

### `--help`
Displays command-line help and usage:
```bash
gemini-adk-study-coach --help
gemini-adk-study-coach start --help
```

---

## 3. Configuration & Credentials

The CLI supports credential configuration through environment variables or local `.env` files:

| Environment Variable | Description | Default |
| :--- | :--- | :--- |
| `GEMINI_API_KEY` | Primary API key for Google Gemini model inference | *None* |
| `GOOGLE_API_KEY` | Supported alternative alias for Gemini API key | *None* |
| `GEMINI_MODEL` | Target Gemini model name | `gemini-3.8-flash` |
| `OTEL_ENABLED` | Enable/disable OpenTelemetry trace exporter | `true` |

> **Privacy Note**: The CLI never prints raw API keys to stdout or logs. The `doctor` command automatically masks credential strings (e.g., `AIza...XXXX (length: 39)`).

---

## 4. Troubleshooting & FAQ

### Port Conflict Detected
If port 8501 is occupied, the CLI detects the conflict and advises:
```text
Error: Port 8501 is already in use by another process.
Specify a different port using: gemini-adk-study-coach start --port <PORT>
```

### Missing API Key Warning
If neither `GEMINI_API_KEY` nor `GOOGLE_API_KEY` is set, the application starts with a notification. Core UI and static catalog navigation remain active, but AI generation features will prompt for a key.

### Docker Requirement
Docker is **strictly optional**. The core Study Coach application, Google ADK agents, and Streamlit UI run entirely within Python. Docker is only needed if you wish to run the Prometheus, Grafana, and Tempo observability containers.
