"""
performers.py - which stocks did best over a period, and what's their RISK forecast (Lesson 32).

Two very different kinds of number, on purpose:
  - PAST return: a FACT ("ZS went up 41% this month").
  - Next month's normal RANGE: a forecast of how much it may SWING (Lesson 28 showed this
    works: rank correlation +0.70).
What it deliberately does NOT do is forecast the direction. Lessons 23 and 28 tested that:
last period's winners told us nothing about the next period (rank correlation about 0.00).
"""

import pandas as pd

from lab.risk_forecast import forecasts, monthly_ranges

PERIODS = {"1 week": 5, "1 month": 21, "3 months": 63, "1 year": 252}

POPULAR = ["AAPL", "MSFT", "NVDA", "AMD", "AVGO", "GOOGL", "META", "AMZN", "TSLA", "NFLX",
           "ORCL", "CRM", "ADBE", "INTC", "JPM", "BAC", "V", "MA", "WMT", "COST", "KO", "PEP",
           "JNJ", "PFE", "LLY", "XOM", "CVX", "CAT", "DIS", "SPY", "QQQ", "URTH"]


def top_performers(closes, period_days):
    """
    closes: daily closing prices, one column per symbol (gaps allowed, e.g. new listings).
    Returns one row per symbol with enough history, best first:
      return_%      how much it went up or down over the last `period_days` trading days
      volatility_%  next month's risk forecast (3-month method; EWMA if the stock is newer)
      typical_%     in about 2 months out of 3, next month's move stays within ± this
      bad_%         roughly 1 month in 20 is worse than this
    """
    rows = {}
    for symbol in closes.columns:
        prices = closes[symbol].dropna()
        if len(prices) <= period_days:
            continue  # not listed long enough for this period
        returns = prices.pct_change().dropna().to_frame(symbol)
        made = forecasts(returns)
        vol = made["3 months"][symbol].iloc[-1]
        if pd.isna(vol):
            vol = made["EWMA"][symbol].iloc[-1]
        rows[symbol] = {"return_%": (prices.iloc[-1] / prices.iloc[-1 - period_days] - 1) * 100,
                        "volatility_%": vol}

    table = pd.DataFrame(rows).T
    if table.empty:
        return pd.DataFrame(columns=["return_%", "volatility_%", "typical_%", "bad_%"])
    ranges = monthly_ranges(table["volatility_%"])
    return table[["return_%"]].join(ranges).sort_values("return_%", ascending=False)
