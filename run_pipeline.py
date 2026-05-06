"""
=============================================================
  AI COUPON FINDER — RUN ALL PIPELINE STEPS IN SEQUENCE
=============================================================
"""
import subprocess
import sys
import time
import os

if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

STEPS = [
    ("1_data_collection.py",   "Data Collection (5,000 coupon records)"),
    ("2_feature_engineering.py","Feature Engineering (head/describe/info/isnull/encoding/scaling)"),
    ("3_eda_analysis.py",       "EDA — Matplotlib & Seaborn (12 plots)"),
    ("4_model_training.py",     "Hyperparameter Tuning + Model Training"),
    ("5_predict.py",            "Inference — Classify New Coupons"),
]

print("=" * 65)
print("  AI COUPON FINDER — FULL PIPELINE RUNNER")
print("=" * 65)

for i, (script, description) in enumerate(STEPS, 1):
    print(f"\n[{i}/{len(STEPS)}] ▶  {description}")
    print("─" * 65)
    t0 = time.time()
    result = subprocess.run(
        [sys.executable, script],
        capture_output=False
    )
    elapsed = time.time() - t0
    if result.returncode == 0:
        print(f"\n  ✅ Done in {elapsed:.1f}s")
    else:
        print(f"\n  ❌ FAILED (exit code {result.returncode})")
        sys.exit(1)

print("\n" + "=" * 65)
print("  🎉  All pipeline steps completed successfully!")
print("  📁  Output directories:")
print("       data/    → raw + processed datasets")
print("       plots/   → 15 EDA + model evaluation plots")
print("       models/  → trained model .pkl files")
print("       results/ → metrics JSON + feature importances CSV")
print("=" * 65)
