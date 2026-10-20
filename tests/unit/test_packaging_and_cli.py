"""Packaging, distribution, and CLI unit tests.

Verifies:
1. Package metadata
2. Console entrypoint
3. Wheel contents
4. Source distribution contents
5. YAML curriculum availability
6. Streamlit application availability
7. No runtime dependency on Git checkout
8. CLI --help
9. CLI version
10. CLI doctor
11. Missing credentials handling
12. Missing optional Docker handling
13. Occupied port handling
14. No secrets in distributions
15. Existing application compatibility
"""

import os
import socket
import tarfile
import zipfile
from pathlib import Path

import pytest

from study_coach.cli import (
    cmd_doctor,
    get_ui_app_path,
    main,
    mask_key,
)
from study_coach.models.student import StudentProfile
from study_coach.services.provider_registry import (
    resolve_provider_for_url,
)
from study_coach.tools.curriculum_tools import CURRICULUM_FILE, load_curriculum
from study_coach.tools.resource_tools import load_learning_resources
from ui.components.resource_cards import ASSETS_DIR, get_provider_logo_svg

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


def test_package_metadata() -> None:
    """1. Verify PEP 621 package metadata in pyproject.toml."""
    pyproject_path = PROJECT_ROOT / "pyproject.toml"
    assert pyproject_path.is_file()

    content = pyproject_path.read_text(encoding="utf-8")
    assert 'name = "gemini-adk-study-coach"' in content
    assert 'version = "1.1.0"' in content
    assert 'requires-python = ">=3.12"' in content
    assert "streamlit" in content
    assert "google-adk" in content
    assert "python-dotenv" in content


def test_console_entrypoint_defined() -> None:
    """2. Verify console script entrypoint is registered."""
    pyproject_path = PROJECT_ROOT / "pyproject.toml"
    content = pyproject_path.read_text(encoding="utf-8")
    assert "[project.scripts]" in content
    assert 'gemini-adk-study-coach = "study_coach.cli:main"' in content


def test_wheel_contents(tmp_path: Path) -> None:
    """3. Verify wheel artifact contains all required packages and assets."""
    dist_dir = PROJECT_ROOT / "dist"
    wheels = list(dist_dir.glob("gemini_adk_study_coach-*.whl")) + list(
        dist_dir.glob("study_coach-*.whl")
    )
    if not wheels:
        pytest.skip("No wheel built in dist/ yet. Run 'uv build' to produce wheel.")

    wheel_path = max(wheels, key=os.path.getmtime)
    with zipfile.ZipFile(wheel_path, "r") as zf:
        namelist = zf.namelist()

        # Study coach core
        assert any("study_coach/__init__.py" in name for name in namelist)
        assert any("study_coach/cli.py" in name for name in namelist)
        assert any("study_coach/agent.py" in name for name in namelist)

        # Bundled curriculum & resources
        assert any(
            "study_coach/data/google_cloud_genai_leader.yaml" in name
            for name in namelist
        )
        assert any(
            "study_coach/data/learning_resources.yaml" in name for name in namelist
        )
        assert any(
            "study_coach/data/resource_providers.yaml" in name for name in namelist
        )

        # Bundled UI & SVGs
        assert any("ui/app.py" in name for name in namelist)
        assert any("ui/components/resource_cards.py" in name for name in namelist)
        assert any(
            "ui/assets/provider_icons/google-cloud.svg" in name for name in namelist
        )


def test_sdist_contents() -> None:
    """4. Verify sdist artifact contains sources, license, and metadata."""
    dist_dir = PROJECT_ROOT / "dist"
    sdists = list(dist_dir.glob("gemini_adk_study_coach-*.tar.gz")) + list(
        dist_dir.glob("study_coach-*.tar.gz")
    )
    if not sdists:
        pytest.skip("No sdist built in dist/ yet. Run 'uv build' to produce sdist.")

    sdist_path = max(sdists, key=os.path.getmtime)
    with tarfile.open(sdist_path, "r:gz") as tf:
        namelist = tf.getnames()
        assert any("pyproject.toml" in name for name in namelist)
        assert any("README.md" in name for name in namelist)
        assert any("LICENSE" in name for name in namelist)
        assert any("src/study_coach/cli.py" in name for name in namelist)
        assert any("ui/app.py" in name for name in namelist)


def test_yaml_curriculum_availability() -> None:
    """5. Verify YAML curriculum syllabus is valid and loads."""
    assert CURRICULUM_FILE.is_file()
    data = load_curriculum()
    assert "topics" in data
    assert len(data["topics"]) >= 4
    topic_ids = [t["id"] for t in data["topics"]]
    assert "genai_concepts" in topic_ids
    assert "llm_architecture" in topic_ids


def test_streamlit_app_availability() -> None:
    """6. Verify Streamlit UI entrypoint is located."""
    app_path = get_ui_app_path()
    assert app_path.is_file()
    assert app_path.name == "app.py"


def test_no_runtime_dependency_on_git_checkout(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """7. Verify resource loading works from an arbitrary non-repo working directory."""
    monkeypatch.chdir(tmp_path)

    # Load curriculum from non-repo CWD
    curriculum = load_curriculum()
    assert "topics" in curriculum

    # Load resources catalog from non-repo CWD
    resources = load_learning_resources()
    assert len(resources) > 0

    # Resolve provider and load SVG from non-repo CWD
    prov = resolve_provider_for_url("https://cloud.google.com/vertex-ai")
    assert prov.provider_id == "google_cloud"
    svg = get_provider_logo_svg(prov.icon_asset)
    assert "<svg" in svg


def test_cli_help(capsys: pytest.CaptureFixture[str]) -> None:
    """8. Verify CLI --help exits with 0 and prints usage."""
    with pytest.raises(SystemExit) as excinfo:
        main(["--help"])
    assert excinfo.value.code == 0
    captured = capsys.readouterr()
    assert "gemini-adk-study-coach" in captured.out
    assert "start" in captured.out
    assert "doctor" in captured.out
    assert "version" in captured.out


def test_cli_version(capsys: pytest.CaptureFixture[str]) -> None:
    """9. Verify CLI version command prints correct version string."""
    ret = main(["version"])
    assert ret == 0
    captured = capsys.readouterr()
    assert "gemini-adk-study-coach" in captured.out
    assert "1.1.0" in captured.out


def test_cli_doctor(capsys: pytest.CaptureFixture[str]) -> None:
    """10. Verify CLI doctor command passes and displays all diagnostics."""
    import argparse

    ret = cmd_doctor(argparse.Namespace())
    assert ret == 0
    captured = capsys.readouterr()
    assert "GEMINI ADK STUDY COACH — ENVIRONMENT & DIAGNOSTICS" in captured.out
    assert "Python Runtime:" in captured.out
    assert "Curriculum Syllabus:" in captured.out
    assert "Brand Provider Icons:" in captured.out
    assert "Port Availability:" in captured.out


def test_cli_missing_credentials_handling(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """11. Verify doctor handles missing API credentials gracefully without crashing."""
    import argparse

    monkeypatch.setattr("study_coach.cli.load_dotenv", lambda: None)
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    ret = cmd_doctor(argparse.Namespace())
    assert ret == 0  # Missing key is a non-fatal setup warning in doctor
    captured = capsys.readouterr()
    assert "Neither GEMINI_API_KEY nor GOOGLE_API_KEY is set" in captured.out


def test_cli_missing_optional_docker_handling(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """12. Verify doctor handles missing Docker gracefully without error."""
    import argparse

    monkeypatch.setattr("shutil.which", lambda cmd: None)

    ret = cmd_doctor(argparse.Namespace())
    assert ret == 0
    captured = capsys.readouterr()
    assert "Docker is not installed" in captured.out
    assert "Docker is optional" in captured.out


def test_cli_occupied_port_handling(capsys: pytest.CaptureFixture[str]) -> None:
    """13. Verify start command detects occupied port and gives actionable guidance."""
    import argparse

    from study_coach.cli import cmd_start

    # Bind a temporary port
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        occupied_port = s.getsockname()[1]

        args = argparse.Namespace(
            port=occupied_port,
            address="127.0.0.1",
            headless=True,
        )
        ret = cmd_start(args)
        assert ret == 1
        captured = capsys.readouterr()
        assert f"Port {occupied_port} is already in use" in captured.err
        assert "--port" in captured.err


def test_no_secrets_in_distributions() -> None:
    """14. Verify distributions do not contain secrets or environment files."""
    dist_dir = PROJECT_ROOT / "dist"
    if not dist_dir.exists():
        pytest.skip("No dist/ directory found.")

    for path in dist_dir.glob("*.whl"):
        with zipfile.ZipFile(path, "r") as zf:
            for name in zf.namelist():
                assert not name.endswith(".env")
                assert ".git" not in name
                assert "__pycache__" not in name
                assert "secrets" not in name.lower()


def test_existing_application_compatibility() -> None:
    """15. Verify existing models, curriculum tools, and facades continue to function."""
    profile = StudentProfile(
        experience_level="intermediate",
        daily_study_minutes=60,
    )
    assert profile.experience_level == "intermediate"

    curriculum = load_curriculum()
    assert "topics" in curriculum
    assert len(curriculum["topics"]) > 0

    resources = load_learning_resources()
    assert len(resources) > 0

    assert ASSETS_DIR.is_dir()
    assert len(list(ASSETS_DIR.glob("*.svg"))) >= 15


def test_mask_key() -> None:
    """Helper test to verify key masking security."""
    assert mask_key("") == "[NOT SET]"
    assert mask_key("short") == "****"
    masked = mask_key("AIzaSyDummySecretKeyForUnitTestingOnly12345")
    assert masked.startswith("AIza...")
    assert masked.endswith("2345 (length: 43)")
    assert "DummySecret" not in masked
