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


def _market_returns(n: int = 300, seed: int = 99) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range("2025-01-02", periods=n)
    log_spy = pd.Series(np.cumsum(rng.normal(0.0003, 0.008, n)))
    out = pd.DataFrame({
        "date": dates,
        "mkt_ret_1d": log_spy.diff(1).values,
        "mkt_ret_21d": log_spy.diff(21).values,
    })
    for h in (5, 21):
        out[f"mkt_fwd_ret_{h}d"] = (log_spy.shift(-h) - log_spy).values
    return out


def test_21d_labels_exist_alongside_5d():
    feats = compute_price_features(_prices(), horizon=5, extra_horizons=(21,))
    for col in ("label_fwd_log_ret_5d", "label_fwd_log_ret_21d",
                "label_direction_5d", "label_direction_21d"):
        assert col in feats.columns
    # 21d labels lose the last 21 rows, not 5
    s = feats.sort_values("date")
    assert s["label_fwd_log_ret_21d"].tail(21).isna().all()
    assert s["label_fwd_log_ret_21d"].iloc[-22] == s["label_fwd_log_ret_21d"].iloc[-22]  # not NaN


def test_residual_label_is_raw_minus_beta_times_market():
    feats = compute_price_features(_prices(), market_returns=_market_returns(), horizon=5)
    ok = feats.dropna(subset=["label_fwd_resid_ret_5d", "beta_63d",
                              "label_mkt_fwd_ret_5d", "label_fwd_log_ret_5d"])
    assert len(ok) > 50
    expected = ok["label_fwd_log_ret_5d"] - ok["beta_63d"] * ok["label_mkt_fwd_ret_5d"]
    assert np.allclose(ok["label_fwd_resid_ret_5d"], expected)


def test_forward_market_return_never_selectable_as_feature():
    """The forward market return is a future value; it must carry the label_
    prefix so feature_columns() excludes it."""
    feats = compute_price_features(_prices(), market_returns=_market_returns(), horizon=5)
    assert "mkt_fwd_ret_5d" not in feats.columns
    assert "label_mkt_fwd_ret_5d" in feats.columns
    from src.features.build import feature_columns
    assert all(not c.startswith("label_") for c in feature_columns(feats))
