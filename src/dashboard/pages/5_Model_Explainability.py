"""Page 6 — Model explainability: training runs, metrics, global importance."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import pandas as pd
import plotly.express as px
import streamlit as st

from src.config.settings import get_settings
from src.dashboard.common import safe_query, show_disclaimer

st.set_page_config(page_title="Model Explainability", page_icon="🧠", layout="wide")
st.title("🧠 Model Explainability")
show_disclaimer()

runs = safe_query(
    "SELECT * FROM model_training_runs ORDER BY trained_at DESC",
    required_table="model_training_runs",
)
if runs.empty:
    st.stop()

st.subheader("Walk-forward model comparison (latest runs)")
latest = runs.drop_duplicates("model_name", keep="first").copy()
metric_rows = []
for r in latest.itertuples():
    m = json.loads(r.metrics_json or "{}")
    metric_rows.append({"model": r.model_name, "task": r.task, **m})
metrics_df = pd.DataFrame(metric_rows)
st.dataframe(metrics_df, use_container_width=True, hide_index=True)

if "daily_ic" in metrics_df.columns:
    reg = metrics_df[metrics_df["task"] == "regression"].dropna(subset=["daily_ic"])
    if not reg.empty:
        st.plotly_chart(
            px.bar(reg.sort_values("daily_ic"), x="daily_ic", y="model", orientation="h",
                   title="Daily cross-sectional information coefficient (higher is better)"),
            use_container_width=True,
        )

st.subheader("Global feature importance (persisted best model)")
try:
    import joblib
    from src.models.explain import global_importance

    art = Path(get_settings().models_dir) / "best_regressor.joblib"
    if art.exists():
        bundle = joblib.load(art)
        imp = global_importance(bundle["model"], bundle["features"]).head(25)
        if not imp.empty:
            st.plotly_chart(
                px.bar(imp.sort_values("importance"), x="importance", y="feature",
                       orientation="h", height=650,
                       title=f"Top features — {bundle['name']}"),
                use_container_width=True,
            )
    else:
        st.info("No persisted model yet — run scripts/train_models.py")
except Exception as exc:  # noqa: BLE001
    st.warning(f"Could not load model artifact: {exc}")

st.subheader("Per-prediction narratives")
st.write(
    "Each stored prediction carries a plain-English explanation (top SHAP "
    "drivers + congressional flow). See the **Weekly Predictions** and "
    "**Ticker Detail** pages."
)
