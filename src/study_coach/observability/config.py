"""Observability configuration for Google ADK Study Coach."""

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class ObservabilityConfig:
    """Configuration settings for OpenTelemetry tracing and Prometheus metrics."""

    service_name: str = "study-coach"
    service_version: str = "0.7.0"
    environment: str = "development"
    otlp_endpoint: str = "http://localhost:4318"
    otlp_protocol: str = "http"  # 'http' or 'grpc'
    metrics_port: int = 8001
    enabled: bool = True
    export_traces: bool = True
    export_metrics: bool = True

    @classmethod
    def from_env(cls) -> "ObservabilityConfig":
        """Builds configuration from environment variables with safe defaults."""
        enabled_str = os.getenv("OTEL_ENABLED", "true").lower()
        enabled = enabled_str not in ("false", "0", "no", "off")

        traces_str = os.getenv("OTEL_TRACES_ENABLED", "true").lower()
        export_traces = traces_str not in ("false", "0", "no", "off")

        metrics_str = os.getenv("OTEL_METRICS_ENABLED", "true").lower()
        export_metrics = metrics_str not in ("false", "0", "no", "off")

        return cls(
            service_name=os.getenv("OTEL_SERVICE_NAME", "study-coach"),
            service_version=os.getenv("OTEL_SERVICE_VERSION", "0.7.0"),
            environment=os.getenv("OTEL_ENVIRONMENT", os.getenv("ENV", "development")),
            otlp_endpoint=os.getenv(
                "OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4318"
            ),
            otlp_protocol=os.getenv("OTEL_EXPORTER_OTLP_PROTOCOL", "http").lower(),
            metrics_port=int(os.getenv("OTEL_METRICS_PORT", "8001")),
            enabled=enabled,
            export_traces=export_traces,
            export_metrics=export_metrics,
        )
