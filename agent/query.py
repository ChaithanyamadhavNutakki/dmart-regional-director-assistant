# ==========================================
# DMart Regional Director Assistant
# Component 4: Query Engine
# File: agent/query.py
# ==========================================

import csv
import sqlite3
from pathlib import Path


# Data files are resolved from the repository root, not the current notebook
# working directory.
REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATA_DIR = REPOSITORY_ROOT / "data"

DATA_FILES = {
    "store_daily": "store_daily_clean.csv",
    "inventory": "inventory.csv",
    "feedback": "feedback.csv",
}

APPROVED_FIELDS = {
    "store_daily": {
        "revenue_inr", "daily_target_inr", "footfall",
        "stockout_hours", "discount_pct", "achievement_pct",
        "performance_band",
    },
    "inventory": {"stock_units", "reorder_threshold"},
    "feedback": {"rating", "theme"},
}

KEY_FIELDS = {"store", "store_id", "date", "product", "product_id"}

NUMERIC_FIELDS = {
    "footfall", "revenue_inr", "daily_target_inr", "stockout_hours",
    "discount_pct", "achievement_pct", "stock_units",
    "reorder_threshold", "rating",
}


def _parse_value(field, value):
    """Convert CSV values to SQLite-compatible Python values."""

    if value is None or value == "":
        return None

    if field in NUMERIC_FIELDS:
        number = float(value)
        if number.is_integer() and field not in {
            "revenue_inr", "daily_target_inr", "stockout_hours",
            "discount_pct", "achievement_pct", "rating",
        }:
            return int(number)
        return number

    return value


def _load_table(connection, table, data_dir):
    """Load one approved CSV into an in-memory SQLite table."""

    filename = DATA_FILES[table]
    file_path = Path(data_dir) / filename

    if not file_path.is_file():
        raise FileNotFoundError(
            f"Required data file was not found: {file_path}"
        )

    with file_path.open("r", newline="", encoding="utf-8-sig") as file:
        reader = csv.DictReader(file)
        headers = reader.fieldnames

        if not headers:
            raise ValueError(f"The data file has no header: {file_path}")

        # Table and column names come only from fixed repository files.
        column_sql = ", ".join(
            '"' + header.replace('"', '""') + '"'
            for header in headers
        )
        connection.execute(
            f'CREATE TABLE "{table}" ({column_sql})'
        )

        placeholders = ", ".join("?" for _ in headers)
        insert_sql = (
            f'INSERT INTO "{table}" ({column_sql}) '
            f"VALUES ({placeholders})"
        )

        rows = []
        for row in reader:
            rows.append(tuple(
                _parse_value(header, row.get(header))
                for header in headers
            ))

        connection.executemany(insert_sql, rows)

    return len(headers), len(rows)


def _open_database(data_dir):
    """Build an isolated SQLite database from the committed CSV datasets."""

    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row

    try:
        for table in DATA_FILES:
            _load_table(connection, table, data_dir)
    except Exception:
        connection.close()
        raise

    return connection


def _records(cursor):
    """Convert fetched SQLite rows into ordinary dictionaries."""

    return [dict(row) for row in cursor.fetchall()]


def _query_result(table, query_type, records, fields, sql=None):
    """Return a consistent, auditable query payload."""

    return {
        "success": True,
        "table": table,
        "query_type": query_type,
        "fields": list(fields),
        "records": records,
        "row_count": len(records),
        "sql": sql,
    }


def _validate_inputs(interpretation, validation):
    """Fail closed unless the upstream Validator approved this request."""

    if not isinstance(interpretation, dict):
        raise ValueError("A valid interpretation dictionary is required.")

    if not isinstance(validation, dict) or not validation.get("valid"):
        raise ValueError("Query execution requires successful validation.")

    intent = interpretation.get("intent")
    entities = interpretation.get("entities") or {}
    table = validation.get("table")
    fields = validation.get("fields") or []
    route = validation.get("route")

    if table not in APPROVED_FIELDS:
        raise ValueError("The selected dataset is not approved.")

    if not fields or any(
        field not in APPROVED_FIELDS[table] or field in KEY_FIELDS
        for field in fields
    ):
        raise ValueError("The selected measured fields are not approved.")

    if validation.get("intent") != intent:
        raise ValueError("The validation result does not match the intent.")

    if route not in {"python", "sql"}:
        raise ValueError("This query engine accepts only Python or SQL routes.")

    return intent, entities, table, fields, route


def _python_lookup(connection, entities, table, fields):
    """Fetch one store/date row using a parameterised SQLite lookup."""

    store = entities.get("store")
    record_date = entities.get("date")

    if not store or not record_date:
        raise ValueError("A store and one date are required for this lookup.")

    selected = ["store", "date"] + fields
    select_sql = ", ".join(f'"{field}"' for field in selected)

    sql = (
        f'SELECT {select_sql} FROM "{table}" '
        "WHERE store = ? AND date = ?"
    )
    cursor = connection.execute(sql, (store, record_date))
    return _query_result(
        table, "single_store_date_lookup", _records(cursor), fields, sql
    )


def _python_target_check(connection, entities):
    """Fetch revenue, target, and stored band for one store/date."""

    store = entities.get("store")
    record_date = entities.get("date")

    if not store or not record_date:
        raise ValueError("A store and one date are required for a target check.")

    fields = ["revenue_inr", "daily_target_inr", "performance_band"]
    sql = (
        'SELECT store, date, "revenue_inr", "daily_target_inr", '
        '"performance_band" FROM store_daily '
        "WHERE store = ? AND date = ?"
    )
    cursor = connection.execute(sql, (store, record_date))
    return _query_result(
        "store_daily", "target_vs_actual", _records(cursor), fields, sql
    )


def _sql_range_lookup(connection, entities, table, fields):
    """Fetch the inclusive-period average for one store and one metric."""

    store = entities.get("store")
    start_date = entities.get("start_date")
    end_date = entities.get("end_date")

    if not store or not start_date or not end_date:
        raise ValueError("A store and inclusive date range are required.")

    metric = fields[0]
    # The metric identifier has already passed the allowlist above.
    sql = (
        f'SELECT store, AVG("{metric}") AS "{metric}" '
        f'FROM "{table}" WHERE store = ? AND date BETWEEN ? AND ? '
        "GROUP BY store"
    )
    cursor = connection.execute(sql, (store, start_date, end_date))
    return _query_result(
        table, "date_range_average", _records(cursor), fields, sql
    )


def _sql_comparison(connection, entities, table, fields):
    """Calculate per-store averages over an inclusive date range."""

    start_date = entities.get("start_date")
    end_date = entities.get("end_date")

    if not start_date or not end_date:
        raise ValueError("A date range is required for store comparison.")

    metric = fields[0]
    sql = (
        f'SELECT store, AVG("{metric}") AS "{metric}" '
        f'FROM "{table}" WHERE date BETWEEN ? AND ? '
        "GROUP BY store"
    )
    cursor = connection.execute(sql, (start_date, end_date))
    return _query_result(
        table, "store_comparison_averages", _records(cursor), fields, sql
    )


def _sql_inventory(connection, entities, table, fields):
    """Fetch product records strictly below their reorder threshold."""

    product = entities.get("product")
    store = entities.get("store")

    if not product:
        raise ValueError("A recognised product is required for inventory.")

    selected = ["store", "product"] + fields
    select_sql = ", ".join(f'"{field}"' for field in selected)

    sql = (
        f'SELECT {select_sql} FROM "{table}" '
        "WHERE product = ? AND stock_units < reorder_threshold"
    )
    parameters = [product]

    if store:
        sql += " AND store = ?"
        parameters.append(store)

    sql += " ORDER BY store ASC"
    cursor = connection.execute(sql, tuple(parameters))
    return _query_result(
        table, "inventory_below_threshold", _records(cursor), fields, sql
    )


def _sql_feedback(connection, entities, table, fields):
    """Fetch all feedback rows for a store; aggregation is a later step."""

    store = entities.get("store")

    if not store:
        raise ValueError("A recognised store is required for feedback.")

    selected = ["store", "date"] + fields
    select_sql = ", ".join(f'"{field}"' for field in selected)

    sql = (
        f'SELECT {select_sql} FROM "{table}" '
        "WHERE store = ? ORDER BY date ASC"
    )
    cursor = connection.execute(sql, (store,))
    return _query_result(
        table, "store_feedback_rows", _records(cursor), fields, sql
    )


def query(interpretation, validation, data_dir=None):
    """
    Execute one validated data request.

    Parameters
    ----------
    interpretation : dict
        Output from agent.understand.understand().
    validation : dict
        Successful output from agent.validate.validate(), including route,
        table, and approved measured fields.
    data_dir : str or Path, optional
        Dataset directory. Defaults to the repository's data/ directory.

    Returns
    -------
    dict
        Query payload containing records, row_count, query_type, fields,
        table, and the parameterised SQL statement used where applicable.

    The function performs one execution attempt. Retry policy and status
    assignment belong to the orchestration layer.
    """

    intent, entities, table, fields, route = _validate_inputs(
        interpretation, validation
    )

    if intent == "weather":
        raise ValueError(
            "Weather requests must be handled by the weather tool, not query.py."
        )

    resolved_data_dir = Path(data_dir) if data_dir else DEFAULT_DATA_DIR
    connection = _open_database(resolved_data_dir)

    try:
        if route == "python":
            if intent == "lookup":
                return _python_lookup(connection, entities, table, fields)

            if intent == "target_vs_actual":
                return _python_target_check(connection, entities)

            raise ValueError(
                f"No Python query function is defined for intent: {intent}"
            )

        if route == "sql":
            if intent == "lookup":
                return _sql_range_lookup(
                    connection, entities, table, fields
                )

            if intent == "comparison":
                return _sql_comparison(
                    connection, entities, table, fields
                )

            if intent == "inventory":
                return _sql_inventory(
                    connection, entities, table, fields
                )

            if intent == "feedback":
                return _sql_feedback(
                    connection, entities, table, fields
                )

            raise ValueError(
                f"No SQL query function is defined for intent: {intent}"
            )

        raise ValueError(f"Unsupported query route: {route}")

    finally:
        connection.close()
