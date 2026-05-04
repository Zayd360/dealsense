"""
=============================================================
  AI COUPON FINDER — STEP 5: PREDICT NEW COUPONS
  Load trained model and classify any new coupon
=============================================================
"""

import pandas as pd
import numpy as np
import joblib
import json
import os

MODEL_PATH   = "models/random_forest_best.pkl"
ENCODER_PATH = "data/label_encoders.json"
DATA_FILE    = "data/coupons_processed.csv"

FEATURE_COLS = [
    "category_enc", "platform_enc", "discount_type_enc",
    "user_segment_enc", "season_enc", "price_tier_enc",
    "discount_value", "original_price", "savings_pct",
    "redemption_count", "user_rating", "coupon_lifetime_days",
    "absolute_savings", "redemption_rate", "days_until_expiry",
    "min_order_required", "high_demand", "high_rated",
    "is_urgent", "great_discount", "is_expired",
    "created_month", "created_quarter",
]

# ─── LOAD ─────────────────────────────────────────────────
model    = joblib.load(MODEL_PATH)
with open(ENCODER_PATH) as f:
    encoders = json.load(f)

print("=" * 65)
print("  AI COUPON FINDER — COUPON CLASSIFIER")
print("=" * 65)
print(f"  Model loaded: {MODEL_PATH}\n")

# ─── DEMO: Classify 5 sample new coupons  ─────────────────
sample_coupons = [
    {
        "description"   : "75% off Nike Shoes on Honey",
        "category"      : "Fashion",
        "platform"      : "Honey",
        "discount_type" : "Percentage",
        "user_segment"  : "Premium Member",
        "season"        : "Winter",
        "price_tier"    : "Premium",
        "discount_value": 75.0,
        "original_price": 250.0,
        "final_price"   : 62.5,
        "savings_pct"   : 75.0,
        "redemption_count": 180,
        "user_rating"   : 4.8,
        "coupon_lifetime_days": 30,
        "absolute_savings": 187.5,
        "redemption_rate" : 6.0,
        "days_until_expiry": 2,
        "min_order_required": 0.0,
        "high_demand"   : 1,
        "high_rated"    : 1,
        "is_urgent"     : 1,
        "great_discount": 1,
        "is_expired"    : 0,
        "created_month" : 1,
        "created_quarter": 1,
    },
    {
        "description"   : "5% off Pen on Office Supplies",
        "category"      : "Office Supplies",
        "platform"      : "DealPlus",
        "discount_type" : "Flat Amount",
        "user_segment"  : "All",
        "season"        : "Summer",
        "price_tier"    : "Budget",
        "discount_value": 0.50,
        "original_price": 9.99,
        "final_price"   : 9.49,
        "savings_pct"   : 5.0,
        "redemption_count": 5,
        "user_rating"   : 2.9,
        "coupon_lifetime_days": 5,
        "absolute_savings": 0.5,
        "redemption_rate" : 1.0,
        "days_until_expiry": 30,
        "min_order_required": 0.0,
        "high_demand"   : 0,
        "high_rated"    : 0,
        "is_urgent"     : 0,
        "great_discount": 0,
        "is_expired"    : 0,
        "created_month" : 7,
        "created_quarter": 3,
    },
    {
        "description"   : "40% off Electronics on Amazon (Groupon)",
        "category"      : "Electronics",
        "platform"      : "Groupon",
        "discount_type" : "Percentage",
        "user_segment"  : "New User",
        "season"        : "Fall",
        "price_tier"    : "Mid-Range",
        "discount_value": 40.0,
        "original_price": 120.0,
        "final_price"   : 72.0,
        "savings_pct"   : 40.0,
        "redemption_count": 220,
        "user_rating"   : 4.3,
        "coupon_lifetime_days": 14,
        "absolute_savings": 48.0,
        "redemption_rate" : 15.7,
        "days_until_expiry": 7,
        "min_order_required": 50.0,
        "high_demand"   : 1,
        "high_rated"    : 1,
        "is_urgent"     : 0,
        "great_discount": 1,
        "is_expired"    : 0,
        "created_month" : 10,
        "created_quarter": 4,
    },
]


def encode_coupon(coupon_dict, encs):
    """Apply label encoding to categorical fields."""
    cat_map = {
        "category"      : "category_enc",
        "platform"      : "platform_enc",
        "discount_type" : "discount_type_enc",
        "user_segment"  : "user_segment_enc",
        "season"        : "season_enc",
        "price_tier"    : "price_tier_enc",
    }
    row = coupon_dict.copy()
    for raw_col, enc_col in cat_map.items():
        val = str(row[raw_col])
        row[enc_col] = encs.get(raw_col, {}).get(val, 0)
    return row


print("  📋  Classifying Sample Coupons:\n")
print(f"  {'#':<3} {'Description':<45} {'Prediction':<18} {'Confidence'}")
print("  " + "─" * 80)

for i, coupon in enumerate(sample_coupons, 1):
    enc = encode_coupon(coupon, encoders)
    row = pd.DataFrame([{col: enc.get(col, 0) for col in FEATURE_COLS}])
    pred  = model.predict(row)[0]
    prob  = model.predict_proba(row)[0][1]
    label = "✅ GOOD DEAL" if pred == 1 else "❌ NOT WORTH IT"
    print(f"  {i:<3} {coupon['description']:<45} {label:<18} {prob:.2%}")

print("\n" + "=" * 65)
print("\n  ℹ  Usage: Add your own coupon dict to `sample_coupons`")
print("     and re-run this script to classify it instantly.")
print("\n" + "=" * 65)
