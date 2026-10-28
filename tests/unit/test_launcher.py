"""Unit tests for the Developer Lab Launcher service and app."""

from pathlib import Path
from unittest.mock import MagicMock, patch

from streamlit.testing.v1 import AppTest

from study_coach.services.launcher import (
    DEFAULT_SERVICES,
    check_http_endpoint,
    check_port_listening,
    evaluate_service_status,
    get_all_services_status,
)


def test_default_services_configuration() -> None:
    """Verifies that all 8 required developer lab services are defined."""
    ids = [s["id"] for s in DEFAULT_SERVICES]
    assert "adk_ui" in ids
    assert "study_coach" in ids
    assert "agent_ops" in ids
    assert "evaluations" in ids
    assert "grafana" in ids
    assert "tempo" in ids
    assert "prometheus" in ids
    assert "app_metrics" in ids

    # Check direct query param navigation URLs
    ops_svc = next(s for s in DEFAULT_SERVICES if s["id"] == "agent_ops")
    assert "?tab=ops" in str(ops_svc["url"])

    eval_svc = next(s for s in DEFAULT_SERVICES if s["id"] == "evaluations")
    assert "?tab=eval" in str(eval_svc["url"])


def test_check_http_endpoint_success() -> None:
    """Verifies check_http_endpoint returns True on 200 OK."""
    mock_resp = MagicMock()
    mock_resp.status = 200
    mock_resp.__enter__.return_value = mock_resp

    with patch("urllib.request.urlopen", return_value=mock_resp):
        is_healthy, detail = check_http_endpoint("http://example.com/health")
        assert is_healthy is True
        assert "HTTP 200" in detail


def test_check_http_endpoint_failure() -> None:
    """Verifies check_http_endpoint returns False on connection error."""
    with patch("urllib.request.urlopen", side_effect=OSError("Connection failed")):
        is_healthy, detail = check_http_endpoint("http://example.com/health")
        assert is_healthy is False
        assert "Unreachable" in detail


def test_check_port_listening() -> None:
    """Verifies check_port_listening detects open sockets."""
    with patch("socket.create_connection", return_value=MagicMock()):
        assert check_port_listening("127.0.0.1", 8000) is True

    with patch("socket.create_connection", side_effect=OSError("Refused")):
        assert check_port_listening("127.0.0.1", 8000) is False


def test_evaluate_service_status_online() -> None:
    """Verifies evaluate_service_status builds green online badge when reachable."""
    svc_dict = {
        "id": "test_svc",
        "name": "Test Service",
        "category": "Test",
        "description": "Test description",
        "url": "http://localhost:8501",
        "port": 8501,
        "health_endpoint": "http://localhost:8501/health",
    }
    with patch(
        "study_coach.services.launcher.check_http_endpoint",
        return_value=(True, "HTTP 200 OK"),
    ):
        status = evaluate_service_status(svc_dict)
        assert status.is_online is True
        assert status.badge_color == "green"
        assert "Online" in status.status_detail


def test_evaluate_service_status_offline() -> None:
    """Verifies evaluate_service_status builds red offline badge when unreachable."""
    svc_dict = {
        "id": "test_svc",
        "name": "Test Service",
        "category": "Test",
        "description": "Test description",
        "url": "http://localhost:8501",
        "port": 8501,
        "health_endpoint": "http://localhost:8501/health",
    }
    with (
        patch(
            "study_coach.services.launcher.check_http_endpoint",
            return_value=(False, "Unreachable"),
        ),
        patch("study_coach.services.launcher.check_port_listening", return_value=False),
    ):
        status = evaluate_service_status(svc_dict)
        assert status.is_online is False
        assert status.badge_color == "red"
        assert "Offline" in status.status_detail


def test_get_all_services_status_list() -> None:
    """Verifies get_all_services_status returns all 8 items."""
    with patch("study_coach.services.launcher.evaluate_service_status") as mock_eval:
        mock_eval.side_effect = lambda s: MagicMock(id=s["id"])
        statuses = get_all_services_status()
        assert len(statuses) == 8


def test_launcher_app_ui_rendering() -> None:
    """Verifies launcher_app.py renders header, metrics, and cards via AppTest."""
    app_path = Path(__file__).resolve().parent.parent.parent / "ui" / "launcher_app.py"
    at = AppTest.from_file(str(app_path), default_timeout=30).run()
    assert not at.exception
    assert "Developer Lab Launcher" in at.title[0].value
    metric_labels = [m.label for m in at.metric]
    assert "Services Online" in metric_labels
    assert "Google ADK UI" in metric_labels
    assert "Study Coach App" in metric_labels
    assert "Observability Stack" in metric_labels


def test_direct_tab_navigation_in_study_coach() -> None:
    """Verifies that ui/app.py navigates directly to requested tabs via ?tab= query parameter."""
    app_path = Path(__file__).resolve().parent.parent.parent / "ui" / "app.py"

    # Test ops tab navigation
    at_ops = AppTest.from_file(str(app_path), default_timeout=30)
    at_ops.query_params["tab"] = "ops"
    at_ops.run()
    assert at_ops.session_state.get("main_nav_tab") == "🔭 Agent Ops"

    # Test evals tab navigation
    at_eval = AppTest.from_file(str(app_path), default_timeout=30)
    at_eval.query_params["tab"] = "eval"
    at_eval.run()
    assert at_eval.session_state.get("main_nav_tab") == "🧪 Evaluations"

    # Test chat tab navigation
    at_chat = AppTest.from_file(str(app_path), default_timeout=30)
    at_chat.query_params["tab"] = "chat"
    at_chat.run()
    assert at_chat.session_state.get("main_nav_tab") == "💬 Ask Study Coach"
