"""
Tests for the dashboard (Lesson 34).

Streamlit's AppTest runs step11_dashboard.py inside the test - no browser - and lets us
check for crashes, read what's on the page, and click widgets.

The dashboard normally downloads live data from Alpaca. Tests must work WITHOUT internet
or API keys (GitHub's automatic tests don't have your keys), so every function that talks
to Alpaca is swapped for a FAKE that returns made-up data (monkeypatching, Lesson 24).
"""

import sys
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from lab import currency  # noqa: E402
from lab import dividends  # noqa: E402
from lab import helpers  # noqa: E402
from lab import portfolio  # noqa: E402
from lab import report  # noqa: E402

HOLDINGS = ["SPY", "NVDA", "AAPL", "TSLA"]


# --- Fake data -------------------------------------------------------------------------

def fake_daily_closes(symbols, days=365, keep_gaps=False):
    """Made-up random-walk prices, dated like the real ones (04:00 UTC on weekdays)."""
    index = pd.bdate_range(end=pd.Timestamp.today().normalize(), periods=min(days, 600))
    index = index.tz_localize("UTC") + pd.Timedelta(hours=4)
    names = [symbols] if isinstance(symbols, str) else list(symbols)
    table = pd.DataFrame({
        # seed from the letters' codes: the same symbol always gets the same made-up prices
        s: 100 * np.cumprod(1 + np.random.default_rng(sum(map(ord, s))).normal(0.0005, 0.015, len(index)))
        for s in names
    }, index=index)
    return table[symbols] if isinstance(symbols, str) else table


def fake_minutes(symbol):
    index = pd.date_range("2026-10-09 09:30", periods=60, freq="min", tz="America/New_York")
    prices = np.linspace(100, 101, 60)
    return pd.DataFrame({"open": prices, "high": prices + 0.2, "low": prices - 0.2, "close": prices}, index=index)


def fake_latest_trade(symbol):
    return SimpleNamespace(price=101.0, size=10, timestamp=datetime(2026, 10, 9, 15, 0, tzinfo=timezone.utc))


def position(symbol, value):
    return SimpleNamespace(symbol=symbol, qty="2", avg_entry_price="90", current_price=str(value / 2),
                           market_value=str(value), unrealized_pl="10", unrealized_plpc="0.05",
                           asset_class=SimpleNamespace(value="us_equity"))


class FakeClient:
    """Pretends to be Alpaca's TradingClient for a small paper account."""

    def get_account(self):
        return SimpleNamespace(portfolio_value="100000", cash="90000", last_equity="99900")

    def get_all_positions(self):
        return [position("SPY", 5000), position("NVDA", 3000), position("TSLA", 2000)]

    def get_clock(self):
        return SimpleNamespace(is_open=False, timestamp=datetime.now(timezone.utc))

    def get_portfolio_history(self, request):
        stamps = pd.bdate_range(end=pd.Timestamp.today(), periods=22)
        return SimpleNamespace(equity=list(np.linspace(99000, 100000, 22)),
                               timestamp=[int(t.timestamp()) for t in stamps])


@pytest.fixture
def fake_alpaca(monkeypatch, tmp_path):
    """
    A FIXTURE is setup code pytest runs before each test that asks for it.
    This one swaps every Alpaca call for a fake, and runs the test in an empty folder
    that only contains an example portfolio file.
    """
    for module in (helpers, portfolio, report):
        monkeypatch.setattr(module, "daily_closes", fake_daily_closes)
    for module in (helpers, portfolio):
        monkeypatch.setattr(module, "trading_client", lambda: FakeClient())
    monkeypatch.setattr(helpers, "latest_session_minutes", fake_minutes)
    monkeypatch.setattr(helpers, "latest_trade", fake_latest_trade)
    monkeypatch.setattr(currency, "euro_strength", lambda days=400: fake_daily_closes("FXE", days))
    monkeypatch.setattr(dividends, "fetch_cash_dividends", lambda symbols, **kw: pd.DataFrame(
        [("SPY", pd.Timestamp("2026-09-19").date(), pd.Timestamp("2026-10-31").date(), 1.9, False)],
        columns=dividends.COLUMNS))

    pd.DataFrame({"symbol": HOLDINGS, "name": HOLDINGS, "value_eur": [500, 300, 150, 50],
                  "profit_eur": [20, 15, -5, 2]}).to_csv(tmp_path / "my_portfolio.csv", index=False)
    monkeypatch.chdir(tmp_path)
    st.cache_data.clear()  # never reuse cached answers from another test
    yield


def run_dashboard():
    app = AppTest.from_file(str(ROOT / "lessons" / "step11_dashboard.py"), default_timeout=60)
    app.run()
    return app


# --- The tests ------------------------------------------------------------------------------

def test_dashboard_runs_without_crashing(fake_alpaca):
    app = run_dashboard()
    assert not app.exception, app.exception  # any error on ANY tab shows up here
    assert app.title[0].value == "📈 My Stock Dashboard"
    assert len(app.tabs) == 6


def test_home_page_summarises_the_portfolio(fake_alpaca):
    app = run_dashboard()
    labels = [m.label for m in app.metric]
    assert "Worth" in labels and "Normal monthly swing" in labels
    worth = next(m for m in app.metric if m.label == "Worth")
    assert worth.value == "€1,000.00"  # 500 + 300 + 150 + 50 from the example file


def test_switching_to_dollars_still_works(fake_alpaca):
    app = run_dashboard()
    app.sidebar.radio[0].set_value("$ dollars").run()  # click the € / $ switch
    assert not app.exception, app.exception
    assert any("(in dollars)" in m.value for m in app.markdown)


def test_dividends_section_shows(fake_alpaca):
    app = run_dashboard()
    labels = [m.label for m in app.metric]
    assert "Rough yearly income" in labels and "Holdings that paid" in labels


def test_dashboard_works_without_a_portfolio_file(fake_alpaca):
    Path("my_portfolio.csv").unlink()  # a new user who hasn't created the file yet
    app = run_dashboard()
    assert not app.exception, app.exception
    assert any("my_portfolio.csv" in w.value for w in app.warning)
