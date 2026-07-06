"""Macro data ingestion from FRED (official St. Louis Fed API).

Requires a free API key: https://fred.stlouisfed.org/docs/api/api_key.html
Set FRED_API_KEY in .env. The job is skipped gracefully when unset.
"""
from __future__ import annotations

from datetime import date

import duckdb
import pandas as pd

from src.config.settings import FRED_SERIES, get_settings
from src.db.engine import insert_ignore_df
from src.ingestion.base import IngestionResult, store_raw_event, utcnow
from src.utils.http import RateLimitedClient
from src.utils.logging import get_logger

logger = get_logger(__name__)
SOURCE = "fred"
API_URL = "https://api.stlouisfed.org/fred/series/observations"
HISTORY_START = "2015-01-01"


def run(con: duckdb.DuckDBPyConnection, series: list[str] | None = None) -> IngestionResult:
    settings = get_settings()
    result = IngestionResult(source=SOURCE)
    if not settings.fred_api_key:
        logger.info("FRED_API_KEY not set; skipping macro ingestion.")
        return result

    series = series or FRED_SERIES
    last = {
        r[0]: r[1]
        for r in con.execute(
            "SELECT series_id, max(date) FROM macro_daily GROUP BY series_id"
        ).fetchall()
    }

    with RateLimitedClient(rate_limit_seconds=0.6) as client:
        for series_id in series:
            start = last.get(series_id)
            start_str = start.isoformat() if start else HISTORY_START
            try:
                resp = client.get(
                    API_URL,
                    params={
                        "series_id": series_id,
                        "api_key": settings.fred_api_key,
                        "file_type": "json",
                        "observation_start": start_str,
                    },
                )
                store_raw_event(con, SOURCE, f"{API_URL}?series_id={series_id}", resp.text)
                obs = resp.json().get("observations", [])
                rows = [
                    {
                        "series_id": series_id,
                        "date": pd.to_datetime(o["date"]).date(),
                        "value": float(o["value"]),
                        "source": SOURCE,
                        "retrieved_at": utcnow(),
                    }
                    for o in obs
                    if o.get("value") not in (".", None, "")
                ]
                result.fetched += len(rows)
                if rows:
                    inserted = insert_ignore_df(con, "macro_daily", pd.DataFrame(rows))
                    result.inserted += inserted
                    result.skipped_duplicates += len(rows) - inserted
            except Exception as exc:  # noqa: BLE001
                logger.warning("FRED fetch failed for %s: %s", series_id, exc)
                result.errors.append(f"{series_id}: {exc}")

    logger.info(result.summary())
    return result
