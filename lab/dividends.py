"""
dividends.py - cash that companies pay their shareholders (Lesson 36).

Some companies share part of their profit with shareholders as a DIVIDEND, usually
every 3 months ("quarterly"). Funds like SPY pass on the dividends of the companies inside.

Two dates matter:
  EX-DATE       you must own the share BEFORE this day to get the payment
  PAYABLE DATE  the day the cash actually arrives

DIVIDEND YIELD = a year of dividends per share / today's share price.
  A 2% yield on €500 invested is about €10 a year (before tax).
"""

from datetime import date, timedelta

import pandas as pd

COLUMNS = ["symbol", "ex_date", "payable_date", "rate", "special"]


def fetch_cash_dividends(symbols, days=400, ahead=90):
    """Cash dividends for the symbols: the last `days` days, plus ones already announced ahead."""
    from alpaca.data.enums import CorporateActionsType
    from alpaca.data.historical.corporate_actions import CorporateActionsClient
    from alpaca.data.requests import CorporateActionsRequest

    from lab.helpers import _keys

    client = CorporateActionsClient(*_keys())
    result = client.get_corporate_actions(CorporateActionsRequest(
        symbols=list(symbols), types=[CorporateActionsType.CASH_DIVIDEND],
        start=date.today() - timedelta(days=days), end=date.today() + timedelta(days=ahead),
    ))
    rows = [{"symbol": d.symbol, "ex_date": d.ex_date, "payable_date": d.payable_date,
             "rate": float(d.rate), "special": bool(d.special)}
            for d in result.data.get("cash_dividends", [])]
    return pd.DataFrame(rows, columns=COLUMNS)


def summarise(dividends, prices, values, today=None):
    """
    One row per holding:
      payments_12m     how many regular dividends in the last 12 months (4 = quarterly)
      per_share_12m    dollars per share paid in the last 12 months (regular dividends only)
      yield_%          per_share_12m / today's price
      income_year      rough yearly income on YOUR amount (value x yield), before tax
      next_date        next ex-date: "announced" if it's already in the data, else an estimate
      next_is          "announced" / "estimate" / "-" (no dividends)
    prices: {symbol: latest price in $}; values: {symbol: your money in it}.
    Uses ratios, so the currency of `values` doesn't matter (€ in -> € out).
    """
    today = today or date.today()
    year_ago = today - timedelta(days=365)
    rows = {}
    for symbol, value in pd.Series(values, dtype=float).items():
        own = dividends[(dividends["symbol"] == symbol) & ~dividends["special"]].sort_values("ex_date")
        past = own[(own["ex_date"] <= today) & (own["ex_date"] > year_ago)]
        future = own[own["ex_date"] > today]
        per_share = past["rate"].sum()
        price = prices.get(symbol)
        # No price data (e.g. Bayer's ADR) -> the yield is UNKNOWN (NaN), not zero
        yld = per_share / price * 100 if price else (0.0 if per_share == 0 else float("nan"))

        if len(future):
            next_date, next_is = future["ex_date"].iloc[0], "announced"
        elif len(own) >= 2:
            gap = pd.Series(pd.to_datetime(own["ex_date"])).diff().median()  # typical time between payments
            next_date = (pd.Timestamp(own["ex_date"].iloc[-1]) + gap).date()
            while next_date <= today:  # a missed estimate rolls forward to the next one
                next_date = (pd.Timestamp(next_date) + gap).date()
            next_is = "estimate"
        else:
            next_date, next_is = None, "-"

        rows[symbol] = {"payments_12m": len(past), "per_share_12m": per_share, "yield_%": yld,
                        "income_year": value * yld / 100, "next_date": next_date, "next_is": next_is}
    return pd.DataFrame(rows).T.sort_values("income_year", ascending=False)
