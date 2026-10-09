"""
STEP 6: Trading costs and the overfitting trap.

Two lessons about why backtests often look better than reality:

  1. COSTS. Every switch between stock and cash costs a little: the gap between
     the buy and sell price (the "spread") and price movement while your order fills.
     Alpaca charges no commission, but these hidden costs are still real.

  2. OVERFITTING. If you try 40 settings and keep the best one, you've partly
     just found the one that got LUCKY on that particular stretch of history.
     The honest test: pick the best setting using OLD data only ("training"),
     then check it on NEWER data it has never seen ("testing").
     That's like studying with past exam papers and then sitting a new exam.

New coding ideas in this lesson:
  - a function with DEFAULT values:  def f(x, cost=0.001)
  - splitting data by date into "train" and "test"
  - collecting results in a list, then turning it into a table

Run it with:   python step6_overfitting.py
Other stock:   python step6_overfitting.py AAPL
"""

import os
import sys
from datetime import datetime, timedelta

import matplotlib.pyplot as plt
import pandas as pd
from dotenv import load_dotenv
from alpaca.data.enums import Adjustment, DataFeed
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame

load_dotenv()

symbol = sys.argv[1].upper() if len(sys.argv) > 1 else "SPY"
COST_PER_SWITCH = 0.001  # 0.1% lost every time we buy or sell
WINDOWS_TO_TRY = range(10, 205, 5)  # 10, 15, 20, ... 200 days

client = StockHistoricalDataClient(
    os.getenv("ALPACA_API_KEY"),
    os.getenv("ALPACA_SECRET_KEY"),
)

bars = client.get_stock_bars(
    StockBarsRequest(
        symbol_or_symbols=symbol,
        timeframe=TimeFrame.Day,
        start=datetime.now() - timedelta(days=365 * 6),  # 6 years: more history = fairer test
        feed=DataFeed.IEX,
        adjustment=Adjustment.ALL,  # adjust for stock splits & dividends (see Lesson 19)
    )
)
close = bars.df.loc[symbol]["close"]


# --- The backtest from Lesson 5, packed into a reusable FUNCTION -------------
def backtest(close, ma_days, cost=COST_PER_SWITCH):
    """Return the daily returns of the 'close above its moving average' rule."""
    ma = close.rolling(ma_days).mean()
    in_market = (close > ma).shift(1, fill_value=False)  # act tomorrow, never today
    stock_return = close.pct_change().fillna(0)

    daily = stock_return.where(in_market, 0.0)
    switched = in_market != in_market.shift(1, fill_value=False)
    return daily - switched * cost  # pay the cost on every switch day


def grow_100(daily_returns):
    """Turn daily returns into 'what $100 became' at the end."""
    return 100 * (1 + daily_returns).prod()


# --- Split history: first 2/3 = training, last 1/3 = testing ------------------
# The first 200 days are skipped so even the 200-day average is ready on day one.
usable = close.index[200:]
split_date = usable[int(len(usable) * 2 / 3)]
train = (close.index >= usable[0]) & (close.index < split_date)
test = close.index >= split_date

print(f"{symbol}: training {usable[0]:%Y-%m-%d} -> {split_date:%Y-%m-%d}, "
      f"testing {split_date:%Y-%m-%d} -> {close.index[-1]:%Y-%m-%d}")
print(f"Cost per switch: {COST_PER_SWITCH:.1%}\n")

# --- Part 1: how much do costs hurt? (one window, whole period) ---------------
whole = close.index >= usable[0]
no_cost = grow_100(backtest(close, 50, cost=0)[whole])
with_cost = grow_100(backtest(close, 50)[whole])
print("Part 1 - the 50-day rule over the whole period")
print(f"  without costs: $100 -> ${no_cost:.2f}")
print(f"  with costs   : $100 -> ${with_cost:.2f}\n")

# --- Part 2: try every window, measure on train AND test ---------------------
results = []
for days in WINDOWS_TO_TRY:
    daily = backtest(close, days)  # computed on all data; MA only looks backwards
    results.append({
        "window": days,
        "train_$": grow_100(daily[train]),
        "test_$": grow_100(daily[test]),
    })
table = pd.DataFrame(results).set_index("window")

stock_return = close.pct_change().fillna(0)
bh_train = grow_100(stock_return[train])
bh_test = grow_100(stock_return[test])

best_window = table["train_$"].idxmax()  # the setting that looked best on OLD data
best_train = table.loc[best_window, "train_$"]
best_test = table.loc[best_window, "test_$"]
test_rank = int(table["test_$"].rank(ascending=False)[best_window])

print("Part 2 - pick the best window using training data only")
print(f"  Best window on training data: {best_window} days")
print(f"  {'':<26}{'Training':>10}{'Testing':>10}")
print(f"  {'Best window ($100 ->)':<26}{best_train:>10.2f}{best_test:>10.2f}")
print(f"  {'Buy & hold ($100 ->)':<26}{bh_train:>10.2f}{bh_test:>10.2f}")
print(f"  On new data it ranked #{test_rank} of {len(table)} windows.")
beat = sum(table["test_$"] > bh_test)
print(f"  Windows that beat buy & hold in testing: {beat} of {len(table)}")

# --- Chart: each window's result on train vs test ----------------------------
fig, ax = plt.subplots(figsize=(11, 5))
ax.plot(table.index, table["train_$"], marker="o", markersize=3, label="Training period")
ax.plot(table.index, table["test_$"], marker="o", markersize=3, label="Testing period (unseen)")
ax.axhline(bh_train, color="C0", linestyle=":", label="Buy & hold, training")
ax.axhline(bh_test, color="C1", linestyle=":", label="Buy & hold, testing")
ax.axvline(best_window, color="gray", linestyle="--", linewidth=1)
ax.annotate(f"best on training: {best_window} days", (best_window, ax.get_ylim()[0]),
            textcoords="offset points", xytext=(5, 8), color="gray",
            ha="right" if best_window > 150 else "left")
ax.set_title(f"{symbol}: what $100 became for each moving-average window (after costs)")
ax.set_xlabel("Moving-average window (days)")
ax.set_ylabel("$100 became")
ax.legend()
ax.grid(alpha=0.3)
plt.tight_layout()

os.makedirs("data", exist_ok=True)
plt.savefig(f"data/{symbol}_overfitting.png")
print(f"\nSaved chart to data/{symbol}_overfitting.png")
