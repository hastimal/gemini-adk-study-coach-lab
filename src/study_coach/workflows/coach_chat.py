"""Multi-turn Conversational Study Coach and Document RAG workflow.

Orchestrates multi-turn student/coach dialogues, Google ADK root coordinator routing,
session document indexing, citation generation, and document-grounded quizzing.
"""

import logging
from typing import Any

from google.adk.runners import InMemoryRunner
from google.genai import types

from study_coach.agent import root_agent
from study_coach.agents.document_agent import document_agent
from study_coach.agents.quiz_generator import quiz_generator
from study_coach.models.document import (
    ChatMessage,
    DocumentGroundingResult,
    DocumentMetadata,
)
from study_coach.models.quiz import Quiz, StudentQuizQuestion
from study_coach.observability import (
    CHAT_MESSAGES_TOTAL,
    DOCUMENT_OPERATIONS_TOTAL,
    DOCUMENT_RETRIEVAL_LATENCY_SECONDS,
    QUIZ_GENERATION_DURATION_SECONDS,
    ADKObservabilityPlugin,
    trace_workflow_step,
)
from study_coach.rag.index import document_index_registry
from study_coach.rag.parser import parse_uploaded_file
from study_coach.services.learning_session import LearningSessionService

logger = logging.getLogger(__name__)


class ConversationalCoachWorkflow:
    """Coordinates multi-turn conversations, Document AI RAG, and document quizzing."""

    def __init__(
        self,
        session_service: LearningSessionService | None = None,
        observability_plugin: ADKObservabilityPlugin | None = None,
    ) -> None:
        self.session_service = session_service or LearningSessionService()
        self.observability_plugin = observability_plugin or ADKObservabilityPlugin()

    # ==========================================================================
    # 1. DOCUMENT INGESTION & MANAGEMENT
    # ==========================================================================

    @trace_workflow_step(
        "ingest_document", workflow="document_rag", agent="document_agent"
    )
    async def ingest_document(
        self,
        session_id: str,
        user_id: str,
        filename: str,
        file_bytes: bytes,
    ) -> DocumentMetadata:
        """Parses, chunks, and indexes an uploaded PDF, DOCX, TXT, or MD study guide."""
        metadata, chunks = parse_uploaded_file(filename, file_bytes)

        index = document_index_registry.get_or_create(session_id)
        index.add_document(metadata, chunks)

        session = await self.session_service.get_session(session_id, user_id)
        if session:
            docs_meta = session.metadata.setdefault("uploaded_documents", {})
            docs_meta[metadata.doc_id] = metadata.model_dump(mode="json")
            await self.session_service.save_session(session)

        DOCUMENT_OPERATIONS_TOTAL.labels(
            operation="upload", file_type=metadata.file_type, status="success"
        ).inc()
        return metadata

    async def list_documents(self, session_id: str) -> list[DocumentMetadata]:
        """Lists all active uploaded documents for this session."""
        index = document_index_registry.get_index(session_id)
        if not index:
            return []
        return index.list_documents()

    async def delete_document(self, session_id: str, user_id: str, doc_id: str) -> bool:
        """Removes a document from the session index and session metadata."""
        index = document_index_registry.get_index(session_id)
        removed = index.remove_document(doc_id) if index else False

        session = await self.session_service.get_session(session_id, user_id)
        if session and "uploaded_documents" in session.metadata:
            session.metadata["uploaded_documents"].pop(doc_id, None)
            await self.session_service.save_session(session)

        DOCUMENT_OPERATIONS_TOTAL.labels(
            operation="delete", file_type="all", status="success"
        ).inc()
        return removed

    # ==========================================================================
    # 2. DOCUMENT RETRIEVAL & GROUNDING
    # ==========================================================================

    @trace_workflow_step(
        "query_document", workflow="document_rag", agent="document_agent"
    )
    async def query_documents(
        self,
        session_id: str,
        user_id: str,
        query: str,
        top_k: int = 4,
    ) -> DocumentGroundingResult:
        """Retrieves passages and generates a source-grounded response with citations."""
        index = document_index_registry.get_index(session_id)

        if not index or not index.chunks:
            return DocumentGroundingResult(
                query=query,
                answer=(
                    "No study guides or documents have been uploaded in this session yet. "
                    "Please upload a certification guide (PDF, DOCX, TXT, or MD) using the Document Upload panel above."
                ),
                is_grounded_in_doc=False,
                citations=[],
                follow_up_suggestions=[
                    "Upload a PDF or DOCX certification study guide",
                    "Ask a question from the standard certification syllabus",
                ],
                unsupported_reason="No documents indexed in active session.",
            )

        with DOCUMENT_RETRIEVAL_LATENCY_SECONDS.time():
            scored_chunks = index.search(query=query, top_k=top_k)

        if not scored_chunks:
            return DocumentGroundingResult(
                query=query,
                answer=(
                    f"The uploaded document(s) do not appear to contain relevant information answering '{query}'. "
                    "I can answer from general Google Cloud certification curriculum if you wish, or you can try a different search phrase."
                ),
                is_grounded_in_doc=False,
                citations=[],
                follow_up_suggestions=[
                    "Try broader terminology (e.g., 'Grounding', 'RAG', 'Vertex AI')",
                    "Ask for an explanation from the core curriculum",
                ],
                unsupported_reason="No matching passages found in uploaded documents.",
            )

        citations = index.build_citations(scored_chunks)

        # Build grounded prompt for Document Agent
        passages_text = "\n\n".join(
            [
                f"[Doc: {c.doc_name} | {c.section_title or ('Page ' + str(c.page_number))}]\n{c.content}"
                for c, _ in scored_chunks
            ]
        )

        resp_dict: dict[str, Any] | None = None
        try:
            runner = InMemoryRunner(
                agent=document_agent, plugins=[self.observability_plugin]
            )
            sub_session_id = f"doc_query_{session_id}_{len(citations)}"
            await runner.session_service.create_session(
                app_name=runner.app_name,
                user_id=user_id,
                session_id=sub_session_id,
            )

            prompt = (
                f"Student Query: {query}\n\n"
                f"Retrieved Passages from Uploaded Study Guides:\n{passages_text}\n\n"
                "Provide a comprehensive, factual answer based strictly on the retrieved passages. "
                "List exact citations for each factual claim. If anything cannot be answered from the passages, "
                "explicitly state so."
            )

            async for event in runner.run_async(
                user_id=user_id,
                session_id=sub_session_id,
                new_message=types.Content(
                    role="user",
                    parts=[types.Part.from_text(text=prompt)],
                ),
            ):
                if event.content and event.content.parts:
                    for part in event.content.parts:
                        fc = getattr(part, "function_call", None)
                        if fc and fc.name == "set_model_response" and fc.args:
                            resp_dict = fc.args.get("response") or fc.args
        except Exception as exc:  # noqa: BLE001
            logger.info(
                "Document agent LLM run unavailable (%s); using deterministic grounded fallback.",
                exc,
            )

        if not resp_dict:
            # Fallback deterministic grounded result if LLM structured extraction is interrupted
            combined_answer = (
                f"Based on your uploaded guide ('{scored_chunks[0][0].doc_name}'):\n\n"
                + scored_chunks[0][0].content[:600]
            )
            return DocumentGroundingResult(
                query=query,
                answer=combined_answer,
                is_grounded_in_doc=True,
                citations=citations,
                follow_up_suggestions=[
                    "Would you like a quiz on this chapter?",
                    "Should we generate a study plan activity for this topic?",
                ],
            )

        grounding_result = DocumentGroundingResult.model_validate(resp_dict)
        # Ensure our verified exact citations are preserved
        if not grounding_result.citations and citations:
            grounding_result = grounding_result.model_copy(
                update={"citations": citations}
            )
        return grounding_result

    # ==========================================================================
    # 3. DOCUMENT-GROUNDED QUIZ GENERATION
    # ==========================================================================

    @trace_workflow_step(
        "generate_document_quiz", workflow="document_quiz", agent="quiz_generator"
    )
    async def generate_document_quiz(
        self,
        session_id: str,
        user_id: str,
        question_count: int = 5,
        target_doc_id: str | None = None,
        experience_level: str = "intermediate",
    ) -> list[StudentQuizQuestion]:
        """Generates multiple-choice quiz questions grounded strictly in uploaded study guides."""
        index = document_index_registry.get_index(session_id)
        if not index or not index.chunks:
            raise ValueError(
                "No documents uploaded or indexed in this session. Please upload a study guide before requesting a document quiz."
            )

        chunks_pool = (
            [c for c in index.chunks if c.doc_id == target_doc_id]
            if target_doc_id
            else index.chunks
        )
        if not chunks_pool:
            raise ValueError(f"No content found for document '{target_doc_id}'.")

        # Select representative chunks across the document
        stride = max(1, len(chunks_pool) // max(question_count, 1))
        sampled_chunks = chunks_pool[::stride][: max(question_count, 1) + 2]
        doc_context = "\n\n".join(
            [
                f"[Source: {c.doc_name} | {c.section_title or ('Page ' + str(c.page_number))}]\n{c.content[:400]}"
                for c in sampled_chunks
            ]
        )

        session = await self.session_service.get_session(session_id, user_id)
        if not session:
            raise ValueError(f"Session '{session_id}' not found.")

        prompt = (
            f"Generate a {question_count}-question multiple choice practice quiz strictly grounded "
            f"in the following uploaded study guide content:\n\n{doc_context}\n\n"
            f"Requirements:\n"
            f"1. Exactly {question_count} questions, 4 options each (A, B, C, D).\n"
            f"2. Each question must be answerable using only the provided guide excerpt.\n"
            f"3. In the explanation for each question, include the document name and section/page source.\n"
            f"4. Difficulty: {experience_level}."
        )

        runner = InMemoryRunner(
            agent=quiz_generator, plugins=[self.observability_plugin]
        )
        quiz_session_id = f"{session_id}_doc_quiz_{len(session.stored_quizzes) + 1}"
        await runner.session_service.create_session(
            app_name=runner.app_name,
            user_id=user_id,
            session_id=quiz_session_id,
        )

        quiz_dict: dict[str, Any] | None = None
        with QUIZ_GENERATION_DURATION_SECONDS.labels(quiz_type="document_quiz").time():
            async for event in runner.run_async(
                user_id=user_id,
                session_id=quiz_session_id,
                new_message=types.Content(
                    role="user",
                    parts=[types.Part.from_text(text=prompt)],
                ),
            ):
                if event.content and event.content.parts:
                    for part in event.content.parts:
                        fc = getattr(part, "function_call", None)
                        if fc and fc.name == "set_model_response" and fc.args:
                            quiz_dict = fc.args.get("response") or fc.args

        if not quiz_dict:
            raise RuntimeError(
                "Quiz Generator did not return a structured Quiz from uploaded document content"
            )

        validated_quiz = Quiz.model_validate(quiz_dict)
        quiz_id = f"doc_quiz_{len(session.stored_quizzes) + 1}"

        # Securely store in private session state (answer keys never leaked to student)
        session.stored_quizzes[quiz_id] = validated_quiz
        session.current_quiz_id = quiz_id
        await self.session_service.save_session(session)

        return validated_quiz.to_student_view()

    # ==========================================================================
    # 4. MULTI-TURN CONVERSATIONAL COACH CHAT
    # ==========================================================================

    @trace_workflow_step(
        "process_chat_message",
        workflow="conversational_chat",
        agent="study_coach",
    )
    async def process_chat_message(
        self,
        session_id: str,
        user_id: str,
        student_message: str,
    ) -> ChatMessage:
        """Processes student chat turn, routes to specialist ADK agents, and maintains continuity."""
        session = await self.session_service.get_session(session_id, user_id)
        if not session:
            raise ValueError(f"Session '{session_id}' not found.")

        # Record incoming student message in session metadata history
        history: list[dict[str, Any]] = session.metadata.setdefault("chat_history", [])
        history.append(
            ChatMessage(role="student", content=student_message).model_dump(mode="json")
        )
        CHAT_MESSAGES_TOTAL.labels(role="student", routed_agent="coordinator").inc()

        # Intent routing heuristic
        lower = student_message.lower().strip()
        session_idx = document_index_registry.get_index(session_id)
        has_docs = bool(session_idx is not None and session_idx.chunks)

        is_doc_query = (
            has_docs
            and any(
                k in lower
                for k in [
                    "document",
                    "guide",
                    "pdf",
                    "docx",
                    "chapter",
                    "notes",
                    "uploaded",
                    "page",
                    "according to",
                ]
            )
        ) or (
            has_docs
            and not any(
                k in lower
                for k in [
                    "plan",
                    "schedule",
                    "days remaining",
                    "generate quiz",
                    "quiz me on",
                ]
            )
        )

        is_quiz_query = any(
            k in lower
            for k in [
                "quiz",
                "test me",
                "practice questions",
                "exam questions",
                "quick check",
            ]
        )
        is_plan_query = any(
            k in lower
            for k in ["plan", "schedule", "replan", "days remaining", "budget"]
        )

        if is_doc_query and not is_quiz_query:
            # Route to Document Agent
            grounding = await self.query_documents(
                session_id=session_id, user_id=user_id, query=student_message
            )
            coach_reply = ChatMessage(
                role="coach",
                content=grounding.answer,
                agent_routed="document_agent",
                citations=grounding.citations,
                follow_up_prompt=(
                    grounding.follow_up_suggestions[0]
                    if grounding.follow_up_suggestions
                    else None
                ),
            )
        elif is_quiz_query and has_docs and "document" in lower:
            # Document quiz request
            await self.generate_document_quiz(
                session_id=session_id,
                user_id=user_id,
                question_count=5,
                experience_level=session.student_profile.experience_level,
            )
            qid = session.current_quiz_id
            coach_reply = ChatMessage(
                role="coach",
                content=(
                    f"I have created a 5-question practice quiz grounded in your uploaded study guide! "
                    f"Quiz ID: `{qid}`. You can take it in the interactive quiz card below."
                ),
                agent_routed="quiz_generator",
                quiz_id=qid,
                follow_up_prompt="Submit your answers when ready, and I will grade them deterministically!",
            )
        else:
            # Route through Google ADK Root Coordinator
            runner = InMemoryRunner(
                agent=root_agent, plugins=[self.observability_plugin]
            )
            adk_chat_sid = f"chat_{session_id}"
            try:
                await runner.session_service.create_session(
                    app_name=runner.app_name,
                    user_id=user_id,
                    session_id=adk_chat_sid,
                )
            except Exception:  # noqa: BLE001, S110
                pass  # Session may already exist in InMemorySessionService

            reply_text = ""
            try:
                async for event in runner.run_async(
                    user_id=user_id,
                    session_id=adk_chat_sid,
                    new_message=types.Content(
                        role="user",
                        parts=[types.Part.from_text(text=student_message)],
                    ),
                ):
                    if event.content and event.content.parts:
                        for part in event.content.parts:
                            text = getattr(part, "text", "")
                            if text:
                                reply_text += text
            except Exception as exc:  # noqa: BLE001
                logger.info(
                    "Root coordinator ADK runner unavailable (%s); using deterministic guidance reply.",
                    exc,
                )

            if not reply_text:
                reply_text = (
                    "I am here to guide your certification journey! You can ask me to create a personalized "
                    "study plan, explain any syllabus topic with Google Cloud examples, generate practice quizzes, "
                    "or upload a PDF/DOCX study guide for grounded questions."
                )

            routed = (
                "study_planner"
                if is_plan_query
                else ("quiz_generator" if is_quiz_query else "topic_expert")
            )
            coach_reply = ChatMessage(
                role="coach",
                content=reply_text,
                agent_routed=routed,
                follow_up_prompt=(
                    "Would you like a formative quick check or further clarification on this?"
                ),
            )

        history.append(coach_reply.model_dump(mode="json"))
        await self.session_service.save_session(session)
        CHAT_MESSAGES_TOTAL.labels(
            role="coach", routed_agent=coach_reply.agent_routed or "coordinator"
        ).inc()
        return coach_reply

    async def get_chat_history(
        self, session_id: str, user_id: str
    ) -> list[ChatMessage]:
        """Returns the full ordered list of conversation messages."""
        session = await self.session_service.get_session(session_id, user_id)
        if not session:
            return []
        raw_msgs = session.metadata.get("chat_history", [])
        return [ChatMessage.model_validate(m) for m in raw_msgs]

    async def clear_chat_history(self, session_id: str, user_id: str) -> None:
        """Resets the conversation history for the active session."""
        session = await self.session_service.get_session(session_id, user_id)
        if session and "chat_history" in session.metadata:
            session.metadata["chat_history"] = []
            await self.session_service.save_session(session)
