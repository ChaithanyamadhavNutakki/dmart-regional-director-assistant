# ==========================================
# DMart Regional Director Assistant
# Component 2: Router
# File: agent/route.py
# ==========================================

import re


# Weather wording supported by the agent specification.
WEATHER_PATTERNS = (
    r"\bweather\b",
    r"\brain(?:fall|ing)?\b",
    r"\btemperature\b",
    r"\bhumidity\b",
    r"\bhot\b",
    r"\bcold\b",
)


def _weather_requested(question):
    """Return True when the question explicitly includes weather wording."""

    if not isinstance(question, str):
        return False

    return any(
        re.search(pattern, question, re.IGNORECASE)
        for pattern in WEATHER_PATTERNS
    )


def _has_single_date(entities):
    """Return True when interpretation contains one resolved date, not a range."""

    return bool(
        entities.get("date")
        and not entities.get("start_date")
        and not entities.get("end_date")
    )


def route(interpretation, question=""):
    """
    Select the fixed execution route for an interpreted question.

    Parameters
    ----------
    interpretation : dict
        The dictionary returned by agent.understand.understand().
    question : str, optional
        Original user question. It is used only to detect a weather request
        combined with a supported one-store, one-date data request.

    Returns
    -------
    str
        One of: "python", "sql", "weather", "python+weather", or "none".

    This function only selects a route. It does not validate fields, execute
    queries, call the weather tool, or assign a completion status.
    """

    if not isinstance(interpretation, dict):
        return "none"

    intent = interpretation.get("intent")

    # Never route an interpretation that still needs clarification.
    if interpretation.get("needs_clarification", False):
        return "none"

    # These intents must not access data or external tools.
    if intent in {
        "unsupported_metric",
        "out_of_scope",
        "diagnostic",
    }:
        return "none"

    entities = interpretation.get("entities") or {}
    has_weather = _weather_requested(question)

    # Weather-only request.
    if intent == "weather":
        return "weather"

    # Single-store, single-date lookups use the Python data route.
    if intent == "lookup":
        if _has_single_date(entities):
            if has_weather:
                return "python+weather"
            return "python"

        # Date-range lookups use SQL. The specification does not define a
        # combined SQL-and-weather route.
        if entities.get("start_date") and entities.get("end_date"):
            return "sql"

        return "none"

    # Target checks use Python and accept one date only.
    if intent == "target_vs_actual":
        if _has_single_date(entities):
            if has_weather:
                return "python+weather"
            return "python"
        return "none"

    # These intents are always handled through parameterised SQL.
    if intent in {"comparison", "inventory", "feedback"}:
        return "sql"

    # Unknown or unsupported intent: fail closed.
    return "none"
