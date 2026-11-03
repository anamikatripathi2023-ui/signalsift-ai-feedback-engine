"""SignalSift dashboard. Run with:  streamlit run app.py"""
from __future__ import annotations

import io
from dataclasses import replace

import pandas as pd
import plotly.express as px
import streamlit as st

from signalsift.brief import build_brief
from signalsift.pipeline import SAMPLE_DATA, run_pipeline
from signalsift.preprocess import clean_text, load_reviews
from signalsift.prioritize import PrioritizationConfig, score_backlog
from signalsift.themes import DEFAULT_THEMES, fit_themes
from signalsift.trends import top_segment

st.set_page_config(page_title="SignalSift - Voice of Customer AI", layout="wide")


@st.cache_resource(show_spinner="Reading feedback and training models...")
def analyse(file_bytes: bytes | None, k: int, mau: int):
    source = io.BytesIO(file_bytes) if file_bytes else SAMPLE_DATA
    return run_pipeline(load_reviews(source), PrioritizationConfig(monthly_active_users=mau), k=k)


@st.cache_data(show_spinner="Scoring theme counts...")
def silhouette_curve(file_bytes: bytes | None) -> pd.DataFrame:
    source = io.BytesIO(file_bytes) if file_bytes else SAMPLE_DATA
    model = fit_themes(load_reviews(source)["clean_text"], diagnostics_k_range=range(5, 13))
    return pd.DataFrame(list(model.silhouette_by_k.items()), columns=["themes", "silhouette"])


# ---------------------------------------------------------------- sidebar
st.sidebar.title("SignalSift")
st.sidebar.caption("Turns raw user feedback into a prioritised product backlog.")
upload = st.sidebar.file_uploader("Upload feedback CSV", type="csv",
                                  help="Needs `date` and `text` columns. Optional: rating, platform, "
                                       "app_version, city_tier.")
file_bytes = upload.getvalue() if upload else None
if not upload:
    st.sidebar.info("Using the sample: 6 months of reviews for FreshKart, a fictional 10-minute grocery app.")
k = st.sidebar.slider("Number of themes", 5, 12, DEFAULT_THEMES,
                      help="More themes = finer detail but a longer backlog.")
mau = st.sidebar.number_input("Monthly active users", 10_000, 500_000_000, 2_000_000, step=100_000,
                              help="Used to estimate how many users each theme reaches.")

try:
    result = analyse(file_bytes, k, int(mau))
except ValueError as error:
    st.error(f"Could not analyse this file: {error}")
    st.stop()

df = result.reviews
st.title("Voice of Customer insights")
st.caption(f"{len(df):,} pieces of feedback from {df['date'].min():%d %b %Y} to {df['date'].max():%d %b %Y}")

tab_overview, tab_themes, tab_alerts, tab_backlog, tab_try, tab_brief = st.tabs(
    ["Overview", "Themes", "Spike alerts", "Prioritised backlog", "Try the model", "Insights brief"]
)

# ---------------------------------------------------------------- overview
with tab_overview:
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Feedback analysed", f"{len(df):,}")
    c2.metric("Negative", f"{df['sentiment'].eq('negative').mean():.0%}")
    c3.metric("Themes found", result.theme_model.k)
    c4.metric("Themes with spike alerts", len(result.alerts))

    weekly_sentiment = (df.assign(week=df["date"].dt.to_period("W-SUN").dt.start_time)
                        .groupby(["week", "sentiment"]).size().reset_index(name="reviews"))
    weekly_sentiment = weekly_sentiment[weekly_sentiment["week"].isin(result.weekly.index)]  # complete weeks only
    st.plotly_chart(px.area(weekly_sentiment, x="week", y="reviews", color="sentiment",
                            title="Weekly feedback volume by sentiment",
                            color_discrete_map={"negative": "#d1495b", "neutral": "#edae49", "positive": "#00798c"}),
                    width="stretch")

    m = result.sentiment_model.metrics
    st.markdown(
        f"**Model quality.** Sentiment was trained on {result.sentiment_trained_on}: hold-out accuracy "
        f"**{m['accuracy']:.0%}**, macro F1 **{m['macro_f1']}**, negative recall **{m['negative_recall']:.0%}**."
        + (f" Theme discovery matches the labelled evaluation set at **ARI {result.theme_ari}**."
           if result.theme_ari is not None else "")
    )

# ---------------------------------------------------------------- themes
with tab_themes:
    themes = result.themes.sort_values("reviews")
    st.plotly_chart(px.bar(themes, x="reviews", y="theme", orientation="h", color="negative_rate",
                           color_continuous_scale="RdYlGn_r", range_color=(0, 1),
                           title="Themes by volume (colour = share negative)"), width="stretch")

    chosen = st.selectbox("Drill into a theme", result.backlog["theme"])
    row = result.themes.set_index("theme").loc[chosen]
    c1, c2, c3 = st.columns(3)
    c1.metric("Reviews", f"{int(row['reviews']):,}")
    c2.metric("Negative", f"{row['negative_rate']:.0%}")
    c3.metric("Last 28 days vs previous", f"{row['trend']:+.0%}",
              help="Statistically significant" if row["trend_significant"] else "Within normal noise")
    cluster_id = next(i for i, name in result.theme_model.names.items() if name == chosen)
    st.write("**Top terms:** " + ", ".join(result.theme_model.top_terms[cluster_id]))
    segment = top_segment(df, chosen)
    if segment and segment["lift"] >= 1.5:
        st.warning(f"Over-represented in **{segment['segment']}**: {segment['share_of_theme']:.0%} of this theme "
                   f"vs {segment['share_of_all']:.0%} of all feedback ({segment['lift']}x lift).")
    examples = df[df["theme"] == chosen][["date", "text", "sentiment"] + (["rating"] if "rating" in df else [])]
    st.dataframe(examples.sort_values("date", ascending=False).head(25), hide_index=True, width="stretch")

    with st.expander("How many themes should we use?"):
        st.write("Silhouette measures how well separated the themes are (higher is better). It usually keeps "
                 "rising as themes get finer, so pick the point where extra themes stop being actionable.")
        if st.button("Score 5-12 themes"):
            st.plotly_chart(px.line(silhouette_curve(file_bytes), x="themes", y="silhouette", markers=True),
                            width="stretch")

# ---------------------------------------------------------------- alerts
with tab_alerts:
    weekly_long = result.weekly.reset_index().melt(id_vars="week", var_name="theme", value_name="reviews")
    fig = px.line(weekly_long, x="week", y="reviews", color="theme", title="Weekly reviews per theme")
    if not result.alerts.empty:
        fig.add_scatter(x=result.alerts["week"], y=result.alerts["count"], mode="markers",
                        marker={"size": 14, "symbol": "x", "color": "black"}, name="first alert")
    st.plotly_chart(fig, width="stretch")
    if result.alerts.empty:
        st.success("No spikes: every theme is within its normal weekly range.")
    else:
        st.write("First week each theme broke above its 6-week baseline (z-score >= 3.5):")
        st.dataframe(result.alerts, hide_index=True, width="stretch")

# ---------------------------------------------------------------- backlog
with tab_backlog:
    st.write("Engineering effort is a team estimate. Edit it and the ranking updates.")
    efforts = st.data_editor(
        result.backlog[["theme", "effort_weeks"]], hide_index=True, width="stretch",
        column_config={"theme": st.column_config.TextColumn(disabled=True),
                       "effort_weeks": st.column_config.NumberColumn("effort (person-weeks)", min_value=0.5,
                                                                     max_value=52, step=0.5)},
    )
    backlog = score_backlog(result.themes, dict(zip(efforts["theme"], efforts["effort_weeks"])), result.config)
    st.dataframe(backlog[["rank", "theme", "reviews", "negative_rate", "trend", "reach", "impact", "confidence",
                          "effort_weeks", "urgency", "opportunity_score"]]
                 .style.format({"negative_rate": "{:.0%}", "trend": "{:+.0%}", "reach": "{:,}"}),
                 hide_index=True, width="stretch")
    st.plotly_chart(px.scatter(backlog, x="reach", y="impact", size="opportunity_score", color="theme",
                               size_max=60, title="Opportunity map: reach vs impact (bubble = score)"),
                    width="stretch")
    result = replace(result, backlog=backlog)

# ---------------------------------------------------------------- try it
with tab_try:
    text = st.text_area("Paste any piece of feedback", "Payment failed twice with UPI and money was deducted")
    if text.strip():
        cleaned = clean_text(text)
        prediction = result.sentiment_model.predict([cleaned]).iloc[0]
        c1, c2 = st.columns(2)
        c1.metric("Sentiment", prediction["sentiment"].title())
        c2.metric("Theme", result.theme_model.assign([cleaned])[0])
        probabilities = prediction.drop("sentiment").astype(float).rename(lambda c: c.replace("p_", ""))
        st.plotly_chart(px.bar(x=probabilities.index, y=probabilities.values, labels={"x": "", "y": "probability"},
                               range_y=(0, 1)), width="stretch")

# ---------------------------------------------------------------- brief
with tab_brief:
    brief = build_brief(result)
    st.download_button("Download brief (Markdown)", brief, file_name="insights_brief.md")
    st.markdown(brief)
