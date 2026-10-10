"""
report.py - builds the daily market report (Lesson 26).

It gathers FACTS and checks YOUR OWN RULES. It never says what to buy, hold or sell:
that's investment advice, and the decisions stay yours.

  market_overview()  how indexes and sectors moved (1 day and ~1 month)
  holdings_moves()   how each of your holdings moved, and your estimated portfolio move
  check_rules()      which of your rules are broken right now
  build_html()       turns everything into an email-friendly HTML page
"""

import html
from datetime import datetime, timedelta

import pandas as pd
from alpaca.data.requests import NewsRequest

from helpers import daily_closes, news_client
from portfolio import ETFS, SECTOR

# Funds that track the whole market or one sector - a quick "weather report"
MARKET = {
    "SPY": "S&P 500", "URTH": "MSCI World", "QQQ": "Nasdaq 100",
    "XLK": "Tech", "XLF": "Finance", "XLV": "Health", "XLE": "Energy",
    "XLU": "Utilities", "XLI": "Industrial", "XLY": "Consumer",
}


def moves(symbols, days=45):
    """Latest close, 1-day % and ~1-month % (21 trading days) for each symbol that has data."""
    closes = daily_closes(list(symbols), days=days, keep_gaps=True)
    rows = {}
    for s in closes.columns:
        c = closes[s].dropna()
        if len(c) < 2:
            continue  # no data (e.g. not on the free feed)
        rows[s] = {
            "close": c.iloc[-1],
            "day_%": (c.iloc[-1] / c.iloc[-2] - 1) * 100,
            "month_%": (c.iloc[-1] / c.iloc[max(0, len(c) - 22)] - 1) * 100,
        }
    return pd.DataFrame(rows).T


def market_overview():
    table = moves(MARKET)
    table.insert(0, "name", [MARKET[s] for s in table.index])
    return table


def holdings_moves(holdings):
    """Each holding's moves, its share of your money, and the money-weighted portfolio move."""
    table = moves(holdings.index)
    table.insert(0, "name", holdings.loc[table.index, "name"])
    table["share_%"] = holdings["value_eur"] / holdings["value_eur"].sum() * 100
    covered = table.dropna(subset=["day_%"])
    weights = covered["share_%"] / covered["share_%"].sum()
    portfolio_day = (covered["day_%"] * weights).sum()
    missing = [s for s in holdings.index if s not in table.index]
    return table.sort_values("day_%"), portfolio_day, missing


def check_rules(holdings, today, rules):
    """
    Compare your portfolio with YOUR rules. Returns a list of plain-English alerts.
    rules = {"max_single_stock_%": 20, "max_sector_%": 50, "daily_move_alert_%": 5}
    """
    alerts = []
    share = holdings["value_eur"] / holdings["value_eur"].sum() * 100
    stocks = share[[s for s in share.index if s not in ETFS]]

    limit = rules.get("max_single_stock_%")
    if limit is not None:
        for s, pct in stocks[stocks > limit].items():
            alerts.append(f"{s} is {pct:.1f}% of your portfolio - above your {limit}% single-stock limit.")

    limit = rules.get("max_sector_%")
    if limit is not None:
        sectors = stocks.groupby(lambda s: SECTOR.get(s, "Other")).sum()
        for sector, pct in sectors[sectors > limit].items():
            alerts.append(f"{sector} stocks are {pct:.1f}% of your portfolio - above your {limit}% sector limit.")

    limit = rules.get("daily_move_alert_%")
    if limit is not None and not today.empty:
        for s, move in today["day_%"][today["day_%"].abs() > limit].items():
            alerts.append(f"{s} moved {move:+.1f}% on the latest trading day - beyond your ±{limit}% alert level.")
    return alerts


def headlines(symbols, per_symbol=2, hours=24):
    """The newest headlines for each symbol from the last `hours` hours."""
    news = news_client().get_news(
        NewsRequest(symbols=",".join(symbols), start=datetime.now() - timedelta(hours=hours))
    ).df
    if news.empty:
        return []
    picked, seen = [], set()
    for s in symbols:
        for _, row in news[news["symbols"].apply(lambda tags: s in tags)].head(per_symbol).iterrows():
            if row["headline"] not in seen:
                seen.add(row["headline"])
                picked.append((s, row["headline"], row["url"]))
    return picked


# --- HTML (emails are written in HTML, the language of web pages) ------------------------------

def _pct(x):
    colour = "#1a7f37" if x > 0 else "#cf222e" if x < 0 else "#57606a"  # green / red / grey
    return f'<td style="text-align:right;color:{colour}">{x:+.2f}%</td>'


def _table(df, columns):
    head = "".join(f'<th style="text-align:left;padding:4px 8px">{c}</th>' for c in columns)
    body = ""
    for s, r in df.iterrows():
        body += (f'<tr><td style="padding:4px 8px"><b>{html.escape(s)}</b></td>'
                 f'<td style="padding:4px 8px">{html.escape(str(r["name"]))}</td>'
                 f'{_pct(r["day_%"])}{_pct(r["month_%"])}</tr>')
    return f'<table style="border-collapse:collapse;font-size:14px"><tr>{head}</tr>{body}</table>'


def risk_html(per_holding, mix, left_out):
    """The 'next month's normal range' section (Lesson 29)."""
    m = mix.iloc[0]
    rows = "".join(
        f'<tr><td style="padding:2px 8px"><b>{html.escape(s)}</b></td>'
        f'<td style="text-align:right;padding:2px 8px">{r["volatility_%"]:.0f}%</td>'
        f'<td style="text-align:right;padding:2px 8px">±{r["typical_%"]:.1f}%</td>'
        f'<td style="text-align:right;padding:2px 8px;color:#cf222e">{r["bad_%"]:.1f}%</td></tr>'
        for s, r in per_holding.iterrows())
    note = f"<p style='color:#57606a'>No forecast for: {', '.join(left_out)}.</p>" if left_out else ""
    return f"""<h3>Next month's normal range (risk forecast)</h3>
<p>Your whole mix: in about <b>2 months out of 3</b> the month's move stays within
<b>±{m["typical_%"]:.1f}%</b>; roughly <b>1 month in 20</b> is worse than <b>{m["bad_%"]:.1f}%</b>.
This says how much prices may swing - not which way. A rough guide: real markets have more
extreme days than it assumes.</p>
<table style="border-collapse:collapse;font-size:14px"><tr><th></th>
<th style="padding:2px 8px">Volatility / year</th><th style="padding:2px 8px">Typical month</th>
<th style="padding:2px 8px">Rough bad month</th></tr>{rows}</table>{note}"""


def build_html(market, mine, portfolio_day, missing, alerts, news, date, risk=None):
    """
    One HTML page with every section. html.escape() makes any text safe to show.
    risk: optional (per_holding, mix, left_out) from risk_forecast.forecast_holdings()
    """
    columns = ["", "Name", "1 day", "~1 month"]
    alert_html = ("".join(f"<li>{html.escape(a)}</li>" for a in alerts)
                  or "<li>None of your rules are broken today.</li>")
    def short(text, limit=140):  # some "headlines" are whole social-media posts
        return text if len(text) <= limit else text[:limit].rsplit(" ", 1)[0] + "…"

    news_html = "".join(f'<li><b>{s}</b>: <a href="{html.escape(u)}">{html.escape(short(h))}</a></li>'
                        for s, h, u in news) or "<li>No headlines in the last 24 hours.</li>"
    missing_note = (f"<p style='color:#57606a'>No price data for: {', '.join(missing)}.</p>"
                    if missing else "")
    direction = "up" if portfolio_day > 0 else "down"
    return f"""<html><body style="font-family:Arial,sans-serif;color:#24292f;max-width:640px">
<h2>Daily market report - {date:%A %d %B %Y}</h2>
<h3>Your rule alerts</h3><ul>{alert_html}</ul>
<h3>Your holdings</h3>
<p>Weighted by your money, your holdings went <b>{direction} about {abs(portfolio_day):.2f}%</b>
on the latest trading day (today so far, if the US market is still open; in US dollars,
the euro exchange rate is not included).</p>
{_table(mine, columns)}{missing_note}
{risk_html(*risk) if risk else ""}
<h3>Market overview</h3>{_table(market, columns)}
<h3>Headlines for your holdings</h3><ul>{news_html}</ul>
<p style="color:#57606a;font-size:12px">Facts only, from the free Alpaca/IEX feed. This report is
not investment advice and does not recommend buying, holding or selling anything.
Sent by your stock-market-data-lab project.</p>
</body></html>"""
