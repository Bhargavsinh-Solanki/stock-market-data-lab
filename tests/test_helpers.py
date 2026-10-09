"""
Automated tests for helpers.py.

A TEST is a tiny program that checks another program gives the right answer.
We feed in made-up prices where WE already know the correct result,
then `assert` (insist) that the code agrees. If it doesn't, the test fails loudly.

Run all tests with:   pytest
(No internet or Alpaca keys needed - everything here uses fake prices.)
"""

import sys
from pathlib import Path

import pandas as pd
import pytest

# Let this file find helpers.py, which lives one folder up.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from helpers import backtest, biggest_drop, grow_100, ma_rule_positions  # noqa: E402


def fake_prices(values):
    """Turn a plain list like [10, 11, 12] into prices with real weekday dates."""
    return pd.Series(values, index=pd.bdate_range("2024-01-01", periods=len(values)), dtype=float)


# --- grow_100 --------------------------------------------------------------------

def test_grow_100_no_change():
    assert grow_100([0, 0, 0]) == 100


def test_grow_100_compounds():
    # +10% then -10% is NOT back to even: 100 -> 110 -> 99
    assert grow_100([0.10, -0.10]) == pytest.approx(99)


# --- biggest_drop ----------------------------------------------------------------

def test_biggest_drop():
    # Peak is 120, the low after it is 90: (90 - 120) / 120 = -25%
    assert biggest_drop([100, 120, 90, 110]) == pytest.approx(-25)


def test_biggest_drop_never_falls():
    assert biggest_drop([1, 2, 3, 4]) == 0


# --- ma_rule_positions -----------------------------------------------------------

def test_rule_holds_stock_in_steady_rise():
    close = fake_prices(range(1, 11))  # 1, 2, ..., 10: always above its average
    in_market = ma_rule_positions(close, ma_days=3)
    # Days 0-2: no 3-day average yet. Day 2 is the first signal, acted on day 3.
    assert list(in_market) == [False] * 3 + [True] * 7


def test_rule_never_peeks_at_the_future():
    # Flat price, then a sudden jump on the LAST day.
    close = fake_prices([10, 10, 10, 10, 20])
    in_market = ma_rule_positions(close, ma_days=3)
    # The jump is only known after day 4 closes, so we must NOT already own it on day 4.
    assert in_market.iloc[-1] == False  # noqa: E712


# --- backtest --------------------------------------------------------------------

def test_backtest_charges_cost_on_each_switch():
    close = fake_prices([10, 10, 10, 11, 12, 13])
    with_cost = backtest(close, ma_days=3, cost=0.01)
    free = backtest(close, ma_days=3, cost=0)
    # The rule switches into the stock once, so it pays the 1% cost exactly once.
    assert (free - with_cost).sum() == pytest.approx(0.01)


def test_backtest_earns_nothing_while_in_cash():
    close = fake_prices([10, 9, 8, 7, 6, 5])  # always below average -> always cash
    assert grow_100(backtest(close, ma_days=3)) == 100
