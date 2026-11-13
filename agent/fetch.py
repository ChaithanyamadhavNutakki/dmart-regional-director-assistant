"""Validated data-fetch component with bounded retry handling.

The Validator approves the intent, route, date range, and reportable fields
before this component is called. This module executes only that approved
request through the parameterised query engine.
"""

from __future__ import annotations

from agent.query import query


MAX_QUERY_ATTEMPTS = 3


def fetch(
    interpretation,
    validation,
    *,
    simulated_failures=0,
    max_attempts=MAX_QUERY_ATTEMPTS,
    data_dir=None,
):
    """Run one validated data request, retrying up to three total attempts.

    Returns a structured dictionary containing success, query_result,
    attempts, executed, and error. Retries count as attempts, not tool calls.
    """
    if not isinstance(validation, dict) or not validation.get("valid"):
        return {
            "success": False,
            "query_result": None,
            "attempts": 0,
            "executed": None,
            "error": "A valid validation result is required before fetching data.",
        }

    try:
        attempt_limit = min(MAX_QUERY_ATTEMPTS, max(1, int(max_attempts)))
        failures_to_simulate = max(0, int(simulated_failures))
    except (TypeError, ValueError):
        return {
            "success": False,
            "query_result": None,
            "attempts": 0,
            "executed": None,
            "error": "Retry configuration must use whole numbers.",
        }

    last_error = None
    for attempt in range(1, attempt_limit + 1):
        try:
            if attempt <= failures_to_simulate:
                raise RuntimeError("Simulated database failure")

            result = query(
                interpretation,
                validation,
                data_dir=data_dir,
            )
            executed = (
                result.get("sql")
                or f"python:{result.get('query_type', 'data_query')}"
            )
            return {
                "success": True,
                "query_result": result,
                "attempts": attempt,
                "executed": executed,
                "error": None,
            }
        except Exception as exc:
            last_error = exc

    return {
        "success": False,
        "query_result": None,
        "attempts": attempt_limit,
        "executed": "agent.fetch.fetch",
        "error": str(last_error) if last_error else "Data query failed.",
    }
