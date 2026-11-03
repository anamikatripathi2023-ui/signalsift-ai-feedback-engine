"""Sentiment classifier trained on star ratings as weak labels.

Star ratings are noisy but free labels. Training a text model on them lets us
score feedback that has no rating at all (support tickets, social posts,
survey verbatims) on the same scale.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, classification_report, f1_score
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline

from .preprocess import SENTIMENT_LABELS, rating_to_sentiment


@dataclass
class SentimentModel:
    pipeline: Pipeline
    metrics: dict = field(default_factory=dict)

    def predict(self, clean_texts) -> pd.DataFrame:
        """Return the predicted label and the probability of each label."""
        texts = list(clean_texts)
        probabilities = self.pipeline.predict_proba(texts)
        classes = list(self.pipeline.classes_)
        result = pd.DataFrame(probabilities, columns=[f"p_{c}" for c in classes])
        result.insert(0, "sentiment", np.array(classes)[probabilities.argmax(axis=1)])
        return result


def _build_pipeline() -> Pipeline:
    return Pipeline([
        ("tfidf", TfidfVectorizer(ngram_range=(1, 2), min_df=2, sublinear_tf=True)),
        ("clf", LogisticRegression(max_iter=2000, class_weight="balanced")),
    ])


def train_sentiment_model(clean_texts, ratings, random_state: int = 42) -> SentimentModel:
    """Train on 80% of rated feedback, report hold-out metrics, then refit on all of it."""
    texts = pd.Series(list(clean_texts)).reset_index(drop=True)
    labels = pd.Series(list(ratings)).map(rating_to_sentiment).reset_index(drop=True)
    if labels.nunique() < len(SENTIMENT_LABELS):
        raise ValueError("Need negative, neutral and positive ratings to train the sentiment model.")

    x_train, x_test, y_train, y_test = train_test_split(
        texts, labels, test_size=0.2, stratify=labels, random_state=random_state
    )
    pipeline = _build_pipeline().fit(x_train, y_train)
    predicted = pipeline.predict(x_test)
    report = classification_report(y_test, predicted, output_dict=True, zero_division=0)
    metrics = {
        "accuracy": round(float(accuracy_score(y_test, predicted)), 3),
        "macro_f1": round(float(f1_score(y_test, predicted, average="macro")), 3),
        "negative_recall": round(float(report["negative"]["recall"]), 3),
        "n_train": int(len(x_train)),
        "n_test": int(len(x_test)),
    }
    return SentimentModel(pipeline=_build_pipeline().fit(texts, labels), metrics=metrics)
