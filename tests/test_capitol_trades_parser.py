"""Parser tests against a mocked CapitolTrades API response (no network)."""
import json
from datetime import date
from pathlib import Path

from src.ingestion.capitol_trades import parse_trade

FIXTURE = Path(__file__).parent / "fixtures" / "capitol_trades_page.json"


def _records() -> list[dict]:
    return json.loads(FIXTURE.read_text())["data"]


def test_parses_buy_with_bucket_size():
    trade = parse_trade(_records()[0])
    assert trade["politician_name"] == "Jane Sampleton"
    assert trade["party"] == "democrat"
    assert trade["chamber"] == "house"
    assert trade["state"] == "CA"
    assert trade["ticker"] == "AAPL"
    assert trade["tx_type"] == "buy"
    assert trade["owner"] == "spouse"
    assert trade["size_min"] == 1_001 and trade["size_max"] == 15_000
    assert trade["size_mid"] == (1_001 + 15_000) / 2
    assert trade["traded_date"] == date(2026, 6, 15)
    assert trade["published_date"] == date(2026, 7, 1)
    assert trade["filed_after_days"] == 16


def test_parses_sell_with_exact_value_and_no_ticker():
    trade = parse_trade(_records()[1])
    assert trade["ticker"] is None  # 'N/A' must not become a ticker
    assert trade["tx_type"] == "sell"
    assert trade["size_mid"] == 75_000  # exact disclosed value beats midpoint
    assert trade["chamber"] == "senate"


def test_hash_is_stable_and_dedupes():
    first = parse_trade(_records()[0])
    second = parse_trade(_records()[0])
    assert first["trade_hash"] == second["trade_hash"]


def test_hash_differs_for_different_trades():
    a = parse_trade(_records()[0])
    b = parse_trade(_records()[1])
    assert a["trade_hash"] != b["trade_hash"]


def test_missing_fields_do_not_crash():
    trade = parse_trade({})
    assert trade["tx_type"] == "other"
    assert trade["owner"] == "undisclosed"
    assert trade["ticker"] is None
    assert trade["traded_date"] is None
