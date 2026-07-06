"""Backtest engine sanity tests."""
import numpy as np
import pandas as pd

from src.backtesting.engine import max_drawdown, run_backtest


def _oof(n_dates: int = 30, n_tickers: int = 30, seed: int = 3) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range("2025-01-03", periods=n_dates, freq="W-FRI")
    rows = []
    for d in dates:
        for i in range(n_tickers):
            true_ret = rng.normal(0, 0.03)
            rows.append({
                "ticker": f"T{i:03d}", "date": d,
                # prediction correlated with truth -> strategy should profit
                "prediction": true_ret + rng.normal(0, 0.01),
                "label": true_ret,
            })
    return pd.DataFrame(rows)


def test_skillful_predictions_beat_zero():
    report = run_backtest(_oof(), label_col="label", top_k=5, cost_bps=5)
    assert report.total_return > 0
    assert not report.equity_curve.empty


def test_costs_reduce_returns():
    oof = _oof()
    cheap = run_backtest(oof, label_col="label", top_k=5, cost_bps=0)
    pricey = run_backtest(oof, label_col="label", top_k=5, cost_bps=100)
    assert cheap.total_return > pricey.total_return


def test_max_drawdown_negative_and_bounded():
    equity = np.array([1.0, 1.2, 0.9, 1.1, 1.3])
    dd = max_drawdown(equity)
    assert -1.0 <= dd <= 0.0
    assert np.isclose(dd, (0.9 - 1.2) / 1.2)


def test_empty_predictions_do_not_crash():
    report = run_backtest(pd.DataFrame(columns=["ticker", "date", "prediction", "label"]),
                          label_col="label")
    assert np.isnan(report.total_return)
