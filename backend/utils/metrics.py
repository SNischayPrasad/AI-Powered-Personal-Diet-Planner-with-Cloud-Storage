"""Minimal application metrics in Prometheus text format.

Cloud monitoring works on *metrics* (numbers over time) as well as logs. This module keeps a
few thread-safe counters and renders them in the Prometheus exposition format at
``GET /api/metrics`` — the format scraped by Prometheus, Grafana Agent, Datadog and
AWS Managed Prometheus.

Counters live in process memory, so each server instance reports its own numbers; a metrics
backend adds them up across instances. That is exactly how horizontally-scaled services are
monitored.
"""

import threading
from collections import defaultdict

LabelSet = tuple[tuple[str, str], ...]

DESCRIPTIONS = {
    "http_requests_total": "HTTP requests handled, by method, route template and status.",
    "auth_events_total": "Authentication events (register, login_success, login_failure, logout).",
    "plans_generated_total": "Diet plans generated, by engine that produced them.",
    "ai_fallbacks_total": "Times the AI provider failed and the rule-based engine was used.",
    "files_uploaded_total": "Files stored in cloud object storage.",
    "dependency_errors_total": "Failures talking to cloud dependencies (database, storage).",
}


def _escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


def _format_number(value: float) -> str:
    return str(int(value)) if float(value).is_integer() else repr(value)


class Metrics:
    """Thread-safe in-memory counters."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._counters: dict[str, dict[LabelSet, float]] = defaultdict(lambda: defaultdict(float))

    def inc(self, name: str, amount: float = 1.0, **labels: str) -> None:
        label_set: LabelSet = tuple(sorted((key, str(value)) for key, value in labels.items()))
        with self._lock:
            self._counters[name][label_set] += amount

    def render_prometheus(self) -> str:
        lines: list[str] = []
        with self._lock:
            for name in sorted(self._counters):
                lines.append(f"# HELP {name} {DESCRIPTIONS.get(name, name)}")
                lines.append(f"# TYPE {name} counter")
                for label_set, value in sorted(self._counters[name].items()):
                    labels = ",".join(f'{key}="{_escape(val)}"' for key, val in label_set)
                    series = f"{name}{{{labels}}}" if labels else name
                    lines.append(f"{series} {_format_number(value)}")
        return "\n".join(lines) + "\n"
