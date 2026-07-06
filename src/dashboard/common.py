"""Shared dashboard helpers: DB access, disclaimer, empty-state handling."""
from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd
import streamlit as st

from src.config.settings import DISCLAIMER, get_settings  # noqa: E402
from src.db.engine import get_connection, table_exists  # noqa: E402


def show_disclaimer() -> None:
    st.caption(DISCLAIMER)


@st.cache_data(ttl=300, show_spinner=False)
def query(sql: str, params: tuple = ()) -> pd.DataFrame:
    con = get_connection(read_only=True)
    try:
        return con.execute(sql, list(params)).fetch_df()
    finally:
        con.close()


def safe_query(sql: str, params: tuple = (), required_table: str | None = None) -> pd.DataFrame:
    """Query that returns an empty frame (with a friendly note) when data
    hasn't been ingested yet, instead of crashing the page."""
    try:
        if required_table:
            con = get_connection(read_only=True)
            try:
                if not table_exists(con, required_table):
                    st.info(
                        f"Table `{required_table}` doesn't exist yet. "
                        "Run `python scripts/run_daily_ingestion.py` (and the feature/"
                        "training scripts) to populate the platform."
                    )
                    return pd.DataFrame()
            finally:
                con.close()
        return query(sql, params)
    except Exception as exc:  # noqa: BLE001
        st.warning(f"Query failed: {exc}")
        return pd.DataFrame()
