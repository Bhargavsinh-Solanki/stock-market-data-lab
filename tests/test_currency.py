"""Tests for currency.py with made-up prices and exchange rates."""

import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lab.currency import split_return, to_euro_prices, to_euro_returns  # noqa: E402

DAYS = pd.bdate_range("2026-01-05", periods=3)


def test_split_return_example_from_the_docstring():
    in_euros, currency_part = split_return(10, 5)  # stock +10% in $, euro +5% vs $
    assert in_euros == pytest.approx(4.76, abs=0.01)
    assert currency_part == pytest.approx(-5.24, abs=0.01)


def test_weaker_euro_helps_a_euro_investor():
    in_euros, currency_part = split_return(0, -2)  # flat stock, euro falls 2%
    assert in_euros > 0 and currency_part > 0


def test_euro_returns_match_euro_prices():
    usd = pd.DataFrame({"A": [100.0, 110.0, 99.0]}, index=DAYS)
    euro = pd.Series([1.00, 1.05, 1.05], index=DAYS)            # euro +5% on day 2
    prices = to_euro_prices(usd, euro)
    from_prices = prices.pct_change().dropna()
    from_returns = to_euro_returns(usd.pct_change().dropna(), euro.pct_change().dropna())
    assert from_returns["A"].tolist() == pytest.approx(from_prices["A"].tolist())
    assert from_returns["A"].iloc[0] == pytest.approx(1.10 / 1.05 - 1)


def test_missing_exchange_rate_days_are_filled():
    usd = pd.Series([100.0, 101.0, 102.0], index=DAYS)
    euro = pd.Series([1.0, 1.0], index=DAYS[[0, 2]])            # no rate on day 2
    assert to_euro_prices(usd, euro).notna().all()
