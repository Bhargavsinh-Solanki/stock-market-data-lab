# Global Political Trades Stock Intelligence Platform

A legally compliant research platform that collects daily stock-market data and U.S. political
trading disclosures (CapitolTrades + official House/Senate sources), engineers point-in-time
features, and uses ML / neural forecasting to produce **next-week (5 trading day) stock return,
direction, and risk** signals — served through a Streamlit dashboard.

> ⚠️ **Disclaimer:** All outputs are **experimental research signals only — NOT investment
> advice**. Congressional disclosures are filed with delays of up to 45 days under the STOCK Act.
> The platform performs **no automatic trade execution** and contains no order-routing code.

---

## Architecture

```
┌────────────────────────── SCHEDULER (cron / GitHub Actions, after US close) ────────────────────────┐
│                                                                                                     │
│  INGESTION (incremental, rate-limited, robots.txt-aware, raw+normalized, hash-deduped)              │
│  capitol_trades.py   house_disclosures.py   senate_disclosures.py   market_prices.py   macro.py     │
│  (public JSON API)   (Clerk yearly ZIP)     (eFD, opt-in/manual)    (yfinance)         (FRED)       │
│          └───────────────────┴──────────────┬───────┴────────────────────┴───────────────┘          │
│                                             ▼                                                       │
│                DuckDB ── raw_source_events (audit) + normalized tables                              │
│                                             ▼                                                       │
│  FEATURES: price/technical ⊕ political flow (published-date, point-in-time) ⊕ macro context         │
│                → features_daily → features_weekly (+ forward 5d labels)                             │
│                                             ▼                                                       │
│  MODELS: baselines → ridge / RF / LightGBM → NHITS / TFT ── walk-forward + embargo (no leakage)     │
│                                             ▼                                                       │
│  predictions_weekly + backtest_results + SHAP narratives ──► STREAMLIT DASHBOARD (7 pages)          │
└─────────────────────────────────────────────────────────────────────────────────────────────────────┘
```

## Setup

```bash
git clone <your-repo-url> && cd global-political-trades-forecast
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt          # core platform
# optional extras:
pip install ".[neural]"                  # torch + neuralforecast (NHITS / TFT)
pip install ".[tracking]"                # MLflow

cp .env.example .env                     # set CONTACT_EMAIL + FRED_API_KEY
```

### Run the pipeline (Phase order)

```bash
python scripts/run_daily_ingestion.py           # 1. political trades + prices + macro
python scripts/run_feature_build.py             # 2. features_daily / features_weekly
python scripts/train_models.py                  # 3. baselines + ML, walk-forward, backtest
python scripts/train_models.py --neural NHITS   #    (optional) add a neural model
python scripts/generate_weekly_predictions.py   # 4. next-week predictions + explanations
streamlit run src/dashboard/app.py              # 5. dashboard at http://localhost:8501
```

### Tests

```bash
pytest -q
```

### Docker

```bash
docker compose up dashboard          # dashboard only
docker compose up                    # dashboard + in-container cron scheduler
```

### Scheduling

Either the bundled GitHub Actions workflow (`.github/workflows/daily_pipeline.yml`:
weekdays 22:30 UTC ingestion+features; Sundays retrain+predict) or classic cron:

```cron
30 22 * * 1-5  cd /path/to/repo && .venv/bin/python scripts/run_daily_ingestion.py && .venv/bin/python scripts/run_feature_build.py
0  12 * * 0    cd /path/to/repo && .venv/bin/python scripts/train_models.py && .venv/bin/python scripts/generate_weekly_predictions.py
```

---

## Database schema

DuckDB for the MVP (single file, zero ops); `src/db/schema.sql` is portable SQL, so moving to
PostgreSQL means swapping `src/db/engine.py`. Tables:

| Table | Purpose |
|---|---|
| `raw_source_events` | Every raw fetch: source, URL, retrieval timestamp, full payload (audit trail) |
| `politicians` / `issuers` | Dimension tables from disclosures |
| `political_trades` | Normalized trades, PK = stable content hash (dedupes refetches & cross-source duplicates), size-bucket midpoints, traded vs published date, `filed_after_days` |
| `securities_master` | Ticker metadata, sector, active flag (delisting-aware) |
| `prices_daily` | Adjusted OHLCV (splits/dividends handled via adjusted close) |
| `macro_daily` | FRED series (rates, CPI, unemployment, USD, oil) |
| `features_daily` / `features_weekly` | Derived, rebuilt each run by the feature pipeline |
| `model_training_runs` | Every training run: params, walk-forward metrics, residual std, MLflow id |
| `predictions_weekly` | Signals + intervals + confidence + explanation, flagged `is_research_signal_only` |
| `backtest_results` | Strategy metrics + serialized equity curve |

## Modeling choices — and why we don't predict raw prices

**Targets** (never raw prices):

1. `next_5_trading_day_log_return` — regression target
2. direction (up/down) — classifier probability
3. 80% prediction interval from out-of-fold residual quantiles + confidence score
4. expected risk-adjusted return = predicted return / trailing 21-day volatility

Raw prices are non-stationary: a model that predicts "tomorrow ≈ today" achieves spectacular
R²/MAPE while containing zero tradable information, and price levels aren't comparable across
tickers so nothing can be ranked cross-sectionally. Log returns are approximately stationary,
symmetric, additive across horizons, and directly measure what a portfolio earns — which is why
evaluation centers on the **cross-sectional daily information coefficient** rather than raw error.

**Model ladder** (each rung must beat the previous out-of-sample):

1. Baselines: naive last-return persistence, zero-return (EMH null), market-beta drift
2. Ridge regression (leak-proof scaler inside the fold pipeline)
3. RandomForest
4. LightGBM (regression + direction classifier) — usually the best classical model on tabular
   cross-sectional features
5. Neural (`src/models/neural.py`, optional extra): **NHITS** as the efficient default, **TFT**
   as the flagship — chosen because this problem mixes *observed exogenous* series (political
   buy/sell pressure, VIX, macro), *known-future* covariates (calendar) and *static* covariates
   (sector, chamber exposure), the exact covariate structure TFT was designed for. PatchTST is a
   sensible later addition once several years of universe history accumulate.
6. Ensemble: weighted average of the best classical + neural forecasts (`ensemble_predictions`)

**Validation — walk-forward only, never random splits:**

- expanding train window → embargo gap → test window, stepped through time
- 5-trading-day embargo purges training labels that overlap the test horizon
- scalers/imputers live inside per-fold sklearn pipelines (fit on train only)
- political features keyed to **published_date** — a trade executed Jan 2 but disclosed Feb 10
  influences features only from Feb 10 (tested in `tests/test_political_features.py`)
- macro joined as-of the trading calendar with forward-fill only (no future values)

**Metrics:** MAE, RMSE, Spearman IC, mean per-date cross-sectional IC, directional accuracy,
up-move precision/recall, AUC; portfolio level: top-k weekly return, Sharpe, max drawdown,
turnover, transaction-cost-adjusted return vs SPY. MAPE is intentionally omitted for returns
(division by near-zero actuals makes it meaningless).

**Explainability:** SHAP for tree models, global importances, and a per-prediction plain-English
narrative ("why this stock is predicted to rise/fall next week") stored with every signal.

## Dashboard (7 pages)

1. **Market Overview** — indices, VIX, daily disclosed-trade counts
2. **Latest Political Trades** — filterable table, top-traded tickers
3. **Ticker Detail** — candlestick with disclosure markers, buy/sell pressure, next-week
   prediction with interval, top drivers, source links
4. **Weekly Predictions** — ranked signals, distribution, confidence scatter
5. **Backtest Results** — equity curve vs SPY, Sharpe/drawdown/turnover
6. **Model Explainability** — model comparison, IC ranking, feature importance
7. **Data Quality Monitor** — freshness, coverage, null rates, ingestion audit trail

## Compliance notes

- **No circumvention** of logins, CAPTCHAs, paywalls, robots.txt, rate limits or anti-bot
  systems anywhere in the codebase. The HTTP client refuses robots.txt-disallowed URLs
  (`src/utils/http.py`) and throttles to ~1 request / 2s with an identifying User-Agent and
  contact email.
- **Official sources are the source of record.** House political trades come from the Clerk's
  public disclosure system: the yearly filing index ZIP plus per-filing PTR PDFs, whose
  transaction tables are parsed by `ingest_ptr_transactions` (electronic filings only; paper
  scans are recorded as skipped, never silently dropped). The Senate eFD site requires
  accepting a usage agreement, so automated Senate ingestion ships **disabled**; a
  manual-export loader is provided instead (`data/raw/senate/`).
- **CapitolTrades ships disabled** (`ENABLE_CAPITOL_TRADES=false`): its API host's robots.txt
  is `Disallow: /` for all agents, and the site sits behind an anti-bot checkpoint. Under this
  project's rules (no robots.txt or anti-bot circumvention) it is not usable as an automated
  source — the compliance client refuses the fetches. The ingester remains only in case its
  access policy changes.
- **yfinance** is a research-grade convenience; for production SLAs use a licensed feed
  (Polygon/Tiingo/EODHD) behind the same `market_prices.py` interface.
- **Global sources** (free, keyless, robots-checked, rate-limited): the official ECB Data
  Portal for euro-area FX/rates and the World Bank open API for country-level inflation/GDP.
  A Stooq ingester exists as an optional second price source but ships **disabled**: Stooq's
  robots.txt disallows its CSV download path, and the compliance client refuses such fetches —
  a live demonstration that the robots.txt guard is enforced, not decorative.
- **Auditability:** every fetch stores source URL, retrieval timestamp and raw payload in
  `raw_source_events`.
- **No secrets in code** — everything via `.env` (see `.env.example`).
- **No auto-trading**, and every stored prediction carries `is_research_signal_only = TRUE`.

## Project structure

```
global-political-trades-forecast/
├── README.md · requirements.txt · pyproject.toml · docker-compose.yml · Dockerfile · .env.example
├── .github/workflows/daily_pipeline.yml
├── data/{raw,processed}/
├── notebooks/01_data_exploration … 04_neural_forecasting.ipynb
├── scripts/run_daily_ingestion.py · run_feature_build.py · train_models.py · generate_weekly_predictions.py
├── src/
│   ├── config/settings.py            # pydantic settings, universe, sector ETFs, FRED series
│   ├── db/{schema.sql,engine.py}
│   ├── utils/{http.py,hashing.py,logging.py}
│   ├── ingestion/{base,capitol_trades,house_disclosures,senate_disclosures,market_prices,macro}.py
│   ├── processing/normalize.py       # size buckets, tx types, owners, tickers
│   ├── features/{price_features,political_features,macro_features,build}.py
│   ├── models/{baselines,ml_models,neural,walk_forward,metrics,explain}.py
│   ├── backtesting/engine.py
│   └── dashboard/{app.py,common.py,pages/…}
└── tests/                            # parsers, features, walk-forward, backtest (mocked, no network)
```

## Roadmap

- **Phase 1 (done):** market + political ingestion, normalized store, latest-trades dashboard
- **Phase 2 (done):** feature pipeline, baselines + ridge/RF/LightGBM, walk-forward validation
- **Phase 3 (done, optional deps):** NHITS/TFT via NeuralForecast, MLflow tracking, SHAP
- **Phase 4 (done):** weekly prediction report, cost-aware backtesting, scheduled jobs
- **Global expansion (done):** ADRs from Asia/Europe/LatAm/Africa-Oceania in the universe
  (USD-denominated on purpose — no currency mixing), 16 world indices across the Americas,
  Europe and Asia-Pacific, Stooq as a second price source, ECB + World Bank macro.
- **Next:** House PTR PDF transaction extraction, committee-relevance scoring (committee
  membership × issuer sector), earnings-date & news-sentiment exogenous features, PatchTST,
  PostgreSQL migration, alerting (email/Slack) on abnormal political activity.
- **Non-US political disclosures (research needed):** few are machine-readable today — the UK
  Register of Members' Financial Interests (HTML/registers), EU Parliament declarations (PDF),
  Canada's conflict-of-interest registry, Australia's register of interests (PDF). Adding any
  of these means building a per-country parser feeding the same `political_trades` schema;
  the normalized model (chamber/party/owner/size buckets) already accommodates them.
