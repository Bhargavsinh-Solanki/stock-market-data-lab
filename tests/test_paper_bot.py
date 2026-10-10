"""Tests for paper_bot.py - pure logic, no Alpaca connection needed."""

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lab.paper_bot import BUY, HOLD, SELL, STAY_OUT, WAIT, decide, shares_for, trend_rule  # noqa: E402


def test_every_row_of_the_decision_table():
    assert decide(rule_says_own=True, shares_held=0, order_pending=False) == BUY
    assert decide(rule_says_own=True, shares_held=5, order_pending=False) == HOLD
    assert decide(rule_says_own=False, shares_held=5, order_pending=False) == SELL
    assert decide(rule_says_own=False, shares_held=0, order_pending=False) == STAY_OUT
    assert decide(rule_says_own=True, shares_held=0, order_pending=True) == WAIT


def test_shares_for_budget_uses_whole_shares():
    assert shares_for(5000, 777.79) == 6      # 6 x 777.79 = 4,666.74
    assert shares_for(5000, 14.42) == 346
    assert shares_for(500, 777.79) == 0       # can't afford one share


def test_trend_rule():
    rising = pd.Series(range(1, 61), dtype=float)   # 1..60, always above its average
    falling = pd.Series(range(60, 0, -1), dtype=float)
    assert trend_rule(rising, ma_days=50)[0] is True
    assert trend_rule(falling, ma_days=50)[0] is False
