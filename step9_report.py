"""
STEP 9 (part 1): A daily report card for your paper account.

What it shows:
  1. Account value over the last month (Alpaca keeps this history for us)
  2. Each position and how it's doing
  3. The bot's most recent decisions (from data/bot_log.csv)
It also saves a chart: data/portfolio.png

Run it with:   python step9_report.py
Longer history: python step9_report.py 3M      (1W, 1M, 3M, 6M, 1A = one year)

New coding ideas in this lesson:
  - converting "Unix timestamps" (seconds since 1 Jan 1970) into normal dates
  - reading a CSV file back in with pandas
"""

import os
import sys
from datetime import datetime

import matplotlib.pyplot as plt
import pandas as pd
from dotenv import load_dotenv
from alpaca.trading.client import TradingClient
from alpaca.trading.requests import GetPortfolioHistoryRequest

load_dotenv()

period = sys.argv[1] if len(sys.argv) > 1 else "1M"
LOG_FILE = "data/bot_log.csv"

trading = TradingClient(os.getenv("ALPACA_API_KEY"), os.getenv("ALPACA_SECRET_KEY"), paper=True)

print(f"=== Daily report, {datetime.now():%A %d %B %Y, %H:%M} ===\n")

# --- 1. Account value over time ------------------------------------------------
history = trading.get_portfolio_history(
    GetPortfolioHistoryRequest(period=period, timeframe="1D")
)
# Alpaca sends dates as Unix timestamps (e.g. 1791504000). Convert to real dates.
equity = pd.Series(
    history.equity,
    index=pd.to_datetime(history.timestamp, unit="s"),
).dropna()
equity = equity[equity > 0]  # ignore days before the account had any money

start, end = equity.iloc[0], equity.iloc[-1]
print(f"Account value: ${end:,.2f}")
print(f"Over {period}: ${end - start:+,.2f} ({(end / start - 1) * 100:+.2f}%)")
if len(equity) > 1:
    day_change = equity.iloc[-1] - equity.iloc[-2]
    print(f"Last day:     ${day_change:+,.2f}")

# --- 2. Positions --------------------------------------------------------------
print("\nPositions:")
positions = trading.get_all_positions()
if not positions:
    print("  (none)")
for p in positions:
    pl = float(p.unrealized_pl)
    pl_pct = float(p.unrealized_plpc) * 100
    mark = "up  " if pl >= 0 else "down"
    print(f"  {p.symbol:<6} {p.qty:>4} shares  value ${float(p.market_value):>10,.2f}  "
          f"{mark} ${abs(pl):,.2f} ({pl_pct:+.1f}%)")

# --- 3. The bot's latest decisions ---------------------------------------------
print("\nBot's latest decisions:")
if os.path.exists(LOG_FILE):
    log = pd.read_csv(LOG_FILE)
    last_run = log[log["time"] == log["time"].iloc[-1]]  # rows from the newest run
    for _, row in last_run.iterrows():
        sent = "sent" if row["sent"] else "not sent"
        print(f"  {row['time']}  {row['symbol']:<5} rule={row['rule']:<4} "
              f"-> {row['action']} {row['qty'] or ''} ({sent})")
    print(f"  ({len(log)} decisions logged in total)")
else:
    print("  (no log yet - run step8_bot.py first)")

# --- Chart ----------------------------------------------------------------------
plt.figure(figsize=(10, 4))
plt.plot(equity.index, equity.values, marker="o", markersize=3)
plt.title(f"Paper account value - last {period}")
plt.ylabel("USD")
plt.grid(alpha=0.3)
plt.tight_layout()
os.makedirs("data", exist_ok=True)
plt.savefig("data/portfolio.png")
print("\nSaved chart to data/portfolio.png")
