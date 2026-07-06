"""Price/technical feature and label correctness tests."""
import numpy as np
import pandas as pd

from src.features.price_features import compute_price_features


def _prices(n: int = 300, ticker: str = "TEST", seed: int = 7) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range("2025-01-02", periods=n)
    close = 100 * np.exp(np.cumsum(rng.normal(0.0005, 0.01, n)))
    return pd.DataFrame({
        "ticker": ticker, "date": dates,
        "adj_close": close, "volume": rng.integers(1e5, 1e7, n),
    })


def test_forward_label_matches_manual_computation():
    df = _prices()
    feats = compute_price_features(df, horizon=5).sort_values("date").reset_index(drop=True)
    i = 100
    expected = np.log(df["adj_close"].iloc[i + 5]) - np.log(df["adj_close"].iloc[i])
    assert np.isclose(feats["label_fwd_log_ret_5d"].iloc[i], expected)
    # last 5 rows can have no label (future unknown)
    assert feats["label_fwd_log_ret_5d"].tail(5).isna().all()


def test_returns_are_log_returns():
    df = _prices()
    feats = compute_price_features(df, horizon=5).sort_values("date").reset_index(drop=True)
    i = 50
    expected = np.log(df["adj_close"].iloc[i]) - np.log(df["adj_close"].iloc[i - 21])
    assert np.isclose(feats["ret_21d"].iloc[i], expected)


def test_direction_label_binary_or_nan():
    feats = compute_price_features(_prices(), horizon=5)
    vals = feats["label_direction_5d"].dropna().unique()
    assert set(vals).issubset({0.0, 1.0})


def test_rsi_bounded():
    feats = compute_price_features(_prices(), horizon=5)
    rsi = feats["rsi_14"].dropna()
    assert ((rsi >= 0) & (rsi <= 100)).all()


def test_multiple_tickers_do_not_bleed():
    a, b = _prices(ticker="AAA", seed=1), _prices(ticker="BBB", seed=2)
    feats = compute_price_features(pd.concat([a, b], ignore_index=True), horizon=5)
    first_b = feats[feats["ticker"] == "BBB"].sort_values("date").iloc[0]
    assert np.isnan(first_b["ret_1d"])  # no return computed across the ticker boundary
