"""JSONL audit logging for the DMart Regional Director Assistant.

The orchestration layer is responsible for constructing the complete audit
record and reading AGENT_LOG_PATH inside handle() on every request. This
module validates the record shape and appends exactly one JSON object per line.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping


REQUIRED_LOG_FIELDS = (
    "run_id",
    "user_id",
    "session_id",
    "timestamp",
    "question",
    "intent",
    "confidence",
    "route",
    "executed",
    "attempts",
    "tools_called",
    "status",
    "answer_text",
    "evidence",
    "grounded_values",
    "latency_ms",
    "tokens_est",
    "tool_calls",
    "ungrounded_numbers",
    "budget_exceeded",
)

ALLOWED_ROUTES = {"python", "sql", "weather", "python+weather", "none"}
ALLOWED_STATUSES = {
    "Answered",
    "Drafted",
    "Clarification Needed",
    "Escalated",
    "Safe Failure",
}


def validate_log_record(log_record: Mapping[str, Any]) -> None:
    """Raise ValueError when a record does not satisfy the audit contract."""
    if not isinstance(log_record, Mapping):
        raise TypeError("log_record must be a mapping")

    missing = [field for field in REQUIRED_LOG_FIELDS if field not in log_record]
    if missing:
        raise ValueError("Missing required log fields: " + ", ".join(missing))

    if log_record["route"] not in ALLOWED_ROUTES:
        raise ValueError(f"Unsupported route: {log_record['route']!r}")

    if log_record["status"] not in ALLOWED_STATUSES:
        raise ValueError(f"Unsupported status: {log_record['status']!r}")

    for field in ("attempts", "tool_calls", "latency_ms", "tokens_est", "ungrounded_numbers"):
        value = log_record[field]
        if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0:
            raise ValueError(f"{field} must be a non-negative number")

    if not isinstance(log_record["tools_called"], list):
        raise ValueError("tools_called must be a list")

    if not isinstance(log_record["evidence"], list):
        raise ValueError("evidence must be a list")

    if not isinstance(log_record["grounded_values"], list):
        raise ValueError("grounded_values must be a list")

    if not isinstance(log_record["budget_exceeded"], bool):
        raise ValueError("budget_exceeded must be a boolean")


def record(log_record: Mapping[str, Any], log_path: str | Path | None = None) -> dict[str, Any]:
    """Append one validated audit record as a JSON Lines entry.

    Args:
        log_record: Complete record assembled by the public handle() function.
        log_path: Explicit path. The orchestrator should read AGENT_LOG_PATH
            during each handle() call and pass the resulting path here. If no
            path is supplied, the default is logs/runs.jsonl.

    Returns:
        A small receipt containing the path and number of records appended.
    """
    validate_log_record(log_record)

    destination = Path(log_path) if log_path is not None else Path("logs/runs.jsonl")
    destination.parent.mkdir(parents=True, exist_ok=True)

    # Convert mappings to a plain dict so the JSON encoder receives a stable
    # top-level object. Unsupported values fail loudly rather than being
    # silently stringified and corrupting the audit trail.
    payload = json.dumps(dict(log_record), ensure_ascii=False, separators=(",", ":"))

    with destination.open("a", encoding="utf-8", newline="\n") as log_file:
        log_file.write(payload + "\n")

    return {"path": str(destination), "records_appended": 1}


append_log = record
