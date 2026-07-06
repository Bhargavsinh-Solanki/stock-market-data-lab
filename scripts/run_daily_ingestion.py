#!/usr/bin/env python
"""Daily ingestion job — run after US market close (e.g. 22:30 UTC weekdays).

Order matters: political trades first so newly disclosed tickers join the
price universe in the same run.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.db.engine import get_connection, init_db
from src.ingestion import (
    capitol_trades,
    ecb,
    house_disclosures,
    macro,
    market_prices,
    senate_disclosures,
    stooq,
    world_bank,
)
from src.utils.logging import get_logger

logger = get_logger("daily_ingestion")


def main() -> int:
    parser = argparse.ArgumentParser(description="Run all daily ingestion jobs.")
    parser.add_argument("--skip-prices", action="store_true")
    parser.add_argument("--skip-political", action="store_true")
    parser.add_argument("--skip-macro", action="store_true")
    args = parser.parse_args()

    init_db()
    con = get_connection()
    results = []
    try:
        if not args.skip_political:
            results.append(capitol_trades.run(con))
            results.append(house_disclosures.run(con))
            results.append(senate_disclosures.run(con))
        if not args.skip_prices:
            results.append(market_prices.run(con))
            results.append(stooq.run(con))       # second source: global indices
        if not args.skip_macro:
            results.append(macro.run(con))       # FRED (US)
            results.append(ecb.run(con))         # ECB (euro area)
            results.append(world_bank.run(con))  # World Bank (global annual)
    finally:
        con.close()

    logger.info("=== Daily ingestion complete ===")
    failures = 0
    for r in results:
        logger.info(r.summary())
        failures += len(r.errors)
    return 1 if failures and all(r.inserted == 0 for r in results) else 0


if __name__ == "__main__":
    raise SystemExit(main())
