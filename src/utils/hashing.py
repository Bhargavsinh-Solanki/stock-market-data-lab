"""Stable content hashing used for idempotent, deduplicated ingestion."""
from __future__ import annotations

import hashlib
from typing import Any


def stable_hash(*parts: Any) -> str:
    """Deterministic sha256 over the string form of the given parts.

    None values are normalized to the literal "null" so that hashes stay
    stable when optional fields are missing versus explicitly null.
    """
    normalized = "|".join("null" if p is None else str(p).strip().lower() for p in parts)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()
