"""Shared ingestion utilities: raw-event audit logging and run results."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

import duckdb
import pandas as pd

from src.db.engine import insert_ignore_df
from src.utils.hashing import stable_hash


@dataclass
class IngestionResult:
    source: str
    fetched: int = 0
    inserted: int = 0
    skipped_duplicates: int = 0
    errors: list[str] = field(default_factory=list)

    def summary(self) -> str:
        return (
            f"[{self.source}] fetched={self.fetched} inserted={self.inserted} "
            f"duplicates={self.skipped_duplicates} errors={len(self.errors)}"
        )


def store_raw_event(
    con: duckdb.DuckDBPyConnection, source: str, source_url: str, payload: str
) -> str:
    """Persist the raw response for auditability. Returns the event_id."""
    event_id = stable_hash(source, source_url, payload)
    df = pd.DataFrame(
        [
            {
                "event_id": event_id,
                "source": source,
                "source_url": source_url,
                "retrieved_at": datetime.now(timezone.utc).replace(tzinfo=None),
                "payload": payload,
                "status": "ok",
            }
        ]
    )
    insert_ignore_df(con, "raw_source_events", df)
    return event_id


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)
