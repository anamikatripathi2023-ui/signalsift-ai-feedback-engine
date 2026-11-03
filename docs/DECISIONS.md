# Decision log

Product decisions are trade-offs. This log records what was chosen, what was rejected, and why.

## D1. Classic ML (TF-IDF + K-Means) instead of an LLM for v1

| Option | Pros | Cons |
|---|---|---|
| **TF-IDF + LSA + K-Means (chosen)** | Free, runs offline in seconds, same input gives the same output, every theme explainable by its top terms, no user text sent to a third party | Misses synonyms and sarcasm |
| LLM API to label each review | Understands nuance; fluent theme names | Cost per review; results vary between runs; privacy review needed; harder to explain |
| Sentence embeddings + clustering | Better semantic grouping | Large model download; slower; less explainable |

**Decision:** Classic ML for v1. It reached ARI 0.98 on the labelled sample, which is good enough. Reproducibility and privacy matter more for a tool whose output is used to argue roadmap decisions.
**Revisit when:** feedback in Hinglish or other mixed languages becomes significant, or audits show themes being missed.

## D2. Star ratings as weak labels for sentiment

Nobody has time to hand-label thousands of reviews. Star ratings are noisy (people write "great app" and give 3 stars), but they are free and plentiful. A model trained on them reached 82% accuracy and **88% recall on negative feedback**. Negative recall is the number that matters, because missing a complaint costs more than mislabelling praise. The model then scores feedback that has no rating, such as tickets and surveys.

## D3. Show 8 themes by default (configurable)

Statistical scores like silhouette keep improving as themes get more granular, so they cannot choose the "right" number by themselves. Eight themes fit on one screen and in one brief, and on the labelled sample k = 8 matched the true structure best (ARI 0.98 vs 0.92 at k = 7 or 9). The dashboard has a slider and a silhouette chart so teams can choose their own granularity.

## D4. Spike threshold of 3.5σ with a Poisson noise floor

Back-test on the sample (8 themes, 6 months of complete weeks):

| Threshold | Incidents caught | False alarm weeks |
|---|---|---|
| 2.0σ | 2 / 2 (fee alert fires a month *before* the fee existed) | 5 |
| 2.5σ | 2 / 2 | 2 |
| 3.0σ | 2 / 2 | 0 |
| **3.5σ (chosen)** | **2 / 2** | **0** |
| 4.0σ | 1 / 2 (misses the fee change) | 0 |

An alerting tool that cries wolf gets muted within a month. Both 3.0σ and 3.5σ are clean here, so I chose 3.5σ for headroom: a real product has more themes and more weeks, which means more chances for a false alarm. 4.0σ is too blunt: it misses the smaller fee-change spike. The Poisson floor (std ≥ √mean) stops small, naturally noisy themes from triggering alerts.

## D5. Urgency only counts significant growth

A theme going from 40 to 52 reviews looks like +30%, but that is within normal noise. A binomial test on recent vs. prior counts (p < 0.05) decides whether growth raises urgency. This stops the backlog from reshuffling every week because of noise.

## D6. Effort is a human input

The model can estimate reach and impact from data. It cannot know that a fix needs a payments-partner integration. Effort stays editable and owned by engineering, which also gets engineering involved in prioritisation.

## D7. Synthetic data with planted incidents

Real review data cannot be shared publicly, and it has no ground truth. Generating data with two known incidents let me *prove* the detector works, with a measured delay and a measured false-alarm rate. Next, the same tests should run on a public review dataset.
