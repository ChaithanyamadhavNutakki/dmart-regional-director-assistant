# DMart Regional Director Assistant

## Purpose

This repository contains one connected capstone project: a data-quality and operational-premise analysis for five synthetic DMart stores, followed by a rule-based conversational analytics assistant. The assistant answers approved store-performance, target, comparison, inventory and feedback questions. Each reply carries evidence and numeric-grounding information.

**Data notice:** All records are synthetic practice data produced by `scripts/generate_data.py`. They are not DMart's real operating data.

## Project status

- **Part A — Data foundation:** datasets, cleaning log, data-quality report, findings and executive summary are present.
- **Part B — Specification:** requirement, data-context and agent-specification documents are present.
- **Part C — Agent:** the prescribed entry-point modules, supporting implementation modules, weather stub, weather test report, acceptance transcript and audit log are present. The latest recorded integration run reported 20/20 acceptance cases, 6/6 weather checks and audit integrity PASS. Part C is closed unless a new integration defect is found.
- **Part D — Evaluation and release decision:** the 38-case golden set (24 fixed and 14 additional cases), derivation notes, evaluation runner, measured result CSV, per-case JSONL audit log, four-metric summary and release-gate decision are committed. The recorded evaluation passed 38/38 cases and met all four release conditions (GO).

## Free offline setup

Use Python 3.9 or later. Run from the repository root:

```bash
python -m venv .venv
# Activate the environment:
# Windows: .venv\\Scripts\\activate
# macOS/Linux: source .venv/bin/activate

python -m pip install --upgrade pip
pip install -r requirements.txt
```

The default path is local and does not require an API key or hosted service:

- `LLM_MODE=mock`: deterministic, rule-based interpretation and fixed answer templates.
- `WEATHER_MODE=stub`: deterministic local weather responses; no network access.
- Local CSV files and an in-memory SQLite database for data access.
- `.env` files are ignored by Git and must not be committed.

The optional `WEATHER_MODE=live` branch uses Open-Meteo and requires `requests`. It is not needed for the offline acceptance or evaluation path.

## Reproducible run order

Run all commands from the repository root.

1. **Generate raw data:** `python scripts/generate_data.py`. The raw files are already committed. This script overwrites them, so do not run it during normal use or after the raw datasets have been frozen for submission.
2. **Clean the daily data:** `python scripts/clean_data.py`. Reads `data/store_daily.csv`, writes `data/store_daily_clean.csv` and `analysis/cleaning_log.csv`.
3. **Recreate Part A findings:** `python scripts/analyze.py`. Reads the raw and cleaned daily files and writes `analysis/findings.md`.
4. **Run the weather and Part C acceptance checks:** `python scripts/run_integration_checks.py`. This runs the six weather stub checks and all twenty fixed agent acceptance cases. It rewrites `tests/weather_tool_tests.md`, `outputs/acceptance_transcript.md` and `logs/runs.jsonl`.
5. **Run Part D evaluation:** `python eval/run_eval.py`. It runs every golden case with `LLM_MODE=mock`, `WEATHER_MODE=stub` and writes `eval/eval_results.csv` plus one JSONL record per case in `eval/eval_runs.jsonl`. It empties only the evaluation log; the Part C `logs/runs.jsonl` remains separate. The committed `eval/eval_summary.md` and `docs/release_gate.md` document the measured run recorded for this submission; regenerate and review them if a new evaluation run changes the results.

For a fresh clone, the committed raw data can be used directly. Begin at step 2 only when intentionally reproducing the cleaning and analysis artefacts. Never edit the raw CSV files manually.

## Repository layout

```text
README.md
.gitignore
requirements.txt
data/
  store_daily.csv
  inventory.csv
  feedback.csv
  store_daily_clean.csv
scripts/
  generate_data.py
  clean_data.py
  analyze.py
  run_acceptance.py
  run_weather_tests.py
  run_integration_checks.py
analysis/
  data_quality_report.md
  cleaning_log.csv
  findings.md
  executive_summary.md
docs/
  requirement.md
  data_context.md
  agent_spec.md
  release_gate.md
agent/
  understand.py
  fetch.py
  answer.py
  run_agent.py
  main.py
  route.py
  validate.py
  query.py
  calculate.py
  synthesize.py
  ground.py
  record.py
tools/
  weather.py
tests/
  weather_tool_tests.md
outputs/
  acceptance_transcript.md
logs/
  runs.jsonl
eval/
  golden_set.csv
  golden_set_derivation.md
  run_eval.py
  eval_results.csv
  eval_runs.jsonl
  eval_summary.md
```

The prescribed `agent/fetch.py` and `agent/answer.py` modules are used by the orchestrator. Other `agent/` modules are implementation helpers that keep interpretation, routing, validation, querying, calculation, synthesis, grounding and logging separate. The additional `scripts/run_weather_tests.py` and `scripts/run_integration_checks.py` are convenience runners: the first records weather-tool outputs, and the second runs weather checks followed by the fixed agent acceptance suite. The package `__init__.py` files support reliable imports.

## Data and calculation rules

The daily store dataset covers 1 April 2026 through 29 June 2026. The assistant reads the cleaned daily dataset, the current inventory snapshot and feedback independently. Inventory has no historical date column.

Only the eleven approved measured fields listed in `docs/requirement.md` may be reported. The assistant is read-only: it does not restock inventory, modify records or send messages. Requests for unsupported metrics or analyst judgement are safely refused or escalated; correlation is not presented as causation.

**Rounding method:** SQL returns non-null counts and integer-cent sums for averages; Python divides using `Decimal` and `ROUND_HALF_UP` to round the result to two decimal places.

## Known limitations

- The datasets are synthetic, cover five stores and a fixed 90-day period, and do not represent actual DMart operations.
- The rule-based interpreter uses a bounded vocabulary; unfamiliar wording may require clarification or escalation.
- Session context is held in memory and does not persist across process restarts.
- Inventory is a current snapshot, not a dated history, so inventory trends cannot be calculated.
- The assistant is read-only and does not perform transactions or communications.
- Stub weather values are deterministic test values, not observed weather measurements.
- Part C acceptance passing does not establish Part D evaluation quality or authorise a release decision.

## Prioritised Iteration-2 backlog

1. **Trend analysis across time**
   - Input: approved metric, store and explicit date range.
   - Output: a descriptive time series and period summary.
   - Success: all periods are within the data range, results reconcile to source rows, and each number is grounded.
   - Failure: clarify missing or ambiguous entities; safely reject unsupported dates; never infer causation.

2. **Deeper conversational follow-ups**
   - Input: a follow-up referring to a previous result, such as another metric or a narrower date range.
   - Output: an answer that inherits only unambiguous, valid context.
   - Success: context is isolated by user and session; explicit values override previous values; ambiguity never silently inherits.
   - Failure: request clarification when a reference cannot be resolved and clear context on reset.

3. **Persistent, governed data storage**
   - Input: approved CSV datasets loaded into a managed relational database with a documented schema.
   - Output: the same validated answers and audit records using parameterised database queries.
   - Success: results reconcile with the offline SQLite baseline, access remains read-only, and latency and failures are measured.
   - Failure: retry transient failures within a fixed limit, then escalate without fabricating figures or exposing credentials.

4. **Human-reviewed operational workflows**
   - Input: an explicitly approved request from an authenticated, authorised role.
   - Output: a reviewable recommendation and recorded approval or rejection; no automatic stock or communication action by default.
   - Success: permissions, approval trail, idempotency and audit records are verified before any execution capability is enabled.
   - Failure: deny unauthorised or ambiguous requests and leave source records unchanged.

## Submission status

All project work must remain on the single `main` branch and be contained in this repository. Part D measured evidence and release documentation are committed. The recorded offline evaluation passed all 38 golden cases, with zero ungrounded numbers and zero budget breaches. See `eval/eval_summary.md` for the four-metric results and `docs/release_gate.md` for the explicit GO decision.
