# Part A — Findings

## 1. Store-level performance

All stores is calculated from the pooled 450 store-day rows. Mean values
are calculated across daily observations; revenue per footfall is total
revenue divided by total footfall.

| store      |   mean_daily_revenue_inr |   mean_footfall |   mean_stockout_hours |   revenue_per_footfall |   mean_achievement_pct |   poor_band_days |
|:-----------|-------------------------:|----------------:|----------------------:|-----------------------:|-----------------------:|-----------------:|
| Ahmedabad  |                782647.37 |         1922.59 |                  3.19 |                 407.08 |                  92.08 |             1.00 |
| Bengaluru  |                931065.68 |         2076.86 |                  2.38 |                 448.31 |                  98.01 |             0.00 |
| Hyderabad  |                893233.01 |         2209.51 |                  3.85 |                 404.27 |                  94.02 |             0.00 |
| Mumbai     |               1064371.60 |         2391.27 |                  1.93 |                 445.11 |                 101.37 |             0.00 |
| Pune       |                636358.55 |         1517.71 |                  2.32 |                 419.29 |                  70.71 |            70.00 |
| All stores |                861535.24 |         2023.59 |                  2.74 |                 425.75 |                  91.24 |            71.00 |

## 2. Premise test: Is Pune's low revenue explained by stockouts?

### Mean stockout hours by store

Rank 1 indicates the highest mean stockout hours.

| store     |   mean_stockout_hours |   rank |
|:----------|----------------------:|-------:|
| Hyderabad |                  3.85 |      1 |
| Ahmedabad |                  3.19 |      2 |
| Bengaluru |                  2.38 |      3 |
| Pune      |                  2.32 |      4 |
| Mumbai    |                  1.93 |      5 |

Pune ranks 4 of 5 stores for mean stockout hours
(2.32 hours per day in this dataset). The store with the highest mean
stockout hours is Hyderabad at
3.85 hours per day.

The premise that Pune is the lowest-revenue store because it has the
highest stockouts is **not supported by the store-level stockout ranking**.
Pune has the lowest mean daily revenue, but it does not have the highest
mean stockout hours. This does not establish that stockouts have no effect;
it means the supplied data does not support the stated explanation.

## 3. Correlation analysis

| Population | Variables | Pearson correlation |
|---|---|---:|
| All 450 cleaned store-days | Revenue and stockout hours | -0.152 |
| All 450 cleaned store-days | Revenue and footfall | 0.918 |
| Pune cleaned store-days | Revenue and stockout hours | -0.254 |
| Pune cleaned store-days | Revenue and footfall | 0.735 |
| Deduplicated raw rows with non-missing footfall | Revenue and footfall | 0.548 (n=446) |

Pearson correlation measures linear association. Correlation does not
establish causation and does not by itself prove that a factor causes
higher or lower revenue.

## 4. Facts

- Pune has mean daily revenue of ₹636,358.55,
  compared with ₹861,535.24 across all stores.
- Pune's mean daily footfall is 1,517.71,
  compared with 2,023.59 across all stores.
- Pune's mean stockout hours are 2.32;
  Pune ranks 4 of 5 stores by mean stockout hours.
- The cleaned-data revenue–footfall correlation across all stores is
  0.918; the Pune-only correlation is
  0.735.
- The revenue–footfall correlation on deduplicated raw data with
  non-missing footfall is 0.548, using
  446 observations.

## 5. Insights

- Pune's mean daily revenue is 26.14% below the all-store
  mean, while its mean footfall is 25.00% below the
  all-store mean. Its revenue per footfall is
  1.52% below the pooled all-store figure.
- The store-level ranking does not support the claim that Pune's low
  revenue is explained by Pune having the most stockout hours. Footfall
  has a stronger positive linear association with revenue than stockout
  hours have across the pooled cleaned observations; this is association,
  not proof of cause.

## 6. Hypotheses requiring further evidence

These are hypotheses, not confirmed findings.

1. **Hypothesis:** Lower customer traffic may be an important contributor
   to Pune's revenue gap. **Additional data needed:** hourly footfall,
   store catchment and location data, local competition, and comparable
   store traffic trends.
2. **Hypothesis:** Product-level availability or the timing of stockouts
   may affect Pune's sales even though its mean stockout hours are not
   the highest. **Additional data needed:** SKU-level stockout timestamps,
   lost-sales estimates, inventory availability, and transaction-level
   sales during stockout periods.

