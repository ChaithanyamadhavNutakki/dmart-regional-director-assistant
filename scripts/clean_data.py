import pandas as pd
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

# Paths
RAW_PATH = Path("data/store_daily.csv")
CLEAN_PATH = Path("data/store_daily_clean.csv")
LOG_PATH = Path("analysis/cleaning_log.csv")

TWO_PLACES = Decimal("0.01")


def round_half_up(value):
    """Round a numeric value to two decimal places using Decimal."""
    return Decimal(str(value)).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


def decimal_value(value):
    """Convert a pandas/numeric value to Decimal without binary-float arithmetic."""
    return Decimal(str(value))


# Load raw data; never overwrite the source file.
df = pd.read_csv(RAW_PATH)

# 1. Remove exact duplicates, keeping the first occurrence.
df = df.drop_duplicates(keep="first").copy()

# Store every change in the cleaning log.
log_records = []

# 2. Convert negative footfall to missing.
negative_mask = df["footfall"] < 0

for idx in df.index[negative_mask]:
    log_records.append({
        "store": df.at[idx, "store"],
        "date": df.at[idx, "date"],
        "old_footfall": df.at[idx, "footfall"],
        "new_footfall": None,
        "rule": "negative_to_missing",
    })

df.loc[negative_mask, "footfall"] = float("nan")

# 3. Calculate store-level IQR bounds and cap outliers.
for store, group in df.groupby("store"):
    values = group["footfall"].dropna()

    q1 = values.quantile(0.25, interpolation="linear")
    q3 = values.quantile(0.75, interpolation="linear")
    iqr = q3 - q1

    lower = q1 - 1.5 * iqr
    upper = q3 + 1.5 * iqr

    outside = (
        df["store"].eq(store)
        & df["footfall"].notna()
        & (
            (df["footfall"] < lower)
            | (df["footfall"] > upper)
        )
    )

    for idx in df.index[outside]:
        old_value = df.at[idx, "footfall"]
        capped_value = min(max(old_value, lower), upper)
        capped_value = round_half_up(capped_value)

        log_records.append({
            "store": store,
            "date": df.at[idx, "date"],
            "old_footfall": old_value,
            "new_footfall": float(capped_value),
            "rule": "iqr_cap",
        })

        df.at[idx, "footfall"] = float(capped_value)

# 4. Impute missing footfall with the median for that store.
for store, group in df.groupby("store"):
    median_value = group["footfall"].median()
    missing = group.index[group["footfall"].isna()]

    for idx in missing:
        log_records.append({
            "store": store,
            "date": df.at[idx, "date"],
            "old_footfall": None,
            "new_footfall": median_value,
            "rule": "median_impute",
        })

        df.at[idx, "footfall"] = median_value

# 5. Add the six required Part A features after cleaning and imputation.
# All numeric features are rounded half-up to two decimal places.
df["revenue_per_footfall"] = [
    float(round_half_up(decimal_value(revenue) / decimal_value(footfall)))
    for revenue, footfall in zip(df["revenue_inr"], df["footfall"])
]

df["marketing_efficiency"] = [
    float(round_half_up(decimal_value(revenue) / decimal_value(marketing)))
    for revenue, marketing in zip(df["revenue_inr"], df["marketing_spend_inr"])
]

df["achievement_pct"] = [
    float(round_half_up(
        decimal_value(revenue) / decimal_value(target) * Decimal("100")
    ))
    for revenue, target in zip(df["revenue_inr"], df["daily_target_inr"])
]

df["shortfall_inr"] = [
    float(round_half_up(decimal_value(target) - decimal_value(revenue)))
    for revenue, target in zip(df["daily_target_inr"], df["revenue_inr"])
]

dates = pd.to_datetime(df["date"], errors="raise")
df["weekend_flag"] = dates.dt.dayofweek.isin([5, 6]).map(
    {True: "Yes", False: "No"}
)

df["performance_band"] = df["achievement_pct"].map(
    lambda achievement: (
        "Excellent" if achievement >= 100
        else "Good" if achievement >= 75
        else "Poor"
    )
)

# Keep the six derived fields in the specified order.
feature_columns = [
    "revenue_per_footfall",
    "marketing_efficiency",
    "achievement_pct",
    "shortfall_inr",
    "weekend_flag",
    "performance_band",
]
original_columns = [column for column in df.columns if column not in feature_columns]
df = df[original_columns + feature_columns]

# Save cleaned data and log.
df.to_csv(CLEAN_PATH, index=False)

log_columns = [
    "store",
    "date",
    "old_footfall",
    "new_footfall",
    "rule",
]

log_df = pd.DataFrame(log_records, columns=log_columns)
log_df.to_csv(LOG_PATH, index=False)

print("Cleaned dataset shape:", df.shape)
print("Remaining missing values:", int(df.isna().sum().sum()))
print("Negative footfall values:", int((df["footfall"] < 0).sum()))
print("\\nCleaning log counts:")
print(log_df["rule"].value_counts().to_string())
print("\\nSaved:", CLEAN_PATH)
print("Saved:", LOG_PATH)
