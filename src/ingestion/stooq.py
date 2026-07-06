"""Stooq daily price ingestion (stooq.com) — independent second price source.

Stooq offers free public CSV downloads of daily OHLCV for global indices and
equities (no login, no key). We use it to cross-check yfinance and gap-fill
global index history: rows land in the same prices_daily table under the
canonical ticker, and the (ticker, date) primary key means whichever source
loaded a bar first wins — the second source only fills holes.

Endpoint: https://stooq.com/q/d/l/?s=<symbol>&i=d[&d1=YYYYMMDD]
"""
from __future__ import annotations

import io
from datetime import date, timedelta

import duckdb
import pandas as pd

from src.config.settings import STOOQ_INDEX_SYMBOLS, get_settings
from src.db.engine import insert_ignore_df
from src.ingestion.base import IngestionResult, store_raw_event, utcnow
from src.utils.http import ComplianceError, RateLimitedClient
from src.utils.logging import get_logger

logger = get_logger(__name__)
SOURCE = "stooq"
CSV_URL = "https://stooq.com/q/d/l/"
HISTORY_START = date(2015, 1, 1)


def parse_stooq_csv(text: str, ticker: str) -> pd.DataFrame:
    """Parse a Stooq daily CSV into prices_daily rows (pure function).

    Stooq CSV header: Date,Open,High,Low,Close,Volume (Volume may be absent
    for indices). Returns an empty frame for 'No data' responses.
    """
    if not text or not text.lower().startswith("date"):
        return pd.DataFrame()
    df = pd.read_csv(io.StringIO(text))
    df.columns = [c.strip().lower() for c in df.columns]
    if "close" not in df.columns or df.empty:
        return pd.DataFrame()
    out = pd.DataFrame({
        "ticker": ticker,
        "date": pd.to_datetime(df["date"], errors="coerce").dt.date,
        "open": pd.to_numeric(df.get("open"), errors="coerce"),
        "high": pd.to_numeric(df.get("high"), errors="coerce"),
        "low": pd.to_numeric(df.get("low"), errors="coerce"),
        "close": pd.to_numeric(df["close"], errors="coerce"),
    })
    # Stooq prices are unadjusted for indices (no dividends apply); for
    # equities prefer yfinance rows, which carry proper adjustments.
    out["adj_close"] = out["close"]
    vol = pd.to_numeric(df.get("volume"), errors="coerce") if "volume" in df.columns else None
    out["volume"] = (vol.fillna(0).astype("int64") if vol is not None else 0)
    out["source"] = SOURCE
    out["retrieved_at"] = utcnow()
    return out.dropna(subset=["date", "adj_close"])


def run(
    con: duckdb.DuckDBPyConnection, symbols: dict[str, str] | None = None
) -> IngestionResult:
    settings = get_settings()
    result = IngestionResult(source=SOURCE)
    if not settings.enable_stooq:
        logger.info("Stooq ingestion disabled via settings; skipping.")
        return result

    symbols = symbols or STOOQ_INDEX_SYMBOLS
    last = {
        r[0]: r[1]
        for r in con.execute(
            "SELECT ticker, max(date) FROM prices_daily WHERE ticker IN "
            f"({','.join('?' * len(symbols))}) GROUP BY ticker",
            list(symbols),
        ).fetchall()
    }

    with RateLimitedClient() as client:
        for ticker, stooq_symbol in symbols.items():
            start = last.get(ticker)
            params = {"s": stooq_symbol, "i": "d"}
            if start:
                if start >= date.today():
                    continue
                params["d1"] = (start + timedelta(days=1)).strftime("%Y%m%d")
            else:
                params["d1"] = HISTORY_START.strftime("%Y%m%d")
            try:
                resp = client.get(CSV_URL, params=params)
            except ComplianceError as exc:
                logger.warning("%s", exc)
                result.errors.append(str(exc))
                return result
            except Exception as exc:  # noqa: BLE001
                logger.warning("Stooq fetch failed for %s (%s): %s", ticker, stooq_symbol, exc)
                result.errors.append(f"{ticker}: {exc}")
                continue

            store_raw_event(con, SOURCE, f"{CSV_URL}?s={stooq_symbol}", resp.text)
            df = parse_stooq_csv(resp.text, ticker)
            if df.empty:
                logger.info("Stooq returned no rows for %s (%s)", ticker, stooq_symbol)
                continue
            result.fetched += len(df)
            inserted = insert_ignore_df(con, "prices_daily", df)
            result.inserted += inserted
            result.skipped_duplicates += len(df) - inserted

    logger.info(result.summary())
    return result
