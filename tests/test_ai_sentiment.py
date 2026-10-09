"""
Tests for ai_sentiment.py. We swap the real FinBERT for a FAKE model, so the tests are
instant, need no download, and we know the right answers. (This trick is called a "mock".)
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ai_sentiment import score_texts  # noqa: E402

calls = []


def fake_model(texts):
    """Pretends to be FinBERT: 'up' -> positive, 'down' -> negative, else neutral."""
    calls.append(list(texts))
    out = []
    for t in texts:
        if "up" in t:
            out.append({"positive": 0.9, "negative": 0.05, "neutral": 0.05})
        elif "down" in t:
            out.append({"positive": 0.1, "negative": 0.8, "neutral": 0.1})
        else:
            out.append({"positive": 0.2, "negative": 0.1, "neutral": 0.7})
    return out


def test_labels_and_scores(tmp_path):
    result = score_texts(["stock up", "stock down", "meeting today"],
                         model=fake_model, cache_file=tmp_path / "cache.csv")
    assert list(result["label"]) == ["positive", "negative", "neutral"]
    assert list(result["score"]) == [1, -1, 0]


def test_cache_means_each_text_is_scored_once(tmp_path):
    cache = tmp_path / "cache.csv"
    calls.clear()
    score_texts(["stock up", "stock down"], model=fake_model, cache_file=cache)
    score_texts(["stock up", "stock down", "new text"], model=fake_model, cache_file=cache)
    # 1st call scores both texts; 2nd call only needs the one it hasn't seen
    assert calls == [["stock up", "stock down"], ["new text"]]


def test_repeated_texts_keep_their_order(tmp_path):
    result = score_texts(["down", "up", "down"], model=fake_model, cache_file=tmp_path / "c.csv")
    assert list(result["text"]) == ["down", "up", "down"]
    assert list(result["score"]) == [-1, 1, -1]
