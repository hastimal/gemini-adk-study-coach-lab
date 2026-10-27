"""End-to-end integration test verifying all 6 live Gemini-backed multi-agent workflows:
1. Topic explanation (topic_expert agent)
2. Study plan generation (study_planner agent)
3. Formative quick check generation (quiz_generator agent)
4. Formative quick check deterministic evaluation (pure Python)
5. Practice quiz generation & deterministic scoring (server-side answer key protection)
6. Adaptive remediation plan generation (study_planner prioritizing weak topics)
"""

import os

import pytest
from dotenv import load_dotenv

from study_coach.models.quiz import QuizSubmission
from study_coach.models.student import StudentProfile
from study_coach.services.workshop_facade import WorkshopFacade

load_dotenv()
HAS_GEMINI_KEY = bool(os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY"))
RUN_LIVE_OPT_IN = os.getenv("RUN_LIVE_GEMINI_TESTS", "false").lower() in (
    "true",
    "1",
    "yes",
)


@pytest.mark.live
@pytest.mark.anyio
async def test_all_six_live_multi_agent_workflows() -> None:
    """Runs all 6 live multi-agent workflows in end-to-end sequence."""
    if not RUN_LIVE_OPT_IN:
        pytest.skip(
            "Live Gemini tests are opt-in. Set RUN_LIVE_GEMINI_TESTS=true to run."
        )
    if not HAS_GEMINI_KEY:
        pytest.skip(
            "Gemini API key not found; skipping live end-to-end agent execution."
        )

    facade = WorkshopFacade()
    profile = StudentProfile(
        daily_study_minutes=30,
        experience_level="beginner",
    )
    session_id = "test_e2e_live_suite"
    user_id = "test_e2e_learner"

    # 1. Topic Explanation
    explanation = await facade.explain_topic("genai_concepts", "beginner")
    assert explanation.topic_title
    assert len(explanation.key_concepts) >= 1
    assert len(explanation.explanation) > 20

    # 2. Initial Study Plan Generation
    plan = await facade.create_study_plan(session_id, user_id, profile)
    assert len(plan.days) == 14
    assert plan.certification_name == "Google Cloud Generative AI Leader"

    # 3. Formative Quick Check Generation
    qc_id, questions = await facade.generate_quick_check(
        session_id, user_id, "genai_concepts"
    )
    assert len(questions) == 3

    # 4. Quick Check Deterministic Evaluation
    sub = QuizSubmission(
        quiz_id=qc_id,
        student_answers={q.question_id: "A" for q in questions},
    )
    qc_res = await facade.evaluate_quick_check(session_id, user_id, sub)
    assert qc_res.total_questions == 3
    assert 0.0 <= qc_res.score_percentage <= 100.0

    # 5. Practice Quiz Generation & Deterministic Scoring
    quiz_questions = await facade.generate_quiz(session_id, user_id, ["genai_concepts"])
    assert len(quiz_questions) == 5
    session = await facade.get_session(session_id, user_id)
    assert session is not None
    quiz_sub = QuizSubmission(
        quiz_id=session.current_quiz_id or "default_quiz",
        student_answers={q.question_id: "A" for q in quiz_questions},
    )
    quiz_res = await facade.submit_quiz(session_id, user_id, quiz_sub)
    assert quiz_res.total_questions == 5
    assert 0.0 <= quiz_res.score_percentage <= 100.0

    # 6. Adaptive Remediation Plan Generation
    adapted_plan = await facade.adapt_study_plan(session_id, user_id, completed_days=1)
    assert len(adapted_plan.days) == 13
    assert len(adapted_plan.planning_notes) > 10
