"""Price/technical features at (ticker, date) level. Pure pandas, no I/O.

All features use information available at the close of `date` only.
Forward-looking columns are prefixed `label_` and exist solely as targets.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

RETURN_WINDOWS = (1, 5, 10, 21, 63)


def _rsi(close: pd.Series, window: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / window, min_periods=window).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / window, min_periods=window).mean()
    rs = gain / loss.replace(0, np.nan)
    return 100 - 100 / (1 + rs)


def _per_ticker(df: pd.DataFrame, horizons: tuple[int, ...]) -> pd.DataFrame:
    df = df.sort_values("date").copy()
    close = df["adj_close"]
    log_close = np.log(close)

    for w in RETURN_WINDOWS:
        df[f"ret_{w}d"] = log_close.diff(w)

    ret_1d = df["ret_1d"]
    df["vol_21d"] = ret_1d.rolling(21).std() * np.sqrt(252)
    df["vol_63d"] = ret_1d.rolling(63).std() * np.sqrt(252)

    vol_mean = df["volume"].rolling(21).mean()
    vol_std = df["volume"].rolling(21).std()
    df["volume_z_21d"] = (df["volume"] - vol_mean) / vol_std.replace(0, np.nan)

    # Momentum: medium-term trend excluding the most recent week (reversal).
    df["momentum_63_5"] = df["ret_63d"] - df["ret_5d"]
    df["rsi_14"] = _rsi(close)

    ema12 = close.ewm(span=12, min_periods=12).mean()
    ema26 = close.ewm(span=26, min_periods=26).mean()
    macd = ema12 - ema26
    df["macd"] = macd / close  # scale-free
    df["macd_signal"] = macd.ewm(span=9, min_periods=9).mean() / close
    df["macd_hist"] = df["macd"] - df["macd_signal"]

    df["ma_dist_20"] = close / close.rolling(20).mean() - 1
    df["ma_dist_50"] = close / close.rolling(50).mean() - 1

    # Labels: forward log return per horizon (targets, never features).
    for h in horizons:
        df[f"label_fwd_log_ret_{h}d"] = log_close.shift(-h) - log_close
        df[f"label_direction_{h}d"] = (
            (df[f"label_fwd_log_ret_{h}d"] > 0).astype("float")
            .where(df[f"label_fwd_log_ret_{h}d"].notna())
        )
    return df


def compute_price_features(
    prices: pd.DataFrame,
    market_returns: pd.DataFrame | None = None,
    sector_map: dict[str, str] | None = None,
    sector_returns: pd.DataFrame | None = None,
    horizon: int = 5,
    extra_horizons: tuple[int, ...] = (21,),
) -> pd.DataFrame:
    """prices: columns [ticker, date, adj_close, volume].
    market_returns: [date, mkt_ret_1d, mkt_ret_21d] (e.g. SPY), optionally
    with mkt_fwd_ret_{h}d columns used for market-neutral residual labels.
    sector_returns: [date, ticker(ETF), ret_21d] for sector-relative return.
    """
    horizons = tuple(sorted({horizon, *extra_horizons}))
    # explicit iteration (not groupby.apply) so the ticker column is kept
    # across pandas versions
    out = pd.concat(
        [_per_ticker(g, horizons) for _, g in prices.groupby("ticker", sort=False)],
        ignore_index=True,
    )

    if market_returns is not None and not market_returns.empty:
        out = out.merge(market_returns, on="date", how="left")
        # Forward market returns are future values: give them the label_
        # prefix immediately so feature_columns() can never select them.
        out = out.rename(columns={
            c: f"label_{c}" for c in out.columns if c.startswith("mkt_fwd_ret_")
        })
        # Rolling 63d market beta from daily log returns. Explicit iteration
        # (not groupby.apply) for stable behavior across pandas versions.
        out = out.sort_values(["ticker", "date"])
        betas = []
        for _, g in out.groupby("ticker", sort=False):
            cov = g["ret_1d"].rolling(63).cov(g["mkt_ret_1d"])
            var = g["mkt_ret_1d"].rolling(63).var()
            betas.append(cov / var.replace(0, np.nan))
        out["beta_63d"] = pd.concat(betas)  # index-aligned assignment
    else:
        out["mkt_ret_1d"] = np.nan
        out["mkt_ret_21d"] = np.nan
        out["beta_63d"] = np.nan

    # Market-neutral residual labels: what the stock did beyond its beta
    # exposure to the market move. Removes the market-noise component that
    # dominates raw returns, so models learn stock selection, not beta.
    for h in horizons:
        fwd_col = f"label_mkt_fwd_ret_{h}d"
        if fwd_col in out.columns:
            out[f"label_fwd_resid_ret_{h}d"] = (
                out[f"label_fwd_log_ret_{h}d"] - out["beta_63d"].fillna(1.0) * out[fwd_col]
            )

    # Sector-relative 21d return.
    out["sector_rel_ret_21d"] = np.nan
    if sector_map and sector_returns is not None and not sector_returns.empty:
        etf_ret = sector_returns.rename(
            columns={"ticker": "sector_etf", "ret_21d": "sector_ret_21d"}
        )
        out["sector_etf"] = out["ticker"].map(sector_map)
        out = out.merge(etf_ret, on=["date", "sector_etf"], how="left")
        out["sector_rel_ret_21d"] = out["ret_21d"] - out["sector_ret_21d"]
        out = out.drop(columns=["sector_etf", "sector_ret_21d"], errors="ignore")

    return out
