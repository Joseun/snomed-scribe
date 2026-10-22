"""Observability wiring: OpenTelemetry traces + structured JSON logs sharing
a trace_id, Prometheus metrics for Grafana panels.

Hard rule: nothing sent to a telemetry backend here may carry note text, a
patient identifier, or clinician identity — only counts, confidence scores,
status transitions, and latencies (see docs/SPEC.md).
"""
import json
import logging
import os
from datetime import datetime, timezone

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from prometheus_client import Counter, Histogram, make_asgi_app

OTEL_EXPORTER_OTLP_ENDPOINT = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "http://otel-collector:4318")

suggestions_created_total = Counter(
    "clincode_suggestions_created_total", "Candidate suggestions created from extraction"
)
clinician_decisions_total = Counter(
    "clincode_clinician_decisions_total", "Clinician decisions on suggestions", ["action"]
)
extraction_latency_seconds = Histogram(
    "clincode_extraction_latency_seconds", "Latency of the extraction client call"
)
suggestion_confidence = Histogram(
    "clincode_suggestion_confidence", "Confidence score distribution of created/decided suggestions"
)


class JsonLogFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        span_context = trace.get_current_span().get_span_context()
        trace_id = format(span_context.trace_id, "032x") if span_context and span_context.trace_id else None
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "trace_id": trace_id,
        }
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload)


def setup_telemetry(app) -> None:
    resource = Resource.create({"service.name": "clincode-backend"})
    provider = TracerProvider(resource=resource)
    exporter = OTLPSpanExporter(endpoint=f"{OTEL_EXPORTER_OTLP_ENDPOINT}/v1/traces")
    provider.add_span_processor(BatchSpanProcessor(exporter))
    trace.set_tracer_provider(provider)

    FastAPIInstrumentor.instrument_app(app)

    handler = logging.StreamHandler()
    handler.setFormatter(JsonLogFormatter())
    root_logger = logging.getLogger()
    root_logger.handlers = [handler]
    root_logger.setLevel(logging.INFO)

    app.mount("/internal/metrics", make_asgi_app())


def get_tracer():
    return trace.get_tracer("clincode")
