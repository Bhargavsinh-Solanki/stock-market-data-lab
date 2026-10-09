"""Tests for risk_forecast.py using made-up returns where we know the true volatility."""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from risk_forecast import evaluate, ewma_volatility, forecasts, realised_next  # noqa: E402

DAYS = pd.bdate_range("2020-01-01", periods=800)


def calm_then_wild(seed=0):
    """400 calm days (1% daily moves), then 400 wild days (3% daily moves)."""
    rng = np.random.default_rng(seed)
    daily = np.concatenate([rng.normal(0, 0.01, 400), rng.normal(0, 0.03, 400)])
    return pd.DataFrame({"X": daily}, index=DAYS)


def test_forecasts_match_the_true_volatility_in_a_calm_period():
    made = forecasts(calm_then_wild())
    true_vol = 0.01 * np.sqrt(252) * 100  # about 15.9%
    for name in ["last month", "3 months", "1 year", "EWMA"]:
        assert made[name]["X"].iloc[390] == pytest.approx(true_vol, rel=0.35)


def test_short_windows_react_faster_to_a_change():
    made = forecasts(calm_then_wild())
    day = 430  # one month after things got wild
    assert made["last month"]["X"].iloc[day] > made["1 year"]["X"].iloc[day]


def test_realised_next_only_looks_forward():
    returns = calm_then_wild()
    nxt = realised_next(returns)
    # On day 380 the NEXT 21 days are still calm; on day 400 they're all wild
    assert nxt["X"].iloc[378] < 25 < nxt["X"].iloc[400]
    assert np.isnan(nxt["X"].iloc[-1])  # no future to look at on the last day


def test_ewma_weights_recent_days_more():
    quiet = pd.Series([0.0] * 50 + [0.05])          # one big move at the very end
    early = pd.Series([0.05] + [0.0] * 50)          # the same move, long ago
    assert ewma_volatility(quiet).iloc[-1] > ewma_volatility(early).iloc[-1]


def test_evaluate_returns_one_row_per_method():
    table = evaluate(calm_then_wild())
    assert set(table.index) == {"last month", "3 months", "1 year", "EWMA"}
    assert (table["checks"] > 0).all()
