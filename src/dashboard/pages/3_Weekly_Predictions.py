"""Page 4 — Weekly predictions table + distribution."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import numpy as np
import plotly.express as px
import streamlit as st

from src.dashboard.common import safe_query, show_disclaimer

st.set_page_config(page_title="Weekly Predictions", page_icon="🔮", layout="wide")
st.title("🔮 Weekly Predictions")
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
    st.stop()

preds["expected_return_pct"] = (np.exp(preds["predicted_log_return"]) - 1) * 100
st.caption(f"As of {preds['as_of_date'].iloc[0]} · model: {preds['model_name'].iloc[0]} · "
           f"horizon: {preds['horizon_days'].iloc[0]} trading days")

tab_top, tab_bottom, tab_all = st.tabs(["Top 10 predicted gainers", "Bottom 10", "All"])
cols = ["ticker", "expected_return_pct", "predicted_direction_prob", "confidence",
        "expected_risk_adj_return", "explanation"]
with tab_top:
    st.dataframe(preds.head(10)[cols], use_container_width=True, hide_index=True)
with tab_bottom:
    st.dataframe(preds.tail(10)[cols], use_container_width=True, hide_index=True)
with tab_all:
    st.dataframe(preds[cols], use_container_width=True, height=500, hide_index=True)

fig = px.histogram(preds, x="expected_return_pct", nbins=40,
                   title="Distribution of predicted 5-day returns (%)")
st.plotly_chart(fig, use_container_width=True)

scatter = px.scatter(
    preds, x="expected_return_pct", y="confidence", hover_name="ticker",
    color="predicted_direction_prob", color_continuous_scale="RdYlGn",
    title="Prediction vs confidence (color = P(up))",
)
st.plotly_chart(scatter, use_container_width=True)
