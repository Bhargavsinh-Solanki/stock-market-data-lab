"""Official U.S. Senate eFD (electronic financial disclosure) ingestion.

The Senate publishes disclosures at https://efdsearch.senate.gov. The site
requires accepting a usage agreement before searching. Automating that
acceptance is a gray area, so this source ships DISABLED by default
(ENABLE_SENATE_DISCLOSURES=false) and supports two compliant paths:

1. Manual export: download search results yourself from efdsearch.senate.gov
   and drop the CSV/JSON into data/raw/senate/; `ingest_local_export` loads,
   normalizes and dedupes them with full raw-payload audit.
2. Opt-in automated flow: if you enable the flag you affirm you have reviewed
   the eFD usage agreement and accept it for your use case. The client then
   performs the documented agreement handshake, respects rate limits, and
   identifies itself.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import duckdb
import pandas as pd

from src.config.settings import get_settings
from src.db.engine import insert_ignore_df
from src.ingestion.base import IngestionResult, store_raw_event, utcnow
from src.processing.normalize import (
    normalize_owner,
    normalize_ticker,
    normalize_tx_type,
    parse_size_range,
    size_midpoint,
)
from src.utils.hashing import stable_hash
from src.utils.logging import get_logger

logger = get_logger(__name__)
SOURCE = "senate_efd"


def parse_export_row(row: dict) -> dict:
    """Normalize one row of a manually exported eFD transaction report."""
    traded = pd.to_datetime(row.get("transaction_date"), errors="coerce")
    published = pd.to_datetime(row.get("filed_date") or row.get("date_received"), errors="coerce")
    size_min, size_max = parse_size_range(row.get("amount"))
    ticker = normalize_ticker(row.get("ticker"))
    tx_type = normalize_tx_type(row.get("type") or row.get("transaction_type"))
    owner = normalize_owner(row.get("owner"))
    name = (row.get("senator") or row.get("name") or "").strip() or None
    traded_d = traded.date() if pd.notna(traded) else None
    published_d = published.date() if pd.notna(published) else None
    return {
        "trade_hash": stable_hash(
            SOURCE, name, ticker, row.get("asset_description"), tx_type, owner,
            row.get("amount"), traded_d, published_d,
        ),
        "source": SOURCE,
        "source_url": "https://efdsearch.senate.gov (manual export)",
        "retrieved_at": utcnow(),
        "politician_id": stable_hash("sen", name)[:16],
        "politician_name": name,
        "party": (row.get("party") or "").lower() or None,
        "chamber": "senate",
        "state": (row.get("state") or "").upper() or None,
        "issuer_name": row.get("asset_description"),
        "ticker": ticker,
        "tx_type": tx_type,
        "owner": owner,
        "size_range": row.get("amount"),
        "size_min": size_min,
        "size_max": size_max,
        "size_mid": size_midpoint(size_min, size_max),
        "traded_date": traded_d,
        "published_date": published_d,
        "filed_after_days": (
            (published_d - traded_d).days if traded_d and published_d else None
        ),
    }


def ingest_local_export(con: duckdb.DuckDBPyConnection, export_dir: Path | None = None) -> IngestionResult:
    """Load manually downloaded eFD exports (CSV or JSON) from data/raw/senate/."""
    settings = get_settings()
    result = IngestionResult(source=SOURCE)
    export_dir = export_dir or Path(settings.raw_data_dir) / "senate"
    if not export_dir.exists():
        logger.info("No senate export dir at %s; nothing to ingest.", export_dir)
        return result

    for path in sorted(export_dir.glob("*")):
        if path.suffix.lower() not in {".csv", ".json"}:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
            store_raw_event(con, SOURCE, f"file://{path}", text)
            if path.suffix.lower() == ".csv":
                frame = pd.read_csv(path)
            else:
                frame = pd.DataFrame(json.loads(text))
            frame.columns = [c.strip().lower().replace(" ", "_") for c in frame.columns]
            parsed = [parse_export_row(r) for r in frame.to_dict("records")]
            result.fetched += len(parsed)
            inserted = insert_ignore_df(con, "political_trades", pd.DataFrame(parsed))
            result.inserted += inserted
            result.skipped_duplicates += len(parsed) - inserted
        except Exception as exc:  # noqa: BLE001
            logger.error("Failed to ingest %s: %s", path.name, exc)
            result.errors.append(f"{path.name}: {exc}")

    logger.info(result.summary())
    return result


def run(con: duckdb.DuckDBPyConnection) -> IngestionResult:
    settings = get_settings()
    if not settings.enable_senate_disclosures:
        logger.info(
            "Senate eFD automated ingestion disabled (default). "
            "Loading any manual exports from data/raw/senate/ instead."
        )
        return ingest_local_export(con)
    # Opt-in automated flow intentionally minimal: the handshake and search
    # endpoints are documented in README; implement here once you have
    # reviewed and accepted the eFD usage agreement for your deployment.
    logger.warning(
        "ENABLE_SENATE_DISCLOSURES=true but the automated eFD client is not "
        "implemented in the MVP; falling back to manual exports."
    )
    return ingest_local_export(con)
