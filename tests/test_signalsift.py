import pandas as pd
import pytest

from signalsift.pipeline import SAMPLE_DATA, run_pipeline
from signalsift.preprocess import clean_text, load_reviews, prepare_reviews, rating_to_sentiment
from signalsift.prioritize import PrioritizationConfig, score_backlog
from signalsift.trends import detect_spikes


@pytest.fixture(scope="module")
def result():
    return run_pipeline(load_reviews(SAMPLE_DATA))


def test_clean_text_strips_noise():
    assert clean_text("  UPI failed!!! See https://x.co  ") == "upi failed see"


def test_rating_to_sentiment():
    assert [rating_to_sentiment(r) for r in (1, 2, 3, 4, 5)] == \
        ["negative", "negative", "neutral", "positive", "positive"]


def test_prepare_rejects_missing_columns():
    with pytest.raises(ValueError, match="text"):
        prepare_reviews(pd.DataFrame({"date": ["2026-01-01"]}))


def test_prepare_drops_bad_rows():
    df = prepare_reviews(pd.DataFrame({"date": ["2026-01-01", "not a date", "2026-01-02"],
                                       "text": ["Great app", "Bad", "!!!"]}))
    assert df["text"].tolist() == ["Great app"]


def test_sentiment_model_beats_baseline(result):
    metrics = result.sentiment_model.metrics
    assert metrics["accuracy"] > 0.75
    assert metrics["negative_recall"] > 0.8


def test_themes_recover_labelled_topics(result):
    assert result.theme_model.k == 8
    assert result.theme_ari > 0.9


def test_planted_incidents_are_detected(result):
    alerted = result.alerts.set_index("theme")
    payment = next(t for t in alerted.index if "payment" in t)
    fees = next(t for t in alerted.index if "fee" in t)
    # v4.2 shipped 18 Aug 2026; the handling fee went live 1 Jul 2026.
    assert pd.Timestamp("2026-08-17") <= alerted.loc[payment, "week"] <= pd.Timestamp("2026-08-24")
    assert pd.Timestamp("2026-06-29") <= alerted.loc[fees, "week"] <= pd.Timestamp("2026-07-20")
    assert len(result.alerts) == 2, "no false alarms on the sample data"


def test_payment_incident_ranks_first(result):
    assert "payment" in result.backlog.iloc[0]["theme"]


def test_praise_ranks_low(result):
    praise_rank = result.backlog.loc[result.backlog["negative_rate"] < 0.2, "rank"]
    assert praise_rank.min() > len(result.backlog) - 3


def test_effort_changes_ranking(result):
    top = result.backlog.iloc[0]["theme"]
    rescored = score_backlog(result.themes, {top: 52}, PrioritizationConfig())
    assert rescored.iloc[0]["theme"] != top


def test_spike_detector_ignores_noise_and_catches_jump():
    weeks = pd.date_range("2026-01-05", periods=10, freq="W-MON")
    weekly = pd.DataFrame({"steady": [10, 12, 9, 11, 10, 12, 11, 9, 10, 12],
                           "spiky": [10, 12, 9, 11, 10, 12, 11, 9, 10, 40]}, index=weeks)
    spikes = detect_spikes(weekly)
    assert spikes["theme"].tolist() == ["spiky"]


def test_new_feedback_can_be_classified(result):
    cleaned = clean_text("UPI payment failed and money deducted")
    assert result.sentiment_model.predict([cleaned]).iloc[0]["sentiment"] == "negative"
    assert "payment" in result.theme_model.assign([cleaned])[0]


def test_works_without_ratings():
    df = load_reviews(SAMPLE_DATA).drop(columns=["rating", "gold_theme"]).head(600)
    result = run_pipeline(df, k=6)
    assert "bundled" in result.sentiment_trained_on
    assert len(result.backlog) == 6
