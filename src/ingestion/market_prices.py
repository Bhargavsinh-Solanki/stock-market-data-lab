"""Daily OHLCV ingestion via yfinance (Yahoo Finance).

Incremental: for each ticker we only request bars after the last stored date.
Raw payload summaries are logged to raw_source_events for audit. yfinance is
suitable for research use; for production-grade SLAs swap in a licensed feed
(Polygon, Tiingo, EODHD...) behind the same interface.
"""
from __future__ import annotations

import json
from datetime import date, timedelta

import duckdb
import pandas as pd

from src.config.settings import (
    DEFAULT_UNIVERSE,
    GLOBAL_ADR_UNIVERSE,
    INDEX_TICKERS,
    SECTOR_ETFS,
    get_settings,
)
from src.db.engine import insert_ignore_df, table_exists
from src.ingestion.base import IngestionResult, store_raw_event, utcnow
from src.utils.logging import get_logger

logger = get_logger(__name__)
SOURCE = "yfinance"
HISTORY_START = "2015-01-01"
CONTEXT_TICKERS = ["SPY", "QQQ", "IWM"] + sorted(set(SECTOR_ETFS.values())) + INDEX_TICKERS


def build_universe(con: duckdb.DuckDBPyConnection) -> list[str]:
    """Default universe + tickers observed in political trades (if enabled)."""
    settings = get_settings()
    tickers = set(DEFAULT_UNIVERSE)
    if settings.include_global_adrs:
        tickers.update(GLOBAL_ADR_UNIVERSE)
    if settings.auto_expand_universe and table_exists(con, "political_trades"):
        rows = con.execute(
            "SELECT DISTINCT ticker FROM political_trades WHERE ticker IS NOT NULL"
        ).fetchall()
        tickers.update(r[0] for r in rows)
    universe = sorted(tickers)[: settings.max_universe_size]
    return universe + [t for t in CONTEXT_TICKERS if t not in universe]


def _last_dates(con: duckdb.DuckDBPyConnection) -> dict[str, date]:
    rows = con.execute("SELECT ticker, max(date) FROM prices_daily GROUP BY ticker").fetchall()
    return {r[0]: r[1] for r in rows if r[1] is not None}


def _normalize_download(raw: pd.DataFrame, ticker: str) -> pd.DataFrame:
    if raw is None or raw.empty:
        return pd.DataFrame()
    df = raw.copy()
    if isinstance(df.columns, pd.MultiIndex):  # yf batch shape
        df.columns = df.columns.get_level_values(0)
    df = df.reset_index().rename(
        columns={
            "Date": "date", "Open": "open", "High": "high", "Low": "low",
            "Close": "close", "Adj Close": "adj_close", "Volume": "volume",
        }
    )
    if "adj_close" not in df.columns:  # auto_adjust=True: Close is adjusted
        df["adj_close"] = df["close"]
    df["ticker"] = ticker
    df["date"] = pd.to_datetime(df["date"]).dt.date
    df["source"] = SOURCE
    df["retrieved_at"] = utcnow()
    df = df.dropna(subset=["adj_close"])
    df["volume"] = df["volume"].fillna(0).astype("int64")
    cols = ["ticker", "date", "open", "high", "low", "close", "adj_close",
            "volume", "source", "retrieved_at"]
    return df[cols]


def _update_securities_master(con: duckdb.DuckDBPyConnection, tickers: list[str]) -> None:
    known = {r[0] for r in con.execute("SELECT ticker FROM securities_master").fetchall()}
    new = [t for t in tickers if t not in known]
    if not new:
        return
    rows = []
    for t in new:
        asset_type = "index" if t.startswith("^") else ("etf" if t in CONTEXT_TICKERS else "equity")
        rows.append(
            {"ticker": t, "name": t, "sector": None, "industry": None,
             "exchange": None, "currency": "USD", "asset_type": asset_type,
             "is_active": True, "updated_at": utcnow()}
        )
    insert_ignore_df(con, "securities_master", pd.DataFrame(rows))


def run(con: duckdb.DuckDBPyConnection, tickers: list[str] | None = None) -> IngestionResult:
    import yfinance as yf  # imported lazily so tests don't require it

    result = IngestionResult(source=SOURCE)
    tickers = tickers or build_universe(con)
    _update_securities_master(con, tickers)
    last_dates = _last_dates(con)
    today = date.today()

    for ticker in tickers:
        start = last_dates.get(ticker)
        start_str = (start + timedelta(days=1)).isoformat() if start else HISTORY_START
        if start and start >= today:
            continue
        try:
            raw = yf.download(
                ticker, start=start_str, auto_adjust=False,
                progress=False, threads=False,
            )
            df = _normalize_download(raw, ticker)
            if df.empty:
                continue
            result.fetched += len(df)
            inserted = insert_ignore_df(con, "prices_daily", df)
            result.inserted += inserted
            result.skipped_duplicates += len(df) - inserted
            store_raw_event(
                con, SOURCE, f"yfinance://{ticker}?start={start_str}",
                json.dumps({"ticker": ticker, "rows": len(df),
                            "first": str(df['date'].min()), "last": str(df['date'].max())}),
            )
        except Exception as exc:  # noqa: BLE001 - a bad/delisted ticker must not kill the run
            logger.warning("Price fetch failed for %s: %s", ticker, exc)
            result.errors.append(f"{ticker}: {exc}")

    logger.info(result.summary())
    return result
