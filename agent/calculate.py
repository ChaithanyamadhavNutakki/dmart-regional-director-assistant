# ==========================================
# DMart Regional Director Assistant
# Component 5: Calculation Engine
# File: agent/calculate.py
# ==========================================

from collections import Counter
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP


TWO_DECIMAL_PLACES = Decimal("0.01")
POOR_BAND = "Poor"
POOR_ACHIEVEMENT_THRESHOLD = Decimal("75")


def _decimal(value):
    """Convert a fetched numeric value to Decimal without float artefacts."""

    if value is None or value == "":
        return None

    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        raise ValueError(f"Expected a numeric fetched value, received: {value!r}")


def _round_two(value):
    """Apply the specification's round-half-up rule."""

    number = _decimal(value)
    if number is None:
        return None
    return number.quantize(TWO_DECIMAL_PLACES, rounding=ROUND_HALF_UP)


def _format_decimal(value):
    """Return a two-decimal string for a Decimal-compatible value."""

    rounded = _round_two(value)
    return None if rounded is None else format(rounded, ".2f")


def _base_result(query_result, calculation_type, **values):
    """Build a consistent calculation payload while retaining query lineage."""

    return {
        "success": True,
        "calculation_type": calculation_type,
        "table": query_result.get("table"),
        "query_type": query_result.get("query_type"),
        "source_row_count": query_result.get("row_count", 0),
        "fields": list(query_result.get("fields") or []),
        "values": values,
    }


def _require_query_result(query_result):
    if not isinstance(query_result, dict) or not query_result.get("success"):
        raise ValueError("Calculation requires a successful query result.")

    records = query_result.get("records")
    if not isinstance(records, list):
        raise ValueError("The query result must contain a records list.")

    return records


def _calculate_target(records, query_result):
    if not records:
        return _base_result(
            query_result,
            "target_vs_actual",
            found=False,
            alert=False,
            message="No record was found for the requested store and date.",
        )

    if len(records) != 1:
        raise ValueError("A target check must return exactly one store/date record.")

    record = records[0]
    revenue = _decimal(record.get("revenue_inr"))
    target = _decimal(record.get("daily_target_inr"))
    band = record.get("performance_band")

    if revenue is None or target is None or target == 0:
        raise ValueError("Revenue and a non-zero daily target are required.")

    achievement = (revenue / target) * Decimal("100")
    achievement_rounded = _round_two(achievement)

    alert = (
        str(band).strip().casefold() == POOR_BAND.casefold()
        and achievement < POOR_ACHIEVEMENT_THRESHOLD
    )

    return _base_result(
        query_result,
        "target_vs_actual",
        found=True,
        store=record.get("store"),
        date=record.get("date"),
        revenue_inr=_format_decimal(revenue),
        daily_target_inr=_format_decimal(target),
        achievement_pct=format(achievement_rounded, ".2f"),
        performance_band=band,
        alert=alert,
        status="Drafted" if alert else "Answered",
    )


def _calculate_average(records, query_result):
    if not records:
        return _base_result(
            query_result,
            "average",
            found=False,
            average=None,
            message="No matching records were found for the requested period.",
        )

    metric = (query_result.get("fields") or [None])[0]
    if not metric:
        raise ValueError("The query result does not identify the averaged metric.")

    record = records[0]
    if record.get("_value_count") is not None:
        value_count = int(record.get("_value_count") or 0)
        sum_cents = record.get("_sum_cents")
        if value_count == 0 or sum_cents is None:
            average = None
        else:
            average = (
                Decimal(str(sum_cents))
                / (Decimal(value_count) * Decimal("100"))
            )
    else:
        average = record.get(metric)

    if average is None:
        return _base_result(
            query_result,
            "average",
            found=False,
            metric=metric,
            average=None,
            message="No numeric values were available for the requested period.",
        )

    return _base_result(
        query_result,
        "average",
        found=True,
        store=record.get("store"),
        metric=metric,
        average=_format_decimal(average),
    )


def _comparison_direction(question, metric):
    """Resolve ranking direction from the closed wording in the specification."""

    text = (question or "").casefold()

    if "lowest" in text:
        return "ASC"
    if "highest" in text:
        return "DESC"

    if "worst" in text:
        return "DESC" if metric == "stockout_hours" else "ASC"
    if "best" in text:
        return "ASC" if metric == "stockout_hours" else "DESC"

    # Default comparison order is highest first.
    return "DESC"


def _calculate_comparison(records, query_result, question):
    metric = (query_result.get("fields") or [None])[0]
    if not metric:
        raise ValueError("The comparison query does not identify a metric.")

    direction = _comparison_direction(question, metric)
    calculated = []

    for record in records:
        if record.get("_value_count") is not None:
            value_count = int(record.get("_value_count") or 0)
            sum_cents = record.get("_sum_cents")
            if value_count == 0 or sum_cents is None:
                continue
            raw_value = (
                Decimal(str(sum_cents))
                / (Decimal(value_count) * Decimal("100"))
            )
        else:
            raw_value = record.get(metric)

        value = _round_two(raw_value)
        if value is None:
            continue
        calculated.append({
            "store": record.get("store"),
            metric: format(value, ".2f"),
            "_sort_value": value,
        })

    # Compare at two decimal places, then break ties by store name ascending,
    # irrespective of ranking direction.
    calculated.sort(
        key=lambda row: (
            -row["_sort_value"] if direction == "DESC" else row["_sort_value"],
            str(row.get("store") or ""),
        )
    )

    ranked = []
    for index, row in enumerate(calculated, start=1):
        ranked.append({
            "rank": index,
            "store": row["store"],
            metric: row[metric],
        })

    return _base_result(
        query_result,
        "comparison",
        found=bool(ranked),
        metric=metric,
        direction=direction,
        ranking=ranked,
        message=None if ranked else "No matching comparison records were found.",
    )


def _calculate_inventory(records, query_result):
    below_threshold = []

    for record in records:
        stock = _decimal(record.get("stock_units"))
        threshold = _decimal(record.get("reorder_threshold"))

        if stock is None or threshold is None:
            continue

        # Apply the strict threshold rule after retrieval; equality is not
        # a shortage.
        if stock < threshold:
            below_threshold.append({
                "store": record.get("store"),
                "product": record.get("product"),
                "stock_units": int(stock) if stock == stock.to_integral_value() else float(stock),
                "reorder_threshold": int(threshold) if threshold == threshold.to_integral_value() else float(threshold),
            })

    below_threshold.sort(key=lambda row: str(row.get("store") or ""))

    return _base_result(
        query_result,
        "inventory",
        found=bool(records),
        below_threshold=below_threshold,
        shortage_count=len(below_threshold),
        no_shortage=bool(records) and not below_threshold,
        message=(
            "No stores are below the reorder threshold for this product."
            if records and not below_threshold else None
        ),
    )


def _calculate_feedback(records, query_result):
    total_rows = len(records)
    rated_values = [
        _decimal(row.get("rating"))
        for row in records
        if row.get("rating") is not None and row.get("rating") != ""
    ]
    rated_values = [value for value in rated_values if value is not None]

    theme_counts = Counter(
        str(row.get("theme")).strip()
        for row in records
        if row.get("theme") is not None and str(row.get("theme")).strip()
    )

    average_rating = None
    if rated_values:
        average_rating = sum(rated_values, Decimal("0")) / Decimal(len(rated_values))

    most_frequent_theme = None
    theme_count = 0
    if theme_counts:
        highest_frequency = max(theme_counts.values())
        most_frequent_theme = sorted(
            theme for theme, count in theme_counts.items()
            if count == highest_frequency
        )[0]
        theme_count = highest_frequency

    return _base_result(
        query_result,
        "feedback",
        found=bool(records),
        average_rating=_format_decimal(average_rating),
        rated_rows=len(rated_values),
        total_rows=total_rows,
        most_frequent_theme=most_frequent_theme,
        theme_frequency=theme_count,
    )


def calculate(query_result, interpretation=None, question=""):
    """
    Calculate permitted derived results from a successful Query Engine result.

    Supported query types:
      - target_vs_actual
      - single_store_date_lookup (passed through as fetched values)
      - date_range_average
      - store_comparison_averages
      - store_comparison_single_date
      - inventory_below_threshold
      - store_feedback_rows

    Numeric averages and percentages use Decimal arithmetic and round-half-up.
    This component does not query data, assign general completion statuses,
    synthesize answer text, or create grounding/audit records.
    """

    records = _require_query_result(query_result)
    query_type = query_result.get("query_type")

    if query_type == "target_vs_actual":
        return _calculate_target(records, query_result)

    if query_type == "single_store_date_lookup":
        # The lookup value is already fetched and approved. Preserve it without
        # presenting it as a newly calculated metric.
        return _base_result(
            query_result,
            "lookup",
            found=bool(records),
            records=records,
            message=None if records else "No record was found for the requested store and date.",
        )

    if query_type == "date_range_average":
        return _calculate_average(records, query_result)

    if query_type in {
        "store_comparison_averages",
        "store_comparison_single_date",
    }:
        return _calculate_comparison(records, query_result, question)

    if query_type == "inventory_below_threshold":
        return _calculate_inventory(records, query_result)

    if query_type == "store_feedback_rows":
        return _calculate_feedback(records, query_result)

    raise ValueError(f"Unsupported query result type: {query_type!r}")
