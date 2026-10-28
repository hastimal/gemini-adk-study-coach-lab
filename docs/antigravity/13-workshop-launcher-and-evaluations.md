# Antigravity Milestone: Workshop Launcher & Agent Evaluations (v1.2.0)

## Objective and Scope
Implement GitHub issues:
- **Issue #6: Workshop Launcher and Environment Diagnostics**: Audit launcher functionality, avoid duplicate launchers, validate Python >= 3.12, `uv` package manager, Gemini API keys and model configuration, optional Docker daemon, and ports with clear actionable diagnostics. Preserve app-only, ADK-only, and full-demo launcher modes. Ensure Docker is strictly optional.
- **Issue #5: Agent Evaluation Regression Suite and GitHub CI**: Add deterministic agent regression test cases covering Study Planner, Topic Expert, Quiz Generator, Coordinator routing, tool executions, malformed responses, answer key isolation, and adaptive learning behavior. Standardize failure categories across the evaluation runner and UI. Integrate offline deterministic evaluations into CI while keeping live Gemini tests opt-in.
- **Preserve Clean Extension Points**: Accommodate future conversational Study Coach chatbot, multi-turn Q&A, student progress/chat persistence, and PDF/DOCX retrieval with citations without implementing them prematurely in v1.2.0.

---

## Full Antigravity Instructions

```text
PROJECT: hastimal/gemini-adk-study-coach-lab
BASE RELEASE: v1.1.2
NEXT MILESTONE: v1.2.0

Read GEMINI.md and inspect the existing
implementation before modifying anything.

Implement GitHub issues #6 and #5.

ISSUE #6 — WORKSHOP LAUNCHER
- Audit existing launcher functionality.
- Avoid duplicating completed v1.1.2 work.
- Validate Python, uv, API key presence,
  Gemini configuration, Docker, and ports.
- Display clear actionable diagnostics.
- Preserve app-only, ADK-only, and
  full-demo launcher modes.
- Ensure optional Docker does not block
  the standalone application.

ISSUE #5 — AGENT EVALUATION
- Add deterministic agent regression cases.
- Evaluate planner, topic expert, quiz
  generator, coordinator routing, and tools.
- Cover malformed responses and failures.
- Test quiz answer-key isolation.
- Validate adaptive learning behavior.
- Integrate offline evaluations into CI.
- Keep live Gemini tests opt-in.

FUTURE FEATURE REQUIREMENTS
Preserve a clean extension path for:
- Conversational Study Coach chatbot.
- Multi-turn question/answer interactions.
- Student progress and chat persistence.
- PDF/DOCX upload and retrieval-based Q&A.
- Source/page citations.
- Uploaded-guide-based quizzes.
- Existing three-agent orchestration.

Do not implement these future features
in v1.2.0.

DELIVERY
- New feature branch.
- Automated tests, ruff, mypy, packaging.
- Updated README and developer docs.
- PR linked to issues #6 and #5.
- Merge only after green CI.
- Report findings before publishing.
- Do not publish to PyPI until the
  acceptance criteria are verified.
```

---

## Files Created or Modified

1. `src/study_coach/cli.py`:
   - Enhanced `cmd_doctor` to explicitly verify `uv` package manager presence and version in PATH, outputting actionable guidance (`https://docs.astral.sh/uv/`) when missing.
   - Preserves Python 3.12+, bundled resources, masked API keys, model configuration, port availability (8501, 8000, 8001, 8500), and optional Docker daemon checks.
2. `src/study_coach/models/evaluation.py`:
   - Added `failure_category` field (`Literal["none", "schema_validation", "constraint_violation", "missing_credentials", "timeout", "unhandled_exception", "curriculum_grounding"]`) to `EvaluationScenarioResult`.
3. `src/study_coach/evaluation/runner.py`:
   - Updated scenario evaluation handlers (`topic_expert`, `quiz_generator`, `study_planner`, `root_coordinator`, and credential pre-checks) to classify and assign explicit `failure_category` values on timeout, schema errors, and unhandled exceptions.
4. `ui/components/evaluations_view.py`:
   - Updated Streamlit evaluation dashboard to display formatted `:red-background[failure_category]` badges when a scenario encounters failures.
5. `src/study_coach/models/learning_session.py`:
   - Added `metadata: dict[str, Any] = Field(default_factory=dict)` to `LearningSession` to preserve clean extension points for conversational multi-turn chat persistence, document IDs, and retrieval state without breaking existing schemas.
6. `tests/unit/test_agent_deterministic_evaluations.py`:
   - Added 15 comprehensive deterministic regression tests covering:
     - Study planner sequential days, numerical duration sum validation, and deterministic minute calculations.
     - Topic expert tools, curriculum retrieval, and schema structure sanitization.
     - Quiz generator structure, client-side answer key isolation, and pure Python deterministic grading.
     - Root coordinator agent declaration and routing heuristics.
     - Adaptive learning state progression and replanning with completed days.
     - Evaluation failure category serialization.
     - Future session extensibility metadata verification.
7. `tests/unit/test_packaging_and_cli.py`:
   - Updated version assertions for `1.2.0`.
8. `pyproject.toml` & `src/study_coach/__init__.py`:
   - Bumped package version to `1.2.0`.
9. `uv.lock`:
   - Updated lockfile with package version `1.2.0`.
10. `README.md`, `docs/cli.md`, `docs/evaluation.md`:
    - Updated documentation to reflect `uv` diagnostics, `1.2.0` versioning, deterministic agent regression tests, failure categories, and opt-in live Gemini evaluations.

---

## Validation Commands & Verification Evidence

### 1. Quality Gates
```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy src tests
uv run pytest -q
python3 scripts/validate_pypi_readme.py
```
- **Ruff Linter**: Passed (All checks passed).
- **Ruff Formatter**: Passed (126 files compliant).
- **Mypy**: Success (no issues found in 76 source files).
- **Pytest**: Passed: 188 passed, 1 skipped (live test opt-in guarded) in 5.69s.
- **PyPI README Validator**: Passed (Checked 25 URLs and 9 images).

### 2. Environment Diagnostics Check
```bash
uv run gemini-adk-study-coach-lab doctor
```
- Output verified:
  - `[OK] Python Runtime: v3.12.15`
  - `[OK] uv Package Manager: uv 0.13.0 (/Users/hastimal.jangid/.local/bin/uv)`
  - `[OK] Package: gemini-adk-study-coach-lab v1.2.0`
  - `[OK] Masked Gemini Key`
  - `[OK] Docker Daemon: Running and responsive (Observability stack can be started)`

### 3. Packaging & Distribution Integrity
```bash
rm -rf dist && uv build && uvx twine check --strict dist/*
```
- Built `dist/gemini_adk_study_coach_lab-1.2.0.tar.gz` and `dist/gemini_adk_study_coach_lab-1.2.0-py3-none-any.whl`.
- Twine strict verification: PASSED.

---

## Acceptance Criteria Verification (Issues #6 & #5)

### Issue #6 (Workshop Launcher and Environment Diagnostics)
- [x] Audited existing launcher script (`scripts/run_local.sh`) and verified app-only (`--app-only`), ADK-only (`--adk-only`), and full-demo (`--full-demo`) modes.
- [x] Validated Python, `uv`, Gemini credentials, Docker, and ports in `cmd_doctor` with actionable diagnostics.
- [x] Confirmed Docker remains strictly optional and does not impede standalone application or CLI operations.

### Issue #5 (Agent Evaluation Regression Suite and GitHub CI)
- [x] Deterministic agent regression test suite added in `tests/unit/test_agent_deterministic_evaluations.py`.
- [x] Evaluates planner, topic expert, quiz generator, coordinator routing, and tools offline.
- [x] Tested quiz answer-key isolation: client questions contain only options and question text, while ground truth is evaluated strictly server-side.
- [x] Tested adaptive learning behavior: weak topic prioritization and completed day preservation.
- [x] Integrated offline evaluations into CI test suite (now 188 automated tests).
- [x] Kept live Gemini tests opt-in (`tests/eval/run_live_evaluation.py`).
- [x] Preserved clean extension points for conversational study coach and document retrieval.

---

## Known Limitations
- Custom certification track authoring remains planned for post-v1.2.0.
- Chat session persistence across process restarts will build on the newly added `LearningSession.metadata` extension points.
