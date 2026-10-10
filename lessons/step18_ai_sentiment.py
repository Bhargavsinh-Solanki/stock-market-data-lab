"""
STEP 18: Let a free AI read the news (FinBERT).

Three parts:
  1. WORD LIST vs AI: score 6 months of Apple headlines both ways. Where do they disagree?
  2. YOUR CRAWLED ARTICLES: does the AI read the full article the same way as its headline?
  3. THE REAL QUESTION: does the AI's "good news" predict the next day better than the
     word list did? Lesson 16's luck test (shuffle test) on 12 stocks will tell us.

Run it with:   python lessons/step18_ai_sentiment.py      (1-3 minutes; first ever run also downloads the model)

New coding ideas in this lesson:
  - a pre-trained AI MODEL: someone else trained it, we just use it ("inference")
  - PROBABILITIES: the AI says "92% positive", not just "positive"
  - MOCKS: in the tests, a fake AI stands in for the real one
  - LAZY LOADING: only load the heavy AI library when it's actually needed
"""

import os

import pandas as pd

from lab.ai_sentiment import score_texts
from lab.crawler import article_file, load_archive
from lab.helpers import news_by_day, shuffle_test

SCOREBOARD = ["AAPL", "TSLA", "NVDA", "MSFT", "AMZN", "GOOGL",
              "META", "AMD", "NFLX", "JPM", "XOM", "INTC"]
label_of = lambda s: "positive" if s > 0 else "negative" if s < 0 else "neutral"

# --- Part 1: word list vs AI on Apple headlines ----------------------------------------
print("Part 1 - word list vs AI on 6 months of AAPL headlines")
news, _ = news_by_day("AAPL")
ai = score_texts(news["headline"])
news["word_label"] = news["score"].apply(label_of)  # Lesson 15's word-list score
news["ai_label"] = ai["label"].values
news["ai_confidence"] = ai[["positive", "negative", "neutral"]].max(axis=1).values

agree = (news["word_label"] == news["ai_label"]).mean()
print(f"  {len(news)} headlines. They agree on {agree:.0%} of them.\n")
print("  Rows = word list, columns = AI:")
print("  " + pd.crosstab(news["word_label"], news["ai_label"]).to_string().replace("\n", "\n  "))

print("\n  Biggest disagreements (AI very sure, word list says the opposite):")
opposite = news[((news["word_label"] == "positive") & (news["ai_label"] == "negative"))
                | ((news["word_label"] == "negative") & (news["ai_label"] == "positive"))]
for _, r in opposite.nlargest(4, "ai_confidence").iterrows():
    print(f"   words={r['word_label']:<8} AI={r['ai_label']} ({r['ai_confidence']:.0%})  "
          f"{r['headline'][:75]}")

# --- Part 2: headline vs full article (from your Lesson 17 crawler) ---------------------
print("\nPart 2 - your crawled articles: headline vs full text")
archive = load_archive()
saved = archive[archive["text_status"] == "saved"]
if saved.empty:
    print("  No saved articles yet - run step17_news_crawler.py first.")
else:
    texts = []
    for url in saved["url"]:
        with open(article_file(url)) as f:
            texts.append(f.read())
    head = score_texts(saved["headline"])
    body = score_texts(texts)
    same = (head["label"].values == body["label"].values).mean()
    print(f"  {len(saved)} articles. Headline and full article get the same label "
          f"{same:.0%} of the time.")
    print(f"  Headlines labelled neutral: {(head['label'] == 'neutral').mean():.0%}   "
          f"Full articles labelled neutral: {(body['label'] == 'neutral').mean():.0%}")
    for i in range(len(saved)):
        if head["label"].iat[i] != body["label"].iat[i]:
            print(f"  e.g. headline={head['label'].iat[i]}, article={body['label'].iat[i]}: "
                  f"{saved['headline'].iat[i][:70]}")
            break

# --- Part 3: does AI "good news" predict tomorrow? ---------------------------------------
print("\nPart 3 - luck test: good-news days -> price up the NEXT day?  (p < 0.05 = PASS)")
print(f"  {'Stock':<7}{'word list':>18}{'AI (FinBERT)':>20}")
passed = {"words": 0, "ai": 0}
for symbol in SCOREBOARD:
    try:
        news, table = news_by_day(symbol)
        news["ai_score"] = score_texts(news["headline"])["score"].values
        ai_mood = news.groupby("trading_day")["ai_score"].mean().rename("ai_mood")
        table = table.join(ai_mood).dropna(subset=["next_day_move_%"])
    except Exception as error:
        print(f"  {symbol:<7} skipped ({error})")
        continue

    line = f"  {symbol:<7}"
    for name, column in [("words", "mood"), ("ai", "ai_mood")]:
        _, _, p = shuffle_test(table["next_day_move_%"], table[column] > 0)
        passed[name] += p < 0.05
        line += f"{'p=' + format(p, '.3f') + (' PASS' if p < 0.05 else '     '):>19}"
    print(line)

n = len(SCOREBOARD)
print(f"\n  Passed: word list {passed['words']} of {n}, AI {passed['ai']} of {n}. "
      f"Pure luck would give about {n * 0.05:.1f}.")
print(f"\nAI scores are cached in data/finbert_cache.csv "
      f"({os.path.getsize('data/finbert_cache.csv') / 1e6:.1f} MB) - next run is much faster.")
