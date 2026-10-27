"""Launcher service providing unified health checks and links across lab tools."""

import socket
import urllib.error
import urllib.request
from typing import Any

from pydantic import BaseModel


class ServiceEndpoint(BaseModel):
    """Definition and live status of a developer lab service endpoint."""

    id: str
    name: str
    category: str
    description: str
    url: str
    port: int
    health_endpoint: str
    is_online: bool = False
    status_detail: str = "Checking..."
    action_label: str = "Open"
    badge_color: str = "gray"


DEFAULT_SERVICES = [
    {
        "id": "adk_ui",
        "name": "Google ADK Developer UI",
        "category": "Agent Development",
        "description": "Interactive developer playground for conversational debugging, trace logs, and direct agent testing.",
        "url": "http://127.0.0.1:8000",
        "port": 8000,
        "health_endpoint": "http://127.0.0.1:8000/health",
        "action_label": "Open ADK Playground",
    },
    {
        "id": "study_coach",
        "name": "Streamlit Study Coach",
        "category": "Student Experience",
        "description": "Full multi-agent student workshop app: study plan generation, interactive topic learning, and practice quizzes.",
        "url": "http://localhost:8501",
        "port": 8501,
        "health_endpoint": "http://localhost:8501/_stcore/health",
        "action_label": "Open Study Coach",
    },
    {
        "id": "agent_ops",
        "name": "Streamlit Agent Ops",
        "category": "Observability GUI",
        "description": "Live observability dashboard tab inside Study Coach showing Prometheus health and telemetry status.",
        "url": "http://localhost:8501/?tab=ops",
        "port": 8501,
        "health_endpoint": "http://localhost:8501/_stcore/health",
        "action_label": "Open Agent Ops Tab",
    },
    {
        "id": "evaluations",
        "name": "Streamlit Evaluations",
        "category": "Evaluation GUI",
        "description": "Interactive model evaluations tab inside Study Coach with run trigger, pass/fail badges, and latency metrics.",
        "url": "http://localhost:8501/?tab=eval",
        "port": 8501,
        "health_endpoint": "http://localhost:8501/_stcore/health",
        "action_label": "Open Evaluations Tab",
    },
    {
        "id": "grafana",
        "name": "Grafana Dashboard",
        "category": "Metrics & Dashboards",
        "description": "Pre-provisioned dashboard displaying token consumption, agent call rates, latency histograms, and alert panels.",
        "url": "http://localhost:3000/d/study-coach-main/study-coach-lab-observability-telemetry?orgId=1&refresh=5s",
        "port": 3000,
        "health_endpoint": "http://localhost:3000/api/health",
        "action_label": "Open Grafana",
    },
    {
        "id": "tempo",
        "name": "Grafana Tempo Explore",
        "category": "Distributed Tracing",
        "description": "Trace explorer for OpenTelemetry distributed spans, subagent delegation traces, and tool execution waterfalled.",
        "url": "http://localhost:3000/explore?orgId=1&left=%7B%22datasource%22:%22Tempo%22,%22queries%22:%5B%7B%22refId%22:%22A%22%7D%5D%7D",
        "port": 3200,
        "health_endpoint": "http://localhost:3200/ready",
        "action_label": "Open Tempo Traces",
    },
    {
        "id": "prometheus",
        "name": "Prometheus Scraper & TSDB",
        "category": "Time-Series Database",
        "description": "Prometheus target status and metrics time-series explorer for study-coach application telemetry.",
        "url": "http://localhost:9090/targets",
        "port": 9090,
        "health_endpoint": "http://localhost:9090/-/healthy",
        "action_label": "Open Prometheus Targets",
    },
    {
        "id": "app_metrics",
        "name": "Application Metrics Endpoint",
        "category": "Telemetry Exporter",
        "description": "Prometheus metrics scrape target exposed by the Study Coach runtime.",
        "url": "http://localhost:8001/metrics",
        "port": 8001,
        "health_endpoint": "http://localhost:8001/metrics",
        "action_label": "View Raw Metrics",
    },
]


def check_port_listening(host: str, port: int, timeout: float = 0.5) -> bool:
    """Checks whether a TCP socket is listening on the given host and port."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except (OSError, TimeoutError):
        return False


def check_http_endpoint(url: str, timeout: float = 1.0) -> tuple[bool, str]:
    """Checks an HTTP health endpoint. Returns (is_healthy, status_detail)."""
    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "StudyCoach-DeveloperLabLauncher/1.0"},
            method="GET",
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            code = resp.status
            if 200 <= code < 400:
                return True, f"HTTP {code} OK"
            return False, f"HTTP {code}"
    except urllib.error.HTTPError as err:
        if err.code in (200, 301, 302, 307, 308):
            return True, f"HTTP {err.code}"
        return False, f"HTTP {err.code} {err.reason}"
    except (urllib.error.URLError, OSError, TimeoutError) as err:
        return False, f"Unreachable ({err.__class__.__name__})"


def evaluate_service_status(service_dict: dict[str, Any]) -> ServiceEndpoint:
    """Evaluates the actual real-time status of a service endpoint."""
    health_url = service_dict["health_endpoint"]
    port = service_dict["port"]

    is_online, detail = check_http_endpoint(health_url)

    # Fallback to TCP port check if endpoint returned error but port is open
    if not is_online and check_port_listening("127.0.0.1", port):
        # Specific check for ADK UI on port 8000 if /health wasn't available
        is_online = True
        detail = "Port Open (Active)"

    badge_color = "green" if is_online else "red"
    status_detail = "Online" if is_online else "Offline"
    if is_online:
        status_detail = f"Online ({detail})"
    else:
        status_detail = f"Offline ({detail})"

    return ServiceEndpoint(
        id=service_dict["id"],
        name=service_dict["name"],
        category=service_dict["category"],
        description=service_dict["description"],
        url=service_dict["url"],
        port=service_dict["port"],
        health_endpoint=health_url,
        is_online=is_online,
        status_detail=status_detail,
        action_label=service_dict.get("action_label", "Open"),
        badge_color=badge_color,
    )


def get_all_services_status() -> list[ServiceEndpoint]:
    """Evaluates all registered developer lab services."""
    return [evaluate_service_status(s) for s in DEFAULT_SERVICES]
