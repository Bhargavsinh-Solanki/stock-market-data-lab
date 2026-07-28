"""Unit tests for pure normalization helpers."""
from src.processing.normalize import (
    normalize_owner,
    normalize_ticker,
    normalize_tx_type,
    parse_size_range,
    size_midpoint,
)


class TestParseSizeRange:
    def test_bucket_label(self):
        assert parse_size_range("1K-15K") == (1_001, 15_000)

    def test_bucket_label_en_dash(self):
        assert parse_size_range("1K–15K") == (1_001, 15_000)

    def test_verbose_dollar_range(self):
        lo, hi = parse_size_range("$1,001 - $15,000")
        assert lo == 1_001 and hi == 15_000

    def test_millions(self):
        lo, hi = parse_size_range("1M-5M")
        assert lo == 1_000_001 and hi == 5_000_000

    def test_open_top_bucket(self):
        lo, hi = parse_size_range("50M+")
        assert lo == 50_000_001 and hi > lo

    def test_none_and_garbage(self):
        assert parse_size_range(None) == (None, None)
        assert parse_size_range("unknown") == (None, None)

    def test_truncated_bucket_lower_bound_restores_full_bucket(self):
        """PDF line wraps can cut '$250,001 - $500,000' down to '$250,001'."""
        assert parse_size_range("$250,001 ") == (250_001, 500_000)
        assert parse_size_range("$15,001") == (15_001, 50_000)

    def test_non_bucket_single_value_stays_exact(self):
        assert parse_size_range("$7,500") == (7_500, 7_500)


class TestSizeMidpoint:
    def test_exact_value_wins(self):
        assert size_midpoint(1_001, 15_000, exact_value=5_000) == 5_000

    def test_midpoint_fallback(self):
        assert size_midpoint(1_000, 3_000) == 2_000

    def test_all_missing(self):
        assert size_midpoint(None, None) is None


class TestNormalizers:
    def test_tx_type(self):
        assert normalize_tx_type("Purchase") == "buy"
        assert normalize_tx_type("Sale (Partial)") == "sell"
        assert normalize_tx_type("weird") == "other"
        assert normalize_tx_type(None) == "other"

    def test_owner(self):
        assert normalize_owner("SP") == "spouse"
        assert normalize_owner("JT") == "joint"
        assert normalize_owner(None) == "undisclosed"

    def test_ticker(self):
        assert normalize_ticker("AAPL:US") == "AAPL"
        assert normalize_ticker("BRK.B") == "BRK-B"
        assert normalize_ticker("N/A") is None
        assert normalize_ticker(None) is None
