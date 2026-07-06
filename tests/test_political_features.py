"""Political-feature tests, especially the anti-lookahead guarantee."""
import pandas as pd

from src.features.political_features import compute_political_features


def _panel(ticker: str = "AAPL") -> pd.DataFrame:
    dates = pd.bdate_range("2026-01-05", "2026-03-31")
    return pd.DataFrame({"ticker": ticker, "date": dates})


def _trade(published: str, tx_type: str = "buy", size_mid: float = 8_000.0,
           politician_id: str = "P1", **overrides) -> dict:
    row = {
        "ticker": "AAPL", "published_date": published, "traded_date": "2026-01-02",
        "tx_type": tx_type, "size_mid": size_mid, "politician_id": politician_id,
        "chamber": "house", "party": "democrat", "owner": "self",
        "filed_after_days": 10,
    }
    row.update(overrides)
    return row


def test_no_lookahead_before_published_date():
    """A trade disclosed on Feb 10 must contribute nothing before Feb 10 —
    even though it was executed on Jan 2."""
    trades = pd.DataFrame([_trade(published="2026-02-10")])
    feats = compute_political_features(trades, _panel())
    before = feats[feats["date"] < "2026-02-10"]
    on_after = feats[(feats["date"] >= "2026-02-10") & (feats["date"] <= "2026-02-20")]
    assert (before["pol_buy_count_30d"] == 0).all()
    assert (on_after["pol_buy_count_30d"] == 1).all()


def test_window_expiry():
    trades = pd.DataFrame([_trade(published="2026-01-10")])
    feats = compute_political_features(trades, _panel())
    in_window = feats[feats["date"] == "2026-01-15"].iloc[0]
    out_of_window = feats[feats["date"] == "2026-03-20"].iloc[0]
    assert in_window["pol_buy_count_7d"] == 1
    assert out_of_window["pol_buy_count_60d"] == 0


def test_amounts_and_net_pressure():
    trades = pd.DataFrame([
        _trade(published="2026-01-10", tx_type="buy", size_mid=10_000),
        _trade(published="2026-01-12", tx_type="sell", size_mid=5_000, politician_id="P2"),
    ])
    feats = compute_political_features(trades, _panel())
    row = feats[feats["date"] == "2026-01-20"].iloc[0]
    assert row["pol_buy_amount_30d"] == 10_000
    assert row["pol_sell_amount_30d"] == 5_000
    assert 0 < row["pol_net_buy_pressure_30d"] < 1
    assert row["pol_unique_politicians_30d"] == 2


def test_unaffected_ticker_stays_zero():
    trades = pd.DataFrame([_trade(published="2026-01-10")])
    panel = pd.concat([_panel("AAPL"), _panel("MSFT")], ignore_index=True)
    feats = compute_political_features(trades, panel)
    msft = feats[feats["ticker"] == "MSFT"]
    assert (msft["pol_buy_count_30d"] == 0).all()


def test_empty_trades_returns_zero_features():
    feats = compute_political_features(pd.DataFrame(), _panel())
    assert (feats["pol_buy_count_30d"] == 0).all()
    assert len(feats) == len(_panel())
