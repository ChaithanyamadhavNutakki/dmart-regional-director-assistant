# ==========================================
# DMart Regional Director Assistant
# Component 7: Grounding
# File: agent/ground.py
# ==========================================

import re
from datetime import date


SOURCE_FILES = {
    "store_daily": "data/store_daily_clean.csv",
    "inventory": "data/inventory.csv",
    "feedback": "data/feedback.csv",
    "weather": "weather_tool",
}

# Numeric tokens are checked independently of ISO dates and product sizes.
NUMBER_PATTERN = re.compile(r"(?<![A-Za-z0-9_])\d+(?:\.\d+)?(?![A-Za-z0-9_])")
ISO_DATE_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")
PRODUCT_SIZE_PATTERN = re.compile(r"\b\d+(?:\.\d+)?\s*(?:ml|l|kg|g)\b", re.IGNORECASE)


def _is_number(value):
    if isinstance(value, bool) or value is None:
        return False
    if isinstance(value, (int, float)):
        return True
    if isinstance(value, str):
        try:
            float(value)
            return bool(re.fullmatch(r"-?\d+(?:\.\d+)?", value.strip()))
        except ValueError:
            return False
    return False


MONEY_FIELDS = {"revenue_inr", "daily_target_inr"}
TWO_DECIMAL_FIELDS = {
    "discount_pct", "achievement_pct", "footfall", "stockout_hours",
    "rating", "average_rating",
}
WEATHER_FIELDS = {
    "temperature_c", "humidity_pct", "wind_kmh", "rain_mm", "rainfall_mm",
}
INTEGER_FIELDS = {
    "stock_units", "reorder_threshold", "rated_rows", "total_rows",
    "shortage_count", "theme_frequency", "rank",
}


def _format_grounded_token(value, field_name=None):
    """Format fetched values to the same precision used by answer templates."""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value).strip()

    if field_name in MONEY_FIELDS or field_name in TWO_DECIMAL_FIELDS:
        return f"{number:.2f}"
    if field_name in WEATHER_FIELDS:
        return f"{number:.1f}"
    if field_name in INTEGER_FIELDS:
        return str(int(number)) if number.is_integer() else str(value).strip()
    return str(value).strip()


def _collect_numeric_values(value, output, field_name=None):
    """Collect formatted numeric values from structured sources, never answer text."""

    if isinstance(value, dict):
        metric_name = value.get("metric")
        for key, item in value.items():
            # Dates and identifiers are not measured numeric evidence.
            if key in {"date", "start_date", "end_date", "store_id", "product_id"}:
                continue
            effective_key = metric_name if key == "average" and metric_name else key
            _collect_numeric_values(item, output, effective_key)
    elif isinstance(value, (list, tuple)):
        for item in value:
            _collect_numeric_values(item, output, field_name)
    elif _is_number(value):
        token = _format_grounded_token(value, field_name)
        if token not in output:
            output.append(token)


def _display_number_tokens(answer_text):
    """Extract numeric tokens for checking; omit dates and product-size tokens."""

    text = str(answer_text or "")
    ignored_spans = []

    for pattern in (ISO_DATE_PATTERN,):
        for match in re.finditer(r"\b\d{4}-\d{2}-\d{2}\b", text):
            ignored_spans.append(match.span())

    for match in PRODUCT_SIZE_PATTERN.finditer(text):
        ignored_spans.append(match.span())

    tokens = []
    for match in NUMBER_PATTERN.finditer(text):
        if any(match.start() >= start and match.end() <= end for start, end in ignored_spans):
            continue
        tokens.append(match.group(0))
    return tokens


def _numeric_equivalent(left, right):
    try:
        return float(left) == float(right)
    except (TypeError, ValueError):
        return str(left) == str(right)


def _source_evidence(query_result, interpretation, weather_result):
    evidence = []
    entities = (interpretation or {}).get("entities") or {}

    if isinstance(query_result, dict) and query_result.get("success"):
        table = query_result.get("table")
        if table in SOURCE_FILES:
            records = query_result.get("records") or []
            first = records[0] if records else {}
            fields = list(query_result.get("fields") or [])
            if table == "store_daily":
                fields = fields or [
                    key for key in first
                    if key not in {"store", "store_id", "date"}
                ]
            elif table == "inventory":
                fields = fields or [
                    key for key in first
                    if key not in {"store", "store_id", "product", "product_id"}
                ]
            elif table == "feedback":
                fields = fields or [
                    key for key in first
                    if key not in {"store", "store_id", "date"}
                ]

            stores = sorted({
                row.get("store") for row in records if row.get("store")
            })
            dates = sorted({
                row.get("date") for row in records if row.get("date")
            })

            if (
                query_result.get("query_type", "").startswith("store_comparison")
                or (table == "inventory" and not entities.get("store"))
            ):
                evidence_store = "all"
            elif len(stores) == 1:
                evidence_store = stores[0]
            else:
                evidence_store = entities.get("store")

            if entities.get("start_date") and entities.get("end_date"):
                evidence_date = (
                    f"{entities['start_date']} to {entities['end_date']}"
                )
            elif len(dates) == 1:
                evidence_date = dates[0]
            else:
                evidence_date = entities.get("date")

            evidence.append({
                "source": SOURCE_FILES[table],
                "fields": fields,
                "store": evidence_store,
                "date": evidence_date,
            })

    if isinstance(weather_result, dict) and weather_result.get("success"):
        evidence.append({
            "source": SOURCE_FILES["weather"],
            "fields": ["temperature_c", "humidity_pct", "wind_kmh", "rain_mm"],
            "store": weather_result.get("store") or entities.get("store"),
            "date": weather_result.get("date") or entities.get("date"),
        })

    return evidence


def ground(synthesis_result, calculation_result=None, query_result=None,
           interpretation=None, weather_result=None, quoted_constants=None):
    """
    Attach source evidence and numeric grounding metadata to a synthesized reply.

    grounded_values is assembled from structured fetched/calculated/tool data,
    plus explicitly supplied fixed constants. It is not generated by scanning
    the final answer. The answer is scanned only to count unmatched numbers.
    """

    if not isinstance(synthesis_result, dict):
        raise ValueError("Grounding requires a synthesis result dictionary.")

    result = dict(synthesis_result)
    answer_text = str(result.get("answer_text") or "")

    numeric_sources = {
        "calculation": calculation_result,
        "query": query_result.get("records", []) if isinstance(query_result, dict) else None,
        "weather": weather_result,
    }
    candidates = []
    for source_data in numeric_sources.values():
        _collect_numeric_values(source_data, candidates)

    for constant in quoted_constants or []:
        if _is_number(constant):
            token = str(constant).strip()
            if token not in candidates:
                candidates.append(token)

    # Keep grounded values in a stable order and avoid duplicates by value.
    grounded_values = []
    for token in candidates:
        if token not in grounded_values:
            grounded_values.append(token)

    displayed_numbers = _display_number_tokens(answer_text)
    ungrounded_numbers = sum(
        1 for token in displayed_numbers
        if not any(_numeric_equivalent(token, grounded) for grounded in grounded_values)
    )

    result["evidence"] = _source_evidence(
        query_result, interpretation, weather_result
    )
    result["grounded_values"] = grounded_values
    result["ungrounded_numbers"] = ungrounded_numbers
    return result


# Descriptive alias for callers that prefer an explicit function name.
attach_grounding = ground
