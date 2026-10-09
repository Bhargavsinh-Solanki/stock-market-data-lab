"""
crawler.py - our own polite news crawler (Lesson 17).

Three jobs:
  1. COLLECT headlines from two free sources: Alpaca news + Yahoo Finance RSS
  2. ARCHIVE them in data/news_archive.csv, adding only stories we haven't seen before
  3. CRAWL: visit each new story's web page and save just the article text

Being POLITE (so sites don't block us, and we play fair):
  - check each site's robots.txt (its "rules for robots") before visiting a page
  - wait a few seconds between visits to the same site
  - say who we are in the User-Agent (like a name badge)
  - never download the same page twice (we keep what we saved)
  - skip sites whose terms of use forbid scraping
"""

import hashlib
import os
import time
import urllib.robotparser
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import urlparse

import pandas as pd
import requests
import trafilatura

USER_AGENT = "stock-market-data-lab/1.0 (student learning project; polite crawler)"
DELAY_SECONDS = 3  # wait at least this long between two visits to the same site
SKIP_DOMAINS = {"finance.yahoo.com"}  # Yahoo's terms forbid scraping its pages (its RSS is fine)
ARCHIVE_FILE = "data/news_archive.csv"
ARTICLES_DIR = "data/articles"
COLUMNS = ["published", "symbols", "source", "headline", "summary", "url", "text_status"]
YAHOO_RSS = "https://feeds.finance.yahoo.com/rss/2.0/headline?s={symbol}&region=US&lang=en-US"


# --- 1. COLLECT -----------------------------------------------------------------------

def site_of(url):
    """'https://www.benzinga.com/news/...' -> 'benzinga.com' (one name per website)."""
    return urlparse(url).netloc.removeprefix("www.")


def parse_rss(xml_text, symbol):
    """Turn an RSS feed (XML text) into a table of headlines."""
    rows = []
    for item in ET.fromstring(xml_text).iter("item"):
        url = item.findtext("link") or ""
        rows.append({
            "published": parsedate_to_datetime(item.findtext("pubDate")).astimezone(timezone.utc),
            "symbols": symbol,
            "source": site_of(url),
            "headline": (item.findtext("title") or "").strip(),
            "summary": (item.findtext("description") or "").strip(),
            "url": url,
        })
    return pd.DataFrame(rows, columns=COLUMNS[:-1])


def yahoo_headlines(symbol):
    """The ~20 newest headlines from Yahoo Finance's free RSS feed."""
    response = requests.get(YAHOO_RSS.format(symbol=symbol),
                            headers={"User-Agent": USER_AGENT}, timeout=15)
    response.raise_for_status()  # stop with an error if the site said no (e.g. 404)
    return parse_rss(response.text, symbol)


def alpaca_headlines(symbol, days=7):
    """Recent headlines from Alpaca, in the same shape as yahoo_headlines()."""
    from alpaca.data.requests import NewsRequest  # imported here so the tests don't need it
    from helpers import news_client

    news = news_client().get_news(
        NewsRequest(symbols=symbol, start=datetime.now() - timedelta(days=days))
    ).df
    return pd.DataFrame({
        "published": pd.to_datetime(news["created_at"], utc=True),
        "symbols": symbol,
        "source": news["url"].apply(site_of),  # the site's name from its link, like the RSS
        "headline": news["headline"],
        "summary": news["summary"],
        "url": news["url"],
    }).reset_index(drop=True)


# --- 2. ARCHIVE -----------------------------------------------------------------------

def load_archive(path=ARCHIVE_FILE):
    if not os.path.exists(path):
        return pd.DataFrame(columns=COLUMNS)
    archive = pd.read_csv(path, keep_default_na=False)  # keep "" as "", not as NaN
    archive["published"] = pd.to_datetime(archive["published"], utc=True)
    return archive


def headline_key(headline):
    """Simplify a headline so tiny differences don't matter: 'Apple Drops 3%!' -> 'appledrops3'."""
    return "".join(ch for ch in str(headline).lower() if ch.isalnum())


def merge_into_archive(archive, new):
    """
    Add stories we haven't seen. A story is 'seen' if its URL OR its headline is already
    there (the same story often arrives from two sources with slightly different links).
    If a seen story arrives for another stock, that stock is added to its 'symbols'.
    Returns (updated archive, number of stories added).
    """
    stories = archive.to_dict("records")  # a list of dictionaries, one per story
    by_url = {s["url"]: s for s in stories}
    by_headline = {headline_key(s["headline"]): s for s in stories}
    added = 0

    for story in new.to_dict("records"):
        if not story["url"]:
            continue
        seen = by_url.get(story["url"]) or by_headline.get(headline_key(story["headline"]))
        if seen:
            # Same story: just make sure this stock is listed on it, e.g. "AAPL TSLA"
            symbols = set(str(seen["symbols"]).split()) | {story["symbols"]}
            seen["symbols"] = " ".join(sorted(symbols))
        else:
            story["text_status"] = ""  # "" = we haven't tried to fetch its text yet
            stories.append(story)
            by_url[story["url"]] = by_headline[headline_key(story["headline"])] = story
            added += 1

    combined = pd.DataFrame(stories, columns=COLUMNS)
    combined["published"] = pd.to_datetime(combined["published"], utc=True)
    return combined.sort_values("published", ascending=False, ignore_index=True), added


def save_archive(archive, path=ARCHIVE_FILE):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    archive.to_csv(path, index=False)


# --- 3. CRAWL -------------------------------------------------------------------------

class PoliteFetcher:
    """
    A CLASS bundles data and functions that belong together. Each PoliteFetcher
    remembers each site's robots.txt rules and when we last visited that site.
    """

    def __init__(self, delay=DELAY_SECONDS):
        self.delay = delay
        self.session = requests.Session()  # reuses connections; faster and lighter for sites
        self.session.headers["User-Agent"] = USER_AGENT
        self.robots = {}       # domain -> its rules
        self.last_visit = {}   # domain -> time of our last request

    def rules_for(self, domain):
        if domain not in self.robots:
            rules = urllib.robotparser.RobotFileParser()
            try:
                r = self.session.get(f"https://{domain}/robots.txt", timeout=10)
                # No robots.txt (404) means "no special rules"; other errors mean "keep out"
                rules.parse(r.text.splitlines() if r.ok else ([] if r.status_code == 404
                                                              else ["User-agent: *", "Disallow: /"]))
            except requests.RequestException:
                rules.parse(["User-agent: *", "Disallow: /"])
            self.robots[domain] = rules
        return self.robots[domain]

    def check(self, url):
        """Return "" if we may visit the URL, otherwise the reason we may not."""
        domain = urlparse(url).netloc
        if domain.removeprefix("www.") in SKIP_DOMAINS or domain in SKIP_DOMAINS:
            return "skipped_site"
        if not self.rules_for(domain).can_fetch(USER_AGENT, url):
            return "blocked_by_robots"
        return ""

    def get(self, url):
        """Download a page, waiting first if we visited this site very recently."""
        domain = urlparse(url).netloc
        wait = self.delay - (time.time() - self.last_visit.get(domain, 0))
        if wait > 0:
            time.sleep(wait)
        self.last_visit[domain] = time.time()
        return self.session.get(url, timeout=15)


def article_file(url):
    """A short, safe file name for a URL (a 'hash': a fingerprint of the text)."""
    return os.path.join(ARTICLES_DIR, hashlib.sha1(url.encode()).hexdigest()[:16] + ".txt")


def crawl_new_articles(archive, fetcher, limit=20):
    """
    Visit stories whose text we haven't tried to get yet (text_status is empty),
    save the article text, and record what happened in text_status.
    """
    os.makedirs(ARTICLES_DIR, exist_ok=True)
    todo = archive.index[archive["text_status"] == ""][:limit]
    for i in todo:
        url = archive.at[i, "url"]
        status = fetcher.check(url)
        if not status:
            try:
                response = fetcher.get(url)
                if not response.ok:
                    status = f"http_{response.status_code}"  # e.g. 403 = "forbidden"
                else:
                    text = trafilatura.extract(response.text) or ""
                    if len(text) < 300:  # too short: probably a paywall or a JavaScript-only page
                        status = "no_article_text"
                    else:
                        with open(article_file(url), "w") as f:
                            f.write(text)
                        status = "saved"
            except requests.RequestException as error:
                status = f"error_{type(error).__name__}"
        archive.at[i, "text_status"] = status
        print(f"  {status:<18} {archive.at[i, 'source'][:18]:<19} {archive.at[i, 'headline'][:60]}")
    return archive
