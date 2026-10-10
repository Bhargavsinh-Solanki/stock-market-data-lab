"""
STEP 13: Live streaming prices.

Until now we ASKED Alpaca for prices ("what was AAPL's price?"), like sending
a letter and waiting for a reply. That's called a REQUEST.

A STREAM (websocket) is more like a phone call that stays open: we say once
"tell me about every AAPL trade", and Alpaca keeps talking, pushing each
trade to us the moment it happens, until we hang up.

This script listens for SECONDS seconds, then hangs up and prints a summary.
It only listens - it never places orders.

Run it with:   python lessons/step13_live.py
Other stocks:  python lessons/step13_live.py NVDA TSLA

Notes:
  - Only works while the US market is open (15:30-22:00 your time).
  - Free data (IEX) shows a slice of all trades, so it's quieter than the real market.
  - The free plan allows ONE stream at a time. Close other streaming scripts first.

New coding ideas in this lesson:
  - CALLBACKS: functions WE write but ALPACA calls, whenever new data arrives
  - async def / await: Python's way of waiting for many things at once
  - a TIMER that does something later (hang up after N seconds)
"""

import os
import sys
import threading
from datetime import datetime

import pandas as pd

from lab.helpers import live_stream, trading_client

SECONDS = 60
symbols = [s.upper() for s in sys.argv[1:]] or ["SPY", "AAPL", "TSLA"]

clock = trading_client().get_clock()
if not clock.is_open:
    sys.exit(f"The market is closed, so no live trades will arrive.\n"
             f"It opens {clock.next_open:%A %d %B at %H:%M} New York time.")

trades = []  # every trade we receive gets added here


# --- CALLBACKS: Alpaca calls these for us whenever something arrives -------------
# "async def" marks a function that can wait without freezing the whole program.
async def on_trade(trade):
    trades.append({
        "time": trade.timestamp,
        "symbol": trade.symbol,
        "price": trade.price,
        "shares": trade.size,
    })
    local_time = trade.timestamp.astimezone()  # Alpaca sends UTC; show YOUR clock time
    print(f"  {local_time:%H:%M:%S.%f}"[:-3] +
          f"  {trade.symbol:<5} ${trade.price:>9.2f}  x {trade.size:g}")


async def on_bar(bar):
    # A 1-minute bar arrives just after each minute ends (Lesson 2's candles, live!)
    print(f"\n  >>> 1-minute bar {bar.symbol} {bar.timestamp.astimezone():%H:%M}: "
          f"open {bar.open:.2f}  high {bar.high:.2f}  low {bar.low:.2f}  "
          f"close {bar.close:.2f}  volume {bar.volume:g}\n")


# --- Connect, subscribe, and set a timer to hang up -------------------------------
stream = live_stream()
stream.subscribe_trades(on_trade, *symbols)
stream.subscribe_bars(on_bar, *symbols)

threading.Timer(SECONDS, stream.stop).start()  # in SECONDS seconds, hang up

print(f"Listening to {', '.join(symbols)} for {SECONDS} seconds "
      f"(started {datetime.now():%H:%M:%S}, your time). Ctrl+C to stop early.\n")
stream.run()  # blocks here, calling on_trade/on_bar, until stream.stop() runs

# --- Summary --------------------------------------------------------------------
print(f"\nHung up. Received {len(trades)} trades.\n")
if trades:
    df = pd.DataFrame(trades)
    summary = df.groupby("symbol").agg(
        trades=("price", "size"),
        shares=("shares", "sum"),
        first=("price", "first"),
        last=("price", "last"),
        low=("price", "min"),
        high=("price", "max"),
    )
    summary["change_%"] = (summary["last"] / summary["first"] - 1) * 100
    print(summary.round(3).to_string())

    os.makedirs("data", exist_ok=True)
    df.to_csv("data/live_trades.csv", index=False)
    print("\nSaved every trade to data/live_trades.csv")
