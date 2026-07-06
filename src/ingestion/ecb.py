"""Euro-area macro ingestion from the official ECB Data Portal.

https://data-api.ecb.europa.eu — free, no API key, explicitly public. We use
the SDMX REST API with `format=csvdata`, the simplest machine-readable form.
Series land in macro_daily under canonical ids (ECB_EURUSD, ECB_MRO_RATE, ...).
"""
from __future__ import annotations

import io
from datetime import date

import duckdb
import pandas as pd

from src.config.settings import ECB_SERIES, get_settings
from src.db.engine import insert_ignore_df
from src.ingestion.base import IngestionResult, store_raw_event, utcnow
from src.utils.http import ComplianceError, RateLimitedClient
from src.utils.logging import get_logger

logger = get_logger(__name__)
SOURCE = "ecb"
API_URL = "https://data-api.ecb.europa.eu/service/data/{flow}/{key}"
HISTORY_START = "2015-01-01"


def parse_ecb_csv(text: str, series_id: str) -> pd.DataFrame:
    """Parse an ECB SDMX csvdata response into macro_daily rows (pure).

    Relevant columns: TIME_PERIOD (date or period), OBS_VALUE (float).
    Monthly/quarterly periods (e.g. '2026-05') parse to the period start.
    """
    if not text or "TIME_PERIOD" not in text:
        return pd.DataFrame()
    df = pd.read_csv(io.StringIO(text))
    if "TIME_PERIOD" not in df.columns or "OBS_VALUE" not in df.columns:
        return pd.DataFrame()
    out = pd.DataFrame({
        "series_id": series_id,
        "date": pd.to_datetime(df["TIME_PERIOD"], errors="coerce").dt.date,
        "value": pd.to_numeric(df["OBS_VALUE"], errors="coerce"),
        "source": SOURCE,
        "retrieved_at": utcnow(),
    })
    return out.dropna(subset=["date", "value"])


def run(
    con: duckdb.DuckDBPyConnection,
    series: list[tuple[str, str, str]] | None = None,
) -> IngestionResult:
    settings = get_settings()
    result = IngestionResult(source=SOURCE)
    if not settings.enable_ecb:
        logger.info("ECB ingestion disabled via settings; skipping.")
        return result

    series = series or ECB_SERIES
    last = {
        r[0]: r[1]
        for r in con.execute(
            "SELECT series_id, max(date) FROM macro_daily WHERE source = ? GROUP BY series_id",
            [SOURCE],
        ).fetchall()
    }

    with RateLimitedClient() as client:
        for flow, key, series_id in series:
            url = API_URL.format(flow=flow, key=key)
            start = last.get(series_id)
            params = {
                "format": "csvdata",
                "startPeriod": start.isoformat() if start else HISTORY_START,
            }
            try:
                resp = client.get(url, params=params)
            except ComplianceError as exc:
                logger.warning("%s", exc)
                result.errors.append(str(exc))
                return result
            except Exception as exc:  # noqa: BLE001
                logger.warning("ECB fetch failed for %s: %s", series_id, exc)
                result.errors.append(f"{series_id}: {exc}")
                continue

            store_raw_event(con, SOURCE, f"{url}?startPeriod={params['startPeriod']}", resp.text)
            rows = parse_ecb_csv(resp.text, series_id)
            if rows.empty:
                continue
            result.fetched += len(rows)
            inserted = insert_ignore_df(con, "macro_daily", rows)
            result.inserted += inserted
            result.skipped_duplicates += len(rows) - inserted

    logger.info(result.summary())
    return result
