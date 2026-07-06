"""Page 7 — Data quality monitor: freshness, coverage, ingestion audit."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import plotly.express as px
import streamlit as st

from src.dashboard.common import safe_query, show_disclaimer

st.set_page_config(page_title="Data Quality", page_icon="✅", layout="wide")
st.title("✅ Data Quality Monitor")
show_disclaimer()

st.subheader("Freshness")
freshness = safe_query(
    """
    SELECT 'prices_daily' AS dataset, max(date)::VARCHAR AS latest, count(*) AS rows FROM prices_daily
    UNION ALL
    SELECT 'political_trades', max(published_date)::VARCHAR, count(*) FROM political_trades
    UNION ALL
    SELECT 'macro_daily', max(date)::VARCHAR, count(*) FROM macro_daily
    UNION ALL
    SELECT 'raw_source_events', max(retrieved_at)::VARCHAR, count(*) FROM raw_source_events
    """,
    required_table="prices_daily",
)
if not freshness.empty:
    st.dataframe(freshness, use_container_width=True, hide_index=True)

st.subheader("Price coverage")
coverage = safe_query(
    """
    SELECT ticker, count(*) AS days, min(date)::VARCHAR AS first_date,
           max(date)::VARCHAR AS last_date
    FROM prices_daily GROUP BY ticker ORDER BY days ASC LIMIT 30
    """,
    required_table="prices_daily",
)
if not coverage.empty:
    st.caption("Tickers with the least history (watch for delisted/missing symbols):")
    st.dataframe(coverage, use_container_width=True, hide_index=True)

st.subheader("Political trades: null & mapping rates")
nulls = safe_query(
    """
    SELECT
      count(*) AS total_trades,
      round(100.0 * count(*) FILTER (ticker IS NULL) / count(*), 1) AS pct_no_ticker,
      round(100.0 * count(*) FILTER (size_mid IS NULL) / count(*), 1) AS pct_no_size,
      round(100.0 * count(*) FILTER (published_date IS NULL) / count(*), 1) AS pct_no_pub_date,
      round(avg(filed_after_days), 1) AS avg_disclosure_delay_days
    FROM political_trades
    """,
    required_table="political_trades",
)
if not nulls.empty:
    st.dataframe(nulls, use_container_width=True, hide_index=True)

st.subheader("Ingestion audit trail (raw_source_events)")
events = safe_query(
    """
    SELECT source, date_trunc('day', retrieved_at)::VARCHAR AS day, count(*) AS fetches
    FROM raw_source_events
    WHERE retrieved_at >= current_date - INTERVAL 30 DAY
    GROUP BY 1, 2 ORDER BY 2
    """,
    required_table="raw_source_events",
)
if not events.empty:
    st.plotly_chart(
        px.bar(events, x="day", y="fetches", color="source",
               title="Raw fetches per day by source (last 30 days)"),
        use_container_width=True,
    )
st.caption("Every stored row links back to a raw payload with source URL and "
           "retrieval timestamp for full auditability.")
