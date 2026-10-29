import pandas as pd
from pathlib import Path

# Paths
RAW_PATH = Path("data/store_daily.csv")
CLEAN_PATH = Path("data/store_daily_clean.csv")
LOG_PATH = Path("analysis/cleaning_log.csv")

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
        capped_value = round(capped_value + 1e-12, 2)

        log_records.append({
            "store": store,
            "date": df.at[idx, "date"],
            "old_footfall": old_value,
            "new_footfall": capped_value,
            "rule": "iqr_cap",
        })

        df.at[idx, "footfall"] = capped_value

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
print("\nCleaning log counts:")
print(log_df["rule"].value_counts().to_string())
print("\nSaved:", CLEAN_PATH)
print("Saved:", LOG_PATH)
