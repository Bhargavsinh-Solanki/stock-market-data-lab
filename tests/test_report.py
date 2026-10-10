"""Tests for report.py and emailer.py - no internet, and never a real email."""

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from emailer import send_email  # noqa: E402
from report import build_html, check_rules  # noqa: E402

HOLDINGS = pd.DataFrame({
    "name": ["Nvidia", "Zscaler", "MSCI World"],
    "value_eur": [300.0, 300.0, 400.0],
}, index=["NVDA", "ZS", "URTH"])
TODAY = pd.DataFrame({"name": ["Nvidia", "Zscaler", "MSCI World"],
                      "day_%": [-6.0, 1.0, 0.5], "month_%": [2.0, 3.0, 1.0]},
                     index=["NVDA", "ZS", "URTH"])


def test_rules_catch_big_positions_sectors_and_moves():
    alerts = check_rules(HOLDINGS, TODAY, {"max_single_stock_%": 25, "max_sector_%": 50,
                                           "daily_move_alert_%": 5})
    text = " | ".join(alerts)
    assert "NVDA is 30.0%" in text and "ZS is 30.0%" in text   # 300 of 1000 each
    assert "Tech stocks are 60.0%" in text                      # NVDA + ZS
    assert "NVDA moved -6.0%" in text
    assert "URTH" not in text  # ETFs don't count as single stocks


def test_no_alerts_when_rules_are_met():
    assert check_rules(HOLDINGS, TODAY, {"max_single_stock_%": 40, "daily_move_alert_%": 10}) == []


def test_html_escapes_headlines():
    # A headline containing HTML must be shown as text, not run as code
    news = [("NVDA", "<script>alert('hi')</script> Nvidia & co", "https://example.com/a")]
    page = build_html(TODAY, TODAY, 1.0, [], [], news, pd.Timestamp("2026-10-09"))
    assert "<script>" not in page
    assert "&lt;script&gt;" in page and "Nvidia &amp; co" in page


class FakeSMTP:
    """Pretends to be an email server and remembers what it was asked to do."""
    sent = []

    def __init__(self, host, port, context):
        self.host = host

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def login(self, user, password):
        self.user = user

    def send_message(self, message):
        FakeSMTP.sent.append(message)


def test_send_email_builds_the_message():
    settings = {"to": "me@example.com", "user": "bot@example.com", "password": "x",
                "host": "smtp.example.com", "port": 465}
    send_email("Hello", "<p>Report</p>", settings=settings, smtp_class=FakeSMTP)
    message = FakeSMTP.sent[-1]
    assert message["To"] == "me@example.com" and message["Subject"] == "Hello"
    assert "<p>Report</p>" in message.get_body(("html",)).get_content()


class RefusingSMTP(FakeSMTP):
    """Pretends to be Gmail refusing the login, like a wrong password."""

    def login(self, user, password):
        import smtplib
        raise smtplib.SMTPServerDisconnected("Connection unexpectedly closed")


def test_refused_login_gives_a_clear_error():
    import pytest
    from emailer import EmailError

    settings = {"to": "me@example.com", "user": "bot@example.com", "password": "x",
                "host": "smtp.example.com", "port": 465}
    with pytest.raises(EmailError, match="App Password"):
        send_email("Hello", "<p>Report</p>", settings=settings, smtp_class=RefusingSMTP)


def test_risk_section_appears_only_when_given():
    from risk_forecast import monthly_ranges

    risk = (monthly_ranges({"NVDA": 37.0}), monthly_ranges({"Whole mix": 26.0}), ["BAYRY"])
    with_risk = build_html(TODAY, TODAY, 1.0, [], [], [], pd.Timestamp("2026-10-10"), risk=risk)
    without = build_html(TODAY, TODAY, 1.0, [], [], [], pd.Timestamp("2026-10-10"))
    assert "Next month's normal range" in with_risk and "BAYRY" in with_risk
    assert "Next month's normal range" not in without


def test_long_headlines_are_shortened():
    news = [("SPY", "word " * 100, "https://example.com/a")]
    page = build_html(TODAY, TODAY, 1.0, [], [], news, pd.Timestamp("2026-10-10"))
    assert "word " * 40 not in page and "…" in page
