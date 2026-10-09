"""
STEP 20: A health check for YOUR paper portfolio.

Lesson 19 showed diversification on made-up portfolios. Now we point the same
tools at what you actually own in your paper account:

  1. Where is the MONEY? (each position's share, and by sector)
  2. Where is the RISK? (a position can be 20% of the money but 40% of the risk)
  3. How diversified is it really? ("effective number of stocks")
  4. Which holdings move together? (hidden overlap)
  5. How bumpy would the last year have been, compared with just owning SPY?

READ-ONLY: it looks at your positions but never places orders.
Educational analysis of a practice account - not financial advice.

Run it with:   python step20_portfolio_check.py

New coding ideas in this lesson:
  - WEIGHTS: each position's share of the total, adding up to 1 (100%)
  - COVARIANCE: like correlation, but also counts how big the moves are
  - MATRIX MULTIPLICATION with @: combine every pair of stocks in one line
"""

import os

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from helpers import (
    annual_volatility, biggest_drop, daily_closes, effective_stocks, risk_shares,
    trading_client, weighted_returns,
)

# Alpaca doesn't tell us a company's sector, so we keep a small list ourselves.
SECTOR = {
    "AAPL": "Tech", "MSFT": "Tech", "NVDA": "Tech", "AMD": "Tech", "INTC": "Tech",
    "GOOGL": "Tech", "META": "Tech", "LITE": "Tech", "AVGO": "Tech",
    "AMZN": "Consumer", "TSLA": "Consumer", "NFLX": "Consumer", "WMT": "Consumer",
    "COST": "Consumer", "KO": "Consumer", "PEP": "Consumer", "HD": "Consumer",
    "JPM": "Finance", "BAC": "Finance", "GS": "Finance",
    "XOM": "Energy", "CVX": "Energy", "JNJ": "Health", "PFE": "Health", "CAT": "Industrial",
    "SPY": "Fund: S&P 500", "QQQ": "Fund: Nasdaq 100",
}

# --- Your positions --------------------------------------------------------------------
client = trading_client()
account = client.get_account()
positions = [p for p in client.get_all_positions() if p.asset_class.value == "us_equity"]
if not positions:
    raise SystemExit("No stock positions in your paper account yet - nothing to check.")

values = pd.Series({p.symbol: float(p.market_value) for p in positions}).sort_values(ascending=False)
weights = values / values.sum()  # each position's share of the invested money (adds up to 1)
invested, total = values.sum(), float(account.portfolio_value)
print(f"Paper account: ${total:,.0f}  ->  invested ${invested:,.0f} ({invested / total:.0%}), "
      f"cash ${total - invested:,.0f} ({1 - invested / total:.0%})")
print("Everything below is about the INVESTED part only.\n")

# --- One year of returns for each holding (+ SPY as the yardstick) ---------------------
symbols = list(weights.index) + (["SPY"] if "SPY" not in weights.index else [])
returns = daily_closes(symbols, days=365).pct_change().dropna()
portfolio = weighted_returns(returns, weights)

risk = risk_shares(returns, weights)
table = pd.DataFrame({
    "sector": [SECTOR.get(s, "Other") for s in weights.index],
    "value_$": values,
    "money_%": weights * 100,
    "risk_%": risk,
    "own_volatility_%": [annual_volatility(returns[s]) for s in weights.index],
})

print("1-2. Money vs risk, position by position (past year of prices)")
print(f"  {'':<6}{'sector':<18}{'value':>10}{'money':>8}{'risk':>8}{'its own bumpiness':>19}")
for s, r in table.iterrows():
    flag = "  <- risk > 1.5x its money" if r["risk_%"] > 1.5 * r["money_%"] else ""
    print(f"  {s:<6}{r['sector']:<18}{r['value_$']:>10,.0f}{r['money_%']:>7.1f}%{r['risk_%']:>7.1f}%"
          f"{r['own_volatility_%']:>18.1f}%{flag}")

print("\n  By sector (money):")
for sector, pct in table.groupby("sector")["money_%"].sum().sort_values(ascending=False).items():
    print(f"    {sector:<18}{pct:>6.1f}%  " + "#" * int(round(pct / 2)))

# --- 3. Effective number of stocks --------------------------------------------------------
eff = effective_stocks(weights)
print(f"\n3. You hold {len(weights)} positions, but by size they act like about "
      f"{eff:.1f} equal-sized ones.")

# --- 4. Hidden overlap: which holdings move together? -------------------------------------
corr = returns[weights.index].corr()
pairs = corr.where(np.triu(np.ones(corr.shape, dtype=bool), k=1)).stack().dropna()
close_pairs = pairs[pairs > 0.7].sort_values(ascending=False)
print("\n4. Holdings that move closely together (correlation above 0.7):")
if close_pairs.empty:
    print("   none")
for (a, b), c in close_pairs.items():
    print(f"   {a} & {b}: {c:.2f}")

# --- 5. The last year vs just owning SPY ---------------------------------------------------
spy = returns["SPY"]
print("\n5. If you'd held today's mix for the past year, rebalanced daily:")
for name, daily in [("Your mix", portfolio), ("Just SPY", spy)]:
    value = 100 * (1 + daily).cumprod()
    print(f"   {name:<9} $100 -> ${value.iloc[-1]:>6.2f}   volatility {annual_volatility(daily):5.1f}%   "
          f"biggest drop {biggest_drop(value):6.1f}%")
print("\n(Educational analysis of a practice account - not financial advice.)")

# --- Chart -----------------------------------------------------------------------------------
fig, (left, right) = plt.subplots(1, 2, figsize=(13, 5), gridspec_kw={"width_ratios": [1.2, 1]})
y = np.arange(len(table))
left.barh(y + 0.2, table["money_%"], height=0.4, label="Share of money")
left.barh(y - 0.2, table["risk_%"], height=0.4, label="Share of risk")
left.set_yticks(y, table.index)
left.invert_yaxis()
left.set_xlabel("%")
left.set_title("Money vs risk per position")
left.legend()
left.grid(alpha=0.3, axis="x")

image = right.imshow(corr, cmap="RdYlGn_r", vmin=0, vmax=1)
right.set_xticks(range(len(corr)), corr.columns, rotation=90)
right.set_yticks(range(len(corr)), corr.columns)
for i in range(len(corr)):
    for j in range(len(corr)):
        right.text(j, i, f"{corr.iat[i, j]:.2f}", ha="center", va="center", fontsize=8)
right.set_title("How your holdings move together")
fig.colorbar(image, ax=right, shrink=0.8)

plt.tight_layout()
os.makedirs("data", exist_ok=True)
plt.savefig("data/portfolio_check.png")
print("Saved chart to data/portfolio_check.png")
