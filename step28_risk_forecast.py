"""
STEP 28: Your first honest forecast - how bumpy will next month be?

Part 1: THE TEST. Replay 5 years of history for 25 stocks and funds, month by month.
        Each method forecasts next month's volatility using only the past; then we
        check against what really happened. Which method wins?
Part 2: THE CONTRAST. The same test for RETURNS: does last month's return predict next month's?
Part 3: THE FORECAST. Use the winning method on your holdings (my_portfolio.csv, or your
        paper account if that file doesn't exist): how big a move is "normal" next month?

A risk forecast says how much prices may SWING - not which way. It is not advice.

Run it with:   python step28_risk_forecast.py

New coding ideas in this lesson:
  - WALK-FORWARD TESTING: forecast, wait, check, repeat - only ever using the past
  - EWMA: an average where recent days count more
  - turning a volatility into everyday terms: "in about 2 months out of 3, the move stays within ±X%"
"""

import os
from datetime import datetime

import matplotlib.pyplot as plt
import pandas as pd

from helpers import daily_closes
from portfolio import current_weights
from risk_forecast import HORIZON, evaluate, forecast_holdings, forecasts, realised_next, return_forecast_check

UNIVERSE = ["AAPL", "MSFT", "NVDA", "AMD", "GOOGL", "META", "AMZN", "TSLA", "NFLX", "WMT", "COST",
            "HD", "KO", "PEP", "JPM", "BAC", "GS", "XOM", "CVX", "JNJ", "PFE", "CAT",
            "SPY", "QQQ", "URTH"]
days = (datetime.now() - datetime(2021, 1, 1)).days

# --- Part 1: which method forecasts risk best? ---------------------------------------------
print(f"Downloading ~5 years of prices for {len(UNIVERSE)} stocks and funds...")
returns = daily_closes(UNIVERSE, days=days).pct_change().dropna()
table = evaluate(returns)
best = table.index[0]

print(f"\nPart 1 - forecasting next month's volatility ({int(table['checks'].iloc[0]):,} checks per method)")
print(f"  {'Method':<12}{'Average miss':>14}{'Rank correlation':>19}")
for name, r in table.iterrows():
    print(f"  {name:<12}{r['avg_error_pts']:>11.1f} pts{r['rank_corr']:>19.2f}"
          + ("   <- best" if name == best else ""))
print("  (miss = how far the forecast was from what happened, in volatility points;"
      "\n   rank correlation = did it put the stocks in the right ORDER, from calm to bumpy?)")

# --- Part 2: the same test for returns --------------------------------------------------------
r_corr = return_forecast_check(returns)
print(f"\nPart 2 - does last month's RETURN predict next month's?  rank correlation {r_corr:+.2f}")
print(f"  Risk: {table.loc[best, 'rank_corr']:+.2f}  vs  returns: {r_corr:+.2f}  ->  "
      "risk is forecastable; returns aren't.")

# --- Part 3: forecast for your holdings ---------------------------------------------------------
if os.path.exists("my_portfolio.csv"):
    values = pd.read_csv("my_portfolio.csv").set_index("symbol")["value_eur"]
    source = "my_portfolio.csv"
else:
    values = current_weights()
    source = "your paper account"
per_holding, mix, left_out = forecast_holdings(values, method=best)

print(f"\nPart 3 - next month for {source} (method: {best}, EWMA for very new listings):")
if left_out:
    print(f"  (no forecast - too little price history: {', '.join(left_out)})")
print(f"  {'':<6}{'expected volatility':>20}{'typical month (2 in 3)':>25}{'rough bad month (1 in 20)':>28}")
for s, r in per_holding.iterrows():
    print(f"  {s:<6}{r['volatility_%']:>19.1f}%{'±' + format(r['typical_%'], '.1f') + '%':>25}"
          f"{r['bad_%']:>27.1f}%")

m = mix.iloc[0]
print(f"\n  Whole mix (EWMA): about {m['volatility_%']:.1f}% a year  ->  in about 2 months out of 3, "
      f"the month's move stays within ±{m['typical_%']:.1f}%;\n  roughly 1 month in 20 is worse than "
      f"{m['bad_%']:.1f}%. (A rough guide: real markets have more extreme days than this assumes.)")
print("\nA risk forecast says how much prices may swing, not which way. Not investment advice.")

# --- Chart: forecast vs what happened -----------------------------------------------------------
made, actual = forecasts(returns)[best], realised_next(returns)
checkpoints = returns.index[252:-HORIZON:HORIZON]
pairs = pd.DataFrame({"forecast": made.loc[checkpoints].stack(),
                      "actual": actual.loc[checkpoints].stack()}).dropna()
past = returns.rolling(HORIZON).sum().loc[checkpoints].stack() * 100
future = returns.rolling(HORIZON).sum().shift(-HORIZON).loc[checkpoints].stack() * 100
rets = pd.DataFrame({"past": past, "future": future}).dropna()

fig, (left, right) = plt.subplots(1, 2, figsize=(13, 5.5))
left.scatter(pairs["forecast"], pairs["actual"], s=8, alpha=0.4)
top = pairs.max().max()
left.plot([0, top], [0, top], color="gray", linestyle="--", label="perfect forecast")
left.set_xlabel("Forecast volatility for next month (%)")
left.set_ylabel("What actually happened (%)")
left.set_title(f"RISK: {best} method (rank corr {table.loc[best, 'rank_corr']:+.2f})")
left.legend()
left.grid(alpha=0.3)

right.scatter(rets["past"], rets["future"], s=8, alpha=0.4, color="C1")
right.axhline(0, color="gray", linewidth=1)
right.axvline(0, color="gray", linewidth=1)
right.set_xlabel("Last month's return (%)")
right.set_ylabel("Next month's return (%)")
right.set_title(f"RETURNS: last month vs next (rank corr {r_corr:+.2f})")
right.grid(alpha=0.3)

plt.tight_layout()
os.makedirs("data", exist_ok=True)
plt.savefig("data/risk_forecast.png")
print("Saved chart to data/risk_forecast.png")
