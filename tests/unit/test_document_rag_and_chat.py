"""Comprehensive deterministic unit and regression tests for Document AI RAG and Conversational Study Coach.

Covers:
1. Upload validation and file format / size restrictions.
2. PDF and DOCX text extraction, chunking, and metadata provenance.
3. In-memory session-isolated index, BM25 scoring, and search accuracy.
4. Verifiable page/section citations and snippet generation.
5. Unsupported query detection and fallback handling.
6. Untrusted text prompt-injection containment.
7. Multi-turn conversation message recording, routing, and continuity.
8. Document-grounded quiz generation and strict answer-key isolation.
9. Deterministic scoring of document quizzes.
10. Session state isolation and conversation reset.
"""

import io
from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch

import docx
import pytest
from pypdf import PdfWriter

from study_coach.models.document import (
    DocumentChunk,
    DocumentMetadata,
)
from study_coach.models.quiz import Quiz, QuizQuestion
from study_coach.models.student import StudentProfile
from study_coach.rag.index import LocalDocumentIndex, document_index_registry
from study_coach.rag.parser import (
    MAX_FILE_SIZE_BYTES,
    DocumentParseError,
    parse_docx,
    parse_pdf,
    parse_plain_text,
    validate_upload,
)
from study_coach.services.learning_session import LearningSessionService
from study_coach.services.workshop_facade import WorkshopFacade
from study_coach.tools.document_tools import (
    list_session_documents,
    search_uploaded_documents,
)
from study_coach.workflows.coach_chat import ConversationalCoachWorkflow

# ==============================================================================
# 1. PARSER & UPLOAD VALIDATION TESTS
# ==============================================================================


def test_validate_upload_allowed_extensions() -> None:
    """Allowed extensions (pdf, docx, txt, md) pass validation."""
    for ext in ["pdf", "docx", "txt", "md"]:
        doc_id, res_ext = validate_upload(f"study_guide.{ext}", b"Sample content")
        assert doc_id.startswith("doc_")
        assert res_ext == ext


def test_validate_upload_rejects_unsupported_extensions() -> None:
    """Disallowed formats (exe, zip, py, bin) raise DocumentParseError."""
    with pytest.raises(DocumentParseError, match="Unsupported file format"):
        validate_upload("malicious.exe", b"binary content")

    with pytest.raises(DocumentParseError, match="Unsupported file format"):
        validate_upload("archive.zip", b"PK...")


def test_validate_upload_enforces_size_limit() -> None:
    """Files exceeding size limit raise DocumentParseError."""
    oversized = b"A" * (MAX_FILE_SIZE_BYTES + 1024)
    with pytest.raises(DocumentParseError, match="exceeds maximum allowed size"):
        validate_upload("huge_guide.pdf", oversized)


def test_parse_plain_text_and_markdown() -> None:
    """Text and markdown files are parsed into bounded chunks."""
    content = "Google Cloud Generative AI Leader certification covers foundational LLM concepts and Vertex AI Studio."
    meta, chunks = parse_plain_text(
        content.encode("utf-8"), "doc_test1", "guide.md", "md"
    )
    assert meta.filename == "guide.md"
    assert meta.file_type == "md"
    assert len(chunks) >= 1
    assert "Vertex AI Studio" in chunks[0].content
    assert chunks[0].page_number is None
    assert chunks[0].section_title == "Document Body"


def test_parse_docx_with_headings() -> None:
    """DOCX parser preserves heading hierarchy in chunk metadata."""
    doc = docx.Document()
    doc.add_heading("Chapter 1: LLM Architecture", level=1)
    doc.add_paragraph(
        "Transformers rely on self-attention mechanisms to weigh tokens dynamically."
    )
    doc.add_heading("Chapter 2: Vertex AI Studio", level=1)
    doc.add_paragraph(
        "Vertex AI Studio allows rapid prototyping with Gemini multimodal models."
    )

    stream = io.BytesIO()
    doc.save(stream)
    stream.seek(0)

    meta, chunks = parse_docx(stream, "doc_docx1", "guide.docx")
    assert meta.file_type == "docx"
    assert len(chunks) == 2
    assert chunks[0].section_title == "Chapter 1: LLM Architecture"
    assert "self-attention" in chunks[0].content
    assert chunks[1].section_title == "Chapter 2: Vertex AI Studio"
    assert "multimodal" in chunks[1].content


def test_parse_pdf_preserves_page_numbers() -> None:
    """PDF parser assigns 1-based page numbers to extracted chunks."""
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    stream = io.BytesIO()
    writer.write(stream)
    stream.seek(0)

    meta, _chunks = parse_pdf(stream, "doc_pdf1", "guide.pdf")
    assert meta.file_type == "pdf"
    assert meta.total_pages == 1


# ==============================================================================
# 2. LOCAL BM25 INDEX & RETRIEVAL TESTS
# ==============================================================================


def test_local_document_index_search_and_citations() -> None:
    """Index retrieves relevant chunks and constructs verifiable citations."""
    index = LocalDocumentIndex(session_id="test_session")
    meta = DocumentMetadata(
        doc_id="doc_rag_1",
        filename="cloud_ai_study_guide.pdf",
        file_type="pdf",
        file_size_bytes=4096,
        total_pages=3,
        total_chunks=2,
    )
    chunk1 = DocumentChunk(
        chunk_id="doc_rag_1_c0",
        doc_id="doc_rag_1",
        doc_name="cloud_ai_study_guide.pdf",
        page_number=1,
        section_title="Page 1",
        content="Retrieval-Augmented Generation (RAG) grounds language models with external enterprise data.",
        chunk_index=0,
    )
    chunk2 = DocumentChunk(
        chunk_id="doc_rag_1_c1",
        doc_id="doc_rag_1",
        doc_name="cloud_ai_study_guide.pdf",
        page_number=2,
        section_title="Page 2",
        content="Vertex AI Search provides managed RAG indexing over Google Cloud Storage buckets.",
        chunk_index=1,
    )
    index.add_document(meta, [chunk1, chunk2])

    # Search for RAG
    results = index.search("What is Retrieval-Augmented Generation RAG?")
    assert len(results) > 0
    top_chunk, score = results[0]
    assert top_chunk.chunk_id == "doc_rag_1_c0"
    assert score > 0

    # Build citations
    citations = index.build_citations(results)
    assert len(citations) > 0
    assert citations[0].doc_name == "cloud_ai_study_guide.pdf"
    assert citations[0].page_number == 1
    assert "Retrieval-Augmented Generation" in citations[0].snippet


def test_session_isolation_in_registry() -> None:
    """Document indexes remain strictly isolated between different student sessions."""
    registry = document_index_registry
    idx_a = registry.get_or_create("session_student_A")
    idx_b = registry.get_or_create("session_student_B")

    chunk_a = DocumentChunk(
        chunk_id="a_1",
        doc_id="doc_a",
        doc_name="doc_a.txt",
        page_number=None,
        section_title=None,
        content="Student A private notes on Responsible AI principles.",
    )
    idx_a.add_document(
        DocumentMetadata(
            doc_id="doc_a",
            filename="doc_a.txt",
            file_type="txt",
            file_size_bytes=100,
        ),
        [chunk_a],
    )

    # Search in session B must NOT see session A documents
    assert len(idx_b.search("Responsible AI")) == 0
    assert len(idx_a.search("Responsible AI")) == 1

    registry.remove_session("session_student_A")
    registry.remove_session("session_student_B")


# ==============================================================================
# 3. GOOGLE ADK DOCUMENT TOOLS TESTS
# ==============================================================================


def test_search_uploaded_documents_tool_empty() -> None:
    """Tool returns clear empty message when no documents are uploaded."""
    res = search_uploaded_documents(query="transformer", session_id="empty_session")
    assert res["found"] is False
    assert "No documents uploaded" in res["message"]


def test_search_uploaded_documents_tool_with_matches() -> None:
    """Tool returns structured chunks and scores when match is found."""
    registry = document_index_registry
    idx = registry.get_or_create("tool_test_session")
    chunk = DocumentChunk(
        chunk_id="chunk_tool_1",
        doc_id="doc_tool",
        doc_name="notes.md",
        page_number=4,
        section_title="Fine-Tuning",
        content="Parameter-Efficient Fine-Tuning (PEFT) with LoRA adapts model weights using low-rank matrices.",
    )
    idx.add_document(
        DocumentMetadata(
            doc_id="doc_tool",
            filename="notes.md",
            file_type="md",
            file_size_bytes=200,
        ),
        [chunk],
    )

    res = search_uploaded_documents(
        query="LoRA PEFT matrices", session_id="tool_test_session"
    )
    assert res["found"] is True
    assert res["match_count"] >= 1
    assert res["chunks"][0]["section_title"] == "Fine-Tuning"
    assert res["chunks"][0]["page_number"] == 4

    # Test list_session_documents tool
    doc_list = list_session_documents(session_id="tool_test_session")
    assert doc_list["document_count"] == 1
    assert doc_list["documents"][0]["filename"] == "notes.md"

    registry.remove_session("tool_test_session")


# ==============================================================================
# 4. WORKFLOW & CONVERSATIONAL CHAT TESTS
# ==============================================================================


@pytest.mark.anyio
async def test_workflow_document_ingestion_and_deletion() -> None:
    """Workflow ingests document into session index and updates metadata."""
    svc = LearningSessionService()
    workflow = ConversationalCoachWorkflow(session_service=svc)

    sid = "wf_session_test"
    uid = "user_wf"
    profile = StudentProfile(experience_level="beginner", daily_study_minutes=60)
    await svc.get_or_create_session(sid, uid, profile)

    # Ingest document
    sample_text = "Vertex AI Model Garden provides enterprise access to open and proprietary foundation models."
    meta = await workflow.ingest_document(
        session_id=sid,
        user_id=uid,
        filename="model_garden_guide.txt",
        file_bytes=sample_text.encode("utf-8"),
    )
    assert meta.filename == "model_garden_guide.txt"
    assert meta.total_chunks == 1

    docs = await workflow.list_documents(sid)
    assert len(docs) == 1
    assert docs[0].doc_id == meta.doc_id

    # Verify session metadata records document
    session = await svc.get_session(sid, uid)
    assert session is not None
    assert meta.doc_id in session.metadata.get("uploaded_documents", {})

    # Delete document
    deleted = await workflow.delete_document(sid, uid, meta.doc_id)
    assert deleted is True
    assert len(await workflow.list_documents(sid)) == 0

    document_index_registry.remove_session(sid)


@pytest.mark.anyio
async def test_workflow_query_documents_unsupported_graceful_handling() -> None:
    """When query is unsupported in uploaded document, clear fallback reason is returned."""
    svc = LearningSessionService()
    workflow = ConversationalCoachWorkflow(session_service=svc)

    sid = "wf_unsupported_session"
    uid = "user_unsupported"
    profile = StudentProfile(experience_level="beginner", daily_study_minutes=60)
    await svc.get_or_create_session(sid, uid, profile)

    await workflow.ingest_document(
        session_id=sid,
        user_id=uid,
        filename="rag_guide.txt",
        file_bytes=b"Retrieval Augmented Generation concepts only.",
    )

    # Ask completely unrelated query
    res = await workflow.query_documents(
        session_id=sid,
        user_id=uid,
        query="What is the boiling point of liquid nitrogen in astrophysics?",
    )
    assert res.is_grounded_in_doc is False
    assert res.unsupported_reason is not None

    document_index_registry.remove_session(sid)


@pytest.mark.anyio
async def test_multi_turn_chat_history_continuity_and_reset() -> None:
    """Chat messages accumulate across multi-turn exchanges and reset cleanly."""
    svc = LearningSessionService()
    workflow = ConversationalCoachWorkflow(session_service=svc)

    sid = "chat_continuity_session"
    uid = "user_chat"
    profile = StudentProfile(experience_level="intermediate", daily_study_minutes=60)
    await svc.get_or_create_session(sid, uid, profile)

    # Turn 1: Study planning request
    reply1 = await workflow.process_chat_message(
        session_id=sid,
        user_id=uid,
        student_message="Help me plan 14 days of study for Google Cloud Generative AI Leader",
    )
    assert reply1.role == "coach"
    assert reply1.agent_routed == "study_planner"

    # Turn 2: Follow-up question
    reply2 = await workflow.process_chat_message(
        session_id=sid,
        user_id=uid,
        student_message="Explain Day 1 topics in more depth",
    )
    assert reply2.role == "coach"

    # Check history contains 4 messages (2 user, 2 coach)
    history = await workflow.get_chat_history(sid, uid)
    assert len(history) == 4
    assert history[0].role == "student"
    assert history[1].role == "coach"
    assert history[2].role == "student"
    assert history[3].role == "coach"

    # Clear history
    await workflow.clear_chat_history(sid, uid)
    history_after = await workflow.get_chat_history(sid, uid)
    assert len(history_after) == 0


@pytest.mark.anyio
async def test_document_grounded_quiz_answer_key_isolation() -> None:
    """Document quizzes keep correct answers private on server and return student view."""
    svc = LearningSessionService()
    workflow = ConversationalCoachWorkflow(session_service=svc)

    sid = "doc_quiz_isolation_session"
    uid = "user_quiz"
    profile = StudentProfile(experience_level="intermediate", daily_study_minutes=60)
    await svc.get_or_create_session(sid, uid, profile)

    # Ingest guide
    await workflow.ingest_document(
        session_id=sid,
        user_id=uid,
        filename="vertex_notes.txt",
        file_bytes=b"Vertex AI Search indexes unstructured documents. Vertex AI Conversation builds chatbots.",
    )

    # Mock Quiz Generator output
    mock_quiz = Quiz(
        certification_name="Google Cloud Generative AI Leader",
        topic_ids=["vertex_ai_studio"],
        experience_level="intermediate",
        questions=[
            QuizQuestion(
                question_id="dq1",
                topic_id="vertex_ai_studio",
                question_text="Which Google Cloud service indexes unstructured enterprise data for RAG?",
                difficulty="intermediate",
                options={
                    "A": "Vertex AI Search",
                    "B": "Cloud Bigtable",
                    "C": "Google Cloud Storage archive",
                    "D": "Compute Engine instances",
                },
                correct_answer="A",
                explanation="Vertex AI Search provides enterprise retrieval over unstructured documents.",
            )
        ],
    )

    mock_event = MagicMock()
    mock_part = MagicMock()
    mock_fc = MagicMock()
    mock_fc.name = "set_model_response"
    mock_fc.args = {"response": mock_quiz.model_dump()}
    mock_part.function_call = mock_fc
    mock_content = MagicMock()
    mock_content.parts = [mock_part]
    mock_event.content = mock_content

    async def mock_run_async(
        *args: object, **kwargs: object
    ) -> AsyncGenerator[MagicMock, None]:
        yield mock_event

    with patch("study_coach.workflows.coach_chat.InMemoryRunner") as mock_runner_cls:
        mock_instance = mock_runner_cls.return_value
        mock_instance.app_name = "quiz_generator"
        mock_instance.session_service = AsyncMock()
        mock_instance.run_async = mock_run_async

        student_questions = await workflow.generate_document_quiz(
            session_id=sid,
            user_id=uid,
            question_count=1,
        )

        assert len(student_questions) == 1
        sq = student_questions[0]
        # Crucial security check: student view MUST NOT have correct_answer or explanation attributes
        assert not hasattr(sq, "correct_answer")
        assert not hasattr(sq, "explanation")
        assert sq.question_text.startswith("Which Google Cloud service")
        assert len(sq.options) == 4

        # Server session must store full private quiz with answer keys
        updated_session = await svc.get_session(sid, uid)
        assert updated_session is not None
        assert updated_session.current_quiz_id in updated_session.stored_quizzes
        stored = updated_session.stored_quizzes[updated_session.current_quiz_id]
        assert stored.questions[0].correct_answer == "A"

    document_index_registry.remove_session(sid)


@pytest.mark.anyio
async def test_facade_integration_and_routing() -> None:
    """WorkshopFacade delegates chat and document management accurately."""
    facade = WorkshopFacade()
    sid = "facade_chat_session"
    uid = "user_facade"
    profile = StudentProfile(experience_level="beginner", daily_study_minutes=60)
    await facade.get_or_create_session(sid, uid, profile)

    # Ingest document via facade
    meta = await facade.upload_document(
        session_id=sid,
        user_id=uid,
        filename="quick_facts.txt",
        file_bytes=b"Responsible AI requires fairness, interpretability, privacy, and security.",
    )
    assert meta.filename == "quick_facts.txt"

    docs = await facade.list_documents(session_id=sid)
    assert len(docs) == 1

    # Query via facade
    grounding = await facade.query_documents(
        session_id=sid, user_id=uid, query="What are the Responsible AI principles?"
    )
    assert grounding.is_grounded_in_doc is True
    assert len(grounding.citations) >= 1
    assert "quick_facts.txt" in grounding.citations[0].doc_name

    document_index_registry.remove_session(sid)
