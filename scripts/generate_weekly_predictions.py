#!/usr/bin/env python
"""Generate next-week predictions from the latest feature snapshot using the
persisted best models, with intervals, confidence, risk-adjusted expectation
and per-ticker explanations. Writes to predictions_weekly.

Run weekly (e.g. Friday after close / Sunday) after ingestion + features.
"""
from __future__ import annotations

import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import joblib
import numpy as np
import pandas as pd

from src.config.settings import get_settings
from src.db.engine import get_connection, insert_ignore_df, read_df, table_exists
from src.ingestion.base import utcnow
from src.models.explain import narrate_prediction, shap_values_for
from src.utils.hashing import stable_hash
from src.utils.logging import get_logger

logger = get_logger("weekly_predictions")
Z_80 = 1.2816  # 80% two-sided normal interval


def main() -> int:
    settings = get_settings()
    models_dir = Path(settings.models_dir)
    reg_art = models_dir / "best_regressor.joblib"
    clf_art = models_dir / "direction_classifier.joblib"
    if not reg_art.exists():
        logger.error("No trained model at %s — run scripts/train_models.py first.", reg_art)
        return 1

    reg = joblib.load(reg_art)
    clf = joblib.load(clf_art) if clf_art.exists() else None

    con = get_connection()
    try:
        if not table_exists(con, "features_daily"):
            logger.error("features_daily missing — run scripts/run_feature_build.py first.")
            return 1
        feats = read_df(con, "SELECT * FROM features_daily")
        feats["date"] = pd.to_datetime(feats["date"])
        as_of = feats["date"].max()
        snap = feats[feats["date"] == as_of].reset_index(drop=True)
        logger.info("Predicting for %d tickers as of %s", len(snap), as_of.date())

        X = snap[reg["features"]]
        pred = reg["model"].predict(X)
        proba_up = (
            clf["model"].predict_proba(snap[clf["features"]])[:, 1]
            if clf is not None else np.full(len(snap), np.nan)
        )

        # Interval width from the best run's OOF residual std.
        row = con.execute(
            "SELECT residual_std FROM model_training_runs "
            "WHERE model_name = ? AND residual_std IS NOT NULL "
            "ORDER BY trained_at DESC LIMIT 1", [reg["name"]],
        ).fetchone()
        residual_std = float(row[0]) if row and row[0] else float(np.nanstd(pred) or 0.05)

        vol = snap["vol_21d"].replace(0, np.nan)
        risk_adj = pred / (vol.fillna(vol.median()) / np.sqrt(252 / 5)).to_numpy()
        confidence = np.clip(np.abs(pred) / (residual_std + 1e-9), 0, 3) / 3

        shap_df = shap_values_for(reg["model"], X, reg["features"])
        run_row = con.execute(
            "SELECT run_id FROM model_training_runs WHERE model_name = ? "
            "ORDER BY trained_at DESC LIMIT 1", [reg["name"]],
        ).fetchone()

        rows = []
        for i, r in snap.iterrows():
            explanation = narrate_prediction(
                r["ticker"], float(pred[i]),
                shap_df.iloc[i] if shap_df is not None else None,
                r, top_n=3,
            )
            rows.append({
                "prediction_id": stable_hash("pred", r["ticker"], as_of.date(), reg["name"]),
                "run_id": run_row[0] if run_row else None,
                "model_name": reg["name"],
                "ticker": r["ticker"],
                "as_of_date": as_of.date(),
                "horizon_days": settings.label_horizon_days,
                "predicted_log_return": float(pred[i]),
                "predicted_direction_prob": float(proba_up[i]) if not np.isnan(proba_up[i]) else None,
                "pred_lower": float(pred[i] - Z_80 * residual_std),
                "pred_upper": float(pred[i] + Z_80 * residual_std),
                "confidence": float(confidence[i]),
                "expected_risk_adj_return": float(risk_adj[i]) if not np.isnan(risk_adj[i]) else None,
                "explanation": explanation,
                "created_at": utcnow(),
                "is_research_signal_only": True,
            })
        inserted = insert_ignore_df(con, "predictions_weekly", pd.DataFrame(rows))
        logger.info("Stored %d predictions (as_of=%s). Research signals only.", inserted, as_of.date())

        top = pd.DataFrame(rows).nlargest(10, "predicted_log_return")
        logger.info("Top 10 predicted (NOT investment advice):")
        for r in top.itertuples():
            logger.info("  %-6s %+0.2f%%  conf=%.2f", r.ticker,
                        (np.exp(r.predicted_log_return) - 1) * 100, r.confidence)
        return 0
    finally:
        con.close()


if __name__ == "__main__":
    raise SystemExit(main())
