#!/usr/bin/env python
"""Train & evaluate models with walk-forward validation, persist the best,
record runs in model_training_runs, and store a backtest of the best model.

Optional: --neural NHITS|TFT adds a neural model (requires pip install ".[neural]").
Optional: MLflow logging when MLFLOW_TRACKING_URI is set.
"""
from __future__ import annotations

import argparse
import json
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import joblib
import numpy as np
import pandas as pd

from src.backtesting.engine import run_backtest
from src.config.settings import get_settings
from src.db.engine import get_connection, insert_ignore_df, read_df, table_exists
from src.features.build import feature_columns
from src.ingestion.base import utcnow
from src.models.baselines import BASELINES
from src.models.ml_models import MODEL_NAMES, fit_final_model, run_walk_forward
from src.utils.logging import get_logger

logger = get_logger("train_models")


def _maybe_mlflow_log(run_id: str, model_name: str, metrics: dict) -> str | None:
    settings = get_settings()
    if not settings.mlflow_tracking_uri:
        return None
    try:
        import mlflow
        mlflow.set_tracking_uri(settings.mlflow_tracking_uri)
        mlflow.set_experiment(settings.mlflow_experiment)
        with mlflow.start_run(run_name=f"{model_name}-{run_id[:8]}") as run:
            mlflow.log_params({"model": model_name})
            mlflow.log_metrics({k: v for k, v in metrics.items() if isinstance(v, (int, float)) and not np.isnan(v)})
            return run.info.run_id
    except Exception as exc:  # noqa: BLE001
        logger.warning("MLflow logging failed: %s", exc)
        return None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--neural", choices=["NHITS", "TFT"], default=None,
                        help="Additionally train a neural model (optional deps).")
    args = parser.parse_args()

    settings = get_settings()
    con = get_connection()
    try:
        if not table_exists(con, "features_weekly"):
            logger.error("features_weekly missing — run scripts/run_feature_build.py first.")
            return 1
        df = read_df(con, "SELECT * FROM features_weekly ORDER BY date")
        df["date"] = pd.to_datetime(df["date"])
        label = f"label_fwd_log_ret_{settings.label_horizon_days}d"
        dir_label = f"label_direction_{settings.label_horizon_days}d"
        feats = feature_columns(df)
        logger.info("Training on %d rows, %d features", len(df), len(feats))

        # Weekly grid -> convert day-based walk-forward params to weeks.
        wf = dict(
            min_train=max(settings.walk_forward_min_train_days // 5, 30),
            test_size=max(settings.walk_forward_test_days // 5, 4),
            step=max(settings.walk_forward_step_days // 5, 4),
            embargo=max(settings.walk_forward_embargo_days // 5, 1),
        )

        candidates = list(BASELINES) + MODEL_NAMES
        results = {}
        for name in candidates:
            results[name] = run_walk_forward(df, feats, label, name, task="regression", **wf)

        # Direction classifier (best tree model family).
        clf_name = "lightgbm" if "lightgbm" in MODEL_NAMES else "random_forest"
        clf_result = run_walk_forward(df, feats, dir_label, clf_name, task="classification", **wf)

        # Pick best learner (baselines excluded) by daily IC.
        learned = {k: v for k, v in results.items() if k not in BASELINES and v["metrics"]}
        best_name = max(learned, key=lambda k: np.nan_to_num(learned[k]["metrics"].get("daily_ic", -9), nan=-9))
        best = learned[best_name]
        logger.info("Best model: %s (daily IC %.4f)", best_name, best["metrics"].get("daily_ic", float("nan")))

        # Fit finals on all labeled data and persist.
        models_dir = Path(settings.models_dir)
        models_dir.mkdir(parents=True, exist_ok=True)
        final_reg = fit_final_model(df, feats, label, best_name, task="regression")
        final_clf = fit_final_model(df, feats, dir_label, clf_name, task="classification")
        reg_path = models_dir / "best_regressor.joblib"
        clf_path = models_dir / "direction_classifier.joblib"
        joblib.dump({"model": final_reg, "features": feats, "name": best_name}, reg_path)
        joblib.dump({"model": final_clf, "features": feats, "name": clf_name}, clf_path)

        # Record every run.
        labeled = df.dropna(subset=[label])
        run_rows = []
        for name, res in {**results, "direction_" + clf_name: clf_result}.items():
            if not res["metrics"]:
                continue
            run_id = str(uuid.uuid4())
            res["run_id"] = run_id
            run_rows.append({
                "run_id": run_id,
                "model_name": name,
                "task": res["task"],
                "trained_at": utcnow(),
                "train_start": labeled["date"].min().date(),
                "train_end": labeled["date"].max().date(),
                "n_samples": len(labeled),
                "params_json": json.dumps(wf),
                "metrics_json": json.dumps({k: (None if isinstance(v, float) and np.isnan(v) else v)
                                            for k, v in res["metrics"].items()}),
                "residual_std": res["metrics"].get("residual_std"),
                "mlflow_run_id": _maybe_mlflow_log(run_id, name, res["metrics"]),
                "artifact_path": str(reg_path) if name == best_name else None,
            })
        insert_ignore_df(con, "model_training_runs", pd.DataFrame(run_rows))

        # Backtest best model's OOF predictions vs SPY.
        spy = read_df(con, "SELECT date, adj_close FROM prices_daily WHERE ticker='SPY' ORDER BY date")
        spy["date"] = pd.to_datetime(spy["date"])
        spy["ret"] = np.log(spy["adj_close"]).shift(-settings.label_horizon_days) - np.log(spy["adj_close"])
        report = run_backtest(
            best["oof"], label_col=label, top_k=settings.backtest_top_k,
            cost_bps=settings.transaction_cost_bps, benchmark=spy[["date", "ret"]],
        )
        insert_ignore_df(con, "backtest_results", pd.DataFrame([{
            "backtest_id": str(uuid.uuid4()),
            "run_id": best["run_id"],
            "model_name": best_name,
            "strategy": report.strategy,
            "start_date": best["oof"]["date"].min().date(),
            "end_date": best["oof"]["date"].max().date(),
            "top_k": report.top_k,
            "cost_bps": report.cost_bps,
            "total_return": report.total_return,
            "annualized_return": report.annualized_return,
            "sharpe": report.sharpe,
            "max_drawdown": report.max_drawdown,
            "avg_turnover": report.avg_turnover,
            "benchmark_ticker": "SPY",
            "benchmark_return": report.benchmark_return,
            "equity_curve_json": report.equity_curve_json(),
            "created_at": utcnow(),
        }]))

        if args.neural:
            try:
                from src.models.neural import train_neural_model
                daily = read_df(con, "SELECT * FROM features_daily")
                daily["date"] = pd.to_datetime(daily["date"])
                train_neural_model(daily, model_name=args.neural)
                logger.info("Neural %s trained (forecasts logged; wire into ensemble as needed).", args.neural)
            except ImportError as exc:
                logger.warning("%s", exc)

        logger.info("Training complete. Best=%s saved to %s", best_name, reg_path)
        return 0
    finally:
        con.close()


if __name__ == "__main__":
    raise SystemExit(main())
