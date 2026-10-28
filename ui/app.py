"""Streamlit Workshop Web Application for Gemini ADK Study Coach."""

import asyncio
import os
import sys
import uuid
from pathlib import Path
from typing import Any, Literal, cast

# Ensure project root and src are reliably on sys.path for direct streamlit execution
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import streamlit as st
from dotenv import load_dotenv

from study_coach.evaluation import EvaluationRunner
from study_coach.models.quiz import QuizResult, QuizSubmission
from study_coach.models.student import StudentProfile
from study_coach.observability import setup_tracing, start_metrics_server
from study_coach.services.workshop_facade import WorkshopFacade
from ui.components import (
    render_agent_ops_tab,
    render_evaluations_tab,
    render_resource_grid,
    render_study_coach_chat_tab,
)

# Load environment configuration
load_dotenv()

# Initialize optional observability gracefully
setup_tracing()
start_metrics_server()

st.set_page_config(
    page_title="Gemini ADK Study Coach Lab",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded",
)


def run_async(coro: Any) -> Any:
    """Helper to run async facade methods inside synchronous Streamlit execution."""
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    if loop.is_running():
        # Inside an active loop, run in a new sub-thread or runner
        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor() as pool:
            return pool.submit(asyncio.run, coro).result()
    return loop.run_until_complete(coro)


# Initialize persistent Facade in Streamlit session state

if "facade" not in st.session_state:
    st.session_state.facade = WorkshopFacade()

if "session_id" not in st.session_state:
    st.session_state.session_id = f"sess_{uuid.uuid4().hex[:8]}"

if "user_id" not in st.session_state:
    st.session_state.user_id = f"student_{uuid.uuid4().hex[:6]}"

if "preselected_quiz_topic" not in st.session_state:
    st.session_state.preselected_quiz_topic = None

# M6-G Formative Quick Check state
if "quick_check_quiz_id" not in st.session_state:
    st.session_state.quick_check_quiz_id = None
if "quick_check_questions" not in st.session_state:
    st.session_state.quick_check_questions = None
if "quick_check_selections" not in st.session_state:
    st.session_state.quick_check_selections = {}
if "quick_check_result" not in st.session_state:
    st.session_state.quick_check_result = None
if "selected_topic_id" not in st.session_state:
    st.session_state.selected_topic_id = None
if "_prev_quick_check_topic_id" not in st.session_state:
    st.session_state._prev_quick_check_topic_id = None
if "eval_runner" not in st.session_state:
    st.session_state.eval_runner = EvaluationRunner()

eval_runner: EvaluationRunner = st.session_state.eval_runner
facade: WorkshopFacade = st.session_state.facade
session_id: str = st.session_state.session_id
user_id: str = st.session_state.user_id

# Header
st.title("🎓 Gemini + Google ADK Multi-Agent Study Coach")
st.caption(
    "Interactive, visual, evidence-linked certification preparation powered by Gemini, "
    "Google Agent Development Kit (ADK), and deterministic Python grading."
)

# Sidebar: Student Configuration
with st.sidebar:
    st.header("⚙️ Student Setup")
    certification_name = st.selectbox(
        "Target Certification",
        ["Google Cloud Generative AI Leader"],
        index=0,
    )
    raw_exp = st.selectbox(
        "Experience Level",
        ["beginner", "intermediate", "advanced"],
        index=0,
    )
    experience_level: Literal["beginner", "intermediate", "advanced"] = cast(
        Literal["beginner", "intermediate", "advanced"], raw_exp
    )
    days_until_exam = st.number_input(
        "Study Days Remaining",
        min_value=1,
        max_value=90,
        value=14,
        step=1,
    )
    daily_study_minutes = st.number_input(
        "Daily Study Budget (Minutes)",
        min_value=15,
        max_value=240,
        value=90,
        step=15,
    )

    if st.button("🚀 Start / Reset Session", use_container_width=True):
        profile = StudentProfile(
            experience_level=experience_level,
            daily_study_minutes=int(daily_study_minutes),
        )
        run_async(
            facade.get_or_create_session(
                session_id=session_id,
                user_id=user_id,
                student_profile=profile,
                certification_name=certification_name,
                days_remaining=int(days_until_exam),
            )
        )
        st.session_state.active_quiz = None
        st.session_state.active_quiz_result = None
        st.session_state.explained_topic = None
        st.session_state.preselected_quiz_topic = None
        st.success(f"Session started! (ID: {session_id})")

    st.divider()
    st.markdown("**Session Info:**")
    st.text(f"Session ID: {session_id}")
    st.text(f"User ID: {user_id}")

    # Check API key status safely without printing secret
    has_api_key = bool(os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY"))
    if has_api_key:
        st.success("API Key: Configured")
    else:
        st.warning("API Key: Not Found in .env")

# Load curriculum topics and mapping
curriculum_topics = facade.get_supported_curriculum_topics()
topic_map = {f"{t['title']} ({t['id']})": t["id"] for t in curriculum_topics}


def navigate_to_practice_quiz_callback(target_topic_id: str) -> None:
    """Preselects topic and directly opens the Practice Quiz tab."""
    st.session_state.preselected_quiz_topic = target_topic_id
    st.session_state.main_nav_tab = "📝 Practice Quiz"
    for label, tid in topic_map.items():
        if tid == target_topic_id:
            st.session_state["quiz_topic_select"] = label
            break


# Navigation Tabs
MAIN_NAV_OPTIONS = [
    "💬 Ask Study Coach",
    "📅 Study Plan",
    "📖 Learn Topic",
    "📝 Practice Quiz",
    "🔄 Adaptive Plan",
    "🔭 Agent Ops",
    "🧪 Evaluations",
]

# Query param direct navigation support
TAB_QUERY_PARAM_MAP: dict[str, str] = {
    "chat": "💬 Ask Study Coach",
    "ask": "💬 Ask Study Coach",
    "coach": "💬 Ask Study Coach",
    "rag": "💬 Ask Study Coach",
    "doc": "💬 Ask Study Coach",
    "plan": "📅 Study Plan",
    "study_plan": "📅 Study Plan",
    "learn": "📖 Learn Topic",
    "topic": "📖 Learn Topic",
    "quiz": "📝 Practice Quiz",
    "practice": "📝 Practice Quiz",
    "adaptive": "🔄 Adaptive Plan",
    "ops": "🔭 Agent Ops",
    "agent_ops": "🔭 Agent Ops",
    "observability": "🔭 Agent Ops",
    "eval": "🧪 Evaluations",
    "evals": "🧪 Evaluations",
    "evaluations": "🧪 Evaluations",
}

requested_tab_param = st.query_params.get("tab", "").strip().lower()
if requested_tab_param in TAB_QUERY_PARAM_MAP:
    target_tab_label = TAB_QUERY_PARAM_MAP[requested_tab_param]
    if st.session_state.get("_last_synced_query_tab") != requested_tab_param:
        st.session_state.main_nav_tab = target_tab_label
        st.session_state._last_synced_query_tab = requested_tab_param

tab_chat, tab_plan, tab_learn, tab_quiz, tab_adaptive, tab_ops, tab_evals = st.tabs(
    MAIN_NAV_OPTIONS,
    key="main_nav_tab",
    on_change="rerun",
)

# Fetch current session state
current_session = run_async(facade.get_session(session_id, user_id))

# ==============================================================================
# TAB 0: ASK STUDY COACH (CONVERSATIONAL AI + DOCUMENT RAG)
# ==============================================================================
with tab_chat:
    render_study_coach_chat_tab(
        facade=facade,
        session_id=session_id,
        user_id=user_id,
        run_async_fn=run_async,
    )

# ==============================================================================
# TAB 1: STUDY PLAN
# ==============================================================================
with tab_plan:
    st.header("📅 Personalized Certification Study Plan")
    st.write(
        "The Study Planner agent crafts a day-by-day roadmap aligned with curriculum objectives "
        "and validates that daily limits are strictly respected."
    )

    col1, col2 = st.columns([1, 3])
    with col1:
        if st.button("Generate Initial Plan", type="primary", use_container_width=True):
            profile = StudentProfile(
                experience_level=experience_level,
                daily_study_minutes=int(daily_study_minutes),
            )
            with st.spinner("Invoking Study Planner agent via Google ADK..."):
                try:
                    plan = run_async(
                        facade.create_study_plan(
                            session_id=session_id,
                            user_id=user_id,
                            student_profile=profile,
                            certification_name=certification_name,
                            days_until_exam=int(days_until_exam),
                        )
                    )
                    st.success("Study plan successfully generated!")
                    current_session = run_async(facade.get_session(session_id, user_id))
                except (RuntimeError, ValueError) as err:
                    st.error(f"Error generating study plan: {err}")

    if current_session and current_session.current_study_plan:
        plan = current_session.current_study_plan
        st.subheader(
            f"Active Schedule: {plan.days_until_exam} Days ({plan.total_planned_minutes} Total Planned Minutes)"
        )
        st.info(f"**Planning Notes:** {plan.planning_notes}")

        # Day selector
        day_options = [f"Day {d.day_number}: {d.title}" for d in plan.days]
        selected_day_idx = st.selectbox(
            "Select a day to view its detailed activities:",
            range(len(plan.days)),
            format_func=lambda i: day_options[i],
        )

        selected_day = plan.days[selected_day_idx]
        st.markdown(f"### Details for {day_options[selected_day_idx]}")
        st.write(
            f"**Allocated Core Time:** {selected_day.total_minutes} / {plan.daily_study_minutes} minutes"
        )

        st.markdown("#### 📌 Core Planned Activities")
        day_topic_ids: list[str] = []
        for act in selected_day.activities:
            if act.topic_id and act.topic_id not in day_topic_ids:
                day_topic_ids.append(act.topic_id)
            with st.container(border=True):
                st.markdown(
                    f"**Topic:** `{act.topic_id}` | **Type:** `{act.activity_type}`"
                )
                st.write(act.description)
                st.caption(f"⏱️ Allocated: {act.duration_minutes} minutes")

        # Matched Learning Resources for Selected Day
        day_resources = facade.get_day_resources(day_topic_ids)
        if day_resources:
            st.markdown(
                f"#### 📚 Curated Learning Resources for Day {selected_day.day_number}"
            )
            st.info(
                "💡 **Study Budget Notice:** External resources are optional enrichment with independent "
                "time estimates and do **not** silently inflate your daily study budget."
            )
            render_resource_grid(day_resources, columns=2)
    else:
        st.info(
            "No active study plan found. Click 'Generate Initial Plan' above to start."
        )

# ==============================================================================
# TAB 2: LEARN TOPIC
# ==============================================================================
with tab_learn:
    st.header("📖 Interactive Topic Learning Experience")
    st.write(
        "Structured multi-modal lessons featuring curriculum objectives, visual diagrams, "
        "step-by-step explanations, runnable Python demos, and verified external learning resources."
    )

    topics = facade.get_supported_curriculum_topics()
    topic_map = {f"{t['title']} ({t['id']})": t["id"] for t in topics}

    selected_topic_label = st.selectbox(
        "Select Curriculum Topic", list(topic_map.keys())
    )
    chosen_topic_id = topic_map[selected_topic_label]

    if st.button("Teach This Topic", type="primary"):
        with st.spinner(
            "Topic Expert agent is generating explanation grounded in curriculum..."
        ):
            try:
                explanation = run_async(
                    facade.explain_topic(
                        topic_id=chosen_topic_id,
                        experience_level=experience_level,
                    )
                )
                st.session_state.explained_topic = explanation
                st.success("Topic explanation loaded!")
            except (RuntimeError, ValueError) as err:
                st.error(f"Error fetching topic explanation: {err}")

    if st.session_state.get("explained_topic"):
        exp = st.session_state.explained_topic
        chosen_topic_id = exp.topic_id
        st.markdown(f"## {exp.topic_title} (`{exp.topic_id}`)")
        st.caption(
            f"Adapted Level: **{exp.experience_level.capitalize()}** | Official Exam Domain: Google Cloud Generative AI Leader"
        )

        # Progressive Disclosure: Tabs for Structured Multi-Modal Learning
        learn_subtabs = st.tabs(
            [
                "🎯 Summary & Objectives",
                "📊 Architecture Diagram",
                "📘 Step-by-Step Lesson",
                "💻 Hands-On Python",
                "🌐 Verified Resources",
                "🚀 Practice & Share",
            ]
        )

        with learn_subtabs[0]:
            st.markdown("### 🎯 Learning Objectives")
            for obj in exp.learning_objectives:
                st.markdown(f"- {obj}")

            st.markdown("### 💡 Key Concepts & Vocabulary")
            st.write(", ".join(f"`{c}`" for c in exp.key_concepts))

        with learn_subtabs[1]:
            diagram = facade.get_topic_diagram(chosen_topic_id)
            if diagram:
                st.markdown(f"### 📊 {diagram.title}")
                st.caption(diagram.description)

                # Render Streamlit-native Mermaid diagram
                st.markdown(f"```mermaid\n{diagram.mermaid_code}\n```")

                with st.expander(
                    "🔍 Architecture Breakdown & Component Roles", expanded=True
                ):
                    for comp, role in diagram.components.items():
                        st.markdown(f"- **{comp}**: {role}")

                with st.expander("📝 Accessible Text Alternative (Fallback)"):
                    st.text(diagram.text_alternative)
            else:
                st.info(
                    "Conceptual architecture diagram is in preparation for this topic."
                )

        with learn_subtabs[2]:
            st.markdown("### 📘 In-Depth Technical Explanation")
            st.write(exp.explanation)

            st.markdown("### ☁️ Practical Google Cloud Architecture Example")
            st.info(exp.practical_example)

            st.markdown("### ⚠️ Common Misconceptions & Pitfalls")
            for m in exp.common_misconceptions:
                st.warning(m)

        with learn_subtabs[3]:
            code_examples = facade.get_topic_code_examples(chosen_topic_id)
            if code_examples:
                st.markdown("### 💻 Practical Python Examples")
                st.caption(
                    "Curated, self-contained, beginner-friendly runnable examples. Zero credentials or cloud charges required."
                )
                for c_ex in code_examples:
                    with st.container(border=True):
                        st.markdown(f"#### {c_ex.title}")
                        st.caption(
                            f"🏷️ Type: **{c_ex.example_type}** | Credentials Required: **{c_ex.requires_credentials}**"
                        )
                        st.write(c_ex.description)
                        st.code(c_ex.code, language="python")
                        st.markdown("**Expected Output:**")
                        st.code(c_ex.expected_output)
            else:
                st.info(
                    "Interactive Python example is available in the Hands-on lab library."
                )

        with learn_subtabs[4]:
            st.markdown("### 🌐 Curated Free Learning Resources")
            st.caption(
                "Strictly verified free documentation, video explanations, and interactive guides."
            )
            topic_res = facade.get_topic_resources(chosen_topic_id)
            if topic_res:
                render_resource_grid(topic_res, columns=2)
            else:
                st.info("Resources catalog currently being populated for this topic.")

        with learn_subtabs[5]:
            st.markdown("### 🚀 Practice & Share")
            st.write(
                "Reinforce your understanding with an interactive 3-question Quick Knowledge Check, "
                "or jump directly to a full 5-question formal practice quiz evaluated deterministically in Python."
            )

            # Invalidate stale quick check state only when topic actually changes
            prev_topic = st.session_state.get("_prev_quick_check_topic_id")
            if prev_topic is not None and prev_topic != chosen_topic_id:
                st.session_state.quick_check_quiz_id = None
                st.session_state.quick_check_questions = None
                st.session_state.quick_check_selections = {}
                st.session_state.quick_check_result = None
            st.session_state._prev_quick_check_topic_id = chosen_topic_id

            st.session_state.selected_topic_id = chosen_topic_id

            col_qc_left, col_qc_right = st.columns([1, 1], gap="medium")

            # ------------------------------------------------------------------
            # LEFT: Quick Knowledge Check (3 MCQs)
            # ------------------------------------------------------------------
            with col_qc_left, st.container(border=True):
                st.markdown("#### ⚡ Quick Knowledge Check (3 MCQs)")
                st.caption(
                    "Formative self-assessment crafted by the Quiz Generator agent and Gemini. "
                    "Deterministically scored in pure Python; answer keys remain protected on the backend."
                )

                qc_questions = st.session_state.get("quick_check_questions")
                qc_id = st.session_state.get("quick_check_quiz_id")
                qc_result: QuizResult | None = st.session_state.get(
                    "quick_check_result"
                )

                if not qc_questions:
                    st.info(
                        f"Generate a 3-question formative check tailored for **{chosen_topic_id}** "
                        f"at the **{experience_level}** level."
                    )
                    btn_gen_col, btn_full_col = st.columns([1, 1])
                    with btn_gen_col:
                        if st.button(
                            "⚡ Generate Quick Check",
                            type="primary",
                            use_container_width=True,
                            key=f"btn_gen_qc_{chosen_topic_id}",
                        ):
                            with st.spinner(
                                "Quiz Generator agent is creating 3 original MCQs with Gemini..."
                            ):
                                try:
                                    q_id, student_qs = run_async(
                                        facade.generate_quick_check(
                                            session_id=session_id,
                                            user_id=user_id,
                                            topic_id=chosen_topic_id,
                                            experience_level=experience_level,
                                        )
                                    )
                                    st.session_state.quick_check_quiz_id = q_id
                                    st.session_state.quick_check_questions = student_qs
                                    st.session_state.quick_check_selections = {}
                                    st.session_state.quick_check_result = None
                                    st.rerun()
                                except (RuntimeError, ValueError) as err:
                                    st.error(f"Error generating quick check: {err}")
                    with btn_full_col:
                        st.button(
                            "📝 Start Practice Quiz",
                            use_container_width=True,
                            key=f"btn_nav_quiz_init_{chosen_topic_id}",
                            on_click=navigate_to_practice_quiz_callback,
                            args=(chosen_topic_id,),
                        )
                else:
                    # Render the 3 interactive questions
                    st.markdown(
                        f"**Topic:** `{chosen_topic_id}` | **Items:** 3 Questions"
                    )

                    opt_letters = ["A", "B", "C", "D"]
                    for idx, q in enumerate(qc_questions, 1):
                        st.markdown(f"**Question {idx}:** {q.question_text}")
                        radio_key = f"qc_radio_{qc_id}_{q.question_id}"
                        prev_sel = st.session_state.quick_check_selections.get(
                            q.question_id
                        )
                        sel_index = (
                            opt_letters.index(prev_sel)
                            if prev_sel in opt_letters
                            else None
                        )

                        chosen_letter = st.radio(
                            label=f"Choice for question {idx}",
                            options=opt_letters,
                            format_func=lambda letter, q=q: (
                                f"{letter}) {q.options.get(letter, '')}"
                            ),
                            index=sel_index,
                            key=radio_key,
                            disabled=bool(qc_result),
                            label_visibility="collapsed",
                        )

                        if chosen_letter and not qc_result:
                            st.session_state.quick_check_selections[q.question_id] = (
                                chosen_letter
                            )

                        # If graded, render immediate question feedback
                        if qc_result:
                            fb = next(
                                (
                                    f
                                    for f in qc_result.question_feedback
                                    if f.question_id == q.question_id
                                ),
                                None,
                            )
                            if fb:
                                if fb.is_correct:
                                    st.success(
                                        f"✅ **Correct!** (Answer: **{fb.correct_answer}**)\n\n"
                                        f"{fb.explanation}"
                                    )
                                else:
                                    student_ans_str = fb.student_answer or "Unanswered"
                                    st.error(
                                        f"❌ **Incorrect.** (You selected: **{student_ans_str}** | Correct: **{fb.correct_answer}**)\n\n"
                                        f"{fb.explanation}"
                                    )

                    st.divider()

                    # Submission & Results Display
                    if not qc_result:
                        unanswered_count = len(qc_questions) - len(
                            st.session_state.quick_check_selections
                        )
                        if unanswered_count > 0:
                            st.caption(
                                f"ℹ️ {unanswered_count} question(s) unselected (unanswered questions count as incorrect)."
                            )

                        if st.button(
                            "✅ Submit / Check Answers",
                            type="primary",
                            use_container_width=True,
                            key=f"btn_submit_qc_{qc_id}",
                        ):
                            sub = QuizSubmission(
                                quiz_id=str(qc_id),
                                student_answers=dict(
                                    st.session_state.quick_check_selections
                                ),
                            )
                            with st.spinner(
                                "Scoring answers deterministically in pure Python..."
                            ):
                                try:
                                    res = run_async(
                                        facade.evaluate_quick_check(
                                            session_id=session_id,
                                            user_id=user_id,
                                            submission=sub,
                                        )
                                    )
                                    st.session_state.quick_check_result = res
                                    st.rerun()
                                except (RuntimeError, ValueError) as err:
                                    st.error(f"Error evaluating quick check: {err}")
                    else:
                        # Display Formative Score Banner
                        pct = qc_result.score_percentage
                        if pct >= 70.0:
                            st.success(
                                f"🎯 **Quick Check Score: {pct:.1f}%** "
                                f"({qc_result.correct_answers}/{qc_result.total_questions} correct)"
                            )
                        else:
                            st.warning(
                                f"💡 **Quick Check Score: {pct:.1f}%** "
                                f"({qc_result.correct_answers}/{qc_result.total_questions} correct)"
                            )

                        st.caption(
                            "🔒 **Formative isolation:** This check reinforces learning and does not alter "
                            "formal quiz records, weak-topic classification, or adaptive plans."
                        )

                        qc_btn_col1, qc_btn_col2 = st.columns(2)
                        with qc_btn_col1:
                            if st.button(
                                "🔄 Retry Quick Check",
                                use_container_width=True,
                                key=f"btn_retry_qc_{qc_id}",
                            ):
                                st.session_state.quick_check_quiz_id = None
                                st.session_state.quick_check_questions = None
                                st.session_state.quick_check_selections = {}
                                st.session_state.quick_check_result = None
                                st.rerun()
                        with qc_btn_col2:
                            st.button(
                                "📝 Start Full Practice Quiz",
                                type="primary",
                                use_container_width=True,
                                key=f"btn_nav_quiz_after_{qc_id}",
                                on_click=navigate_to_practice_quiz_callback,
                                args=(chosen_topic_id,),
                            )

            # ------------------------------------------------------------------
            # RIGHT: Share My Learning
            # ------------------------------------------------------------------
            with col_qc_right, st.container(border=True):
                st.markdown("#### 📢 Share My Learning")
                st.caption(
                    "Broadcast your progress on LinkedIn to celebrate study milestones."
                )

                default_share_text = (
                    f"I'm learning about '{exp.topic_title}' as part of my preparation for the "
                    f"{certification_name} certification with Gemini & Google ADK Study Coach!\n\n"
                    f"#GoogleCloud #GenerativeAI #StudyCoach #GeminiADK #ContinuousLearning"
                )

                share_post_text = st.text_area(
                    "LinkedIn Post Preview (Editable):",
                    value=default_share_text,
                    height=125,
                    key=f"share_preview_{chosen_topic_id}",
                )

                st.markdown("**Copy Post Text:**")
                st.code(share_post_text, language="markdown")

                st.link_button(
                    "🌐 Open LinkedIn Post Editor",
                    "https://www.linkedin.com/sharing/share-offsite/?url=https://cloud.google.com/learn/certification/generative-ai-leader",
                    use_container_width=True,
                )

                st.info(
                    "📋 **Sharing Instructions:** Modern LinkedIn sharing URLs do not support automated post text prefill. "
                    "Click the copy button in the top-right corner of the code box above, then click **Open LinkedIn Post Editor** "
                    "and paste your draft directly into the post editor."
                )
                st.caption(
                    "🔒 Privacy Notice: Does not auto-publish. Zero test scores, quiz answers, or student credentials are shared."
                )

# ==============================================================================
# TAB 3: PRACTICE QUIZ
# ==============================================================================
with tab_quiz:
    st.header("📝 Certification Practice Quiz")
    st.write(
        "Test your knowledge with original practice questions. "
        "Answer keys are strictly protected on the backend until you submit."
    )

    # Check for preselected topic from Learn tab
    default_topic_idx = 0
    if st.session_state.get("preselected_quiz_topic"):
        target_id = st.session_state.preselected_quiz_topic
        for idx, (label, tid) in enumerate(topic_map.items()):
            if tid == target_id:
                default_topic_idx = idx
                break

    q_col1, q_col2 = st.columns([1, 1])
    with q_col1:
        sel_kwargs: dict[str, Any] = {"key": "quiz_topic_select"}
        if "quiz_topic_select" not in st.session_state:
            sel_kwargs["index"] = default_topic_idx
        quiz_topic_label = st.selectbox(
            "Select Quiz Topic",
            list(topic_map.keys()),
            **sel_kwargs,
        )
        quiz_topic_id = topic_map[quiz_topic_label]
    with q_col2:
        question_count = st.number_input(
            "Number of Questions",
            min_value=1,
            max_value=10,
            value=5,
            step=1,
        )

    if st.button("Generate Practice Quiz", type="primary"):
        if not current_session:
            st.error("Please start a session in the sidebar first.")
        else:
            with st.spinner(
                "Quiz Generator agent is creating multiple choice questions..."
            ):
                try:
                    student_questions = run_async(
                        facade.generate_quiz(
                            session_id=session_id,
                            user_id=user_id,
                            topic_ids=[quiz_topic_id],
                            question_count=int(question_count),
                            experience_level=experience_level,
                        )
                    )
                    st.session_state.active_quiz = student_questions
                    st.session_state.active_quiz_result = None
                    st.session_state.student_choices = {}
                    st.success(
                        f"Generated {len(student_questions)} practice questions!"
                    )
                except (RuntimeError, ValueError) as err:
                    st.error(f"Error generating quiz: {err}")

    if st.session_state.get("active_quiz"):
        questions = st.session_state.active_quiz
        st.markdown(f"### Questions ({len(questions)} items)")

        with st.form("quiz_submission_form"):
            user_answers: dict[str, Literal["A", "B", "C", "D"]] = {}
            radio_opts: list[Literal["A", "B", "C", "D"]] = ["A", "B", "C", "D"]
            for idx, q in enumerate(questions, 1):
                st.markdown(f"**Question {idx} ({q.question_id}):** {q.question_text}")

                def _format_option(opt_key: str, q_item: Any = q) -> str:
                    return f"{opt_key}: {q_item.options.get(opt_key, '')}"

                chosen_opt = st.radio(
                    f"Select your answer for Question {idx}:",
                    options=["A", "B", "C", "D"],
                    format_func=_format_option,
                    key=f"ans_{q.question_id}",
                )
                user_answers[q.question_id] = cast(
                    Literal["A", "B", "C", "D"], chosen_opt or "A"
                )
                st.divider()

            submit_quiz_button = st.form_submit_button(
                "Submit Answers for Deterministic Grading", type="primary"
            )

        if submit_quiz_button:
            with st.spinner("Grading answers deterministically via Python..."):
                try:
                    submission = QuizSubmission(
                        quiz_id=current_session.current_quiz_id or "default_quiz",
                        student_answers=user_answers,
                    )
                    grading_result = run_async(
                        facade.submit_quiz(
                            session_id=session_id,
                            user_id=user_id,
                            submission=submission,
                        )
                    )
                    st.session_state.active_quiz_result = grading_result
                    current_session = run_async(facade.get_session(session_id, user_id))
                    st.success("Quiz graded successfully!")
                except (RuntimeError, ValueError) as err:
                    st.error(f"Error submitting quiz: {err}")

    if st.session_state.get("active_quiz_result"):
        res = st.session_state.active_quiz_result
        st.markdown("## 📊 Evaluation & Diagnostic Feedback")
        score_metric, correct_metric = st.columns(2)
        with score_metric:
            st.metric("Score Percentage", f"{res.score_percentage:.1f}%")
        with correct_metric:
            st.metric(
                "Correct Answers", f"{res.correct_answers} / {res.total_questions}"
            )

        if res.weak_topics:
            st.error(
                f"⚠️ **Identified Weak Topics (< 70%):** {', '.join(res.weak_topics)}"
            )
        if res.strong_topics:
            st.success(
                f"✅ **Demonstrated Strong Topics (≥ 70%):** {', '.join(res.strong_topics)}"
            )

        st.markdown("### Detailed Item Feedback")
        for fb in res.question_feedback:
            status_icon = "✅" if fb.is_correct else "❌"
            with st.expander(
                f"{status_icon} Question {fb.question_id} ({fb.topic_id})"
            ):
                st.write(f"**Your Answer:** {fb.student_answer}")
                st.write(f"**Correct Answer:** {fb.correct_answer}")
                st.info(f"**Factual Explanation:** {fb.explanation}")

# ==============================================================================
# TAB 4: ADAPTIVE PLAN
# ==============================================================================
with tab_adaptive:
    st.header("🔄 Dynamic Adaptive Replanning")
    st.write(
        "When quiz results expose weak topics, the multi-agent orchestration layer "
        "re-engages the Study Planner to dynamically adapt the remaining schedule."
    )

    if current_session:
        st.markdown(f"**Current Plan Revision:** Rev {current_session.plan_revision}")
        if current_session.weak_topics:
            st.warning(
                f"Identified Weak Topics: {', '.join(current_session.weak_topics)}"
            )

            # Targeted Resource & Visual Recommendations for Weak Topics
            st.markdown("### 🎯 Recommended Remediation Pathways")
            for wt in current_session.weak_topics:
                with st.expander(f"Remediation Plan for `{wt}`", expanded=True):
                    st.markdown(f"**Action Steps for `{wt}`:**")
                    st.markdown(
                        "1. 📊 Review the visual architecture diagram in Learn Topic."
                    )
                    st.markdown(
                        "2. 💻 Step through the offline runnable Python code demo."
                    )
                    st.markdown(
                        "3. 📖 Review the official documentation and video resources below:"
                    )
                    wt_res = facade.get_topic_resources(wt)
                    render_resource_grid(wt_res, columns=2)
        else:
            st.info(
                "No weak topics identified yet. Complete a practice quiz to generate performance evidence."
            )

        completed_days_input = st.number_input(
            "Days completed so far:",
            min_value=0,
            max_value=max(0, current_session.exam_deadline_or_days_remaining - 1),
            value=min(3, max(0, current_session.exam_deadline_or_days_remaining - 1)),
            step=1,
        )

        if st.button("Generate Adapted Plan", type="primary"):
            with st.spinner(
                "Re-engaging Study Planner agent with weak topic diagnostic feedback..."
            ):
                try:
                    adapted_plan = run_async(
                        facade.adapt_study_plan(
                            session_id=session_id,
                            user_id=user_id,
                            completed_days=int(completed_days_input),
                        )
                    )
                    st.success(
                        f"Adapted plan generated! (Revision {current_session.plan_revision + 1})"
                    )
                    current_session = run_async(facade.get_session(session_id, user_id))
                except (RuntimeError, ValueError) as err:
                    st.error(f"Error adapting study plan: {err}")

        if (
            current_session.study_plan_history
            and len(current_session.study_plan_history) > 1
        ):
            st.markdown("### 📜 Plan Evolution History")
            for rev_idx, h_plan in enumerate(current_session.study_plan_history, 1):
                with st.expander(
                    f"Plan Revision {rev_idx}: {h_plan.days_until_exam} Days ({h_plan.total_planned_minutes}m)"
                ):
                    st.write(f"**Planning Notes:** {h_plan.planning_notes}")
                    for d in h_plan.days:
                        st.text(
                            f"Day {d.day_number}: {d.title} ({d.total_minutes} min)"
                        )
    else:
        st.info("Start a session in the sidebar to test adaptive replanning.")

# ==============================================================================
# TAB 5: AGENT OPS & OBSERVABILITY
# ==============================================================================
with tab_ops:
    render_agent_ops_tab()

# ==============================================================================
# TAB 6: AGENT EVALUATIONS SUITE
# ==============================================================================
with tab_evals:
    render_evaluations_tab(runner=eval_runner, run_async_fn=run_async)
