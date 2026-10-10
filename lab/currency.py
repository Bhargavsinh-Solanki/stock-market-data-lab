"""
currency.py - seeing US-dollar investments through euro eyes (Lesson 33).

You invest in EUROS, but almost everything you own is priced in US DOLLARS.
So your result in euros has TWO parts:
  1. how the stock moved in dollars
  2. how the dollar moved against the euro

Example: a stock rises 10% in dollars, but the euro rises 5% against the dollar
(each dollar now buys fewer euros):   1.10 / 1.05 - 1 = +4.8% in euros, not +10%.

Where the exchange rate comes from: FXE is a fund that simply holds euros, so its
dollar price moves with EUR/USD. (It also charges a tiny yearly fee - close enough.)
"""

import pandas as pd

FX_SYMBOL = "FXE"


def euro_strength(days=400):
    """Daily closes of FXE: the euro's value in dollars (up = euro stronger, dollar weaker)."""
    from lab.helpers import daily_closes  # imported here so the tests need no internet

    return daily_closes(FX_SYMBOL, days=days)  # same dates as every other daily_closes() call


def to_euro_prices(usd_prices, euro_in_usd):
    """
    Convert dollar prices into euro terms by dividing by the euro's dollar value.
    (Only CHANGES matter for returns, so FXE's price level doesn't need to equal EUR/USD.)
    """
    fx = euro_in_usd.reindex(usd_prices.index).ffill()  # line up the dates; fill small gaps
    if isinstance(usd_prices, pd.DataFrame):
        return usd_prices.div(fx, axis=0)
    return usd_prices / fx


def to_euro_returns(usd_returns, euro_returns):
    """Daily returns in euros: (1 + dollar return) / (1 + euro's change vs the dollar) - 1."""
    fx = euro_returns.reindex(usd_returns.index).fillna(0.0)
    if isinstance(usd_returns, pd.DataFrame):
        return (1 + usd_returns).div(1 + fx, axis=0) - 1
    return (1 + usd_returns) / (1 + fx) - 1


def split_return(usd_return_pct, euro_change_pct):
    """
    Break a result in euros into its two parts (all in %).
    Returns (return in euros, the part that came from the exchange rate).
    """
    in_euros = ((1 + usd_return_pct / 100) / (1 + euro_change_pct / 100) - 1) * 100
    return in_euros, in_euros - usd_return_pct
