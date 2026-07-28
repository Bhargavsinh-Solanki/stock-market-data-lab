"""Feature-build orchestrator: reads normalized tables, computes all feature
blocks, joins them, attaches forward labels, and writes features_daily and
features_weekly (last trading day of each ISO week)."""
from __future__ import annotations

import numpy as np
import pandas as pd

from src.config.settings import SECTOR_ETFS, get_settings
from src.db.engine import get_connection, read_df, table_exists
from src.features.macro_features import compute_macro_features, compute_market_context
from src.features.political_features import compute_political_features
from src.features.price_features import compute_price_features
from src.ingestion.market_prices import CONTEXT_TICKERS
from src.utils.logging import get_logger

logger = get_logger(__name__)


def _sector_map(con) -> dict[str, str]:
    df = read_df(con, "SELECT ticker, sector FROM securities_master WHERE sector IS NOT NULL")
    return {
        r.ticker: SECTOR_ETFS[r.sector]
        for r in df.itertuples()
        if r.sector in SECTOR_ETFS
    }


def build_features(write: bool = True) -> pd.DataFrame:
    settings = get_settings()
    con = get_connection()
    try:
        prices = read_df(
            con,
            "SELECT ticker, date, adj_close, volume FROM prices_daily ORDER BY ticker, date",
        )
        if prices.empty:
            raise RuntimeError("prices_daily is empty — run daily ingestion first.")
        prices["date"] = pd.to_datetime(prices["date"])

        context_prices = prices[prices["ticker"].isin(CONTEXT_TICKERS)]
        equity_prices = prices[~prices["ticker"].isin(CONTEXT_TICKERS)]

        # --- market / sector context ---
        market_ctx = compute_market_context(context_prices)
        spy = context_prices[context_prices["ticker"] == "SPY"].sort_values("date")
        log_spy = np.log(spy["adj_close"])
        market_returns = pd.DataFrame({
            "date": spy["date"].values,
            "mkt_ret_1d": log_spy.diff(1).values,
            "mkt_ret_21d": log_spy.diff(21).values,
        })
        # Forward market returns feed the market-neutral residual labels;
        # they get the label_ prefix inside compute_price_features.
        for h in sorted({settings.label_horizon_days, 21}):
            market_returns[f"mkt_fwd_ret_{h}d"] = (log_spy.shift(-h) - log_spy).values
        etfs = sorted(set(SECTOR_ETFS.values()))
        sector_rets = []
        for etf in etfs:
            s = context_prices[context_prices["ticker"] == etf].sort_values("date")
            if s.empty:
                continue
            sector_rets.append(pd.DataFrame({
                "date": s["date"].values, "ticker": etf,
                "ret_21d": np.log(s["adj_close"]).diff(21).values,
            }))
        sector_returns = pd.concat(sector_rets, ignore_index=True) if sector_rets else None

        # --- price/technical + labels ---
        feats = compute_price_features(
            equity_prices,
            market_returns=market_returns,
            sector_map=_sector_map(con),
            sector_returns=sector_returns,
            horizon=settings.label_horizon_days,
        )

        # --- political flow (point-in-time on published_date) ---
        trades = (
            read_df(con, "SELECT * FROM political_trades")
            if table_exists(con, "political_trades") else pd.DataFrame()
        )
        pol = compute_political_features(trades, feats[["ticker", "date"]])
        feats = feats.merge(pol, on=["ticker", "date"], how="left")

        # --- macro context ---
        macro = (
            read_df(con, "SELECT series_id, date, value FROM macro_daily")
            if table_exists(con, "macro_daily") else pd.DataFrame()
        )
        macro_feats = compute_macro_features(macro, feats["date"])
        feats = feats.merge(macro_feats, on="date", how="left")
        feats = feats.merge(market_ctx, on="date", how="left")

        feats = feats.sort_values(["ticker", "date"]).reset_index(drop=True)

        if write:
            con.register("_feats", feats)
            con.execute("CREATE OR REPLACE TABLE features_daily AS SELECT * FROM _feats")
            weekly = last_trading_day_per_week(feats)
            con.register("_weekly", weekly)
            con.execute("CREATE OR REPLACE TABLE features_weekly AS SELECT * FROM _weekly")
            con.unregister("_feats")
            con.unregister("_weekly")
            logger.info(
                "Wrote features_daily (%d rows) and features_weekly (%d rows)",
                len(feats), len(weekly),
            )
        return feats
    finally:
        con.close()


def last_trading_day_per_week(feats: pd.DataFrame) -> pd.DataFrame:
    """Keep the last available trading day per (ticker, ISO week)."""
    df = feats.copy()
    iso = df["date"].dt.isocalendar()
    df["_week_key"] = iso["year"].astype(str) + "-" + iso["week"].astype(str).str.zfill(2)
    idx = df.groupby(["ticker", "_week_key"])["date"].idxmax()
    return df.loc[idx].drop(columns="_week_key").sort_values(["ticker", "date"]).reset_index(drop=True)


FEATURE_EXCLUDE = {"ticker", "date"}


def feature_columns(df: pd.DataFrame) -> list[str]:
    """All numeric model inputs: excludes keys, label_* targets, and columns
    with no observed values (e.g. sector-relative return before sector data
    is populated)."""
    return [
        c for c in df.columns
        if c not in FEATURE_EXCLUDE
        and not c.startswith("label_")
        and pd.api.types.is_numeric_dtype(df[c])
        and df[c].notna().any()
    ]
