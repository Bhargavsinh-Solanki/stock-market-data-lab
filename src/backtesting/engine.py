"""Weekly top-k portfolio backtest from out-of-fold predictions.

Simulation loop (weekly rebalance, 5-trading-day hold):
  1. On each prediction date, rank tickers by predicted 5d log return.
  2. Long the top-k equal-weight (optionally short the bottom decile).
  3. Realize the actual forward 5d return, minus transaction costs on turnover.

All returns come from OOF walk-forward predictions, so the backtest never
sees a prediction made with future knowledge.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from src.utils.logging import get_logger

logger = get_logger(__name__)
WEEKS_PER_YEAR = 52


@dataclass
class BacktestReport:
    strategy: str
    top_k: int
    cost_bps: float
    total_return: float = np.nan
    annualized_return: float = np.nan
    sharpe: float = np.nan
    max_drawdown: float = np.nan
    avg_turnover: float = np.nan
    benchmark_return: float = np.nan
    equity_curve: pd.DataFrame = field(default_factory=pd.DataFrame)

    def metrics(self) -> dict[str, float]:
        return {
            "total_return": self.total_return,
            "annualized_return": self.annualized_return,
            "sharpe": self.sharpe,
            "max_drawdown": self.max_drawdown,
            "avg_turnover": self.avg_turnover,
            "benchmark_return": self.benchmark_return,
        }

    def equity_curve_json(self) -> str:
        if self.equity_curve.empty:
            return "[]"
        df = self.equity_curve.copy()
        df["date"] = df["date"].astype(str)
        return json.dumps(df.to_dict("records"))


def max_drawdown(equity: np.ndarray) -> float:
    peaks = np.maximum.accumulate(equity)
    return float(((equity - peaks) / peaks).min())


def run_backtest(
    oof: pd.DataFrame,
    label_col: str,
    top_k: int = 10,
    cost_bps: float = 10.0,
    long_short: bool = False,
    benchmark: pd.DataFrame | None = None,  # [date, ret] realized 5d log return of SPY
    rebalance_every: int = 1,               # in prediction dates (weekly grid -> 1)
) -> BacktestReport:
    """oof: [ticker, date, prediction, <label_col>] from run_walk_forward."""
    strategy = f"{'long_short' if long_short else 'long_only'}_top_{top_k}"
    report = BacktestReport(strategy=strategy, top_k=top_k, cost_bps=cost_bps)

    df = oof.dropna(subset=["prediction", label_col]).copy()
    if df.empty:
        logger.warning("No OOF predictions to backtest.")
        return report

    dates = sorted(df["date"].unique())[::rebalance_every]
    cost = cost_bps / 1e4
    prev_holdings: set[str] = set()
    rows = []
    for d in dates:
        g = df[df["date"] == d].sort_values("prediction", ascending=False)
        if len(g) < top_k:
            continue
        longs = g.head(top_k)
        gross = longs[label_col].map(lambda r: np.exp(r) - 1).mean()
        holdings = set(longs["ticker"])
        if long_short:
            shorts = g.tail(max(top_k, len(g) // 10))
            gross -= shorts[label_col].map(lambda r: np.exp(r) - 1).mean()
            holdings |= {f"-{t}" for t in shorts["ticker"]}
        turnover = (
            1.0 - len(holdings & prev_holdings) / len(holdings) if prev_holdings else 1.0
        )
        net = gross - 2 * cost * turnover  # round-trip cost on the changed sleeve
        rows.append({"date": d, "gross": gross, "net": net, "turnover": turnover})
        prev_holdings = holdings

    if not rows:
        return report
    periods = pd.DataFrame(rows).sort_values("date").reset_index(drop=True)
    equity = (1 + periods["net"]).cumprod()
    n_years = max(len(periods) / WEEKS_PER_YEAR, 1e-9)

    report.total_return = float(equity.iloc[-1] - 1)
    report.annualized_return = float(equity.iloc[-1] ** (1 / n_years) - 1)
    ret_std = periods["net"].std()
    report.sharpe = float(periods["net"].mean() / ret_std * np.sqrt(WEEKS_PER_YEAR)) if ret_std > 0 else np.nan
    report.max_drawdown = max_drawdown(equity.to_numpy())
    report.avg_turnover = float(periods["turnover"].mean())

    curve = pd.DataFrame({"date": periods["date"], "strategy": equity})
    if benchmark is not None and not benchmark.empty:
        bench = benchmark.set_index("date")["ret"].reindex(periods["date"]).fillna(0.0)
        bench_equity = (1 + bench.map(lambda r: np.exp(r) - 1)).cumprod()
        report.benchmark_return = float(bench_equity.iloc[-1] - 1)
        curve["benchmark"] = bench_equity.to_numpy()
    report.equity_curve = curve

    logger.info(
        "Backtest %s: total=%.1f%% sharpe=%.2f maxDD=%.1f%% turnover=%.0f%%",
        strategy, report.total_return * 100, report.sharpe,
        report.max_drawdown * 100, report.avg_turnover * 100,
    )
    return report
