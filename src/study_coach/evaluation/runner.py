"""Reusable Agent Evaluation Runner for Google ADK Study Coach.

Executes real Gemini ADK evaluation scenarios across specialized agents.
Provides thread-safety, execution timeouts, report persistence, and sanitized outputs.
"""

import asyncio
import json
import logging
import os
import time
import uuid
from pathlib import Path
from typing import Any

from google.adk.runners import InMemoryRunner
from google.genai import types

from study_coach.agent import root_agent
from study_coach.config import GEMINI_MODEL
from study_coach.models.evaluation import (
    EvaluationScenarioResult,
    EvaluationSummaryReport,
)
from study_coach.models.student import StudentProfile
from study_coach.observability import ADKObservabilityPlugin, setup_tracing
from study_coach.services.workshop_facade import WorkshopFacade
from study_coach.workflows.adaptive_study import AdaptiveStudyWorkflow

logger = logging.getLogger("study_coach.evaluation")

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
DEFAULT_FIXTURES_PATH = (
    PROJECT_ROOT / "tests" / "eval" / "fixtures" / "evaluation_scenarios.json"
)
EVALUATION_REPORT_PATH = (
    PROJECT_ROOT / "docs" / "reports" / "recent_evaluation_report.json"
)


def load_evaluation_report(
    path: Path = EVALUATION_REPORT_PATH,
) -> EvaluationSummaryReport | None:
    """Loads the most recent evaluation report JSON if it exists and is valid."""
    if not path.exists():
        return None
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return EvaluationSummaryReport.model_validate(data)
    except (json.JSONDecodeError, OSError, ValueError) as err:
        logger.warning("Failed to load evaluation report from %s: %s", path, err)
        return None


def save_evaluation_report(
    report: EvaluationSummaryReport, path: Path = EVALUATION_REPORT_PATH
) -> None:
    """Saves the evaluation summary report to local JSON, creating parent folders if needed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(report.model_dump(), f, indent=2)


class EvaluationRunner:
    """Thread-safe, non-blocking evaluation runner for ADK specialized agents."""

    _lock = asyncio.Lock()

    def __init__(
        self,
        fixtures_path: Path = DEFAULT_FIXTURES_PATH,
        timeout_seconds: float = 60.0,
        model: str | None = None,
    ) -> None:
        self.fixtures_path = fixtures_path
        self.timeout_seconds = timeout_seconds
        self.model = model or GEMINI_MODEL

    def is_running(self) -> bool:
        """Returns True if an evaluation run is actively executing."""
        return self._lock.locked()

    def load_scenarios(self) -> list[dict[str, Any]]:
        """Loads evaluation scenarios from JSON fixture file."""
        if not self.fixtures_path.exists():
            raise FileNotFoundError(f"Fixtures not found at {self.fixtures_path}")
        with open(self.fixtures_path, encoding="utf-8") as f:
            data = json.load(f)
        scenarios: list[dict[str, Any]] = data.get("scenarios", [])
        return scenarios

    async def run_scenario_topic_expert(
        self,
        facade: WorkshopFacade,
        scenario_meta: dict[str, Any],
    ) -> EvaluationScenarioResult:
        """Scenario 3: Evaluates Topic Expert agent for concepts, objectives, and structured schema."""
        scenario_id = scenario_meta.get("id", "scenario_3")
        desc = scenario_meta.get(
            "description", "Explain generative AI concepts for a beginner"
        )
        target_agent = "topic_expert"
        topic_id = "genai_concepts"
        start = time.time()

        try:
            explanation = await asyncio.wait_for(
                facade.explain_topic(
                    topic_id=topic_id,
                    experience_level="beginner",
                ),
                timeout=self.timeout_seconds,
            )
            duration = time.time() - start
            if len(explanation.key_concepts) < 3:
                raise ValueError(
                    f"Expected >= 3 key concepts, got {len(explanation.key_concepts)}"
                )
            if len(explanation.learning_objectives) < 2:
                raise ValueError(
                    f"Expected >= 2 learning objectives, got {len(explanation.learning_objectives)}"
                )

            concepts_sample = ", ".join(explanation.key_concepts[:3])
            return EvaluationScenarioResult(
                scenario_id=scenario_id,
                scenario_description=desc,
                target_agent=target_agent,
                status="PASS",
                failure_category="none",
                duration_seconds=round(duration, 2),
                details=f"Topic '{explanation.topic_title}' generated successfully. Key concepts: {concepts_sample}.",
                metadata={
                    "topic_id": topic_id,
                    "concept_count": len(explanation.key_concepts),
                    "objective_count": len(explanation.learning_objectives),
                },
            )
        except TimeoutError as err:
            duration = time.time() - start
            return EvaluationScenarioResult(
                scenario_id=scenario_id,
                scenario_description=desc,
                target_agent=target_agent,
                status="FAIL",
                failure_category="timeout",
                duration_seconds=round(duration, 2),
                details="Topic Expert execution timed out.",
                error=str(err),
            )
        except (ValueError, AssertionError) as err:
            duration = time.time() - start
            return EvaluationScenarioResult(
                scenario_id=scenario_id,
                scenario_description=desc,
                target_agent=target_agent,
                status="FAIL",
                failure_category="schema_validation",
                duration_seconds=round(duration, 2),
                details="Topic Expert returned invalid schema or insufficient concepts.",
                error=str(err),
            )
        except (
            RuntimeError,
            OSError,
        ) as err:
            duration = time.time() - start
            return EvaluationScenarioResult(
                scenario_id=scenario_id,
                scenario_description=desc,
                target_agent=target_agent,
                status="FAIL",
                failure_category="unhandled_exception",
                duration_seconds=round(duration, 2),
                details="Failed to generate structured topic explanation.",
                error=str(err),
            )

    async def run_scenario_quiz_generator(
        self,
        workflow: AdaptiveStudyWorkflow,
        scenario_meta: dict[str, Any],
    ) -> EvaluationScenarioResult:
        """Scenario 5: Evaluates Quiz Generator for 3 formative MCQs with 4 options each."""
        scenario_id = scenario_meta.get("id", "scenario_5")
        desc = scenario_meta.get("description", "Generate three formative MCQs")
        target_agent = "quiz_generator"
        start = time.time()
        sess_id = f"eval_quiz_{uuid.uuid4().hex[:6]}"

        try:
            profile = StudentProfile(
                experience_level="beginner", daily_study_minutes=60
            )
            await workflow.session_service.get_or_create_session(
                sess_id, "eval_user", profile
            )
            questions = await asyncio.wait_for(
                workflow.generate_practice_quiz(
                    session_id=sess_id,
                    user_id="eval_user",
                    topic_ids=["genai_concepts"],
                    question_count=3,
                ),
                timeout=self.timeout_seconds,
            )
            duration = time.time() - start
            if len(questions) != 3:
                raise ValueError(f"Expected exactly 3 questions, got {len(questions)}")
            for q in questions:
                if len(q.options) != 4:
                    raise ValueError(
                        f"Question {q.question_id} has {len(q.options)} options instead of 4"
                    )

            return EvaluationScenarioResult(
                scenario_id=scenario_id,
                scenario_description=desc,
                target_agent=target_agent,
                status="PASS",
                failure_category="none",
                duration_seconds=round(duration, 2),
                details="3 formative MCQs successfully generated with all 4 options sanitized.",
                metadata={"question_count": len(questions)},
            )
        except TimeoutError as err:
            duration = time.time() - start
            return EvaluationScenarioResult(
                scenario_id=scenario_id,
                scenario_description=desc,
                target_agent=target_agent,
                status="FAIL",
                failure_category="timeout",
                duration_seconds=round(duration, 2),
                details="Quiz Generator execution timed out.",
                error=str(err),
            )
        except (ValueError, AssertionError) as err:
            duration = time.time() - start
            return EvaluationScenarioResult(
                scenario_id=scenario_id,
                scenario_description=desc,
                target_agent=target_agent,
                status="FAIL",
                failure_category="schema_validation",
                duration_seconds=round(duration, 2),
                details="Quiz questions did not meet schema constraints.",
                error=str(err),
            )
        except (
            RuntimeError,
            OSError,
        ) as err:
            duration = time.time() - start
            return EvaluationScenarioResult(
                scenario_id=scenario_id,
                scenario_description=desc,
                target_agent=target_agent,
                status="FAIL",
                failure_category="unhandled_exception",
                duration_seconds=round(duration, 2),
                details="Failed to generate formative MCQs.",
                error=str(err),
            )

    async def run_scenario_study_planner(
        self,
        workflow: AdaptiveStudyWorkflow,
        scenario_meta: dict[str, Any],
    ) -> EvaluationScenarioResult:
        """Scenario 2: Evaluates Study Planner for 7 days with <= 45 min/day budget adherence."""
        scenario_id = scenario_meta.get("id", "scenario_2")
        desc = scenario_meta.get(
            "description", "7 days, intermediate, 45 minutes daily plan request"
        )
        target_agent = "study_planner"
        start = time.time()
        sess_id = f"eval_plan_{uuid.uuid4().hex[:6]}"

        try:
            profile = StudentProfile(
                experience_level="intermediate", daily_study_minutes=45
            )
            plan = await asyncio.wait_for(
                workflow.create_initial_plan(
                    session_id=sess_id,
                    user_id="eval_user",
                    student_profile=profile,
                    certification_name="Google Cloud Generative AI Leader",
                    days_until_exam=7,
                ),
                timeout=self.timeout_seconds,
            )
            duration = time.time() - start
            if plan.days_until_exam != 7:
                raise ValueError(
                    f"Expected 7 days_until_exam, got {plan.days_until_exam}"
                )
            if len(plan.days) != 7:
                raise ValueError(f"Expected 7 planned days, got {len(plan.days)}")
            for d in plan.days:
                if d.total_minutes > 45:
                    raise ValueError(
                        f"Day {d.day_number} exceeds 45 minute daily budget ({d.total_minutes}m)"
                    )

            return EvaluationScenarioResult(
                scenario_id=scenario_id,
                scenario_description=desc,
                target_agent=target_agent,
                status="PASS",
                failure_category="none",
                duration_seconds=round(duration, 2),
                details="7-day study plan generated strictly respecting 45 min/day budget.",
                metadata={
                    "planned_days": len(plan.days),
                    "total_minutes": plan.total_planned_minutes,
                },
            )
        except TimeoutError as err:
            duration = time.time() - start
            return EvaluationScenarioResult(
                scenario_id=scenario_id,
                scenario_description=desc,
                target_agent=target_agent,
                status="FAIL",
                failure_category="timeout",
                duration_seconds=round(duration, 2),
                details="Study Planner execution timed out.",
                error=str(err),
            )
        except (ValueError, AssertionError) as err:
            duration = time.time() - start
            return EvaluationScenarioResult(
                scenario_id=scenario_id,
                scenario_description=desc,
                target_agent=target_agent,
                status="FAIL",
                failure_category="constraint_violation",
                duration_seconds=round(duration, 2),
                details="Study plan violated schedule constraints or daily study budget.",
                error=str(err),
            )
        except (
            RuntimeError,
            OSError,
        ) as err:
            duration = time.time() - start
            return EvaluationScenarioResult(
                scenario_id=scenario_id,
                scenario_description=desc,
                target_agent=target_agent,
                status="FAIL",
                failure_category="unhandled_exception",
                duration_seconds=round(duration, 2),
                details="Failed to generate budget-compliant study plan.",
                error=str(err),
            )

    async def run_scenario_root_coordinator(
        self,
        plugin: ADKObservabilityPlugin,
        scenario_meta: dict[str, Any],
    ) -> EvaluationScenarioResult:
        """Scenario 1: Evaluates Root Coordinator delegation and user inquiry response."""
        scenario_id = scenario_meta.get("id", "scenario_1")
        desc = scenario_meta.get(
            "description", "14 days, beginner, 90 minutes daily plan request"
        )
        target_agent = "root_agent"
        start = time.time()
        sess_id = f"eval_root_{uuid.uuid4().hex[:6]}"
        request_text = scenario_meta.get(
            "request",
            "I am preparing for the Google Cloud Generative AI Leader certification in 14 days. I am a beginner and can study 90 minutes daily. Create my study plan.",
        )

        try:
            runner = InMemoryRunner(agent=root_agent, plugins=[plugin])
            await runner.session_service.create_session(
                app_name=runner.app_name,
                user_id="eval_user",
                session_id=sess_id,
            )
            response_text = ""
            user_content = types.Content(
                role="user",
                parts=[types.Part.from_text(text=request_text)],
            )

            async def _execute_root() -> str:
                resp = ""
                async for event in runner.run_async(
                    user_id="eval_user",
                    session_id=sess_id,
                    new_message=user_content,
                ):
                    event_content = getattr(event, "content", None)
                    if event_content and getattr(event_content, "parts", None):
                        parts = getattr(event_content, "parts", []) or []
                        for part in parts:
                            txt = getattr(part, "text", None)
                            if txt:
                                resp += str(txt)
                return resp

            response_text = await asyncio.wait_for(
                _execute_root(), timeout=self.timeout_seconds
            )
            duration = time.time() - start
            if len(response_text) < 50:
                raise ValueError(
                    f"Root coordinator returned empty or short response ({len(response_text)} chars)"
                )

            return EvaluationScenarioResult(
                scenario_id=scenario_id,
                scenario_description=desc,
                target_agent=target_agent,
                status="PASS",
                failure_category="none",
                duration_seconds=round(duration, 2),
                details=f"Root coordinator routed & answered ({len(response_text)} chars response).",
                metadata={"response_chars": len(response_text)},
            )
        except TimeoutError as err:
            duration = time.time() - start
            return EvaluationScenarioResult(
                scenario_id=scenario_id,
                scenario_description=desc,
                target_agent=target_agent,
                status="FAIL",
                failure_category="timeout",
                duration_seconds=round(duration, 2),
                details="Root coordinator execution timed out.",
                error=str(err),
            )
        except (ValueError, AssertionError) as err:
            duration = time.time() - start
            return EvaluationScenarioResult(
                scenario_id=scenario_id,
                scenario_description=desc,
                target_agent=target_agent,
                status="FAIL",
                failure_category="schema_validation",
                duration_seconds=round(duration, 2),
                details="Root coordinator returned empty or invalid response.",
                error=str(err),
            )
        except (
            RuntimeError,
            OSError,
        ) as err:
            duration = time.time() - start
            return EvaluationScenarioResult(
                scenario_id=scenario_id,
                scenario_description=desc,
                target_agent=target_agent,
                status="FAIL",
                failure_category="unhandled_exception",
                duration_seconds=round(duration, 2),
                details="Root coordinator failed to route or respond.",
                error=str(err),
            )

    async def run_all(
        self, persist: bool = True
    ) -> tuple[EvaluationSummaryReport, bool]:
        """Runs the four evaluation scenarios concurrently or sequentially.

        Returns (report, already_running_flag).
        """
        # Prevent concurrent duplicate runs
        if self._lock.locked():
            cached = load_evaluation_report()
            if cached:
                return cached, True
            # Return an empty temporary report indicating in-flight
            empty_report = EvaluationSummaryReport(
                run_id="in_flight",
                model=self.model,
                total_scenarios=4,
                passed_scenarios=0,
                failed_scenarios=0,
                total_duration_seconds=0.0,
            )
            return empty_report, True

        async with self._lock:
            # Check credentials early
            api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
            run_id = f"eval_{uuid.uuid4().hex[:8]}"

            if not api_key:
                err_msg = (
                    "Missing Gemini credentials (neither GOOGLE_API_KEY nor "
                    "GEMINI_API_KEY is configured in the environment)."
                )
                scenarios = [
                    EvaluationScenarioResult(
                        scenario_id=f"scenario_{i}",
                        scenario_description="Credential validation gate",
                        target_agent="auth",
                        status="FAIL",
                        failure_category="missing_credentials",
                        duration_seconds=0.0,
                        details="Credential check failed before agent execution.",
                        error=err_msg,
                    )
                    for i in [3, 5, 2, 1]
                ]
                report = EvaluationSummaryReport(
                    run_id=run_id,
                    model=self.model,
                    total_scenarios=4,
                    passed_scenarios=0,
                    failed_scenarios=4,
                    total_duration_seconds=0.0,
                    scenarios=scenarios,
                )
                if persist:
                    save_evaluation_report(report)
                return report, False

            setup_tracing()
            plugin = ADKObservabilityPlugin()
            facade = WorkshopFacade(observability_plugin=plugin)
            workflow = AdaptiveStudyWorkflow(observability_plugin=plugin)

            all_scenarios_meta = self.load_scenarios()
            scenario_meta_map = {s["id"]: s for s in all_scenarios_meta}

            overall_start = time.time()
            results: list[EvaluationScenarioResult] = []

            # 1. Topic Expert (Scenario 3)
            s3_meta = scenario_meta_map.get(
                "scenario_3", {"id": "scenario_3", "description": "Scenario 3"}
            )
            res_s3 = await self.run_scenario_topic_expert(facade, s3_meta)
            results.append(res_s3)

            # 2. Quiz Generator (Scenario 5)
            s5_meta = scenario_meta_map.get(
                "scenario_5", {"id": "scenario_5", "description": "Scenario 5"}
            )
            res_s5 = await self.run_scenario_quiz_generator(workflow, s5_meta)
            results.append(res_s5)

            # 3. Study Planner (Scenario 2)
            s2_meta = scenario_meta_map.get(
                "scenario_2", {"id": "scenario_2", "description": "Scenario 2"}
            )
            res_s2 = await self.run_scenario_study_planner(workflow, s2_meta)
            results.append(res_s2)

            # 4. Root Coordinator (Scenario 1)
            s1_meta = scenario_meta_map.get(
                "scenario_1", {"id": "scenario_1", "description": "Scenario 1"}
            )
            res_s1 = await self.run_scenario_root_coordinator(plugin, s1_meta)
            results.append(res_s1)

            total_duration = time.time() - overall_start
            passed = sum(1 for r in results if r.status == "PASS")
            failed = sum(1 for r in results if r.status == "FAIL")

            report = EvaluationSummaryReport(
                run_id=run_id,
                model=self.model,
                total_scenarios=len(results),
                passed_scenarios=passed,
                failed_scenarios=failed,
                total_duration_seconds=round(total_duration, 2),
                scenarios=results,
            )

            if persist:
                save_evaluation_report(report)

            return report, False
