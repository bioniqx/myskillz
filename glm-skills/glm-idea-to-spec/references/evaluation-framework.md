# Evaluation Framework

Score on evidence, not enthusiasm. Every score needs a reason and, where possible, a source. Never inflate scores to please the user — the purpose is to protect their time and money.

## 1. Scorecard (1–5 per criterion)

| # | Criterion | Weight | 1 = | 5 = |
|---|---|---|---|---|
| 1 | Pain intensity | 15% | Nice-to-have, rare | Frequent, costly pain; people already hack together workarounds |
| 2 | Willingness to pay (proof) | 20% | No one pays for anything similar | Competitors earn clear revenue; buyers have budget; manual services exist |
| 3 | Reachability of buyers | 15% | No clear channel, expensive acquisition | Cheap, concrete channel; founder already has access/audience |
| 4 | Differentiation & competition | 10% | Saturated, no edge; free incumbent | Clear gap or strong edge that is hard to copy |
| 5 | Unit economics | 10% | Variable costs eat the margin; low price, high churn | High gross margin, healthy LTV/CAC (heuristic ≥ 3) |
| 6 | Time to first revenue | 10% | > 6 months, needs heavy build or regulation first | Can charge within weeks (pre-sale, pilot, simple MVP) |
| 7 | Market size vs. money goal | 10% | Too small for the user's goal, or shrinking | Comfortably fits the goal and is growing |
| 8 | Feasibility for this founder | 5% | Needs skills/capital the founder lacks | Buildable with current skills, tools and budget |
| 9 | Timing & platform risk | 5% | Too early/late; one platform can kill it | Recent shift opens a window; low dependency risk |

Weighted score = Σ(score × weight), on a 5-point scale.

**Verdict:**
- ≥ 3.8 → **BUILD** — focus on execution and the first customers.
- 3.0–3.7 → **BUILD WITH CHANGES** — name the weak criteria and exactly how to fix them.
- < 3.0 → **DON'T BUILD AS-IS** — propose pivots.
- **Red flag override:** if criterion 2 (willingness to pay) or 3 (reachability) ≤ 2, the verdict cannot be BUILD regardless of total. No payer or no path to payers means no business.

Adjust weights to the money goal and state the change: venture-scale → raise #7; fast side income → raise #6 and #3.

## 2. Revenue model

Prefer bottom-up because it can be checked:

```
New paying customers per month = reachable prospects per month (named channel) × conversion rate
Active customers(m) = Active customers(m−1) × (1 − monthly churn) + new customers(m)
MRR(m) = Active customers(m) × ARPU
Year-1 revenue = Σ MRR(m) for m = 1..12   (NOT month-12 MRR × 12 — that overstates a ramp)
```

Show three scenarios (conservative / base / optimistic) with every assumption labeled. Compare against the user's money goal: "Base case reaches $X MRR in month 12 vs. your goal of $Y." Put top-down TAM/SAM from reports beside it for reference only.

Use conversion and churn benchmarks only with a cited source; otherwise label them as assumptions and pick conservative values.

## 3. Unit economics (estimate, labeled)

- ARPU per month
- Variable cost per customer per month: AI/API usage, hosting, payment fees, app-store commission, SMS/email, support time
- Gross margin = (ARPU − variable cost) / ARPU
- CAC by channel (ads, content, outbound, partnerships)
- Monthly churn → lifetime ≈ 1 / churn
- LTV ≈ ARPU × gross margin × lifetime
- LTV/CAC and CAC payback months
- Break-even: monthly fixed costs ÷ (ARPU × gross margin) = customers needed

For AI products, compute token cost for a heavy user, not an average one — heavy users kill margins.

## 4. Risks (pick the top 3)

Market (no need) · Distribution (can't reach buyers) · Competition (big player ships it free) · Platform dependency (API/app store/policy change) · Technical · Legal/compliance · Operating cost · Founder bandwidth.

Each: likelihood (L/M/H) × impact (L/M/H) × concrete mitigation.

## 5. Path to money (always required)

- **Beachhead:** the narrowest segment that is easiest to win and pays fastest.
- **Positioning line:** "For [who] who [pain], [product] is the [category] that [key benefit], unlike [alternative]."
- **Pricing & packaging:** tiers, price points, trial/freemium decision with reason, annual discount, anchor against competitors. Default to charging from day one unless a strong network effect requires free usage.
- **Channels:** top 2–3 ranked by cost and speed, matched to where the beachhead already gathers.
- **First 10 paying customers:** a concrete, named plan (which communities, which outreach message, which offer).
- **First 100:** what repeatable channel takes over.
- **Moat to build over time:** data, workflow lock-in, integrations, community, niche brand.
- **Milestones:** week 2 (validation result), month 1–3 (MVP + first payment), month 6, month 12 — each with a metric (paying customers, MRR, churn).

## 6. Pre-build validation test

Design the cheapest test that produces a money signal within 1–2 weeks. Options, strongest first:
1. Pre-sale or paid pilot (money changes hands)
2. Deposit / letter of intent (B2B)
3. Concierge/manual service delivered by hand, charged
4. Landing page with price shown + "buy/reserve" button + small ad or community traffic
5. 10–20 customer interviews (weakest; opinions ≠ payments)

State pass/fail thresholds in advance (e.g. "≥ 3 pre-sales at full price from 30 conversations" or "≥ 5% of visitors click Buy at the shown price"). Mark thresholds as judgment calls, not industry standards, unless sourced.

## 7. Kill criteria

Define in advance what ends or pivots the project, e.g. validation test fails twice with different messaging; CAC > 1/3 of first-year revenue per customer after testing two channels; no paying customer after N months of active selling.

## 8. Pivot options (if score < 3.8)

Offer 1–3 concrete pivots drawn from gaps found in research — change of customer segment, of problem, of business model (e.g. software → done-for-you service first), or of channel. Re-score each briefly.

## 9. Presentation template

```markdown
## Verdict: [Product]
**[BUILD / BUILD WITH CHANGES / DON'T BUILD AS-IS] — X.X/5**
One-sentence why.

| Criterion | Score | Evidence (source) |
|---|---|---|

**Revenue scenarios (month 12 MRR):** conservative $A · base $B · optimistic $C vs. goal $G
**Unit economics:** ARPU · gross margin · CAC · LTV/CAC (estimates)
**Top risks:** 1… 2… 3…
**Path to money:** beachhead · price · channels · first-10 plan
**Validate first (14 days):** test + pass threshold
**Kill criteria:** …
```
