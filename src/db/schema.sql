-- Global Political Trades Stock Intelligence Platform — DuckDB schema.
-- Plain ANSI-ish SQL so migration to PostgreSQL is mechanical.

CREATE TABLE IF NOT EXISTS raw_source_events (
    event_id      VARCHAR PRIMARY KEY,   -- sha256(source, url, payload)
    source        VARCHAR NOT NULL,      -- capitol_trades | house_clerk | senate_efd | yfinance | fred
    source_url    VARCHAR NOT NULL,
    retrieved_at  TIMESTAMP NOT NULL,
    payload       VARCHAR NOT NULL,      -- raw response body for auditability
    status        VARCHAR DEFAULT 'ok'
);

CREATE TABLE IF NOT EXISTS politicians (
    politician_id VARCHAR PRIMARY KEY,
    full_name     VARCHAR NOT NULL,
    party         VARCHAR,               -- democrat | republican | other
    chamber       VARCHAR,               -- house | senate
    state         VARCHAR,
    first_seen_at TIMESTAMP,
    updated_at    TIMESTAMP
);

CREATE TABLE IF NOT EXISTS issuers (
    issuer_id   VARCHAR PRIMARY KEY,
    issuer_name VARCHAR,
    ticker      VARCHAR,
    sector      VARCHAR,
    country     VARCHAR,
    updated_at  TIMESTAMP
);

CREATE TABLE IF NOT EXISTS political_trades (
    trade_hash       VARCHAR PRIMARY KEY,  -- stable hash for dedupe across refetches
    source           VARCHAR NOT NULL,
    source_url       VARCHAR,
    retrieved_at     TIMESTAMP,
    politician_id    VARCHAR,
    politician_name  VARCHAR,
    party            VARCHAR,
    chamber          VARCHAR,
    state            VARCHAR,
    issuer_name      VARCHAR,
    ticker           VARCHAR,              -- NULL when the asset has no public ticker
    tx_type          VARCHAR,              -- buy | sell | exchange | receive | other
    owner            VARCHAR,              -- self | spouse | joint | dependent | undisclosed
    size_range       VARCHAR,
    size_min         DOUBLE,
    size_max         DOUBLE,
    size_mid         DOUBLE,               -- midpoint estimate of transaction value
    traded_date      DATE,
    published_date   DATE,                 -- point-in-time key for features (no lookahead)
    filed_after_days INTEGER
);

CREATE TABLE IF NOT EXISTS securities_master (
    ticker     VARCHAR PRIMARY KEY,
    name       VARCHAR,
    sector     VARCHAR,
    industry   VARCHAR,
    exchange   VARCHAR,
    currency   VARCHAR,
    asset_type VARCHAR DEFAULT 'equity',   -- equity | etf | index
    is_active  BOOLEAN DEFAULT TRUE,
    updated_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS prices_daily (
    ticker       VARCHAR NOT NULL,
    date         DATE NOT NULL,
    open         DOUBLE,
    high         DOUBLE,
    low          DOUBLE,
    close        DOUBLE,
    adj_close    DOUBLE,                  -- split/dividend adjusted
    volume       BIGINT,
    source       VARCHAR,
    retrieved_at TIMESTAMP,
    PRIMARY KEY (ticker, date)
);

CREATE TABLE IF NOT EXISTS macro_daily (
    series_id    VARCHAR NOT NULL,
    date         DATE NOT NULL,
    value        DOUBLE,
    source       VARCHAR,
    retrieved_at TIMESTAMP,
    PRIMARY KEY (series_id, date)
);

-- features_daily / features_weekly are derived tables rebuilt by the feature
-- pipeline via CREATE OR REPLACE TABLE ... AS SELECT; no fixed DDL here.

CREATE TABLE IF NOT EXISTS model_training_runs (
    run_id        VARCHAR PRIMARY KEY,
    model_name    VARCHAR NOT NULL,
    task          VARCHAR NOT NULL,        -- regression | classification
    trained_at    TIMESTAMP NOT NULL,
    train_start   DATE,
    train_end     DATE,
    n_samples     BIGINT,
    params_json   VARCHAR,
    metrics_json  VARCHAR,                 -- walk-forward aggregate metrics
    residual_std  DOUBLE,                  -- OOF residual std, used for intervals
    mlflow_run_id VARCHAR,
    artifact_path VARCHAR
);

CREATE TABLE IF NOT EXISTS predictions_weekly (
    prediction_id            VARCHAR PRIMARY KEY,
    run_id                   VARCHAR,
    model_name               VARCHAR,
    ticker                   VARCHAR NOT NULL,
    as_of_date               DATE NOT NULL,   -- last feature date used
    horizon_days             INTEGER,
    predicted_log_return     DOUBLE,
    predicted_direction_prob DOUBLE,          -- P(up)
    pred_lower               DOUBLE,          -- ~80% interval
    pred_upper               DOUBLE,
    confidence               DOUBLE,          -- 0..1 heuristic score
    expected_risk_adj_return DOUBLE,          -- pred / trailing 21d vol
    explanation              VARCHAR,         -- human-readable top drivers
    created_at               TIMESTAMP,
    is_research_signal_only  BOOLEAN DEFAULT TRUE
);

CREATE TABLE IF NOT EXISTS backtest_results (
    backtest_id       VARCHAR PRIMARY KEY,
    run_id            VARCHAR,
    model_name        VARCHAR,
    strategy          VARCHAR,              -- e.g. long_top_10
    start_date        DATE,
    end_date          DATE,
    top_k             INTEGER,
    cost_bps          DOUBLE,
    total_return      DOUBLE,
    annualized_return DOUBLE,
    sharpe            DOUBLE,
    max_drawdown      DOUBLE,
    avg_turnover      DOUBLE,
    benchmark_ticker  VARCHAR,
    benchmark_return  DOUBLE,
    equity_curve_json VARCHAR,              -- [{date, strategy, benchmark}, ...]
    created_at        TIMESTAMP
);
