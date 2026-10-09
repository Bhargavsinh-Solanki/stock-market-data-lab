"""Tests for the what-if calculations in portfolio.py (fake prices, no internet)."""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from portfolio import normalise, simulate  # noqa: E402


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
