"""
STEP 19: Diversification - "don't put all your eggs in one basket".

Part 1: build thousands of random portfolios of 1, 2, 5, 10 and 20 stocks
        and measure how bumpy each one was. Does owning more stocks smooth the ride?
Part 2: CORRELATION between stocks. Diversification only helps if the stocks
        don't all move together - so which ones do?

Everything uses an EQUAL-WEIGHT portfolio: the same amount of money in each stock.

Run it with:   python lessons/step19_diversification.py

New coding ideas in this lesson:
  - ANNUALISING: turning a daily number into a yearly one (x sqrt(252) for volatility)
  - RANDOM SAMPLING of combinations (Lesson 16's simulation idea again)
  - a CORRELATION MATRIX: every stock compared with every other, shown as a HEATMAP
"""

import os

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from lab.helpers import annual_volatility, biggest_drop, daily_closes, portfolio_returns

# 22 big US companies from different industries (SECTORS)
SECTORS = {
    "Tech":       ["AAPL", "MSFT", "NVDA", "AMD", "GOOGL", "META"],
    "Consumer":   ["AMZN", "TSLA", "NFLX", "WMT", "COST", "HD", "KO", "PEP"],
    "Finance":    ["JPM", "BAC", "GS"],
    "Energy":     ["XOM", "CVX"],
    "Health":     ["JNJ", "PFE"],
    "Industrial": ["CAT"],
}
symbols = [s for group in SECTORS.values() for s in group]
SIZES = [1, 2, 5, 10, 20]
SAMPLES = 2000  # random portfolios per size

print(f"Downloading 3 years of prices for {len(symbols)} stocks...")
closes = daily_closes(symbols, days=365 * 3)
returns = closes.pct_change().dropna()
print(f"  {len(returns)} trading days, {closes.index[0]:%Y-%m-%d} -> {closes.index[-1]:%Y-%m-%d}\n")

# --- Part 1: random portfolios of different sizes -----------------------------------
rng = np.random.default_rng(0)
results = []
for size in SIZES:
    for _ in range(SAMPLES):
        picks = rng.choice(symbols, size=size, replace=False)  # random stocks, no repeats
        daily = portfolio_returns(returns, picks)
        value = 100 * (1 + daily).cumprod()
        results.append({
            "stocks": size,
            "volatility_%": annual_volatility(daily),
            "biggest_drop_%": biggest_drop(value),
            "return_%": value.iloc[-1] - 100,
        })
table = pd.DataFrame(results)

summary = table.groupby("stocks").agg(
    typical_volatility=("volatility_%", "median"),
    typical_drop=("biggest_drop_%", "median"),
    worst_drop=("biggest_drop_%", "min"),
    typical_return=("return_%", "median"),
    worst_return=("return_%", "min"),
)
print(f"Part 1 - {SAMPLES:,} random portfolios per size (3 years, equal weight)\n")
print(f"{'Stocks':>6} {'Volatility':>11} {'Typical drop':>13} {'Worst drop':>11} "
      f"{'Typical return':>15} {'Worst return':>13}")
for n, r in summary.iterrows():
    print(f"{n:>6} {r['typical_volatility']:>10.1f}% {r['typical_drop']:>12.1f}% "
          f"{r['worst_drop']:>10.1f}% {r['typical_return']:>+14.0f}% {r['worst_return']:>+12.0f}%")

one, twenty = summary.loc[1], summary.loc[20]
print(f"\nGoing from 1 to 20 stocks cut the typical volatility by "
      f"{(1 - twenty['typical_volatility'] / one['typical_volatility']):.0%}, "
      f"and the worst outcome went from {one['worst_return']:+.0f}% to {twenty['worst_return']:+.0f}%.")

# --- Part 2: which stocks move together? --------------------------------------------
corr = returns.corr()  # every stock vs every other stock: -1 to +1
pairs = corr.where(np.triu(np.ones(corr.shape, dtype=bool), k=1)).stack().dropna()  # each pair once
print("\nPart 2 - correlation of daily returns (1 = always move together, 0 = unrelated)")
print("  Most alike:  " + ", ".join(f"{a}/{b} {c:.2f}" for (a, b), c in pairs.nlargest(4).items()))
print("  Least alike: " + ", ".join(f"{a}/{b} {c:.2f}" for (a, b), c in pairs.nsmallest(4).items()))

sector_of = {s: name for name, group in SECTORS.items() for s in group}
same = [c for (a, b), c in pairs.items() if sector_of[a] == sector_of[b]]
different = [c for (a, b), c in pairs.items() if sector_of[a] != sector_of[b]]
print(f"  Average: same sector {np.mean(same):.2f}, different sectors {np.mean(different):.2f}")

# A fair comparison: 5 tech stocks vs 5 stocks from 5 different sectors
tech5 = ["AAPL", "MSFT", "NVDA", "GOOGL", "META"]
mixed5 = ["AAPL", "JPM", "XOM", "JNJ", "KO"]
for name, picks in [("5 tech stocks", tech5), ("5 different sectors", mixed5)]:
    daily = portfolio_returns(returns, picks)
    print(f"  {name:<20} {', '.join(picks):<28} volatility {annual_volatility(daily):.1f}%  "
          f"biggest drop {biggest_drop(100 * (1 + daily).cumprod()):.1f}%")

# --- Charts --------------------------------------------------------------------------
fig, (left, right) = plt.subplots(1, 2, figsize=(14, 6), gridspec_kw={"width_ratios": [1, 1.2]})

left.boxplot([table.loc[table["stocks"] == n, "volatility_%"] for n in SIZES],
             tick_labels=[str(n) for n in SIZES], showfliers=False)
left.set_title("Bumpiness of random portfolios\n(box = middle half of 2,000 portfolios)")
left.set_xlabel("Number of stocks in the portfolio")
left.set_ylabel("Annual volatility (%)")
left.grid(alpha=0.3)

image = right.imshow(corr, cmap="RdYlGn_r", vmin=0, vmax=1)
right.set_xticks(range(len(symbols)), symbols, rotation=90, fontsize=8)
right.set_yticks(range(len(symbols)), symbols, fontsize=8)
right.set_title("Correlation heatmap (red = move together)")
fig.colorbar(image, ax=right, shrink=0.8)

plt.tight_layout()
os.makedirs("data", exist_ok=True)
plt.savefig("data/diversification.png")
print("\nSaved chart to data/diversification.png")
