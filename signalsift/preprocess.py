"""Loading, validation and text cleaning for raw user feedback."""
from __future__ import annotations

import re

import pandas as pd

REQUIRED_COLUMNS = {"date", "text"}
SENTIMENT_LABELS = ("negative", "neutral", "positive")

_URL = re.compile(r"http\S+")
_NON_ALPHANUMERIC = re.compile(r"[^a-z0-9\s]")
_WHITESPACE = re.compile(r"\s+")


def clean_text(text: str) -> str:
    """Lower-case, strip URLs and punctuation, collapse whitespace."""
    text = _URL.sub(" ", str(text).lower())
    text = _NON_ALPHANUMERIC.sub(" ", text)
    return _WHITESPACE.sub(" ", text).strip()


def rating_to_sentiment(rating: float) -> str:
    """Star ratings act as weak labels: 1-2 negative, 3 neutral, 4-5 positive."""
    if rating <= 2:
        return "negative"
    if rating == 3:
        return "neutral"
    return "positive"


def prepare_reviews(df: pd.DataFrame) -> pd.DataFrame:
    """Validate a feedback table and add a ``clean_text`` column.

    Only ``date`` and ``text`` are required. ``rating``, ``platform``,
    ``app_version`` and ``city_tier`` unlock extra analysis when present.
    """
    df = df.copy()
    df.columns = [str(c).strip().lower() for c in df.columns]
    missing = REQUIRED_COLUMNS - set(df.columns)
    if missing:
        raise ValueError(f"Feedback file is missing required column(s): {', '.join(sorted(missing))}")

    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date", "text"])
    df["text"] = df["text"].astype(str)
    df["clean_text"] = df["text"].map(clean_text)
    df = df[df["clean_text"].str.len() > 0]

    if "rating" in df.columns:
        df["rating"] = pd.to_numeric(df["rating"], errors="coerce")
        df.loc[~df["rating"].between(1, 5), "rating"] = pd.NA

    if df.empty:
        raise ValueError("No usable feedback rows after cleaning.")
    return df.sort_values("date", kind="stable").reset_index(drop=True)


def load_reviews(source) -> pd.DataFrame:
    """Read a CSV path or file-like object and prepare it."""
    return prepare_reviews(pd.read_csv(source))
