"""
STEP 8: A simple trading bot.

This joins everything together:
  Lesson 2/3 -> fetch prices         Lesson 5 -> the moving-average rule
  Lesson 7   -> place paper orders   + NEW: a log file of every decision

What the bot does, for each stock on its WATCHLIST:
  1. Download recent daily prices and work out the 50-day average
  2. Decide: close above average -> "should own it", below -> "should hold cash"
  3. Compare with what we actually own right now
  4. If they don't match, buy or sell to fix it
  5. Write the decision to data/bot_log.csv

SAFETY:
  - Paper account only (hard-coded).
  - DRY RUN by default: it only PRINTS what it would do. Add --trade to send orders.
  - It only touches stocks on its WATCHLIST. Anything else you own is left alone.
  - It skips a stock if an order for it is already waiting, so it never doubles up.

Remember Lessons 5 and 6: this rule did NOT beat buy & hold in our tests.
The point here is learning how a bot is built, not making money.

Run it with:
  python step8_bot.py           -> dry run (safe, nothing is sent)
  python step8_bot.py --trade   -> actually send the paper orders

New coding ideas in this lesson:
  - a DICTIONARY:  {"SPY": 10}  -> look things up by name, like a phone book
  - TRY / EXCEPT:  handle errors without the whole program crashing
  - APPENDING to a log file so you have a history of every run
"""

import csv
import os
import sys
from datetime import datetime, timedelta

from dotenv import load_dotenv
from alpaca.data.enums import Adjustment, DataFeed
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame
from alpaca.trading.client import TradingClient
from alpaca.trading.enums import OrderSide, QueryOrderStatus, TimeInForce
from alpaca.trading.requests import GetOrdersRequest, MarketOrderRequest

load_dotenv()

# --- Settings ------------------------------------------------------------------
# A DICTIONARY: stock symbol -> how many shares to buy when the rule says "own it".
WATCHLIST = {
    "SPY": 10,
    "QQQ": 5,  # QQQ is a fund tracking the 100 biggest Nasdaq companies
}
MA_DAYS = 50
LOG_FILE = "data/bot_log.csv"

really_trade = "--trade" in sys.argv

key, secret = os.getenv("ALPACA_API_KEY"), os.getenv("ALPACA_SECRET_KEY")
trading = TradingClient(key, secret, paper=True)  # paper only, always
data = StockHistoricalDataClient(key, secret)


def latest_signal(symbol, clock):
    """Return (last close, moving average, should_own) using finished trading days only."""
    bars = data.get_stock_bars(
        StockBarsRequest(
            symbol_or_symbols=symbol,
            timeframe=TimeFrame.Day,
            start=datetime.now() - timedelta(days=MA_DAYS * 2 + 30),  # enough days for the average
            feed=DataFeed.IEX,
            adjustment=Adjustment.ALL,  # adjust for stock splits & dividends (see Lesson 19)
        )
    )
    close = bars.df.loc[symbol]["close"]

    # While the market is open, today's bar is still changing - it isn't a real
    # "close" yet. Drop it so the bot decides on finished days only.
    # (We check the date too: right after the open, today's bar may not exist yet.)
    if clock.is_open and close.index[-1].date() == clock.timestamp.date():
        close = close.iloc[:-1]

    ma = close.rolling(MA_DAYS).mean()
    return close.iloc[-1], ma.iloc[-1], close.iloc[-1] > ma.iloc[-1]


def write_log(row):
    """Add one line to the log file (and create it with a header the first time)."""
    os.makedirs("data", exist_ok=True)
    is_new = not os.path.exists(LOG_FILE)
    with open(LOG_FILE, "a", newline="") as f:  # "a" = append, don't overwrite
        writer = csv.DictWriter(f, fieldnames=row.keys())
        if is_new:
            writer.writeheader()
        writer.writerow(row)


# --- Main program ----------------------------------------------------------------
clock = trading.get_clock()
run_time = f"{datetime.now():%Y-%m-%d %H:%M:%S}"  # one timestamp shared by this whole run
mode = "TRADE (paper)" if really_trade else "DRY RUN (nothing will be sent)"
print(f"Bot started {datetime.now():%Y-%m-%d %H:%M}  |  mode: {mode}")
print(f"Market is {'OPEN' if clock.is_open else 'CLOSED'}\n")

# What do we own right now? Turn the list into a dictionary: {"SPY": 10, ...}
owned = {p.symbol: int(float(p.qty)) for p in trading.get_all_positions()}

for symbol, shares in WATCHLIST.items():
    # TRY / EXCEPT: if one stock fails (bad symbol, network hiccup...),
    # report it and carry on with the next one instead of crashing.
    try:
        price, ma, should_own = latest_signal(symbol, clock)
        holding = owned.get(symbol, 0)  # .get(..., 0) = "0 if we don't own any"

        waiting = trading.get_orders(
            GetOrdersRequest(status=QueryOrderStatus.OPEN, symbols=[symbol])
        )

        if waiting:
            action, qty = "WAIT", 0  # an order is already pending - don't double up
        elif should_own and holding == 0:
            action, qty = "BUY", shares
        elif not should_own and holding > 0:
            action, qty = "SELL", holding
        else:
            action, qty = "HOLD", 0  # already where the rule wants us

        print(f"{symbol:<5} close ${price:.2f}  {MA_DAYS}-day avg ${ma:.2f}  "
              f"-> rule says {'OWN' if should_own else 'CASH'}, we own {holding}  =>  {action}"
              + (f" {qty}" if qty else ""))

        sent = False
        if action in ("BUY", "SELL") and really_trade:
            order = trading.submit_order(
                MarketOrderRequest(
                    symbol=symbol,
                    qty=qty,
                    side=OrderSide.BUY if action == "BUY" else OrderSide.SELL,
                    time_in_force=TimeInForce.DAY,
                )
            )
            sent = True
            print(f"      order sent, status: {order.status.value}")

        write_log({
            "time": run_time,
            "symbol": symbol,
            "close": round(price, 2),
            "ma": round(ma, 2),
            "rule": "OWN" if should_own else "CASH",
            "holding": holding,
            "action": action,
            "qty": qty,
            "sent": sent,
        })

    except Exception as error:
        print(f"{symbol:<5} ERROR: {error}")

if not really_trade:
    print("\nDry run only. Add --trade to send these as paper orders.")
print(f"Decisions saved to {LOG_FILE}")
