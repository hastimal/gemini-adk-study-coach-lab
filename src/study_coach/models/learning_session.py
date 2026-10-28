from typing import Any

from pydantic import BaseModel, Field, model_validator

from study_coach.models.quiz import Quiz, QuizResult, StudentQuizQuestion
from study_coach.models.student import StudentProfile
from study_coach.models.study_plan import StudyPlan


class LearningProgress(BaseModel):
    """Aggregate metrics of student learning across sessions and quizzes."""

    total_quizzes_taken: int = Field(default=0, ge=0)
    total_questions_attempted: int = Field(default=0, ge=0)
    total_questions_correct: int = Field(default=0, ge=0)
    overall_score_percentage: float = Field(default=0.0, ge=0.0, le=100.0)
    topics_covered: list[str] = Field(default_factory=list)


class LearningSession(BaseModel):
    """Validated learning session state representing student context and progress."""

    session_id: str = Field(..., min_length=1, description="Unique session identifier")
    user_id: str = Field(
        ..., min_length=1, description="Unique student/user identifier"
    )
    student_profile: StudentProfile
    certification_name: str = Field(..., min_length=1)
    exam_deadline_or_days_remaining: int = Field(..., gt=0)
    current_study_plan: StudyPlan | None = None
    study_plan_history: list[StudyPlan] = Field(default_factory=list)
    current_quiz_id: str | None = None
    stored_quizzes: dict[str, Quiz] = Field(
        default_factory=dict,
        description="Private server-side storage of quizzes including answer keys.",
    )
    quiz_results: list[QuizResult] = Field(
        default_factory=list,
        description="History of evaluated quiz results.",
    )
    weak_topics: list[str] = Field(default_factory=list)
    strong_topics: list[str] = Field(default_factory=list)
    completed_topics: list[str] = Field(default_factory=list)
    plan_revision: int = Field(default=1, ge=1)
    learning_progress: LearningProgress = Field(default_factory=LearningProgress)
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Extensible metadata storage for conversation history, documents, and tool state.",
    )

    @model_validator(mode="after")
    def validate_session(self) -> "LearningSession":
        if self.plan_revision < 1:
            raise ValueError("plan_revision must be at least 1")
        if self.exam_deadline_or_days_remaining <= 0:
            raise ValueError("exam_deadline_or_days_remaining must be positive")
        return self

    def get_sanitized_quiz(
        self, quiz_id: str | None = None
    ) -> list[StudentQuizQuestion]:
        """Returns student-facing sanitized questions without answer keys or private explanations."""
        qid = quiz_id or self.current_quiz_id
        if not qid or qid not in self.stored_quizzes:
            raise ValueError(f"No quiz found with ID '{qid}' in session state")
        return self.stored_quizzes[qid].to_student_view()

    def to_adk_state(self) -> dict[str, Any]:
        """Converts session state to a dictionary suitable for ADK session state."""
        return self.model_dump(mode="json")

    @classmethod
    def from_adk_state(cls, data: dict[str, Any]) -> "LearningSession":
        """Reconstructs a LearningSession from ADK session state dictionary."""
        return cls.model_validate(data)
