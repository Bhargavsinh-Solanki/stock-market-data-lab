"""Worldwide macro ingestion from the World Bank open data API.

https://api.worldbank.org — free, open, no API key. Annual country-level
series (inflation, GDP growth) across continents; they enter the feature
panel as slow-moving regime context via forward-fill.

series_id convention: WB_<indicator with dots as underscores>_<ISO3>,
e.g. WB_FP_CPI_TOTL_ZG_CHN.
"""
from __future__ import annotations

from datetime import date
from typing import Any

import duckdb
import pandas as pd

from src.config.settings import WORLD_BANK_COUNTRIES, WORLD_BANK_INDICATORS, get_settings
from src.db.engine import insert_ignore_df
from src.ingestion.base import IngestionResult, store_raw_event, utcnow
from src.utils.http import ComplianceError, RateLimitedClient
from src.utils.logging import get_logger

logger = get_logger(__name__)
SOURCE = "world_bank"
API_URL = "https://api.worldbank.org/v2/country/{countries}/indicator/{indicator}"
FIRST_YEAR = 2014


def parse_wb_json(payload: Any, indicator: str) -> pd.DataFrame:
    """Parse a World Bank v2 JSON response into macro_daily rows (pure).

    Payload shape: [meta, [{country: {id}, date: 'YYYY', value: ...}, ...]].
    Annual values are dated to Dec 31 of their year — the earliest moment the
    full-year figure could conceivably be known — so forward-fill onto the
    trading calendar can never leak a year's value into that same year.
    """
    if not isinstance(payload, list) or len(payload) < 2 or not payload[1]:
        return pd.DataFrame()
    ind_key = indicator.replace(".", "_")
    rows = []
    for obs in payload[1]:
        value = obs.get("value")
        year = obs.get("date")
        # countryiso3code is authoritative; country.id is the 2-letter code
        iso3 = (obs.get("countryiso3code")
                or (obs.get("country") or {}).get("id") or "").upper()
        if value is None or not year or not str(year).isdigit() or not iso3:
            continue
        rows.append({
            "series_id": f"WB_{ind_key}_{iso3}",
            "date": date(int(year), 12, 31),
            "value": float(value),
            "source": SOURCE,
            "retrieved_at": utcnow(),
        })
    return pd.DataFrame(rows)


def run(
    con: duckdb.DuckDBPyConnection,
    indicators: list[str] | None = None,
    countries: list[str] | None = None,
) -> IngestionResult:
    settings = get_settings()
    result = IngestionResult(source=SOURCE)
    if not settings.enable_world_bank:
        logger.info("World Bank ingestion disabled via settings; skipping.")
        return result

    indicators = indicators or WORLD_BANK_INDICATORS
    countries = countries or WORLD_BANK_COUNTRIES
    country_str = ";".join(countries)

    with RateLimitedClient(rate_limit_seconds=1.0) as client:
        for indicator in indicators:
            url = API_URL.format(countries=country_str, indicator=indicator)
            params = {"format": "json", "per_page": 2000,
                      "date": f"{FIRST_YEAR}:{date.today().year}"}
            try:
                resp = client.get(url, params=params)
            except ComplianceError as exc:
                logger.warning("%s", exc)
                result.errors.append(str(exc))
                return result
            except Exception as exc:  # noqa: BLE001
                logger.warning("World Bank fetch failed for %s: %s", indicator, exc)
                result.errors.append(f"{indicator}: {exc}")
                continue

            store_raw_event(con, SOURCE, url, resp.text)
            try:
                rows = parse_wb_json(resp.json(), indicator)
            except ValueError as exc:
                result.errors.append(f"{indicator}: bad JSON ({exc})")
                continue
            if rows.empty:
                continue
            result.fetched += len(rows)
            inserted = insert_ignore_df(con, "macro_daily", rows)
            result.inserted += inserted
            result.skipped_duplicates += len(rows) - inserted

    logger.info(result.summary())
    return result
