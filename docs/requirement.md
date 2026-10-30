# Requirements — DMart Regional Director Assistant

## 1. Goal

### Outcome

Build a grounded conversational analytics assistant that enables a DMart Regional Director to ask operational questions in natural language and receive answers supported by the available data. The assistant must retrieve or calculate the requested information, validate it against approved data fields, and present a clear answer with supporting evidence.

When the request cannot be answered safely or reliably, the assistant must ask for clarification, return a safe failure, or escalate the request instead of inventing an answer.

### Stakeholder

The primary stakeholder is **Kavita Rao, Regional Director at DMart**.

Kavita needs a reliable way to access store performance, inventory, and customer feedback information without manually examining multiple datasets. She should be able to ask questions about individual stores, compare performance across stores, check target achievement, identify inventory below reorder thresholds, and understand customer feedback.

The assistant must help her access reported facts quickly while making its limitations clear. It must not present unsupported assumptions or unverified explanations as facts.

### Scope

The assistant uses the following three datasets:

1. **`store_daily`** — daily store-level operational and sales performance.
2. **`inventory`** — product-level inventory quantities and reorder thresholds.
3. **`feedback`** — customer ratings and feedback themes.

The five stores in scope are:

- Mumbai
- Pune
- Hyderabad
- Bengaluru
- Ahmedabad

Store names may be used to filter, group, and compare records. The assistant must respect the available dates and records in the datasets.

The assistant supports questions about the approved metrics, comparisons across stores, inventory thresholds, and customer feedback. Weather questions may be handled through the designated weather tool rather than the three datasets. Requests outside the defined scope must not be answered as though they were supported by the DMart data.

### Decision Boundary

The assistant is a **read-only, grounded analytics assistant**. It retrieves, calculates, compares, and summarizes information from approved sources. It does not independently make operational decisions or execute business actions.

It may:
- Retrieve approved metrics for a specified store, product, or date.
- Calculate target achievement and compare actual performance with targets.
- Compare stores using approved metrics.
- Identify inventory records below their reorder thresholds.
- Summarize customer ratings and feedback themes.
- Ask for clarification when required information is missing or ambiguous.
- Explain when a requested metric or date is unavailable.
- Escalate diagnostic questions that require analyst judgment.
- Use the designated weather tool for weather-related questions.

It must not:
- Invent or estimate missing values.
- Return unapproved metrics or treat derived fields as approved metrics.
- Claim that a correlation proves causation.
- Reorder stock, update inventory, or execute other operational transactions.
- Send messages, notifications, or instructions to store staff.
- Fabricate records, dates, figures, sources, or explanations.
- Answer out-of-scope questions as if they were supported by the DMart datasets.
- Fill an unresolved store or date using conversational context without explicit resolution.

## 2. Approved Reportable Metrics

The assistant may report **exactly these 11 metric fields** from the three datasets.

| Dataset | Approved reportable fields |
|---|---|
| `store_daily` | `revenue_inr`, `daily_target_inr`, `footfall`, `stockout_hours`, `discount_pct`, `achievement_pct`, `performance_band` |
| `inventory` | `stock_units`, `reorder_threshold` |
| `feedback` | `rating`, `theme` |

No other field may be returned or treated as a reportable metric.

### Fields permitted only as keys

The following fields may be used only as filters, grouping keys, and row labels or identifiers when needed to present results:

- `store`
- `store_id`
- `date`
- `product`
- `product_id`

They must never be treated as measured values or reportable metrics. Only the 11 approved metric fields listed above may be reported as metrics. marketing_spend_inr is not an approved metric.

### Explicitly unapproved fields

`marketing_spend_inr` is not an approved reportable metric. The assistant must refuse requests to report it, even if the field exists in a source dataset.

Derived fields such as `weekend_flag`, `revenue_per_footfall`, and `marketing_efficiency` are also not part of the approved metric list and must not be reported as approved metrics.

If a request requires an unapproved field, the assistant must not substitute another field, infer the requested value, or produce a numerical estimate.

## 3. Questions the Assistant Should Answer

The assistant should answer questions that can be resolved using approved metrics, permitted identifiers, the supported date range, and the designated weather tool where applicable.

| Question type | Example | Expected behaviour |
|---|---|---|
| Single-store lookup | “What was Pune’s revenue on 15 May 2026?” | Retrieve the approved revenue value for the specified store and date. |
| Target versus actual | “Did Pune meet its target on 15 May 2026?” | Retrieve the actual revenue and target, and report the supported target-achievement result. |
| Store comparison | “Compare average revenue across the five stores.” | Compare stores using the approved revenue metric and a clearly defined period. |
| Performance ranking | “Which store had the highest average revenue during the available period?” | Calculate and report the ranking using the approved metric. |
| Inventory threshold | “Which stores are below the reorder threshold for Amul Milk?” | Compare `stock_units` with `reorder_threshold` and list records strictly below the threshold. |
| Customer feedback | “What are customers saying about Hyderabad?” | Summarize available feedback themes and report ratings only when supported by the data. |
| Date-range analysis | “What was Mumbai’s average daily revenue in May 2026?” | Calculate the average from eligible records in the requested period. |
| Weather | “What was the weather in Pune on 2026-05-15?” | Use the designated weather tool; do not invent weather information from the DMart datasets. |

For every data-backed response, the assistant must use retrieved or calculated values from approved sources. It must clearly identify the relevant store, product, date, or period when needed to interpret the answer.

## 4. Questions the Assistant Must Refuse or Escalate

| Request type | Example | Expected behaviour |
|---|---|---|
| Unapproved metric | “What was Pune’s profit margin on 15 May 2026?” | Safe Failure: explain that the requested metric is unavailable or unapproved; do not provide a figure. |
| Unapproved field | “What was Pune’s marketing spend?” | Safe Failure: do not report `marketing_spend_inr`. |
| Out-of-scope general knowledge | “What is the capital of India?” | Escalated: identify that the request is outside the assistant’s defined DMart analytics scope. |
| Operational action | “Reorder stock for Amul Milk.” | Do not execute the action; the assistant is read-only. |
| Causal diagnosis | “Why is Pune’s revenue so low?” | Escalated: this requires analyst judgment. Do not state a cause or invent a numerical explanation. |
| Missing or ambiguous entity | “What was its revenue yesterday?” when the store is unresolved | Clarification Needed: ask for the missing store or other required information. |
| Unknown store | “What was Kolkata’s revenue on 15 May 2026?” | Clarification Needed: identify the valid stores and request a supported store selection. |
| Date outside the available range | “What was Mumbai’s revenue on 15 July 2026?” | Safe Failure: explain the supported date range and do not fabricate a value. |
| Missing record | A request for a store/date combination with no matching record | Safe Failure: state that no matching record was found. |

An inability to answer must not be hidden by guessing, silently changing the question, or substituting an unapproved metric.

## 5. Prohibited Actions

The assistant must not perform any of the following actions:

1. **Invent or impute missing values at query time.** It must not manufacture a value when the requested record or metric is missing.
2. **Report unapproved metrics.** It must not return fields outside the exact 11 approved reportable metrics, including `marketing_spend_inr` and unapproved derived fields.
3. **Claim causation from correlation.** A relationship between two variables must not be presented as proof that one caused the other.
4. **Execute operational transactions.** It must not reorder inventory, change stock quantities, or modify business records.
5. **Send communications or instructions.** It must not send messages or notifications to employees, suppliers, or stores.
6. **Fabricate data or evidence.** It must not invent numerical results, source records, or citations to support an answer.
7. **Use unresolved context as a substitute for clarification.** It must not silently fill a missing store or date from a previous conversational turn.
8. **Answer unsupported diagnostic questions as established fact.** Questions requiring causal analysis or analyst judgment must be escalated.
9. **Return results for unsupported dates or nonexistent records.** It must use Safe Failure rather than extrapolating or guessing.

## 6. Governing Principle

Every data-backed answer must be grounded in the approved datasets and approved metrics. The assistant must distinguish between a supported answer, a request requiring clarification, a request that cannot safely be answered, and a request requiring escalation.

**Correctness and traceability take priority over producing an answer to every question.**
