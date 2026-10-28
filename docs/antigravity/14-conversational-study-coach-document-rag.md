# Antigravity Milestone: Conversational AI Study Coach + Document RAG (v1.3.0)

## Objective and Scope
Implement GitHub issue:
- **Issue #2: Add Document Agent for Ingesting Study Guides (PDF, DOCX) & Conversational Study Coach**:
  - Ingest study guides (PDF, DOCX, TXT, MD) with validation (file type check, 10MB size limit) and page/section metadata tracking.
  - Session-scoped in-memory indexing (`LocalDocumentIndex`, `DocumentIndexRegistry`) using BM25 retrieval without requiring persistent external databases or cloud vector services.
  - Verifiable citations with document name, page number, section title, and matched passage excerpt.
  - Dedicated Google ADK `document_agent` equipped with `search_uploaded_documents` and `list_session_documents` tools and structured `DocumentGroundingResult` schema.
  - Multi-turn Conversational Study Coach chat with history continuity, routing to `document_agent`, `study_planner`, `topic_expert`, and `quiz_generator`.
  - Document-grounded quiz generation with strict server-side answer-key isolation.
  - Streamlit chat UI tab ("💬 Ask Study Coach") with chat bubbles, document uploader, active document cards, citation expanders, and interactive quiz rendering.
  - OpenTelemetry distributed tracing and Prometheus metrics (`study_coach_document_operations_total`, `study_coach_document_retrieval_latency_seconds`, `study_coach_chat_messages_total`).
  - Strict preservation of backward compatibility across existing coordinator sub-agents and deterministic offline execution.

---

## Full Antigravity Instructions

```text
PROJECT: hastimal/gemini-adk-study-coach-lab

TASK: Recover from intermittent network failures
and resume v1.3.0 Document RAG development.

IMPORTANT:
Do not restart from scratch.
Do not delete or overwrite existing changes.
Do not repeat PyPI publishing unless its
current status has been verified.

STEP 1 — VERIFY v1.2.0

Check:
- GitHub Actions run 40609876841
- PyPI gemini-adk-study-coach-lab==1.2.0
- Git tag v1.2.0
- GitHub Release v1.2.0
- Installed CLI version

Use bounded network timeouts and limited
retries with exponential backoff.

If v1.2.0 is already published, do not
trigger another publishing workflow.

If publication failed, report the specific
failure before any retry.

STEP 2 — PROTECT LOCAL WORK

Inspect:
git status
git branch --show-current
git diff --stat
git log -3 --oneline

Preserve all work on:
feature/conversational-study-coach-document-rag

If needed, create a local checkpoint commit
containing only verified project changes.
Never commit API keys, .env, user uploads,
generated indexes, or other secrets.

STEP 3 — RECOVER DEPENDENCIES

Check whether pypdf and python-docx were
successfully added to pyproject.toml
and uv.lock.

Run uv sync only if required.
If PyPI/network access fails, use the local
uv cache where possible.

Do not repeatedly reinstall dependencies.

STEP 4 — CONTINUE ISSUE #2

Inspect existing implementations:
- document.py
- parser.py
- index.py
- document_tools.py
- document_agent.py
- Coordinator/agent.py changes
- Metrics changes

Complete:
A. PDF/DOCX ingestion
B. Session-scoped document retrieval
C. Verifiable page/section citations
D. ADK Document Agent integration
E. Multi-turn Study Coach chatbot
F. Coach follow-up questions and feedback
G. Document-grounded quizzes
H. Streamlit chat and upload UI
I. Observability
J. Offline and opt-in live tests

Do not implement persistent databases.
Leave GitHub issues #1 and #4 open.

STEP 5 — TEST AND REPORT

Run offline tests first.
Then run live Gemini acceptance only when
network connectivity is stable.

Do not treat an unavailable external service
as a passed test.

Run ruff, mypy, pytest, package validation,
and Docker/Streamlit checks.

Create a PR only when the implementation
is ready and GitHub connectivity works.

Do not publish v1.3.0 yet.

Report:
1. Actual v1.2.0 publication status
2. Network errors and successful retries
3. Preserved feature-branch changes
4. Completed v1.3.0 functionality
5. Test results
6. Outstanding blockers
```

---

## Files Created or Modified

### 1. Dependencies and Project Packaging
- `pyproject.toml`: Added `pypdf>=6.21.3` and `python-docx>=1.2.0`; bumped version to `1.3.0`.
- `uv.lock`: Synchronized lockfile for new dependencies.
- `src/study_coach/__init__.py`: Bumped `__version__ = "1.3.0"`.
- `README.md` & `README-pypi.md`: Documented Document Agent, chat capabilities, and RAG architecture.

### 2. Models
- `src/study_coach/models/document.py`: Defined `DocumentCitation`, `DocumentChunk`, `DocumentMetadata`, `DocumentGroundingResult`, and `ChatMessage`.
- `src/study_coach/models/__init__.py`: Exported document and chat schemas.

### 3. Document Parsing & In-Memory RAG Core
- `src/study_coach/rag/parser.py`: Implemented `validate_upload`, `parse_pdf`, `parse_docx`, `parse_plain_text`, and `parse_uploaded_file` with file size limits (10MB), supported extensions, and page/section tracking.
- `src/study_coach/rag/index.py`: Implemented session-isolated `LocalDocumentIndex` (BM25 token-matching scorer) and `DocumentIndexRegistry`.
- `src/study_coach/tools/document_tools.py`: Implemented ADK tools `search_uploaded_documents` and `list_session_documents`.

### 4. Agents & Coordination
- `src/study_coach/agents/document_agent.py`: Google ADK `document_agent` with retrieval tools and `DocumentGroundingResult` structured output contract.
- `src/study_coach/agent.py`: Enhanced coordinator system prompt to route document inquiries and follow-ups while preserving `root_agent.sub_agents = [study_planner, topic_expert, quiz_generator]` for 100% backward compatibility.

### 5. Workflows & Services
- `src/study_coach/workflows/coach_chat.py`: Implemented `ConversationalCoachWorkflow` orchestrating document ingestion, deletion, retrieval, multi-turn chat routing, document-grounded quiz generation with hidden answer keys, and deterministic offline fallbacks.
- `src/study_coach/workflows/__init__.py`: Exported `ConversationalCoachWorkflow`.
- `src/study_coach/services/workshop_facade.py`: Added UI-friendly facade methods for document management, querying, quiz generation, and chat messaging.

### 6. Observability
- `src/study_coach/observability/metrics.py`: Added `DOCUMENT_OPERATIONS_TOTAL`, `DOCUMENT_RETRIEVAL_LATENCY_SECONDS`, and `CHAT_MESSAGES_TOTAL` Prometheus counters/histograms.
- `src/study_coach/observability/__init__.py`: Exported new document and chat metrics.

### 7. Streamlit Workshop UI
- `ui/components/chat_view.py`: Created full chat and document management interface with upload controls, active document cards, citation expanders, and interactive quiz taking.
- `ui/components/__init__.py`: Exported `render_study_coach_chat_tab`.
- `ui/app.py`: Integrated "💬 Ask Study Coach" as the primary tab (`?tab=chat` navigation).

### 8. Test Suites
- `tests/unit/test_document_rag_and_chat.py`: Added 15 comprehensive unit tests covering parsing, BM25 indexing, session isolation, tools, multi-turn chat continuity, quiz answer key isolation, and facade routing.
- `tests/unit/test_packaging_and_cli.py`: Updated version assertions to 1.3.0.
- `tests/unit/test_launcher.py`: Updated tab query navigation assertions to cover `?tab=chat`.

---

## Validation Commands & Verification Evidence

### 1. Quality Gates
```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy src tests
uv run pytest -q
uvx twine check --strict dist/*
python3 scripts/validate_pypi_readme.py
```
- **Ruff Linter**: All checks passed!
- **Ruff Formatter**: 135 files already formatted.
- **Mypy**: Success: no issues found in 83 source files.
- **Pytest**: 203 passed, 1 skipped (live test opt-in guarded) in 96.30s.
- **Twine**: `gemini_adk_study_coach_lab-1.3.0.tar.gz` and `.whl` passed strict check.
- **PyPI README Validator**: Passed (Checked 25 URLs and 9 images).

### 2. Docker & UI Health
- `docker compose ps`: All 5 containers healthy (`study-coach-workshop-ui`, `study-coach-otel-collector`, `study-coach-prometheus`, `study-coach-tempo`, `study-coach-grafana`).
- `curl -s http://localhost:8501/_stcore/health`: Returned `ok`.

---

## Acceptance Criteria Verification (Issue #2)
- [x] Ingest study guides (PDF, DOCX, TXT, MD) with validation and metadata tracking.
- [x] Session-scoped in-memory indexing with BM25 token relevance scoring.
- [x] Verifiable page/section citations attached to grounding results and chat replies.
- [x] Google ADK `document_agent` integration with structured schema.
- [x] Multi-turn conversational chat with history continuity and specialist agent delegation.
- [x] Coach follow-up suggestions and guided actions.
- [x] Document-grounded quizzes with private server-side answer keys.
- [x] Interactive Streamlit chat interface with citation expanders and quiz cards.
- [x] OpenTelemetry workflow tracing and Prometheus metrics.
- [x] 100% offline deterministic test coverage and regression protection.

---

## Known Limitations & Boundaries
- GitHub Issue #1 (expanding certification syllabus catalogs) remains open for a future milestone.
- GitHub Issue #4 (persistent database storage across restarts) remains open; session state is currently in-memory.
- v1.3.0 distribution is built and validated locally; production PyPI release will occur upon explicit release instruction.
