"""Run the six required weather-tool checks and record observed outputs."""

from __future__ import annotations

import os
import pprint
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.weather import get_weather


CASES = [
    (
        "Mumbai reference output",
        "Mumbai",
        "2026-05-15",
        {
            "ok": True, "city": "Mumbai", "date": "2026-05-15",
            "mode": "stub", "temperature_c": 26.0, "humidity_pct": 43.0,
            "wind_kmh": 10.0, "rain_mm": 0.0,
        },
    ),
    (
        "Pune reference output",
        "Pune",
        "2026-05-16",
        {
            "ok": True, "city": "Pune", "date": "2026-05-16",
            "mode": "stub", "temperature_c": 25.0, "humidity_pct": 88.0,
            "wind_kmh": 11.0, "rain_mm": 6.5,
        },
    ),
    (
        "Hyderabad reference output",
        "Hyderabad",
        "2026-04-01",
        {
            "ok": True, "city": "Hyderabad", "date": "2026-04-01",
            "mode": "stub", "temperature_c": 30.0, "humidity_pct": 58.0,
            "wind_kmh": 6.0, "rain_mm": 0.0,
        },
    ),
    (
        "Unsupported city",
        "Kolkata",
        "2026-05-15",
        {"ok": False, "error": "unsupported city: Kolkata"},
    ),
    (
        "Invalid calendar date",
        "Pune",
        "2026-02-30",
        {"ok": False, "error": "invalid date: 2026-02-30"},
    ),
    (
        "Additional supported city/date",
        "Ahmedabad",
        "2026-06-29",
        {
            "ok": True, "city": "Ahmedabad", "date": "2026-06-29",
            "mode": "stub", "temperature_c": 29.0, "humidity_pct": 47.0,
            "wind_kmh": 5.0, "rain_mm": 6.5,
        },
    ),
]


def main():
    os.environ["WEATHER_MODE"] = "stub"
    sections = [
        "# Weather tool tests",
        "",
        "Observed outputs from scripts/run_weather_tests.py using WEATHER_MODE=stub.",
        "",
    ]
    failures = []

    for index, (label, city, requested_date, expected) in enumerate(CASES, start=1):
        actual = get_weather(city, requested_date)
        passed = actual == expected
        if not passed:
            failures.append((label, expected, actual))

        sections.extend(
            [
                f"## Case {index} — {label} — {'PASS' if passed else 'FAIL'}",
                f"Input: get_weather({city!r}, {requested_date!r})",
                "",
                "Observed output:",
                "",
                chr(96) * 3 + "python",
                pprint.pformat(actual, sort_dicts=False),
                chr(96) * 3,
                "",
            ]
        )

    output_path = ROOT / "tests" / "weather_tool_tests.md"
    output_path.write_text("\n".join(sections), encoding="utf-8")

    print(f"Weather tool checks passed: {len(CASES) - len(failures)} / {len(CASES)}")
    print(f"Observed outputs written to: {output_path.relative_to(ROOT)}")

    if failures:
        for label, expected, actual in failures:
            print(f"FAILED {label}: expected={expected!r}; actual={actual!r}")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
