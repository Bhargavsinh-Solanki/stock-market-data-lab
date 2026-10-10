"""
STEP 5: Your first backtest.

A BACKTEST asks: "If I had followed this rule in the past, how would I have done?"
It uses old prices only. No real (or paper) orders are placed.

Our rule (a classic called "trend following"):
  - If today's close is ABOVE its 50-day moving average -> own the stock tomorrow
  - If today's close is BELOW its 50-day moving average -> hold cash tomorrow

We compare it against the simplest strategy of all: BUY AND HOLD
(buy on day one and never touch it).

New coding ideas in this lesson:
  - IF / ELSE logic done on a whole column at once (True/False columns)
  - SHIFT: moving data one day later, so we never "peek" at the future

Run it with:   python lessons/step5_backtest.py
Other stock / window:   python lessons/step5_backtest.py TSLA 20
"""

import os
import sys
from datetime import datetime, timedelta

import matplotlib.pyplot as plt
from dotenv import load_dotenv
from alpaca.data.enums import Adjustment, DataFeed
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame

load_dotenv()

symbol = sys.argv[1].upper() if len(sys.argv) > 1 else "SPY"
ma_days = int(sys.argv[2]) if len(sys.argv) > 2 else 50
years = 3

client = StockHistoricalDataClient(
    os.getenv("ALPACA_API_KEY"),
    os.getenv("ALPACA_SECRET_KEY"),
)

bars = client.get_stock_bars(
    StockBarsRequest(
        symbol_or_symbols=symbol,
        timeframe=TimeFrame.Day,
        start=datetime.now() - timedelta(days=365 * years),
        feed=DataFeed.IEX,
        adjustment=Adjustment.ALL,  # adjust for stock splits & dividends (see Lesson 19)
    )
)
df = bars.df.loc[symbol][["close"]].copy()

# --- 1. The indicator --------------------------------------------------------
df["ma"] = df["close"].rolling(ma_days).mean()
df = df.dropna()  # the first `ma_days` days have no average yet, so skip them

# --- 2. The signal: a True/False column --------------------------------------
# For each day: is the close above the average? (True = we want to own it)
df["signal"] = df["close"] > df["ma"]

# --- 3. The position: act on TOMORROW, not today -----------------------------
# We only know today's close after the market shuts, so the earliest we can act
# is the next day. shift(1) moves every signal down one row (one day later).
# Forgetting this is the #1 beginner mistake - it's called "look-ahead bias",
# and it makes a strategy look far better than it could ever really be.
df["in_market"] = df["signal"].shift(1, fill_value=False)

# --- 4. Daily returns ---------------------------------------------------------
df["stock_return"] = df["close"].pct_change().fillna(0)
# When in the market we earn the stock's move; when in cash we earn 0.
df["strategy_return"] = df["stock_return"].where(df["in_market"], 0.0)

# --- 5. Grow $100 day by day (compounding) ------------------------------------
# (1 + r1) * (1 + r2) * ... = how much $1 grew. cumprod = "multiply as you go".
df["buy_hold_$"] = 100 * (1 + df["stock_return"]).cumprod()
df["strategy_$"] = 100 * (1 + df["strategy_return"]).cumprod()


def summary(dollars):
    """Final value and biggest drop for a column of dollar values."""
    drop = (dollars - dollars.cummax()) / dollars.cummax()
    return dollars.iloc[-1], drop.min() * 100


bh_final, bh_drop = summary(df["buy_hold_$"])
st_final, st_drop = summary(df["strategy_$"])

# How many times did we switch between stock and cash?
trades = (df["in_market"] != df["in_market"].shift(1)).sum() - 1
time_in_market = df["in_market"].mean() * 100

print(f"{symbol}, {df.index[0]:%Y-%m-%d} -> {df.index[-1]:%Y-%m-%d}, rule: close vs {ma_days}-day average\n")
print(f"{'':<22}{'Buy & hold':>12}{'MA rule':>12}")
print("-" * 46)
print(f"{'$100 became':<22}{'$' + format(bh_final, '.2f'):>12}{'$' + format(st_final, '.2f'):>12}")
print(f"{'Biggest drop':<22}{bh_drop:>11.1f}%{st_drop:>11.1f}%")
print(f"{'Time in the market':<22}{100:>11.0f}%{time_in_market:>11.0f}%")
print(f"{'Number of switches':<22}{0:>12}{trades:>12}")

# --- 6. Chart -----------------------------------------------------------------
fig, (top, bottom) = plt.subplots(2, 1, figsize=(11, 8), sharex=True)

top.plot(df.index, df["close"], label="Price", linewidth=1)
top.plot(df.index, df["ma"], label=f"{ma_days}-day average")
# Shade the days the rule was holding the stock
top.fill_between(df.index, df["close"].min(), df["close"].max(),
                 where=df["in_market"], alpha=0.12, color="green", label="Rule owns stock")
top.set_title(f"{symbol}: when the rule was in the market")
top.legend()
top.grid(alpha=0.3)

bottom.plot(df.index, df["buy_hold_$"], label="Buy & hold")
bottom.plot(df.index, df["strategy_$"], label="MA rule")
bottom.axhline(100, color="gray", linewidth=1, linestyle="--")
bottom.set_title("What $100 became")
bottom.legend()
bottom.grid(alpha=0.3)

plt.tight_layout()
os.makedirs("data", exist_ok=True)
plt.savefig(f"data/{symbol}_backtest.png")
print(f"\nSaved chart to data/{symbol}_backtest.png")
