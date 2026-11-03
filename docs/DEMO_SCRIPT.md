# 5-minute demo script

**Setup:** run `streamlit run app.py` before the meeting. Open the Overview tab.

| Time | Screen | What to say |
|---|---|---|
| 0:00 | Title | "PMs get thousands of reviews and read maybe 50. I built SignalSift to read all of them and say what to fix first, and to catch a bad release in days instead of weeks." |
| 0:30 | **Overview** | "This is 6 months of reviews for FreshKart, a fictional grocery app: about 3,000 reviews. 53% are negative. The sentiment model learned from star ratings, so it can also score tickets that have no rating. It gets 88% of negative feedback right." |
| 1:15 | **Themes** | "No one labelled these. The model found 8 themes on its own and named them from their top words. Let me drill into payments." *(Select the payment theme.)* "It flags that this theme is concentrated in Android plus app v4.2." |
| 2:00 | **Spike alerts** | "Here is the key moment. v4.2 shipped on 18 August. The alert fired the same week, at seven standard deviations above normal. The threshold was tuned so that over 6 months there were zero false alarms. If an alert tool cries wolf, people mute it." |
| 2:45 | **Prioritised backlog** | "Delivery delays are the *largest* theme, but payments ranks #1. Losing money is more severe, and it is growing. Every input is visible. Watch: if engineering says the payment fix is a 20-week project…" *(edit effort)* "…the ranking updates. Engineering owns that input." |
| 3:45 | **Try the model** | *(Type a new complaint.)* "Support can paste any ticket and get a theme and sentiment instantly." |
| 4:15 | **Insights brief** | "Finally, it writes the weekly brief: TL;DR, alerts, backlog and real quotes. I can paste it straight into a team update." |
| 4:40 | Close | "Next steps: test it with three product teams, add Hindi support, and connect directly to the Play Store. Happy to go deeper on any trade-off; they're in my decision log." |

## Likely questions

- **Why not just use an LLM?** Cost, reproducibility and privacy. See [decision log D1](DECISIONS.md).
- **How do you know the themes are right?** Measured against labelled data (ARI 0.98), and the model quality is shown in the product.
- **What would you measure after launch?** Time from issue onset to awareness. See [metrics](METRICS_AND_LAUNCH.md).
- **Reviews are biased toward angry people. Doesn't that skew reach?** Yes. Reach is labelled as an estimate, and the next step joins feedback with product analytics.
