"""Tests for the what-if calculations in portfolio.py (fake prices, no internet)."""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from portfolio import normalise, simulate, yearly_stats  # noqa: E402


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
