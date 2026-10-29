# Data Quality Report

## 1. Dataset overview

- **File:** `data/store_daily.csv`
- **Shape:** 453 rows × 9 columns
- **Exact duplicate rows:** 3
- **Raw footfall minimum:** -150.00
- **Raw footfall maximum:** 9800.00

## 2. Column data types

| Column | Data type |
|---|---|
| `date` | `object` |
| `store_id` | `object` |
| `store` | `object` |
| `footfall` | `float64` |
| `revenue_inr` | `float64` |
| `daily_target_inr` | `int64` |
| `marketing_spend_inr` | `int64` |
| `stockout_hours` | `float64` |
| `discount_pct` | `float64` |

## 3. Missing values by column

| Column | Null count |
|---|---:|
| `date` | 0 |
| `store_id` | 0 |
| `store` | 0 |
| `footfall` | 4 |
| `revenue_inr` | 0 |
| `daily_target_inr` | 0 |
| `marketing_spend_inr` | 0 |
| `stockout_hours` | 0 |
| `discount_pct` | 0 |

## 4. Per-store footfall IQR analysis

For this calculation, exact duplicates were removed, negative footfall was
treated as missing, and quartiles were calculated using linear interpolation.
Only non-missing footfall values were used.

The lower bound is Q1 - 1.5 × IQR; the upper bound is Q3 + 1.5 × IQR.

| Store | Q1 | Q3 | Lower bound | Upper bound |
|---|---:|---:|---:|---:|
| Ahmedabad | 1844.500 | 2019.250 | 1582.375 | 2281.375 |
| Bengaluru | 1952.000 | 2211.000 | 1563.500 | 2599.500 |
| Hyderabad | 2053.000 | 2356.000 | 1598.500 | 2810.500 |
| Mumbai | 2246.000 | 2542.000 | 1802.000 | 2986.000 |
| Pune | 1434.000 | 1593.500 | 1194.750 | 1832.750 |

### Observations outside the bounds

| Store | Date | Footfall |
|---|---|---:|
| Ahmedabad | 2026-05-26 | 9800.00 |
| Mumbai | 2026-04-09 | 6100.00 |

**Number of observations outside the bounds:** 2

## 5. Decisions

### 5.1 Exact duplicate rows

- **Treatment:** Removed exact duplicate rows, keeping the first occurrence.
- **Why:** Duplicate records can cause the same store-day observation to be counted more than once and distort performance metrics.
- **Alternative rejected:** Keeping duplicates would inflate the number of observations and potentially bias analysis.
- **Raw file:** `data/store_daily.csv` remains unchanged and retains all three duplicate rows.

### 5.2 Negative footfall

- **Treatment:** Converted the negative footfall value to missing, then imputed it using the median footfall of the same store.
- **Why:** Negative customer footfall is not a plausible observed count. Treating it as missing avoids using an invalid value in subsequent calculations.
- **Alternative rejected:** Replacing it directly with zero would incorrectly represent the store as having no visitors. Using a value from another store would ignore differences in store-level footfall.
- **Raw file:** The original negative value of -150 remains in `data/store_daily.csv`.

### 5.3 Extreme footfall values

- **Treatment:** Capped non-missing footfall observations outside each store's IQR bounds at the nearest bound.
- **Why:** Store-specific bounds account for differences in footfall distributions between stores. Capping limits the influence of extreme observations while retaining the affected store-day records.
- **Alternative rejected:** Deleting the observations would discard potentially useful business activity and reduce the dataset unnecessarily.
- **Raw file:** The original extreme values of 9800 for Ahmedabad and 6100 for Mumbai remain in `data/store_daily.csv`.

### 5.4 Missing footfall

- **Treatment:** Imputed missing footfall using the median of the same store after duplicate removal, negative-value handling, and IQR capping.
- **Why:** The median is less sensitive to extreme values than the mean and preserves the store-specific distribution more robustly.
- **Alternatives rejected:** Replacing missing values with zero would imply no visitors; using the overall mean or median would ignore differences between stores. The median was selected rather than the mean because it is less sensitive to unusually high or low observations.
- **Raw file:** The four originally missing footfall values remain missing in `data/store_daily.csv`. The negative value is also retained there rather than overwritten.

### 5.5 Auditability

All footfall corrections are recorded in `analysis/cleaning_log.csv`, including the store, date, original value where applicable, replacement value where applicable, and rule applied. The raw dataset is preserved separately from the cleaned dataset.
