"""Classical ML models behind a single factory + walk-forward runner.

Scalers live inside sklearn Pipelines, so each fold fits its scaler on that
fold's training data only — no scaling leakage.
"""
from __future__ import annotations

from typing import Any, Callable

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from src.models.baselines import BASELINES
from src.models.metrics import (
    classification_metrics,
    daily_information_coefficient,
    regression_metrics,
)
from src.models.walk_forward import walk_forward_splits, split_frame
from src.utils.logging import get_logger

logger = get_logger(__name__)


def _lightgbm_available() -> bool:
    try:
        import lightgbm  # noqa: F401
        return True
    except ImportError:
        return False


def _make_pipeline(steps: list) -> Pipeline:
    """Pipeline whose transformers emit DataFrames, so estimators keep
    feature names between fit and predict (kills the sklearn/LightGBM
    'X does not have valid feature names' warning)."""
    pipe = Pipeline(steps)
    pipe.set_output(transform="pandas")
    return pipe


def get_model(name: str, task: str = "regression") -> Pipeline:
    """Factory. task: 'regression' | 'classification'."""
    # keep_empty_features: a column that is all-NaN inside one training fold
    # (e.g. a macro series that starts mid-history) is imputed to 0 instead
    # of being dropped, keeping the feature space identical across folds.
    imputer = ("impute", SimpleImputer(strategy="median", keep_empty_features=True))
    if name == "ridge":
        if task == "regression":
            est = Ridge(alpha=1.0)
        else:
            est = LogisticRegression(max_iter=2000, C=0.5)
        return _make_pipeline([imputer, ("scale", StandardScaler()), ("model", est)])
    if name == "random_forest":
        cls = RandomForestRegressor if task == "regression" else RandomForestClassifier
        return _make_pipeline([
            imputer,
            ("model", cls(n_estimators=300, max_depth=8, min_samples_leaf=50,
                          n_jobs=-1, random_state=42)),
        ])
    if name == "lightgbm":
        if not _lightgbm_available():
            raise ImportError("lightgbm is not installed; `pip install lightgbm`.")
        import lightgbm as lgb
        params: dict[str, Any] = dict(
            n_estimators=500, learning_rate=0.03, num_leaves=31,
            min_child_samples=50, subsample=0.8, colsample_bytree=0.8,
            reg_lambda=1.0, random_state=42, n_jobs=-1, verbosity=-1,
        )
        est = lgb.LGBMRegressor(**params) if task == "regression" else lgb.LGBMClassifier(**params)
        return _make_pipeline([imputer, ("model", est)])
    raise ValueError(f"Unknown model '{name}'")


MODEL_NAMES = ["ridge", "random_forest"] + (["lightgbm"] if _lightgbm_available() else [])


def run_walk_forward(
    df: pd.DataFrame,
    feature_cols: list[str],
    label_col: str,
    model_name: str,
    task: str = "regression",
    min_train: int = 252,
    test_size: int = 21,
    step: int = 21,
    embargo: int = 5,
) -> dict[str, Any]:
    """Walk-forward evaluation. Returns aggregate metrics + OOF predictions."""
    data = df.dropna(subset=[label_col]).copy()
    oof_frames: list[pd.DataFrame] = []

    for fold in walk_forward_splits(
        data["date"], min_train=min_train, test_size=test_size, step=step, embargo=embargo
    ):
        train, test = split_frame(data, fold)
        if train.empty or test.empty:
            continue
        if model_name in BASELINES:
            preds = BASELINES[model_name](test)
        else:
            model = get_model(model_name, task=task)
            model.fit(train[feature_cols], train[label_col])
            if task == "classification":
                preds = model.predict_proba(test[feature_cols])[:, 1]
            else:
                preds = model.predict(test[feature_cols])
        oof_frames.append(
            test[["ticker", "date", label_col]].assign(prediction=preds, fold=fold.fold_id)
        )

    if not oof_frames:
        return {"model": model_name, "task": task, "metrics": {}, "oof": pd.DataFrame()}

    oof = pd.concat(oof_frames, ignore_index=True)
    y_true = oof[label_col].to_numpy(dtype=float)
    y_pred = oof["prediction"].to_numpy(dtype=float)
    if task == "classification":
        metrics = classification_metrics(y_true, y_pred)
    else:
        metrics = regression_metrics(y_true, y_pred)
        metrics["daily_ic"] = daily_information_coefficient(oof, "prediction", label_col)
        metrics["directional_accuracy"] = float(
            ((y_pred > 0) == (y_true > 0)).mean()
        )
        metrics["residual_std"] = float(np.nanstd(y_true - y_pred))
    metrics["n_oof"] = int(len(oof))
    metrics["n_folds"] = int(oof["fold"].nunique())
    logger.info("%s (%s): %s", model_name, task, {k: round(v, 4) if isinstance(v, float) else v for k, v in metrics.items()})
    return {"model": model_name, "task": task, "metrics": metrics, "oof": oof}


def fit_final_model(
    df: pd.DataFrame, feature_cols: list[str], label_col: str,
    model_name: str, task: str = "regression",
) -> Pipeline:
    """Fit on all labeled history for live prediction."""
    data = df.dropna(subset=[label_col])
    model = get_model(model_name, task=task)
    model.fit(data[feature_cols], data[label_col])
    return model
