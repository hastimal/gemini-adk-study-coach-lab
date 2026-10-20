"""Command-line interface for Gemini ADK Study Coach.

Provides commands to start the Streamlit application, run environment
diagnostics, and check version/help information.
"""

import argparse
import importlib.metadata
import os
import shutil
import socket
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path

from dotenv import load_dotenv

from study_coach import __version__


def get_version() -> str:
    """Returns the installed package version or fallback."""
    try:
        return importlib.metadata.version("gemini-adk-study-coach")
    except importlib.metadata.PackageNotFoundError:
        try:
            return importlib.metadata.version("study-coach")
        except importlib.metadata.PackageNotFoundError:
            return __version__


def get_ui_app_path() -> Path:
    """Locates the bundled Streamlit application entrypoint."""
    # 1. Check relative to ui module if importable
    try:
        import ui

        if hasattr(ui, "__file__") and ui.__file__:
            candidate = Path(ui.__file__).resolve().parent / "app.py"
            if candidate.is_file():
                return candidate
    except (ImportError, AttributeError, OSError):
        pass

    # 2. Check sibling to study_coach module (wheel structure in site-packages)
    try:
        import study_coach

        if hasattr(study_coach, "__file__") and study_coach.__file__:
            sc_dir = Path(study_coach.__file__).resolve().parent
            candidate = sc_dir.parent / "ui" / "app.py"
            if candidate.is_file():
                return candidate
    except (ImportError, AttributeError, OSError):
        pass

    # 3. Check current working directory (repository checkout)
    cwd_candidate = Path.cwd() / "ui" / "app.py"
    if cwd_candidate.is_file():
        return cwd_candidate.resolve()

    raise FileNotFoundError(
        "Could not locate bundled Streamlit entrypoint 'ui/app.py'. "
        "Ensure the gemini-adk-study-coach package is properly installed."
    )


def is_port_in_use(port: int, host: str = "127.0.0.1") -> bool:
    """Checks whether a local TCP port is already bound."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        try:
            s.bind((host, port))
            return False
        except OSError:
            return True


def mask_key(key: str) -> str:
    """Masks an API key for safe terminal display."""
    if not key:
        return "[NOT SET]"
    if len(key) <= 8:
        return "****"
    return f"{key[:4]}...{key[-4:]} (length: {len(key)})"


def cmd_version(args: argparse.Namespace) -> int:
    """Prints the installed package version."""
    version = get_version()
    print(f"gemini-adk-study-coach {version}")
    return 0


def cmd_doctor(args: argparse.Namespace) -> int:
    """Runs environment, credential, dependency, and port diagnostics."""
    # Ensure current working directory .env is loaded if present
    load_dotenv()

    print(
        "================================================================================"
    )
    print("🩺 GEMINI ADK STUDY COACH — ENVIRONMENT & DIAGNOSTICS")
    print(
        "================================================================================"
    )

    has_critical_failure = False

    # 1. Python Environment Check
    py_ver = sys.version.split()[0]
    py_major, py_minor = sys.version_info.major, sys.version_info.minor
    if (py_major, py_minor) >= (3, 12):
        print(f"  [OK] Python Runtime: v{py_ver} (>= 3.12 required)")
    else:
        print(f"  [ERROR] Python Runtime: v{py_ver} (Python >= 3.12 is required)")
        has_critical_failure = True

    # 2. Package Installation Check
    version = get_version()
    package_location = "Local checkout / editable"
    try:
        import study_coach

        if hasattr(study_coach, "__file__") and study_coach.__file__:
            package_location = str(Path(study_coach.__file__).resolve().parent)
    except (ImportError, AttributeError, OSError):
        package_location = "Unknown"
    print(f"  [OK] Package: gemini-adk-study-coach v{version}")
    print(f"       Location: {package_location}")

    # 3. Bundled Resource Verification
    print("\n📦 Bundled Resources:")
    # Curriculum YAML
    try:
        from study_coach.tools.curriculum_tools import CURRICULUM_FILE

        if CURRICULUM_FILE.is_file():
            print(f"  [OK] Curriculum Syllabus: {CURRICULUM_FILE.name} (Found)")
        else:
            print(f"  [ERROR] Curriculum Syllabus: Missing at {CURRICULUM_FILE}")
            has_critical_failure = True
    except (ImportError, OSError, ValueError) as exc:
        print(f"  [ERROR] Curriculum Syllabus Check Failed: {exc}")
        has_critical_failure = True

    # Learning Resources YAML
    try:
        from study_coach.tools.resource_tools import CATALOG_PATH

        if CATALOG_PATH.is_file():
            print(f"  [OK] Learning Resources Catalog: {CATALOG_PATH.name} (Found)")
        else:
            print(f"  [ERROR] Learning Resources Catalog: Missing at {CATALOG_PATH}")
            has_critical_failure = True
    except (ImportError, OSError, ValueError) as exc:
        print(f"  [ERROR] Learning Resources Check Failed: {exc}")
        has_critical_failure = True

    # Resource Providers YAML
    try:
        from study_coach.services.provider_registry import PROVIDERS_REGISTRY_PATH

        if PROVIDERS_REGISTRY_PATH.is_file():
            print(f"  [OK] Provider Registry: {PROVIDERS_REGISTRY_PATH.name} (Found)")
        else:
            print(f"  [ERROR] Provider Registry: Missing at {PROVIDERS_REGISTRY_PATH}")
            has_critical_failure = True
    except (ImportError, OSError, ValueError) as exc:
        print(f"  [ERROR] Provider Registry Check Failed: {exc}")
        has_critical_failure = True

    # Streamlit UI Entrypoint
    try:
        app_path = get_ui_app_path()
        print(f"  [OK] Streamlit UI Entrypoint: {app_path.name} (Found)")
    except (FileNotFoundError, OSError) as exc:
        print(f"  [ERROR] Streamlit UI Entrypoint: {exc}")
        has_critical_failure = True

    # Brand SVG Icons
    try:
        from ui.components.resource_cards import ASSETS_DIR

        if ASSETS_DIR.is_dir():
            icon_count = len(list(ASSETS_DIR.glob("*.svg")))
            print(f"  [OK] Brand Provider Icons: {icon_count} SVG assets verified")
        else:
            print(
                f"  [WARNING] Brand Provider Icons: Directory missing at {ASSETS_DIR}"
            )
    except (ImportError, OSError) as exc:
        print(f"  [WARNING] Provider Icons Check: {exc}")

    # 4. Credential Verification
    print("\n🔑 Credentials & Model Configuration:")
    google_key = os.getenv("GOOGLE_API_KEY", "")
    gemini_key = os.getenv("GEMINI_API_KEY", "")
    active_key = google_key or gemini_key

    if active_key:
        key_source = "GOOGLE_API_KEY" if google_key else "GEMINI_API_KEY"
        print(f"  [OK] Gemini API Key: Configured via {key_source}")
        print(f"       Masked Value: {mask_key(active_key)}")
    else:
        print(
            "  [WARNING] Gemini API Key: Neither GEMINI_API_KEY nor GOOGLE_API_KEY is set."
        )
        print(
            "            AI capabilities (Planner, Explanations, Quizzes) require a Gemini key."
        )
        print(
            "            Setup: export GEMINI_API_KEY='your-key' or create a local .env file."
        )

    gemini_model = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")
    print(f"  [OK] Default Gemini Model: {gemini_model}")

    # 5. Port Availability Verification
    print("\n🌐 Port Availability:")
    ports_to_check = [
        (8501, "Study Coach Web UI (Default)"),
        (8000, "Google ADK Web / Prometheus Metrics"),
        (8500, "Developer Lab Launcher (Local scripts)"),
    ]
    for port, label in ports_to_check:
        in_use = is_port_in_use(port)
        if in_use:
            print(f"  [OCCUPIED] Port {port}: {label} (In use by another process)")
        else:
            print(f"  [AVAILABLE] Port {port}: {label}")

    # 6. Optional Docker Environment Check
    print("\n🐳 Optional Docker Observability:")
    docker_bin = shutil.which("docker")
    if docker_bin:
        try:
            res = subprocess.run(
                ["docker", "info"],
                capture_output=True,
                check=False,
                timeout=2.0,
            )
            if res.returncode == 0:
                print("  [OK] Docker Daemon: Running and responsive.")
                print(
                    "       Observability stack (Prometheus/Grafana/Tempo) can be started."
                )
            else:
                print("  [INFO] Docker CLI is installed, but daemon is not responding.")
                print(
                    "         (Docker is optional; core Study Coach does not require Docker.)"
                )
        except (subprocess.SubprocessError, OSError):
            print("  [INFO] Docker CLI found; status check timed out.")
            print(
                "         (Docker is optional; core Study Coach does not require Docker.)"
            )
    else:
        print("  [INFO] Docker is not installed.")
        print(
            "         (Docker is optional; core Study Coach does not require Docker.)"
        )

    print(
        "\n================================================================================"
    )
    if has_critical_failure:
        print(
            "❌ STATUS: Critical issues detected above. Please resolve before running."
        )
        print(
            "================================================================================"
        )
        return 1

    print("✅ STATUS: Environment is ready to run Gemini ADK Study Coach.")
    print("   Run: gemini-adk-study-coach start")
    print(
        "================================================================================"
    )
    return 0


def cmd_start(args: argparse.Namespace) -> int:
    """Launches the Streamlit Study Coach application."""
    load_dotenv()

    port = getattr(args, "port", 8501)
    address = getattr(args, "address", "0.0.0.0")
    headless = getattr(args, "headless", False)

    try:
        app_path = get_ui_app_path()
    except FileNotFoundError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    # Check for port conflicts before starting
    if is_port_in_use(port, host="127.0.0.1"):
        print(
            f"Error: Port {port} is already in use by another process.\n"
            f"Specify a different port using: gemini-adk-study-coach start --port <PORT>\n"
            f"Example: gemini-adk-study-coach start --port 8502",
            file=sys.stderr,
        )
        return 1

    # Check API key configuration notice
    google_key = os.getenv("GOOGLE_API_KEY", "")
    gemini_key = os.getenv("GEMINI_API_KEY", "")
    if not (google_key or gemini_key):
        print(
            "⚠️ Notice: Neither GEMINI_API_KEY nor GOOGLE_API_KEY is configured in your environment.\n"
            "   Study Coach will start, but AI study plans, explanations, and quizzes require an API key.\n"
            "   Configure your key: export GEMINI_API_KEY='your-key' or place in a local .env file.\n"
        )

    print(
        "================================================================================"
    )
    print("🎓 GEMINI ADK STUDY COACH")
    print(
        "================================================================================"
    )
    print("Starting Streamlit application server...")
    print(f"  Local URL:   http://localhost:{port}")
    if address == "0.0.0.0":
        print(f"  Network URL: http://0.0.0.0:{port}")
    else:
        print(f"  Network URL: http://{address}:{port}")
    print("\nPress Ctrl+C to stop the application server.")
    print(
        "================================================================================\n"
    )

    cmd = [
        sys.executable,
        "-m",
        "streamlit",
        "run",
        str(app_path),
        "--server.port",
        str(port),
        "--server.address",
        str(address),
    ]

    if headless:
        cmd.extend(["--server.headless", "true"])

    try:
        proc = subprocess.run(cmd, check=False)
        return proc.returncode
    except KeyboardInterrupt:
        print("\n\nStudy Coach server stopped. Goodbye!")
        return 0
    except FileNotFoundError:
        print(
            "Error: Streamlit runtime not found in active Python environment.\n"
            "Ensure 'streamlit' is installed: pip install streamlit",
            file=sys.stderr,
        )
        return 1
    except OSError as exc:
        print(f"Error launching Study Coach: {exc}", file=sys.stderr)
        return 1


def build_parser() -> argparse.ArgumentParser:
    """Builds the command-line argument parser."""
    parser = argparse.ArgumentParser(
        prog="gemini-adk-study-coach",
        description="Gemini + Google ADK Multi-Agent Study Coach CLI.",
    )
    parser.add_argument(
        "-v",
        "--version",
        action="version",
        version=f"%(prog)s {get_version()}",
        help="Show installed package version and exit.",
    )

    subparsers = parser.add_subparsers(
        dest="command",
        title="Commands",
        description="Available commands (running without arguments starts Study Coach UI)",
    )

    # start command
    start_parser = subparsers.add_parser(
        "start",
        help="Launch the Streamlit Study Coach web application.",
    )
    start_parser.add_argument(
        "-p",
        "--port",
        type=int,
        default=8501,
        help="Local port to bind Streamlit server (default: 8501).",
    )
    start_parser.add_argument(
        "--address",
        type=str,
        default="0.0.0.0",
        help="Network address to bind server (default: 0.0.0.0).",
    )
    start_parser.add_argument(
        "--headless",
        action="store_true",
        help="Run Streamlit in headless mode without auto-opening a browser tab.",
    )

    # doctor command
    subparsers.add_parser(
        "doctor",
        help="Run environment diagnostics (Python, dependencies, API keys, ports, Docker).",
    )

    # version command
    subparsers.add_parser(
        "version",
        help="Display installed package version.",
    )

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entrypoint function."""
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "start":
        return cmd_start(args)
    elif args.command == "doctor":
        return cmd_doctor(args)
    elif args.command == "version":
        return cmd_version(args)
    elif args.command is None:
        # Default behavior: start Study Coach UI
        return cmd_start(args)
    else:
        parser.print_help()
        return 0


if __name__ == "__main__":
    sys.exit(main())
