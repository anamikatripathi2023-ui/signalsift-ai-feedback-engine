# Discovery plan

Before building, I wrote down what had to be true for SignalSift to be worth building, and how to test each assumption cheaply.

## Riskiest assumptions

| # | Assumption | Type | How to test | Signal that it's true |
|---|---|---|---|---|
| A1 | PMs spend meaningful time (2+ hrs/week) on feedback triage | Value | 5–8 PM interviews; ask them to walk through last week | Most describe a manual, recurring process |
| A2 | Regressions reach reviews before internal dashboards catch them | Value | Review past incident post-mortems; compare review timestamps with detection time | At least one incident visible in reviews first |
| A3 | Unsupervised themes are readable enough to act on | Usability | Show 8 auto-named themes to PMs; ask them to label each | ≥ 6 of 8 labelled correctly without help |
| A4 | Teams will trust a ranking if the inputs are visible | Usability | Show ranked backlog with and without inputs; ask which they would bring to planning | Strong preference for visible inputs |
| A5 | Star ratings are good enough labels for sentiment | Feasibility | Train and evaluate on held-out data | Negative recall ≥ 80% |
| A6 | Classic ML is accurate enough; no paid LLM API needed for v1 | Feasibility / cost | Measure ARI against a labelled sample | ARI ≥ 0.8 |

A5 and A6 were tested in this prototype (negative recall 88%, ARI 0.98 on the sample). A1 to A4 need conversations with real users. The guide below is ready for that.

## Interview guide (30 minutes)

**Warm-up**
1. Tell me about your role and the product you own.

**Current behaviour (A1, A2)**
2. Walk me through the last time you looked at user feedback. Where was it? What did you do with it?
3. How long did that take? How often do you do it?
4. Tell me about the last time something broke in production. How did you first hear about it?

**Decision-making (A4)**
5. Think of the last roadmap debate you were in. What evidence won the argument?
6. When someone says "users are complaining about X", how do you decide whether it is real?

**Reaction to prototype (A3, A4)**
7. *(Show the theme list.)* What would you call each of these? What's missing?
8. *(Show the backlog.)* Would you bring this to planning? What would you change?

**Wrap-up**
9. If this disappeared tomorrow, what would you miss?

Rules: ask about past behaviour, not hypotheticals. Do not pitch. Note exact quotes.

## Competitive landscape

| Option | Strength | Gap SignalSift fills |
|---|---|---|
| Reading reviews manually | Deep context | Doesn't scale; anecdote-driven |
| Store consoles (Play / App Store) | Free, built in | Star averages only; no themes, no spike alerts, no prioritisation |
| Enterprise VoC suites | Powerful, many connectors | Expensive and slow to set up; rankings are often opaque |
| Ask an LLM chatbot to summarise | Fast, fluent | Not reproducible; no trend or spike tracking; no evidence trail |

**Positioning:** a transparent, reproducible triage engine that a PM can run in a minute and defend in a meeting.
