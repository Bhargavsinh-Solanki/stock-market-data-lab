"""Parser tests for the global sources (Stooq, ECB, World Bank) — mocked, no network."""
from datetime import date

from src.ingestion.ecb import parse_ecb_csv
from src.ingestion.stooq import parse_stooq_csv
from src.ingestion.world_bank import parse_wb_json

STOOQ_CSV = """Date,Open,High,Low,Close,Volume
2026-07-01,39800.5,40120.0,39750.2,40011.3,0
2026-07-02,40020.0,40200.9,39900.1,40150.7,0
"""

ECB_CSV = (
    "KEY,FREQ,CURRENCY,CURRENCY_DENOM,EXR_TYPE,EXR_SUFFIX,TIME_PERIOD,OBS_VALUE\n"
    "EXR.D.USD.EUR.SP00.A,D,USD,EUR,SP00,A,2026-07-01,1.0842\n"
    "EXR.D.USD.EUR.SP00.A,D,USD,EUR,SP00,A,2026-07-02,1.0867\n"
)

WB_JSON = [
    {"page": 1, "pages": 1, "per_page": 2000, "total": 3},
    [
        # live API puts the 2-letter code in country.id; ISO3 must win
        {"indicator": {"id": "FP.CPI.TOTL.ZG"}, "country": {"id": "CN", "value": "China"},
         "countryiso3code": "CHN", "date": "2025", "value": 1.8},
        {"indicator": {"id": "FP.CPI.TOTL.ZG"}, "country": {"id": "DE", "value": "Germany"},
         "countryiso3code": "DEU", "date": "2025", "value": 2.4},
        {"indicator": {"id": "FP.CPI.TOTL.ZG"}, "country": {"id": "BR", "value": "Brazil"},
         "countryiso3code": "BRA", "date": "2025", "value": None},  # missing -> dropped
    ],
]


class TestStooq:
    def test_parses_rows(self):
        df = parse_stooq_csv(STOOQ_CSV, "^N225")
        assert len(df) == 2
        assert (df["ticker"] == "^N225").all()
        assert df["date"].iloc[0] == date(2026, 7, 1)
        assert df["adj_close"].iloc[1] == 40150.7

    def test_no_data_response(self):
        assert parse_stooq_csv("No data", "^N225").empty
        assert parse_stooq_csv("", "^N225").empty


class TestECB:
    def test_parses_series(self):
        df = parse_ecb_csv(ECB_CSV, "ECB_EURUSD")
        assert len(df) == 2
        assert (df["series_id"] == "ECB_EURUSD").all()
        assert df["value"].iloc[0] == 1.0842
        assert df["date"].iloc[1] == date(2026, 7, 2)

    def test_garbage_returns_empty(self):
        assert parse_ecb_csv("<html>error</html>", "ECB_EURUSD").empty
        assert parse_ecb_csv("", "ECB_EURUSD").empty


class TestWorldBank:
    def test_parses_countries_and_drops_nulls(self):
        df = parse_wb_json(WB_JSON, "FP.CPI.TOTL.ZG")
        assert len(df) == 2  # BRA null dropped
        assert set(df["series_id"]) == {"WB_FP_CPI_TOTL_ZG_CHN", "WB_FP_CPI_TOTL_ZG_DEU"}

    def test_annual_value_dated_to_year_end(self):
        """Anti-lookahead: a 2025 annual figure must not be visible before
        the end of 2025 when forward-filled onto the calendar."""
        df = parse_wb_json(WB_JSON, "FP.CPI.TOTL.ZG")
        assert (df["date"] == date(2025, 12, 31)).all()

    def test_empty_or_error_payload(self):
        assert parse_wb_json([{"message": "err"}], "X").empty
        assert parse_wb_json([], "X").empty
        assert parse_wb_json([{"page": 1}, None], "X").empty
