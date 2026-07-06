"""Page 8 — Next Week Movers: stocks predicted to go UP or DOWN next week."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import numpy as np
import plotly.express as px
import streamlit as st

from src.dashboard.common import safe_query, show_disclaimer

st.set_page_config(page_title="Next Week Movers", page_icon="🚦", layout="wide")
st.title("🚦 Next Week Movers")
show_disclaimer()

preds = safe_query(
    """
    SELECT ticker, as_of_date, horizon_days, predicted_log_return,
           predicted_direction_prob, pred_lower, pred_upper, confidence,
           expected_risk_adj_return, model_name, explanation
    FROM predictions_weekly
    WHERE as_of_date = (SELECT max(as_of_date) FROM predictions_weekly)
    ORDER BY predicted_log_return DESC
    """,
    required_table="predictions_weekly",
)
if preds.empty:
    st.info("No predictions yet — run scripts/generate_weekly_predictions.py")
    st.stop()

preds["expected_return_pct"] = (np.exp(preds["predicted_log_return"]) - 1) * 100
preds["interval"] = preds.apply(
    lambda r: f"{(np.exp(r['pred_lower']) - 1) * 100:+.1f}% … {(np.exp(r['pred_upper']) - 1) * 100:+.1f}%",
    axis=1,
)
st.caption(
    f"As of {preds['as_of_date'].iloc[0]} · model: {preds['model_name'].iloc[0]} · "
    f"horizon: {preds['horizon_days'].iloc[0]} trading days · {len(preds)} tickers"
)

# --- controls ---
c1, c2 = st.columns([1, 2])
basis = c1.radio(
    "Direction based on",
    ["Predicted return sign", "Direction classifier P(up)"],
    help="Return sign uses the regressor's forecast; P(up) uses the separate "
         "direction classifier (threshold 0.5).",
)
min_conf = c2.slider("Minimum confidence", 0.0, 1.0, 0.0, 0.05)

view = preds[preds["confidence"] >= min_conf].copy()
if basis == "Predicted return sign":
    view["direction"] = np.where(view["predicted_log_return"] > 0, "up", "down")
else:
    prob = view["predicted_direction_prob"].fillna(0.5)
    view["direction"] = np.where(prob > 0.5, "up", "down")

up = view[view["direction"] == "up"].sort_values("expected_return_pct", ascending=False)
down = view[view["direction"] == "down"].sort_values("expected_return_pct")

m1, m2, m3 = st.columns(3)
m1.metric("Predicted UP 📈", len(up))
m2.metric("Predicted DOWN 📉", len(down))
breadth = len(up) / len(view) * 100 if len(view) else 0
m3.metric("Bullish breadth", f"{breadth:.0f}%",
          help="Share of covered tickers predicted to rise next week")

TABLE_COLS = ["ticker", "expected_return_pct", "predicted_direction_prob",
              "confidence", "expected_risk_adj_return", "interval"]
COL_CFG = {
    "ticker": st.column_config.TextColumn("Ticker"),
    "expected_return_pct": st.column_config.NumberColumn("Exp. 5d return", format="%+.2f%%"),
    "predicted_direction_prob": st.column_config.ProgressColumn(
        "P(up)", min_value=0.0, max_value=1.0, format="%.2f"),
    "confidence": st.column_config.NumberColumn("Confidence", format="%.2f"),
    "expected_risk_adj_return": st.column_config.NumberColumn("Risk-adj", format="%.2f"),
    "interval": st.column_config.TextColumn("80% interval"),
}

left, right = st.columns(2)
with left:
    st.subheader(f"📈 Predicted to rise ({len(up)})")
    st.dataframe(up[TABLE_COLS], use_container_width=True, hide_index=True,
                 height=420, column_config=COL_CFG)
with right:
    st.subheader(f"📉 Predicted to fall ({len(down)})")
    st.dataframe(down[TABLE_COLS], use_container_width=True, hide_index=True,
                 height=420, column_config=COL_CFG)

# --- diverging overview chart ---
chart = view.sort_values("expected_return_pct")
fig = px.bar(
    chart, x="expected_return_pct", y="ticker", orientation="h",
    color="direction", color_discrete_map={"up": "#2ca02c", "down": "#d62728"},
    hover_data={"predicted_direction_prob": ":.2f", "confidence": ":.2f"},
    title="Predicted 5-day return by ticker (%)",
    height=max(400, 18 * len(chart)),
)
fig.update_layout(yaxis_title=None, xaxis_title="expected return %", showlegend=False)
st.plotly_chart(fig, use_container_width=True)

# --- per-ticker explanation ---
st.subheader("Why? Per-ticker explanation")
pick = st.selectbox("Ticker", view.sort_values("ticker")["ticker"].tolist())
row = view[view["ticker"] == pick].iloc[0]
st.info(row["explanation"])
