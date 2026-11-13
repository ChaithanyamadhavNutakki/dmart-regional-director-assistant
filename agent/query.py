# ==========================================
# DMart Regional Director Assistant
# Component 4: Query Engine
# File: agent/query.py
# ==========================================

import csv
import sqlite3
from pathlib import Path


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
    """Convert CSV values to numeric values where the schema requires it."""

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


def _read_csv(table, data_dir):
    """Read one fixed repository dataset into Python dictionaries."""

    if table not in DATA_FILES:
        raise ValueError("The requested dataset is not approved.")

    file_path = Path(data_dir) / DATA_FILES[table]
    if not file_path.is_file():
        raise FileNotFoundError(f"Required data file was not found: {file_path}")

    with file_path.open("r", newline="", encoding="utf-8-sig") as file:
        reader = csv.DictReader(file)
        if not reader.fieldnames:
            raise ValueError(f"The data file has no header: {file_path}")
        return [
            {
                field: _parse_value(field, value)
                for field, value in row.items()
            }
            for row in reader
        ]


def _load_table(connection, table, data_dir):
    """Load one fixed CSV into SQLite for parameterised SQL operations."""

    file_path = Path(data_dir) / DATA_FILES[table]
    if not file_path.is_file():
        raise FileNotFoundError(f"Required data file was not found: {file_path}")

    with file_path.open("r", newline="", encoding="utf-8-sig") as file:
        reader = csv.DictReader(file)
        headers = reader.fieldnames
        if not headers:
            raise ValueError(f"The data file has no header: {file_path}")

        # Identifiers come only from the fixed CSV header, never user input.
        column_sql = ", ".join(
            '"' + header.replace('"', '""') + '"' for header in headers
        )
        connection.execute(f'CREATE TABLE "{table}" ({column_sql})')

        placeholders = ", ".join("?" for _ in headers)
        insert_sql = (
            f'INSERT INTO "{table}" ({column_sql}) VALUES ({placeholders})'
        )
        rows = [
            tuple(_parse_value(header, row.get(header)) for header in headers)
            for row in reader
        ]
        connection.executemany(insert_sql, rows)


def _open_database(data_dir):
    """Build an isolated in-memory SQLite database from approved CSV files."""

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
    return [dict(row) for row in cursor.fetchall()]


def _query_result(table, query_type, records, fields, sql=None):
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
    """Fail closed unless the Validator approved this exact request."""

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
    if route not in {"python", "sql", "python+weather"}:
        raise ValueError("This query engine does not accept the selected route.")

    return intent, entities, table, fields, route


def _python_lookup(data_dir, entities, table, fields):
    """Filter the daily CSV in Python for a single store and date."""

    store = entities.get("store")
    record_date = entities.get("date")
    if not store or not record_date:
        raise ValueError("A store and one date are required for this lookup.")

    matches = [
        row for row in _read_csv(table, data_dir)
        if row.get("store") == store and row.get("date") == record_date
    ]
    records = [
        {key: row.get(key) for key in ["store", "date"] + fields}
        for row in matches
    ]
    return _query_result(table, "single_store_date_lookup", records, fields)


def _python_target_check(data_dir, entities):
    """Fetch revenue, target, and stored performance band in Python."""

    store = entities.get("store")
    record_date = entities.get("date")
    if not store or not record_date:
        raise ValueError("A store and one date are required for a target check.")

    fields = ["revenue_inr", "daily_target_inr", "performance_band"]
    matches = [
        row for row in _read_csv("store_daily", data_dir)
        if row.get("store") == store and row.get("date") == record_date
    ]
    records = [
        {key: row.get(key) for key in ["store", "date"] + fields}
        for row in matches
    ]
    return _query_result(
        "store_daily", "target_vs_actual", records, fields
    )


def _sql_range_lookup(connection, entities, table, fields):
    """Calculate one store's average metric over an inclusive date range."""

    store = entities.get("store")
    start_date = entities.get("start_date")
    end_date = entities.get("end_date")
    if not store or not start_date or not end_date:
        raise ValueError("A store and inclusive date range are required.")

    metric = fields[0]  # Already checked against the approved-field allowlist.
    sql = (
        f'SELECT store, COUNT("{metric}") AS "_value_count", '
        f'SUM(CAST(ROUND("{metric}" * 100) AS INTEGER)) AS "_sum_cents" '
        f'FROM "{table}" WHERE store = ? AND date BETWEEN ? AND ? '
        "GROUP BY store"
    )
    cursor = connection.execute(sql, (store, start_date, end_date))
    return _query_result(
        table, "date_range_average", _records(cursor), fields, sql
    )


def _sql_comparison(connection, entities, table, fields):
    """Calculate per-store metric values for a date or inclusive date range."""

    single_date = entities.get("date")
    start_date = entities.get("start_date")
    end_date = entities.get("end_date")
    metric = fields[0]

    if start_date and end_date:
        sql = (
            f'SELECT store, COUNT("{metric}") AS "_value_count", '
            f'SUM(CAST(ROUND("{metric}" * 100) AS INTEGER)) AS "_sum_cents" '
            f'FROM "{table}" WHERE date BETWEEN ? AND ? GROUP BY store'
        )
        parameters = (start_date, end_date)
        query_type = "store_comparison_averages"
    elif single_date:
        sql = (
            f'SELECT store, "{metric}" AS "{metric}" '
            f'FROM "{table}" WHERE date = ? ORDER BY store ASC'
        )
        parameters = (single_date,)
        query_type = "store_comparison_single_date"
    else:
        raise ValueError("A date or inclusive date range is required for comparison.")

    cursor = connection.execute(sql, parameters)
    return _query_result(table, query_type, _records(cursor), fields, sql)


def _sql_inventory(connection, entities, table, fields):
    """Fetch all rows for a product; threshold filtering is calculated downstream."""

    product = entities.get("product")
    store = entities.get("store")
    if not product:
        raise ValueError("A recognised product is required for inventory.")

    selected = ["store", "product"] + fields
    select_sql = ", ".join(f'"{field}"' for field in selected)
    # The interpreter resolves canonical product names (for example,
    # "Amul Milk"), while inventory.csv stores descriptive labels with pack
    # sizes (for example, "Amul Milk 1L"). Match the canonical name exactly
    # or as the beginning of a product label followed by a space.
    sql = (
        f'SELECT {select_sql} FROM "{table}" '
        "WHERE product = ? OR product LIKE ?"
    )
    parameters = [product, product + " %"]
    if store:
        sql += " AND store = ?"
        parameters.append(store)
    sql += " ORDER BY store ASC"

    cursor = connection.execute(sql, tuple(parameters))
    return _query_result(
        table, "inventory_below_threshold", _records(cursor), fields, sql
    )


def _sql_feedback(connection, entities, table, fields):
    """Fetch all feedback rows for a store; summarisation is downstream."""

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

    Python routes use direct CSV filtering for single-store/date lookups and
    target checks. SQL routes use parameterised SQLite queries for range
    lookups, comparisons, inventory, and feedback. Weather execution belongs
    to the weather component. This function performs one attempt only; retry
    policy and completion status belong to orchestration.
    """

    intent, entities, table, fields, route = _validate_inputs(
        interpretation, validation
    )
    if intent == "weather":
        raise ValueError("Weather requests must be handled by the weather tool.")

    resolved_data_dir = Path(data_dir) if data_dir else DEFAULT_DATA_DIR

    if route in {"python", "python+weather"}:
        if intent == "lookup":
            return _python_lookup(resolved_data_dir, entities, table, fields)
        if intent == "target_vs_actual":
            return _python_target_check(resolved_data_dir, entities)
        raise ValueError(f"No Python query function is defined for intent: {intent}")

    connection = _open_database(resolved_data_dir)
    try:
        if intent == "lookup":
            return _sql_range_lookup(connection, entities, table, fields)
        if intent == "comparison":
            return _sql_comparison(connection, entities, table, fields)
        if intent == "inventory":
            return _sql_inventory(connection, entities, table, fields)
        if intent == "feedback":
            return _sql_feedback(connection, entities, table, fields)
        raise ValueError(f"No SQL query function is defined for intent: {intent}")
    finally:
        connection.close()
