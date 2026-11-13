# ==========================================
# DMart Regional Director Assistant
# Component 3: Validator
# File: agent/validate.py
# ==========================================

from datetime import date


# Exact reportable-field allowlist from docs/requirement.md.
APPROVED_FIELDS = {
    "store_daily": {
        "revenue_inr",
        "daily_target_inr",
        "footfall",
        "stockout_hours",
        "discount_pct",
        "achievement_pct",
        "performance_band",
    },
    "inventory": {
        "stock_units",
        "reorder_threshold",
    },
    "feedback": {
        "rating",
        "theme",
    },
}

# These columns are permitted only as filters, grouping keys, or labels.
KEY_ONLY_FIELDS = {
    "store",
    "store_id",
    "date",
    "product",
    "product_id",
}

# Fixed fields fetched for each supported intent.
INTENT_DATA_REQUIREMENTS = {
    "lookup": {
        "table": "store_daily",
        "fields_from_metric": True,
    },
    "target_vs_actual": {
        "table": "store_daily",
        "fields": [
            "revenue_inr",
            "daily_target_inr",
            "performance_band",
        ],
    },
    "comparison": {
        "table": "store_daily",
        "fields_from_metric": True,
    },
    "inventory": {
        "table": "inventory",
        "fields": ["stock_units", "reorder_threshold"],
    },
    "feedback": {
        "table": "feedback",
        "fields": ["rating", "theme"],
    },
}

SUPPORTED_START_DATE = date(2026, 4, 1)
SUPPORTED_END_DATE = date(2026, 6, 29)

# Canonical metrics that may be selected by lookup/comparison.
METRIC_TABLE_FIELDS = {
    "revenue_inr": "store_daily",
    "daily_target_inr": "store_daily",
    "footfall": "store_daily",
    "stockout_hours": "store_daily",
    "discount_pct": "store_daily",
    "achievement_pct": "store_daily",
    "performance_band": "store_daily",
    "stock_units": "inventory",
    "reorder_threshold": "inventory",
    "rating": "feedback",
    "theme": "feedback",
}


def _result(valid, status, reason, intent=None, table=None, fields=None,
            route="none"):
    """Build a consistent validator response."""

    return {
        "valid": valid,
        "status": status,
        "reason": reason,
        "intent": intent,
        "table": table,
        "fields": list(fields or []),
        "route": route,
    }


def _date_is_supported(value):
    """Check a single ISO date against the available dataset period."""

    if not isinstance(value, str):
        return False

    try:
        parsed = date.fromisoformat(value)
    except ValueError:
        return False

    return SUPPORTED_START_DATE <= parsed <= SUPPORTED_END_DATE


def _period_is_supported(entities):
    """Validate the single date or inclusive date range used by an intent."""

    start_date = entities.get("start_date")
    end_date = entities.get("end_date")
    single_date = entities.get("date")

    if start_date or end_date:
        if not start_date or not end_date:
            return False
        if not _date_is_supported(start_date):
            return False
        if not _date_is_supported(end_date):
            return False
        return date.fromisoformat(start_date) <= date.fromisoformat(end_date)

    if single_date:
        return _date_is_supported(single_date)

    return False


def _required_fields(intent, entities):
    """Resolve the fixed measured fields required by an intent."""

    requirement = INTENT_DATA_REQUIREMENTS.get(intent)
    if requirement is None:
        return None, []

    table = requirement["table"]

    if requirement.get("fields_from_metric"):
        metric = entities.get("metric")
        if not metric:
            return table, []
        return table, [metric]

    return table, requirement["fields"]


def validate(interpretation, selected_route=None):
    """
    Validate an interpreted request before any data query is executed.

    Parameters
    ----------
    interpretation : dict
        Dictionary returned by agent.understand.understand().
    selected_route : str, optional
        Route returned by agent.route.route(). Supplying it allows the
        validator to confirm that a data route has been selected.

    Returns
    -------
    dict
        Structured validation result with valid/status/reason, dataset,
        approved measured fields, and route.

    This component does not execute SQL, access files, or call tools.
    """

    if not isinstance(interpretation, dict):
        return _result(
            False,
            "Clarification Needed",
            "The interpretation result is missing or invalid.",
        )

    intent = interpretation.get("intent")
    entities = interpretation.get("entities") or {}
    route = selected_route or "none"

    # Interpretive safety outcomes take precedence over data validation.
    if intent == "unsupported_metric":
        return _result(
            False,
            "Safe Failure",
            "The requested metric is not in the approved reportable-field list.",
            intent=intent,
            route="none",
        )

    if intent in {"out_of_scope", "diagnostic"}:
        return _result(
            False,
            "Escalated",
            "The request is outside the supported analytics scope or requires analyst judgement.",
            intent=intent,
            route="none",
        )

    if interpretation.get("needs_clarification") or interpretation.get(
        "missing_entities"
    ) or interpretation.get("unresolved_entities"):
        return _result(
            False,
            "Clarification Needed",
            interpretation.get("clarification_question")
            or "Resolve the missing or ambiguous required entities before proceeding.",
            intent=intent,
            route="none",
        )

    # Weather is an external tool route and has no dataset fields to allowlist.
    if intent == "weather":
        if route not in {"weather", "python+weather"}:
            return _result(
                False,
                "Clarification Needed",
                "A valid weather route has not been selected.",
                intent=intent,
                route="none",
            )

        if not _period_is_supported(entities):
            return _result(
                False,
                "Safe Failure",
                "The requested weather date is outside the supported date range.",
                intent=intent,
                route="none",
            )

        return _result(
            True,
            "Valid",
            "The weather request has a supported store and date and may proceed to the weather tool.",
            intent=intent,
            table=None,
            fields=[],
            route=route,
        )

    table, fields = _required_fields(intent, entities)

    if table is None:
        return _result(
            False,
            "Escalated",
            "No execution rule is defined for this intent.",
            intent=intent,
            route="none",
        )

    # Validate the dataset and every measured field before query execution.
    if table not in APPROVED_FIELDS:
        return _result(
            False,
            "Safe Failure",
            "The requested dataset is not approved.",
            intent=intent,
            table=table,
            fields=fields,
            route="none",
        )

    if not fields:
        return _result(
            False,
            "Clarification Needed",
            "A required approved metric has not been resolved.",
            intent=intent,
            table=table,
            route="none",
        )

    for field in fields:
        if field in KEY_ONLY_FIELDS or field not in APPROVED_FIELDS[table]:
            return _result(
                False,
                "Safe Failure",
                "The requested measured field is not approved for this dataset.",
                intent=intent,
                table=table,
                fields=fields,
                route="none",
            )

    # The metric-to-table mapping prevents a valid field being used against
    # the wrong dataset.
    for field in fields:
        expected_table = METRIC_TABLE_FIELDS.get(field)
        if expected_table != table:
            return _result(
                False,
                "Safe Failure",
                "The requested field does not belong to the selected dataset.",
                intent=intent,
                table=table,
                fields=fields,
                route="none",
            )

    # Date range and single-date checks happen before a data query.
    if intent in {"lookup", "target_vs_actual", "comparison"}:
        if not _period_is_supported(entities):
            return _result(
                False,
                "Safe Failure",
                "The requested date or date range is outside 2026-04-01 to 2026-06-29.",
                intent=intent,
                table=table,
                fields=fields,
                route="none",
            )

    # Ensure the route is consistent with the fixed intent-to-route contract.
    expected_routes = {
        "lookup": {"python", "sql", "python+weather"},
        "target_vs_actual": {"python", "python+weather"},
        "comparison": {"sql"},
        "inventory": {"sql"},
        "feedback": {"sql"},
    }

    if route not in expected_routes.get(intent, set()):
        return _result(
            False,
            "Clarification Needed",
            "A valid execution route has not been selected for this intent.",
            intent=intent,
            table=table,
            fields=fields,
            route="none",
        )

    # Range lookup must use SQL; single-date lookup must use Python.
    if intent == "lookup":
        is_range = bool(entities.get("start_date") and entities.get("end_date"))
        if is_range and route != "sql":
            return _result(
                False,
                "Safe Failure",
                "A date-range lookup must use the SQL route.",
                intent=intent,
                table=table,
                fields=fields,
                route="none",
            )
        if not is_range and route not in {"python", "python+weather"}:
            return _result(
                False,
                "Safe Failure",
                "A single-date lookup must use the Python route.",
                intent=intent,
                table=table,
                fields=fields,
                route="none",
            )

    if intent == "target_vs_actual" and (
        entities.get("start_date") or entities.get("end_date")
    ):
        return _result(
            False,
            "Safe Failure",
            "Target checks support one date only, not a date range.",
            intent=intent,
            table=table,
            fields=fields,
            route="none",
        )

    return _result(
        True,
        "Valid",
        "The request uses approved fields and may proceed to the query component.",
        intent=intent,
        table=table,
        fields=fields,
        route=route,
    )
