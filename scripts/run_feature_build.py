#!/usr/bin/env python
"""Rebuild features_daily and features_weekly from normalized tables."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.features.build import build_features
from src.utils.logging import get_logger

logger = get_logger("feature_build")

if __name__ == "__main__":
    feats = build_features(write=True)
    logger.info(
        "Feature build done: %d rows, %d tickers, %s → %s",
        len(feats), feats["ticker"].nunique(), feats["date"].min().date(), feats["date"].max().date(),
    )
