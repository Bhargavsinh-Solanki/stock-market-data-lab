"""
portfolio.py - the portfolio health-check CALCULATIONS (Lessons 20-21).

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
    "SPY": "Fund: S&P 500", "QQQ": "Fund: Nasdaq 100",
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
    growth: pd.DataFrame        # "$100 became..." day by day: your mix vs just SPY
    comparison: pd.DataFrame    # final value, volatility and biggest drop: your mix vs SPY


def health_check(days=365):
    """Analyse the current paper portfolio. Returns a HealthCheck, or None if it's empty."""
    client = trading_client()
    account = client.get_account()
    held = [p for p in client.get_all_positions() if p.asset_class.value == "us_equity"]
    if not held:
        return None

    values = pd.Series({p.symbol: float(p.market_value) for p in held}).sort_values(ascending=False)
    weights = values / values.sum()

    symbols = list(weights.index) + (["SPY"] if "SPY" not in weights.index else [])
    returns = daily_closes(symbols, days=days).pct_change().dropna()

    positions = pd.DataFrame({
        "sector": [SECTOR.get(s, "Other") for s in weights.index],
        "value_$": values,
        "money_%": weights * 100,
        "risk_%": risk_shares(returns, weights),
        "own_volatility_%": [annual_volatility(returns[s]) for s in weights.index],
    })

    corr = returns[weights.index].corr()
    pairs = corr.where(np.triu(np.ones(corr.shape, dtype=bool), k=1)).stack().dropna()

    daily = {"Your mix": weighted_returns(returns, weights), "Just SPY": returns["SPY"]}
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
        total=float(account.portfolio_value),
        invested=values.sum(),
        positions=positions,
        by_sector=positions.groupby("sector")["money_%"].sum().sort_values(ascending=False),
        effective=effective_stocks(weights),
        correlations=corr,
        close_pairs=pairs[pairs > 0.7].sort_values(ascending=False),
        growth=growth,
        comparison=comparison,
    )
