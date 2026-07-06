"""Neural forecasting via NeuralForecast (NHITS / TFT). Phase-3 layer.

Why TFT/NBEATSx-class models for this problem: the signal mixes
  * observed exogenous series (political buy/sell pressure, VIX, macro),
  * known-future covariates (calendar), and
  * static covariates (sector, chamber exposure),
which is exactly the covariate structure TFT was designed for; NHITS is the
strong cheap default. Both are optional: everything else in the platform
works without torch installed.

Install: pip install ".[neural]"   (torch + neuralforecast)
"""
from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from src.utils.logging import get_logger

logger = get_logger(__name__)

# Exogenous columns passed to the neural models (subset of features_daily).
HIST_EXOG = [
    "ret_5d", "ret_21d", "vol_21d", "volume_z_21d", "rsi_14", "macd_hist",
    "pol_buy_count_30d", "pol_sell_count_30d", "pol_net_buy_pressure_30d",
    "pol_activity_zscore_30d", "spy_ret_5d", "vix_level",
]


def _require_neuralforecast():
    # Must be set before torch initializes: lets the rare op without an MPS
    # kernel fall back to CPU instead of crashing the run on Apple Silicon.
    import os
    os.environ.setdefault("PYTORCH_ENABLE_MPS_FALLBACK", "1")
    try:
        from neuralforecast import NeuralForecast
        from neuralforecast.models import NHITS, TFT
        return NeuralForecast, NHITS, TFT
    except ImportError as exc:
        raise ImportError(
            "Neural models require the optional stack: pip install \".[neural]\" "
            "(installs torch + neuralforecast)."
        ) from exc


def detect_accelerator() -> str:
    """Best available PyTorch-Lightning accelerator: CUDA > Apple MPS > CPU."""
    try:
        import torch
        if torch.cuda.is_available():
            return "gpu"
        if torch.backends.mps.is_available():
            return "mps"
    except ImportError:
        pass
    return "cpu"


def to_long_format(feats: pd.DataFrame) -> pd.DataFrame:
    """features_daily -> NeuralForecast long format.

    y = 1-day log return (the model forecasts the horizon path; we sum the
    horizon to get the 5-day forecast), unique_id = ticker.
    """
    exog = [c for c in HIST_EXOG if c in feats.columns]
    df = feats[["ticker", "date", "ret_1d", *exog]].rename(
        columns={"ticker": "unique_id", "date": "ds", "ret_1d": "y"}
    )
    df = df.sort_values(["unique_id", "ds"])
    # NeuralForecast rejects NaNs: forward-fill exog gaps within each series,
    # then drop the leading warm-up rows that have no exog history yet.
    if exog:
        df[exog] = df.groupby("unique_id")[exog].ffill()
    return df.dropna(subset=["y", *exog])


def train_neural_model(
    feats: pd.DataFrame,
    model_name: str = "NHITS",
    horizon: int = 5,
    max_steps: int = 500,
    val_size: int = 63,
    accelerator: str | None = None,
) -> tuple[Any, pd.DataFrame]:
    """Train NHITS or TFT and return (nf_object, horizon-summed forecasts).

    Trains on the best available device by default (CUDA > Apple MPS > CPU);
    pass accelerator="cpu" to force CPU. Returned forecast frame:
    [ticker, predicted_log_return] — the sum of the next `horizon` daily
    forecasts per ticker.
    """
    NeuralForecast, NHITS, TFT = _require_neuralforecast()
    accelerator = accelerator or detect_accelerator()
    logger.info("Neural training on accelerator=%s", accelerator)
    long_df = to_long_format(feats)
    exog = [c for c in HIST_EXOG if c in long_df.columns]

    common = dict(h=horizon, input_size=63, max_steps=max_steps,
                  hist_exog_list=exog, scaler_type="robust", random_seed=42,
                  accelerator=accelerator, devices=1)
    if model_name.upper() == "TFT":
        model = TFT(hidden_size=64, **common)
    elif model_name.upper() == "NHITS":
        model = NHITS(**common)
    else:
        raise ValueError(f"Unsupported neural model '{model_name}' (use NHITS or TFT)")

    nf = NeuralForecast(models=[model], freq="B")
    nf.fit(long_df, val_size=val_size)
    fcst = nf.predict()

    pred_col = next(c for c in fcst.columns if c not in ("unique_id", "ds"))
    fcst = fcst.reset_index() if "unique_id" not in fcst.columns else fcst
    summed = (
        fcst.groupby("unique_id")[pred_col].sum()
        .rename("predicted_log_return").reset_index()
        .rename(columns={"unique_id": "ticker"})
    )
    logger.info("Neural %s trained; %d ticker forecasts", model_name, len(summed))
    return nf, summed


def ensemble_predictions(frames: list[pd.DataFrame], weights: list[float] | None = None) -> pd.DataFrame:
    """Weighted average of [ticker, predicted_log_return] frames."""
    weights = weights or [1.0] * len(frames)
    merged: pd.DataFrame | None = None
    for i, (frame, w) in enumerate(zip(frames, weights)):
        s = (frame.set_index("ticker")["predicted_log_return"] * w).rename(f"p{i}")
        merged = s.to_frame() if merged is None else merged.join(s, how="outer")
    out = (merged.sum(axis=1, min_count=1) / sum(weights)).rename("predicted_log_return")
    return out.reset_index()
