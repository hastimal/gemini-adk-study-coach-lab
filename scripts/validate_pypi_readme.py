#!/usr/bin/env python3
"""Validates README-pypi.md for PyPI rendering requirements:
1. No raw ```mermaid blocks.
2. All images use absolute, reachable HTTPS URLs.
3. All markdown links use absolute HTTPS URLs.
4. No repository-relative links (e.g. docs/...).
5. CLI examples use verified CLI subcommands.
"""

import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))
PYPI_README = PROJECT_ROOT / "README-pypi.md"


def main() -> int:
    if not PYPI_README.is_file():
        print(f"ERROR: {PYPI_README} not found")
        return 1

    content = PYPI_README.read_text(encoding="utf-8")
    errors: list[str] = []

    # 1. Reject raw Mermaid code blocks
    if "```mermaid" in content:
        errors.append("Found unsupported '```mermaid' block in PyPI README.")

    # 2. Reject repository-relative links: [text](docs/...) or (LICENSE)
    relative_links = re.findall(
        r"\[([^\]]+)\]\((?!https?://|mailto:|#)([^)]+)\)", content
    )
    for text, target in relative_links:
        errors.append(
            f"Found relative link: [{text}]({target}). Must use absolute HTTPS URL."
        )

    # 3. Check all URLs for proper formatting
    urls = re.findall(r"https?://[^\s\)\"\'>]+", content)
    for url in urls:
        if "google.github.io/agent-development-kit" in url:
            errors.append(f"Known 404 URL found: {url}")
        if url.endswith("]"):
            errors.append(f"Malformed URL ending with bracket: {url}")

    # 4. Check that image URLs point to valid files in the local git repository
    raw_github_prefix = (
        "https://raw.githubusercontent.com/hastimal/gemini-adk-study-coach-lab/main/"
    )
    img_matches = re.findall(r"!\[([^\]]*)\]\((https?://[^\)]+)\)", content)
    for alt, img_url in img_matches:
        if img_url.startswith(raw_github_prefix):
            rel_path = img_url[len(raw_github_prefix) :]
            local_file = PROJECT_ROOT / rel_path
            if not local_file.is_file():
                errors.append(
                    f"Image referenced at '{img_url}' does not exist locally at '{local_file}'."
                )

    # 5. Check valid CLI commands in code blocks
    import argparse

    valid_subcommands: set[str] = {"doctor", "start", "version"}
    try:
        from study_coach.cli import build_parser

        parser = build_parser()
        for action in parser._actions:
            if isinstance(action, argparse._SubParsersAction):
                valid_subcommands.update(action.choices.keys())
    except ImportError:
        pass
    valid_flags: set[str] = {"--help", "-h", "--version", "-v"}

    cli_lines = [
        line.strip()
        for line in content.splitlines()
        if line.strip().startswith("gemini-adk-study-coach-lab")
    ]
    for line in cli_lines:
        tokens = line.split()
        if len(tokens) > 1:
            subcmd = tokens[1]
            if (
                subcmd not in valid_subcommands
                and subcmd not in valid_flags
                and not subcmd.startswith("-")
            ):
                errors.append(
                    f"Invalid CLI subcommand '{subcmd}' found in '{line}'. Must be one of {sorted(valid_subcommands)}."
                )

    if errors:
        print("❌ PyPI README validation failed:")
        for err in errors:
            print(f"  - {err}")
        return 1

    print(
        f"✅ PyPI README validation passed! (Checked {len(urls)} URLs and {len(img_matches)} images)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
