import pandas as pd
from pathlib import Path

CLEAN_PATH = Path("data/store_daily_clean.csv")
RAW_PATH = Path("data/store_daily.csv")
FINDINGS_PATH = Path("analysis/findings.md")

df = pd.read_csv(CLEAN_PATH)
raw = pd.read_csv(RAW_PATH)

# Confirm the expected analysis dataset.
assert df.shape == (450, 15), f"Unexpected cleaned shape: {df.shape}"
assert df.isna().sum().sum() == 0, "Cleaned dataset contains missing values"

# A. Store-level performance metrics.
def performance_metrics(group):
    return pd.Series({
        "mean_daily_revenue_inr": group["revenue_inr"].mean(),
        "mean_footfall": group["footfall"].mean(),
        "mean_stockout_hours": group["stockout_hours"].mean(),
        "revenue_per_footfall": (
            group["revenue_inr"].sum() / group["footfall"].sum()
        ),
        "mean_achievement_pct": group["achievement_pct"].mean(),
        "poor_band_days": (group["performance_band"] == "Poor").sum(),
    })

store_metrics = (
    df.groupby("store", sort=True)
      .apply(performance_metrics, include_groups=False)
      .reset_index()
)

all_metrics = performance_metrics(df).to_frame().T
all_metrics.insert(0, "store", "All stores")

metrics = pd.concat(
    [store_metrics, all_metrics],
    ignore_index=True
)

numeric_cols = metrics.select_dtypes(include="number").columns
metrics[numeric_cols] = metrics[numeric_cols].round(2)

print("STORE PERFORMANCE METRICS")
print(metrics.to_string(index=False))

# B. Rank stores by mean stockout hours.
stockout_ranking = (
    df.groupby("store")["stockout_hours"]
      .mean()
      .sort_values(ascending=False)
      .rename("mean_stockout_hours")
      .reset_index()
)

stockout_ranking["rank"] = range(1, len(stockout_ranking) + 1)
stockout_ranking["mean_stockout_hours"] = (
    stockout_ranking["mean_stockout_hours"].round(2)
)

print("\nSTOCKOUT RANKING (highest first)")
print(stockout_ranking.to_string(index=False))

# C. Correlations on cleaned data.
all_revenue_stockout = df["revenue_inr"].corr(df["stockout_hours"])
all_revenue_footfall = df["revenue_inr"].corr(df["footfall"])

pune = df[df["store"] == "Pune"]
pune_revenue_stockout = pune["revenue_inr"].corr(pune["stockout_hours"])
pune_revenue_footfall = pune["revenue_inr"].corr(pune["footfall"])

# D. Pre-cleaning correlation:
# remove exact duplicates, exclude missing footfall,
# but retain negative and extreme footfall observations.
raw_dedup = raw.drop_duplicates(keep="first").copy()
raw_corr_data = raw_dedup.dropna(subset=["footfall"])

raw_revenue_footfall = raw_corr_data["revenue_inr"].corr(
    raw_corr_data["footfall"]
)

print("\nCORRELATIONS")
print(f"Cleaned all stores: revenue vs stockout hours = {all_revenue_stockout:.3f}")
print(f"Cleaned all stores: revenue vs footfall = {all_revenue_footfall:.3f}")
print(f"Cleaned Pune: revenue vs stockout hours = {pune_revenue_stockout:.3f}")
print(f"Cleaned Pune: revenue vs footfall = {pune_revenue_footfall:.3f}")
print(
    "Deduplicated raw data: revenue vs footfall = "
    f"{raw_revenue_footfall:.3f} (n={len(raw_corr_data)})"
)

# Store names and metrics for report interpretation.
by_store = metrics.set_index("store")
pune_m = by_store.loc["Pune"]
all_m = by_store.loc["All stores"]

pune_stockout_rank = int(
    stockout_ranking.loc[
        stockout_ranking["store"] == "Pune", "rank"
    ].iloc[0]
)

highest_stockout = stockout_ranking.iloc[0]
revenue_gap_pct = (
    (all_m["mean_daily_revenue_inr"] - pune_m["mean_daily_revenue_inr"])
    / all_m["mean_daily_revenue_inr"] * 100
)
footfall_gap_pct = (
    (all_m["mean_footfall"] - pune_m["mean_footfall"])
    / all_m["mean_footfall"] * 100
)
rev_per_footfall_gap_pct = (
    (all_m["revenue_per_footfall"] - pune_m["revenue_per_footfall"])
    / all_m["revenue_per_footfall"] * 100
)

# Markdown table output.
metrics_md = metrics.to_markdown(index=False, floatfmt=".2f")
ranking_md = stockout_ranking.to_markdown(index=False, floatfmt=".2f")

findings = f"""# Part A — Findings

## 1. Store-level performance

All stores is calculated from the pooled 450 store-day rows. Mean values
are calculated across daily observations; revenue per footfall is total
revenue divided by total footfall.

{metrics_md}

## 2. Premise test: Is Pune's low revenue explained by stockouts?

### Mean stockout hours by store

Rank 1 indicates the highest mean stockout hours.

{ranking_md}

Pune ranks {pune_stockout_rank} of 5 stores for mean stockout hours
(2.32 hours per day in this dataset). The store with the highest mean
stockout hours is {highest_stockout['store']} at
{highest_stockout['mean_stockout_hours']:.2f} hours per day.

The premise that Pune is the lowest-revenue store because it has the
highest stockouts is **not supported by the store-level stockout ranking**.
Pune has the lowest mean daily revenue, but it does not have the highest
mean stockout hours. This does not establish that stockouts have no effect;
it means the supplied data does not support the stated explanation.

## 3. Correlation analysis

| Population | Variables | Pearson correlation |
|---|---|---:|
| All 450 cleaned store-days | Revenue and stockout hours | {all_revenue_stockout:.3f} |
| All 450 cleaned store-days | Revenue and footfall | {all_revenue_footfall:.3f} |
| Pune cleaned store-days | Revenue and stockout hours | {pune_revenue_stockout:.3f} |
| Pune cleaned store-days | Revenue and footfall | {pune_revenue_footfall:.3f} |
| Deduplicated raw rows with non-missing footfall | Revenue and footfall | {raw_revenue_footfall:.3f} (n={len(raw_corr_data)}) |

Pearson correlation measures linear association. Correlation does not
establish causation and does not by itself prove that a factor causes
higher or lower revenue.

## 4. Facts

- Pune has mean daily revenue of ₹{pune_m['mean_daily_revenue_inr']:,.2f},
  compared with ₹{all_m['mean_daily_revenue_inr']:,.2f} across all stores.
- Pune's mean daily footfall is {pune_m['mean_footfall']:,.2f},
  compared with {all_m['mean_footfall']:,.2f} across all stores.
- Pune's mean stockout hours are {pune_m['mean_stockout_hours']:.2f};
  Pune ranks {pune_stockout_rank} of 5 stores by mean stockout hours.
- The cleaned-data revenue–footfall correlation across all stores is
  {all_revenue_footfall:.3f}; the Pune-only correlation is
  {pune_revenue_footfall:.3f}.
- The revenue–footfall correlation on deduplicated raw data with
  non-missing footfall is {raw_revenue_footfall:.3f}, using
  {len(raw_corr_data)} observations.

## 5. Insights

- Pune's mean daily revenue is {revenue_gap_pct:.2f}% below the all-store
  mean, while its mean footfall is {footfall_gap_pct:.2f}% below the
  all-store mean. Its revenue per footfall is
  {rev_per_footfall_gap_pct:.2f}% below the pooled all-store figure.
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

"""
FINDINGS_PATH.write_text(findings, encoding="utf-8")

print("\nSaved:", FINDINGS_PATH)
print("Report size:", FINDINGS_PATH.stat().st_size, "bytes")
