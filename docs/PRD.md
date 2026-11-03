# PRD: SignalSift, AI Voice-of-Customer Engine

| | |
|---|---|
| **Status** | v1 built (prototype) |
| **Product area** | Internal tooling for product, engineering and support teams |
| **Example customer** | FreshKart (fictional 10-minute grocery app, ~2M monthly active users, India) |

## 1. Problem

FreshKart receives about 500 app reviews a month, plus support tickets and survey comments. Today:

- A PM skims a sample once a week. Most feedback is never read.
- Prioritisation is anecdotal. The most recent or most senior complaint wins.
- Regressions are found late. When app v4.2 broke UPI payments on Android, nobody connected the rising one-star reviews to the release for days. Every one of those days cost failed orders and trust.

**Problem statement:** PMs cannot turn high-volume unstructured feedback into prioritised, evidence-backed decisions fast enough to catch regressions or defend roadmap choices.

## 2. Users and jobs to be done

| Persona | Job to be done | Today's workaround |
|---|---|---|
| **Priya, Product Manager** | "When I plan the quarter, I want to know which user problems are biggest and growing, so I can defend my roadmap with evidence." | Reads 50 reviews, builds a spreadsheet by hand |
| **Arjun, Engineering Manager** | "When we ship a release, I want to know within days if it broke something users care about." | Crash dashboards (misses non-crash bugs like failed payments) |
| **Meera, Support Lead** | "When a complaint repeats, I want it to become a tracked product issue, not 200 separate tickets." | Escalation emails |

## 3. Goals and non-goals

**Goals**
1. Cut the time from an issue starting to the team knowing about it to **under 7 days**.
2. Give every roadmap item a **quantified evidence trail**: volume, sentiment, reach and trend.
3. Make the ranking **transparent and editable**, not a black box.

**Non-goals (v1)**
- Replacing user interviews. SignalSift says *what* and *how much*; interviews explain *why*.
- Responding to users or auto-creating tickets.
- Real-time streaming. Daily or weekly batch is enough for the job.

## 4. User stories

| # | As a… | I want to… | So that… | Priority |
|---|---|---|---|---|
| 1 | PM | upload a CSV of feedback and see themes in under a minute | I can start without setup or labelling | P0 |
| 2 | PM | see each theme's volume, % negative and trend | I know what is big and what is getting worse | P0 |
| 3 | Eng manager | get an alert when a theme spikes, with the affected segment | I can link it to a release and roll back | P0 |
| 4 | PM | get a ranked backlog with the scoring inputs visible | I can defend and adjust the ranking | P0 |
| 5 | PM | edit effort estimates and see the ranking update | engineering input is reflected | P1 |
| 6 | PM | download a written brief | I can share it in the weekly update | P1 |
| 7 | Support lead | paste one complaint and see its theme | I can tag tickets consistently | P2 |

## 5. Requirements

**P0 (must have for v1)**
- Accept CSV with `date` and `text`. Validate it and show a clear error for missing columns.
- Sentiment for every row, including rows with no rating.
- Unsupervised themes with human-readable names.
- Weekly spike detection with a false-alarm rate low enough that people trust it.
- RICE-based ranked backlog with every input shown.

**P1 (should have)**
- Segment lift (platform, app version, city tier).
- Editable effort, plus a downloadable Markdown brief.
- Model quality shown in the product (accuracy, ARI) so users know how far to trust it.

**P2 (nice to have / later)**
- Hindi and Hinglish support.
- Direct connectors (Play Store, App Store, Zendesk) instead of CSV.
- Slack or email alert delivery.

## 6. Success metrics

| Type | Metric | Target |
|---|---|---|
| **North star** | Median days from issue onset to team awareness | < 7 days (baseline: unknown, est. 2–3 weeks) |
| Adoption | Weekly active PMs / EMs using the dashboard or brief | 60% of product teams within one quarter |
| Quality | Alert precision (alerts confirmed as real issues) | ≥ 80% |
| Quality | Theme accuracy on a 200-review labelled audit | ARI ≥ 0.8 |
| Impact | Roadmap items citing SignalSift evidence | ≥ 50% of new items |
| Guardrail | Time a PM spends on feedback triage per week | Goes down, not up |

## 7. Risks and mitigations

| Risk | Mitigation |
|---|---|
| Alert fatigue causes people to ignore it | 3.5σ threshold back-tested to zero false alarms; Poisson noise floor |
| "Black box" ranking is not trusted | Every RICE input shown and editable; method section in every brief |
| Reviews are biased toward angry users | Reach labelled as an estimate; next step joins with product analytics |
| Personal data in feedback text | Strip names, phones and emails before storage (v1.1); no raw text leaves the team's environment |
| Model drift as the product changes | Show model metrics in the UI; retrain on each run |

## 8. Launch plan (summary)

Dogfood with one product team → beta with three teams → general availability. Full detail in [Metrics & launch plan](METRICS_AND_LAUNCH.md).

## 9. Open questions

1. Should alerts go to the owning team automatically? That needs a theme-to-team mapping.
2. What is the right refresh cadence: daily for incidents, weekly for roadmap?
3. Can we get consent to join review text with account-level product events?
