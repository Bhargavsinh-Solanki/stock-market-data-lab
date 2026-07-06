"""Page 2 — Latest political trades with filters."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import plotly.express as px
import streamlit as st

from src.dashboard.common import safe_query, show_disclaimer

st.set_page_config(page_title="Latest Political Trades", page_icon="📜", layout="wide")
st.title("📜 Latest Political Trades")
show_disclaimer()

trades = safe_query(
    """
    SELECT published_date, traded_date, politician_name, party, chamber, state,
           ticker, issuer_name, tx_type, owner, size_range, size_mid,
           filed_after_days, source, source_url
    FROM political_trades
    ORDER BY published_date DESC NULLS LAST, traded_date DESC
    LIMIT 5000
    """,
    required_table="political_trades",
)

if trades.empty:
    st.stop()

c1, c2, c3, c4 = st.columns(4)
chamber = c1.multiselect("Chamber", sorted(trades["chamber"].dropna().unique()))
party = c2.multiselect("Party", sorted(trades["party"].dropna().unique()))
tx = c3.multiselect("Type", sorted(trades["tx_type"].dropna().unique()))
ticker = c4.text_input("Ticker contains").strip().upper()

view = trades
if chamber:
    view = view[view["chamber"].isin(chamber)]
if party:
    view = view[view["party"].isin(party)]
if tx:
    view = view[view["tx_type"].isin(tx)]
if ticker:
    view = view[view["ticker"].fillna("").str.contains(ticker)]

m1, m2, m3 = st.columns(3)
m1.metric("Trades shown", f"{len(view):,}")
m2.metric("Unique politicians", f"{view['politician_name'].nunique():,}")
m3.metric("Median disclosure delay", f"{view['filed_after_days'].median():.0f} days"
          if view["filed_after_days"].notna().any() else "n/a")

st.dataframe(view, use_container_width=True, height=480)

top = (
    view.dropna(subset=["ticker"])
    .groupby(["ticker", "tx_type"]).size().rename("trades").reset_index()
    .sort_values("trades", ascending=False).head(40)
)
if not top.empty:
    st.plotly_chart(
        px.bar(top, x="ticker", y="trades", color="tx_type", barmode="stack",
               color_discrete_map={"buy": "#2ca02c", "sell": "#d62728"},
               title="Most-traded tickers in current view"),
        use_container_width=True,
    )
