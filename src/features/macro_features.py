"""Macro & market-context features, merged as-of so that monthly series
(CPI, unemployment) only appear from their release date forward."""
from __future__ import annotations

import numpy as np
import pandas as pd


def compute_market_context(prices: pd.DataFrame) -> pd.DataFrame:
    """From prices_daily rows of SPY/QQQ/^VIX build daily context features.

    Returns a frame keyed by `date`.
    """
    ctx = pd.DataFrame({"date": np.sort(prices["date"].unique())})
    ctx["date"] = pd.to_datetime(ctx["date"])

    def _series(ticker: str) -> pd.Series | None:
        s = prices[prices["ticker"] == ticker].sort_values("date")
        if s.empty:
            return None
        return s.set_index(pd.to_datetime(s["date"]))["adj_close"]

    for ticker, prefix in (("SPY", "spy"), ("QQQ", "qqq")):
        s = _series(ticker)
        if s is None:
            ctx[f"{prefix}_ret_1d"] = np.nan
            ctx[f"{prefix}_ret_5d"] = np.nan
            continue
        log_s = np.log(s)
        ctx = ctx.merge(
            pd.DataFrame({
                "date": s.index,
                f"{prefix}_ret_1d": log_s.diff(1).values,
                f"{prefix}_ret_5d": log_s.diff(5).values,
            }),
            on="date", how="left",
        )

    vix = _series("^VIX")
    if vix is not None:
        ctx = ctx.merge(
            pd.DataFrame({
                "date": vix.index,
                "vix_level": vix.values,
                "vix_change_5d": vix.diff(5).values,
            }),
            on="date", how="left",
        )
    else:
        ctx["vix_level"] = np.nan
        ctx["vix_change_5d"] = np.nan
    return ctx


def compute_macro_features(macro: pd.DataFrame, dates: pd.Series) -> pd.DataFrame:
    """Pivot macro_daily to wide, forward-fill onto the trading calendar,
    and add simple change features. Keyed by `date`."""
    calendar = pd.DataFrame({"date": pd.to_datetime(sorted(dates.unique()))})
    if macro is None or macro.empty:
        return calendar

    wide = (
        macro.assign(date=lambda d: pd.to_datetime(d["date"]))
        .pivot_table(index="date", columns="series_id", values="value", aggfunc="last")
        .sort_index()
    )
    # Reindex on the UNION of observation dates and trading days before the
    # forward-fill: macro observations dated on non-trading days (annual
    # values on Dec 31, monthly values on the 1st) must survive the join and
    # carry forward to the next trading day, not be dropped.
    calendar_dates = pd.DatetimeIndex(calendar["date"].sort_values().unique())
    wide = (
        wide.reindex(wide.index.union(calendar_dates))
        .ffill()
        .reindex(calendar_dates)
    )

    out = calendar.merge(
        wide.reset_index().rename(columns={"index": "date"}), on="date", how="left"
    )
    out.columns = [c if c == "date" else f"macro_{c.lower()}" for c in out.columns]
    if "macro_dgs10" in out.columns:
        out["macro_dgs10_chg_21d"] = out["macro_dgs10"].diff(21)
    if "macro_fedfunds" in out.columns:
        out["macro_rate_regime_rising"] = (
            out["macro_fedfunds"].diff(63).fillna(0) > 0
        ).astype(float)
    return out
