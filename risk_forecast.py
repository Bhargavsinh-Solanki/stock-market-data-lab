"""
risk_forecast.py - forecasting how BUMPY a stock will be next month (Lesson 28).

Lesson 23 showed volatility carries over from one period to the next, while returns
don't. So risk is the one thing worth trying to forecast. Four simple methods:

  "last month"  volatility of the last 21 trading days
  "3 months"    volatility of the last 63 trading days
  "1 year"      volatility of the last 252 trading days
  "EWMA"        an average where recent days count more (lambda = 0.94, the "RiskMetrics"
                method banks have used since the 1990s)

Every forecast only uses days BEFORE the month it predicts - no peeking (Lesson 5).
All volatilities are annualised (x sqrt(252)), in %.
"""

import numpy as np
import pandas as pd

HORIZON = 21  # trading days in a month
WINDOWS = {"last month": 21, "3 months": 63, "1 year": 252}


def ewma_volatility(returns, lam=0.94):
    """
    EWMA ("exponentially weighted moving average") volatility, day by day.
    Each day: variance = lam x yesterday's variance + (1 - lam) x today's squared return.
    So yesterday counts 6%, the day before 6% x 0.94, and so on - older days fade away.
    """
    variance = (returns ** 2).ewm(alpha=1 - lam, adjust=False).mean()
    return np.sqrt(variance * 252) * 100


def forecasts(returns):
    """Every method's forecast, made at the end of each day, for each column (stock)."""
    out = {name: returns.rolling(days).std() * np.sqrt(252) * 100 for name, days in WINDOWS.items()}
    out["EWMA"] = ewma_volatility(returns)
    return out


def realised_next(returns, horizon=HORIZON):
    """What actually happened: the volatility of the NEXT `horizon` days after each day."""
    future = returns.rolling(horizon).std().shift(-horizon)  # shift(-21) = look 21 days ahead
    return future * np.sqrt(252) * 100


def evaluate(returns, horizon=HORIZON, start=252):
    """
    Walk forward through history one month at a time. At each step, every method
    makes its forecast, then we check it against what really happened next month.
    Returns a table: method -> average error and rank correlation (across all stocks and months).
    """
    made = forecasts(returns)
    actual = realised_next(returns, horizon)
    checkpoints = returns.index[start:-horizon:horizon]  # month-end-ish dates, skipping year 1

    rows = {}
    for name, f in made.items():
        pairs = pd.DataFrame({
            "forecast": f.loc[checkpoints].stack(),
            "actual": actual.loc[checkpoints].stack(),
        }).dropna()
        rows[name] = {
            "avg_error_pts": (pairs["forecast"] - pairs["actual"]).abs().mean(),
            "rank_corr": pairs["forecast"].rank().corr(pairs["actual"].rank()),
            "checks": len(pairs),
        }
    return pd.DataFrame(rows).T.sort_values("avg_error_pts")


def return_forecast_check(returns, horizon=HORIZON, start=252):
    """
    The same honest test, for RETURNS: does last month's return predict next month's?
    Returns the rank correlation (near 0 = no, it doesn't).
    """
    past = returns.rolling(horizon).sum()
    future = returns.rolling(horizon).sum().shift(-horizon)
    checkpoints = returns.index[start:-horizon:horizon]
    pairs = pd.DataFrame({"past": past.loc[checkpoints].stack(),
                          "future": future.loc[checkpoints].stack()}).dropna()
    return pairs["past"].rank().corr(pairs["future"].rank())
