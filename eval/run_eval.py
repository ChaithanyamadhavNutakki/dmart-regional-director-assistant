"""Reproducible Part D golden-set evaluation runner (offline defaults)."""

from __future__ import annotations

import csv
import json
import os
import re
import sys
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent.run_agent import clear_all_sessions, handle


GOLDEN_PATH = ROOT / "eval" / "golden_set.csv"
RESULTS_PATH = ROOT / "eval" / "eval_results.csv"
LOG_PATH = ROOT / "eval" / "eval_runs.jsonl"

RESULT_FIELDS = [
    "case_id", "category", "expected_status", "actual_status",
    "intent_match", "contains_match", "latency_ms", "tokens_est",
    "tool_calls", "ungrounded_numbers", "budget_exceeded", "passed",
]

FIXED_IDS = {
    "A{:02d}".format(number) for number in range(1, 21)
} | {"W01", "W02", "W03", "R01"}

REQUIRED_OWN_CATEGORIES = {
    "typo", "synonym", "ambiguity", "unsupported_metric",
    "out_of_scope", "injection", "out_of_range_date",
    "unresolved_store", "unresolved_date",
}

GATE_CATEGORIES = {
    "unsupported_metric", "out_of_scope", "out_of_range_date",
    "injection", "ambiguity", "unresolved_store", "unresolved_date",
}


def _linear_percentile(values, percentile):
    """Compute a percentile using linear interpolation."""
    ordered = sorted(float(value) for value in values)
    if not ordered:
        return 0.0
    position = (len(ordered) - 1) * percentile
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = position - lower
    return ordered[lower] + (ordered[upper] - ordered[lower]) * fraction


def _expected_fragment_matches(answer_text: str, fragment: str) -> bool:
    """Match a required substring; decimal figures allow +/- 0.01."""
    if fragment in answer_text:
        return True

    decimal_tokens = re.findall(
        r"(?<![A-Za-z])\d+\.\d+(?![A-Za-z])", fragment
    )
    if not decimal_tokens:
        return False

    pattern = re.escape(fragment)
    for token in decimal_tokens:
        value = Decimal(token)
        alternatives = "|".join(
            re.escape(format(value + delta, ".2f"))
            for delta in (
                Decimal("-0.01"), Decimal("0.00"), Decimal("0.01")
            )
        )
        pattern = pattern.replace(
            re.escape(token), "(?:" + alternatives + ")"
        )
    return re.search(pattern, answer_text) is not None


def _contains_all(answer_text: str, expected_contains: str) -> bool:
    fragments = [item for item in expected_contains.split("|") if item]
    return all(
        _expected_fragment_matches(answer_text, fragment)
        for fragment in fragments
    )


def _load_cases():
    with GOLDEN_PATH.open("r", newline="", encoding="utf-8-sig") as file:
        cases = list(csv.DictReader(file))

    if not cases:
        raise ValueError("The golden set is empty.")

    required_columns = {
        "case_id", "category", "session_id", "question",
        "simulate_failures", "expected_status", "expected_intent",
        "expected_contains",
    }
    if set(cases[0]) != required_columns:
        raise ValueError("golden_set.csv does not have the exact required columns.")
    if len(cases) < 34:
        raise ValueError("The official golden set minimum is 34 cases.")

    case_ids = [row["case_id"] for row in cases]
    if len(set(case_ids)) != len(case_ids):
        raise ValueError("case_id values must be unique.")

    missing_fixed = sorted(FIXED_IDS - set(case_ids))
    if missing_fixed:
        raise ValueError(
            "Golden set is missing fixed cases: " + ", ".join(missing_fixed)
        )

    own_cases = [row for row in cases if row["case_id"] not in FIXED_IDS]
    own_categories = {row["category"] for row in own_cases}
    missing_categories = sorted(REQUIRED_OWN_CATEGORIES - own_categories)
    if len(own_cases) < 10 or missing_categories:
        raise ValueError(
            "Golden set needs at least ten original cases and all nine required "
            "categories. Missing categories: " + ", ".join(missing_categories)
        )

    excluded_sessions = {
        "s{}".format(number) for number in range(1, 17)
    } | {"s29"}
    invalid_sessions = sorted({
        row["session_id"] for row in own_cases
        if row["session_id"] in excluded_sessions
    })
    if invalid_sessions:
        raise ValueError(
            "Original cases must use new session IDs; invalid: "
            + ", ".join(invalid_sessions)
        )

    return cases


def main():
    os.environ["LLM_MODE"] = "mock"
    os.environ["WEATHER_MODE"] = "stub"
    os.environ["AGENT_LOG_PATH"] = str(LOG_PATH)
    os.environ.pop("SIMULATE_DB_FAILURES", None)

    cases = _load_cases()
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    LOG_PATH.write_text("", encoding="utf-8")
    clear_all_sessions()

    rows = []
    for case in cases:
        os.environ["SIMULATE_DB_FAILURES"] = case["simulate_failures"] or "0"
        result = handle(case["question"], case["session_id"])
        answer_text = str(result.get("answer_text") or "")

        status_match = result.get("status") == case["expected_status"]
        intent_match = result.get("intent") == case["expected_intent"]
        contains_match = _contains_all(
            answer_text, case["expected_contains"]
        )
        ungrounded = int(result.get("ungrounded_numbers", 0) or 0)
        budget_exceeded = bool(result.get("budget_exceeded", False))
        passed = status_match and intent_match and contains_match

        rows.append({
            "case_id": case["case_id"],
            "category": case["category"],
            "expected_status": case["expected_status"],
            "actual_status": result.get("status", ""),
            "intent_match": intent_match,
            "contains_match": contains_match,
            "latency_ms": result.get("latency_ms", 0),
            "tokens_est": result.get("tokens_est", 0),
            "tool_calls": result.get("tool_calls", 0),
            "ungrounded_numbers": ungrounded,
            "budget_exceeded": budget_exceeded,
            "passed": passed,
        })

    os.environ.pop("SIMULATE_DB_FAILURES", None)

    with RESULTS_PATH.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=RESULT_FIELDS)
        writer.writeheader()
        writer.writerows(rows)

    with LOG_PATH.open("r", encoding="utf-8") as file:
        audit_records = [
            json.loads(line) for line in file if line.strip()
        ]

    if len(audit_records) != len(cases):
        raise RuntimeError(
            "Evaluation audit count mismatch: "
            "{} records for {} cases.".format(len(audit_records), len(cases))
        )

    expected_log_keys = {
        "run_id", "user_id", "session_id", "timestamp", "question",
        "intent", "confidence", "route", "executed", "attempts",
        "tools_called", "status", "answer_text", "evidence",
        "grounded_values", "latency_ms", "tokens_est", "tool_calls",
        "ungrounded_numbers", "budget_exceeded",
    }
    missing_keys = sorted(
        key
        for record in audit_records
        for key in expected_log_keys
        if key not in record
    )
    if missing_keys:
        raise RuntimeError(
            "Audit records are missing required fields: "
            + ", ".join(missing_keys)
        )

    paired = list(zip(cases, audit_records))
    record_by_case = {
        case["case_id"]: record for case, record in paired
    }

    passed = sum(bool(row["passed"]) for row in rows)
    total = len(rows)
    latencies = [float(row["latency_ms"] or 0) for row in rows]
    token_counts = [int(row["tokens_est"] or 0) for row in rows]
    ungrounded_total = sum(
        int(row["ungrounded_numbers"] or 0) for row in rows
    )
    budget_total = sum(bool(row["budget_exceeded"]) for row in rows)
    tool_calls_total = sum(
        int(row["tool_calls"] or 0) for row in rows
    )

    category_summary = {}
    for row in rows:
        item = category_summary.setdefault(
            row["category"], {"passed": 0, "total": 0}
        )
        item["total"] += 1
        item["passed"] += int(bool(row["passed"]))

    gate_rows = [
        row for row in rows if row["category"] in GATE_CATEGORIES
    ]
    safety_rows = [
        row for row in rows
        if row["category"] in {
            "injection", "unsupported_metric", "out_of_scope"
        }
    ]

    non_answer_statuses = {
        "Safe Failure", "Escalated", "Clarification Needed"
    }
    non_answer_inr = sum(
        1 for record in audit_records
        if record.get("status") in non_answer_statuses
        and re.search(
            r"\bINR\s+-?\d", str(record.get("answer_text", ""))
        )
    )

    gitignore_path = ROOT / ".gitignore"
    env_ignored = (
        gitignore_path.is_file()
        and ".env" in {
            line.strip()
            for line in gitignore_path.read_text(encoding="utf-8").splitlines()
        }
    )

    weather_checks = {
        "A01_no_weather_tool": (
            "weather_tool" not in record_by_case["A01"].get("tools_called", [])
        ),
        "W01_weather_tool_called": (
            "weather_tool" in record_by_case["W01"].get("tools_called", [])
        ),
        "W02_weather_tool_called": (
            "weather_tool" in record_by_case["W02"].get("tools_called", [])
        ),
    }

    print("Part D evaluation complete")
    print("Cases: {} | Passed: {} | Failed: {}".format(
        total, passed, total - passed
    ))
    print("Pass rate: {:.2f}%".format(100.0 * passed / total))
    print("Audit records:", len(audit_records))
    print("Cost — mean tokens: {:.2f} | max tokens: {}".format(
        sum(token_counts) / total, max(token_counts)
    ))
    print("Cost — total tool calls: {} | budget breaches: {}".format(
        tool_calls_total, budget_total
    ))
    print("Latency — mean ms: {:.3f} | p90 ms (linear): {:.3f} | max ms: {:.3f}".format(
        sum(latencies) / total,
        _linear_percentile(latencies, 0.90),
        max(latencies),
    ))
    print("Quality — ungrounded numbers:", ungrounded_total)
    print("Safety — injection/unsupported_metric/out_of_scope: {}/{} passed".format(
        sum(int(bool(row["passed"])) for row in safety_rows),
        len(safety_rows),
    ))
    print("Safety — non-answer replies with INR figures:", non_answer_inr)
    print("Safety — .gitignore lists .env:", "YES" if env_ignored else "NO")
    print("Release-gate categories: {}/{} passed".format(
        sum(int(bool(row["passed"])) for row in gate_rows),
        len(gate_rows),
    ))
    print("Weather tool invocation checks:")
    for name, passed_check in weather_checks.items():
        print("  {}: {}".format(name, "PASS" if passed_check else "FAIL"))

    print("Pass counts by category:")
    for category in sorted(category_summary):
        item = category_summary[category]
        print("  {}: {}/{}".format(
            category, item["passed"], item["total"]
        ))

    r01_record = record_by_case.get("R01")
    if r01_record:
        print("R01 full-period reconciliation answer:")
        print(r01_record.get("answer_text", ""))

    print("Results:", RESULTS_PATH.relative_to(ROOT))
    print("Audit:", LOG_PATH.relative_to(ROOT))
    print()
    print("Case failures:")
    for row in rows:
        if not row["passed"]:
            record = record_by_case.get(row["case_id"], {})
            print(
                row["case_id"],
                "category={}".format(row["category"]),
                "expected={}".format(row["expected_status"]),
                "actual={}".format(row["actual_status"]),
                "intent_match={}".format(row["intent_match"]),
                "contains_match={}".format(row["contains_match"]),
                "answer={!r}".format(record.get("answer_text", "")),
            )

    if ungrounded_total:
        print("WARNING: one or more replies contain ungrounded numbers.")
    if budget_total:
        print("WARNING: one or more replies exceed the token budget.")
    if not all(weather_checks.values()):
        print("WARNING: one or more weather invocation checks failed.")


if __name__ == "__main__":
    main()
