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
import re
import zipfile
from datetime import date, datetime
from xml.etree import ElementTree

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


# ---------------------------------------------------------------------------
# PTR transaction extraction (official source of record for trades).
# Electronically-filed PTRs (DocIDs starting with '2') are text PDFs with a
# consistent row layout:
#   [SP|DC|JT] <asset name> (TICKER) [ST] P|S|E [(partial)] MM/DD/YYYY MM/DD/YYYY $1,001 - $15,000
# Paper filings (other DocID prefixes) are scans needing OCR — recorded as
# skipped, never silently dropped.
# ---------------------------------------------------------------------------

_TX_ROW_RE = re.compile(
    r"(?P<tx>[PSE])\s*(?:\((?:partial|full)\))?\s+"
    r"(?P<tx_date>\d{2}/\d{2}/\d{4})\s+"
    r"(?P<notif_date>\d{2}/\d{2}/\d{4})\s+"
    r"(?P<amount>\$[\d,]+\s*-\s*\$[\d,]+|\$[\d,]+\s*\+?)"
)
_TICKER_RE = re.compile(r"\(([A-Z][A-Z0-9./-]{0,9})\)")
# fallback: bare ticker immediately before the asset-type tag, e.g.
# 'Invesco QQQ [OT]' or a continuation line reading 'DIA [OT]'.
# 2+ chars: single letters are usually PDF layout artifacts, and real
# one-letter tickers (T, V) always appear in the parenthesized form.
_BARE_TICKER_RE = re.compile(r"\b([A-Z]{2,6})\s*\[[A-Z]{2}\]")
_OWNER_PREFIX_RE = re.compile(r"^(SP|DC|JT)\s+")


def extract_filer_info(text: str) -> dict:
    name = None
    m = re.search(r"Name:\s*(.+)", text)
    if m:
        name = re.sub(r"^(Hon|Mr|Mrs|Ms|Dr)\.?\s+", "", m.group(1).strip()).strip()
    m = re.search(r"State/District:\s*([A-Z]{2})(\d*)", text)
    state = m.group(1) if m else None
    district = (m.group(1) + m.group(2)) if m else None
    return {"name": name, "state": state, "state_district": district}


def parse_ptr_text(
    text: str, doc_id: str, filing_date: date | None
) -> list[dict]:
    """Parse transaction rows out of an electronic PTR's extracted text.

    Pure function (unit-tested against fixture text). published_date is the
    official FILING date — the first moment the information was public.
    """
    filer = extract_filer_info(text)
    lines = [ln.strip() for ln in text.splitlines()]
    rows: list[dict] = []

    for i, line in enumerate(lines):
        m = _TX_ROW_RE.search(line)
        if not m:
            continue
        prefix = line[: m.start()].strip()
        owner_raw = None
        om = _OWNER_PREFIX_RE.match(prefix)
        if om:
            owner_raw = om.group(1)
            prefix = prefix[om.end():].strip()
        asset = prefix
        # Wrapped rows: the '(TICKER) [ST]' tail often lands on the next
        # line. Metadata lines (Filing Status / Subholding Of / Description)
        # contain an early colon and are never ticker continuations.
        continuation = ""
        if i + 1 < len(lines):
            nxt = lines[i + 1]
            if not _TX_ROW_RE.search(nxt) and ":" not in nxt[:20]:
                continuation = nxt
        searchable = f"{asset} {continuation}"
        ticker_match = (
            _TICKER_RE.search(searchable)
            or _BARE_TICKER_RE.search(searchable)
            or re.match(r"^([A-Z]{1,6})\s+-\s", asset)  # 'DIA - State Street...'
        )
        ticker = normalize_ticker(ticker_match.group(1)) if ticker_match else None
        _clean = lambda s: re.sub(r"\[[A-Z]{2}\]", "", _TICKER_RE.sub("", s)).strip(" -–")  # noqa: E731
        asset = _clean(asset)
        if not asset and i > 0:
            asset = _clean(lines[i - 1])

        traded = datetime.strptime(m.group("tx_date"), "%m/%d/%Y").date()
        size_min, size_max = parse_size_range(m.group("amount"))
        tx_type = normalize_tx_type(m.group("tx"))
        owner = normalize_owner(owner_raw) if owner_raw else "self"
        published = filing_date

        rows.append({
            "trade_hash": stable_hash(
                "house_clerk_ptr", doc_id, len(rows), filer["name"], ticker,
                asset, tx_type, owner, traded, m.group("amount"),
            ),
            "source": "house_clerk_ptr",
            "source_url": PTR_PDF_URL.format(year=traded.year, doc_id=doc_id),
            "retrieved_at": utcnow(),
            "politician_id": stable_hash("rep", filer["name"])[:16],
            "politician_name": filer["name"],
            "party": None,  # index carries no party; enrich later if needed
            "chamber": "house",
            "state": filer["state"],
            "issuer_name": asset or None,
            "ticker": ticker,
            "tx_type": tx_type,
            "owner": owner,
            "size_range": m.group("amount"),
            "size_min": size_min,
            "size_max": size_max,
            "size_mid": size_midpoint(size_min, size_max),
            "traded_date": traded,
            "published_date": published,
            "filed_after_days": (published - traded).days if published else None,
        })
    return rows


def _ensure_ptr_tracking(con: duckdb.DuckDBPyConnection) -> None:
    con.execute(
        """
        CREATE TABLE IF NOT EXISTS house_ptr_parsed (
            doc_id VARCHAR PRIMARY KEY, year INTEGER, parsed_at TIMESTAMP,
            n_trades INTEGER, status VARCHAR
        )
        """
    )


def ingest_ptr_transactions(
    con: duckdb.DuckDBPyConnection, year: int, max_docs: int | None = None
) -> IngestionResult:
    """Download & parse unprocessed PTR PDFs for `year` into political_trades.

    Idempotent: each DocID is processed once and recorded in house_ptr_parsed.
    Rate-limited (~2s/PDF); ~275 filings ≈ 10 min, so backfills run in batches.
    """
    from pathlib import Path as _Path

    result = IngestionResult(source="house_clerk_ptr")
    _ensure_ptr_tracking(con)
    settings = get_settings()

    pending = con.execute(
        """
        SELECT f.doc_id, f.filing_date, f.full_name
        FROM house_filings_index f
        LEFT JOIN house_ptr_parsed p USING (doc_id)
        WHERE f.year = ? AND f.filing_type = 'P' AND p.doc_id IS NULL
        ORDER BY f.filing_date DESC
        """,
        [year],
    ).fetchall()
    if max_docs:
        pending = pending[:max_docs]
    if not pending:
        logger.info("No unprocessed PTR filings for %d.", year)
        return result

    pdf_dir = _Path(settings.raw_data_dir) / "house_ptrs" / str(year)
    pdf_dir.mkdir(parents=True, exist_ok=True)
    logger.info("Processing %d PTR filings for %d...", len(pending), year)

    import pdfplumber

    with RateLimitedClient() as client:
        for idx, (doc_id, filing_date, _name) in enumerate(pending, 1):
            if idx % 25 == 0:
                logger.info(
                    "PTR progress %d: %d/%d filings, %d trades so far",
                    year, idx, len(pending), result.inserted,
                )
            status, n_trades = "ok", 0
            if not str(doc_id).startswith("2"):
                status = "skipped_paper"  # scanned filing; needs OCR
            else:
                url = PTR_PDF_URL.format(year=year, doc_id=doc_id)
                try:
                    resp = client.get(url)
                    pdf_path = pdf_dir / f"{doc_id}.pdf"
                    pdf_path.write_bytes(resp.content)
                    store_raw_event(
                        con, "house_clerk_ptr", url,
                        f'{{"doc_id":"{doc_id}","bytes":{len(resp.content)},"saved_to":"{pdf_path}"}}',
                    )
                    with pdfplumber.open(io.BytesIO(resp.content)) as pdf:
                        text = "\n".join(p.extract_text() or "" for p in pdf.pages)
                    trades = parse_ptr_text(text, str(doc_id), filing_date)
                    n_trades = len(trades)
                    result.fetched += n_trades
                    if trades:
                        inserted = insert_ignore_df(con, "political_trades", pd.DataFrame(trades))
                        result.inserted += inserted
                        result.skipped_duplicates += n_trades - inserted
                    if n_trades == 0:
                        status = "no_rows_parsed"
                except ComplianceError as exc:
                    result.errors.append(str(exc))
                    logger.warning("%s", exc)
                    return result
                except Exception as exc:  # noqa: BLE001 - one bad PDF must not kill the batch
                    status = "error"
                    result.errors.append(f"{doc_id}: {exc}")
                    logger.warning("PTR %s failed: %s", doc_id, exc)
            con.execute(
                "INSERT INTO house_ptr_parsed VALUES (?, ?, ?, ?, ?) ON CONFLICT DO NOTHING",
                [str(doc_id), year, utcnow(), n_trades, status],
            )

    logger.info(result.summary())
    return result


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
