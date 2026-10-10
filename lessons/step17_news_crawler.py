"""
STEP 17: Build your own news archive with a polite crawler.

Each time you run this:
  1. Collect the latest headlines from Alpaca (last 7 days) and Yahoo Finance RSS
  2. Add ONLY the new ones to data/news_archive.csv (your archive grows over time)
  3. Visit up to MAX_PAGES new article pages and save their text in data/articles/
  4. Show a report: what's in the archive, and how the crawl went per website

Run it again later and you'll see "0 new" for stories you already have -
that's the point: fresh data every run, without re-downloading anything.

Run it with:   python lessons/step17_news_crawler.py
Other stocks:  python lessons/step17_news_crawler.py NVDA MSFT

New coding ideas in this lesson:
  - a CLASS (PoliteFetcher): data + functions bundled together
  - XML: the text format RSS feeds are written in
  - HTTP status codes: 200 = OK, 403 = forbidden, 404 = not found
  - de-duplication: never storing the same thing twice
"""

import sys

from lab.crawler import (
    PoliteFetcher, alpaca_headlines, article_file, crawl_new_articles, load_archive,
    merge_into_archive, save_archive, yahoo_headlines,
)

symbols = [s.upper() for s in sys.argv[1:]] or ["AAPL", "TSLA", "NVDA"]
MAX_PAGES = 15  # pages to visit per run - small and polite

archive = load_archive()
print(f"Archive before: {len(archive)} stories\n")

# --- 1 & 2. Collect and archive ---------------------------------------------------------
for symbol in symbols:
    for source_name, fetch in [("Alpaca", alpaca_headlines), ("Yahoo RSS", yahoo_headlines)]:
        try:
            new = fetch(symbol)
        except Exception as error:
            print(f"  {symbol:<5} {source_name:<10} failed: {error}")
            continue
        archive, added = merge_into_archive(archive, new)
        print(f"  {symbol:<5} {source_name:<10} {len(new):>3} headlines, {added:>3} new")

save_archive(archive)

# --- 3. Crawl new article pages -----------------------------------------------------------
waiting = (archive["text_status"] == "").sum()
print(f"\nCrawling up to {MAX_PAGES} of {waiting} stories without text yet "
      f"(a few seconds between visits to the same site)...")
archive = crawl_new_articles(archive, PoliteFetcher(), limit=MAX_PAGES)
save_archive(archive)  # save after crawling too, so progress isn't lost

# --- 4. Report ------------------------------------------------------------------------------
print(f"\nArchive after: {len(archive)} stories, "
      f"{archive['published'].min():%Y-%m-%d} -> {archive['published'].max():%Y-%m-%d}")

tried = archive[archive["text_status"] != ""]
if len(tried):
    print("\nCrawl results by website (all runs so far):")
    report = tried.groupby(["source", "text_status"]).size().unstack(fill_value=0)
    print(report.to_string())

    saved = tried[tried["text_status"] == "saved"]
    if len(saved):
        example = saved.iloc[0]
        with open(article_file(example["url"])) as f:
            text = f.read()
        print(f"\nExample saved article ({len(text):,} characters vs "
              f"{len(example['summary'])} in the summary):")
        print(f"  {example['headline']}")
        print(f"  \"{text[:300].strip()}...\"")
