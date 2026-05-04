"""
=============================================================
  AI COUPON FINDER — STEP 4: MODEL TRAINING + HYPERPARAMETER TUNING
  Random Forest + XGBoost + GridSearchCV / RandomizedSearchCV
=============================================================
"""

import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import seaborn as sns
import warnings
import os
import json
import joblib
from tqdm import tqdm

from sklearn.model_selection import (
    train_test_split, GridSearchCV, RandomizedSearchCV,
    StratifiedKFold, cross_val_score
)
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.svm import SVC
from sklearn.metrics import (
    classification_report, confusion_matrix,
    roc_auc_score, roc_curve, accuracy_score,
    precision_recall_curve, average_precision_score
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from imblearn.over_sampling import SMOTE

try:
    import xgboost as xgb
    XGB_AVAILABLE = True
except ImportError:
    XGB_AVAILABLE = False
    print("⚠  XGBoost not found, skipping XGB model")

warnings.filterwarnings("ignore")
sns.set_theme(style="darkgrid", palette="husl")

DATA_FILE   = "data/coupons_processed.csv"
MODEL_DIR   = "models"
PLOT_DIR    = "plots"
RESULTS_DIR = "results"

for d in [MODEL_DIR, PLOT_DIR, RESULTS_DIR]:
    os.makedirs(d, exist_ok=True)

def save_plot(fig, name):
    path = os.path.join(PLOT_DIR, name)
    fig.savefig(path, dpi=150, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    print(f"  💾 {path}")

# ════════════════════════════════════════════════════════
# 1. PREPARE FEATURES
# ════════════════════════════════════════════════════════
print("=" * 65)
print("  AI COUPON FINDER — ML TRAINING & HYPERPARAMETER TUNING")
print("=" * 65)

df = pd.read_csv(DATA_FILE)

FEATURE_COLS = [
    # Encoded categoricals
    "category_enc", "platform_enc", "discount_type_enc",
    "user_segment_enc", "season_enc", "price_tier_enc",
    # Numerics
    "discount_value", "original_price", "savings_pct",
    "redemption_count", "user_rating", "coupon_lifetime_days",
    "absolute_savings", "redemption_rate", "days_until_expiry",
    "min_order_required", "high_demand", "high_rated",
    "is_urgent", "great_discount", "is_expired",
    "created_month", "created_quarter",
]

TARGET = "is_good_deal"

# Drop any missing feature rows
df_model = df[FEATURE_COLS + [TARGET]].dropna()
X = df_model[FEATURE_COLS].values
y = df_model[TARGET].values

print(f"\n  Features  : {len(FEATURE_COLS)}")
print(f"  Samples   : {len(X):,}")
print(f"  Class distribution:")
unique, counts = np.unique(y, return_counts=True)
for u, c in zip(unique, counts):
    print(f"    {'Good Deal' if u==1 else 'Not Good Deal'}: {c:,} ({c/len(y)*100:.1f}%)")

# ─── Train/Test Split ───────────────────────────────────
X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.2, stratify=y, random_state=42
)
print(f"\n  Train set : {len(X_train):,} | Test set: {len(X_test):,}")

# ─── Handle Class Imbalance with SMOTE ──────────────────
print("\n  Applying SMOTE to balance training set...")
sm = SMOTE(random_state=42)
X_train_sm, y_train_sm = sm.fit_resample(X_train, y_train)
print(f"  After SMOTE — {len(X_train_sm):,} training samples")

# ════════════════════════════════════════════════════════
# 2. BASELINE MODELS
# ════════════════════════════════════════════════════════
print("\n\n🔷 [2] Baseline Models (5-Fold CV)")
print("─" * 65)

cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)

baseline_models = {
    "Logistic Regression": Pipeline([
        ("scaler", StandardScaler()),
        ("clf",    LogisticRegression(max_iter=500, random_state=42))
    ]),
    "Random Forest (base)": RandomForestClassifier(n_estimators=100, random_state=42),
    "Gradient Boosting":    GradientBoostingClassifier(n_estimators=100, random_state=42),
}

baseline_results = {}
for name, model in baseline_models.items():
    scores = cross_val_score(model, X_train_sm, y_train_sm, cv=cv,
                             scoring="roc_auc", n_jobs=-1)
    baseline_results[name] = {"mean_auc": scores.mean(), "std_auc": scores.std()}
    print(f"  {name:<30}  AUC = {scores.mean():.4f} ± {scores.std():.4f}")

# ════════════════════════════════════════════════════════
# 3. HYPERPARAMETER TUNING — RANDOM FOREST (GridSearchCV)
# ════════════════════════════════════════════════════════
print("\n\n🔷 [3] Hyperparameter Tuning — Random Forest (GridSearchCV)")
print("─" * 65)

rf_param_grid = {
    "n_estimators"  : [100, 200, 300],
    "max_depth"     : [None, 10, 20, 30],
    "min_samples_split": [2, 5, 10],
    "max_features"  : ["sqrt", "log2"],
    "class_weight"  : ["balanced", None],
}

rf_grid = GridSearchCV(
    RandomForestClassifier(random_state=42),
    param_grid=rf_param_grid,
    cv=StratifiedKFold(n_splits=3, shuffle=True, random_state=42),
    scoring="roc_auc",
    n_jobs=-1,
    verbose=1,
    return_train_score=True
)

print("  Running GridSearchCV (this may take a minute)...")
rf_grid.fit(X_train_sm, y_train_sm)
best_rf  = rf_grid.best_estimator_
best_rf_params = rf_grid.best_params_

print(f"\n  ✅ Best RF Parameters:")
for k, v in best_rf_params.items():
    print(f"     {k:<25} = {v}")
print(f"  ✅ Best CV AUC : {rf_grid.best_score_:.4f}")

joblib.dump(best_rf, os.path.join(MODEL_DIR, "random_forest_best.pkl"))

# GridSearch CV Results
cv_results = pd.DataFrame(rf_grid.cv_results_)[
    ["param_n_estimators", "param_max_depth", "param_max_features",
     "mean_test_score", "std_test_score", "rank_test_score"]
].sort_values("rank_test_score").head(10)

print(f"\n  Top 10 GridSearch Configurations:")
print(cv_results.to_string(index=False))

# ════════════════════════════════════════════════════════
# 4. HYPERPARAMETER TUNING — XGBoost (RandomizedSearchCV)
# ════════════════════════════════════════════════════════
if XGB_AVAILABLE:
    print("\n\n🔷 [4] Hyperparameter Tuning — XGBoost (RandomizedSearchCV)")
    print("─" * 65)

    xgb_param_dist = {
        "n_estimators"      : [100, 200, 300, 400],
        "max_depth"         : [3, 5, 7, 9],
        "learning_rate"     : [0.01, 0.05, 0.1, 0.2],
        "subsample"         : [0.6, 0.7, 0.8, 0.9, 1.0],
        "colsample_bytree"  : [0.5, 0.6, 0.7, 0.8, 1.0],
        "min_child_weight"  : [1, 3, 5],
        "gamma"             : [0, 0.1, 0.2, 0.3],
        "reg_alpha"         : [0, 0.1, 0.5, 1.0],
        "reg_lambda"        : [0.5, 1.0, 1.5, 2.0],
    }

    xgb_rscv = RandomizedSearchCV(
        xgb.XGBClassifier(random_state=42, eval_metric="logloss", verbosity=0),
        param_distributions=xgb_param_dist,
        n_iter=40,
        cv=StratifiedKFold(n_splits=3, shuffle=True, random_state=42),
        scoring="roc_auc",
        n_jobs=-1,
        random_state=42,
        verbose=1
    )

    print("  Running RandomizedSearchCV for XGBoost (40 iterations)...")
    xgb_rscv.fit(X_train_sm, y_train_sm)
    best_xgb = xgb_rscv.best_estimator_

    print(f"\n  ✅ Best XGBoost Parameters:")
    for k, v in xgb_rscv.best_params_.items():
        print(f"     {k:<25} = {v}")
    print(f"  ✅ Best CV AUC : {xgb_rscv.best_score_:.4f}")

    joblib.dump(best_xgb, os.path.join(MODEL_DIR, "xgboost_best.pkl"))

# ════════════════════════════════════════════════════════
# 5. EVALUATE BEST MODELS ON TEST SET
# ════════════════════════════════════════════════════════
print("\n\n🔷 [5] Final Evaluation on Test Set")
print("─" * 65)

models_eval = {"Random Forest (tuned)": best_rf}
if XGB_AVAILABLE:
    models_eval["XGBoost (tuned)"] = best_xgb

all_metrics = {}
fig_roc, ax_roc = plt.subplots(figsize=(9, 7), facecolor="#0f0f1a")
ax_roc.set_facecolor("#1a1a2e")
roc_colors = ["#3498db", "#e67e22", "#2ecc71", "#9b59b6"]

for idx, (name, model) in enumerate(models_eval.items()):
    y_pred      = model.predict(X_test)
    y_prob      = model.predict_proba(X_test)[:, 1]
    acc         = accuracy_score(y_test, y_pred)
    auc         = roc_auc_score(y_test, y_prob)
    ap          = average_precision_score(y_test, y_prob)

    all_metrics[name] = {
        "Accuracy": round(acc, 4),
        "ROC AUC" : round(auc, 4),
        "Avg Precision": round(ap, 4),
    }

    print(f"\n  ── {name} ──")
    print(f"    Accuracy     : {acc:.4f}")
    print(f"    ROC AUC      : {auc:.4f}")
    print(f"    Avg Precision: {ap:.4f}")
    print(f"\n    Classification Report:")
    print(classification_report(y_test, y_pred,
                                target_names=["Not Good Deal", "Good Deal"],
                                digits=4))

    # ROC curve
    fpr, tpr, _ = roc_curve(y_test, y_prob)
    ax_roc.plot(fpr, tpr, color=roc_colors[idx], lw=2,
                label=f"{name} (AUC={auc:.3f})")

    # Confusion Matrix
    cm    = confusion_matrix(y_test, y_pred)
    fig_cm, ax_cm = plt.subplots(figsize=(7, 5), facecolor="#0f0f1a")
    ax_cm.set_facecolor("#1a1a2e")
    sns.heatmap(cm, annot=True, fmt="d", cmap="Blues", ax=ax_cm,
                xticklabels=["Not Good", "Good"],
                yticklabels=["Not Good", "Good"],
                annot_kws={"size": 14})
    ax_cm.set_title(f"Confusion Matrix — {name}", color="white", fontsize=12)
    ax_cm.tick_params(colors="white")
    ax_cm.set_xlabel("Predicted", color="white")
    ax_cm.set_ylabel("Actual", color="white")
    save_plot(fig_cm, f"cm_{name.replace(' ', '_').replace('(', '').replace(')', '')}.png")

ax_roc.plot([0, 1], [0, 1], "w--", lw=1, label="Random Baseline")
ax_roc.set_xlim([0, 1]); ax_roc.set_ylim([0, 1.02])
ax_roc.set_title("ROC Curves — All Models", color="white", fontsize=14)
ax_roc.set_xlabel("False Positive Rate", color="white")
ax_roc.set_ylabel("True Positive Rate", color="white")
ax_roc.tick_params(colors="white")
ax_roc.legend(facecolor="#1a1a2e", labelcolor="white")
for spine in ax_roc.spines.values(): spine.set_edgecolor("#444")
save_plot(fig_roc, "13_roc_curves.png")

# ════════════════════════════════════════════════════════
# 6. FEATURE IMPORTANCE (Random Forest)
# ════════════════════════════════════════════════════════
print("\n\n🔷 [6] Feature Importance — Random Forest")
print("─" * 65)

fi = pd.DataFrame({
    "Feature"   : FEATURE_COLS,
    "Importance": best_rf.feature_importances_
}).sort_values("Importance", ascending=False)

print(fi.head(15).to_string(index=False))

fig, ax = plt.subplots(figsize=(10, 8), facecolor="#0f0f1a")
ax.set_facecolor("#1a1a2e")
sns.barplot(data=fi.head(15), x="Importance", y="Feature",
            palette="viridis", ax=ax)
ax.set_title("Top 15 Feature Importances (RF)", color="white", fontsize=14)
ax.set_xlabel("Importance Score", color="white")
ax.set_ylabel("Feature", color="white")
ax.tick_params(colors="white")
for spine in ax.spines.values(): spine.set_edgecolor("#444")
save_plot(fig, "14_feature_importance_rf.png")

# ════════════════════════════════════════════════════════
# 7. LEARNING CURVES
# ════════════════════════════════════════════════════════
print("\n\n🔷 [7] Learning Curves — Random Forest")
print("─" * 65)
from sklearn.model_selection import learning_curve

train_sizes, train_scores, val_scores = learning_curve(
    best_rf, X_train_sm, y_train_sm,
    cv=3, scoring="roc_auc", n_jobs=-1,
    train_sizes=np.linspace(0.1, 1.0, 8), random_state=42
)

fig, ax = plt.subplots(figsize=(10, 5), facecolor="#0f0f1a")
ax.set_facecolor("#1a1a2e")
ax.plot(train_sizes, train_scores.mean(axis=1), "o-", color="#3498db", label="Train Score")
ax.fill_between(train_sizes,
                train_scores.mean(axis=1) - train_scores.std(axis=1),
                train_scores.mean(axis=1) + train_scores.std(axis=1), alpha=0.2, color="#3498db")
ax.plot(train_sizes, val_scores.mean(axis=1), "o-", color="#e74c3c", label="Val Score")
ax.fill_between(train_sizes,
                val_scores.mean(axis=1) - val_scores.std(axis=1),
                val_scores.mean(axis=1) + val_scores.std(axis=1), alpha=0.2, color="#e74c3c")
ax.set_title("Learning Curves — Random Forest", color="white", fontsize=14)
ax.set_xlabel("Training Set Size", color="white")
ax.set_ylabel("ROC AUC", color="white")
ax.tick_params(colors="white")
ax.legend(facecolor="#1a1a2e", labelcolor="white")
for spine in ax.spines.values(): spine.set_edgecolor("#444")
save_plot(fig, "15_learning_curves.png")

# ════════════════════════════════════════════════════════
# 8. SAVE RESULTS
# ════════════════════════════════════════════════════════
with open(os.path.join(RESULTS_DIR, "model_metrics.json"), "w") as f:
    json.dump(all_metrics, f, indent=2)

fi.to_csv(os.path.join(RESULTS_DIR, "feature_importance.csv"), index=False)

print("\n\n✅  Training Complete!")
print(f"  Models saved   → ./{MODEL_DIR}/")
print(f"  Plots saved    → ./{PLOT_DIR}/")
print(f"  Results saved  → ./{RESULTS_DIR}/")
print("=" * 65)
