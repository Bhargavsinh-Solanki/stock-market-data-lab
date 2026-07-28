"""Central configuration. All secrets come from the environment / .env file."""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]

# Sector ETF map used for sector-relative features.
SECTOR_ETFS: dict[str, str] = {
    "Technology": "XLK",
    "Financial Services": "XLF",
    "Healthcare": "XLV",
    "Energy": "XLE",
    "Industrials": "XLI",
    "Consumer Cyclical": "XLY",
    "Consumer Defensive": "XLP",
    "Utilities": "XLU",
    "Basic Materials": "XLB",
    "Real Estate": "XLRE",
    "Communication Services": "XLC",
}

INDEX_TICKERS: list[str] = [
    # Americas
    "^GSPC", "^IXIC", "^DJI", "^VIX", "^GSPTSE", "^BVSP",
    # Europe
    "^FTSE", "^GDAXI", "^FCHI", "^STOXX50E",
    # Asia-Pacific
    "^N225", "^HSI", "^KS11", "^TWII", "^BSESN", "^AXJO",
]

# US-listed ADRs / USD-denominated foreign listings. Kept as ADRs on purpose:
# they trade in USD on US exchanges, so return features stay comparable and
# no currency conversion sneaks into the panel.
GLOBAL_ADR_UNIVERSE: list[str] = [
    # Asia
    "TSM", "BABA", "TM", "SONY", "INFY", "HDB", "PDD", "SE",
    # Europe
    "ASML", "SAP", "NVO", "AZN", "SHEL", "TTE", "UL", "HSBC", "SNY", "NVS",
    # Americas ex-US
    "MELI", "NU", "VALE", "PBR", "SHOP", "RY",
    # Africa / Oceania (via US listings)
    "GOLD", "BHP", "RIO",
]

# --- Stooq (stooq.com): free public CSV downloads. DISABLED by default —
# stooq.com's robots.txt disallows the CSV download path, so the compliance
# client refuses it. Map: canonical ticker -> stooq symbol.
STOOQ_INDEX_SYMBOLS: dict[str, str] = {
    "^GSPC": "^spx",
    "^DJI": "^dji",
    "^N225": "^nkx",
    "^FTSE": "^ukx",
    "^GDAXI": "^dax",
    "^HSI": "^hsi",
}

# --- ECB Data Portal (data-api.ecb.europa.eu): official euro-area series,
# free, no API key. (flow, series key, canonical series_id)
ECB_SERIES: list[tuple[str, str, str]] = [
    ("EXR", "D.USD.EUR.SP00.A", "ECB_EURUSD"),                 # daily USD/EUR reference rate
    ("FM", "B.U2.EUR.4F.KR.MRR_FB.LEV", "ECB_MRO_RATE"),       # main refinancing rate
    ("EXR", "D.GBP.EUR.SP00.A", "ECB_EURGBP"),                 # daily GBP/EUR
]

# --- World Bank open data API (api.worldbank.org): free, no key. Annual
# regime-level series per country; forward-filled onto the trading calendar.
WORLD_BANK_INDICATORS: list[str] = [
    "FP.CPI.TOTL.ZG",      # CPI inflation, %
    "NY.GDP.MKTP.KD.ZG",   # real GDP growth, %
]
WORLD_BANK_COUNTRIES: list[str] = ["USA", "CHN", "JPN", "DEU", "GBR", "IND", "BRA"]

# FRED series ingested by src/ingestion/macro.py (requires FRED_API_KEY).
FRED_SERIES: list[str] = [
    "DGS10",      # 10y treasury yield
    "DGS2",       # 2y treasury yield
    "FEDFUNDS",   # fed funds rate
    "CPIAUCSL",   # CPI (monthly)
    "UNRATE",     # unemployment (monthly)
    "DTWEXBGS",   # trade-weighted USD index
    "DCOILWTICO", # WTI crude
    "T10Y2Y",     # 10y-2y spread
]

# Default research universe: liquid large caps frequently present in
# congressional disclosures. Tickers seen in political trades are added
# automatically when auto_expand_universe is enabled.
DEFAULT_UNIVERSE: list[str] = [
    "AAPL", "MSFT", "NVDA", "GOOGL", "AMZN", "META", "TSLA", "AVGO", "BRK-B",
    "JPM", "V", "MA", "BAC", "GS", "MS", "WFC",
    "UNH", "JNJ", "LLY", "PFE", "MRK", "ABBV",
    "XOM", "CVX", "COP",
    "CAT", "BA", "GE", "LMT", "RTX", "HON", "DE",
    "WMT", "COST", "PG", "KO", "PEP", "MCD", "NKE", "HD", "DIS",
    "CRM", "ORCL", "ADBE", "AMD", "INTC", "QCOM", "TXN", "MU", "CSCO", "IBM", "SMSN.IL",   # Samsung Electronics GDR (London, USD-denominated)
]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # --- storage ---
    db_path: str = str(PROJECT_ROOT / "data" / "processed" / "platform.duckdb")
    raw_data_dir: str = str(PROJECT_ROOT / "data" / "raw")
    models_dir: str = str(PROJECT_ROOT / "data" / "processed" / "models")

    # --- polite-client / compliance ---
    contact_email: str = "you@example.com"
    respect_robots_txt: bool = True
    rate_limit_seconds: float = 2.0
    request_timeout_seconds: float = 30.0
    max_retries: int = 3

    # --- source toggles ---
    # CapitolTrades ships disabled: bff.capitoltrades.com robots.txt is
    # 'Disallow: /' for all agents, so the compliance client refuses every
    # fetch. Official House PTR ingestion (below) is the source of record.
    enable_capitol_trades: bool = False
    enable_house_disclosures: bool = True
    enable_senate_disclosures: bool = False  # eFD flow is gated; opt in explicitly
    capitol_trades_pages: int = 5
    capitol_trades_page_size: int = 100
    # global sources
    include_global_adrs: bool = True   # add GLOBAL_ADR_UNIVERSE to the universe
    # Stooq ships disabled: stooq.com's robots.txt disallows the CSV download
    # path, so the compliance client refuses it. Left in place in case their
    # policy changes or you arrange permitted access.
    enable_stooq: bool = False
    enable_ecb: bool = True            # euro-area macro (no key)
    enable_world_bank: bool = True     # worldwide annual macro (no key)

    # --- API keys (never hardcode; set in .env) ---
    fred_api_key: str = ""

    # --- universe ---
    auto_expand_universe: bool = True
    max_universe_size: int = 300

    # --- modeling ---
    label_horizon_days: int = 5
    walk_forward_min_train_days: int = 252
    walk_forward_test_days: int = 21
    walk_forward_step_days: int = 21
    walk_forward_embargo_days: int = 5
    backtest_top_k: int = 10
    transaction_cost_bps: float = 10.0

    # --- mlflow (optional) ---
    mlflow_tracking_uri: str = ""
    mlflow_experiment: str = "political-trades-forecast"

    @property
    def user_agent(self) -> str:
        return (
            "GlobalPoliticalTradesResearch/0.1 "
            f"(research use; contact: {self.contact_email})"
        )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


DISCLAIMER = (
    "⚠️ Research signals only — NOT investment advice. Forecasts are "
    "experimental model outputs with substantial uncertainty. Political "
    "disclosures are filed with delays of up to 45 days. No automatic trade "
    "execution is performed or supported."
)
