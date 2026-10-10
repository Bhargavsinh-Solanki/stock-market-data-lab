"""Tests for lab/dividends.py with made-up dividend records."""

from datetime import date

import pandas as pd
import pytest

from lab.dividends import COLUMNS, summarise

TODAY = date(2026, 10, 10)


def records(rows):
    return pd.DataFrame(rows, columns=COLUMNS)


QUARTERLY = records([
    ("AAA", date(2025, 11, 10), date(2025, 11, 13), 0.25, False),
    ("AAA", date(2026, 2, 9), date(2026, 2, 12), 0.25, False),
    ("AAA", date(2026, 5, 11), date(2026, 5, 14), 0.25, False),
    ("AAA", date(2026, 8, 10), date(2026, 8, 13), 0.25, False),
    ("AAA", date(2025, 8, 11), date(2025, 8, 14), 0.20, False),   # more than a year ago
    ("BBB", date(2026, 6, 1), date(2026, 6, 5), 5.00, True),       # a one-off SPECIAL dividend
])


def test_yield_and_income():
    table = summarise(QUARTERLY, prices={"AAA": 50.0}, values={"AAA": 1000}, today=TODAY)
    row = table.loc["AAA"]
    assert row["payments_12m"] == 4                       # the old 0.20 payment is outside the year
    assert row["per_share_12m"] == pytest.approx(1.00)
    assert row["yield_%"] == pytest.approx(2.0)           # $1 a year on a $50 share
    assert row["income_year"] == pytest.approx(20.0)      # 2% of 1000


def test_next_date_is_estimated_from_the_usual_gap():
    row = summarise(QUARTERLY, {"AAA": 50.0}, {"AAA": 1000}, today=TODAY).loc["AAA"]
    assert row["next_is"] == "estimate"
    assert date(2026, 11, 1) <= row["next_date"] <= date(2026, 11, 20)  # about 3 months after Aug 10


def test_announced_dividend_wins_over_an_estimate():
    announced = pd.concat([QUARTERLY, records([("AAA", date(2026, 11, 9), date(2026, 11, 12), 0.27, False)])])
    row = summarise(announced, {"AAA": 50.0}, {"AAA": 1000}, today=TODAY).loc["AAA"]
    assert row["next_is"] == "announced" and row["next_date"] == date(2026, 11, 9)


def test_special_dividends_and_non_payers():
    table = summarise(QUARTERLY, {"BBB": 100.0, "CCC": 10.0}, {"BBB": 500, "CCC": 500}, today=TODAY)
    assert table.loc["BBB", "income_year"] == 0     # a one-off special payment isn't "yearly income"
    assert table.loc["CCC", "next_is"] == "-"       # never paid a dividend


def test_missing_price_gives_unknown_yield_not_zero():
    table = summarise(QUARTERLY, prices={}, values={"AAA": 1000}, today=TODAY)
    assert pd.isna(table.loc["AAA", "yield_%"])  # it DID pay - we just can't work out the %
