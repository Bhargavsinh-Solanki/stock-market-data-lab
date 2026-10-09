"""
STEP 3: Save prices to a file and draw a chart.

Goal:
  (a) download 1 year of daily prices
  (b) save them to a CSV file (a simple spreadsheet you can open in Excel/Numbers)
  (c) draw a line chart of the closing price, plus a "moving average" line

Run it with:   python step3_save_and_chart.py
Try another stock:   python step3_save_and_chart.py MSFT
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

symbol = sys.argv[1].upper() if len(sys.argv) > 1 else "AAPL"

client = StockHistoricalDataClient(
    os.getenv("ALPACA_API_KEY"),
    os.getenv("ALPACA_SECRET_KEY"),
)

# --- (a) Download 1 year of daily bars --------------------------------------
bars = client.get_stock_bars(
    StockBarsRequest(
        symbol_or_symbols=symbol,
        timeframe=TimeFrame.Day,
        start=datetime.now() - timedelta(days=365),
        feed=DataFeed.IEX,
    )
)

# The table comes back with two labels per row: (symbol, date).
# We only asked for one stock, so drop the symbol label and keep just the date.
table = bars.df.loc[symbol]

# --- A first bit of analysis: the 20-day moving average ---------------------
# For each day, take the average closing price of the last 20 trading days.
# It smooths out the daily ups and downs so you can see the general trend.
table["ma_20"] = table["close"].rolling(window=20).mean()

# --- (b) Save to a CSV file -------------------------------------------------
os.makedirs("data", exist_ok=True)  # create the "data" folder if it's missing
csv_path = f"data/{symbol}_daily.csv"
table.to_csv(csv_path)
print(f"Saved {len(table)} days of prices to {csv_path}")

# --- (c) Draw the chart -----------------------------------------------------
plt.figure(figsize=(11, 5))
plt.plot(table.index, table["close"], label="Daily close")
plt.plot(table.index, table["ma_20"], label="20-day average")
plt.title(f"{symbol} - last 12 months")
plt.xlabel("Date")
plt.ylabel("Price (USD)")
plt.legend()
plt.grid(alpha=0.3)
plt.tight_layout()

chart_path = f"data/{symbol}_chart.png"
plt.savefig(chart_path)
print(f"Saved chart to {chart_path}")

# A few simple facts about the year
first, last = table["close"].iloc[0], table["close"].iloc[-1]
print(f"\nStart price : ${first:.2f}")
print(f"Latest price: ${last:.2f}")
print(f"Change      : {(last - first) / first * 100:+.1f}%")
print(f"Highest     : ${table['high'].max():.2f}")
print(f"Lowest      : ${table['low'].min():.2f}")
