"""Deterministic weather stub with an optional Open-Meteo archive mode.

The offline stub is the default and is the mode used by acceptance tests.
"""

from __future__ import annotations

import os
import re
from datetime import date as date_type


CITY_COORDINATES = {
    "Mumbai": (19.0760, 72.8777),
    "Pune": (18.5204, 73.8567),
    "Hyderabad": (17.3850, 78.4867),
    "Bengaluru": (12.9716, 77.5946),
    "Ahmedabad": (23.0225, 72.5714),
}

DAILY_FIELDS = (
    "temperature_2m_mean,relative_humidity_2m_mean,"
    "wind_speed_10m_max,precipitation_sum"
)


def _failure(message):
    return {"ok": False, "error": str(message)}


def _validate_city(city):
    if not isinstance(city, str):
        return None
    for supported in CITY_COORDINATES:
        if city.casefold() == supported.casefold():
            return supported
    return None


def _validate_date(date_text):
    if not isinstance(date_text, str) or not re.fullmatch(
        r"\d{4}-\d{2}-\d{2}", date_text
    ):
        return None
    try:
        return date_type.fromisoformat(date_text)
    except ValueError:
        return None


def _stub_weather(city, requested_date):
    day_of_year = requested_date.timetuple().tm_yday
    name_length = len(city)
    return {
        "ok": True,
        "city": city,
        "date": requested_date.isoformat(),
        "mode": "stub",
        "temperature_c": float(20 + (name_length + day_of_year) % 15),
        "humidity_pct": float(40 + (3 * name_length + day_of_year) % 50),
        "wind_kmh": float(5 + day_of_year % 10),
        "rain_mm": 6.5 if day_of_year % 4 == 0 else 0.0,
    }


def _live_weather(city, requested_date):
    latitude, longitude = CITY_COORDINATES[city]
    try:
        import requests

        response = requests.get(
            "https://archive-api.open-meteo.com/v1/archive",
            params={
                "latitude": latitude,
                "longitude": longitude,
                "start_date": requested_date.isoformat(),
                "end_date": requested_date.isoformat(),
                "timezone": "Asia/Kolkata",
                "daily": DAILY_FIELDS,
            },
            timeout=10,
        )
        if response.status_code != 200:
            return _failure(
                f"Open-Meteo returned HTTP status {response.status_code}"
            )

        payload = response.json()
        daily = payload.get("daily") or {}
        required = (
            "temperature_2m_mean",
            "relative_humidity_2m_mean",
            "wind_speed_10m_max",
            "precipitation_sum",
        )
        if any(not daily.get(field) for field in required):
            return _failure("Open-Meteo response did not contain all daily fields")

        return {
            "ok": True,
            "city": city,
            "date": requested_date.isoformat(),
            "mode": "live",
            "temperature_c": daily["temperature_2m_mean"][0],
            "humidity_pct": daily["relative_humidity_2m_mean"][0],
            "wind_kmh": daily["wind_speed_10m_max"][0],
            "rain_mm": daily["precipitation_sum"][0],
        }
    except Exception as exc:
        return _failure(f"Open-Meteo request failed: {exc}")


def get_weather(city, date):
    """Return weather for one supported city and one valid ISO date.

    Failures are returned as dictionaries and never raised to the caller.
    WEATHER_MODE=stub is the default; WEATHER_MODE=live enables Open-Meteo.
    """
    resolved_city = _validate_city(city)
    if resolved_city is None:
        return _failure(f"unsupported city: {city}")

    parsed_date = _validate_date(date)
    if parsed_date is None:
        return _failure(f"invalid date: {date}")

    mode = os.getenv("WEATHER_MODE", "stub").strip().lower()
    if mode == "stub":
        return _stub_weather(resolved_city, parsed_date)
    if mode == "live":
        return _live_weather(resolved_city, parsed_date)
    return _failure(f"unsupported WEATHER_MODE: {mode}")


weather = get_weather
