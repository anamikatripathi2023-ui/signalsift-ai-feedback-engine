"""Turn themes into a ranked, RICE-scored opportunity backlog.

RICE = Reach x Impact x Confidence / Effort (the framework Intercom popularised).
Each input is derived from the feedback itself, so the ranking is reproducible
and every number can be challenged in a review meeting:

* Reach      - estimated monthly users touched: theme share of feedback x MAU.
* Impact     - how badly it hurts (0.25-3): negative rate x severity, where
               severity rises with mentions of money loss, crashes or safety.
* Confidence - how much evidence we have (0.5 / 0.8 / 1.0 by review volume).
* Effort     - person-weeks; a PM/engineering estimate, editable in the app.

An urgency multiplier (1-2x) boosts themes that are growing fast right now, but
only when the growth is statistically real (Poisson test), so noise is ignored.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy.stats import binomtest

CRITICAL_TERMS = ("deducted", "debited", "money", "refund", "crash", "crashes", "crashing",
                  "failed", "fails", "failing", "expired", "rotten", "health", "charged")


@dataclass
class PrioritizationConfig:
    monthly_active_users: int = 2_000_000
    default_effort_weeks: float = 3.0
    recent_days: int = 28


def summarize_themes(df: pd.DataFrame, recent_days: int = 28) -> pd.DataFrame:
    """One row per theme with volume, sentiment, severity and momentum."""
    end = df["date"].max()
    recent_start = end - pd.Timedelta(days=recent_days)
    prior_start = recent_start - pd.Timedelta(days=recent_days)
    critical = df["clean_text"].str.contains(r"\b(?:" + "|".join(CRITICAL_TERMS) + r")\b", regex=True)

    frame = df.assign(
        is_negative=df["sentiment"].eq("negative"),
        is_critical=critical,
        is_recent=df["date"] > recent_start,
        is_prior=(df["date"] > prior_start) & (df["date"] <= recent_start),
    )
    summary = frame.groupby("theme").agg(
        reviews=("clean_text", "size"),
        negative_rate=("is_negative", "mean"),
        critical_rate=("is_critical", "mean"),
        recent_reviews=("is_recent", "sum"),
        prior_reviews=("is_prior", "sum"),
    )
    if "rating" in frame.columns and frame["rating"].notna().any():
        summary["avg_rating"] = frame.groupby("theme")["rating"].mean().round(2)

    summary["share"] = summary["reviews"] / summary["reviews"].sum()
    summary["trend"] = np.where(
        summary["prior_reviews"] > 0,
        summary["recent_reviews"] / summary["prior_reviews"].clip(lower=1) - 1,
        np.where(summary["recent_reviews"] > 0, 1.0, 0.0),
    )
    # If the underlying rate had not changed, recent reviews would be
    # Binomial(recent + prior, 0.5). A small p-value means the change is real.
    summary["trend_p_value"] = [
        binomtest(int(r), int(r + p), 0.5).pvalue if r + p > 0 else 1.0
        for r, p in zip(summary["recent_reviews"], summary["prior_reviews"])
    ]
    summary["trend_significant"] = summary["trend_p_value"] < 0.05
    return summary.round({"negative_rate": 3, "critical_rate": 3, "share": 4, "trend": 3, "trend_p_value": 4}) \
        .sort_values("reviews", ascending=False).reset_index()


def _confidence(reviews: int) -> float:
    if reviews >= 100:
        return 1.0
    if reviews >= 30:
        return 0.8
    return 0.5


def score_backlog(summary: pd.DataFrame, effort_weeks: dict[str, float] | None = None,
                  config: PrioritizationConfig | None = None) -> pd.DataFrame:
    """Add RICE inputs, an urgency multiplier and a 0-100 opportunity score, ranked."""
    config = config or PrioritizationConfig()
    effort_weeks = effort_weeks or {}
    backlog = summary.copy()

    severity = 1 + 2 * backlog["critical_rate"]
    backlog["reach"] = (backlog["share"] * config.monthly_active_users).round().astype(int)
    backlog["impact"] = (backlog["negative_rate"] * severity).clip(0.25, 3).round(2)
    backlog["confidence"] = backlog["reviews"].map(_confidence)
    backlog["effort_weeks"] = [float(effort_weeks.get(t, config.default_effort_weeks)) for t in backlog["theme"]]
    backlog["effort_weeks"] = backlog["effort_weeks"].clip(lower=0.5)
    backlog["rice"] = (backlog["reach"] * backlog["impact"] * backlog["confidence"] / backlog["effort_weeks"]).round()
    backlog["urgency"] = (1 + backlog["trend"].clip(0, 1).where(backlog["trend_significant"], 0)).round(2)

    raw = backlog["rice"] * backlog["urgency"]
    backlog["opportunity_score"] = (100 * raw / raw.max()).round(1) if raw.max() > 0 else 0.0
    backlog = backlog.sort_values("opportunity_score", ascending=False).reset_index(drop=True)
    backlog.insert(0, "rank", range(1, len(backlog) + 1))
    return backlog
