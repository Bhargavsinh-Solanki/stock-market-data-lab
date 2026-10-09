"""
STEP 4: Compare several stocks side by side.

Goal:
  (a) download 1 year of prices for several stocks in ONE request
  (b) answer: "If I had put $100 into each stock a year ago, what would it be worth now?"
  (c) measure how bumpy (risky) each stock's ride was
  (d) draw all of them on one chart

New coding ideas in this lesson:
  - a LIST:      ["AAPL", "MSFT"]  -> several items kept in order
  - a FUNCTION:  def name(...):     -> a reusable recipe you can call by name
  - a LOOP:      for x in list:     -> "do this for every item"

Run it with:   python step4_compare.py
Pick your own: python step4_compare.py NVDA AMZN GOOGL
"""

import os
import sys
from datetime import datetime, timedelta

import matplotlib.pyplot as plt
from dotenv import load_dotenv
from alpaca.data.enums import DataFeed
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame

load_dotenv()

# A LIST of stocks. Use the ones typed after the command, otherwise these four.
symbols = [s.upper() for s in sys.argv[1:]] or ["AAPL", "MSFT", "TSLA", "SPY"]
# SPY isn't a company - it's a fund that tracks the 500 biggest US companies.
# It's our "benchmark": did each stock beat the market as a whole?

client = StockHistoricalDataClient(
    os.getenv("ALPACA_API_KEY"),
    os.getenv("ALPACA_SECRET_KEY"),
)

# --- (a) One request for all the stocks -------------------------------------
bars = client.get_stock_bars(
    StockBarsRequest(
        symbol_or_symbols=symbols,  # we can pass a whole list at once
        timeframe=TimeFrame.Day,
        start=datetime.now() - timedelta(days=365),
        feed=DataFeed.IEX,
    )
)

# "Pivot" the table: one row per date, one column per stock, values = closing price.
# Before: long list of (symbol, date, close)   After: a grid like a spreadsheet.
closes = bars.df["close"].unstack(level="symbol")
closes = closes[symbols].dropna()  # keep our order; drop days where any stock is missing


# --- (b) & (c) A FUNCTION: a recipe that measures one stock -----------------
def describe_stock(prices):
    """Given a column of daily prices, return a few simple numbers about it."""
    daily_change = prices.pct_change()  # % move from one day to the next

    # Biggest drop: the worst fall from a previous high point to a later low.
    running_peak = prices.cummax()
    drop_from_peak = (prices - running_peak) / running_peak

    return {
        "$100 became": 100 * prices.iloc[-1] / prices.iloc[0],
        "Return %": (prices.iloc[-1] / prices.iloc[0] - 1) * 100,
        "Typical daily move %": daily_change.std() * 100,
        "Biggest drop %": drop_from_peak.min() * 100,
    }


# --- A LOOP: run the recipe for every stock in the list ---------------------
print(f"One year: {closes.index[0]:%Y-%m-%d} -> {closes.index[-1]:%Y-%m-%d}\n")
print(f"{'Stock':<7}{'$100 became':>13}{'Return':>10}{'Daily move':>13}{'Biggest drop':>15}")
print("-" * 58)

for symbol in symbols:
    stats = describe_stock(closes[symbol])
    print(
        f"{symbol:<7}"
        f"{'$' + format(stats['$100 became'], '.2f'):>13}"
        f"{stats['Return %']:>+9.1f}%"
        f"{stats['Typical daily move %']:>12.2f}%"
        f"{stats['Biggest drop %']:>14.1f}%"
    )

# --- (d) Chart: everyone starts at $100 so they're fair to compare ----------
# A $340 stock and a $30 stock can't share a chart fairly in raw prices,
# so we rescale each one to start at 100 on day one.
growth_of_100 = closes / closes.iloc[0] * 100

plt.figure(figsize=(11, 5))
for symbol in symbols:
    plt.plot(growth_of_100.index, growth_of_100[symbol], label=symbol)
plt.axhline(100, color="gray", linewidth=1, linestyle="--")  # the starting line
plt.title("What $100 invested a year ago became")
plt.ylabel("Value of $100")
plt.legend()
plt.grid(alpha=0.3)
plt.tight_layout()

os.makedirs("data", exist_ok=True)
plt.savefig("data/compare_chart.png")
print("\nSaved chart to data/compare_chart.png")
