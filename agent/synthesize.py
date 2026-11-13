# ==========================================
# DMart Regional Director Assistant
# Component 6: Answer Synthesis
# File: agent/synthesize.py
# ==========================================

from decimal import Decimal, InvalidOperation


def _money(value):
    """Format a numeric value using the required INR format."""

    number = _number(value)
    return f"INR {number:.2f}"


def _number(value):
    if value is None:
        raise ValueError("A required numeric value is missing.")

    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        raise ValueError(f"Expected a numeric value, received: {value!r}")


def _percentage(value):
    return f"{_number(value):.2f}%"


def _status_result(status, answer_text, calculation_result=None):
    """Return the synthesis output without inventing evidence or grounding."""

    return {
        "status": status,
        "answer_text": answer_text,
        "calculation_type": (
            calculation_result.get("calculation_type")
            if isinstance(calculation_result, dict) else None
        ),
    }


def _synthesize_lookup(result):
    if not result.get("values", {}).get("found"):
        return _status_result(
            "Safe Failure",
            "No record was found for the requested store and date.",
            result,
        )

    records = result.get("values", {}).get("records", [])
    if not records:
        return _status_result(
            "Safe Failure",
            "No record was found for the requested store and date.",
            result,
        )

    record = records[0]
    metric = next(
        (field for field in record if field not in {"store", "date"}),
        None,
    )
    if metric is None or record.get(metric) is None:
        return _status_result(
            "Safe Failure",
            "The requested metric value is not available in the matching record.",
            result,
        )

    store = record.get("store")
    record_date = record.get("date")
    value = record[metric]

    if metric in {"revenue_inr", "daily_target_inr"}:
        displayed_value = _money(value)
    elif metric in {"discount_pct", "achievement_pct"}:
        displayed_value = _percentage(value)
    elif metric == "footfall":
        displayed_value = f"{_number(value):.2f}"
    elif metric == "stockout_hours":
        displayed_value = f"{_number(value):.2f}"
    else:
        displayed_value = str(value)

    return _status_result(
        "Answered",
        f"{store}'s {metric} on {record_date} was {displayed_value}.",
        result,
    )


def _synthesize_average(result):
    values = result.get("values", {})
    if not values.get("found") or values.get("average") is None:
        return _status_result(
            "Safe Failure",
            values.get("message")
            or "No matching records were found for the requested period.",
            result,
        )

    metric = values.get("metric")
    store = values.get("store")
    average = values.get("average")

    if metric in {"revenue_inr", "daily_target_inr"}:
        displayed_value = _money(average)
    elif metric in {"discount_pct", "achievement_pct"}:
        displayed_value = _percentage(average)
    else:
        displayed_value = f"{_number(average):.2f}"

    return _status_result(
        "Answered",
        f"{store}'s average {metric} over the requested date range was {displayed_value}.",
        result,
    )


def _synthesize_target(result):
    values = result.get("values", {})
    if not values.get("found"):
        return _status_result(
            "Safe Failure",
            values.get("message")
            or "No record was found for the requested store and date.",
            result,
        )

    store = values.get("store")
    record_date = values.get("date")
    revenue = _money(values.get("revenue_inr"))
    target = _money(values.get("daily_target_inr"))
    achievement = _percentage(values.get("achievement_pct"))
    band = values.get("performance_band")

    answer = (
        f"{store} recorded revenue of {revenue} against a target of {target} "
        f"on {record_date}. Achievement was {achievement}; "
        f"the stored performance band was {band}."
    )

    if values.get("alert"):
        answer += (
            " This result is held as a draft for human approval because it is "
            "in the Poor performance band and below 75% of target."
        )
        return _status_result("Drafted", answer, result)

    return _status_result("Answered", answer, result)


def _synthesize_comparison(result):
    values = result.get("values", {})
    ranking = values.get("ranking") or []

    if not ranking:
        return _status_result(
            "Safe Failure",
            values.get("message")
            or "No matching comparison records were found.",
            result,
        )

    metric = values.get("metric")
    direction = values.get("direction")
    ordering = "highest to lowest" if direction == "DESC" else "lowest to highest"

    lines = [
        f"Store comparison for {metric}, ranked {ordering}:"
    ]
    for item in ranking:
        value = item.get(metric)
        if metric in {"revenue_inr", "daily_target_inr"}:
            displayed_value = _money(value)
        elif metric in {"discount_pct", "achievement_pct"}:
            displayed_value = _percentage(value)
        else:
            displayed_value = f"{_number(value):.2f}"
        lines.append(
            f"{item.get('rank')}. {item.get('store')}: {displayed_value}"
        )

    return _status_result("Answered", "\n".join(lines), result)


def _synthesize_inventory(result):
    values = result.get("values", {})
    if values.get("no_shortage"):
        return _status_result(
            "Answered",
            "No stores are below the reorder threshold for this product.",
            result,
        )

    rows = values.get("below_threshold") or []
    if not rows:
        return _status_result(
            "Safe Failure",
            "No matching inventory records were found for the requested product.",
            result,
        )

    lines = ["Stores below the reorder threshold:"]
    for row in rows:
        lines.append(
            f"- {row.get('store')}: {row.get('stock_units')} units in stock; "
            f"reorder threshold {row.get('reorder_threshold')} units."
        )

    return _status_result("Answered", "\n".join(lines), result)


def _synthesize_feedback(result):
    values = result.get("values", {})
    if not values.get("found"):
        return _status_result(
            "Safe Failure",
            "No feedback records were found for the requested store.",
            result,
        )

    store = values.get("store")
    average = values.get("average_rating")
    rated_rows = values.get("rated_rows")
    total_rows = values.get("total_rows")
    theme = values.get("most_frequent_theme")

    if average is None:
        rating_text = "No rated feedback rows were available"
    else:
        rating_text = f"Average rating was {average} across {rated_rows} rated rows"

    if theme is None:
        theme_text = "No feedback theme was available"
    else:
        theme_text = f"the most frequent theme was '{theme}'"

    answer = (
        f"{store} feedback summary: {rating_text}; total feedback rows: "
        f"{total_rows}; {theme_text}."
    )
    return _status_result("Answered", answer, result)


def _synthesize_weather(weather_result):
    if not isinstance(weather_result, dict) or not weather_result.get("success"):
        return _status_result(
            "Safe Failure",
            "Weather information could not be retrieved for the requested store and date.",
        )

    # Weather result field names are intentionally read from the weather
    # component's structured output; no weather values are fabricated here.
    store = weather_result.get("store")
    record_date = weather_result.get("date")
    temperature = weather_result.get("temperature_c")
    humidity = weather_result.get("humidity_pct")
    rainfall = weather_result.get("rainfall_mm")

    if any(value is None for value in (store, record_date, temperature, humidity, rainfall)):
        return _status_result(
            "Safe Failure",
            "The weather tool did not return all required weather fields.",
        )

    answer = (
        f"Weather for {store} on {record_date}: temperature "
        f"{_number(temperature):.1f} °C, humidity "
        f"{_number(humidity):.1f}%, rainfall "
        f"{_number(rainfall):.1f} mm."
    )
    return _status_result("Answered", answer)


def synthesize(calculation_result=None, interpretation=None,
               query_result=None, weather_result=None):
    """
    Convert structured calculation or weather results into a fixed-template
    answer and one of the five project completion statuses.

    Clarification, unsupported, out-of-scope, and diagnostic outcomes can be
    synthesised without running a query. Data evidence and numeric grounding
    are attached by the subsequent Ground component.
    """

    intent = (
        interpretation.get("intent")
        if isinstance(interpretation, dict) else None
    )

    if intent == "unsupported_metric":
        return _status_result(
            "Safe Failure",
            "The requested metric is not in the approved reportable-field list. I cannot query or approximate it.",
        )

    if intent in {"out_of_scope", "diagnostic"}:
        return _status_result(
            "Escalated",
            "This request is outside the supported analytics scope or requires analyst judgement. It has not been executed.",
        )

    if isinstance(interpretation, dict) and (
        interpretation.get("needs_clarification")
        or interpretation.get("missing_entities")
        or interpretation.get("unresolved_entities")
    ):
        clarification = (
            interpretation.get("clarification_question")
            or "Please clarify the missing or ambiguous required information."
        )
        return _status_result("Clarification Needed", clarification)

    if intent == "weather":
        return _synthesize_weather(weather_result)

    if weather_result is not None and intent in {"lookup", "target_vs_actual"}:
        if intent == "lookup":
            if not isinstance(calculation_result, dict):
                data_result = _status_result("Safe Failure", "The data lookup result is not available.")
            elif calculation_result.get("calculation_type") == "average":
                data_result = _synthesize_average(calculation_result)
            else:
                data_result = _synthesize_lookup(calculation_result)
        else:
            data_result = _synthesize_target(calculation_result or {})

        weather_text = (
            _synthesize_weather(weather_result).get("answer_text")
            if isinstance(weather_result, dict) and weather_result.get("success")
            else "Weather information could not be retrieved for the requested store and date."
        )
        data_result["answer_text"] = data_result.get("answer_text", "") + "\\n" + weather_text
        return data_result

    if intent == "lookup":
        if not isinstance(calculation_result, dict):
            return _status_result(
                "Safe Failure",
                "The lookup result is not available.",
            )
        if calculation_result.get("calculation_type") == "average":
            return _synthesize_average(calculation_result)
        return _synthesize_lookup(calculation_result)

    if intent == "target_vs_actual":
        return _synthesize_target(calculation_result or {})

    if intent == "comparison":
        return _synthesize_comparison(calculation_result or {})

    if intent == "inventory":
        return _synthesize_inventory(calculation_result or {})

    if intent == "feedback":
        return _synthesize_feedback(calculation_result or {})

    return _status_result(
        "Escalated",
        "The request could not be matched to a supported response template.",
    )
