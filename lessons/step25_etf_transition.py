"""
STEP 25: Plan a gradual move from single stocks into ETFs.

You decide the settings below; the script works out the mechanics:
  1. The order list: how much of each stock to sell, and of each ETF to buy, every month
  2. What it costs in order fees - and how that changes with fewer, bigger steps
  3. How the portfolio's risk changes along the way (using the past year of prices)
It saves the plan to data/etf_transition_plan.csv (private: data/ is never uploaded).

It's a CALCULATOR, not advice: it doesn't say whether, what or when to sell - you do.
Nothing is bought or sold; you place the orders yourself on your platform.

Run it with:   python lessons/step25_etf_transition.py

New coding ideas in this lesson:
  - SETTINGS AT THE TOP: values you're meant to change, kept apart from the logic
  - SIMULATING A PATH: building month-by-month snapshots from a starting point
  - a TWIN AXIS chart: two different units (euros and %) on one chart
"""

import os

import matplotlib.pyplot as plt
import pandas as pd

from lab.portfolio import ETFS, returns_with_history, simulate, transition_plan

# ===================== YOUR SETTINGS - change these to match YOUR decisions =====================
MONTHS = 12           # how many monthly steps to spread the move over
ETF_SPLIT = None      # None = split like your current ETFs; or e.g. {"URTH": 70, "SPY": 30}
KEEP = []             # stocks you decide NOT to sell, e.g. ["JNJ"]
FEE_PER_ORDER = 1.00  # what YOUR platform charges per order, in € (check your price list)
PORTFOLIO_FILE = "my_portfolio.csv"
# ===================================================================================================

if not os.path.exists(PORTFOLIO_FILE):
    raise SystemExit(f"{PORTFOLIO_FILE} not found - see my_portfolio.example.csv")
holdings = pd.read_csv(PORTFOLIO_FILE).set_index("symbol")
values = holdings["value_eur"]
total = values.sum()

etfs_now = [s for s in values.index if s in ETFS]
split = ETF_SPLIT or values[etfs_now].to_dict()  # default: same proportions as today
to_sell = [s for s in values.index if s not in ETFS and s not in KEEP]
if not to_sell:
    raise SystemExit("Nothing to move: every holding is an ETF or on the KEEP list.")
split_pct = pd.Series(split, dtype=float) / sum(split.values()) * 100

plan = transition_plan(values, split, MONTHS, keep=KEEP)
monthly = (plan.iloc[1] - plan.iloc[0]).round(2)  # every month's trades are the same size

print(f"Portfolio €{total:,.2f}: stocks €{values.drop(etfs_now).sum():,.2f}, "
      f"ETFs €{values[etfs_now].sum():,.2f}")
print(f"Settings: {MONTHS} monthly steps · ETF split "
      + ", ".join(f"{s} {p:.0f}%" for s, p in split_pct.items())
      + f" · keep {KEEP or 'nothing'} · €{FEE_PER_ORDER:.2f} per order\n")

# --- 1. The order list --------------------------------------------------------------------
print("1. EVERY MONTH (in today's money):")
for s in to_sell:
    print(f"   sell  €{-monthly[s]:>7.2f}  {s:<6} {holdings.loc[s, 'name']}")
for s in split_pct.index:
    name = holdings.loc[s, "name"] if s in holdings.index else "(new ETF)"
    print(f"   buy   €{monthly[s]:>7.2f}  {s:<6} {name}")
print(f"   -> moves €{-monthly[to_sell].sum():,.2f} a month, €{values[to_sell].sum():,.2f} in total")

# --- 2. Order fees for different numbers of steps -------------------------------------------
orders_per_step = len(to_sell) + len(split_pct)
print(f"\n2. ORDER FEES ({len(to_sell)} sells + {len(split_pct)} buys = {orders_per_step} orders per step):")
for steps in sorted({1, 4, MONTHS}):
    fees = steps * orders_per_step * FEE_PER_ORDER
    print(f"   {steps:>2} step(s): {steps * orders_per_step:>4} orders  ->  €{fees:>7.2f}  "
          f"({fees / total:.1%} of the portfolio){'   <- your setting' if steps == MONTHS else ''}")

# --- 3. Risk along the way ---------------------------------------------------------------------
print("\n3. RISK ALONG THE WAY (if each month's mix had been held over the past year):")
returns, left_out = returns_with_history(plan.columns)
if left_out:
    print(f"   (left out of the risk maths - too little price history: {', '.join(left_out)})")
checkpoints = sorted({0, MONTHS // 4, MONTHS // 2, 3 * MONTHS // 4, MONTHS})
path = []
for m in checkpoints:
    mix = plan.loc[m].drop(left_out)
    result = simulate(returns, mix[mix > 0])
    stocks_share = plan.loc[m].drop(etfs_now + [s for s in split_pct.index if s not in etfs_now],
                                    errors="ignore").sum() / total
    path.append({"month": m, "stocks_%": stocks_share * 100, "volatility_%": result["volatility_%"],
                 "biggest_drop_%": result["biggest_drop_%"]})
    print(f"   month {m:>2}: stocks {stocks_share:>5.1%}  ETFs {1 - stocks_share:>5.1%}  "
          f"volatility {result['volatility_%']:5.1f}%  biggest drop {result['biggest_drop_%']:6.1f}%")
path = pd.DataFrame(path).set_index("month")

print("""
Things to check before acting (they depend on YOUR situation):
  - TAX: selling at a profit can be taxed. Many countries have a yearly tax-free amount
    (e.g. Germany's Sparerpauschbetrag) - spreading sales across calendar years can matter.
  - YOUR ETFs: in the EU you usually hold UCITS versions (e.g. an iShares Core MSCI World
    UCITS ETF) rather than US-listed SPY/URTH. This script uses the US ones for price data.
  - Prices will move between steps, so each month's real amounts will differ a little.""")

os.makedirs("data", exist_ok=True)
plan.round(2).to_csv("data/etf_transition_plan.csv")
print("\nSaved the month-by-month plan to data/etf_transition_plan.csv")

# --- Chart -----------------------------------------------------------------------------------------
stocks_value = plan[[c for c in plan.columns if c not in ETFS]].sum(axis=1)
etf_value = plan[[c for c in plan.columns if c in ETFS]].sum(axis=1)
fig, ax = plt.subplots(figsize=(10, 5))
ax.stackplot(plan.index, stocks_value, etf_value, labels=["Single stocks", "ETFs"], alpha=0.8)
ax.set_xlabel("Month")
ax.set_ylabel("€ (in today's money)")
ax.legend(loc="upper left")
risk_ax = ax.twinx()  # a second y-axis on the right, for a different unit (%)
risk_ax.plot(path.index, path["volatility_%"], color="black", marker="o", label="Volatility (%)")
risk_ax.set_ylabel("Volatility (%)")
risk_ax.set_ylim(bottom=0)
risk_ax.legend(loc="upper right")
ax.set_title(f"Moving from stocks to ETFs over {MONTHS} months")
plt.tight_layout()
plt.savefig("data/etf_transition.png")
print("Saved chart to data/etf_transition.png")
