"""Explainability: SHAP for tree models, coefficients for linear models,
and plain-English per-prediction narratives."""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.pipeline import Pipeline

from src.utils.logging import get_logger

logger = get_logger(__name__)

_FRIENDLY = {
    "ret_5d": "last week's return",
    "ret_21d": "1-month return",
    "ret_63d": "3-month return",
    "momentum_63_5": "medium-term momentum",
    "rsi_14": "RSI (14d)",
    "macd_hist": "MACD histogram",
    "vol_21d": "recent volatility",
    "volume_z_21d": "unusual volume",
    "beta_63d": "market beta",
    "sector_rel_ret_21d": "return vs sector",
    "pol_buy_count_30d": "political buys (30d)",
    "pol_sell_count_30d": "political sells (30d)",
    "pol_net_buy_pressure_30d": "net political buy pressure",
    "pol_unique_politicians_30d": "number of politicians trading",
    "pol_activity_zscore_30d": "abnormal political activity",
    "pol_avg_disclosure_delay_30d": "disclosure delay",
    "vix_level": "VIX level",
    "spy_ret_5d": "market return last week",
}


def _transform_X(model: Pipeline, X: pd.DataFrame) -> np.ndarray:
    """Apply every pipeline step except the final estimator."""
    Xt = X
    for _, step in model.steps[:-1]:
        Xt = step.transform(Xt)
    return np.asarray(Xt)


def shap_values_for(model: Pipeline, X: pd.DataFrame, feature_cols: list[str]) -> pd.DataFrame | None:
    """Per-row SHAP values for tree models; None when unavailable."""
    est = model.steps[-1][1]
    try:
        import shap
    except ImportError:
        logger.info("shap not installed; skipping SHAP explanations.")
        return None
    if not hasattr(est, "predict") or not (
        est.__class__.__module__.startswith(("lightgbm", "sklearn.ensemble", "xgboost"))
    ):
        return None
    try:
        explainer = shap.TreeExplainer(est)
        values = explainer.shap_values(_transform_X(model, X))
        if isinstance(values, list):  # classifiers return per-class arrays
            values = values[-1]
        return pd.DataFrame(values, columns=feature_cols, index=X.index)
    except Exception as exc:  # noqa: BLE001
        logger.warning("SHAP computation failed: %s", exc)
        return None


def global_importance(model: Pipeline, feature_cols: list[str]) -> pd.DataFrame:
    """Model-native global importance, normalized to sum to 1."""
    est = model.steps[-1][1]
    if hasattr(est, "feature_importances_"):
        imp = np.asarray(est.feature_importances_, dtype=float)
    elif hasattr(est, "coef_"):
        imp = np.abs(np.ravel(est.coef_))
    else:
        return pd.DataFrame(columns=["feature", "importance"])
    total = imp.sum() or 1.0
    return (
        pd.DataFrame({"feature": feature_cols, "importance": imp / total})
        .sort_values("importance", ascending=False)
        .reset_index(drop=True)
    )


def narrate_prediction(
    ticker: str,
    predicted_log_return: float,
    row_shap: pd.Series | None,
    row_features: pd.Series,
    top_n: int = 3,
) -> str:
    """'Why this stock is predicted to rise/fall next week.'"""
    direction = "rise" if predicted_log_return > 0 else "fall"
    pct = (np.exp(predicted_log_return) - 1) * 100
    parts = [f"{ticker} is predicted to {direction} ~{pct:+.1f}% over the next 5 trading days."]

    if row_shap is not None and not row_shap.empty:
        top = row_shap.abs().sort_values(ascending=False).head(top_n)
        drivers = []
        for feat in top.index:
            effect = "supports a rise" if row_shap[feat] > 0 else "points down"
            name = _FRIENDLY.get(feat, feat.replace("_", " "))
            val = row_features.get(feat)
            val_txt = f" ({val:.2f})" if isinstance(val, (int, float)) and not np.isnan(val) else ""
            drivers.append(f"{name}{val_txt} {effect}")
        parts.append("Top drivers: " + "; ".join(drivers) + ".")

    buys = row_features.get("pol_buy_count_30d", 0) or 0
    sells = row_features.get("pol_sell_count_30d", 0) or 0
    if buys or sells:
        parts.append(
            f"Congressional flow (last 30d of disclosures): {int(buys)} buy(s), {int(sells)} sell(s)."
        )
    parts.append("Research signal only — not investment advice.")
    return " ".join(parts)
