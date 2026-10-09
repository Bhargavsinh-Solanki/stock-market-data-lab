"""
ai_sentiment.py - FinBERT, a free AI model that reads financial text (Lesson 18).

FinBERT was trained on thousands of financial news sentences labelled
positive / negative / neutral by people. Unlike our word list (Lesson 15),
it reads the whole sentence, so "Tariffs Delivered 85% of Apple's Earnings Beat"
isn't fooled by the word "beat".

It runs on YOUR Mac: free, no account, no data sent anywhere.
The first use downloads the model once (~440 MB) from Hugging Face.

Scores are CACHED in data/finbert_cache.csv: each text is scored once,
then remembered - the same idea as the crawler never re-downloading a page.
"""

import os

import pandas as pd

MODEL_NAME = "ProsusAI/finbert"
CACHE_FILE = "data/finbert_cache.csv"
LABELS = ["positive", "negative", "neutral"]

_model = None  # loaded on first use, then reused (loading takes a few seconds)


def finbert(texts):
    """Run FinBERT on a list of texts. Returns one {label: probability} dict per text."""
    global _model
    if _model is None:
        import huggingface_hub
        import torch
        import transformers
        from transformers import pipeline

        # Hide chatty notices (e.g. "set a HF_TOKEN" - an account is NOT needed for this model)
        transformers.logging.set_verbosity_error()
        huggingface_hub.logging.set_verbosity_error()

        device = "mps" if torch.backends.mps.is_available() else "cpu"  # Mac graphics chip if possible
        _model = pipeline("text-classification", model=MODEL_NAME, top_k=None, device=device)
    # truncation=True: FinBERT reads at most ~400 words; longer articles are cut short
    results = _model(list(texts), batch_size=32, truncation=True)
    return [{r["label"]: r["score"] for r in result} for result in results]


def score_texts(texts, model=finbert, cache_file=CACHE_FILE):
    """
    Probabilities for each text, using the cache where possible.
    Returns a table: text, positive, negative, neutral, label, score
      label = the most likely of the three
      score = +1 positive, -1 negative, 0 neutral (same scale as the Lesson 15 word list)
    `model` can be swapped for a fake one in tests.
    """
    texts = pd.Series(list(texts), dtype=str)
    cache = (pd.read_csv(cache_file, keep_default_na=False)
             if os.path.exists(cache_file) else pd.DataFrame(columns=["text", *LABELS]))

    todo = texts[~texts.isin(cache["text"])].drop_duplicates()
    if len(todo):
        new = pd.DataFrame(model(todo.tolist()))[LABELS]
        new.insert(0, "text", todo.values)
        cache = pd.concat([cache, new], ignore_index=True)
        os.makedirs(os.path.dirname(cache_file) or ".", exist_ok=True)
        cache.to_csv(cache_file, index=False)

    lookup = cache.drop_duplicates("text").set_index("text")[LABELS].astype(float)
    result = lookup.loc[texts].reset_index()
    result["label"] = result[LABELS].idxmax(axis=1)
    result["score"] = result["label"].map({"positive": 1, "negative": -1, "neutral": 0})
    return result
