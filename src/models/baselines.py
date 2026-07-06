"""Naive baselines. Any real model must beat these to justify its existence."""
from __future__ import annotations

import numpy as np
import pandas as pd


def naive_last_return(df: pd.DataFrame) -> np.ndarray:
    """Predict next 5d return = last observed 5d return (persistence)."""
    return df["ret_5d"].fillna(0.0).to_numpy()


def zero_return(df: pd.DataFrame) -> np.ndarray:
    """Predict zero — the efficient-markets null hypothesis."""
    return np.zeros(len(df))


def market_beta_baseline(df: pd.DataFrame) -> np.ndarray:
    """Predict beta * trailing market 5d return (CAPM drift proxy)."""
    beta = df.get("beta_63d", pd.Series(1.0, index=df.index)).fillna(1.0)
    mkt = df.get("spy_ret_5d", pd.Series(0.0, index=df.index)).fillna(0.0)
    return (beta * mkt).to_numpy()


BASELINES = {
    "baseline_naive_last_return": naive_last_return,
    "baseline_zero": zero_return,
    "baseline_market_beta": market_beta_baseline,
}
