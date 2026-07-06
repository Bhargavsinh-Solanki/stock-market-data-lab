"""Evaluation metrics for regression, classification and cross-sectional rank skill."""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from sklearn.metrics import mean_absolute_error, mean_squared_error, roc_auc_score


def regression_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> dict[str, float]:
    mask = ~(np.isnan(y_true) | np.isnan(y_pred))
    y_true, y_pred = y_true[mask], y_pred[mask]
    if len(y_true) < 2:
        return {"mae": np.nan, "rmse": np.nan, "spearman_ic": np.nan}
    rho, _ = spearmanr(y_true, y_pred)
    return {
        "mae": float(mean_absolute_error(y_true, y_pred)),
        "rmse": float(np.sqrt(mean_squared_error(y_true, y_pred))),
        "spearman_ic": float(rho),
    }


def classification_metrics(y_true: np.ndarray, proba_up: np.ndarray) -> dict[str, float]:
    mask = ~(np.isnan(y_true) | np.isnan(proba_up))
    y_true, proba_up = y_true[mask], proba_up[mask]
    if len(y_true) < 2 or len(np.unique(y_true)) < 2:
        return {"directional_accuracy": np.nan, "auc": np.nan,
                "up_precision": np.nan, "up_recall": np.nan}
    pred_up = (proba_up > 0.5).astype(float)
    tp = float(((pred_up == 1) & (y_true == 1)).sum())
    fp = float(((pred_up == 1) & (y_true == 0)).sum())
    fn = float(((pred_up == 0) & (y_true == 1)).sum())
    return {
        "directional_accuracy": float((pred_up == y_true).mean()),
        "auc": float(roc_auc_score(y_true, proba_up)),
        "up_precision": tp / (tp + fp) if (tp + fp) > 0 else np.nan,
        "up_recall": tp / (tp + fn) if (tp + fn) > 0 else np.nan,
    }


def daily_information_coefficient(df: pd.DataFrame, pred_col: str, label_col: str) -> float:
    """Mean per-date cross-sectional Spearman IC — the metric that actually
    matters for a ranking/portfolio use case."""
    ics = []
    for _, g in df.dropna(subset=[pred_col, label_col]).groupby("date"):
        if len(g) >= 5 and g[pred_col].nunique() > 1:
            rho, _ = spearmanr(g[pred_col], g[label_col])
            if not np.isnan(rho):
                ics.append(rho)
    return float(np.mean(ics)) if ics else np.nan
