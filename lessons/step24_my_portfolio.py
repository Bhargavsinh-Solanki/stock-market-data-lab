"""
STEP 24: Analyse your REAL portfolio (from a file, in euros).

Your holdings live in my_portfolio.csv - a PRIVATE file that .gitignore keeps off GitHub,
just like .env. Others can copy my_portfolio.example.csv to try the script.

  1. Profit and loss, per holding and in total (from the numbers in the file)
  2. The Lesson 20 health check: money vs risk, effective number of stocks,
     hidden overlap, sectors, and the past year vs just SPY / just MSCI World

READ-ONLY and offline from your broker: nothing is bought or sold anywhere.
Educational analysis - not financial advice.

Run it with:   python lessons/step24_my_portfolio.py
Another file:  python lessons/step24_my_portfolio.py my_portfolio.example.csv

Notes:
  - Risk maths uses US-dollar prices from Alpaca. You invest in euros, so your real
    ups and downs also include the EUR/USD exchange rate - not included here.
  - Holdings with under ~200 days of prices (e.g. a recent stock-market listing, or
    no data on the free feed) are left out of the risk maths and listed separately.

New coding ideas in this lesson:
  - keeping PRIVATE data out of git (.gitignore + an example file)
  - MONKEYPATCHING in tests: swapping a slow/online function for a fake one
  - generalising a function so it works for more than one purpose
"""

import os
import sys

import pandas as pd

from lab.portfolio import analyse

file = sys.argv[1] if len(sys.argv) > 1 else "my_portfolio.csv"
if not os.path.exists(file):
    raise SystemExit(f"{file} not found. Copy my_portfolio.example.csv to my_portfolio.csv "
                     f"and fill in your holdings.")

holdings = pd.read_csv(file).set_index("symbol")
total = holdings["value_eur"].sum()
profit = holdings["profit_eur"].sum()
cost = total - profit  # what you paid = today's value minus the profit

# --- 1. Profit and loss -----------------------------------------------------------------------
print(f"Your portfolio: €{total:,.2f}  |  profit €{profit:+,.2f} ({profit / cost:+.1%} on €{cost:,.2f} paid)\n")
print(f"  {'':<6}{'name':<22}{'value':>10}{'share':>8}{'profit':>9}{'profit %':>10}")
for s, h in holdings.iterrows():
    paid = h["value_eur"] - h["profit_eur"]
    print(f"  {s:<6}{h['name']:<22}{h['value_eur']:>9,.2f}€{h['value_eur'] / total:>7.1%}"
          f"{h['profit_eur']:>+8.0f}€{h['profit_eur'] / paid:>+9.1%}")

# --- 2. Health check -----------------------------------------------------------------------------
print("\nRunning the health check on one year of prices...")
check = analyse(holdings["value_eur"], benchmarks=("SPY", "URTH"))

if len(check.excluded):
    left_out = check.excluded.sum() / total
    print(f"  Left out of the risk maths (too little price history): "
          + ", ".join(f"{s} (€{v:,.0f})" for s, v in check.excluded.items())
          + f" = {left_out:.1%} of your money. Shares below are of the other {1 - left_out:.1%}.")

print(f"\n  {'':<6}{'sector':<18}{'money':>8}{'risk':>8}{'own bumpiness':>15}")
for s, r in check.positions.iterrows():
    flag = "  <- risk > 1.5x its money" if r["risk_%"] > 1.5 * r["money_%"] else ""
    print(f"  {s:<6}{r['sector']:<18}{r['money_%']:>7.1f}%{r['risk_%']:>7.1f}%{r['own_volatility_%']:>14.1f}%{flag}")

print("\n  By sector (money):")
for sector, pct in check.by_sector.items():
    print(f"    {sector:<18}{pct:>6.1f}%  " + "#" * int(round(pct / 2)))

print(f"\n  {len(holdings)} holdings; the analysed {len(check.positions)} act like about "
      f"{check.effective:.1f} equal-sized ones.")

print("\n  Holdings that move closely together (correlation above 0.7):")
if check.close_pairs.empty:
    print("    none")
for (a, b), c in check.close_pairs.items():
    print(f"    {a} & {b}: {c:.2f}")

print("\n  If you'd held today's mix for the past year (in US dollars, rebalanced daily):")
for name, r in check.comparison.iterrows():
    print(f"    {name:<10} 100 -> {r['$100 became']:>6.1f}   volatility {r['volatility_%']:5.1f}%   "
          f"biggest drop {r['biggest_drop_%']:6.1f}%")
print("\n(Educational analysis - not financial advice.)")
