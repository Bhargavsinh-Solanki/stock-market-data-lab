"""Page 5 — Walk-forward backtest results."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import pandas as pd
import plotly.express as px
import streamlit as st

from src.dashboard.common import safe_query, show_disclaimer

st.set_page_config(page_title="Backtest Results", page_icon="📈", layout="wide")
st.title("📈 Backtest Results")
show_disclaimer()
st.caption("All results are from out-of-fold walk-forward predictions with "
           "embargo — no random splits, no lookahead. Past performance of a "
           "research signal is not indicative of future results.")

bt = safe_query(
    "SELECT * FROM backtest_results ORDER BY created_at DESC",
    required_table="backtest_results",
)
if bt.empty:
    st.stop()

options = [f"{r.model_name} · {r.strategy} · {r.created_at}" for r in bt.itertuples()]
choice = st.selectbox("Backtest run", options)
run = bt.iloc[options.index(choice)]

c = st.columns(6)
c[0].metric("Total return", f"{run['total_return'] * 100:.1f}%")
c[1].metric("Annualized", f"{run['annualized_return'] * 100:.1f}%")
c[2].metric("Sharpe", f"{run['sharpe']:.2f}")
c[3].metric("Max drawdown", f"{run['max_drawdown'] * 100:.1f}%")
c[4].metric("Avg turnover", f"{run['avg_turnover'] * 100:.0f}%")
c[5].metric(f"Benchmark ({run['benchmark_ticker']})",
            f"{run['benchmark_return'] * 100:.1f}%" if pd.notna(run["benchmark_return"]) else "n/a")

curve = pd.DataFrame(json.loads(run["equity_curve_json"] or "[]"))
if not curve.empty:
    curve["date"] = pd.to_datetime(curve["date"])
    melted = curve.melt(id_vars="date", var_name="series", value_name="equity")
    st.plotly_chart(
        px.line(melted, x="date", y="equity", color="series",
                title=f"Equity curve — {run['strategy']} (cost {run['cost_bps']:.0f} bps)"),
        use_container_width=True,
    )

st.subheader("All recorded backtests")
st.dataframe(
    bt.drop(columns=["equity_curve_json"]), use_container_width=True, hide_index=True
)
