"""Weekly trend tracking, spike alerts and segment drill-downs."""
from __future__ import annotations

import math

import pandas as pd


def weekly_counts(df: pd.DataFrame, group_col: str = "theme") -> pd.DataFrame:
    """Reviews per week (rows, Monday start) per group (columns). Missing weeks are 0.

    Partial weeks at either end of the data are dropped: a week with 3 days of
    data would otherwise look like a sudden fall in volume.
    """
    weeks = df["date"].dt.to_period("W-SUN").dt.start_time
    table = df.assign(week=weeks).pivot_table(index="week", columns=group_col, values="clean_text",
                                              aggfunc="count", fill_value=0)
    full_range = pd.date_range(table.index.min(), table.index.max(), freq="W-MON")
    table = table.reindex(full_range, fill_value=0).rename_axis("week")
    first_day, last_day = df["date"].min().normalize(), df["date"].max().normalize()
    complete = (table.index >= first_day) & (table.index + pd.Timedelta(days=6) <= last_day)
    return table[complete]


def detect_spikes(weekly: pd.DataFrame, baseline_weeks: int = 6, z_threshold: float = 3.5,
                  min_count: int = 8) -> pd.DataFrame:
    """Flag weeks where a theme's volume jumps far above its trailing baseline.

    The baseline standard deviation is floored at the Poisson noise level
    (sqrt of the mean) so small, naturally noisy themes do not raise false alarms.
    The 3.5 threshold was back-tested on the sample data: it catches both known
    incidents within three weeks of them starting and raises no false alarms.
    """
    alerts = []
    for theme in weekly.columns:
        series = weekly[theme]
        for i in range(baseline_weeks, len(series)):
            baseline = series.iloc[i - baseline_weeks:i]
            mean = float(baseline.mean())
            std = max(float(baseline.std(ddof=1)), math.sqrt(max(mean, 1.0)))
            count = int(series.iloc[i])
            z_score = (count - mean) / std
            if z_score >= z_threshold and count >= min_count:
                alerts.append({
                    "week": series.index[i], "theme": theme, "count": count,
                    "baseline_mean": round(mean, 1), "z_score": round(z_score, 1),
                    "change_vs_baseline": round(count / mean - 1, 2) if mean else None,
                })
    columns = ["week", "theme", "count", "baseline_mean", "z_score", "change_vs_baseline"]
    return pd.DataFrame(alerts, columns=columns)


def first_alerts(spikes: pd.DataFrame) -> pd.DataFrame:
    """The first week each theme alerted: when the team would have been paged."""
    if spikes.empty:
        return spikes
    return spikes.sort_values("week").groupby("theme", as_index=False).first().sort_values("week")


def top_segment(df: pd.DataFrame, theme: str, segment_cols=("platform", "app_version", "city_tier"),
                min_share: float = 0.2, min_reviews: int = 10) -> dict | None:
    """Find the segment most over-represented in a theme (highest lift vs. all feedback).

    Lift = share of the theme's reviews in the segment / share of all reviews in it.
    A lift of 3 means the segment is 3x more likely to raise this theme. Single
    columns and pairs of columns are both checked, e.g. "Android + v4.2". Tiny
    segments are ignored so the answer is something worth acting on.
    """
    columns = [c for c in segment_cols if c in df.columns]
    if not columns:
        return None
    candidates = {c: df[c].astype(str) for c in columns}
    for i, first in enumerate(columns):
        for second in columns[i + 1:]:
            candidates[f"{first} + {second}"] = df[first].astype(str) + " + " + df[second].astype(str)

    in_theme = df["theme"] == theme
    best = None
    for name, values in candidates.items():
        overall = values.value_counts(normalize=True)
        within = values[in_theme].value_counts()
        for value, count in within.items():
            share = count / in_theme.sum()
            if count < min_reviews or share < min_share:
                continue
            lift = share / overall[value]
            if best is None or lift > best["lift"]:
                best = {"segment": f"{name} = {value}", "reviews": int(count),
                        "share_of_theme": round(float(share), 3),
                        "share_of_all": round(float(overall[value]), 3), "lift": round(float(lift), 2)}
    return best
