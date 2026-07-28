"""House PTR PDF transaction parser tests against fixture text (no network).

Fixture mirrors the real electronic PTR layout, including the wrapped-ticker
and bare-ticker cases observed in live filings.
"""
from datetime import date

from src.ingestion.house_disclosures import extract_filer_info, parse_ptr_text

PTR_TEXT = """Filing ID #20034201
Clerk of the House of Representatives
Name: Hon. Jane Sampleton
Status: Member
State/District: CA11
ID Owner Asset Transaction Date Notification Amount Cap.
Type Date Gains >
Apple Inc. - Common Stock (AAPL) [ST] P 06/15/2026 06/18/2026 $1,001 - $15,000
F S : New
SP Amazon.com, Inc. - Common Stock S (partial) 03/16/2026 03/16/2026 $15,001 - $50,000
(AMZN) [ST]
D : The full transaction included the following sales: AMZN - 25 shares sold @ $209.40/share
DIA - State Street SPDR Dow Jones S (partial) 03/16/2026 03/17/2026 $1,001 - $15,000
Industrial Average ETF Trust
DIA [OT]
JT Invesco QQQ [OT] E 02/01/2026 02/05/2026 $50,001 - $100,000
US Treasury Bill 4.2% due 09/2026 P 01/10/2026 01/12/2026 $100,001 - $250,000
"""


def _rows():
    return parse_ptr_text(PTR_TEXT, "20034201", date(2026, 6, 20))


def test_filer_info():
    info = extract_filer_info(PTR_TEXT)
    assert info["name"] == "Jane Sampleton"
    assert info["state"] == "CA"
    assert info["state_district"] == "CA11"


def test_row_count_and_core_fields():
    rows = _rows()
    assert len(rows) == 5
    first = rows[0]
    assert first["ticker"] == "AAPL"
    assert first["tx_type"] == "buy"
    assert first["owner"] == "self"
    assert first["traded_date"] == date(2026, 6, 15)
    assert first["size_min"] == 1_001 and first["size_max"] == 15_000
    assert first["chamber"] == "house"


def test_published_date_is_filing_date_not_notification():
    """Point-in-time rule: the public learns of the trade when it's FILED."""
    rows = _rows()
    assert all(r["published_date"] == date(2026, 6, 20) for r in rows)
    assert rows[0]["filed_after_days"] == 5  # 06/15 -> 06/20


def test_wrapped_ticker_and_owner_prefix():
    amzn = _rows()[1]
    assert amzn["ticker"] == "AMZN"      # ticker on continuation line
    assert amzn["owner"] == "spouse"     # SP prefix
    assert amzn["tx_type"] == "sell"
    assert amzn["size_mid"] == (15_001 + 50_000) / 2


def test_bare_ticker_variants():
    rows = _rows()
    assert rows[2]["ticker"] == "DIA"    # 'DIA - ...' prefix form
    assert rows[3]["ticker"] == "QQQ"    # 'Invesco QQQ [OT]' inline form
    assert rows[3]["owner"] == "joint"
    assert rows[3]["tx_type"] == "exchange"


def test_asset_without_ticker_kept_with_null_ticker():
    treasury = _rows()[4]
    assert treasury["ticker"] is None
    assert "Treasury" in treasury["issuer_name"]


def test_hashes_stable_and_unique():
    a, b = _rows(), _rows()
    assert [r["trade_hash"] for r in a] == [r["trade_hash"] for r in b]
    assert len({r["trade_hash"] for r in a}) == 5
