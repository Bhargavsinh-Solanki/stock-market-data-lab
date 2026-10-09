"""
helpers.py - our own MODULE (a file of reusable tools).

Lessons 1-9 each copied the same setup code: load keys, make clients, download
prices, run the backtest maths. Copying is risky: fix a bug in one file and the
others still have it. So the shared pieces now live here, ONCE, and any file can use them:

    from helpers import daily_closes, backtest

This file does nothing when run on its own - it only DEFINES tools.
The tests in tests/test_helpers.py check the maths parts automatically.
"""

import os
from datetime import datetime, timedelta

import certifi
import pandas as pd
from dotenv import load_dotenv
from alpaca.data.enums import DataFeed
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.historical.news import NewsClient
from alpaca.data.live import StockDataStream
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame
from alpaca.trading.client import TradingClient

load_dotenv()


# --- Talking to Alpaca ----------------------------------------------------------

def _keys():
    """Read the API keys from .env (the leading _ means 'for use inside this file')."""
    key, secret = os.getenv("ALPACA_API_KEY"), os.getenv("ALPACA_SECRET_KEY")
    if not key or "paste_your" in key:
        raise SystemExit("No Alpaca keys found. Paste them into the .env file.")
    return key, secret


def trading_client():
    """Phone line for account, positions and orders. Always the PAPER account."""
    return TradingClient(*_keys(), paper=True)


def data_client():
    """Phone line for market data (prices)."""
    return StockHistoricalDataClient(*_keys())


def news_client():
    """Phone line for news headlines."""
    return NewsClient(*_keys())


def live_stream():
    """
    An open line where Alpaca PUSHES live prices to us as they happen (a websocket).
    The free plan allows only ONE of these open at a time.
    """
    # Python from python.org on a Mac has no list of trusted certificates, so the
    # secure connection fails ("CERTIFICATE_VERIFY_FAILED"). Borrow certifi's list.
    os.environ.setdefault("SSL_CERT_FILE", certifi.where())
    return StockDataStream(*_keys(), feed=DataFeed.IEX)


def daily_closes(symbols, days=365):
    """
    Download daily closing prices.
    One symbol ("AAPL")        -> a single column of prices (a Series)
    Several (["AAPL", "SPY"])  -> a table with one column per symbol
    """
    bars = data_client().get_stock_bars(
        StockBarsRequest(
            symbol_or_symbols=symbols,
            timeframe=TimeFrame.Day,
            start=datetime.now() - timedelta(days=days),
            feed=DataFeed.IEX,
        )
    )
    if isinstance(symbols, str):
        return bars.df.loc[symbols]["close"]
    return bars.df["close"].unstack(level="symbol")[symbols].dropna()


# --- Maths (no internet needed - this is what the tests check) -----------------

def ma_rule_positions(close, ma_days):
    """
    True on the days the moving-average rule HOLDS the stock.
    The decision made at day N's close is acted on during day N+1 (no peeking).
    """
    ma = close.rolling(ma_days).mean()
    return (close > ma).shift(1, fill_value=False)


def backtest(close, ma_days, cost=0.001):
    """Daily returns of the moving-average rule, paying `cost` on every switch."""
    in_market = ma_rule_positions(close, ma_days)
    stock_return = close.pct_change().fillna(0)
    switched = in_market != in_market.shift(1, fill_value=False)
    return stock_return.where(in_market, 0.0) - switched * cost


def grow_100(daily_returns):
    """What $100 becomes after a series of daily returns (compounding)."""
    return 100 * (1 + pd.Series(daily_returns)).prod()


def trading_day_for(published, trading_days):
    """
    Which trading day's price move could a news story have affected?

    The US market closes at 16:00 New York time. A story published before the
    close can move THAT day's price; a story after the close (or on a weekend)
    can only move the NEXT trading day. Getting this wrong is look-ahead bias again.

    published:    timestamps (any time zone)
    trading_days: sorted dates the market was open
    Returns the matching trading day for each story (NaT if it's after the last day).
    """
    ny = pd.DatetimeIndex(published).tz_convert("America/New_York")
    day = ny.normalize().tz_localize(None)
    day = day.where(ny.hour < 16, day + pd.Timedelta(days=1))  # after close -> next day
    days = pd.DatetimeIndex(trading_days)
    pos = days.searchsorted(day)  # first trading day on or after `day`
    return pd.DatetimeIndex([days[p] if p < len(days) else pd.NaT for p in pos])


def biggest_drop(values):
    """Worst fall from a high point to a later low, as a negative % (e.g. -25.0)."""
    values = pd.Series(values, dtype=float)
    peak = values.cummax()
    return ((values - peak) / peak).min() * 100
