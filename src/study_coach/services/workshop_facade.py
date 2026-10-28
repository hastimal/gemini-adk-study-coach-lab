"""Workshop facade service providing clean UI-friendly methods over multi-agent workflows."""

from typing import Any

from google.adk.runners import InMemoryRunner
from google.genai import types

from study_coach.agents.topic_expert import topic_expert
from study_coach.models.learning_session import LearningProgress, LearningSession
from study_coach.models.quiz import QuizResult, QuizSubmission, StudentQuizQuestion
from study_coach.models.student import StudentProfile
from study_coach.models.study_plan import StudyPlan
from study_coach.models.topic_explanation import TopicExplanation
from study_coach.observability import (
    ADKObservabilityPlugin,
    trace_workflow_step,
)
from study_coach.services.learning_session import LearningSessionService
from study_coach.tools.curriculum_tools import load_curriculum
from study_coach.workflows.adaptive_study import AdaptiveStudyWorkflow
from study_coach.workflows.coach_chat import ConversationalCoachWorkflow


class WorkshopFacade:
    """Thin application facade connecting Streamlit UI to real ADK workflows and agents.

    Ensures session continuity, private answer key protection, and deterministic grading.
    """

    def __init__(
        self,
        session_service: LearningSessionService | None = None,
        workflow: AdaptiveStudyWorkflow | None = None,
        coach_workflow: ConversationalCoachWorkflow | None = None,
        observability_plugin: ADKObservabilityPlugin | None = None,
    ) -> None:
        self.session_service = session_service or LearningSessionService()
        self.observability_plugin = observability_plugin or ADKObservabilityPlugin()
        self.workflow = workflow or AdaptiveStudyWorkflow(
            session_service=self.session_service,
            observability_plugin=self.observability_plugin,
        )
        self.coach_workflow = coach_workflow or ConversationalCoachWorkflow(
            session_service=self.session_service,
            observability_plugin=self.observability_plugin,
        )

    def get_supported_curriculum_topics(self) -> list[dict[str, Any]]:
        """Returns the list of supported curriculum topics with metadata."""
        curriculum = load_curriculum()
        topics: list[dict[str, Any]] = curriculum.get("topics", [])
        return topics

    async def get_or_create_session(
        self,
        session_id: str,
        user_id: str,
        student_profile: StudentProfile | None = None,
        certification_name: str = "Google Cloud Generative AI Leader",
        days_remaining: int = 14,
    ) -> LearningSession:
        """Retrieves an existing learning session or initializes a new validated one."""
        return await self.session_service.get_or_create_session(
            session_id=session_id,
            user_id=user_id,
            student_profile=student_profile,
            certification_name=certification_name,
            days_remaining=days_remaining,
        )

    async def get_session(
        self, session_id: str, user_id: str
    ) -> LearningSession | None:
        """Retrieves a session if it exists."""
        return await self.session_service.get_session(
            session_id=session_id, user_id=user_id
        )

    async def create_study_plan(
        self,
        session_id: str,
        user_id: str,
        student_profile: StudentProfile,
        certification_name: str = "Google Cloud Generative AI Leader",
        days_until_exam: int = 14,
    ) -> StudyPlan:
        """Invokes Study Planner agent through workflow to generate and save plan."""
        return await self.workflow.create_initial_plan(
            session_id=session_id,
            user_id=user_id,
            student_profile=student_profile,
            certification_name=certification_name,
            days_until_exam=days_until_exam,
        )

    @trace_workflow_step(
        "explain_topic", workflow="topic_explanation", agent="topic_expert"
    )
    async def explain_topic(
        self,
        topic_id: str,
        experience_level: str = "beginner",
    ) -> TopicExplanation:
        """Invokes Topic Expert agent using Google ADK to teach a curriculum topic."""
        runner = InMemoryRunner(agent=topic_expert, plugins=[self.observability_plugin])
        prompt = (
            f"Explain the curriculum topic '{topic_id}' thoroughly for a "
            f"{experience_level} student preparing for Google Cloud certification. "
            "Include key concepts, clear explanations, Google Cloud practical examples, "
            "common misconceptions, and comprehension check questions."
        )

        session_id = f"explain_{topic_id}_{experience_level}"
        await runner.session_service.create_session(
            app_name=runner.app_name,
            user_id="workshop_learner",
            session_id=session_id,
        )

        explanation_dict: dict[str, Any] | None = None
        async for event in runner.run_async(
            user_id="workshop_learner",
            session_id=session_id,
            new_message=types.Content(
                role="user",
                parts=[types.Part.from_text(text=prompt)],
            ),
        ):
            if event.content and event.content.parts:
                for part in event.content.parts:
                    fc = getattr(part, "function_call", None)
                    if fc and fc.name == "set_model_response" and fc.args:
                        explanation_dict = fc.args.get("response") or fc.args

        if not explanation_dict:
            raise RuntimeError(
                f"Topic Expert failed to return structured explanation for '{topic_id}'"
            )

        return TopicExplanation.model_validate(explanation_dict)

    async def generate_quiz(
        self,
        session_id: str,
        user_id: str,
        topic_ids: list[str] | None = None,
        question_count: int = 5,
        experience_level: str | None = None,
    ) -> list[StudentQuizQuestion]:
        """Generates a practice quiz and returns sanitized questions with answers hidden."""
        return await self.workflow.generate_practice_quiz(
            session_id=session_id,
            user_id=user_id,
            topic_ids=topic_ids,
            question_count=question_count,
            experience_level=experience_level,
        )

    async def submit_quiz(
        self,
        session_id: str,
        user_id: str,
        submission: QuizSubmission,
    ) -> QuizResult:
        """Deterministically evaluates answers against private server-side quiz."""
        return await self.workflow.submit_quiz_answers(
            session_id=session_id,
            user_id=user_id,
            submission=submission,
        )

    async def generate_quick_check(
        self,
        session_id: str,
        user_id: str,
        topic_id: str,
        experience_level: str | None = None,
    ) -> tuple[str, list[StudentQuizQuestion]]:
        """Generates a 3-question formative quick check with answers hidden from the student view."""
        return await self.workflow.generate_quick_check(
            session_id=session_id,
            user_id=user_id,
            topic_id=topic_id,
            experience_level=experience_level,
        )

    async def evaluate_quick_check(
        self,
        session_id: str,
        user_id: str,
        submission: QuizSubmission,
    ) -> QuizResult:
        """Deterministically scores a quick check formative assessment without mutating formal quiz history."""
        return await self.workflow.evaluate_quick_check(
            session_id=session_id,
            user_id=user_id,
            submission=submission,
        )

    async def get_learning_progress(
        self,
        session_id: str,
        user_id: str,
    ) -> LearningProgress:
        """Retrieves accumulated progress metrics."""
        return await self.workflow.retrieve_learning_progress(
            session_id=session_id,
            user_id=user_id,
        )

    async def adapt_study_plan(
        self,
        session_id: str,
        user_id: str,
        completed_days: int = 0,
    ) -> StudyPlan:
        """Generates adapted study plan prioritizing weak topics identified in quiz results."""
        return await self.workflow.generate_adapted_plan(
            session_id=session_id,
            user_id=user_id,
            completed_days=completed_days,
        )

    def get_topic_resources(
        self,
        topic_id: str,
        experience_level: str | None = None,
    ) -> list[Any]:
        """Returns verified learning resources for a given topic."""
        from study_coach.tools.resource_tools import get_resources_for_topic

        return get_resources_for_topic(
            topic_id=topic_id, experience_level=experience_level
        )

    def get_day_resources(
        self,
        topic_ids: list[str],
        max_minutes: int | None = None,
        experience_level: str | None = None,
    ) -> list[Any]:
        """Returns verified resources fitting a study day's time budget."""
        from study_coach.tools.resource_tools import get_resources_for_day

        return get_resources_for_day(
            topic_ids=topic_ids,
            max_minutes=max_minutes,
            experience_level=experience_level,
        )

    def get_topic_diagram(self, topic_id: str) -> Any | None:
        """Returns declarative lesson diagram for a given topic."""
        from study_coach.services.lesson_visuals import get_diagram_for_topic

        return get_diagram_for_topic(topic_id)

    def get_topic_code_examples(self, topic_id: str) -> list[Any]:
        """Returns curated code examples for a given topic."""
        from study_coach.data.code_examples_registry import get_examples_for_topic

        return get_examples_for_topic(topic_id)

    # ==========================================================================
    # CONVERSATIONAL COACH & DOCUMENT RAG
    # ==========================================================================

    async def upload_document(
        self,
        session_id: str,
        user_id: str,
        filename: str,
        file_bytes: bytes,
    ) -> Any:
        """Parses and indexes an uploaded study guide document."""
        return await self.coach_workflow.ingest_document(
            session_id=session_id,
            user_id=user_id,
            filename=filename,
            file_bytes=file_bytes,
        )

    async def list_documents(self, session_id: str) -> list[Any]:
        """Lists active uploaded documents in the session index."""
        return await self.coach_workflow.list_documents(session_id=session_id)

    async def delete_document(self, session_id: str, user_id: str, doc_id: str) -> bool:
        """Removes an uploaded document from the active session index."""
        return await self.coach_workflow.delete_document(
            session_id=session_id, user_id=user_id, doc_id=doc_id
        )

    async def query_documents(self, session_id: str, user_id: str, query: str) -> Any:
        """Queries uploaded study guides and returns grounded answers with citations."""
        return await self.coach_workflow.query_documents(
            session_id=session_id, user_id=user_id, query=query
        )

    async def generate_document_quiz(
        self,
        session_id: str,
        user_id: str,
        question_count: int = 5,
        target_doc_id: str | None = None,
        experience_level: str = "intermediate",
    ) -> list[StudentQuizQuestion]:
        """Generates multiple-choice practice quiz questions grounded in uploaded documents."""
        return await self.coach_workflow.generate_document_quiz(
            session_id=session_id,
            user_id=user_id,
            question_count=question_count,
            target_doc_id=target_doc_id,
            experience_level=experience_level,
        )

    async def send_chat_message(
        self, session_id: str, user_id: str, message: str
    ) -> Any:
        """Sends student message through multi-agent coach routing and records conversation."""
        return await self.coach_workflow.process_chat_message(
            session_id=session_id, user_id=user_id, student_message=message
        )

    async def get_chat_history(self, session_id: str, user_id: str) -> list[Any]:
        """Retrieves conversational message history for the session."""
        return await self.coach_workflow.get_chat_history(
            session_id=session_id, user_id=user_id
        )

    async def clear_chat_history(self, session_id: str, user_id: str) -> None:
        """Clears conversational message history for the session."""
        await self.coach_workflow.clear_chat_history(
            session_id=session_id, user_id=user_id
        )
