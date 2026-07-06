"""Page 3 — Ticker detail: price, political flow, prediction, drivers, sources."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import numpy as np
import plotly.graph_objects as go
import streamlit as st

from src.dashboard.common import safe_query, show_disclaimer

st.set_page_config(page_title="Ticker Detail", page_icon="🔎", layout="wide")
st.title("🔎 Ticker Detail")
show_disclaimer()

tickers = safe_query(
    "SELECT DISTINCT ticker FROM prices_daily WHERE ticker NOT LIKE '^%' ORDER BY ticker",
    required_table="prices_daily",
)
if tickers.empty:
    st.stop()
ticker = st.selectbox("Ticker", tickers["ticker"].tolist())

prices = safe_query(
    "SELECT date, open, high, low, close, adj_close, volume FROM prices_daily "
    "WHERE ticker = ? AND date >= current_date - INTERVAL 365 DAY ORDER BY date",
    (ticker,),
)
trades = safe_query(
    "SELECT published_date, traded_date, politician_name, party, chamber, tx_type, "
    "owner, size_range, size_mid, filed_after_days, source_url "
    "FROM political_trades WHERE ticker = ? ORDER BY published_date DESC LIMIT 200",
    (ticker,), required_table="political_trades",
)
pred = safe_query(
    "SELECT * FROM predictions_weekly WHERE ticker = ? ORDER BY as_of_date DESC LIMIT 1",
    (ticker,), required_table="predictions_weekly",
)

left, right = st.columns([2, 1])

with left:
    if not prices.empty:
        fig = go.Figure(go.Candlestick(
            x=prices["date"], open=prices["open"], high=prices["high"],
            low=prices["low"], close=prices["close"], name=ticker,
        ))
        buys = trades[trades["tx_type"] == "buy"] if not trades.empty else None
        sells = trades[trades["tx_type"] == "sell"] if not trades.empty else None
        for sub, color, label in ((buys, "green", "political buy"), (sells, "red", "political sell")):
            if sub is not None and not sub.empty:
                merged = sub.merge(prices, left_on="published_date", right_on="date")
                fig.add_scatter(x=merged["date"], y=merged["adj_close"], mode="markers",
                                marker=dict(color=color, size=10, symbol="triangle-up" if color == "green" else "triangle-down"),
                                name=label)
        fig.update_layout(title=f"{ticker} — 12 months (markers = disclosure published)",
                          xaxis_rangeslider_visible=False, height=480)
        st.plotly_chart(fig, use_container_width=True)

with right:
    st.subheader("Next-week prediction")
    if pred.empty:
        st.info("No prediction yet — run scripts/generate_weekly_predictions.py")
    else:
        p = pred.iloc[0]
        exp_pct = (np.exp(p["predicted_log_return"]) - 1) * 100
        st.metric("Expected 5-day return", f"{exp_pct:+.2f}%",
                  help="Model forecast — research signal only")
        lo = (np.exp(p["pred_lower"]) - 1) * 100
        hi = (np.exp(p["pred_upper"]) - 1) * 100
        st.write(f"**80% interval:** {lo:+.2f}% … {hi:+.2f}%")
        if p.get("predicted_direction_prob") is not None:
            st.write(f"**P(up):** {p['predicted_direction_prob']:.0%}")
        st.write(f"**Confidence:** {p['confidence']:.2f} · **Risk-adj:** "
                 f"{p['expected_risk_adj_return']:.2f}" if p.get("expected_risk_adj_return") else "")
        st.info(p["explanation"])

    st.subheader("Political buy/sell pressure (90d)")
    if not trades.empty:
        recent = trades[trades["published_date"] >= (np.datetime64("today") - np.timedelta64(90, "D"))]
        buys_amt = recent.loc[recent["tx_type"] == "buy", "size_mid"].sum()
        sells_amt = recent.loc[recent["tx_type"] == "sell", "size_mid"].sum()
        c1, c2 = st.columns(2)
        c1.metric("Est. buys", f"${buys_amt:,.0f}")
        c2.metric("Est. sells", f"${sells_amt:,.0f}")
        net = (buys_amt - sells_amt) / (buys_amt + sells_amt + 1e-9)
        st.progress((net + 1) / 2, text=f"Net buy pressure: {net:+.2f}")
    else:
        st.write("No disclosed congressional trades for this ticker.")

st.subheader("Recent political trades")
if not trades.empty:
    st.dataframe(trades, use_container_width=True, height=320)
    st.caption("Source links: " + " · ".join(sorted(set(trades["source_url"].dropna().head(3)))))
