"""Tests for the what-if calculations in portfolio.py (fake prices, no internet)."""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from portfolio import normalise, simulate, transition_plan, yearly_stats  # noqa: E402


def fake_returns():
    rng = np.random.default_rng(1)
    return pd.DataFrame({
        "CALM": rng.normal(0.0005, 0.005, 250),   # small daily moves
        "WILD": rng.normal(0.0005, 0.04, 250),    # big daily moves
        "OTHER": rng.normal(0.0005, 0.01, 250),
    })


def test_normalise_scales_to_one_and_drops_zeros():
    w = normalise({"A": 30, "B": 10, "C": 0})
    assert dict(w) == pytest.approx({"A": 0.75, "B": 0.25})


def test_normalise_rejects_all_zero():
    with pytest.raises(ValueError):
        normalise({"A": 0, "B": 0})


def test_moving_money_to_the_calm_stock_lowers_risk():
    returns = fake_returns()
    wild_heavy = simulate(returns, {"CALM": 20, "WILD": 80})
    calm_heavy = simulate(returns, {"CALM": 80, "WILD": 20})
    assert calm_heavy["volatility_%"] < wild_heavy["volatility_%"]


def test_simulate_results_are_consistent():
    result = simulate(fake_returns(), {"CALM": 1, "WILD": 1, "OTHER": 1})
    assert result["effective_stocks"] == pytest.approx(3)
    assert result["risk_%"].sum() == pytest.approx(100)
    assert result["growth"].iloc[-1] == pytest.approx(result["$100 became"])
    assert result["biggest_drop_%"] <= 0


def test_yearly_stats_splits_by_calendar_year():
    days = pd.bdate_range("2024-01-01", "2025-12-31")  # weekdays across two years
    returns = pd.DataFrame({"A": 0.001, "B": 0.0}, index=days)
    stats = yearly_stats(returns, {"A": 1, "B": 1})
    assert list(stats.index) == [2024, 2025]
    assert stats.loc[2024, "days"] == len(days[days.year == 2024])
    # half in A (+0.1% a day), half in B (flat) -> +0.05% a day, compounded over the year
    expected = (1.0005 ** stats.loc[2024, "days"] - 1) * 100
    assert stats.loc[2024, "return_%"] == pytest.approx(expected)
    assert stats.loc[2024, "biggest_drop_%"] == 0  # it only ever went up


def test_analyse_leaves_out_holdings_without_enough_history(monkeypatch):
    import portfolio

    days = pd.bdate_range("2025-01-01", periods=300)
    rng = np.random.default_rng(2)
    prices = pd.DataFrame({s: 100 * np.cumprod(1 + rng.normal(0, 0.01, 300)) for s in ["A", "B", "SPY"]},
                          index=days)
    prices["NEW"] = np.where(np.arange(300) >= 250, 50.0, np.nan)  # listed only 50 days ago
    prices["NODATA"] = np.nan                                      # no prices at all

    # MONKEYPATCH: swap the real download for our fake prices, just for this test
    monkeypatch.setattr(portfolio, "daily_closes",
                        lambda symbols, days, keep_gaps: prices.reindex(columns=symbols))

    check = portfolio.analyse({"A": 500, "B": 300, "NEW": 100, "NODATA": 100})
    assert set(check.excluded.index) == {"NEW", "NODATA"}
    assert list(check.positions.index) == ["A", "B"]
    assert check.positions["money_%"].sum() == pytest.approx(100)
    assert check.invested == 1000  # the total still counts every holding


# --- transition_plan (Lesson 25) ------------------------------------------------------

HOLDINGS = {"NVDA": 600, "ZS": 300, "JNJ": 100, "URTH": 400, "SPY": 300}


def test_plan_starts_today_and_keeps_the_total():
    plan = transition_plan(HOLDINGS, {"URTH": 1, "SPY": 1}, months=4)
    assert len(plan) == 5  # month 0 (today) + 4 steps
    assert dict(plan.loc[0]) == HOLDINGS
    assert plan.sum(axis=1).tolist() == pytest.approx([1700] * 5)  # money only moves, never vanishes


def test_plan_ends_with_no_stocks_except_kept_ones():
    plan = transition_plan(HOLDINGS, {"URTH": 1}, months=3, keep=["JNJ"])
    end = plan.iloc[-1]
    assert end["NVDA"] == pytest.approx(0) and end["ZS"] == pytest.approx(0)
    assert end["JNJ"] == 100                      # kept stock untouched
    assert end["URTH"] == pytest.approx(400 + 900)  # all the sold money went into URTH
    assert end["SPY"] == 300                      # not in the split -> unchanged


def test_plan_sells_equal_slices_and_splits_by_percentage():
    plan = transition_plan({"NVDA": 300, "URTH": 0}, {"URTH": 75, "SPY": 25}, months=3)
    assert plan["NVDA"].tolist() == pytest.approx([300, 200, 100, 0])
    assert plan["SPY"].tolist() == pytest.approx([0, 25, 50, 75])  # a NEW ETF column appears


def test_plan_rows_are_months_even_for_a_named_column():
    # Reading a CSV gives a NAMED column (e.g. "value_eur"); rows must still be months 0..N
    values = pd.Series(HOLDINGS, name="value_eur")
    plan = transition_plan(values, {"URTH": 1}, months=2)
    assert list(plan.index) == [0, 1, 2]
