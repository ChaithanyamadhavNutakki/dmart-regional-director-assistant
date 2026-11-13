# Weather tool checks

The default mode is `WEATHER_MODE=stub`. These cases use the deterministic formula specified in the capstone brief.

## Case 1 — Mumbai reference output

Input: `get_weather("Mumbai", "2026-05-15")`

Expected output:

```python
{
    "ok": True,
    "city": "Mumbai",
    "date": "2026-05-15",
    "mode": "stub",
    "temperature_c": 26.0,
    "humidity_pct": 43.0,
    "wind_kmh": 10.0,
    "rain_mm": 0.0,
}
```

## Case 2 — Pune reference output

Input: `get_weather("Pune", "2026-05-16")`

Expected output:

```python
{
    "ok": True,
    "city": "Pune",
    "date": "2026-05-16",
    "mode": "stub",
    "temperature_c": 25.0,
    "humidity_pct": 88.0,
    "wind_kmh": 11.0,
    "rain_mm": 6.5,
}
```

## Case 3 — Hyderabad reference output

Input: `get_weather("Hyderabad", "2026-04-01")`

Expected output:

```python
{
    "ok": True,
    "city": "Hyderabad",
    "date": "2026-04-01",
    "mode": "stub",
    "temperature_c": 30.0,
    "humidity_pct": 58.0,
    "wind_kmh": 6.0,
    "rain_mm": 0.0,
}
```

## Case 4 — Unsupported city

Input: `get_weather("Kolkata", "2026-05-15")`

Expected output:

```python
{"ok": False, "error": "unsupported city: Kolkata"}
```

## Case 5 — Invalid calendar date

Input: `get_weather("Pune", "2026-02-30")`

Expected output:

```python
{"ok": False, "error": "invalid date: 2026-02-30"}
```

## Case 6 — Additional supported city/date

Input: `get_weather("Ahmedabad", "2026-06-29")`

Expected output:

```python
{
    "ok": True,
    "city": "Ahmedabad",
    "date": "2026-06-29",
    "mode": "stub",
    "temperature_c": 29.0,
    "humidity_pct": 47.0,
    "wind_kmh": 5.0,
    "rain_mm": 6.5,
}
```

These are expected outputs derived from the stub formula. They are not presented as runtime test results; the consolidated integration run will verify them.
