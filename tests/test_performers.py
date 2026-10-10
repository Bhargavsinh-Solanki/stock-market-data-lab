"""Tests for performers.py using made-up prices."""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lab.performers import top_performers  # noqa: E402


def fake_closes():
    days = pd.bdate_range("2025-01-01", periods=200)
    rng = np.random.default_rng(3)
    return pd.DataFrame({
        "UP": 100 * np.cumprod(np.full(200, 1.002)),                    # steady climb
        "DOWN": 100 * np.cumprod(np.full(200, 0.998)),                  # steady fall
        "WILD": 100 * np.cumprod(1 + rng.normal(0, 0.03, 200)),         # big swings
        "NEW": [np.nan] * 190 + list(np.linspace(50, 60, 10)),          # listed 10 days ago
    }, index=days)


def test_best_first_and_return_is_correct():
    table = top_performers(fake_closes(), period_days=21)
    assert table["return_%"].is_monotonic_decreasing                     # best first
    assert list(table.index).index("UP") < list(table.index).index("DOWN")
    assert table.loc["UP", "return_%"] == pytest.approx((1.002 ** 21 - 1) * 100)
    assert table.loc["DOWN", "return_%"] < 0


def test_too_new_stocks_are_left_out_of_long_periods():
    assert "NEW" not in top_performers(fake_closes(), period_days=21).index
    assert "NEW" in top_performers(fake_closes(), period_days=5).index  # 10 days is enough for 1 week


def test_wild_stock_gets_the_widest_range():
    table = top_performers(fake_closes(), period_days=21)
    assert table["typical_%"].idxmax() == "WILD"
    assert (table["bad_%"] <= 0).all()
