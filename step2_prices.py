"""
STEP 2: Fetch stock prices.

Goal: get (a) the latest price of a stock and (b) its daily prices for the last 30 days.

Run it with:   python step2_prices.py
Try another stock:   python step2_prices.py TSLA
"""

import os
import sys
from datetime import datetime, timedelta

from dotenv import load_dotenv
from alpaca.data.enums import Adjustment, DataFeed
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest, StockLatestTradeRequest
from alpaca.data.timeframe import TimeFrame

load_dotenv()

# Which stock? Use the one typed after the command, otherwise Apple (AAPL).
symbol = sys.argv[1].upper() if len(sys.argv) > 1 else "AAPL"

# A different "phone line" - this one is for market data (prices), not your account.
client = StockHistoricalDataClient(
    os.getenv("ALPACA_API_KEY"),
    os.getenv("ALPACA_SECRET_KEY"),
)

# IEX = the free data source included with every Alpaca account.
FEED = DataFeed.IEX

# --- (a) Latest price -------------------------------------------------------
latest = client.get_stock_latest_trade(
    StockLatestTradeRequest(symbol_or_symbols=symbol, feed=FEED)
)[symbol]
print(f"Latest {symbol} price: ${latest.price}  (at {latest.timestamp:%Y-%m-%d %H:%M} UTC)")

# --- (b) Daily "bars" for the last 30 days ----------------------------------
# A "bar" (or "candle") summarises one day: Open, High, Low, Close, Volume.
bars = client.get_stock_bars(
    StockBarsRequest(
        symbol_or_symbols=symbol,
        timeframe=TimeFrame.Day,
        start=datetime.now() - timedelta(days=30),
        feed=FEED,
        adjustment=Adjustment.ALL,  # adjust for stock splits & dividends (see Lesson 19)
    )
)

table = bars.df  # .df turns the result into a pandas table
print(f"\nLast 30 days of {symbol}:")
print(table[["open", "high", "low", "close", "volume"]].round(2).to_string())
