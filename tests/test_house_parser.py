"""House Clerk index parser test against mocked XML (no network)."""
from datetime import date

from src.ingestion.house_disclosures import parse_index_xml

XML = b"""<?xml version="1.0" encoding="utf-8"?>
<FinancialDisclosure>
  <Member>
    <Prefix>Hon.</Prefix>
    <Last>Sampleton</Last>
    <First>Jane</First>
    <Suffix/>
    <FilingType>P</FilingType>
    <StateDst>CA11</StateDst>
    <Year>2026</Year>
    <FilingDate>6/20/2026</FilingDate>
    <DocID>20026789</DocID>
  </Member>
  <Member>
    <Last>Examplesen</Last>
    <First>John</First>
    <FilingType>O</FilingType>
    <StateDst>TX02</StateDst>
    <Year>2026</Year>
    <FilingDate>5/15/2026</FilingDate>
    <DocID>10012345</DocID>
  </Member>
</FinancialDisclosure>
"""


def test_parses_all_filings():
    df = parse_index_xml(XML, 2026)
    assert len(df) == 2
    assert set(df["filing_type"]) == {"P", "O"}


def test_ptr_row_fields():
    df = parse_index_xml(XML, 2026)
    ptr = df[df["filing_type"] == "P"].iloc[0]
    assert ptr["full_name"] == "Jane Sampleton"
    assert ptr["state_district"] == "CA11"
    assert ptr["filing_date"] == date(2026, 6, 20)
    assert ptr["doc_id"] == "20026789"
    assert ptr["pdf_url"].endswith("/2026/20026789.pdf")


def test_hash_stable():
    a = parse_index_xml(XML, 2026)
    b = parse_index_xml(XML, 2026)
    assert list(a["filing_hash"]) == list(b["filing_hash"])
