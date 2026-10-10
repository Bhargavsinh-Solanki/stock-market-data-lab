"""
STEP 23: Does the what-if hold up in other years?

Lesson 22's what-if used ONE year of hindsight. Here we ask two questions:

  Part 1: Your current mix vs a what-if mix (by default: Tesla's share moved into
          Coca-Cola), judged separately for every calendar year since 2021.
          Is the what-if calmer EVERY year? Does it make more money EVERY year?

  Part 2: The bigger idea, tested on 22 stocks: what carries over from one year
          to the next - a stock's RISK, or its RETURN?
          "Rank correlation" between year N and year N+1:
             near +1 -> the same stocks come out on top again (predictable)
             near  0 -> last year tells you nothing about this year

Uses past prices only. Educational - not financial advice.

Run it with:   python lessons/step23_year_by_year.py

New coding ideas in this lesson:
  - GROUPING BY YEAR: .groupby(index.year) splits days into calendar years
  - RANK CORRELATION (Spearman): compares the ORDER of things, not their exact sizes
  - a partial year (this year so far) and why it needs care
"""

import os
from datetime import datetime

import matplotlib.pyplot as plt
import pandas as pd

from lab.helpers import daily_closes
from lab.portfolio import current_weights, yearly_stats

SWAP_OUT, SWAP_IN = "TSLA", "KO"  # the what-if: move SWAP_OUT's share into SWAP_IN
START = datetime(2021, 1, 1)
STOCKS = ["AAPL", "MSFT", "NVDA", "AMD", "GOOGL", "META", "AMZN", "TSLA", "NFLX", "WMT", "COST",
          "HD", "KO", "PEP", "JPM", "BAC", "GS", "XOM", "CVX", "JNJ", "PFE", "CAT"]
this_year = datetime.now().year
days = (datetime.now() - START).days + 5


def rank_corr(a, b):
    """
    Spearman rank correlation, by hand: replace each number by its RANK
    (1st, 2nd, 3rd...), then use the normal correlation on the ranks.
    It asks "is the ORDER the same?" and ignores how far apart the numbers are.
    """
    return a.rank().corr(b.rank())


def yearly_returns(symbols):
    """Daily returns since START (the download begins a few days early, so trim those off)."""
    returns = daily_closes(symbols, days=days).pct_change().dropna()
    return returns[returns.index >= pd.Timestamp(START, tz=returns.index.tz)]


def label(year):
    return f"{year}*" if year == this_year else str(year)  # * = year not finished yet


# --- Part 1: current mix vs what-if, year by year -----------------------------------------
current = current_weights()
if current.empty:
    raise SystemExit("No stock positions in your paper account - Part 1 needs some.")

what_if = current.copy()
moved = what_if.pop(SWAP_OUT) if SWAP_OUT in what_if else 0.20
what_if[SWAP_IN] = what_if.get(SWAP_IN, 0) + moved

symbols = sorted(set(current.index) | set(what_if.index))
returns = yearly_returns(symbols)
now_stats, if_stats = yearly_stats(returns, current), yearly_stats(returns, what_if)

print(f"Part 1 - your current mix vs the what-if ({moved:.0%} moved from {SWAP_OUT} into {SWAP_IN})")
print(f"  {'Year':<6}{'Current: return':>17}{'vol':>7}{'drop':>8}   "
      f"{'What-if: return':>15}{'vol':>7}{'drop':>8}   Calmer   Made more")
calmer = richer = 0
for year in now_stats.index:
    a, b = now_stats.loc[year], if_stats.loc[year]
    calmer_now = b["volatility_%"] < a["volatility_%"]
    richer_now = b["return_%"] > a["return_%"]
    calmer += calmer_now
    richer += richer_now
    print(f"  {label(year):<6}{a['return_%']:>+16.1f}%{a['volatility_%']:>6.1f}%{a['biggest_drop_%']:>7.1f}%   "
          f"{b['return_%']:>+14.1f}%{b['volatility_%']:>6.1f}%{b['biggest_drop_%']:>7.1f}%   "
          f"{'what-if' if calmer_now else 'current':<9}{'what-if' if richer_now else 'current'}")
years = len(now_stats)
print(f"\n  The what-if was calmer in {calmer} of {years} years, and made more money in "
      f"{richer} of {years} years.  (* = {this_year} so far)")

# --- Part 2: does risk or return carry over? ------------------------------------------------
print(f"\nPart 2 - {len(STOCKS)} stocks: does last year's ranking predict this year's?")
stock_returns = yearly_returns(STOCKS)
per_stock = {s: yearly_stats(stock_returns, {s: 1}) for s in STOCKS}
vol = pd.DataFrame({s: t["volatility_%"] for s, t in per_stock.items()})  # rows = years
ret = pd.DataFrame({s: t["return_%"] for s, t in per_stock.items()})

print(f"  {'From -> to':<14}{'Volatility':>12}{'Return':>10}")
pairs = []
for y1, y2 in zip(vol.index[:-1], vol.index[1:]):
    v = rank_corr(vol.loc[y1], vol.loc[y2])  # do the SAME stocks rank as bumpiest?
    r = rank_corr(ret.loc[y1], ret.loc[y2])  # do the SAME stocks rank as best?
    pairs.append((v, r))
    print(f"  {label(y1) + ' -> ' + label(y2):<14}{v:>+12.2f}{r:>+10.2f}")
avg_v = sum(p[0] for p in pairs) / len(pairs)
avg_r = sum(p[1] for p in pairs) / len(pairs)
print(f"  {'Average':<14}{avg_v:>+12.2f}{avg_r:>+10.2f}")
print("\n  Rank correlation: +1 = same order every year, 0 = no link, -1 = order flips.")

# --- Chart --------------------------------------------------------------------------------------
fig, axes = plt.subplots(1, 3, figsize=(16, 5))

ax = axes[0]
x = range(years)
ax.bar([i - 0.2 for i in x], now_stats["volatility_%"], width=0.4, label="Current mix")
ax.bar([i + 0.2 for i in x], if_stats["volatility_%"], width=0.4, label=f"What-if ({SWAP_OUT}->{SWAP_IN})")
ax.set_xticks(list(x), [label(y) for y in now_stats.index])
ax.set_title("Part 1: volatility each year")
ax.set_ylabel("Annual volatility (%)")
ax.legend()
ax.grid(alpha=0.3, axis="y")

for ax, table, name in [(axes[1], vol, "Volatility"), (axes[2], ret, "Return")]:
    for y1, y2 in zip(table.index[:-1], table.index[1:]):
        ax.scatter(table.loc[y1], table.loc[y2], alpha=0.7, label=f"{label(y1)}->{label(y2)}")
    ax.set_xlabel(f"{name} in year N (%)")
    ax.set_ylabel(f"{name} in year N+1 (%)")
    ax.grid(alpha=0.3)
    ax.legend(fontsize=7)
axes[1].set_title(f"Part 2: risk carries over? (avg rank corr {avg_v:+.2f})")
axes[2].set_title(f"Part 2: returns carry over? (avg rank corr {avg_r:+.2f})")

plt.tight_layout()
os.makedirs("data", exist_ok=True)
plt.savefig("data/year_by_year.png")
print("\nSaved chart to data/year_by_year.png")
