"""Page 1 — Market Overview. Entry point: streamlit run src/dashboard/app.py"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import plotly.express as px
import streamlit as st

from src.dashboard.common import safe_query, show_disclaimer

st.set_page_config(
    page_title="Political Trades Intelligence", page_icon="🏛️", layout="wide"
)
st.title("🏛️ Global Political Trades Stock Intelligence")
show_disclaimer()

st.header("Market Overview")

indices = safe_query(
    """
    SELECT ticker, date, adj_close FROM prices_daily
    WHERE ticker IN ('SPY', 'QQQ', '^DJI', '^VIX')
      AND date >= current_date - INTERVAL 365 DAY
    ORDER BY date
    """,
    required_table="prices_daily",
)

if not indices.empty:
    cols = st.columns(4)
    labels = {"SPY": "S&P 500 (SPY)", "QQQ": "Nasdaq 100 (QQQ)", "^DJI": "Dow Jones", "^VIX": "VIX"}
    for col, ticker in zip(cols, ["SPY", "QQQ", "^DJI", "^VIX"]):
        s = indices[indices["ticker"] == ticker].sort_values("date")
        if len(s) >= 2:
            last, prev = s["adj_close"].iloc[-1], s["adj_close"].iloc[-2]
            col.metric(labels[ticker], f"{last:,.2f}", f"{(last / prev - 1) * 100:+.2f}%")

    norm = indices[indices["ticker"] != "^VIX"].copy()
    norm["indexed"] = norm.groupby("ticker")["adj_close"].transform(lambda s: s / s.iloc[0] * 100)
    fig = px.line(norm, x="date", y="indexed", color="ticker",
                  title="Major indices — last 12 months (indexed to 100)")
    st.plotly_chart(fig, use_container_width=True)

    vix = indices[indices["ticker"] == "^VIX"]
    if not vix.empty:
        st.plotly_chart(px.area(vix, x="date", y="adj_close", title="VIX"), use_container_width=True)

st.subheader("Recent political trading activity")
activity = safe_query(
    """
    SELECT published_date AS date,
           count(*) FILTER (tx_type = 'buy')  AS buys,
           count(*) FILTER (tx_type = 'sell') AS sells
    FROM political_trades
    WHERE published_date >= current_date - INTERVAL 90 DAY
    GROUP BY 1 ORDER BY 1
    """,
    required_table="political_trades",
)
if not activity.empty:
    melted = activity.melt(id_vars="date", value_vars=["buys", "sells"],
                           var_name="side", value_name="count")
    st.plotly_chart(
        px.bar(melted, x="date", y="count", color="side", barmode="group",
               color_discrete_map={"buys": "#2ca02c", "sells": "#d62728"},
               title="Disclosed congressional trades per day (by published date)"),
        use_container_width=True,
    )
