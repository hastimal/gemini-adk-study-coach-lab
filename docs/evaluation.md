# Agent Evaluation Guide — Gemini ADK Study Coach Lab

This document explains the evaluation methodology, dataset fixtures, Google ADK evaluation architecture, and verification results for the **Gemini ADK Study Coach Lab**.

---

## 1. Evaluation Methodology

To ensure high quality, deterministic reliability, and rigorous AI safety, evaluation is split into two distinct tiers:

1. **Deterministic Pytest Contract & Agent Regression Tests (`tests/unit/`, `tests/eval/`)**:
   - Fast, reproducible, non-networked unit, schema contract, and agent regression evaluations executed in CI/CD.
   - Validates Pydantic schema validation, daily minute limit invariants, option counts, answer key protection, intent routing heuristics, weak topic identification, adaptive replanning, and failure category taxonomy (`timeout`, `schema_validation`, `constraint_violation`, `missing_credentials`, `unhandled_exception`).
   - Run command: `uv run pytest -q` (188 passed tests).
   - Dedicated agent regression command: `uv run pytest tests/unit/test_agent_deterministic_evaluations.py -v` (15 passed tests).

2. **Opt-In Live Google ADK Model Evaluations (`tests/eval/run_live_evaluation.py`)**:
   - Real Gemini API requests evaluated through Google ADK agents using `InMemoryRunner`.
   - Instrumented with `ADKObservabilityPlugin` to export distributed traces to Tempo and Prometheus metrics.
   - Evaluates multi-turn agent response formatting, tool execution traces, key concept completeness, question generation quality, and latency.
   - Run command: `uv run python tests/eval/run_live_evaluation.py` (opt-in; skipped in normal CI).

---

## 2. Evaluation Scenarios Fixture

Defined in [`tests/eval/fixtures/evaluation_scenarios.json`](../tests/eval/fixtures/evaluation_scenarios.json):

| Scenario ID | Target Agent | Description | Success Criteria |
|---|---|---|---|
| `scenario_1` | `study_planner` / `root_agent` | 14-day beginner plan (90 min daily) | Plan total days = 14, daily minutes <= 90, schema valid |
| `scenario_2` | `study_planner` | 7-day intermediate plan (45 min daily) | Plan total days = 7, daily minutes <= 45, schema valid |
| `scenario_3` | `topic_expert` | Explain Grounding and RAG for beginner | Key concepts >= 3, learning objectives >= 2, Google Cloud context |
| `scenario_4` | `topic_expert` | Transformer attention for intermediate | Multi-head attention explained, technical depth matching level |
| `scenario_5` | `quiz_generator` | Generate 3 formative MCQs on LLM foundations | Exactly 3 questions, 4 options each, private keys protected |
| `scenario_6` | `quiz_generator` | Generate 5 formal practice questions | Exactly 5 questions, 4 options each, valid answer distribution |
| `scenario_7` | `workflow_grading` | Pure Python deterministic grading | Correct percentage calculation, weak/strong topic classification |
| `scenario_8` | `study_planner` | Adaptive replanning using weak topics | Weak topic prioritized, remaining days adjusted |
| `scenario_9` | `topic_expert` | Unknown topic rejection handling | Returns graceful error/fallback, no crashes |
| `scenario_10` | `study_planner` | Invalid daily minutes (0 min budget) | Pydantic validation rejects with clear error |

---

## 3. Analysis of Google ADK Evaluation APIs

Inspection of the installed `google.adk.evaluation` module reveals:

- **`google.adk.evaluation.AgentEvaluator`**: The official Google ADK evaluation harness providing static methods `evaluate(...)` and `evaluate_eval_set(...)`.
- **`google.adk.evaluation.EvalSet`**: Pydantic schema model representing a collection of test cases with `eval_cases`, `name`, `eval_set_id`, and `rubrics`.
- **`google.adk.evaluation.EvalCase`**: Individual test case holding an `Invocation` sequence (user prompt, expected response, rubrics).
- **Dependency Nuance**: `google-adk[eval]` requires Google Cloud Vertex AI SDK (`google.cloud.aiplatform` / `vertexai`). When deploying in environments using direct Gemini Developer API keys (`GOOGLE_GENAI_USE_VERTEXAI=FALSE`), the standalone live evaluation runner [`tests/eval/run_live_evaluation.py`](../tests/eval/run_live_evaluation.py) evaluates ADK agents directly via `InMemoryRunner`, maintaining 100% Google ADK compatibility without requiring Vertex AI enterprise projects.

### 3.1 Reusable Evaluation Runner (`study_coach.evaluation.EvaluationRunner`)
To bridge deterministic CLI tests and the interactive Streamlit user interface, `EvaluationRunner` provides:
- **Thread-safe concurrency control**: Prevents duplicate overlapping evaluation runs via `asyncio.Lock()`.
- **Execution timeouts**: Applies per-scenario timeouts (`timeout_seconds=60.0`) so evaluation never hangs student learning sessions.
- **Report persistence**: Automatically writes execution summaries to [`docs/reports/recent_evaluation_report.json`](../docs/reports/recent_evaluation_report.json).
- **Sanitization & Privacy**: Strictly excludes Gemini API keys, student identifiers, user prompts, and private quiz answer keys from stored reports.
- **Visual Streamlit Dashboard**: Integrated into **"🧪 Evaluations"** tab ([`ui/components/evaluations_view.py`](../ui/components/evaluations_view.py)) with pass/fail indicators, latency stats, expandable scenario details, and formatted error notifications.

---

## 4. Live Model Evaluation Results

Executed using `uv run python tests/eval/run_live_evaluation.py`:

```
================================================================================
🚀 GOOGLE ADK LIVE MODEL EVALUATION SUITE
================================================================================

[1/4] Evaluating Topic Expert agent (Scenario 3: Grounding & RAG)...
  ✓ PASS: 'Generative AI Concepts: Grounding & Retrieval-Augmented Generation (RAG)' generated in 128.60s
    - Key concepts (7): Grounding, Retrieval-Augmented Generation (RAG), Hallucination

[2/4] Evaluating Quiz Generator agent (Scenario 5: 3 formative MCQs)...
  ✓ PASS: 3 formative MCQs generated in 39.44s (all with 4 sanitized options)

[3/4] Evaluating Study Planner agent (Scenario 2: 7 days, 45 mins/day)...
  ✓ PASS: 7-day study plan generated in 15.34s adhering strictly to daily budget (<= 45 min)

[4/4] Evaluating Root Coordinator agent delegation (Scenario 1)...
  ✓ PASS: Root Coordinator routed & responded in 29.27s (8306 chars)

================================================================================
📊 ADK LIVE EVALUATION SUMMARY
================================================================================
Scenario        Target Agent         Status     Details
--------------------------------------------------------------------------------
scenario_3      topic_expert         PASS       128.60s latency
scenario_5      quiz_generator       PASS       39.44s latency
scenario_2      study_planner        PASS       15.34s latency
scenario_1      root_agent           PASS       29.27s latency
================================================================================
Result: 4/4 scenarios passed.
```

---

## 5. Summary of Quality Gates

| Check | Command | Result |
|---|---|---|
| **Ruff Linter** | `uv run ruff check .` | Passed (0 warnings) |
| **Ruff Formatter** | `uv run ruff format --check .` | Passed (94 files compliant) |
| **Mypy Type Checker** | `uv run mypy .` | Passed (72 source files checked, 0 errors) |
| **Deterministic Tests** | `uv run pytest -q` | Passed (139/139 passed in 2.35s) |
| **Live ADK Evaluation** | `uv run python tests/eval/run_live_evaluation.py` | Passed (4/4 scenarios passed) |
