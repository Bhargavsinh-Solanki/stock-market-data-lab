"""
portfolio.py - the portfolio health-check CALCULATIONS (Lessons 20-24).

This file only CALCULATES - it never prints and never draws. Two different
"front ends" use it:
  - step20_portfolio_check.py  -> shows the results as text in the terminal
  - step11_dashboard.py         -> shows them as a web page

Keeping calculations separate from display is called SEPARATION OF CONCERNS:
fix a bug once here, and both the terminal and the web page get the fix.
"""

from dataclasses import dataclass

import numpy as np
import pandas as pd

from helpers import (
    annual_volatility, biggest_drop, daily_closes, effective_stocks, risk_shares,
    trading_client, weighted_returns,
)

# Alpaca doesn't tell us a company's sector, so we keep a small list ourselves.
SECTOR = {
    "AAPL": "Tech", "MSFT": "Tech", "NVDA": "Tech", "AMD": "Tech", "INTC": "Tech",
    "GOOGL": "Tech", "META": "Tech", "LITE": "Tech", "AVGO": "Tech",
    "AMZN": "Consumer", "TSLA": "Consumer", "NFLX": "Consumer", "WMT": "Consumer",
    "COST": "Consumer", "KO": "Consumer", "PEP": "Consumer", "HD": "Consumer",
    "JPM": "Finance", "BAC": "Finance", "GS": "Finance",
    "XOM": "Energy", "CVX": "Energy", "JNJ": "Health", "PFE": "Health", "CAT": "Industrial",
    "ORCL": "Tech", "ZS": "Tech", "MRVL": "Tech", "QBTS": "Tech",
    "CEG": "Utilities", "BAYRY": "Health", "SPCX": "Industrial",
    "SPY": "Fund: S&P 500", "QQQ": "Fund: Nasdaq 100", "URTH": "Fund: MSCI World",
}


@dataclass
class HealthCheck:
    """
    A DATACLASS is a simple container with named fields - like a labelled box
    holding all the results together, so we can hand them over in one piece.
    """
    total: float                # whole paper account, $
    invested: float             # money in stocks, $
    positions: pd.DataFrame     # one row per holding: sector, value, money %, risk %, volatility
    by_sector: pd.Series        # % of invested money per sector
    effective: float            # effective number of stocks
    correlations: pd.DataFrame  # every holding vs every other
    close_pairs: pd.Series      # pairs moving together (correlation > 0.7)
    growth: pd.DataFrame        # "$100 became..." day by day: your mix vs the benchmark(s)
    comparison: pd.DataFrame    # final value, volatility and biggest drop: your mix vs benchmarks
    excluded: pd.Series = None  # holdings left out (too little price history): symbol -> value


def normalise(weights):
    """
    Scale weights so they add up to 1 (100%), dropping zeros.
    {"A": 30, "B": 10, "C": 0} -> {"A": 0.75, "B": 0.25}
    Sliders can add up to anything; this turns them into proper shares.
    """
    weights = pd.Series(weights, dtype=float)
    weights = weights[weights > 0]
    if weights.empty:
        raise ValueError("At least one weight must be above zero.")
    return weights / weights.sum()


def simulate(daily_returns, weights):
    """
    'What if I'd held THIS mix over the period?' (Lesson 22)
    Returns a dict of results plus each position's share of the risk.
    Uses past prices, so it shows what WOULD have happened - not a forecast.
    """
    weights = normalise(weights)
    daily = weighted_returns(daily_returns, weights)
    value = 100 * (1 + daily).cumprod()
    return {
        "$100 became": value.iloc[-1],
        "volatility_%": annual_volatility(daily),
        "biggest_drop_%": biggest_drop(value),
        "effective_stocks": effective_stocks(weights),
        "risk_%": risk_shares(daily_returns, weights),
        "growth": value,
    }


def yearly_stats(daily_returns, weights):
    """
    The same mix, judged one CALENDAR YEAR at a time (Lesson 23).
    Returns one row per year: return %, volatility %, biggest drop %, trading days.
    """
    daily = weighted_returns(daily_returns, normalise(weights))
    rows = {}
    for year, r in daily.groupby(daily.index.year):  # split the days into one bucket per year
        value = 100 * (1 + r).cumprod()
        rows[year] = {
            "return_%": value.iloc[-1] - 100,
            "volatility_%": annual_volatility(r),
            "biggest_drop_%": biggest_drop(value),
            "days": len(r),
        }
    return pd.DataFrame(rows).T


def current_weights():
    """Your paper portfolio's stock positions as {symbol: share of invested money}."""
    held = [p for p in trading_client().get_all_positions() if p.asset_class.value == "us_equity"]
    values = pd.Series({p.symbol: float(p.market_value) for p in held}, dtype=float)
    return (values / values.sum()).sort_values(ascending=False)


def analyse(values, days=365, benchmarks=("SPY",), min_days=200, total=None):
    """
    The health check for ANY set of holdings (Lessons 20-24).
    values:     money in each holding, e.g. {"SPY": 310, "NVDA": 593} - any currency
    benchmarks: what to compare your mix with, e.g. ("SPY", "URTH")
    min_days:   holdings with fewer days of prices than this (new listings, or no data
                at all) are left out of the maths and reported in `excluded`
    """
    values = pd.Series(values, dtype=float).sort_values(ascending=False)
    symbols = list(dict.fromkeys(list(values.index) + list(benchmarks)))  # no repeats, keep order
    closes = daily_closes(symbols, days=days, keep_gaps=True)

    days_of_data = closes.notna().sum()
    usable = [s for s in values.index if days_of_data.get(s, 0) >= min_days]
    excluded = values.drop(usable)
    if not usable:
        raise ValueError("None of the holdings has enough price history.")

    columns = list(dict.fromkeys(usable + list(benchmarks)))
    returns = closes[columns].dropna().pct_change().dropna()
    weights = values[usable] / values[usable].sum()

    positions = pd.DataFrame({
        "sector": [SECTOR.get(s, "Other") for s in usable],
        "value_$": values[usable],
        "money_%": weights * 100,
        "risk_%": risk_shares(returns, weights),
        "own_volatility_%": [annual_volatility(returns[s]) for s in usable],
    })

    corr = returns[usable].corr()
    pairs = corr.where(np.triu(np.ones(corr.shape, dtype=bool), k=1)).stack().dropna()

    daily = {"Your mix": weighted_returns(returns, weights)}
    daily.update({f"Just {b}": returns[b] for b in benchmarks})
    growth = pd.DataFrame({name: 100 * (1 + r).cumprod() for name, r in daily.items()})
    comparison = pd.DataFrame({
        name: {
            "$100 became": growth[name].iloc[-1],
            "volatility_%": annual_volatility(r),
            "biggest_drop_%": biggest_drop(growth[name]),
        }
        for name, r in daily.items()
    }).T

    return HealthCheck(
        total=total if total is not None else values.sum(),
        invested=values.sum(),
        positions=positions,
        by_sector=positions.groupby("sector")["money_%"].sum().sort_values(ascending=False),
        effective=effective_stocks(weights),
        correlations=corr,
        close_pairs=pairs[pairs > 0.7].sort_values(ascending=False),
        growth=growth,
        comparison=comparison,
        excluded=excluded,
    )


def health_check(days=365):
    """Analyse the current PAPER portfolio. Returns a HealthCheck, or None if it's empty."""
    client = trading_client()
    held = [p for p in client.get_all_positions() if p.asset_class.value == "us_equity"]
    if not held:
        return None
    values = {p.symbol: float(p.market_value) for p in held}
    return analyse(values, days=days, total=float(client.get_account().portfolio_value))
