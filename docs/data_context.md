# Data Context — DMart Regional Director Assistant

## 1. Purpose

This document describes the three datasets available to the DMart Regional Director Assistant, their schemas, data quality, relationships, and supported analytical questions.

The assistant must use the cleaned daily dataset produced in Part A rather than the raw daily dataset. It must distinguish between columns that exist in the files and the smaller set of fields approved for reporting in `docs/requirement.md`.

## 2. Dataset Overview

| Dataset | File | Rows | Columns | Date coverage |
|---|---|---:|---:|---|
| Daily store performance | `data/store_daily_clean.csv` | 450 | 15 | 2026-04-01 to 2026-06-29 |
| Inventory | `data/inventory.csv` | 40 | 6 | No date column |
| Customer feedback | `data/feedback.csv` | 200 | 6 | Generated within 2026-04-01 to 2026-06-29 |

The raw daily dataset, `data/store_daily.csv`, contains 453 rows and 9 columns. The cleaned dataset contains 450 rows after duplicate removal and includes six additional feature columns.

The three datasets cover five stores: Mumbai, Pune, Hyderabad, Bengaluru, and Ahmedabad.

## 3. Daily Store Performance

### File and purpose

**File:** `data/store_daily_clean.csv`

This dataset contains daily operational and sales performance records for each store. It supports revenue lookups, target-achievement checks, store comparisons, performance rankings, and date-range averages.

There are 450 rows: five stores across 90 days.

### Columns and data types

The following are the logical data types represented by the CSV values. Identifiers and dates are stored as text in the CSV; numeric columns should be parsed as numeric values when loaded for analysis.

| Column | Logical type | Description |
|---|---|---|
| `date` | Date / ISO-formatted text | Date of the store record, in `YYYY-MM-DD` format |
| `store_id` | String | Store identifier |
| `store` | String | Store name |
| `footfall` | Numeric | Daily store footfall |
| `revenue_inr` | Numeric / decimal | Daily revenue in INR |
| `daily_target_inr` | Numeric | Daily revenue target in INR |
| `marketing_spend_inr` | Numeric | Daily marketing spend in INR; not an approved reportable metric |
| `stockout_hours` | Numeric | Daily stockout duration in hours |
| `discount_pct` | Numeric | Daily discount percentage |
| `revenue_per_footfall` | Numeric / decimal | Derived feature: revenue divided by footfall |
| `marketing_efficiency` | Numeric / decimal | Derived feature: revenue divided by marketing spend |
| `achievement_pct` | Numeric / decimal | Derived feature: revenue divided by target, multiplied by 100 |
| `shortfall_inr` | Numeric / decimal | Derived feature: target minus revenue |
| `weekend_flag` | String | `Yes` for Saturday or Sunday; otherwise `No` |
| `performance_band` | String | `Excellent`, `Good`, or `Poor`, based on target achievement |

### Data quality and cleaning

Part A identified the following issues in the raw dataset:

- The raw file contained **453 rows and 9 columns**.
- **Three exact duplicate rows** were removed, leaving 450 rows.
- Four footfall values were missing.
- Footfall ranged from **-150 to 9,800** in the raw data.
- One negative footfall value was treated as a data error and set to missing before imputation.
- Two extreme footfall values fell outside their store-specific IQR bounds: Mumbai's 6,100 and Ahmedabad's 9,800.
- Five footfall values were filled using the respective store's median after the cleaning and capping steps.

The five median-imputed values were:

| Store | Date | Imputed footfall |
|---|---|---:|
| Mumbai | 2026-04-30 | 2,386.0 |
| Pune | 2026-04-12 | 1,509.5 |
| Pune | 2026-05-17 | 1,509.5 |
| Bengaluru | 2026-06-10 | 2,065.0 |
| Hyderabad | 2026-04-21 | 2,216.0 |

The two capped values were:

| Store | Date | Original footfall | Capped footfall |
|---|---|---:|---:|
| Ahmedabad | 2026-05-26 | 9,800 | 2,281.38 |
| Mumbai | 2026-04-09 | 6,100 | 2,986.00 |

The cleaning process follows a fixed order: remove exact duplicates, treat negative footfall as missing, cap non-missing footfall outside store-specific IQR bounds, impute remaining missing footfall using the relevant store's median, and leave the other original columns unchanged.

### Guarantees of the cleaned file

Part A's acceptance criteria require `data/store_daily_clean.csv` to have:

- Exactly 450 rows.
- No missing values in any column.
- No negative footfall values.
- Six derived feature columns: `revenue_per_footfall`, `marketing_efficiency`, `achievement_pct`, `shortfall_inr`, `weekend_flag`, and `performance_band`.

The cleaning log at `analysis/cleaning_log.csv` records the changes made during cleaning.

### Questions supported

This dataset supports questions such as:

- What was a store's revenue or footfall on a specified date?
- Did a store meet its daily revenue target?
- What was the average revenue for a store over a specified date range?
- How do stores compare on an approved metric?
- Which store had the highest or lowest average value for an approved metric?
- What was a store's performance band on a given date?

The assistant may report only the approved metrics listed in `docs/requirement.md`. The presence of `marketing_spend_inr`, `marketing_efficiency`, `revenue_per_footfall`, or `shortfall_inr` in the CSV does not make them approved reportable metrics.

## 4. Inventory

### File and purpose

**File:** `data/inventory.csv`

The inventory dataset contains one record for each store-product combination. It contains 40 rows, representing five stores and eight products per store.

**This dataset has no date column.** Inventory questions must therefore be answered from the available inventory records, not from a date-based inventory history.

### Columns and data types

| Column | Logical type | Description |
|---|---|---|
| `store_id` | String | Store identifier |
| `store` | String | Store name |
| `product_id` | String | Product identifier |
| `product` | String | Product name |
| `stock_units` | Integer | Units currently recorded in stock |
| `reorder_threshold` | Integer | Stock threshold used to identify inventory below the threshold |

### Data quality

The project brief specifies 40 inventory records, covering five stores and eight products. The supplied brief does not establish additional inventory cleaning or imputation steps. The implementation should inspect the actual CSV before assuming any further guarantees.

The assistant must compare `stock_units` with `reorder_threshold` directly. A store is below the reorder threshold only when:

`stock_units < reorder_threshold`

A value equal to the threshold is not below it.

### Questions supported

This dataset supports questions such as:

- Which stores are below the reorder threshold for a specified product?
- What are the recorded stock units and reorder threshold for a product at a store?
- Does a particular store-product record fall below its threshold?

It does not support historical inventory trends because no inventory date or inventory history is provided. Identifying a low-stock record does not authorize the assistant to reorder stock.

## 5. Customer Feedback

### File and purpose

**File:** `data/feedback.csv`

The feedback dataset contains 200 records, with 40 records generated for each of the five stores. Each record represents a feedback entry associated with a store and a date.

### Columns and data types

| Column | Logical type | Description |
|---|---|---|
| `feedback_id` | String | Feedback record identifier |
| `store_id` | String | Store identifier |
| `store` | String | Store name |
| `date` | Date / ISO-formatted text | Date associated with the feedback record |
| `rating` | Numeric, with missing values | Customer rating on a scale of 1–5 |
| `theme` | String | Feedback theme |

The defined feedback themes are Stock availability, Queue time, Pricing, Freshness, and Staff behaviour.

### Data quality

The project generator deliberately leaves **12 of the 200 feedback ratings unrated**. Missing ratings must remain missing; the assistant must not replace them with an average or an invented rating.

When calculating an average rating, only records with an actual rating are included in the average. The response should distinguish the number of rated records from the total number of feedback records.

The observed feedback dates range from 2026-04-01 to 2026-06-29, verified against the committed data/feedback.csv file. The dataset therefore covers the full project date range.

### Questions supported

This dataset supports questions such as:

- What are customers saying about a specified store?
- What is the average rating for a store?
- How many feedback records are rated, and how many exist in total?
- Which feedback theme occurs most frequently for a store?

An average rating must be calculated from rated rows only. If multiple themes are tied for the highest frequency, the implementation must apply the project's specified tie-breaking rule.

## 6. Relationships Between the Datasets

All three datasets contain the store name in the `store` column. They also contain `store_id`, which identifies the store consistently across the generated datasets.

The five store names are:

| `store_id` | `store` |
|---|---|
| `S01` | Mumbai |
| `S02` | Pune |
| `S03` | Hyderabad |
| `S04` | Bengaluru |
| `S05` | Ahmedabad |

The datasets serve different purposes:

- `store_daily_clean.csv` contains daily store-level measures.
- `inventory.csv` contains current store-product stock and threshold records.
- `feedback.csv` contains dated customer feedback entries.

The shared store names allow the assistant to filter or group each dataset for the relevant store. Query the appropriate dataset independently and do not join datasets for an answer. Inventory has no date, so it must not be represented as historical inventory.

The assistant should filter records to the requested store or stores and use the appropriate dataset for each intent. Joins must preserve the grain of each dataset: daily records, store-product records, and feedback records must not be multiplied inadvertently in a join.

## 7. Approved Metrics Versus Stored Columns

The datasets contain more columns than the assistant is authorized to report. The approved reportable fields are defined in `docs/requirement.md` and total exactly 11:

- **`store_daily`:** `revenue_inr`, `daily_target_inr`, `footfall`, `stockout_hours`, `discount_pct`, `achievement_pct`, `performance_band`
- **`inventory`:** `stock_units`, `reorder_threshold`
- **`feedback`:** `rating`, `theme`

The key columns `store`, `store_id`, `date`, `product`, and `product_id` may be used as filtering or grouping keys only. They are not reportable metrics.

Fields such as `marketing_spend_inr`, `revenue_per_footfall`, `marketing_efficiency`, `shortfall_inr`, and `weekend_flag` may exist in the daily CSV but are not approved reportable metrics. A request for an unapproved metric must be refused rather than answered using an alternative field.

## 8. Part A Findings Relevant to the Assistant

Part A tested the premise that Pune has the lowest revenue because of stockouts. The documented findings include:

1. Pune ranks **fourth out of five stores** by mean stockout hours, at 2.32 hours, compared with the all-store mean of 2.74 hours. Hyderabad has the highest mean stockout duration at 3.85 hours. The claim that Pune has the most stockouts is therefore not supported.
2. Across all daily records, the revenue-footfall correlation is **0.918**, while the revenue-stockout correlation is **-0.152**. These are associations, not proof of causation.
3. Pune's mean daily revenue is **26.14% below** the all-store mean, while its mean footfall is **25.00% below** the all-store mean.
4. Pune's revenue per footfall is 419.29, compared with 425.75 for all stores, a difference of 1.52%. This supports the documented interpretation that Pune's performance gap is more consistent with a footfall gap than a stockout gap; it does not prove a causal mechanism.
5. The daily acceptance examples include Pune on 2026-05-16 with `achievement_pct` 74.59 and `performance_band` `Poor`, and Mumbai on 2026-05-21 with `achievement_pct` 107.99 and `performance_band` `Excellent`.

These findings provide useful context for understanding the dataset, but they must not override the approved-field restrictions or be used to make unsupported causal claims in individual answers.

## 9. Implementation Rules

1. Load `data/store_daily_clean.csv`, not `data/store_daily.csv`, for the assistant's daily performance queries.
2. Load `data/inventory.csv` and `data/feedback.csv` for their respective question types.
3. Check the actual CSV headers, data types, row counts, and date coverage when the implementation loads the files.
4. Do not treat the presence of a field in a CSV as authorization to report it.
5. Use the store identifiers and names consistently and preserve the grain of each dataset.
6. Do not impute missing feedback ratings or invent inventory dates.
7. Use the available daily date range of 2026-04-01 through 2026-06-29 for date-scoped analysis, and reject unsupported dates rather than extrapolating.
8. Ground every numerical response in retrieved records or explicitly defined calculations.

**Principle:** The datasets describe what is recorded, the cleaning process describes what was corrected, and the approved metric list defines what the assistant is allowed to report.
