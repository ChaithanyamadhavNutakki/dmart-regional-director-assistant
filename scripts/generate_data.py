"""Seeded generator for the three practice datasets. Standard library only.
Run from the repository root:  python scripts/generate_data.py
Writes data/store_daily.csv, data/inventory.csv and data/feedback.csv.
"""
import csv
import os
import random
from datetime import date, timedelta

SEED = 2604
os.makedirs("data", exist_ok=True)
rng = random.Random(SEED)
START = date(2026, 4, 1)
DAYS = 90  # 2026-04-01 .. 2026-06-29

# store_id, store, base_footfall, conversion, basket_inr, daily_target_inr, marketing_base_inr, stockout_mean_hours
STORES = [
    ("S01", "Mumbai",    2300, 0.52, 880, 1050000, 52000, 2.0),
    ("S02", "Pune",      1500, 0.50, 860,  900000, 41000, 2.6),
    ("S03", "Hyderabad", 2150, 0.51, 840,  950000, 47000, 3.9),
    ("S04", "Bengaluru", 2050, 0.53, 870,  950000, 49000, 2.4),
    ("S05", "Ahmedabad", 1900, 0.52, 820,  850000, 36000, 3.1),
]

# ---------- store_daily ----------
daily = []
for sid, name, base_ff, conv, basket, target, mkt_base, so_mean in STORES:
    for d in range(DAYS):
        day = START + timedelta(days=d)
        weekend = day.weekday() >= 5
        marketing = mkt_base * rng.gauss(1.0, 0.15)
        footfall = base_ff * (1.05 if weekend else 1.0) * rng.uniform(0.88, 1.12)
        footfall *= 1 + 0.15 * (marketing / mkt_base - 1)
        stockout = max(0.0, round(rng.gauss(so_mean, 1.2), 1))
        discount = round(rng.uniform(3.0, 12.0), 1)
        revenue = footfall * rng.gauss(conv, 0.02) * rng.gauss(basket, 25) * (1 - 0.012 * stockout)
        daily.append({
            "date": day.isoformat(), "store_id": sid, "store": name,
            "footfall": int(round(footfall)), "revenue_inr": round(revenue, 2),
            "daily_target_inr": target, "marketing_spend_inr": int(round(marketing)),
            "stockout_hours": stockout, "discount_pct": discount,
        })

def row(sid, day_offset):
    return next(r for r in daily
                if r["store_id"] == sid and r["date"] == (START + timedelta(days=day_offset)).isoformat())

# data-quality issues injected on purpose
for sid, off in [("S02", 11), ("S02", 46), ("S01", 29), ("S04", 70)]:
    row(sid, off)["footfall"] = ""              # 4 missing footfall values
row("S03", 20)["footfall"] = -150               # impossible negative footfall
row("S05", 55)["footfall"] = 9800               # extreme high footfall
row("S01", 8)["footfall"] = 6100                # extreme high footfall
for sid, off in [("S01", 40), ("S03", 60), ("S05", 15)]:
    daily.append(dict(row(sid, off)))           # 3 exact duplicate rows appended at the end

with open("data/store_daily.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(daily[0].keys()))
    w.writeheader()
    w.writerows(daily)

# ---------- inventory ----------
PRODUCTS = [("P01", "Amul Milk 1L"), ("P02", "Toor Dal 1kg"), ("P03", "Basmati Rice 5kg"),
            ("P04", "Sunflower Oil 1L"), ("P05", "Iodised Salt 1kg"), ("P06", "Instant Noodles 70g"),
            ("P07", "Glucose Biscuits 200g"), ("P08", "Detergent Powder 1kg")]
inventory = []
for sid, name, *_ in STORES:
    for pid, pname in PRODUCTS:
        threshold = rng.randint(60, 150)
        stock = rng.randint(20, 400)
        inventory.append({"store_id": sid, "store": name, "product_id": pid, "product": pname,
                          "stock_units": stock, "reorder_threshold": threshold})
for r in inventory:                              # make the Amul Milk answer deliberate
    if r["product_id"] == "P01":
        r["reorder_threshold"] = 100
        r["stock_units"] = {"Mumbai": 240, "Pune": 85, "Hyderabad": 40, "Bengaluru": 130, "Ahmedabad": 100}[r["store"]]
with open("data/inventory.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(inventory[0].keys()))
    w.writeheader()
    w.writerows(inventory)

# ---------- feedback ----------
THEMES = ["Stock availability", "Queue time", "Pricing", "Freshness", "Staff behaviour"]
THEME_W = {"Mumbai": [1, 4, 2, 2, 1], "Pune": [1, 2, 5, 1, 1], "Hyderabad": [6, 2, 1, 1, 1],
           "Bengaluru": [2, 2, 2, 3, 1], "Ahmedabad": [2, 3, 1, 2, 2]}
RATING_W = {"Mumbai": [1, 1, 3, 5, 4], "Pune": [1, 2, 3, 4, 3], "Hyderabad": [3, 3, 3, 3, 2],
            "Bengaluru": [1, 1, 3, 5, 4], "Ahmedabad": [1, 2, 4, 4, 3]}
feedback = []
n = 0
for sid, name, *_ in STORES:
    for _ in range(40):
        n += 1
        day = START + timedelta(days=rng.randint(0, DAYS - 1))
        rating = rng.choices([1, 2, 3, 4, 5], weights=RATING_W[name], k=1)[0]
        theme = rng.choices(THEMES, weights=THEME_W[name], k=1)[0]
        feedback.append({"feedback_id": f"F{n:03d}", "store_id": sid, "store": name,
                         "date": day.isoformat(), "rating": rating, "theme": theme})
for i in [7, 33, 58, 71, 90, 104, 120, 133, 151, 166, 178, 195]:   # 12 unrated rows
    feedback[i]["rating"] = ""
with open("data/feedback.csv", "w", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(feedback[0].keys()))
    w.writeheader()
    w.writerows(feedback)
print(len(daily), len(inventory), len(feedback))
