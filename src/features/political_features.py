"""Political-trade features at (ticker, date) level.

CRITICAL anti-lookahead rule: all windows are keyed on `published_date`
(when the disclosure became public), never `traded_date`. A trade executed on
Jan 2 but disclosed on Feb 10 contributes to features from Feb 10 onward.
Features are assumed to be consumed after the market close of `date`, so a
disclosure published on `date` is included (pub <= date).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

WINDOWS = (7, 14, 30, 60)
_EPS = 1e-9


def _empty_features(panel: pd.DataFrame) -> pd.DataFrame:
    out = panel.copy()
    for w in WINDOWS:
        for col in (f"pol_buy_count_{w}d", f"pol_sell_count_{w}d",
                    f"pol_buy_amount_{w}d", f"pol_sell_amount_{w}d"):
            out[col] = 0.0
    for col in ("pol_net_buy_pressure_30d", "pol_unique_politicians_30d",
                "pol_house_trades_30d", "pol_senate_trades_30d",
                "pol_dem_trades_30d", "pol_rep_trades_30d",
                "pol_self_owner_trades_30d", "pol_spouse_owner_trades_30d",
                "pol_avg_disclosure_delay_30d", "pol_activity_zscore_30d",
                "pol_committee_relevance"):
        out[col] = 0.0
    return out


def compute_political_features(trades: pd.DataFrame, panel: pd.DataFrame) -> pd.DataFrame:
    """trades: normalized political_trades rows.
    panel: [ticker, date] trading-day grid to compute features for.
    """
    panel = panel[["ticker", "date"]].copy()
    panel["date"] = pd.to_datetime(panel["date"])

    if trades is None or trades.empty:
        return _empty_features(panel)

    t = trades.dropna(subset=["ticker", "published_date"]).copy()
    if t.empty:
        return _empty_features(panel)
    t["published_date"] = pd.to_datetime(t["published_date"])
    t["is_buy"] = (t["tx_type"] == "buy").astype(float)
    t["is_sell"] = (t["tx_type"] == "sell").astype(float)
    t["buy_amt"] = t["is_buy"] * t["size_mid"].fillna(0.0)
    t["sell_amt"] = t["is_sell"] * t["size_mid"].fillna(0.0)
    t["is_house"] = (t["chamber"] == "house").astype(float)
    t["is_senate"] = (t["chamber"] == "senate").astype(float)
    t["is_dem"] = (t["party"] == "democrat").astype(float)
    t["is_rep"] = (t["party"] == "republican").astype(float)
    t["is_self"] = (t["owner"] == "self").astype(float)
    t["is_spouse"] = (t["owner"] == "spouse").astype(float)
    t["delay"] = t["filed_after_days"].fillna(0.0).clip(lower=0)

    sum_cols = ["is_buy", "is_sell", "buy_amt", "sell_amt", "is_house",
                "is_senate", "is_dem", "is_rep", "is_self", "is_spouse", "delay"]
    chunks: list[pd.DataFrame] = []

    for ticker, g in panel.groupby("ticker", sort=False):
        g = g.sort_values("date").copy()
        tt = t[t["ticker"] == ticker].sort_values("published_date")
        if tt.empty:
            chunks.append(_empty_features(g))
            continue

        pub = tt["published_date"].to_numpy()
        dates = g["date"].to_numpy()
        # cumulative sums with a leading zero -> O(1) window aggregation
        cum = {c: np.concatenate(([0.0], np.cumsum(tt[c].to_numpy(dtype=float))))
               for c in sum_cols}
        hi = np.searchsorted(pub, dates, side="right")  # pub <= date

        def window_sum(col: str, w: int) -> np.ndarray:
            lo = np.searchsorted(pub, dates - np.timedelta64(w, "D"), side="left")
            return cum[col][hi] - cum[col][lo]

        for w in WINDOWS:
            g[f"pol_buy_count_{w}d"] = window_sum("is_buy", w)
            g[f"pol_sell_count_{w}d"] = window_sum("is_sell", w)
            g[f"pol_buy_amount_{w}d"] = window_sum("buy_amt", w)
            g[f"pol_sell_amount_{w}d"] = window_sum("sell_amt", w)

        buy30, sell30 = g["pol_buy_amount_30d"], g["pol_sell_amount_30d"]
        g["pol_net_buy_pressure_30d"] = (buy30 - sell30) / (buy30 + sell30 + _EPS)

        lo30 = np.searchsorted(pub, dates - np.timedelta64(30, "D"), side="left")
        pol_ids = tt["politician_id"].fillna("?").to_numpy()
        g["pol_unique_politicians_30d"] = [
            float(len(set(pol_ids[l:h]))) if h > l else 0.0
            for l, h in zip(lo30, hi)
        ]
        for name, col in (("house", "is_house"), ("senate", "is_senate"),
                          ("dem", "is_dem"), ("rep", "is_rep"),
                          ("self_owner", "is_self"), ("spouse_owner", "is_spouse")):
            g[f"pol_{name}_trades_30d"] = window_sum(col, 30)

        n30 = g["pol_buy_count_30d"] + g["pol_sell_count_30d"]
        delay_sum = window_sum("delay", 30)
        g["pol_avg_disclosure_delay_30d"] = np.where(n30 > 0, delay_sum / np.maximum(n30, 1), 0.0)

        # Abnormal activity: today's 30d trade count vs its own trailing
        # 180-trading-day history (shifted so today is excluded).
        hist_mean = n30.shift(1).rolling(180, min_periods=30).mean()
        hist_std = n30.shift(1).rolling(180, min_periods=30).std()
        g["pol_activity_zscore_30d"] = ((n30 - hist_mean) / hist_std.replace(0, np.nan)).fillna(0.0)

        # Placeholder until committee-membership data is wired in (Phase 4+).
        g["pol_committee_relevance"] = 0.0
        chunks.append(g)

    return pd.concat(chunks, ignore_index=True)
