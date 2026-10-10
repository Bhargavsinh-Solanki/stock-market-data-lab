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

Since Lesson 21, the calculations live in portfolio.py (shared with the dashboard);
this file only DISPLAYS them in the terminal.

Run it with:   python lessons/step20_portfolio_check.py

New coding ideas in this lesson:
  - WEIGHTS: each position's share of the total, adding up to 1 (100%)
  - COVARIANCE: like correlation, but also counts how big the moves are
  - MATRIX MULTIPLICATION with @: combine every pair of stocks in one line
"""

import os

import matplotlib.pyplot as plt
import numpy as np

from lab.portfolio import health_check

check = health_check()
if check is None:
    raise SystemExit("No stock positions in your paper account yet - nothing to check.")

cash = check.total - check.invested
print(f"Paper account: ${check.total:,.0f}  ->  invested ${check.invested:,.0f} "
      f"({check.invested / check.total:.0%}), cash ${cash:,.0f} ({cash / check.total:.0%})")
print("Everything below is about the INVESTED part only.\n")

print("1-2. Money vs risk, position by position (past year of prices)")
print(f"  {'':<6}{'sector':<18}{'value':>10}{'money':>8}{'risk':>8}{'its own bumpiness':>19}")
for s, r in check.positions.iterrows():
    flag = "  <- risk > 1.5x its money" if r["risk_%"] > 1.5 * r["money_%"] else ""
    print(f"  {s:<6}{r['sector']:<18}{r['value_$']:>10,.0f}{r['money_%']:>7.1f}%{r['risk_%']:>7.1f}%"
          f"{r['own_volatility_%']:>18.1f}%{flag}")

print("\n  By sector (money):")
for sector, pct in check.by_sector.items():
    print(f"    {sector:<18}{pct:>6.1f}%  " + "#" * int(round(pct / 2)))

print(f"\n3. You hold {len(check.positions)} positions, but by size they act like about "
      f"{check.effective:.1f} equal-sized ones.")

print("\n4. Holdings that move closely together (correlation above 0.7):")
if check.close_pairs.empty:
    print("   none")
for (a, b), c in check.close_pairs.items():
    print(f"   {a} & {b}: {c:.2f}")

print("\n5. If you'd held today's mix for the past year, rebalanced daily:")
for name, r in check.comparison.iterrows():
    print(f"   {name:<9} $100 -> ${r['$100 became']:>6.2f}   volatility {r['volatility_%']:5.1f}%   "
          f"biggest drop {r['biggest_drop_%']:6.1f}%")
print("\n(Educational analysis of a practice account - not financial advice.)")

# --- Chart ---------------------------------------------------------------------------------
table, corr = check.positions, check.correlations
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
