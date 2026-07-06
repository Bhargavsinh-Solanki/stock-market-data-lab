"""DuckDB access layer. Swap for PostgreSQL by replacing this module
(schema.sql is written to be portable)."""
from __future__ import annotations

from pathlib import Path

import duckdb
import pandas as pd

from src.config.settings import get_settings
from src.utils.logging import get_logger

logger = get_logger(__name__)
SCHEMA_PATH = Path(__file__).parent / "schema.sql"


def get_connection(read_only: bool = False) -> duckdb.DuckDBPyConnection:
    settings = get_settings()
    db_path = Path(settings.db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return duckdb.connect(str(db_path), read_only=read_only)


def init_db(con: duckdb.DuckDBPyConnection | None = None) -> None:
    """Create all tables if they do not exist (idempotent)."""
    own = con is None
    con = con or get_connection()
    con.execute(SCHEMA_PATH.read_text())
    if own:
        con.close()
    logger.info("Database schema ensured at %s", get_settings().db_path)


def insert_ignore_df(
    con: duckdb.DuckDBPyConnection, table: str, df: pd.DataFrame
) -> int:
    """Insert rows, silently skipping primary-key conflicts (idempotent loads).

    Returns the number of newly inserted rows.
    """
    if df.empty:
        return 0
    before = con.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
    cols = ", ".join(df.columns)
    con.register("_incoming_df", df)
    con.execute(
        f"INSERT INTO {table} ({cols}) "
        f"SELECT {cols} FROM _incoming_df ON CONFLICT DO NOTHING"
    )
    con.unregister("_incoming_df")
    after = con.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
    return int(after - before)


def upsert_df(
    con: duckdb.DuckDBPyConnection, table: str, df: pd.DataFrame, key_cols: list[str]
) -> None:
    """Delete-then-insert upsert keyed on key_cols (fine at MVP scale)."""
    if df.empty:
        return
    con.register("_incoming_df", df)
    on = " AND ".join(f"t.{c} = s.{c}" for c in key_cols)
    con.execute(f"DELETE FROM {table} t USING _incoming_df s WHERE {on}")
    cols = ", ".join(df.columns)
    con.execute(f"INSERT INTO {table} ({cols}) SELECT {cols} FROM _incoming_df")
    con.unregister("_incoming_df")


def read_df(con: duckdb.DuckDBPyConnection, query: str, params: list | None = None) -> pd.DataFrame:
    return con.execute(query, params or []).fetch_df()


def table_exists(con: duckdb.DuckDBPyConnection, table: str) -> bool:
    row = con.execute(
        "SELECT count(*) FROM information_schema.tables WHERE table_name = ?", [table]
    ).fetchone()
    return bool(row and row[0])
