"""Main orchestration layer for the DMart Regional Director Assistant.

Public entry point:
    handle(question, session_id, user_id="u1")

The orchestrator connects interpretation, routing, validation, data access,
calculation, synthesis, grounding, and JSONL audit recording. It keeps session
context in memory for the lifetime of the Python process.
"""

from __future__ import annotations

import importlib
import os
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from agent.understand import understand
from agent.route import route as select_route
from agent.validate import validate
from agent.query import query
from agent.calculate import calculate
from agent.synthesize import synthesize
from agent.ground import ground
from agent.record import record


MAX_QUERY_ATTEMPTS = 3
DEFAULT_USER_ID = "u1"
DEFAULT_LOG_PATH = "logs/runs.jsonl"
_SESSION_CONTEXT: dict[tuple[str, str], dict[str, Any]] = {}


def _session_key(user_id: str, session_id: str) -> tuple[str, str]:
    return str(user_id), str(session_id)


def _load_weather_callable():
    """Resolve the project's weather stub without requiring a live API."""
    candidates = (
        ("tools.weather", "get_weather"),
        ("tools.weather", "weather"),
        ("agent.weather_tool", "get_weather"),
        ("agent.weather_tool", "weather"),
        ("weather_tool", "get_weather"),
        ("weather_tool", "weather"),
    )
    for module_name, function_name in candidates:
        try:
            module = importlib.import_module(module_name)
            function = getattr(module, function_name, None)
            if callable(function):
                return function
        except ImportError:
            continue
    return None


def _run_weather(entities: dict[str, Any]) -> dict[str, Any]:
    """Call the local weather stub using the resolved store and date."""
    weather_function = _load_weather_callable()
    if weather_function is None:
        return {
            "success": False,
            "error": "The local weather stub is not present in the repository.",
            "store": entities.get("store"),
            "date": entities.get("date"),
        }

    # The weather stub interface is kept deliberately small. A TypeError
    # indicates an incompatible stub contract and is handled as a tool failure.
    result = weather_function(
        city=entities.get("store"),
        date=entities.get("date"),
    )

    if not isinstance(result, dict):
        raise ValueError("The weather stub must return a dictionary.")

    if not result.get("ok"):
        return {
            "success": False,
            "error": result.get("error", "Weather tool failed."),
            "store": entities.get("store"),
            "date": entities.get("date"),
        }

    return {
        "success": True,
        "store": result.get("city"),
        "date": result.get("date"),
        "temperature_c": result.get("temperature_c"),
        "humidity_pct": result.get("humidity_pct"),
        "wind_kmh": result.get("wind_kmh"),
        "rainfall_mm": result.get("rain_mm"),
        "mode": result.get("mode"),
    }


def _failure_synthesis(status: str, message: str) -> dict[str, Any]:
    return {
        "status": status,
        "answer_text": message,
        "calculation_type": None,
    }


def _count_tokens_est(question: str, answer_text: str) -> int:
    return len((str(question) + " " + str(answer_text)).split())


def _log_record(
    *,
    run_id: str,
    user_id: str,
    session_id: str,
    question: str,
    interpretation: dict[str, Any],
    route_name: str,
    executed: str | None,
    attempts: int,
    tools_called: list[str],
    grounded_result: dict[str, Any],
    latency_ms: float,
    tool_calls: int,
) -> dict[str, Any]:
    answer_text = grounded_result.get("answer_text", "")
    tokens_est = _count_tokens_est(question, answer_text)

    return {
        "run_id": run_id,
        "user_id": user_id,
        "session_id": session_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "question": question,
        "intent": interpretation.get("intent"),
        "confidence": interpretation.get("confidence", 1.0),
        "route": route_name,
        "executed": executed,
        "attempts": attempts,
        "tools_called": tools_called,
        "status": grounded_result.get("status"),
        "answer_text": answer_text,
        "evidence": grounded_result.get("evidence", []),
        "grounded_values": grounded_result.get("grounded_values", []),
        "latency_ms": round(latency_ms, 3),
        "tokens_est": tokens_est,
        "tool_calls": tool_calls,
        "ungrounded_numbers": grounded_result.get("ungrounded_numbers", 0),
        "budget_exceeded": tokens_est > 150,
    }


def handle(question, session_id, user_id=DEFAULT_USER_ID):
    """Handle one question and append one audit record.

    Args:
        question: User's natural-language question.
        session_id: Identifier used to isolate conversational context.
        user_id: User identifier; defaults to "u1" as specified.

    Returns:
        A dictionary containing the final status, answer, intent, route,
        evidence, grounding values, and execution metadata.
    """
    started = time.monotonic()
    run_id = str(uuid.uuid4())
    question = question if isinstance(question, str) else str(question)
    session_id = str(session_id)
    user_id = str(user_id)

    context_key = _session_key(user_id, session_id)
    prior_context = dict(_SESSION_CONTEXT.get(context_key, {}))

    interpretation = understand(question, context=prior_context)
    _SESSION_CONTEXT[context_key] = dict(interpretation.get("context") or {})
    intent = interpretation.get("intent")

    selected_route = select_route(interpretation, question)
    validation = validate(interpretation, selected_route=selected_route)

    query_result = None
    calculation_result = None
    weather_result = None
    executed = None
    attempts = 0
    tools_called: list[str] = []
    tool_calls = 0
    actual_route = "none"

    if not validation.get("valid"):
        synthesis_result = _failure_synthesis(
            validation.get("status", "Escalated"),
            validation.get("reason", "The request could not be validated."),
        )
    else:
        actual_route = selected_route

        # Weather-only requests make one tool call and no data-query attempt.
        if intent == "weather":
            tools_called.append("weather_tool")
            tool_calls += 1
            executed = "weather_tool"
            try:
                weather_result = _run_weather(interpretation.get("entities") or {})
                synthesis_result = synthesize(
                    interpretation=interpretation,
                    weather_result=weather_result,
                )
            except Exception as exc:
                weather_result = {"success": False, "error": str(exc)}
                synthesis_result = _failure_synthesis(
                    "Safe Failure",
                    "Weather information could not be retrieved for the requested store and date.",
                )

        else:
            # A Python or SQL route is one data-tool call, irrespective of
            # retries. The weather tool is counted separately when combined.
            tool_calls += 1
            simulated_failures = max(
                0, int(os.getenv("SIMULATE_DB_FAILURES", "0") or "0")
            )
            last_error = None
            executed = "agent.query.query"

            for attempt in range(1, MAX_QUERY_ATTEMPTS + 1):
                attempts = attempt
                try:
                    if attempt <= simulated_failures:
                        raise RuntimeError("Simulated database failure")
                    query_result = query(
                        interpretation,
                        validation,
                    )
                    executed = (
                        query_result.get("sql")
                        or f"python:{query_result.get('query_type', 'data_query')}"
                    )
                    last_error = None
                    break
                except Exception as exc:
                    last_error = exc

            if query_result is None:
                if selected_route == "python+weather":
                    actual_route = "python"
                synthesis_result = _failure_synthesis(
                    "Escalated",
                    "The data query failed after three total attempts. No result has been returned.",
                )
            else:
                try:
                    calculation_result = calculate(
                        query_result,
                        interpretation=interpretation,
                        question=question,
                    )
                    if selected_route == "python+weather":
                        tools_called.append("weather_tool")
                        tool_calls += 1
                        try:
                            weather_result = _run_weather(
                                interpretation.get("entities") or {}
                            )
                        except Exception as exc:
                            weather_result = {
                                "success": False,
                                "error": str(exc),
                            }
                    synthesis_result = synthesize(
                        calculation_result=calculation_result,
                        interpretation=interpretation,
                        query_result=query_result,
                        weather_result=weather_result,
                    )
                except Exception:
                    synthesis_result = _failure_synthesis(
                        "Escalated",
                        "The fetched data could not be processed safely. The request has been escalated for review.",
                    )

    # The weather tool may have been unavailable or returned a failure. The
    # data portion of a combined request remains separately grounded.
    try:
        grounded_result = ground(
            synthesis_result=synthesis_result,
            calculation_result=calculation_result,
            query_result=query_result,
            interpretation=interpretation,
            weather_result=weather_result,
            quoted_constants=(
                [75] if "below 75%" in str(synthesis_result.get("answer_text", ""))
                else []
            ),
        )
    except Exception:
        grounded_result = {
            "status": "Safe Failure",
            "answer_text": "The response could not be grounded safely and has been withheld.",
            "calculation_type": None,
            "evidence": [],
            "grounded_values": [],
            "ungrounded_numbers": 0,
        }

    # Record the actual route only if a data or weather tool was started.
    # Rejected requests retain route=none and no execution metadata.
    if tool_calls == 0:
        actual_route = "none"

    latency_ms = (time.monotonic() - started) * 1000
    audit = _log_record(
        run_id=run_id,
        user_id=user_id,
        session_id=session_id,
        question=question,
        interpretation=interpretation,
        route_name=actual_route,
        executed=executed,
        attempts=attempts,
        tools_called=tools_called,
        grounded_result=grounded_result,
        latency_ms=latency_ms,
        tool_calls=tool_calls,
    )

    # Read AGENT_LOG_PATH on every invocation, not at module import time.
    log_path = os.getenv("AGENT_LOG_PATH", DEFAULT_LOG_PATH)
    record(audit, log_path=log_path)

    return {
        **grounded_result,
        "run_id": run_id,
        "intent": intent,
        "confidence": interpretation.get("confidence", 1.0),
        "route": actual_route,
        "executed": executed,
        "attempts": attempts,
        "tools_called": tools_called,
        "tool_calls": tool_calls,
        "latency_ms": round(latency_ms, 3),
        "tokens_est": audit["tokens_est"],
        "budget_exceeded": audit["budget_exceeded"],
        "ungrounded_numbers": grounded_result.get("ungrounded_numbers", 0),
        "interpretation": interpretation,
        "validation": validation,
    }


def clear_session(session_id, user_id=DEFAULT_USER_ID):
    """Clear one session's in-memory context."""
    _SESSION_CONTEXT.pop(_session_key(str(user_id), str(session_id)), None)


def clear_all_sessions():
    """Clear all in-memory conversational context (primarily for test setup)."""
    _SESSION_CONTEXT.clear()
