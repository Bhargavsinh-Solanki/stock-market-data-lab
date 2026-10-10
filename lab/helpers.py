"""
helpers.py - our own MODULE (a file of reusable tools).

Lessons 1-9 each copied the same setup code: load keys, make clients, download
prices, run the backtest maths. Copying is risky: fix a bug in one file and the
others still have it. So the shared pieces now live here, ONCE, and any file can use them:

    from lab.helpers import daily_closes, backtest

This file does nothing when run on its own - it only DEFINES tools.
The tests in tests/test_helpers.py check the maths parts automatically.
"""

import os
import re
from datetime import datetime, timedelta

import certifi
import numpy as np
import pandas as pd
from dotenv import load_dotenv
from alpaca.data.enums import Adjustment, DataFeed
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.historical.news import NewsClient
from alpaca.data.live import StockDataStream
from alpaca.data.requests import NewsRequest, StockBarsRequest, StockLatestTradeRequest
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


def daily_closes(symbols, days=365, keep_gaps=False):
    """
    Download daily closing prices.
    One symbol ("AAPL")        -> a single column of prices (a Series)
    Several (["AAPL", "SPY"])  -> a table with one column per symbol
    keep_gaps=False: keep only days where EVERY stock has a price (simple to work with)
    keep_gaps=True:  keep every day; a stock with no price that day (not listed yet,
                     or no data at all) gets an empty value (NaN) instead (Lesson 24)
    """
    bars = data_client().get_stock_bars(
        StockBarsRequest(
            symbol_or_symbols=symbols,
            timeframe=TimeFrame.Day,
            start=datetime.now() - timedelta(days=days),
            feed=DataFeed.IEX,
            adjustment=Adjustment.ALL,  # adjust for stock splits & dividends (see Lesson 19)
        )
    )
    if isinstance(symbols, str):
        return bars.df.loc[symbols]["close"]
    table = bars.df["close"].unstack(level="symbol")
    if keep_gaps:
        return table.reindex(columns=symbols)  # a symbol with no data at all -> an empty column
    return table[symbols].dropna()


def latest_session_minutes(symbol):
    """
    1-minute bars for the most recent trading session (today if the market is open,
    otherwise the last day it was open). Returns a table indexed by New York time.
    """
    bars = data_client().get_stock_bars(
        StockBarsRequest(
            symbol_or_symbols=symbol,
            timeframe=TimeFrame.Minute,
            start=datetime.now() - timedelta(days=4),  # enough to cover a weekend
            feed=DataFeed.IEX,
            adjustment=Adjustment.ALL,  # adjust for stock splits & dividends (see Lesson 19)
        )
    )
    df = bars.df.loc[symbol]
    df.index = df.index.tz_convert("America/New_York")
    df = df.between_time("09:30", "15:59")  # regular hours only, no pre-/after-market
    last_day = df.index[-1].date()
    return df[df.index.date == last_day]


def latest_trade(symbol):
    """The most recent trade for a symbol: has .price, .size and .timestamp."""
    request = StockLatestTradeRequest(symbol_or_symbols=symbol, feed=DataFeed.IEX)
    return data_client().get_stock_latest_trade(request)[symbol]


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


# --- News sentiment (Lesson 15) ----------------------------------------------------
# A "word list" (lexicon) approach: count good words and bad words. Very simple -
# it can't understand sarcasm, context or "not good" - but easy to read and test.
POSITIVE_WORDS = {
    "beat", "beats", "surge", "surges", "soar", "soars", "jump", "jumps", "rally", "rallies",
    "gain", "gains", "rise", "rises", "climb", "climbs", "record", "strong", "stronger",
    "upgrade", "upgrades", "upgraded", "outperform", "bullish", "boost", "boosts", "raises",
    "growth", "profit", "profits", "win", "wins", "approval", "approved", "high", "higher",
}
NEGATIVE_WORDS = {
    "miss", "misses", "fall", "falls", "drop", "drops", "plunge", "plunges", "slump", "slumps",
    "sink", "sinks", "tumble", "tumbles", "decline", "declines", "loss", "losses", "weak",
    "weaker", "downgrade", "downgrades", "downgraded", "underperform", "bearish", "cut", "cuts",
    "lawsuit", "probe", "investigation", "recall", "layoffs", "warning", "warns", "low", "lower",
    "fine", "fined", "ban", "concerns", "fears",
}


def headline_sentiment(text):
    """+1 for each positive word, -1 for each negative word. 0 = neutral or mixed."""
    words = re.findall(r"[a-z]+", text.lower())  # split into lowercase words, drop punctuation
    return sum(w in POSITIVE_WORDS for w in words) - sum(w in NEGATIVE_WORDS for w in words)


def news_by_day(symbol, days=180, max_tickers=3):
    """
    Lessons 12 + 15 in one table: for each trading day with news,
    the price move, the next day's move, the number of stories, and the mood.
    Returns (headlines, table).
    """
    news = news_client().get_news(
        NewsRequest(symbols=symbol, start=datetime.now() - timedelta(days=days))
    ).df
    news = news[news["symbols"].apply(len) <= max_tickers].copy()
    news["score"] = news["headline"].apply(headline_sentiment)

    close = daily_closes(symbol, days=days + 10)
    close.index = close.index.tz_localize(None).normalize()
    prices = pd.DataFrame({"move_%": close.pct_change() * 100})
    prices["next_day_move_%"] = prices["move_%"].shift(-1)

    news["trading_day"] = trading_day_for(news["created_at"], prices.index)
    per_day = news.groupby("trading_day").agg(stories=("score", "size"), mood=("score", "mean"))
    table = prices.join(per_day, how="inner").dropna(subset=["move_%"])
    return news, table


# --- Is it real or luck? (Lesson 16) -----------------------------------------------

def shuffle_test(values, chosen, n_shuffles=10_000, seed=0):
    """
    How often would RANDOMLY picked days look as good as the days we chose?

    values: a number for every day (e.g. next-day move)
    chosen: True/False for every day (e.g. "was it a good-news day?")
    Returns (our average, list of random averages, p-value).

    p-value = the fraction of random picks that did at least as well as ours.
      small (under 0.05)  -> hard to get by luck, probably a real effect
      large               -> random days often do this well, so it may just be luck
    """
    values = np.asarray(values, dtype=float)
    chosen = np.asarray(chosen, dtype=bool)
    ours = values[chosen].mean()

    rng = np.random.default_rng(seed)  # a seed makes the "random" results repeatable
    k = chosen.sum()
    random_averages = np.array([
        rng.choice(values, size=k, replace=False).mean() for _ in range(n_shuffles)
    ])
    p_value = (random_averages >= ours).mean()
    return ours, random_averages, p_value


# --- Portfolios (Lesson 19) ----------------------------------------------------------

def portfolio_returns(daily_returns, symbols):
    """
    Daily returns of an EQUAL-WEIGHT portfolio: the same amount in each stock,
    topped back up to equal amounts every day (so it's just the average of their returns).
    daily_returns: a table with one column per stock.
    """
    return daily_returns[list(symbols)].mean(axis=1)


def weighted_returns(daily_returns, weights):
    """
    Daily returns of a portfolio with FIXED weights, e.g. {"SPY": 0.6, "TSLA": 0.4}
    = 60% of the money in SPY and 40% in TSLA (weights should add up to 1).
    """
    weights = pd.Series(weights, dtype=float)
    return daily_returns[weights.index] @ weights  # @ = "multiply each column by its weight, then add"


def effective_stocks(weights):
    """
    'How many equal-sized positions is this portfolio REALLY like?'
    4 equal positions -> 4.0. One 97% position plus three tiny ones -> about 1.1.
    Formula: 1 / sum of squared weights.
    """
    weights = pd.Series(weights, dtype=float)
    return 1 / (weights ** 2).sum()


def risk_shares(daily_returns, weights):
    """
    Each position's share of the portfolio's total risk (adds up to 100%).
    A position can be 20% of the MONEY but 40% of the RISK if it's very bumpy
    and moves together with the rest.
    """
    weights = pd.Series(weights, dtype=float)
    cov = daily_returns[weights.index].cov()   # how each pair of stocks moves together
    portfolio_variance = weights @ cov @ weights
    return weights * (cov @ weights) / portfolio_variance * 100


def annual_volatility(daily_returns):
    """
    How bumpy the ride is over a YEAR, in %. Daily ups and downs grow with the
    square root of time, and a year has about 252 trading days, so: daily std x sqrt(252).
    """
    return pd.Series(daily_returns).std() * np.sqrt(252) * 100


def biggest_drop(values):
    """Worst fall from a high point to a later low, as a negative % (e.g. -25.0)."""
    values = pd.Series(values, dtype=float)
    peak = values.cummax()
    return ((values - peak) / peak).min() * 100
