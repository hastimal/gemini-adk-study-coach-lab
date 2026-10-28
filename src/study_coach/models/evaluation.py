from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class EvaluationScenarioResult(BaseModel):
    """Result of an individual evaluation scenario execution."""

    scenario_id: str
    scenario_description: str
    target_agent: str
    status: Literal["PASS", "FAIL"]
    failure_category: (
        Literal[
            "none",
            "schema_validation",
            "constraint_violation",
            "missing_credentials",
            "timeout",
            "unhandled_exception",
            "curriculum_grounding",
        ]
        | None
    ) = None
    duration_seconds: float = Field(ge=0.0)
    details: str
    error: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class EvaluationSummaryReport(BaseModel):
    """Complete summary report of an evaluation run."""

    run_id: str
    timestamp: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())
    model: str
    total_scenarios: int
    passed_scenarios: int
    failed_scenarios: int
    total_duration_seconds: float
    scenarios: list[EvaluationScenarioResult] = Field(default_factory=list)
