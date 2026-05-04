"""
=============================================================
  AI COUPON FINDER — STEP 1: DATA COLLECTION
  Generates a realistic, large-scale coupon dataset
  simulating real-world coupon/offer platforms.
=============================================================
"""

import pandas as pd
import numpy as np
from faker import Faker
import random
import json
import os
from datetime import datetime, timedelta
from tqdm import tqdm

fake = Faker()
np.random.seed(42)
random.seed(42)

# ─── CONSTANTS ────────────────────────────────────────────
OUTPUT_DIR   = "data"
OUTPUT_FILE  = os.path.join(OUTPUT_DIR, "coupons_raw.csv")
N_SAMPLES    = 5000   # dataset size

CATEGORIES = [
    "Electronics", "Fashion", "Grocery", "Food & Dining",
    "Travel", "Health & Beauty", "Sports", "Home & Kitchen",
    "Books", "Entertainment", "Automotive", "Pets", "Baby",
    "Office Supplies", "Toys & Games"
]

PLATFORMS = [
    "RetailMeNot", "Honey", "Coupons.com", "Groupon",
    "Rakuten", "ShopBack", "Slickdeals", "DealPlus", "PicodeMe"
]

BRANDS = [
    "Amazon", "Walmart", "Target", "BestBuy", "Nike", "Adidas",
    "Zara", "H&M", "Whole Foods", "Dominos", "Subway", "McDonald's",
    "Booking.com", "Expedia", "Sephora", "Walgreens", "Costco",
    "IKEA", "Apple", "Samsung", "Dell", "HP", "Lenovo", "Sony"
]

DISCOUNT_TYPES = ["Percentage", "Flat Amount", "Buy1Get1", "Free Shipping", "Cashback"]
SEASONS        = ["Winter", "Spring", "Summer", "Fall"]
USER_SEGMENTS  = ["Student", "Senior", "Premium Member", "New User", "Returning User", "All"]

# ─── HELPER FUNCTIONS ─────────────────────────────────────

def random_date(start_days_ago=180, end_days_future=90):
    start = datetime.now() - timedelta(days=start_days_ago)
    end   = datetime.now() + timedelta(days=end_days_future)
    delta = end - start
    return start + timedelta(days=random.randint(0, delta.days))


def is_expired(expiry_date):
    return expiry_date < datetime.now()


def compute_season(date):
    month = date.month
    if month in [12, 1, 2]:  return "Winter"
    if month in [3, 4, 5]:   return "Spring"
    if month in [6, 7, 8]:   return "Summer"
    return "Fall"


def simulate_redemption(discount_pct, category, platform, days_until_expiry):
    """Simulate redemption count based on coupon desirability."""
    base = np.random.poisson(50)
    # Higher discount → more redemptions
    base += int(discount_pct * 2)
    # Electronics & Travel get a boost
    if category in ["Electronics", "Travel", "Food & Dining"]:
        base += random.randint(20, 60)
    # Honey & RetailMeNot are popular
    if platform in ["Honey", "RetailMeNot"]:
        base += random.randint(10, 40)
    # Urgency effect
    if 0 < days_until_expiry <= 3:
        base += random.randint(30, 80)
    return max(0, base + random.randint(-10, 10))


def generate_coupon_code():
    return fake.bothify(text="????-####-????").upper()


# ─── DATASET GENERATION ───────────────────────────────────

def generate_dataset(n=N_SAMPLES):
    records = []
    print(f"\n🔄  Generating {n} coupon records...\n")

    for i in tqdm(range(n), desc="Creating coupons"):
        category      = random.choice(CATEGORIES)
        brand         = random.choice(BRANDS)
        platform      = random.choice(PLATFORMS)
        discount_type = random.choice(DISCOUNT_TYPES)
        user_segment  = random.choice(USER_SEGMENTS)

        # Discount value logic per type
        if discount_type == "Percentage":
            discount_value = round(random.uniform(5, 75), 1)
        elif discount_type == "Flat Amount":
            discount_value = round(random.uniform(2, 200), 2)
        elif discount_type == "Buy1Get1":
            discount_value = 50.0  # effectively 50% off
        elif discount_type == "Free Shipping":
            discount_value = round(random.uniform(4, 20), 2)
        else:  # Cashback
            discount_value = round(random.uniform(1, 25), 2)

        original_price = round(random.uniform(10, 1500), 2)

        if discount_type == "Percentage":
            final_price = round(original_price * (1 - discount_value / 100), 2)
        elif discount_type == "Flat Amount":
            final_price = max(0, round(original_price - discount_value, 2))
        else:
            final_price = round(original_price * 0.85, 2)

        created_date = random_date(start_days_ago=180, end_days_future=-10)
        expiry_date  = created_date + timedelta(days=random.randint(1, 120))
        days_until_expiry = (expiry_date - datetime.now()).days

        redemptions  = simulate_redemption(
            discount_value if discount_type == "Percentage" else (discount_value / original_price * 100),
            category, platform, days_until_expiry
        )

        # Introduce some real-world messiness (nulls)
        user_rating    = round(random.uniform(1, 5), 1) if random.random() > 0.12 else None
        verified_by    = fake.name()                     if random.random() > 0.20 else None
        source_url     = fake.url()                      if random.random() > 0.08 else None
        min_order_req  = round(random.uniform(0, 200), 2) if random.random() > 0.30 else None

        # Target label: Is this coupon "worth it"? (classification target)
        savings_pct    = round((original_price - final_price) / original_price * 100, 2)
        is_good_deal   = int(savings_pct >= 20 and redemptions >= 40)

        records.append({
            "coupon_id"         : f"CPN-{i+1:05d}",
            "coupon_code"       : generate_coupon_code(),
            "brand"             : brand,
            "category"          : category,
            "platform"          : platform,
            "discount_type"     : discount_type,
            "discount_value"    : discount_value,
            "original_price"    : original_price,
            "final_price"       : final_price,
            "savings_pct"       : savings_pct,
            "min_order_required": min_order_req,
            "user_segment"      : user_segment,
            "coupon_code_text"  : generate_coupon_code(),
            "created_date"      : created_date.strftime("%Y-%m-%d"),
            "expiry_date"       : expiry_date.strftime("%Y-%m-%d"),
            "days_until_expiry" : days_until_expiry,
            "is_expired"        : int(is_expired(expiry_date)),
            "season"            : compute_season(created_date),
            "redemption_count"  : redemptions,
            "user_rating"       : user_rating,
            "verified_by"       : verified_by,
            "source_url"        : source_url,
            "is_good_deal"      : is_good_deal,   # TARGET LABEL
        })

    df = pd.DataFrame(records)
    return df


# ─── MAIN ─────────────────────────────────────────────────

if __name__ == "__main__":
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    df = generate_dataset(N_SAMPLES)
    df.to_csv(OUTPUT_FILE, index=False)

    print(f"\n✅  Dataset saved → {OUTPUT_FILE}")
    print(f"    Shape : {df.shape[0]} rows × {df.shape[1]} columns")
    print(f"\n📋  First 5 rows:")
    print(df.head().to_string(index=False))
    print(f"\n📊  Good Deal distribution:")
    print(df["is_good_deal"].value_counts().rename({0:"Not a Good Deal", 1:"Good Deal"}))

    # Save column metadata
    meta = {col: str(df[col].dtype) for col in df.columns}
    with open(os.path.join(OUTPUT_DIR, "column_types.json"), "w") as f:
        json.dump(meta, f, indent=2)
    print(f"\n📄  Column metadata → data/column_types.json")
