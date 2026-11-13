"""Reproducible Part D golden-set evaluation runner (offline defaults)."""

from __future__ import annotations

import csv
import json
import os
import re
import sys
from decimal import Decimal, InvalidOperation
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


def _expected_fragment_matches(answer_text: str, fragment: str) -> bool:
    """Match a required substring; decimal numbers allow a +/- INR 0.01 tolerance."""
    if fragment in answer_text:
        return True

    decimal_tokens = re.findall(r"(?<![A-Za-z])\d+\.\d+(?![A-Za-z])", fragment)
    if not decimal_tokens:
        return False

    alternatives = {}
    for token in decimal_tokens:
        value = Decimal(token)
        alternatives[token] = "(?:" + "|".join(
            re.escape(format(value + delta, ".2f"))
            for delta in (Decimal("-0.01"), Decimal("0.00"), Decimal("0.01"))
        ) + ")"

    pattern = re.escape(fragment)
    for token, replacement in alternatives.items():
        pattern = pattern.replace(re.escape(token), replacement)
    return re.search(pattern, answer_text) is not None


def _contains_all(answer_text: str, expected_contains: str) -> bool:
    fragments = [item for item in expected_contains.split("|") if item]
    return all(_expected_fragment_matches(answer_text, item) for item in fragments)


def _load_cases():
    with GOLDEN_PATH.open("r", newline="", encoding="utf-8-sig") as file:
        cases = list(csv.DictReader(file))
    if not cases:
        raise ValueError("The golden set is empty.")
    required = {
        "case_id", "category", "session_id", "question",
        "simulate_failures", "expected_status", "expected_intent",
        "expected_contains",
    }
    if set(cases[0]) != required:
        raise ValueError("golden_set.csv does not have the exact required columns.")
    if len(cases) < 34:
        raise ValueError("The official golden set minimum is 34 cases.")
    if len({row["case_id"] for row in cases}) != len(cases):
        raise ValueError("case_id values must be unique.")
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
        contains_match = _contains_all(answer_text, case["expected_contains"])
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
        audit_records = [json.loads(line) for line in file if line.strip()]

    if len(audit_records) != len(cases):
        raise RuntimeError(
            "Evaluation audit count mismatch: "
            f"{len(audit_records)} records for {len(cases)} cases."
        )

    expected_log_keys = {
        "run_id", "user_id", "session_id", "timestamp", "question",
        "intent", "confidence", "route", "executed", "attempts",
        "tools_called", "status", "answer_text", "evidence",
        "grounded_values", "latency_ms", "tokens_est", "tool_calls",
        "ungrounded_numbers", "budget_exceeded",
    }
    missing_keys = sorted(
        key for record in audit_records for key in expected_log_keys
        if key not in record
    )
    if missing_keys:
        raise RuntimeError("Audit records are missing required fields: " + ", ".join(missing_keys))

    if sum(int(row["ungrounded_numbers"]) for row in rows) != 0:
        print("WARNING: one or more replies contain ungrounded numbers.")
    if sum(bool(row["budget_exceeded"]) for row in rows):
        print("WARNING: one or more replies exceed the token budget.")

    passed = sum(bool(row["passed"]) for row in rows)
    print("Part D evaluation complete")
    print("Cases:", len(rows))
    print("Passed:", passed)
    print("Failed:", len(rows) - passed)
    print("Pass rate: {:.2f}%".format(100.0 * passed / len(rows)))
    print("Audit records:", len(audit_records))
    print("Ungrounded numbers:", sum(int(row["ungrounded_numbers"]) for row in rows))
    print("Budget breaches:", sum(bool(row["budget_exceeded"]) for row in rows))
    print("Total tool calls:", sum(int(row["tool_calls"]) for row in rows))
    print("Results:", RESULTS_PATH.relative_to(ROOT))
    print("Audit:", LOG_PATH.relative_to(ROOT))
    print("\nCase failures:")
    for row in rows:
        if not row["passed"]:
            print(
                row["case_id"],
                "expected={}/{}".format(row["expected_status"], row["category"]),
                "actual={}".format(row["actual_status"]),
                "intent_match={}".format(row["intent_match"]),
                "contains_match={}".format(row["contains_match"]),
            )


if __name__ == "__main__":
    main()
