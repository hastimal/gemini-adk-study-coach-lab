"""Observability package exports for study-coach."""

from study_coach.observability.config import ObservabilityConfig
from study_coach.observability.instrumentation import (
    ADKObservabilityPlugin,
    sanitize_value,
    trace_workflow_step,
)
from study_coach.observability.metrics import (
    AGENT_CALLS_TOTAL,
    AGENT_ERRORS_TOTAL,
    CHAT_MESSAGES_TOTAL,
    DOCUMENT_OPERATIONS_TOTAL,
    DOCUMENT_RETRIEVAL_LATENCY_SECONDS,
    MODEL_INPUT_TOKENS_TOTAL,
    MODEL_OUTPUT_TOKENS_TOTAL,
    QUIZ_GENERATION_DURATION_SECONDS,
    QUIZ_SUBMISSIONS_TOTAL,
    REPLANNING_TOTAL,
    REQUEST_DURATION_SECONDS,
    REQUESTS_TOTAL,
    TOOL_CALLS_TOTAL,
    start_metrics_server,
    study_coach_registry,
)
from study_coach.observability.tracing import (
    get_tracer,
    setup_tracing,
    shutdown_tracing,
)

__all__ = [
    "AGENT_CALLS_TOTAL",
    "AGENT_ERRORS_TOTAL",
    "CHAT_MESSAGES_TOTAL",
    "DOCUMENT_OPERATIONS_TOTAL",
    "DOCUMENT_RETRIEVAL_LATENCY_SECONDS",
    "MODEL_INPUT_TOKENS_TOTAL",
    "MODEL_OUTPUT_TOKENS_TOTAL",
    "QUIZ_GENERATION_DURATION_SECONDS",
    "QUIZ_SUBMISSIONS_TOTAL",
    "REPLANNING_TOTAL",
    "REQUESTS_TOTAL",
    "REQUEST_DURATION_SECONDS",
    "TOOL_CALLS_TOTAL",
    "ADKObservabilityPlugin",
    "ObservabilityConfig",
    "get_tracer",
    "sanitize_value",
    "setup_tracing",
    "shutdown_tracing",
    "start_metrics_server",
    "study_coach_registry",
    "trace_workflow_step",
]
