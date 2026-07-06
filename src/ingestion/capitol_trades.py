"""CapitolTrades ingestion.

Compliance notes
----------------
* Uses the public, unauthenticated JSON endpoint that backs capitoltrades.com.
  No login, CAPTCHA, paywall or anti-bot measure is bypassed.
* robots.txt is checked before every request (see RateLimitedClient) and the
  job aborts politely if disallowed.
* Requests are rate limited (default 1 request / 2s) and identify themselves
  via a User-Agent containing a contact email.
* Every raw response is stored in raw_source_events with URL + timestamp.
* The official House/Senate ingesters remain the sources of record; disable
  this source at any time with ENABLE_CAPITOL_TRADES=false.
"""
from __future__ import annotations

import json
from datetime import date, datetime
from typing import Any

import duckdb
import pandas as pd

from src.config.settings import get_settings
from src.db.engine import insert_ignore_df, upsert_df
from src.ingestion.base import IngestionResult, store_raw_event, utcnow
from src.processing.normalize import (
    normalize_owner,
    normalize_ticker,
    normalize_tx_type,
    parse_size_range,
    size_midpoint,
)
from src.utils.hashing import stable_hash
from src.utils.http import ComplianceError, RateLimitedClient
from src.utils.logging import get_logger

logger = get_logger(__name__)
API_URL = "https://bff.capitoltrades.com/trades"
SOURCE = "capitol_trades"


def _parse_date(raw: Any) -> date | None:
    if raw in (None, "", "N/A"):
        return None
    try:
        return datetime.fromisoformat(str(raw).replace("Z", "+00:00")).date()
    except ValueError:
        return None


def parse_trade(record: dict[str, Any]) -> dict[str, Any]:
    """Normalize one CapitolTrades API record. Pure function (unit-tested)."""
    politician = record.get("politician") or {}
    issuer = record.get("issuer") or {}

    first = (politician.get("firstName") or "").strip()
    last = (politician.get("lastName") or "").strip()
    politician_name = " ".join(p for p in (first, last) if p) or None
    politician_id = str(record.get("_politicianId") or politician.get("_politicianId") or "")
    party = (politician.get("party") or "").lower() or None
    chamber = (politician.get("chamber") or "").lower() or None
    state = (politician.get("_stateId") or "").upper() or None

    ticker = normalize_ticker(issuer.get("issuerTicker") or record.get("asset", {}).get("assetTicker"))
    size_min, size_max = parse_size_range(record.get("size"))
    exact_value = record.get("value")
    mid = size_midpoint(size_min, size_max, exact_value if isinstance(exact_value, (int, float)) else None)

    traded = _parse_date(record.get("txDate"))
    published = _parse_date(record.get("pubDate"))
    filed_after = record.get("filedAfterDays")
    if filed_after is None and traded and published:
        filed_after = (published - traded).days

    tx_type = normalize_tx_type(record.get("txType"))
    owner = normalize_owner(record.get("owner"))

    trade_hash = stable_hash(
        SOURCE, politician_id or politician_name, ticker, issuer.get("issuerName"),
        tx_type, owner, record.get("size"), traded, published,
    )
    return {
        "trade_hash": trade_hash,
        "source": SOURCE,
        "source_url": API_URL,
        "retrieved_at": utcnow(),
        "politician_id": politician_id or stable_hash("pol", politician_name)[:16],
        "politician_name": politician_name,
        "party": party,
        "chamber": chamber,
        "state": state,
        "issuer_name": issuer.get("issuerName"),
        "ticker": ticker,
        "tx_type": tx_type,
        "owner": owner,
        "size_range": record.get("size"),
        "size_min": size_min,
        "size_max": size_max,
        "size_mid": mid,
        "traded_date": traded,
        "published_date": published,
        "filed_after_days": filed_after,
    }


def _upsert_dimensions(con: duckdb.DuckDBPyConnection, trades: pd.DataFrame) -> None:
    now = utcnow()
    pols = (
        trades.dropna(subset=["politician_id"])
        .drop_duplicates("politician_id")
        .assign(first_seen_at=now, updated_at=now)
        .rename(columns={"politician_name": "full_name"})
        [["politician_id", "full_name", "party", "chamber", "state", "first_seen_at", "updated_at"]]
    )
    insert_ignore_df(con, "politicians", pols)

    issuers = (
        trades.dropna(subset=["issuer_name"])
        .drop_duplicates("issuer_name")
        .assign(
            issuer_id=lambda d: d["issuer_name"].map(lambda n: stable_hash("issuer", n)[:20]),
            sector=None, country=None, updated_at=now,
        )
        [["issuer_id", "issuer_name", "ticker", "sector", "country", "updated_at"]]
    )
    insert_ignore_df(con, "issuers", issuers)


def run(con: duckdb.DuckDBPyConnection, max_pages: int | None = None) -> IngestionResult:
    """Fetch recent trades incrementally. Stops early once a full page of
    already-seen trades is encountered."""
    settings = get_settings()
    result = IngestionResult(source=SOURCE)
    if not settings.enable_capitol_trades:
        logger.info("CapitolTrades ingestion disabled via settings; skipping.")
        return result

    pages = max_pages or settings.capitol_trades_pages
    known: set[str] = {
        r[0] for r in con.execute(
            "SELECT trade_hash FROM political_trades WHERE source = ?", [SOURCE]
        ).fetchall()
    }

    with RateLimitedClient() as client:
        for page in range(1, pages + 1):
            params = {"page": page, "pageSize": settings.capitol_trades_page_size}
            try:
                resp = client.get(API_URL, params=params)
            except ComplianceError as exc:
                logger.warning("%s", exc)
                result.errors.append(str(exc))
                return result
            except Exception as exc:  # noqa: BLE001 - log and continue to next run
                logger.error("Fetch failed on page %d: %s", page, exc)
                result.errors.append(f"page {page}: {exc}")
                break

            store_raw_event(con, SOURCE, f"{API_URL}?page={page}", resp.text)
            try:
                records = resp.json().get("data", [])
            except json.JSONDecodeError as exc:
                result.errors.append(f"page {page}: bad JSON ({exc})")
                continue
            if not records:
                break

            parsed = [parse_trade(r) for r in records]
            result.fetched += len(parsed)
            fresh = [t for t in parsed if t["trade_hash"] not in known]
            result.skipped_duplicates += len(parsed) - len(fresh)

            if fresh:
                df = pd.DataFrame(fresh)
                result.inserted += insert_ignore_df(con, "political_trades", df)
                _upsert_dimensions(con, df)
                known.update(t["trade_hash"] for t in fresh)
            elif page > 1:
                logger.info("Page %d fully duplicated; stopping incremental fetch.", page)
                break

    logger.info(result.summary())
    return result
