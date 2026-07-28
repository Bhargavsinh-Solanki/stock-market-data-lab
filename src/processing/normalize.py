"""Pure normalization helpers shared by all political-trade sources.

Kept free of I/O so they are trivially unit-testable.
"""
from __future__ import annotations

import re

# STOCK Act / PTR disclosure value buckets -> (min, max). The open-ended top
# bucket uses a conservative cap.
DISCLOSURE_SIZE_BUCKETS: dict[str, tuple[float, float]] = {
    "1K-15K": (1_001, 15_000),
    "15K-50K": (15_001, 50_000),
    "50K-100K": (50_001, 100_000),
    "100K-250K": (100_001, 250_000),
    "250K-500K": (250_001, 500_000),
    "500K-1M": (500_001, 1_000_000),
    "1M-5M": (1_000_001, 5_000_000),
    "5M-25M": (5_000_001, 25_000_000),
    "25M-50M": (25_000_001, 50_000_000),
    "50M+": (50_000_001, 100_000_000),
}

_TX_TYPE_MAP = {
    "buy": "buy", "purchase": "buy", "p": "buy",
    "sell": "sell", "sale": "sell", "s": "sell",
    "sale (full)": "sell", "sale (partial)": "sell", "s (partial)": "sell",
    "exchange": "exchange", "e": "exchange",
    "receive": "receive", "received": "receive",
}

_OWNER_MAP = {
    "self": "self", "sp": "spouse", "spouse": "spouse",
    "jt": "joint", "joint": "joint",
    "dc": "dependent", "dependent": "dependent", "child": "dependent",
    "undisclosed": "undisclosed", "--": "undisclosed", "": "undisclosed",
}


def normalize_tx_type(raw: str | None) -> str:
    if not raw:
        return "other"
    return _TX_TYPE_MAP.get(str(raw).strip().lower(), "other")


def normalize_owner(raw: str | None) -> str:
    if raw is None:
        return "undisclosed"
    return _OWNER_MAP.get(str(raw).strip().lower(), "undisclosed")


def normalize_ticker(raw: str | None) -> str | None:
    """'AAPL:US' -> 'AAPL'; placeholders like 'N/A' -> None."""
    if not raw:
        return None
    ticker = str(raw).strip().upper().split(":")[0]
    if not ticker or ticker in {"N/A", "NA", "--", "NONE"}:
        return None
    # BRK.B / BRK/B style class shares -> yfinance-compatible BRK-B
    ticker = ticker.replace("/", "-").replace(".", "-")
    return ticker if re.fullmatch(r"[A-Z0-9-]{1,10}", ticker) else None


def parse_size_range(raw: str | None) -> tuple[float | None, float | None]:
    """Parse a disclosure size string into (min, max) dollars.

    Handles both bucket labels ('1K–15K') and verbose ranges
    ('$1,001 - $15,000').
    """
    if not raw:
        return None, None
    text = str(raw).strip().replace("–", "-").replace("—", "-")
    key = text.replace(" ", "").upper()
    if key in DISCLOSURE_SIZE_BUCKETS:
        return DISCLOSURE_SIZE_BUCKETS[key]
    if key.endswith("+") and key[:-1] + "+" in DISCLOSURE_SIZE_BUCKETS:
        return DISCLOSURE_SIZE_BUCKETS[key[:-1] + "+"]
    numbers = re.findall(r"\$?([\d,]+(?:\.\d+)?)\s*([KMB]?)", text.upper())
    values: list[float] = []
    for num, suffix in numbers:
        if not num.replace(",", ""):
            continue
        value = float(num.replace(",", ""))
        value *= {"K": 1e3, "M": 1e6, "B": 1e9}.get(suffix, 1.0)
        values.append(value)
    if len(values) >= 2:
        return min(values[0], values[1]), max(values[0], values[1])
    if len(values) == 1:
        # A lone value that equals a disclosure-bucket lower bound is a
        # wrapped range with the upper bound lost (e.g. '$250,001 ' from a
        # PDF line break) — restore the full bucket.
        for lo, hi in DISCLOSURE_SIZE_BUCKETS.values():
            if abs(values[0] - lo) < 1:
                return lo, hi
        return values[0], values[0]
    return None, None


def size_midpoint(
    size_min: float | None, size_max: float | None, exact_value: float | None = None
) -> float | None:
    """Best estimate of trade dollar value: exact value if disclosed, else
    the midpoint of the reported bucket."""
    if exact_value is not None and exact_value > 0:
        return float(exact_value)
    if size_min is not None and size_max is not None:
        return (size_min + size_max) / 2.0
    return size_min if size_min is not None else size_max
