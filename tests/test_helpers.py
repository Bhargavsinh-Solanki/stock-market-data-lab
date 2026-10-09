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

from helpers import (  # noqa: E402
    annual_volatility, backtest, biggest_drop, grow_100, headline_sentiment, ma_rule_positions,
    portfolio_returns, shuffle_test, trading_day_for,
)


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


# --- trading_day_for (news timing) -------------------------------------------------

def test_news_is_matched_to_the_right_trading_day():
    # Thu 1 Oct and Fri 2 Oct, then Mon 5 Oct 2026 (the weekend is closed)
    trading_days = pd.to_datetime(["2026-10-01", "2026-10-02", "2026-10-05"])
    published = pd.to_datetime([
        "2026-10-02 15:00",  # Friday before the close   -> Friday
        "2026-10-02 17:00",  # Friday after the close    -> Monday
        "2026-10-03 10:00",  # Saturday                  -> Monday
        "2026-10-05 08:00",  # Monday before the open    -> Monday
        "2026-10-05 18:00",  # after our last known day  -> no match
    ]).tz_localize("America/New_York")

    result = trading_day_for(published, trading_days)

    expected = pd.to_datetime(["2026-10-02", "2026-10-05", "2026-10-05", "2026-10-05", None])
    # .equals() treats two "no date" (NaT) values as matching; == would not.
    assert result.equals(pd.DatetimeIndex(expected))


def test_news_timing_works_with_utc_times():
    # Alpaca sends UTC. 21:30 UTC on 1 Oct = 17:30 New York -> after the close -> next day.
    trading_days = pd.to_datetime(["2026-10-01", "2026-10-02"])
    published = pd.to_datetime(["2026-10-01 21:30"]).tz_localize("UTC")
    assert trading_day_for(published, trading_days)[0] == pd.Timestamp("2026-10-02")


# --- headline_sentiment ---------------------------------------------------------------

def test_sentiment_positive_and_negative():
    assert headline_sentiment("Apple beats earnings estimates") == 1
    assert headline_sentiment("Tesla stock falls after delivery miss") == -2


def test_sentiment_ignores_case_and_punctuation():
    assert headline_sentiment("UPGRADE: Nvidia SOARS!") == 2  # capitals and ":" "!" don't matter
    assert headline_sentiment("Nvidia soars; analysts upgraded it") == 2


def test_sentiment_whole_words_only():
    # "falls" hides inside "waterfalls" - it must NOT count as a negative word
    assert headline_sentiment("Waterfalls and highlands tour") == 0


def test_sentiment_mixed_headline_cancels_out():
    assert headline_sentiment("Stock drops despite record profits") == 1  # -1 +1 +1


# --- shuffle_test -------------------------------------------------------------------

def test_shuffle_test_spots_a_real_effect():
    # Days 0-9 are clearly bigger than days 10-99. Picking them by luck is very unlikely.
    values = [10] * 10 + [0] * 90
    chosen = [True] * 10 + [False] * 90
    ours, _, p_value = shuffle_test(values, chosen, n_shuffles=2000)
    assert ours == 10
    assert p_value < 0.01


def test_shuffle_test_shrugs_at_a_typical_pick():
    # Our chosen days are exactly average, so about half of random picks beat them.
    values = list(range(100))
    chosen = [i % 2 == 0 for i in range(100)]  # every other day: average 49 vs overall 49.5
    _, _, p_value = shuffle_test(values, chosen, n_shuffles=2000)
    assert 0.3 < p_value < 0.8


def test_shuffle_test_is_repeatable_with_a_seed():
    values, chosen = list(range(50)), [i < 5 for i in range(50)]
    assert shuffle_test(values, chosen, seed=1)[2] == shuffle_test(values, chosen, seed=1)[2]


# --- portfolios ---------------------------------------------------------------------

def test_portfolio_is_the_average_of_its_stocks():
    returns = pd.DataFrame({"A": [0.02, -0.01], "B": [0.00, 0.03], "C": [0.5, 0.5]})
    assert list(portfolio_returns(returns, ["A", "B"])) == pytest.approx([0.01, 0.01])


def test_opposite_stocks_cancel_out():
    # A zigs when B zags: each one alone is bumpy, together they're perfectly smooth
    returns = pd.DataFrame({"A": [0.02, -0.02] * 50, "B": [-0.02, 0.02] * 50})
    assert annual_volatility(returns["A"]) > 25
    assert annual_volatility(portfolio_returns(returns, ["A", "B"])) == pytest.approx(0)


def test_identical_stocks_give_no_benefit():
    returns = pd.DataFrame({"A": [0.02, -0.01, 0.03, -0.02]})
    returns["B"] = returns["A"]  # B always moves exactly like A
    together = annual_volatility(portfolio_returns(returns, ["A", "B"]))
    assert together == pytest.approx(annual_volatility(returns["A"]))
