"""Streamlit UI component for Conversational Study Coach and Document RAG.

Provides:
- Multi-turn student/coach chat interface with message bubbles.
- Document upload control (PDF, DOCX, TXT, MD) with validation and size limits.
- Active documents list with delete capability.
- Exact source citations viewer (document, page, section, snippet).
- Interactive document quiz integration with server-side private answer keys.
- Clear/reset conversation capability.
"""

from collections.abc import Callable
from typing import Any, Literal, cast

import streamlit as st

from study_coach.models.document import ChatMessage, DocumentMetadata
from study_coach.models.quiz import QuizSubmission, StudentQuizQuestion
from study_coach.services.workshop_facade import WorkshopFacade


def render_study_coach_chat_tab(
    facade: WorkshopFacade,
    session_id: str,
    user_id: str,
    run_async_fn: Callable[[Any], Any],
) -> None:
    """Renders the Ask Study Coach & Document RAG tab in Streamlit."""
    st.header("💬 Ask Study Coach & Document AI")
    st.caption(
        "Chat with your AI Study Coach across multi-turn dialogues, ask grounded questions "
        "about uploaded certification study guides (PDF/DOCX), and generate document-based quizzes."
    )

    # Initialize chat UI state
    if f"chat_messages_{session_id}" not in st.session_state:
        st.session_state[f"chat_messages_{session_id}"] = []

    # 1. Document Management Area (Collapsible / Expander)
    with st.expander(
        "📄 Upload Certification Study Guides (PDF / DOCX)", expanded=False
    ):
        col_upload, col_list = st.columns([1, 1], gap="medium")

        with col_upload:
            st.markdown("##### Upload Study Guide")
            uploaded_file = st.file_uploader(
                "Choose a PDF, Word DOCX, or text file",
                type=["pdf", "docx", "txt", "md"],
                key=f"file_uploader_{session_id}",
                help="Uploaded files are session-isolated and processed locally into searchable text chunks.",
            )

            if uploaded_file is not None and st.button(
                "📥 Parse & Index Document", key=f"btn_parse_{session_id}"
            ):
                file_bytes = uploaded_file.getvalue()
                with st.spinner(f"Parsing and chunking '{uploaded_file.name}'..."):
                    try:
                        meta = run_async_fn(
                            facade.upload_document(
                                session_id=session_id,
                                user_id=user_id,
                                filename=uploaded_file.name,
                                file_bytes=file_bytes,
                            )
                        )
                        st.success(
                            f"Indexed **{meta.filename}** ({meta.total_chunks} chunks"
                            + (
                                f", {meta.total_pages} pages"
                                if meta.total_pages
                                else ""
                            )
                            + ")!"
                        )
                        st.rerun()
                    except Exception as err:  # noqa: BLE001
                        st.error(f"Failed to index document: {err}")

        with col_list:
            st.markdown("##### Active Session Documents")
            active_docs: list[DocumentMetadata] = run_async_fn(
                facade.list_documents(session_id=session_id)
            )

            if not active_docs:
                st.info(
                    "No documents uploaded yet. You can chat about the standard certification curriculum or upload a guide above."
                )
            else:
                for doc in active_docs:
                    c1, c2 = st.columns([3, 1])
                    with c1:
                        icon = (
                            "📕"
                            if doc.file_type == "pdf"
                            else ("📘" if doc.file_type == "docx" else "📄")
                        )
                        pages_str = (
                            f" • {doc.total_pages} pages" if doc.total_pages else ""
                        )
                        st.markdown(
                            f"**{icon} {doc.filename}**\n\n`{doc.total_chunks} chunks{pages_str}`"
                        )
                    with c2:
                        if st.button(
                            "🗑️",
                            key=f"del_{doc.doc_id}",
                            help="Remove document from index",
                        ):
                            run_async_fn(
                                facade.delete_document(session_id, user_id, doc.doc_id)
                            )
                            st.rerun()

                if st.button(
                    "📝 Quiz Me on Uploaded Guides",
                    key=f"btn_doc_quiz_{session_id}",
                    use_container_width=True,
                ):
                    with st.spinner(
                        "Generating 5-question practice quiz from your uploaded study guide..."
                    ):
                        try:
                            questions: list[StudentQuizQuestion] = run_async_fn(
                                facade.generate_document_quiz(
                                    session_id=session_id,
                                    user_id=user_id,
                                    question_count=5,
                                )
                            )
                            st.session_state[f"active_doc_quiz_{session_id}"] = (
                                questions
                            )
                            st.session_state[f"doc_quiz_submitted_{session_id}"] = False
                            st.session_state[f"doc_quiz_result_{session_id}"] = None
                            st.success("Quiz generated! Answer the questions below.")
                        except Exception as err:  # noqa: BLE001
                            st.error(f"Could not generate quiz: {err}")

    # 2. Render Document Quiz if Active
    if st.session_state.get(f"active_doc_quiz_{session_id}"):
        questions = st.session_state[f"active_doc_quiz_{session_id}"]
        st.markdown("---")
        st.markdown("### 📝 Interactive Document-Grounded Quiz")

        doc_selections: dict[str, str] = st.session_state.setdefault(
            f"doc_quiz_selections_{session_id}", {}
        )

        for i, q in enumerate(questions, start=1):
            st.markdown(f"**Question {i}:** {q.question_text}")
            opts = [f"{k}: {v}" for k, v in q.options.items()]
            chosen = st.radio(
                f"Select answer for Q{i}",
                opts,
                key=f"doc_q_radio_{session_id}_{q.question_id}",
                index=None,
                label_visibility="collapsed",
            )
            if chosen:
                doc_selections[q.question_id] = chosen.split(":", 1)[0].strip()

        col_sub, col_cancel = st.columns([1, 1])
        with col_sub:
            if st.button(
                "Submit Document Quiz Answers",
                key=f"sub_doc_quiz_{session_id}",
                type="primary",
            ):
                if len(doc_selections) < len(questions):
                    st.warning(
                        "Please select answers for all questions before submitting."
                    )
                else:
                    typed_answers: dict[str, Literal["A", "B", "C", "D"]] = {
                        k: cast(Literal["A", "B", "C", "D"], v)
                        for k, v in doc_selections.items()
                    }
                    submission = QuizSubmission(
                        quiz_id="default_quiz",
                        student_answers=typed_answers,
                    )
                    with st.spinner("Deterministically grading answers..."):
                        try:
                            res = run_async_fn(
                                facade.submit_quiz(session_id, user_id, submission)
                            )
                            st.session_state[f"doc_quiz_result_{session_id}"] = res
                            st.session_state[f"doc_quiz_submitted_{session_id}"] = True
                        except Exception as err:  # noqa: BLE001
                            st.error(f"Grading error: {err}")

        with col_cancel:
            if st.button("Close Quiz", key=f"close_doc_quiz_{session_id}"):
                st.session_state[f"active_doc_quiz_{session_id}"] = None
                st.session_state[f"doc_quiz_result_{session_id}"] = None
                st.rerun()

        # Display Result if submitted
        if st.session_state.get(f"doc_quiz_result_{session_id}"):
            res = st.session_state[f"doc_quiz_result_{session_id}"]
            st.success(
                f"**Score:** {res.correct_answers}/{res.total_questions} ({res.score_percentage:.1f}%)"
            )
            for fb in res.question_feedback:
                icon = "✅" if fb.is_correct else "❌"
                st.markdown(
                    f"**{icon} {fb.question_id}**: You answered `{fb.student_answer}`, Correct was `{fb.correct_answer}`.\n\n"
                    f"_{fb.explanation}_"
                )

    st.markdown("---")

    # 3. Chat Controls & History Display
    c_hdr, c_reset = st.columns([4, 1])
    with c_hdr:
        st.markdown("#### Conversation History")
    with c_reset:
        if st.button(
            "🔄 Clear Chat",
            key=f"clear_chat_{session_id}",
            help="Reset conversation history",
        ):
            run_async_fn(facade.clear_chat_history(session_id, user_id))
            st.session_state[f"chat_messages_{session_id}"] = []
            st.rerun()

    # Load conversation history from session
    history: list[ChatMessage] = run_async_fn(
        facade.get_chat_history(session_id, user_id)
    )

    if not history:
        st.chat_message("assistant").markdown(
            "👋 Hello! I am your **Google ADK Multi-Agent Study Coach**.\n\n"
            "Ask me anything! For example:\n"
            "- *'Explain Grounding and RAG with a practical Vertex AI example.'*\n"
            "- *'What does my uploaded study guide say about Transformer architectures?'*\n"
            "- *'Quiz me on the uploaded document.'*\n"
            "- *'Create a 14-day study plan with 60 minutes a day.'*"
        )
    else:
        for msg in history:
            role = "user" if msg.role == "student" else "assistant"
            with st.chat_message(role):
                if msg.agent_routed:
                    st.caption(f"🤖 Routed to `{msg.agent_routed}`")
                st.markdown(msg.content)

                # Render verifiable source citations
                if msg.citations:
                    with st.expander(
                        f"📚 Verified Source Citations ({len(msg.citations)})",
                        expanded=False,
                    ):
                        for cit in msg.citations:
                            page_info = (
                                f" • Page {cit.page_number}" if cit.page_number else ""
                            )
                            sec_info = (
                                f" • {cit.section_title}" if cit.section_title else ""
                            )
                            st.markdown(
                                f"**[{cit.doc_name}{page_info}{sec_info}]**\n\n"
                                f'> "{cit.snippet}"'
                            )

                if msg.follow_up_prompt:
                    st.info(f"💡 **Coach Follow-Up:** {msg.follow_up_prompt}")

    # 4. Chat Input Box
    prompt = st.chat_input(
        "Ask a certification or document question (e.g. 'What does my guide say about RAG?')...",
        key=f"chat_input_{session_id}",
    )
    if prompt:
        with st.chat_message("user"):
            st.markdown(prompt)

        with (
            st.chat_message("assistant"),
            st.spinner("Study Coach is thinking and consulting specialist agents..."),
        ):
            try:
                run_async_fn(
                    facade.send_chat_message(
                        session_id=session_id,
                        user_id=user_id,
                        message=prompt,
                    )
                )
                st.rerun()
            except Exception as err:  # noqa: BLE001
                st.error(f"Error communicating with Study Coach: {err}")
