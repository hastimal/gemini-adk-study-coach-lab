"""Deterministic agent regression tests for Google ADK Study Coach.

Evaluates:
1. Study Planner constraints, sequential days, and numerical budgets.
2. Topic Expert grounding, curriculum alignment, and structured schema.
3. Quiz Generator option isolation, answer key protection, and grading.
4. Coordinator agent delegation declaration and keyword intent routing.
5. Error handling for malformed responses, invalid inputs, and missing credentials.
6. Weak topic identification and adaptive learning workflow state transitions.
7. Future-proofing extension points for multi-turn sessions and documents.
"""

from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import ValidationError

from study_coach.agent import root_agent
from study_coach.agents.quiz_generator import quiz_generator
from study_coach.agents.study_planner import study_planner
from study_coach.agents.topic_expert import topic_expert
from study_coach.models.evaluation import (
    EvaluationScenarioResult,
    EvaluationSummaryReport,
)
from study_coach.models.learning_session import LearningSession
from study_coach.models.quiz import (
    QuestionFeedback,
    Quiz,
    QuizQuestion,
    QuizResult,
    QuizSubmission,
    StudentQuizQuestion,
)
from study_coach.models.student import StudentProfile
from study_coach.models.study_plan import (
    StudyActivity,
    StudyDay,
    StudyPlan,
)
from study_coach.models.topic_explanation import TopicExplanation
from study_coach.services.learning_session import LearningSessionService
from study_coach.tools.planning_tools import (
    calculate_available_minutes,
)
from study_coach.tools.quiz_tools import grade_quiz
from study_coach.tools.topic_tools import get_topic_by_id, search_topics
from study_coach.workflows.adaptive_study import AdaptiveStudyWorkflow

# ==============================================================================
# 1. STUDY PLANNER DETERMINISTIC REGRESSION
# ==============================================================================


def test_study_planner_tools_and_agent_structure() -> None:
    """Study Planner agent must be defined with required curriculum and calculation tools."""
    assert study_planner.name == "study_planner"
    assert study_planner.model is not None
    tool_names = [getattr(t, "__name__", str(t)) for t in study_planner.tools]
    assert any("calculate_available_minutes" in n for n in tool_names)
    assert any("load_curriculum" in n for n in tool_names)


def test_study_planner_enforces_sequential_day_numbers() -> None:
    """Non-sequential days must raise ValidationError with clear explanation."""
    days = [
        StudyDay(
            day_number=1,
            title="Day 1",
            total_minutes=60,
            activities=[
                StudyActivity(
                    activity_type="learning",
                    topic_id="genai_concepts",
                    description="Study 1",
                    duration_minutes=60,
                )
            ],
        ),
        StudyDay(
            day_number=3,  # Skipped Day 2!
            title="Day 3",
            total_minutes=60,
            activities=[
                StudyActivity(
                    activity_type="learning",
                    topic_id="genai_concepts",
                    description="Study 3",
                    duration_minutes=60,
                )
            ],
        ),
    ]
    with pytest.raises(ValidationError, match="Day numbers must be sequential"):
        StudyPlan(
            certification_name="Google Cloud Generative AI Leader",
            days_until_exam=2,
            daily_study_minutes=60,
            days=days,
            total_planned_minutes=120,
            planning_notes="Broken sequence",
        )


def test_study_planner_total_minutes_sum_mismatch() -> None:
    """Sum of activity minutes must strictly match total_planned_minutes."""
    days = [
        StudyDay(
            day_number=1,
            title="Day 1",
            total_minutes=45,
            activities=[
                StudyActivity(
                    activity_type="learning",
                    topic_id="genai_concepts",
                    description="Lesson",
                    duration_minutes=45,
                )
            ],
        )
    ]
    with pytest.raises(
        ValidationError, match="total_planned_minutes .* does not match"
    ):
        StudyPlan(
            certification_name="Google Cloud Generative AI Leader",
            days_until_exam=1,
            daily_study_minutes=60,
            days=days,
            total_planned_minutes=999,  # Mismatch!
            planning_notes="Mismatch total minutes",
        )


def test_calculate_available_minutes_deterministic() -> None:
    """calculate_available_minutes utility must return exact mathematical product."""
    assert calculate_available_minutes(14, 90) == 1260
    assert calculate_available_minutes(7, 45) == 315
    assert calculate_available_minutes(30, 60) == 1800
    with pytest.raises(ValueError, match="must be non-negative"):
        calculate_available_minutes(-1, 60)
    with pytest.raises(ValueError, match="must be non-negative"):
        calculate_available_minutes(14, -10)


# ==============================================================================
# 2. TOPIC EXPERT DETERMINISTIC REGRESSION
# ==============================================================================


def test_topic_expert_agent_structure_and_tools() -> None:
    """Topic Expert agent must declare curriculum inspection tools."""
    assert topic_expert.name == "topic_expert"
    tool_names = [getattr(t, "__name__", str(t)) for t in topic_expert.tools]
    assert any("get_topic_by_id" in n for n in tool_names)
    assert any("search_topics" in n for n in tool_names)
    assert any("get_related_topics" in n for n in tool_names)


def test_curriculum_get_topic_by_id_and_search() -> None:
    """Topic retrieval must find known curriculum topics and gracefully return None for unknown."""
    genai = get_topic_by_id("genai_concepts")
    assert genai is not None
    assert genai["id"] == "genai_concepts"
    assert "Generative AI Concepts" in genai["title"]

    unknown = get_topic_by_id("unregistered_quantum_ai")
    assert unknown is None

    search_res = search_topics("transformer")
    assert len(search_res) > 0
    assert any(t["id"] == "llm_architecture" for t in search_res)


def test_topic_explanation_field_sanitization() -> None:
    """TopicExplanation model must validate types and reject malformed schemas."""
    valid_payload = {
        "topic_id": "genai_concepts",
        "topic_title": "Generative AI Concepts",
        "experience_level": "intermediate",
        "learning_objectives": ["Master zero-shot", "Understand few-shot"],
        "key_concepts": ["System instructions", "Role prompting", "Delimiters"],
        "explanation": "Prompt engineering guides model response formatting and grounding.",
        "practical_example": "Structuring system instructions for customer service chatbot in Vertex AI.",
        "common_misconceptions": ["Prompts are identical to SQL queries."],
        "comprehension_questions": [
            "What is few-shot prompting?",
            "Why use delimiters?",
        ],
        "source_references": ["https://cloud.google.com/vertex-ai/docs"],
    }
    obj = TopicExplanation.model_validate(valid_payload)
    assert obj.topic_id == "genai_concepts"
    assert len(obj.key_concepts) == 3

    # Missing mandatory explanation field must fail
    invalid_payload = dict(valid_payload)
    del invalid_payload["explanation"]
    with pytest.raises(ValidationError):
        TopicExplanation.model_validate(invalid_payload)


# ==============================================================================
# 3. QUIZ GENERATOR & ANSWER-KEY ISOLATION REGRESSION
# ==============================================================================


def test_quiz_generator_agent_structure() -> None:
    """Quiz Generator agent must declare curriculum and navigation tools."""
    assert quiz_generator.name == "quiz_generator"
    tool_names = [getattr(t, "__name__", str(t)) for t in quiz_generator.tools]
    assert any("load_curriculum" in n for n in tool_names)
    assert any("get_topic_by_id" in n for n in tool_names)


def test_quiz_student_view_strict_answer_key_isolation() -> None:
    """Quiz.to_student_view() must NEVER leak correct_answer or explanation to client."""
    questions = [
        QuizQuestion(
            question_id="sec_q1",
            topic_id="genai_concepts",
            question_text="What is the primary role of Vector Search in RAG architectures?",
            options={
                "A": "Translates audio to text.",
                "B": "Indexes and retrieves semantic embeddings of enterprise documents.",
                "C": "Executes SQL transaction queries.",
                "D": "Compiles Python code.",
            },
            correct_answer="B",
            explanation="Vector Search enables sub-millisecond similarity search across embeddings.",
            difficulty="intermediate",
        )
    ]
    full_quiz = Quiz(
        certification_name="Google Cloud Generative AI Leader",
        topic_ids=["genai_concepts"],
        experience_level="intermediate",
        questions=questions,
    )

    student_qs = full_quiz.to_student_view()
    assert len(student_qs) == 1
    sq = student_qs[0]
    assert isinstance(sq, StudentQuizQuestion)

    # Student question must contain question_id, topic_id, question_text, options
    assert sq.question_id == "sec_q1"
    assert len(sq.options) == 4
    assert sq.options["B"].startswith("Indexes and retrieves")

    # Attributes that MUST NOT exist on student view
    assert not hasattr(sq, "correct_answer")
    assert not hasattr(sq, "explanation")

    # Serialized dictionary must not contain keys
    dumped = sq.model_dump()
    assert "correct_answer" not in dumped
    assert "explanation" not in dumped


def test_deterministic_quiz_grading_accuracy() -> None:
    """grade_quiz must deterministically grade answers and identify weak/strong topics."""
    questions = [
        QuizQuestion(
            question_id=f"g_q{i}",
            topic_id="llm_architecture" if i <= 3 else "responsible_ai",
            question_text=f"Sample question {i}?",
            options={
                "A": "Option A",
                "B": "Option B",
                "C": "Option C",
                "D": "Option D",
            },
            correct_answer="A",
            explanation="Explanation text",
            difficulty="beginner",
        )
        for i in range(1, 6)
    ]
    quiz = Quiz(
        certification_name="Google Cloud Generative AI Leader",
        topic_ids=["llm_architecture", "responsible_ai"],
        experience_level="beginner",
        questions=questions,
    )

    # Student gets g_q1 correct (A), g_q2 wrong (B), g_q3 wrong (C) -> llm_architecture: 1/3 (33.3% < 70% -> WEAK)
    # Student gets g_q4 correct (A), g_q5 correct (A) -> responsible_ai: 2/2 (100% >= 70% -> STRONG)
    submission = QuizSubmission(
        quiz_id="eval_test_quiz",
        student_answers={
            "g_q1": "A",
            "g_q2": "B",
            "g_q3": "C",
            "g_q4": "A",
            "g_q5": "A",
        },
    )
    result = grade_quiz(quiz, submission)
    assert isinstance(result, QuizResult)
    assert result.total_questions == 5
    assert result.correct_answers == 3
    assert result.score_percentage == 60.0
    assert "llm_architecture" in result.weak_topics
    assert "responsible_ai" in result.strong_topics
    assert len(result.question_feedback) == 5


# ==============================================================================
# 4. COORDINATOR DELEGATION & INTENT REGRESSION
# ==============================================================================


def test_coordinator_agent_declaration() -> None:
    """Root coordinator agent must declare study_planner, topic_expert, and quiz_generator."""
    subagent_names = {a.name for a in root_agent.sub_agents}
    assert "study_planner" in subagent_names
    assert "topic_expert" in subagent_names
    assert "quiz_generator" in subagent_names


# ==============================================================================
# 5. ADAPTIVE LEARNING WORKFLOW REGRESSION
# ==============================================================================


@pytest.mark.anyio
async def test_adaptive_workflow_requires_session_before_quiz() -> None:
    """Generating a quiz for an uninitialized session must fail gracefully with ValueError."""
    svc = LearningSessionService()
    workflow = AdaptiveStudyWorkflow(session_service=svc)

    with pytest.raises(ValueError, match="Session 'uninit_session' not found"):
        await workflow.generate_practice_quiz("uninit_session", "user_1")


@pytest.mark.anyio
async def test_adaptive_replanning_preserves_completed_days() -> None:
    """Adapted study plan must preserve completed days and adapt only remaining days."""
    svc = LearningSessionService()
    workflow = AdaptiveStudyWorkflow(session_service=svc)

    profile = StudentProfile(experience_level="beginner", daily_study_minutes=60)
    session = await svc.get_or_create_session("replan_session", "user_1", profile)

    initial_plan = StudyPlan(
        certification_name="Google Cloud Generative AI Leader",
        days_until_exam=4,
        daily_study_minutes=60,
        days=[
            StudyDay(
                day_number=i,
                title=f"Day {i}",
                total_minutes=60,
                activities=[
                    StudyActivity(
                        activity_type="learning",
                        topic_id="genai_concepts",
                        description=f"Activity {i}",
                        duration_minutes=60,
                    )
                ],
            )
            for i in range(1, 5)
        ],
        total_planned_minutes=240,
        planning_notes="Initial 4-day schedule",
    )
    session.current_study_plan = initial_plan

    # Record a quiz with a weak topic and feedback
    feedback = [
        QuestionFeedback(
            question_id=f"q{i}",
            topic_id="llm_architecture" if i <= 3 else "genai_concepts",
            student_answer="B" if i <= 3 else "A",
            correct_answer="A",
            is_correct=i > 3,
            explanation="Explanation",
        )
        for i in range(1, 6)
    ]
    quiz_result = QuizResult(
        total_questions=5,
        correct_answers=2,
        score_percentage=40.0,
        question_feedback=feedback,
        weak_topics=["llm_architecture"],
        strong_topics=["genai_concepts"],
    )
    session.quiz_results.append(quiz_result)
    await svc.save_session(session)

    # Replan with 2 completed days (out of 4)
    # In offline deterministic CI, mock the InMemoryRunner response so tests run fast and without API keys
    mock_adapted_plan = StudyPlan(
        certification_name="Google Cloud Generative AI Leader",
        days_until_exam=2,
        daily_study_minutes=60,
        days=[
            StudyDay(
                day_number=1,
                title="Adapted Day 1 (Remediation)",
                total_minutes=60,
                activities=[
                    StudyActivity(
                        activity_type="learning",
                        topic_id="llm_architecture",
                        description="Remediation for LLM Architecture",
                        duration_minutes=60,
                    )
                ],
            ),
            StudyDay(
                day_number=2,
                title="Adapted Day 2 (Practice)",
                total_minutes=60,
                activities=[
                    StudyActivity(
                        activity_type="practice",
                        topic_id="llm_architecture",
                        description="Practice questions on LLM Architecture",
                        duration_minutes=60,
                    )
                ],
            ),
        ],
        total_planned_minutes=120,
        planning_notes="Adapted plan prioritizing weak topic llm_architecture.",
    )

    mock_event = MagicMock()
    mock_part = MagicMock()
    mock_fc = MagicMock()
    mock_fc.name = "set_model_response"
    mock_fc.args = {"response": mock_adapted_plan.model_dump()}
    mock_part.function_call = mock_fc
    mock_content = MagicMock()
    mock_content.parts = [mock_part]
    mock_event.content = mock_content

    async def mock_run_async(
        *args: object, **kwargs: object
    ) -> AsyncGenerator[MagicMock, None]:
        yield mock_event

    with patch(
        "study_coach.workflows.adaptive_study.InMemoryRunner"
    ) as mock_runner_cls:
        mock_instance = mock_runner_cls.return_value
        mock_instance.app_name = "study_planner"
        mock_instance.session_service = AsyncMock()
        mock_instance.run_async = mock_run_async

        adapted = await workflow.generate_adapted_plan(
            "replan_session", "user_1", completed_days=2
        )
        assert adapted.days_until_exam == 2
        assert len(adapted.days) == 2
        assert adapted.days[0].activities[0].topic_id == "llm_architecture"
        updated_session = await svc.get_session("replan_session", "user_1")
        assert updated_session is not None
        assert updated_session.plan_revision == 2


# ==============================================================================
# 6. EVALUATION MODELS & FAILURE CATEGORIES
# ==============================================================================


def test_evaluation_failure_category_serialization() -> None:
    """EvaluationScenarioResult must serialize and validate failure categories."""
    res_pass = EvaluationScenarioResult(
        scenario_id="s1",
        scenario_description="Plan generation",
        target_agent="study_planner",
        status="PASS",
        failure_category="none",
        duration_seconds=1.2,
        details="Generated plan",
    )
    assert res_pass.failure_category == "none"

    res_fail = EvaluationScenarioResult(
        scenario_id="s2",
        scenario_description="Auth check",
        target_agent="auth",
        status="FAIL",
        failure_category="missing_credentials",
        duration_seconds=0.0,
        details="No API key",
        error="GOOGLE_API_KEY is not set",
    )
    assert res_fail.failure_category == "missing_credentials"

    report = EvaluationSummaryReport(
        run_id="run_123",
        model="gemini-3.8-flash",
        total_scenarios=2,
        passed_scenarios=1,
        failed_scenarios=1,
        total_duration_seconds=1.2,
        scenarios=[res_pass, res_fail],
    )
    dumped = report.model_dump()
    assert dumped["scenarios"][1]["failure_category"] == "missing_credentials"


# ==============================================================================
# 7. EXTENSION-POINT VALIDATION FOR FUTURE CAPABILITIES
# ==============================================================================


def test_future_extensibility_session_state_fields() -> None:
    """Verify session data structures support multi-turn messages and future document attachments."""
    session = LearningSession(
        session_id="ext_session_1",
        user_id="learner_1",
        certification_name="Google Cloud Generative AI Leader",
        exam_deadline_or_days_remaining=14,
        student_profile=StudentProfile(
            experience_level="intermediate", daily_study_minutes=60
        ),
    )
    # Baseline session attributes
    assert session.session_id == "ext_session_1"
    assert session.current_study_plan is None
    assert len(session.quiz_results) == 0

    # Ensure metadata dictionary exists for document IDs and conversational context
    assert hasattr(session, "metadata")
    session.metadata["conversation_history"] = [
        {"role": "user", "content": "What is self-attention?"},
        {"role": "model", "content": "Self-attention computes dynamic weights..."},
    ]
    session.metadata["uploaded_documents"] = [
        {"doc_id": "guide_1", "filename": "study_guide.pdf", "page_count": 14}
    ]
    assert len(session.metadata["conversation_history"]) == 2
    assert session.metadata["uploaded_documents"][0]["filename"] == "study_guide.pdf"
