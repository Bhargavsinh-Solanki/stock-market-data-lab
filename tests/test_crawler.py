"""
Tests for crawler.py. No internet needed: we use a made-up RSS feed and
made-up robots.txt rules, so we know exactly what the right answers are.
"""

import sys
import urllib.robotparser
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lab.crawler import (  # noqa: E402
    COLUMNS, PoliteFetcher, article_file, headline_key, merge_into_archive, parse_rss, site_of,
)

FAKE_RSS = """<?xml version="1.0"?>
<rss><channel>
  <item>
    <title>Apple Drops 3% on Order Cuts</title>
    <link>https://www.example-news.com/apple-drops</link>
    <pubDate>Fri, 09 Oct 2026 13:31:32 +0000</pubDate>
    <description>Apple fell after a report.</description>
  </item>
  <item>
    <title>Apple Rallies</title>
    <link>https://other.com/rally</link>
    <pubDate>Fri, 09 Oct 2026 15:00:00 +0000</pubDate>
  </item>
</channel></rss>"""


def empty_archive():
    return pd.DataFrame(columns=COLUMNS)


def test_parse_rss():
    table = parse_rss(FAKE_RSS, "AAPL")
    assert len(table) == 2
    first = table.iloc[0]
    assert first["headline"] == "Apple Drops 3% on Order Cuts"
    assert first["source"] == "example-news.com"  # "www." removed
    assert first["published"].hour == 13 and str(first["published"].tz) == "UTC"
    assert table.iloc[1]["summary"] == ""  # missing description -> empty, not a crash


def test_site_of_and_headline_key():
    assert site_of("https://www.benzinga.com/news/x") == "benzinga.com"
    assert headline_key("Apple Drops 3%!") == headline_key("apple drops 3")


def test_merge_adds_new_and_ignores_repeats():
    archive, added = merge_into_archive(empty_archive(), parse_rss(FAKE_RSS, "AAPL"))
    assert added == 2
    archive, added = merge_into_archive(archive, parse_rss(FAKE_RSS, "AAPL"))  # same feed again
    assert added == 0 and len(archive) == 2


def test_merge_matches_same_headline_with_different_link():
    archive, _ = merge_into_archive(empty_archive(), parse_rss(FAKE_RSS, "AAPL"))
    copy = parse_rss(FAKE_RSS, "TSLA").head(1)
    copy["url"] = "https://mirror-site.com/apple-drops-3"  # different link, same story
    archive, added = merge_into_archive(archive, copy)
    assert added == 0
    row = archive[archive["headline"] == "Apple Drops 3% on Order Cuts"].iloc[0]
    assert row["symbols"] == "AAPL TSLA"  # the story now counts for both stocks


def test_newest_story_first():
    archive, _ = merge_into_archive(empty_archive(), parse_rss(FAKE_RSS, "AAPL"))
    assert archive.iloc[0]["headline"] == "Apple Rallies"  # 15:00 is newer than 13:31


def test_polite_fetcher_follows_the_rules():
    fetcher = PoliteFetcher()
    rules = urllib.robotparser.RobotFileParser()
    rules.parse(["User-agent: *", "Disallow: /private/"])
    fetcher.robots["news.com"] = rules  # pretend we already downloaded news.com's robots.txt

    assert fetcher.check("https://news.com/stories/apple") == ""
    assert fetcher.check("https://news.com/private/secret") == "blocked_by_robots"
    assert fetcher.check("https://finance.yahoo.com/news/x") == "skipped_site"


def test_article_file_names():
    a, b = article_file("https://a.com/1"), article_file("https://a.com/2")
    assert a == article_file("https://a.com/1")  # same URL -> same file, every time
    assert a != b and a.endswith(".txt")
