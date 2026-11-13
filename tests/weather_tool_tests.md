# Weather tool tests

Observed outputs from scripts/run_weather_tests.py using WEATHER_MODE=stub.

## Case 1 — Mumbai reference output — PASS
Input: get_weather('Mumbai', '2026-05-15')

Observed output:

```python
{'ok': True,
 'city': 'Mumbai',
 'date': '2026-05-15',
 'mode': 'stub',
 'temperature_c': 26.0,
 'humidity_pct': 43.0,
 'wind_kmh': 10.0,
 'rain_mm': 0.0}
```

## Case 2 — Pune reference output — PASS
Input: get_weather('Pune', '2026-05-16')

Observed output:

```python
{'ok': True,
 'city': 'Pune',
 'date': '2026-05-16',
 'mode': 'stub',
 'temperature_c': 25.0,
 'humidity_pct': 88.0,
 'wind_kmh': 11.0,
 'rain_mm': 6.5}
```

## Case 3 — Hyderabad reference output — PASS
Input: get_weather('Hyderabad', '2026-04-01')

Observed output:

```python
{'ok': True,
 'city': 'Hyderabad',
 'date': '2026-04-01',
 'mode': 'stub',
 'temperature_c': 30.0,
 'humidity_pct': 58.0,
 'wind_kmh': 6.0,
 'rain_mm': 0.0}
```

## Case 4 — Unsupported city — PASS
Input: get_weather('Kolkata', '2026-05-15')

Observed output:

```python
{'ok': False, 'error': 'unsupported city: Kolkata'}
```

## Case 5 — Invalid calendar date — PASS
Input: get_weather('Pune', '2026-02-30')

Observed output:

```python
{'ok': False, 'error': 'invalid date: 2026-02-30'}
```

## Case 6 — Additional supported city/date — PASS
Input: get_weather('Ahmedabad', '2026-06-29')

Observed output:

```python
{'ok': True,
 'city': 'Ahmedabad',
 'date': '2026-06-29',
 'mode': 'stub',
 'temperature_c': 29.0,
 'humidity_pct': 47.0,
 'wind_kmh': 5.0,
 'rain_mm': 6.5}
```
