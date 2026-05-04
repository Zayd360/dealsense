"""
=============================================================
  AI COUPON FINDER — STEP 2: FEATURE ENGINEERING
  head, describe, info, isnull, label encoding,
  standardization, new feature creation
=============================================================
"""

import pandas as pd
import numpy as np
import json
import os
import warnings
from sklearn.preprocessing import LabelEncoder, StandardScaler, MinMaxScaler
from tabulate import tabulate

warnings.filterwarnings("ignore")

DATA_DIR    = "data"
RAW_FILE    = os.path.join(DATA_DIR, "coupons_raw.csv")
OUTPUT_FILE = os.path.join(DATA_DIR, "coupons_processed.csv")

# ════════════════════════════════════════════════════════════
# 1. LOAD DATA
# ════════════════════════════════════════════════════════════

print("=" * 65)
print("  AI COUPON FINDER — FEATURE ENGINEERING PIPELINE")
print("=" * 65)

df = pd.read_csv(RAW_FILE, parse_dates=["created_date", "expiry_date"])

# ────────────────────────────────────────────────────────────
# 2.  head()
# ────────────────────────────────────────────────────────────
print("\n\n🔷 [1] head(10) — First 10 Records")
print("─" * 65)
print(df.head(10).to_string())

# ────────────────────────────────────────────────────────────
# 3.  describe()
# ────────────────────────────────────────────────────────────
print("\n\n🔷 [2] describe() — Statistical Summary (Numeric Columns)")
print("─" * 65)
print(df.describe(include="number").T.to_string())

print("\n\n🔷 [3] describe() — Categorical Columns")
print("─" * 65)
print(df.describe(include="object").T.to_string())

# ────────────────────────────────────────────────────────────
# 4.  info()
# ────────────────────────────────────────────────────────────
print("\n\n🔷 [4] info() — DataFrame Structure")
print("─" * 65)
df.info(verbose=True, show_counts=True)

# ════════════════════════════════════════════════════════════
# 5. MISSING VALUE ANALYSIS (isnull)
# ════════════════════════════════════════════════════════════
print("\n\n🔷 [5] isnull() — Missing Value Analysis")
print("─" * 65)
null_counts  = df.isnull().sum()
null_pct     = (df.isnull().mean() * 100).round(2)
null_summary = pd.DataFrame({
    "Missing Count": null_counts,
    "Missing %"    : null_pct,
    "Data Type"    : df.dtypes
}).query("`Missing Count` > 0").sort_values("Missing %", ascending=False)

print(null_summary.to_string())

print(f"\n  ▸ Total cells    : {df.size:,}")
print(f"  ▸ Missing cells  : {df.isnull().sum().sum():,}")
print(f"  ▸ Missing overall: {df.isnull().mean().mean()*100:.2f}%")

# ────────────────────────────────────────────────────────────
# 5a. Handle Missing Values
# ────────────────────────────────────────────────────────────
print("\n\n🔷 [5a] Imputation Strategy")
print("─" * 65)

# Numeric: fill with median
df["user_rating"]      = df["user_rating"].fillna(df["user_rating"].median())
df["min_order_required"] = df["min_order_required"].fillna(0.0)

# Categorical: fill with "Unknown"
df["verified_by"] = df["verified_by"].fillna("Unknown")
df["source_url"]  = df["source_url"].fillna("N/A")

print("  ✅ user_rating      → filled with median")
print("  ✅ min_order_required → filled with 0.0 (no minimum)")
print("  ✅ verified_by      → filled with 'Unknown'")
print("  ✅ source_url       → filled with 'N/A'")
print(f"\n  Null count after imputation: {df.isnull().sum().sum()}")

# ════════════════════════════════════════════════════════════
# 6. FEATURE ENGINEERING — NEW FEATURES
# ════════════════════════════════════════════════════════════
print("\n\n🔷 [6] Feature Engineering — Derived Features")
print("─" * 65)

# Date-based features
df["coupon_lifetime_days"] = (df["expiry_date"] - df["created_date"]).dt.days
df["days_active"]          = np.where(
    df["is_expired"] == 0,
    (pd.Timestamp.now() - df["created_date"]).dt.days,
    df["coupon_lifetime_days"]
)

# Price & savings features
df["absolute_savings"]    = (df["original_price"] - df["final_price"]).round(2)
df["price_tier"]          = pd.cut(
    df["original_price"],
    bins=[0, 50, 150, 500, np.inf],
    labels=["Budget", "Mid-Range", "Premium", "Luxury"]
)

# Engagement features
df["redemption_rate"]      = (df["redemption_count"] / df["coupon_lifetime_days"].replace(0, 1)).round(3)
df["high_demand"]          = (df["redemption_count"] >= df["redemption_count"].quantile(0.75)).astype(int)

# Rating quality
df["high_rated"]           = (df["user_rating"] >= 4.0).astype(int)

# Urgency
df["is_urgent"]            = ((df["days_until_expiry"] > 0) & (df["days_until_expiry"] <= 3)).astype(int)

# Discount quality
df["great_discount"]       = (df["discount_value"] >= df["discount_value"].quantile(0.75)).astype(int)

# Month & quarter from created_date
df["created_month"]        = df["created_date"].dt.month
df["created_quarter"]      = df["created_date"].dt.quarter

new_cols = [
    "coupon_lifetime_days", "days_active", "absolute_savings",
    "price_tier", "redemption_rate", "high_demand", "high_rated",
    "is_urgent", "great_discount", "created_month", "created_quarter"
]
print(f"  ✅ Created {len(new_cols)} derived features:")
for c in new_cols:
    print(f"     ▸ {c}")

# ════════════════════════════════════════════════════════════
# 7. LABEL ENCODING
# ════════════════════════════════════════════════════════════
print("\n\n🔷 [7] Label Encoding — Categorical → Numeric")
print("─" * 65)

CAT_COLS_TO_ENCODE = [
    "category", "platform", "discount_type",
    "user_segment", "season", "price_tier"
]

label_encoders = {}
for col in CAT_COLS_TO_ENCODE:
    le = LabelEncoder()
    df[f"{col}_enc"] = le.fit_transform(df[col].astype(str))
    label_encoders[col] = dict(zip(le.classes_, le.transform(le.classes_)))
    print(f"  ✅ {col:<20} → {col}_enc  |  Classes: {list(le.classes_)[:4]}{'...' if len(le.classes_)>4 else ''}")

# Save encoding maps
os.makedirs(DATA_DIR, exist_ok=True)
with open(os.path.join(DATA_DIR, "label_encoders.json"), "w") as f:
    json.dump({k: {str(kk): int(vv) for kk, vv in v.items()} for k, v in label_encoders.items()}, f, indent=2)
print(f"\n  📄 Encoding maps saved → data/label_encoders.json")

# ════════════════════════════════════════════════════════════
# 8. STANDARDIZATION & NORMALIZATION
# ════════════════════════════════════════════════════════════
print("\n\n🔷 [8] Standardization (Z-score) & Normalization (Min-Max)")
print("─" * 65)

NUM_COLS_TO_SCALE = [
    "discount_value", "original_price", "final_price",
    "savings_pct", "redemption_count", "user_rating",
    "coupon_lifetime_days", "absolute_savings", "redemption_rate",
    "days_until_expiry", "min_order_required"
]

# StandardScaler — Z-score (mean=0, std=1)
scaler_std = StandardScaler()
scaled_std = scaler_std.fit_transform(df[NUM_COLS_TO_SCALE])
df_std = pd.DataFrame(scaled_std, columns=[f"{c}_std" for c in NUM_COLS_TO_SCALE])

# MinMaxScaler — [0, 1] range
scaler_mm  = MinMaxScaler()
scaled_mm  = scaler_mm.fit_transform(df[NUM_COLS_TO_SCALE])
df_mm  = pd.DataFrame(scaled_mm, columns=[f"{c}_norm" for c in NUM_COLS_TO_SCALE])

df = pd.concat([df.reset_index(drop=True), df_std, df_mm], axis=1)

print(f"  ✅ StandardScaler applied to {len(NUM_COLS_TO_SCALE)} features → *_std suffix")
print(f"  ✅ MinMaxScaler  applied to {len(NUM_COLS_TO_SCALE)} features → *_norm suffix")

# Quick check
print("\n  Sample — Mean & Std of StandardScaled columns:")
std_check = df[[f"{c}_std" for c in NUM_COLS_TO_SCALE[:4]]].agg(["mean", "std"]).round(4)
print(std_check.to_string())

# ════════════════════════════════════════════════════════════
# 9. DUPLICATE CHECK
# ════════════════════════════════════════════════════════════
print("\n\n🔷 [9] Duplicate Check")
print("─" * 65)
dups = df.duplicated(subset=["coupon_code"]).sum()
print(f"  Duplicate coupon codes: {dups}")
if dups > 0:
    df = df.drop_duplicates(subset=["coupon_code"])
    print(f"  ✅ Removed {dups} duplicates")

# ════════════════════════════════════════════════════════════
# 10. OUTLIER DETECTION (IQR Method)
# ════════════════════════════════════════════════════════════
print("\n\n🔷 [10] Outlier Detection (IQR Method)")
print("─" * 65)

outlier_report = []
for col in ["discount_value", "original_price", "redemption_count", "savings_pct"]:
    Q1  = df[col].quantile(0.25)
    Q3  = df[col].quantile(0.75)
    IQR = Q3 - Q1
    lower, upper = Q1 - 1.5 * IQR, Q3 + 1.5 * IQR
    n_out = ((df[col] < lower) | (df[col] > upper)).sum()
    outlier_report.append({"Feature": col, "Lower Fence": round(lower,2),
                           "Upper Fence": round(upper,2), "Outliers": n_out})

print(tabulate(outlier_report, headers="keys", tablefmt="fancy_grid"))

# ════════════════════════════════════════════════════════════
# 11. FINAL SUMMARY & SAVE
# ════════════════════════════════════════════════════════════
print("\n\n🔷 [11] Final Dataset Summary")
print("─" * 65)
print(f"  Shape          : {df.shape[0]:,} rows × {df.shape[1]} columns")
print(f"  Memory usage   : {df.memory_usage(deep=True).sum() / 1e6:.2f} MB")
print(f"  Target balance :")
print(df["is_good_deal"].value_counts().rename({0: "  Not Good Deal", 1: "  Good Deal"}).to_string())

df.to_csv(OUTPUT_FILE, index=False)
print(f"\n  ✅ Processed dataset saved → {OUTPUT_FILE}")
print("\n" + "=" * 65 + "\n")
