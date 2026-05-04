"""
=============================================================
  AI COUPON FINDER — STEP 3: EXPLORATORY DATA ANALYSIS
  Matplotlib + Seaborn visualizations
=============================================================
"""

import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("Agg")   # non-interactive backend
import matplotlib.pyplot as plt
import matplotlib.ticker as mtick
import seaborn as sns
import warnings
import os

warnings.filterwarnings("ignore")

# ─── STYLING ─────────────────────────────────────────────
sns.set_theme(style="darkgrid", palette="husl", font_scale=1.1)
PALETTE    = "coolwarm"
SAVE_DIR   = "plots"
DATA_FILE  = "data/coupons_processed.csv"
os.makedirs(SAVE_DIR, exist_ok=True)

# ─── HELPERS ─────────────────────────────────────────────

def save(fig, name):
    path = os.path.join(SAVE_DIR, name)
    fig.savefig(path, dpi=150, bbox_inches="tight", facecolor=fig.get_facecolor())
    plt.close(fig)
    print(f"  💾 Saved → {path}")

# ─── LOAD DATA ───────────────────────────────────────────
df = pd.read_csv(DATA_FILE, parse_dates=["created_date", "expiry_date"])
print("=" * 65)
print("  AI COUPON FINDER — EDA REPORT")
print("=" * 65)
print(f"  Dataset: {df.shape[0]:,} rows × {df.shape[1]} columns\n")

# ════════════════════════════════════════════════════════
# PLOT 1: Target Variable Distribution
# ════════════════════════════════════════════════════════
print("\n📊  Plot 1: Target Class Distribution")
fig, axes = plt.subplots(1, 2, figsize=(12, 5), facecolor="#0f0f1a")
fig.suptitle("AI Coupon Finder — Target Variable", fontsize=16, color="white", fontweight="bold")

counts = df["is_good_deal"].value_counts()
labels = ["Not a Good Deal", "Good Deal"]
colors = ["#e74c3c", "#2ecc71"]

axes[0].set_facecolor("#1a1a2e")
axes[0].pie(counts, labels=labels, colors=colors, autopct="%1.1f%%",
            startangle=90, textprops={"color": "white", "fontsize": 12})
axes[0].set_title("Class Split", color="white")

axes[1].set_facecolor("#1a1a2e")
sns.countplot(data=df, x="is_good_deal", palette=colors, ax=axes[1])
axes[1].set_xticklabels(labels, color="white")
axes[1].set_title("Count per Class", color="white")
axes[1].set_xlabel("Is Good Deal?", color="white")
axes[1].set_ylabel("Count", color="white")
axes[1].tick_params(colors="white")
for spine in axes[1].spines.values():
    spine.set_edgecolor("#444")

save(fig, "01_target_distribution.png")

# ════════════════════════════════════════════════════════
# PLOT 2: Discount Type vs Average Savings %
# ════════════════════════════════════════════════════════
print("📊  Plot 2: Discount Type vs Savings")
fig, ax = plt.subplots(figsize=(10, 5), facecolor="#0f0f1a")
ax.set_facecolor("#1a1a2e")
data2 = df.groupby("discount_type")["savings_pct"].mean().sort_values(ascending=False).reset_index()
bars = sns.barplot(data=data2, x="discount_type", y="savings_pct",
                   palette="viridis", ax=ax)
ax.set_title("Average Savings % by Discount Type", color="white", fontsize=14)
ax.set_xlabel("Discount Type", color="white")
ax.set_ylabel("Avg Savings %", color="white")
ax.tick_params(colors="white")
ax.yaxis.set_major_formatter(mtick.PercentFormatter())
for p in ax.patches:
    ax.annotate(f"{p.get_height():.1f}%",
                (p.get_x() + p.get_width() / 2., p.get_height()),
                ha="center", va="bottom", color="white", fontsize=11)
for spine in ax.spines.values():
    spine.set_edgecolor("#444")
save(fig, "02_discount_type_savings.png")

# ════════════════════════════════════════════════════════
# PLOT 3: Category-wise Redemption Count (Boxplot)
# ════════════════════════════════════════════════════════
print("📊  Plot 3: Redemption by Category (Boxplot)")
fig, ax = plt.subplots(figsize=(14, 6), facecolor="#0f0f1a")
ax.set_facecolor("#1a1a2e")
order = df.groupby("category")["redemption_count"].median().sort_values(ascending=False).index
sns.boxplot(data=df, x="category", y="redemption_count", order=order,
            palette="plasma", flierprops=dict(markerfacecolor="white", markersize=3), ax=ax)
ax.set_title("Redemption Count by Category", color="white", fontsize=14)
ax.set_xlabel("Category", color="white")
ax.set_ylabel("Redemption Count", color="white")
ax.tick_params(colors="white")
plt.xticks(rotation=45, ha="right")
for spine in ax.spines.values():
    spine.set_edgecolor("#444")
save(fig, "03_category_redemption_boxplot.png")

# ════════════════════════════════════════════════════════
# PLOT 4: Correlation Heatmap
# ════════════════════════════════════════════════════════
print("📊  Plot 4: Correlation Heatmap")
numeric_cols = [
    "discount_value", "original_price", "final_price", "savings_pct",
    "redemption_count", "user_rating", "coupon_lifetime_days",
    "absolute_savings", "redemption_rate", "days_until_expiry",
    "high_demand", "high_rated", "is_urgent", "great_discount",
    "is_expired", "is_good_deal"
]
corr = df[numeric_cols].corr()

fig, ax = plt.subplots(figsize=(14, 10), facecolor="#0f0f1a")
ax.set_facecolor("#1a1a2e")
mask = np.triu(np.ones_like(corr, dtype=bool))
sns.heatmap(corr, mask=mask, annot=True, fmt=".2f", cmap="coolwarm",
            linewidths=0.5, ax=ax, annot_kws={"size": 7},
            cbar_kws={"shrink": 0.8})
ax.set_title("Feature Correlation Heatmap", color="white", fontsize=14)
ax.tick_params(colors="white", labelsize=8)
save(fig, "04_correlation_heatmap.png")

# ════════════════════════════════════════════════════════
# PLOT 5: Savings % Distribution by Season (Violin)
# ════════════════════════════════════════════════════════
print("📊  Plot 5: Savings % by Season (Violin)")
fig, ax = plt.subplots(figsize=(10, 6), facecolor="#0f0f1a")
ax.set_facecolor("#1a1a2e")
sns.violinplot(data=df, x="season", y="savings_pct",
               palette=["#3498db", "#2ecc71", "#f39c12", "#e74c3c"],
               inner="quartile", ax=ax)
ax.set_title("Savings Distribution by Season", color="white", fontsize=14)
ax.set_xlabel("Season", color="white")
ax.set_ylabel("Savings %", color="white")
ax.tick_params(colors="white")
for spine in ax.spines.values():
    spine.set_edgecolor("#444")
save(fig, "05_savings_by_season_violin.png")

# ════════════════════════════════════════════════════════
# PLOT 6: Platform-wise Good Deal Rate (Heatmap pivot)
# ════════════════════════════════════════════════════════
print("📊  Plot 6: Good Deal Rate by Platform & Category")
pivot = df.pivot_table(values="is_good_deal", index="platform",
                       columns="category", aggfunc="mean").fillna(0)

fig, ax = plt.subplots(figsize=(16, 8), facecolor="#0f0f1a")
ax.set_facecolor("#1a1a2e")
sns.heatmap(pivot, cmap="YlOrRd", annot=True, fmt=".2f",
            linewidths=0.5, ax=ax, annot_kws={"size": 7})
ax.set_title("Good Deal Rate: Platform × Category", color="white", fontsize=14)
ax.tick_params(colors="white", labelsize=8)
plt.xticks(rotation=45, ha="right")
save(fig, "06_platform_category_heatmap.png")

# ════════════════════════════════════════════════════════
# PLOT 7: Discount Value Distribution (KDE + Hist)
# ════════════════════════════════════════════════════════
print("📊  Plot 7: Discount Value Distribution")
fig, axes = plt.subplots(1, 2, figsize=(14, 5), facecolor="#0f0f1a")
fig.suptitle("Discount Value Distribution", color="white", fontsize=14, fontweight="bold")

for ax_ in axes:
    ax_.set_facecolor("#1a1a2e")
    for spine in ax_.spines.values():
        spine.set_edgecolor("#444")

axes[0].tick_params(colors="white")
axes[1].tick_params(colors="white")

sns.histplot(data=df, x="discount_value", hue="is_good_deal",
             kde=True, palette=["#e74c3c", "#2ecc71"],
             element="step", ax=axes[0])
axes[0].set_title("Histogram + KDE", color="white")
axes[0].set_xlabel("Discount Value", color="white")
axes[0].set_ylabel("Count", color="white")

sns.kdeplot(data=df[df["is_good_deal"] == 0], x="discount_value",
            fill=True, color="#e74c3c", alpha=0.5, label="Not Good Deal", ax=axes[1])
sns.kdeplot(data=df[df["is_good_deal"] == 1], x="discount_value",
            fill=True, color="#2ecc71", alpha=0.5, label="Good Deal", ax=axes[1])
axes[1].set_title("KDE Comparison", color="white")
axes[1].set_xlabel("Discount Value", color="white")
axes[1].set_ylabel("Density", color="white")
axes[1].legend()
save(fig, "07_discount_distribution.png")

# ════════════════════════════════════════════════════════
# PLOT 8: Scatter — Original Price vs Savings %
# ════════════════════════════════════════════════════════
print("📊  Plot 8: Price vs Savings Scatter")
fig, ax = plt.subplots(figsize=(10, 6), facecolor="#0f0f1a")
ax.set_facecolor("#1a1a2e")
scatter = ax.scatter(
    df["original_price"], df["savings_pct"],
    c=df["is_good_deal"], cmap="RdYlGn",
    alpha=0.5, s=20, edgecolors="none"
)
cbar = fig.colorbar(scatter, ax=ax, label="Good Deal?")
cbar.ax.yaxis.label.set_color("white")
cbar.ax.tick_params(colors="white")
ax.set_title("Original Price vs Savings %", color="white", fontsize=14)
ax.set_xlabel("Original Price ($)", color="white")
ax.set_ylabel("Savings %", color="white")
ax.tick_params(colors="white")
for spine in ax.spines.values():
    spine.set_edgecolor("#444")
save(fig, "08_price_vs_savings_scatter.png")

# ════════════════════════════════════════════════════════
# PLOT 9: Pairplot (subset)
# ════════════════════════════════════════════════════════
print("📊  Plot 9: Pairplot (key features)")
pair_cols = ["discount_value", "savings_pct", "redemption_count", "user_rating", "is_good_deal"]
pair_df   = df[pair_cols].sample(1000, random_state=42)

g = sns.pairplot(pair_df, hue="is_good_deal", palette=["#e74c3c", "#2ecc71"],
                 diag_kind="kde", plot_kws={"alpha": 0.4, "s": 15})
g.fig.suptitle("Pairplot of Key Features", y=1.02, color="white", fontsize=14)
g.fig.patch.set_facecolor("#0f0f1a")
save(g.fig, "09_pairplot.png")

# ════════════════════════════════════════════════════════
# PLOT 10: Top Brands by Average Savings
# ════════════════════════════════════════════════════════
print("📊  Plot 10: Top Brands by Average Savings")
top_brands = (df.groupby("brand")["savings_pct"].mean()
                .sort_values(ascending=False).head(15).reset_index())

fig, ax = plt.subplots(figsize=(12, 6), facecolor="#0f0f1a")
ax.set_facecolor("#1a1a2e")
sns.barplot(data=top_brands, x="brand", y="savings_pct",
            palette="magma", ax=ax)
ax.set_title("Top 15 Brands by Average Savings %", color="white", fontsize=14)
ax.set_xlabel("Brand", color="white")
ax.set_ylabel("Avg Savings %", color="white")
ax.tick_params(colors="white")
plt.xticks(rotation=45, ha="right")
for p in ax.patches:
    ax.annotate(f"{p.get_height():.1f}%",
                (p.get_x() + p.get_width() / 2., p.get_height()),
                ha="center", va="bottom", color="white", fontsize=9)
for spine in ax.spines.values():
    spine.set_edgecolor("#444")
save(fig, "10_top_brands_savings.png")

# ════════════════════════════════════════════════════════
# PLOT 11: Monthly Coupon Activity + Redemption
# ════════════════════════════════════════════════════════
print("📊  Plot 11: Monthly Coupon Activity")
monthly = df.groupby("created_month").agg(
    coupon_count=("coupon_id", "count"),
    avg_redemption=("redemption_count", "mean")
).reset_index()
MONTHS = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]
monthly["month_name"] = monthly["created_month"].apply(lambda x: MONTHS[x-1])

fig, ax1 = plt.subplots(figsize=(12, 5), facecolor="#0f0f1a")
ax1.set_facecolor("#1a1a2e")
ax2 = ax1.twinx()

color1, color2 = "#3498db", "#f39c12"
ax1.bar(monthly["month_name"], monthly["coupon_count"], color=color1, alpha=0.7, label="Coupon Count")
ax2.plot(monthly["month_name"], monthly["avg_redemption"], color=color2,
         marker="o", linewidth=2, label="Avg Redemptions")

ax1.set_title("Monthly Coupon Activity & Redemptions", color="white", fontsize=14)
ax1.set_xlabel("Month", color="white"); ax1.tick_params(colors="white")
ax1.set_ylabel("Coupon Count", color=color1)
ax2.set_ylabel("Avg Redemptions", color=color2)
ax2.tick_params(colors="white")
lines1, labels1 = ax1.get_legend_handles_labels()
lines2, labels2 = ax2.get_legend_handles_labels()
ax1.legend(lines1 + lines2, labels1 + labels2, loc="upper left")
for spine in ax1.spines.values(): spine.set_edgecolor("#444")
save(fig, "11_monthly_activity.png")

# ════════════════════════════════════════════════════════
# PLOT 12: User Segment vs Good Deal (Grouped Bar)
# ════════════════════════════════════════════════════════
print("📊  Plot 12: User Segment vs Good Deal Rate")
seg_deal = (df.groupby(["user_segment", "is_good_deal"])
              .size().unstack(fill_value=0))
seg_deal.columns = ["Not Good Deal", "Good Deal"]
seg_deal["Good Deal Rate"] = (seg_deal["Good Deal"] / seg_deal.sum(axis=1) * 100).round(1)

fig, ax = plt.subplots(figsize=(10, 5), facecolor="#0f0f1a")
ax.set_facecolor("#1a1a2e")
seg_deal[["Not Good Deal", "Good Deal"]].plot(
    kind="bar", ax=ax, color=["#e74c3c", "#2ecc71"], edgecolor="none", width=0.7
)
ax.set_title("Good Deal Distribution by User Segment", color="white", fontsize=14)
ax.set_xlabel("User Segment", color="white")
ax.set_ylabel("Count", color="white")
ax.tick_params(colors="white")
plt.xticks(rotation=30, ha="right")
ax.legend(facecolor="#1a1a2e", labelcolor="white")
for spine in ax.spines.values(): spine.set_edgecolor("#444")
save(fig, "12_segment_good_deal.png")

# ─── DONE ────────────────────────────────────────────────
print(f"\n✅  All 12 EDA plots saved in → ./{SAVE_DIR}/\n")
print("=" * 65)
