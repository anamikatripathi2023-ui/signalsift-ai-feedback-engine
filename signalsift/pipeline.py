"""End-to-end pipeline: raw feedback in, prioritised insights out.

Run from the project root:
    python -m signalsift.pipeline --input data/reviews.csv --out outputs
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from .brief import write_brief
from .preprocess import load_reviews
from .prioritize import PrioritizationConfig, score_backlog, summarize_themes
from .sentiment import SentimentModel, train_sentiment_model
from .themes import DEFAULT_THEMES, ThemeModel, clustering_quality, fit_themes
from .trends import detect_spikes, first_alerts, weekly_counts

SAMPLE_DATA = Path(__file__).resolve().parent.parent / "data" / "reviews.csv"
MIN_RATED_ROWS = 200


@dataclass
class InsightsResult:
    reviews: pd.DataFrame
    themes: pd.DataFrame
    backlog: pd.DataFrame
    weekly: pd.DataFrame
    spikes: pd.DataFrame
    alerts: pd.DataFrame
    sentiment_model: SentimentModel
    theme_model: ThemeModel
    sentiment_trained_on: str
    theme_ari: float | None
    config: PrioritizationConfig


def run_pipeline(reviews: pd.DataFrame, config: PrioritizationConfig | None = None, k: int = DEFAULT_THEMES,
                 effort_weeks: dict[str, float] | None = None) -> InsightsResult:
    """Score sentiment, discover themes, detect spikes and rank opportunities.

    ``reviews`` must already be prepared with :func:`signalsift.preprocess.prepare_reviews`.
    If it has fewer than 200 star ratings, the sentiment model is trained on the
    bundled sample data instead and applied to the unrated feedback.
    """
    config = config or PrioritizationConfig()
    df = reviews.copy()

    rated = df.dropna(subset=["rating"]) if "rating" in df.columns else df.iloc[0:0]
    if len(rated) >= MIN_RATED_ROWS:
        sentiment_model = train_sentiment_model(rated["clean_text"], rated["rating"])
        trained_on = "your rated feedback"
    else:
        sample = load_reviews(SAMPLE_DATA)
        sentiment_model = train_sentiment_model(sample["clean_text"], sample["rating"])
        trained_on = "the bundled FreshKart sample (your file has too few star ratings)"
    df = pd.concat([df, sentiment_model.predict(df["clean_text"]).set_index(df.index)], axis=1)

    theme_model = fit_themes(df["clean_text"], k=k)
    df["theme"] = [theme_model.names[i] for i in theme_model.labels]
    theme_ari = clustering_quality(df["gold_theme"], theme_model.labels) if "gold_theme" in df.columns else None

    weekly = weekly_counts(df)
    spikes = detect_spikes(weekly)
    themes = summarize_themes(df, recent_days=config.recent_days)
    backlog = score_backlog(themes, effort_weeks=effort_weeks, config=config)

    return InsightsResult(df, themes, backlog, weekly, spikes, first_alerts(spikes),
                          sentiment_model, theme_model, trained_on, theme_ari, config)


def main() -> None:
    parser = argparse.ArgumentParser(description="Turn raw user feedback into a prioritised insights brief.")
    parser.add_argument("--input", type=Path, default=SAMPLE_DATA, help="CSV with at least date and text columns")
    parser.add_argument("--out", type=Path, default=Path("outputs"))
    parser.add_argument("--mau", type=int, default=PrioritizationConfig.monthly_active_users,
                        help="monthly active users, used to estimate reach")
    parser.add_argument("--k", type=int, default=DEFAULT_THEMES, help="number of themes to report")
    args = parser.parse_args()

    result = run_pipeline(load_reviews(args.input), PrioritizationConfig(monthly_active_users=args.mau), k=args.k)
    args.out.mkdir(parents=True, exist_ok=True)
    result.backlog.to_csv(args.out / "opportunity_backlog.csv", index=False)
    result.spikes.to_csv(args.out / "spike_alerts.csv", index=False)
    brief_path = write_brief(result, args.out / "insights_brief.md")

    print(f"Analysed {len(result.reviews):,} reviews into {result.theme_model.k} themes.")
    print(f"Sentiment model: accuracy {result.sentiment_model.metrics['accuracy']:.0%}, "
          f"macro F1 {result.sentiment_model.metrics['macro_f1']:.2f}")
    if result.theme_ari is not None:
        print(f"Theme discovery vs. labelled themes (ARI): {result.theme_ari:.2f}")
    print("Top 3 opportunities:")
    for row in result.backlog.head(3).itertuples():
        print(f"  {row.rank}. {row.theme}  (score {row.opportunity_score})")
    print(f"Brief written to {brief_path}")


if __name__ == "__main__":
    main()
