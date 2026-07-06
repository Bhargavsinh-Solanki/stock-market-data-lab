"""Macro join tests: observations on non-trading days must survive the
forward-fill onto the trading calendar (World Bank annual values are dated
Dec 31, monthly series the 1st — often weekends/holidays)."""
import numpy as np
import pandas as pd

from src.features.macro_features import compute_macro_features


def _calendar() -> pd.Series:
    return pd.Series(pd.bdate_range("2022-01-03", "2022-03-31"))


def test_weekend_observation_carries_to_next_trading_day():
    # 2022-01-01 is a Saturday — not in the trading calendar.
    macro = pd.DataFrame([
        {"series_id": "WB_FP_CPI_TOTL_ZG_USA", "date": "2021-12-31", "value": 4.7},
        {"series_id": "WB_FP_CPI_TOTL_ZG_USA", "date": "2022-01-01", "value": 5.0},
    ])
    out = compute_macro_features(macro, _calendar())
    col = "macro_wb_fp_cpi_totl_zg_usa"
    assert col in out.columns
    # first trading day after the weekend observations carries the value
    first = out[out["date"] == "2022-01-03"].iloc[0]
    assert first[col] == 5.0
    # and it forward-fills across the whole quarter (no all-NaN column)
    assert out[col].notna().all()


def test_trading_day_observation_not_shifted():
    macro = pd.DataFrame([
        {"series_id": "ECB_EURUSD", "date": "2022-02-01", "value": 1.12},  # Tuesday
    ])
    out = compute_macro_features(macro, _calendar())
    before = out[out["date"] == "2022-01-31"].iloc[0]
    on = out[out["date"] == "2022-02-01"].iloc[0]
    assert np.isnan(before["macro_ecb_eurusd"])  # no backfill (would be lookahead)
    assert on["macro_ecb_eurusd"] == 1.12


def test_empty_macro_returns_calendar_only():
    out = compute_macro_features(pd.DataFrame(), _calendar())
    assert list(out.columns) == ["date"]
    assert len(out) == len(_calendar())
