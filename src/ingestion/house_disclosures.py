"""Official U.S. House financial disclosure ingestion (source of record).

The House Clerk publishes yearly financial-disclosure indexes as public ZIP
downloads — an explicitly permitted, official source:

    https://disclosures-clerk.house.gov/public_disc/financial-pdfs/{YEAR}FD.zip

The ZIP contains an XML/TXT index of every filing (member, filing type,
filing date, DocID). Periodic Transaction Reports (type 'P') are the filings
that contain individual trades. The transactions themselves live in PDFs;
this MVP ingests the authoritative filing index (useful for disclosure-delay
features and cross-validation of CapitolTrades) and stores raw payloads for
audit. PDF transaction extraction is a documented Phase-2+ extension.
"""
from __future__ import annotations

import io
import zipfile
from datetime import date, datetime
from xml.etree import ElementTree

import duckdb
import pandas as pd

from src.config.settings import get_settings
from src.db.engine import insert_ignore_df
from src.ingestion.base import IngestionResult, store_raw_event, utcnow
from src.utils.hashing import stable_hash
from src.utils.http import ComplianceError, RateLimitedClient
from src.utils.logging import get_logger

logger = get_logger(__name__)
SOURCE = "house_clerk"
INDEX_URL = "https://disclosures-clerk.house.gov/public_disc/financial-pdfs/{year}FD.zip"
PTR_PDF_URL = "https://disclosures-clerk.house.gov/public_disc/ptr-pdfs/{year}/{doc_id}.pdf"


def _parse_filing_date(raw: str | None) -> date | None:
    if not raw:
        return None
    for fmt in ("%m/%d/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(raw.strip(), fmt).date()
        except ValueError:
            continue
    return None


def parse_index_xml(xml_bytes: bytes, year: int) -> pd.DataFrame:
    """Parse the Clerk's {year}FD.xml index into filing rows (pure function)."""
    root = ElementTree.fromstring(xml_bytes)
    rows: list[dict] = []
    for member in root.iter("Member"):
        get = lambda tag: (member.findtext(tag) or "").strip()  # noqa: E731
        doc_id = get("DocID")
        filing_type = get("FilingType")
        filing_date = _parse_filing_date(get("FilingDate"))
        full_name = " ".join(p for p in (get("First"), get("Last")) if p)
        rows.append(
            {
                "filing_hash": stable_hash(SOURCE, year, doc_id, filing_type, full_name),
                "doc_id": doc_id,
                "year": year,
                "full_name": full_name,
                "state_district": get("StateDst"),
                "filing_type": filing_type,  # 'P' = Periodic Transaction Report
                "filing_date": filing_date,
                "pdf_url": PTR_PDF_URL.format(year=year, doc_id=doc_id) if doc_id else None,
            }
        )
    return pd.DataFrame(rows)


def run(con: duckdb.DuckDBPyConnection, year: int | None = None) -> IngestionResult:
    settings = get_settings()
    result = IngestionResult(source=SOURCE)
    if not settings.enable_house_disclosures:
        logger.info("House disclosure ingestion disabled via settings; skipping.")
        return result

    year = year or date.today().year
    url = INDEX_URL.format(year=year)
    with RateLimitedClient() as client:
        try:
            resp = client.get(url)
        except ComplianceError as exc:
            result.errors.append(str(exc))
            logger.warning("%s", exc)
            return result
        except Exception as exc:  # noqa: BLE001
            result.errors.append(str(exc))
            logger.error("House index download failed: %s", exc)
            return result

    try:
        archive = zipfile.ZipFile(io.BytesIO(resp.content))
        xml_name = next(n for n in archive.namelist() if n.lower().endswith(".xml"))
        xml_bytes = archive.read(xml_name)
    except (zipfile.BadZipFile, StopIteration) as exc:
        result.errors.append(f"bad archive: {exc}")
        return result

    store_raw_event(con, SOURCE, url, xml_bytes.decode("utf-8", errors="replace"))
    filings = parse_index_xml(xml_bytes, year)
    result.fetched = len(filings)

    # Keep the authoritative PTR index queryable alongside normalized trades.
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS house_filings_index (
            filing_hash VARCHAR PRIMARY KEY, doc_id VARCHAR, year INTEGER,
            full_name VARCHAR, state_district VARCHAR, filing_type VARCHAR,
            filing_date DATE, pdf_url VARCHAR
        )
        """
    )
    result.inserted = insert_ignore_df(con, "house_filings_index", filings)
    result.skipped_duplicates = result.fetched - result.inserted
    logger.info(result.summary())
    return result
