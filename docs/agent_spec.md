# Agent Specification — DMart Regional Director Assistant

## 1. Purpose and design principles

The DMart Regional Director Assistant answers routine store-operations questions using three synthetic practice datasets created in Part A:

- `data/store_daily_clean.csv`
- `data/inventory.csv`
- `data/feedback.csv`

The assistant supports store-level lookups, target checks, cross-store comparisons, inventory threshold checks, customer-feedback summaries, and a constrained weather tool.

The assistant must follow these principles:

1. **Approved data only:** Report only the 11 approved reportable metric fields defined in `requirement.md`. Do not report unapproved derived fields or other columns as metrics.
2. **Grounded answers:** Every numeric claim must be traceable to a fetched data value, computed result, or explicitly quoted constant.
3. **Clarification over guessing:** Ask for missing or ambiguous required entities rather than silently choosing one.
4. **Safe status handling:** Apply the status rules and precedence in this document consistently.
5. **Auditable execution:** Record every request, its route, status, evidence, grounding information, attempts, and latency.
6. **Offline-first implementation:** Use a rule-based interpreter, fixed answer templates, local SQLite, and the weather stub by default. No language model, API key, or hosted database is required.
7. **No unsupported causal conclusions:** The assistant must never present a correlation as proof of cause. Questions requiring diagnosis or explanation beyond the supported analysis must be escalated.

## 2. Data-access and reportable-field rules

The only approved reportable metric fields are:

| Dataset | Approved reportable metric fields |
|---|---|
| `store_daily` | `revenue_inr`, `daily_target_inr`, `footfall`, `stockout_hours`, `discount_pct`, `achievement_pct`, `performance_band` |
| `inventory` | `stock_units`, `reorder_threshold` |
| `feedback` | `rating`, `theme` |

The following columns may be used only as filters, grouping keys, or row labels: `store`, `store_id`, `date`, `product`, and `product_id`. They are not reportable metrics and are not part of the 11 approved fields.

`marketing_spend_inr` is deliberately not approved. Other unapproved fields include derived fields such as `revenue_per_footfall`, `marketing_efficiency`, `shortfall_inr`, and `weekend_flag`.

Before any query executes, validate the requested table and measured columns against the approved field list. A request for an unapproved field must be classified as `unsupported_metric` and return `Safe Failure`. A prohibited-action or rule-override request must be classified as `out_of_scope` and return `Escalated`.

For SQL:

- Use the local SQLite database built from the three datasets.
- Use `?` placeholders for store names, dates, products, and other user-supplied values.
- Never concatenate user text into a SQL value or filter.
- A dynamic column name may enter SQL only after it has passed the approved-field check.
- Sort direction must be selected from the fixed whitelist `ASC` or `DESC`.
- Never use a key column as the measured value.

## 3. Processing pipeline

The pipeline contains eight steps. **Validation is performed before the data query executes**, even though the steps are presented below in execution order.

| Step | What it does | Type | Technique |
|---|---|---|---|
| Interpret | Identify the intent, store, metric, date or range, product, weather request, confidence, and missing required entities. | Generative-style interface, implemented deterministically | Rule-based interpreter using closed vocabularies, date grammar, exact matches, aliases, and controlled fuzzy matching. No language model in the default mode. |
| Route | Select the appropriate Python function, SQL query, weather tool, combined Python-plus-weather route, or no route. | Deterministic | Fixed intent-to-route mapping. |
| Validate | Check the intent, table, and requested measured fields against the approved list before executing any query. Reject unsupported fields and prohibited requests. | Deterministic | Allowlist and rule checks. |
| Query | Fetch the requested records or aggregates from the cleaned data, local SQLite, or weather tool. | Deterministic | Python lookup functions, parameterised SQLite queries, or the weather tool. |
| Calculate | Calculate target achievement, averages, rankings, counts, and other permitted derived results. | Deterministic | Python arithmetic, SQL aggregation where appropriate, and explicit rounding rules. |
| Synthesize | Turn the validated results into a concise answer and assign the applicable completion status. | Generative-style interface, implemented deterministically | Fixed answer templates and status rules. No language model in the default mode. |
| Ground | Attach source evidence and numeric grounding values; calculate the ungrounded-number count. | Deterministic | Structured evidence records, fetched-value tracking, and numeric checks. |
| Record | Append the result and audit metadata as one JSON line. | Deterministic | JSON Lines logging, a monotonic timer, and token estimation by whitespace-separated words. |

The two generative-style steps are deliberately implemented with deterministic rules in the default configuration. An optional language-model experiment must not change the approved-field restrictions, status precedence, grounding requirements, or offline acceptance behaviour.

## 4. Intent classification and routing

The interpreter uses the following intents. Intent classification follows the priority rules in Section 5; the table describes the resulting intent and route.

| Intent | Example question | Route | Required entities |
|---|---|---|---|
| `lookup` | What was Pune's revenue on 2026-05-15? | Python for one store and one date; SQL for a date-range average | Store, metric, date or range |
| `target_vs_actual` | Did Pune meet its target on 2026-05-15? | Python function | Store, one date |
| `comparison` | Which store had the highest revenue between 2026-05-01 and 2026-05-31? | SQL | Metric, date or range |
| `inventory` | Which stores are below the reorder threshold for Amul Milk? | SQL | Product; store is optional |
| `feedback` | What are customers saying about Hyderabad? | SQL | Store |
| `weather` | What was the weather in Pune on 2026-05-15? | Weather tool | Store, one date |
| `unsupported_metric` | What was Pune's profit margin on 2026-05-15? | None | None |
| `out_of_scope` | What is the capital of India? | None | None |
| `diagnostic` | Why is Pune's revenue so low? | None | None |

A weather request combined with a one-store, one-date lookup or target check uses the Python data route plus the weather tool. There is no combined SQL-and-weather route.

### 4.1 Query behaviour by intent

- **`lookup`:** A single date returns the selected approved metric for one store and date. A date range returns that store's average metric over the inclusive range.
- **`target_vs_actual`:** Fetch revenue and daily target for one store on one date. Calculate achievement as revenue divided by target, multiplied by 100, and use the stored `performance_band` for the band decision. A range is not accepted for this intent.
- **`comparison`:** Calculate each store's average metric over the inclusive date range and rank stores. The default order is highest first. Explicit `highest` means highest first; explicit `lowest` means lowest first. For `stockout_hours`, `best` means lowest first and `worst` means highest first. For other metrics, `best` means highest first and `worst` means lowest first. Ties at two decimal places are sorted by store name, regardless of direction.
- **`inventory`:** Return stores where `stock_units` is strictly below `reorder_threshold` for the selected product. Equality does not count as below threshold. If no store is below threshold, return a fixed no-shortage message without invented figures.
- **`feedback`:** For the selected store, calculate the average `rating` using rated rows only, report the number of rated rows and total rows, and return the most frequent `theme`. Break theme-frequency ties alphabetically by theme name. Do not impute missing ratings.
- **`weather`:** Use the weather tool for one store and one date. Use the stub by default; live calls are optional.
- **`unsupported_metric`:** Do not query the data to approximate the requested metric. Return a safe refusal.
- **`out_of_scope`:** Do not answer unrelated questions or requests to override the rules. Escalate.
- **`diagnostic`:** Do not infer a cause from observed relationships. Escalate for analyst review.

## 5. Interpretation and entity-resolution rules

### 5.1 Store names and aliases

The five recognised stores are Mumbai, Pune, Hyderabad, Bengaluru, and Ahmedabad.

- Match an exact store name case-insensitively, with confidence `1.0`.
- Treat `Bangalore` as an explicit alias for `Bengaluru`, with confidence `1.0`.
- Use controlled fuzzy matching, such as `difflib.SequenceMatcher`, for eligible candidate words. The best similarity score becomes the store entity's confidence.
- A fuzzy candidate must be at least five letters long and capitalised in the question or carry a possessive `'s`. It must not be the first word unless it carries `'s`, and must not be a keyword, stop word, recognised product word, or one of the brief's proper nouns.
- The fuzzy-match examples that must work are `Bengalore` (0.78), `Bangalor` (0.71), `Punee` (0.89), `Hydrabad's` (0.94), and `Mumbay` (0.83). `Banglore` (0.59) must not resolve to a store.
- Lowercase misspellings without a possessive are not fuzzy-matched. The lowercase words `pure`, `ahead`, `plunge`, `pane`, and `ahmed` must not be matched as stores.
- A low-confidence candidate that appears to name a store must be preserved as an unresolved named store where the project rules require it. Do not silently discard a second unresolved store in a comparison or replace an unresolved named store with session context.
- If a brand/persona proper noun from the brief carries `'s` or directly follows `for`, `about`, `in`, or `at`, and no store resolves elsewhere, treat it as an unresolved named store rather than silently taking a store from context.
- The interpreter must distinguish a genuine unsupported question, such as `What is the capital of India?`, from a question that names a possible but unresolved store.

An unresolved named store has confidence `0.4` and results in `Clarification Needed`, except where the intent itself has a higher-priority status under Section 7.

### 5.2 Product names

Match recognised product names case-insensitively, with or without the size suffix. For example, `Amul Milk` and `Amul Milk 1L` refer to the same product. Do not fuzzy-match products.

### 5.3 Metric synonyms and unsupported fields

Use this closed synonym list:

| User wording | Canonical field |
|---|---|
| `revenue`, `sales`, `turnover`, `earnings` | `revenue_inr` |
| `target` | `daily_target_inr` |
| `footfall`, `visitors` | `footfall` |
| `stockout` | `stockout_hours` |
| `discount` | `discount_pct` |

Recognised synonyms have confidence `1.0`. Field names outside the approved list must be checked **before** synonym mapping. In particular, `revenue per footfall` must not be answered as ordinary revenue.

The following words or phrases indicate an unsupported metric or field: `profit`, `margin`, `marketing`, `cost`, `expense`, `shortfall`, `efficiency`, `weekend`, `per footfall`, and `per visitor`. Handle singular and plural forms consistently. Treat underscores as spaces for field-name recognition, so `performance_band` and `performance band` are equivalent.

### 5.4 Closed date grammar

Accept only these date forms:

1. ISO date: `YYYY-MM-DD`, with a real calendar date.
2. Day, full month name, year: `15 May 2026`. The month name is case-insensitive; abbreviated month names are not accepted.
3. `yesterday`.
4. `between <date> and <date>`, inclusive.

`from <date> to <date>` is not a supported range form.

Set `AS_OF_DATE = 2026-06-30`; therefore, `yesterday` resolves to `2026-06-29`.

Anything that looks like a date but is outside the grammar is an unresolved named date. Examples include `20260515`, `2026-5-15`, `2026-W20-5`, `2026-02-30`, `May 15, 2026`, `15 Jun 2026`, `15 May`, `15th May 2026`, `last week`, `tomorrow`, `today`, `Sunday` without a valid matching date, `last 7 days`, `month to date`, `YTD`, and a bare year.

Additional rules:

- A second date outside the supported `between` form is unresolved.
- A range whose start is after its end is unresolved.
- A range supplied to `target_vs_actual` or `weather` is unresolved, whether supplied in the question or carried from context.
- A weekday alongside a valid date is ignored only if it matches the calendar weekday. A mismatched weekday is an unresolved named date.
- A question without a date phrase may take the date from session context when that intent requires a date. A date phrase that is present but unsupported must not be replaced from context.
- Date-like phrases in `inventory` and `feedback` questions are dropped before validation; those intents operate over their supported rows without date filtering.
- Frequency phrases such as `daily target`, `average daily revenue`, `monthly revenue`, and `per day` are metric-frequency language, not date phrases.
- Month names are treated as date phrases wherever they occur, subject to the brief's exceptions for the verbs `may` and `march`.

An unresolved named date has confidence `0.4`. For date-using intents, it produces `Clarification Needed` and is never replaced by a date from session context.

### 5.5 Confidence score and ambiguity

The confidence score is between `0` and `1`.

- Exact store, alias, exact product, recognised metric synonym, or valid date/range: `1.0`.
- Fuzzy store match: its best similarity score.
- Missing required entity, unresolved named store/date, or ambiguous request: `0.4`.
- An entity resolved from valid context in the same session counts as `1.0`.
- If the intent uses no entities, confidence is `1.0`.
- Overall confidence is the minimum confidence across the entities used by the intent, including any store explicitly named in the question.

A confidence score **below `0.7`** requires clarification.

If an intent uses two different stores or two different metrics, set confidence to `0.4` and ask which one the user means. Never use first-match-wins for an ambiguous pair. For example, `Compare Mumbai and Pune revenue on 2026-05-15` requires clarification.

### 5.6 Intent precedence

Classify the intent using the following ordered rules. The first matching rule decides the intent.

1. **Prohibited action or rule override → `out_of_scope`.** This includes `ignore`, `disregard`, `override`, `bypass`, `forget`, `send`, `email`, `whatsapp`, `purchase`, `buy`, `restock`, `place an order`, and imperative uses of `order` or `reorder`. The words `threshold`, `level`, or `point` immediately after `order`/`reorder` indicate an inventory noun phrase rather than an imperative.
2. **Unsupported field → `unsupported_metric`.** Check this before applying synonyms. Include unsupported terms such as profit, margin, marketing, cost, expense, shortfall, efficiency, weekend, per footfall, and per visitor.
3. **Why, trend, or reason question → `diagnostic`.**
4. **Product name or inventory/reorder wording → `inventory`.**
5. **Feedback, reviews, ratings, or customers saying/say/says → `feedback`.**
6. **Target-check language → `target_vs_actual`.** This includes `target` with hit, met, meet, miss, missed, beat, exceed, exceeded, achieve, achieved, reach, reached, below, above, against, versus, or `fall short`; it also includes `achievement` or `performance band`.
7. **Which/highest/lowest/best/worst comparison without a named store → `comparison`.**
8. **Recognised metric, with or without store/date → `lookup`.**
9. **Weather wording without a metric → `weather`.**
10. **A question naming a store and/or date but no metric or weather word → `lookup`.** If the last stored question in the same session was `target_vs_actual`, a bare follow-up naming only a store or only a date remains a target check.
11. **Nothing recognisable → `out_of_scope`.**

These rules are closed vocabularies and may be widened only if doing so does not change any required acceptance-case outcome.

### 5.7 Required entities by intent

Only the entities listed for an intent are used. Other mentioned entities are dropped before validation, do not lower confidence, are not range-checked, and are not stored in context.

| Intent | Required entities | Optional entities | Entity rules |
|---|---|---|---|
| `lookup` | Store, metric, date or range | None | A range returns the store's average metric over the inclusive range. |
| `target_vs_actual` | Store, one date | None | Revenue and target are fixed; a range is unresolved. |
| `comparison` | Metric, date or range | None | Never requires or inherits a store. Missing date requires clarification. |
| `inventory` | Product | Store | A supplied store restricts the result to that store. |
| `feedback` | Store | None | Summarises all rows for the store. |
| `weather` | Store, one date | None | A range is unresolved. |
| `unsupported_metric` | None | None | Intent alone determines the status. |
| `out_of_scope` | None | None | Intent alone determines the status. |
| `diagnostic` | None | None | Intent alone determines the status. |

If required entities remain missing after applying context, return `Clarification Needed` with confidence `0.4`. Name every missing or unresolved entity in the clarification message.

### 5.8 Session context

Context is maintained within a session and must never cross session boundaries.

- A newly named, resolved entity overrides the previous value.
- A required entity omitted from a question may be taken from the last resolved value of the same session: store, metric, date/range, or product.
- Only entities required by the current intent may be inherited. A `comparison` never inherits a store.
- An unresolved named store/date and an ambiguous pair must never be replaced by a context value.
- A date range in context must not be carried into `target_vs_actual` or `weather`, which require one date.
- `unsupported_metric`, `diagnostic`, and `out_of_scope` questions do not update context.
- Every other question, including one ending in `Clarification Needed`, stores the resolved entities it used.
- A `target_vs_actual` question stores the store and date only, not a metric. It marks the session so a bare follow-up naming only a store or date continues the target check. Any other stored question clears that mark.

## 6. Calculation and output rules

### 6.1 Target checks

A target check fetches revenue, target, and the stored performance band for the selected store/date. Achievement is revenue divided by target, multiplied by 100.

A result in the `Poor` band, below 75% of target, triggers the `Drafted` status so that the answer is held for human approval. Other successfully grounded target checks may be `Answered`.

### 6.2 Averages and rounding

Averages for comparisons, date-range lookups, and feedback ratings must be rounded to two decimal places using **round-half-up**. The full-period and 31-day comparison results must reconcile with the project brief's stated outputs and Part A analysis. Document the rounding method in the README.

A suitable implementation is to aggregate counts and sums in SQLite, then divide in Python using the `decimal` module and `ROUND_HALF_UP`. Since the averaged columns have at most two decimal places, integer-cent arithmetic is also acceptable.

### 6.3 Number formats

- Money: `INR <value>` with two decimals and no thousands separator, for example `INR 623845.00`.
- Percentages: two decimals and a `%` sign.
- Average rating, footfall, and stockout hours: two decimals.
- Counts such as stock units, rated rows, and all rows: integers.
- Weather values: one decimal place; rainfall is a number followed by a space and `mm`, for example `0.0 mm`.

### 6.4 Evidence and numeric grounding

Every data answer must contain:

- `evidence`: one entry per data source used, with `source`, `fields`, `store`, and `date`.
- `grounded_values`: the list of numeric values taken from fetched records, computed results, tool results, or quoted constants. Each entry is a string matching the number's displayed form in `answer_text`, without the `INR ` prefix, `%` sign, or unit.
- `ungrounded_numbers`: the count of numbers in `answer_text` that do not match `grounded_values`.

Build `grounded_values` from fetched or computed values, not by scanning the finished answer text. Remove ISO dates and product-size strings such as `Amul Milk 1L` from the numeric check. Fixed-message numbers that were not fetched must be written in words or included in `grounded_values`.

**Every reply must have `ungrounded_numbers = 0`, regardless of status.** Never invent a number or replace a fetched figure with a fabricated one.

## 7. Status decision table and precedence

| Status | Exact condition |
|---|---|
| `Answered` | The question is understood, validated, fetched, and grounded; no alert is triggered and no higher-precedence rule applies. |
| `Drafted` | The answer is composed but held for human approval because a target check returns the `Poor` performance band, below 75% of target. |
| `Clarification Needed` | Confidence is below `0.7`; a required entity is missing; a named store/date remains unresolved; or two different stores or metrics make the request ambiguous. |
| `Escalated` | The request is out of scope, is diagnostic, or the data query has failed after three total attempts. |
| `Safe Failure` | The request asks for an unapproved field, uses an out-of-range date for a date-using intent, or has no record for the requested product, store, or date. |

### 7.1 Status precedence

Apply the first applicable rule in this order:

1. **Intent-based status:** `unsupported_metric` → `Safe Failure`; `out_of_scope` or `diagnostic` → `Escalated`.
2. **Clarification:** Missing required entity, unresolved named store/date, two different stores or metrics, or confidence below `0.7` → `Clarification Needed`.
3. **Date range:** For `lookup`, `target_vs_actual`, `comparison`, and `weather`, a date or range outside `2026-04-01` to `2026-06-29` → `Safe Failure`. `inventory` and `feedback` drop date phrases, so this date rule does not apply to them.
4. **Query result:** Three failed attempts → `Escalated`; no record found → `Safe Failure`.
5. **Successful result:** If the alert fires, `Drafted`; otherwise, `Answered`.

A prohibited-action or rule-override request is `out_of_scope` and therefore `Escalated`, even if it also names a metric. Do not execute its requested action.

## 8. Retry and escalation policy

Each data query has a maximum of **three total attempts: one initial attempt plus two retries**.

- Retry a failed data query until it succeeds or reaches the maximum.
- After the third failure, return `Escalated`; do not fabricate a result.
- The log's `attempts` value is the highest attempt count among the question's data queries, or `0` if no data query ran.
- A retry does not count as an additional tool call.
- For reproducible testing, `SIMULATE_DB_FAILURES=<n>` makes the first `n` attempts of every query in a question fail.
- Two simulated failures followed by success must return a grounded answer with `attempts = 3`.
- Three simulated failures must return `Escalated` with `attempts = 3` and no invented data figure.

## 9. Logging and audit contract

The public function is:

`handle(question, session_id, user_id="u1")`

It returns a structured dictionary and appends one JSON line per call to the path specified by `AGENT_LOG_PATH`, defaulting to `logs/runs.jsonl`. Read this environment variable inside `handle` on every call, not only at import time.

Each log record contains:

- `run_id`
- `user_id`
- `session_id`
- `timestamp`
- `question`
- `intent`
- `confidence`
- `route`
- `executed`
- `attempts`
- `tools_called`
- `status`
- `answer_text`
- `evidence`
- `grounded_values`
- `latency_ms`
- `tokens_est`
- `tool_calls`
- `ungrounded_numbers`
- `budget_exceeded`

Allowed route values are `python`, `sql`, `weather`, `python+weather`, and `none`.

Logging rules:

- `executed` records the function or SQL text actually run; it is `null` when no query was started.
- `route`, `executed`, and `tool_calls` describe data access actually started. A question rejected before querying has route `none`, `executed = null`, and `tool_calls = 0`.
- A question whose data query was attempted but all attempts failed keeps its route and data `tool_calls = 1`.
- `tools_called` lists external tools only. The weather tool is named `weather_tool`.
- A Python or SQL data route contributes one `tool_calls` entry; each weather call contributes one more. Retries do not add entries.
- A data lookup alone has `tools_called = []` and `tool_calls = 1`. A lookup with weather has `tools_called = ["weather_tool"]` and `tool_calls = 2`. A weather-only request has `tools_called = ["weather_tool"]`, `tool_calls = 1`, and `attempts = 0`.
- Measure `latency_ms` using a monotonic clock around the whole call.
- `tokens_est` is the number of whitespace-separated words in the question plus the answer.
- `budget_exceeded` is `true` when `tokens_est` is above 150.

The acceptance runner writes its output to `logs/runs.jsonl` and must clear that file before running the 20 acceptance cases. The evaluation runner writes to `eval/eval_runs.jsonl`. These logs must remain separate.

## 10. Success criteria

The assistant is successful only when the following criteria can be demonstrated from committed text, logs, and transcripts:

1. **Intent and entity resolution:** All nine required intents are represented. Exact store names, the `Bangalore` alias, required fuzzy matches, metric synonyms, supported dates, and session-context rules behave as specified.
2. **Clarification:** Every missing or ambiguous required entity is identified. Confidence below `0.7` never produces a data answer. Unresolved named stores/dates are not silently replaced by context.
3. **Field safety:** Every requested measured field is checked against the 11-field allowlist before query execution. Unsupported metrics do not execute a data query.
4. **Query correctness:** Single-store/single-date lookups and target checks use Python; comparisons, inventory, feedback, and range lookups use SQL.
5. **Safe SQL:** User-supplied values are parameterised; dynamic fields are allowlisted; sort direction is restricted to `ASC` or `DESC`.
6. **Numerical correctness:** Target achievement, averages, rankings, inventory thresholds, and feedback summaries match the source records and required rounding rules.
7. **Grounding:** Every answer has evidence and grounding metadata; `ungrounded_numbers` is zero in every logged reply.
8. **Status correctness:** All five statuses follow the decision table and precedence without conflicting outcomes.
9. **Retries:** Two simulated failures followed by success complete on attempt three; three simulated failures end as `Escalated`.
10. **Audit completeness:** Every handled question creates one valid JSONL record with the required fields, correct route, attempt count, latency, token estimate, tool-call count, and status.
11. **Offline operation:** The default assistant works using local files, Python, SQLite, a rule-based interpreter, and the weather stub, without an API key.
12. **Reproducibility:** The acceptance transcript and logs are committed to the repository and provide evidence for the claims made in the README.

## 11. Completion states

Every request ends in exactly one of the following states:

- **Answered:** A supported answer was retrieved, validated, and grounded successfully.
- **Drafted:** A supported answer was prepared but requires human approval because the target-check alert fired.
- **Clarification Needed:** The user must resolve a missing, ambiguous, or unresolved required entity before the assistant can answer.
- **Escalated:** The request needs human or analyst intervention, is out of scope, is diagnostic, or exhausted its permitted query attempts.
- **Safe Failure:** The request cannot be answered safely because it uses an unapproved field, an out-of-range date, or has no matching record.

Every state must return an explicit status and an appropriate answer message. A state must not imply that an action was executed when the assistant only prepared or refused a response.

## 12. Part D test categories

Part D must test and report evidence for these categories:

1. **Basic lookups and context:** Exact store/date/metric; missing entities; case-insensitive store names; `Bangalore`; fuzzy store typo; `yesterday`; supported date ranges; same-session follow-up; session isolation.
2. **Target checks:** `Poor`, `Good`, and `Excellent` outcomes; the `Poor` case must be `Drafted`.
3. **Comparisons:** Average metric across a range; highest/lowest rankings; correct ordering and tie-breaking; reconciliation with Part A.
4. **Inventory:** Below-threshold results; equality to threshold excluded; no stores below threshold; unknown product/store handling.
5. **Feedback:** Rated-row averages, rated versus total row counts, most frequent theme, tie-breaking, and no imputation of unrated feedback.
6. **Unsupported fields and prohibited actions:** Unapproved fields; `marketing_spend_inr`; profit/margin; requests to send messages, order/reorder stock, or override rules.
7. **Out-of-scope and diagnostic questions:** Unrelated questions and requests for causal explanations.
8. **Date and entity failures:** Out-of-range dates; invalid date formats; unresolved dates; unknown store; ambiguous stores or metrics.
9. **Retry and escalation:** Recovery after two simulated failures; escalation after three failures; no fabricated figures after exhaustion.
10. **Grounding and logging:** Correct evidence, `grounded_values`, `ungrounded_numbers = 0`, route, attempts, tool calls, latency, token estimate, and separate acceptance/evaluation logs.
11. **Weather:** Stub output, route and tool-call accounting, weather number formats, and safe behaviour for unsupported dates or unresolved stores.
12. **Regression and reproducibility:** The 20 required acceptance cases and the Part D golden-set evaluation, with results committed to the repository.

The implementation must follow this specification. If a behaviour is not explicitly supported by the data, approved-field list, or intent rules, the assistant must clarify, safely refuse, or escalate rather than invent a result.
