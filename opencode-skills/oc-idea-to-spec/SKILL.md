---
name: oc-idea-to-spec
description: Turns a raw software idea (app, SaaS, web tool, AI agent, bot, extension, marketplace, game) into a complete, build-ready markdown spec whose purpose is to make money. Researches the latest market, competitor, pricing, tech and legal data on the web with cited sources; interviews the user in rounds to deepen the idea; gives a blunt, evidence-based verdict on whether the idea can earn money and how to make it succeed; then writes a PRD/technical spec detailed enough for any AI coding agent or developer to build without guessing. Use this skill WHENEVER the user describes a product or software idea, says "I have an idea", asks to write a PRD, spec, product doc or build plan, asks whether an idea is good, viable or profitable, wants market or competitor analysis for an app, or wants to plan a software business — even if they never say "document" or "spec".
---

# Idea → Money-Making Spec

The end goal is not a document. The end goal is **software that makes money**. The document is the tool that gets there: it must tell the user honestly whether the idea can earn money, show the fastest path to the first paying customers, and give an AI coding agent everything it needs to build that path.

## Core principles

1. **Money is the north star.** Every phase answers: who pays, how much, why now, through which channel, how soon, at what margin. Features that don't serve acquisition, activation, payment or retention get pushed out of the MVP.
2. **Evidence before opinion.** Every market, competitor, price, tech-version and legal claim carries a source and a date. Unsourced numbers are labeled `ASSUMPTION` or `ESTIMATE` with the formula shown. The user will spend real money on this document; a confident made-up number is worse than "unknown".
3. **Honesty over comfort.** If the idea is weak, say so plainly, explain why with evidence, and propose concrete pivots. Flattery costs the user months and money.
4. **Research first, then ask.** Never make the user answer what the internet already knows. Ask only what only the user can know (goals, resources, unfair advantages, preferences), and attach a research-backed suggestion to each question.
5. **Build-ready precision.** "Fast" becomes "p95 < 300 ms". "Easy" becomes "new user completes first order in < 2 min". No unexplained TBDs.

**Language:** talk to the user in their language (Vietnamese if they write Vietnamese). Write the final document in the language they choose (ask once); keep technical terms in English.

**State:** keep all working files in `docs/<product-slug>/` so the session can resume: `research-notes.md` (findings + sources), `decisions.md` (answers, assumptions, decisions with dates). Track phases with TodoWrite if available.

---

## Phase 0 — Intake (one turn)

- Restate the idea in 2–3 sentences and confirm.
- Classify the product type (B2C app, B2B SaaS, marketplace, dev tool, AI app/agent, bot, extension, game, internal tool). Type drives questions, revenue model and scoring.
- If missing, ask these together (via AskUserQuestion if available):
  - Target market/country
  - Resources: solo or team, coding skill, budget, hours per week
  - Money goal: e.g. first $1k MRR side income, replace a salary, venture-scale startup
  - Unfair advantages: domain expertise, existing audience, customer relationships, data

The money goal sets the bar: a $3k/month solo business and a VC-scale startup need very different markets.

## Phase 1 — Research sweep

Read `references/research-playbook.md` for tools, sources, verification and note-taking rules.

Minimum findings before the interview:
- **Competitors & substitutes:** 5–10 direct/indirect, with pricing, positioning, weaknesses from real reviews, and revenue/traction signals where public. Always include the non-software substitute (spreadsheets, chat groups, hiring a person).
- **Proof of payment:** evidence that people already pay to solve this (competitor revenue, pricing pages, public MRR, job posts, agencies selling it as a service). This is the single most important finding.
- **Pain evidence:** real complaints from Reddit, Hacker News, app-store and G2/Capterra low-star reviews, forums, local communities.
- **Market size & trend:** bottom-up preferred; top-down with source and year.
- **Tech:** current stable versions, APIs/AI models and their current pricing.
- **Legal/platform risk:** data protection, payments, regulated sectors, app-store rules.

If a subagent tool (Task/Agent) exists, run branches in parallel (competitors & pricing / pain & demand / market & trend / tech & cost / legal) and have each return findings + sources.

Report to the user: the 5–8 findings that matter most for making money, each with a link. Flag any early red flag immediately (e.g. no evidence anyone pays).

## Phase 2 — Deep-dive interview (rounds)

Read `references/question-bank.md` and pick the questions with the highest impact on revenue and design.

- Ask 3–4 questions per round (AskUserQuestion supports up to 4 questions with multiple-choice options; there is always a free-text "Other").
- Prefix each with research context: "Competitor A charges $19/mo per seat, B charges per use — which fits your customers?"
- If the user is unsure, propose a sensible default, log it as an `ASSUMPTION` in `decisions.md`, and move on. Never stall.
- If an answer opens a new unknown (new competitor, channel, integration), research it right away.
- After each round, show the coverage map with ✅ / ⚠️ (assumption) / ❌.

**Coverage map** — move to Phase 3 only when every row is ✅ or ⚠️:

| Area | Required |
|---|---|
| Problem & specific paying customer (persona + who signs/pays) | yes |
| Proof people pay for this today | yes |
| Differentiation vs. competitors & substitutes | yes |
| Revenue model, price points, payment method | yes |
| First 10 customers: exact channel and plan | yes |
| MVP scope (must / later / never) and the "aha" moment | yes |
| Core user flows | yes |
| Platform(s) | yes |
| Core data entities | yes |
| External integrations (payments, auth, AI, messaging...) | yes |
| Non-functional needs (scale, security, performance, i18n) | yes |
| Constraints (budget, time, skills) | yes |
| Legal/compliance | when relevant |

Usually 2–4 rounds. If the user says "go fast", fill the rest with labeled assumptions.

## Phase 3 — Verdict & path to money

Read `references/evaluation-framework.md`. Score with evidence and present the result BEFORE writing the spec, because it may change the plan.

Deliver:
- **One-line verdict:** BUILD / BUILD WITH CHANGES / DON'T BUILD AS-IS — weighted score X.X/5.
- Scorecard (9 criteria, each with reason + source).
- Unit economics and a revenue scenario (conservative / base / optimistic) against the user's money goal.
- Top 3 risks with mitigations; the strongest moat the user can realistically build.
- **Path to money:** beachhead niche, positioning line, pricing and packaging, top 2–3 acquisition channels, a concrete plan for the first 10 and first 100 paying customers, realistic milestones.
- **Pre-build validation test** (1–2 weeks, cheap) with a pass/fail threshold — e.g. pre-sales, paid pilot, landing page + waitlist, concierge service.
- **Kill criteria:** signals that mean stop or pivot.
- If score < 3.8: 1–3 concrete pivots grounded in gaps found in research, each re-scored.

Ask: keep, adjust per recommendations, or pivot. Big changes → loop back to Phase 2 for affected areas.

## Phase 4 — Write the spec

Read `references/spec-template.md` and follow its structure. Default output: `docs/<product-slug>/spec.md`. For large products, offer a split (`01-business.md`, `02-prd.md`, `03-technical.md`, `04-roadmap.md` + `README.md` index).

Writing rules:
- Every MVP feature: ID, priority, user story, Given/When/Then acceptance criteria, edge cases, dependencies.
- **Monetization is built in, not bolted on:** pricing/paywall, checkout, billing, receipts/invoices, plan limits, failed-payment handling, and revenue analytics events are P0 in the MVP unless the validation plan deliberately uses manual payment first (then say so).
- Data model: fields, types, constraints, relations, indexes. API: method, path, auth, request/response examples, error codes.
- Tech stack: version + reason + alternative, verified as current stable in this session. Prefer boring, cheap, fast-to-ship choices for the user's skill level; include monthly cost at 100 / 1k / 10k users.
- Explicit non-goals so the AI agent does not add scope.
- Mermaid for architecture, flows and ERD.
- Unknowns go to "Open questions & assumptions" with impact and how to verify — never silent gaps.
- Every external number links to the References section with dates.

Write section by section and save as you go; don't attempt the whole document in one write.

## Phase 5 — Self-review and handoff

Re-read the whole document as (a) a developer starting tomorrow, (b) an AI coding agent with no other context, and (c) an investor or the user's own wallet. Check:

- [ ] A developer/AI can start coding without asking any blocking question.
- [ ] Every MVP feature has testable acceptance criteria; data model and APIs match the features.
- [ ] Payment flow, pricing and revenue tracking are fully specified.
- [ ] Every number has a source or an `ASSUMPTION`/`ESTIMATE` label; versions and prices were checked this session.
- [ ] Verdict, risks, kill criteria and validation test are present and consistent with the scorecard.
- [ ] Milestones have estimates and done-criteria; the first revenue milestone is explicit.
- [ ] The "Instructions for AI coding agents" section is complete.
- [ ] No contradictions between sections (pricing, scope, stack, persona).

Fix what fails. Then give the user: file path(s), a 5-line summary, the verdict, the assumptions they must confirm, and the next 3 actions (usually: run the validation test → build M0 → get first paying customer).

---

## Modes

- **Fast mode** ("go fast", detailed brief already given): one research sweep + one round of ≤4 questions, then verdict and spec with labeled assumptions. Never skip the verdict — it's the most valuable part.
- **Verdict only** ("is this idea good?"): Phases 0, 1, 3 → `docs/<slug>/evaluation.md`; then offer to continue to a full spec.
- **Update existing doc:** read it, compare against the coverage map and template, re-research data older than ~6 months, ask only about gaps, and keep a changelog in Metadata.

## When web access is unavailable

Tell the user plainly. Continue with built-in knowledge, but mark every market, price and version claim `UNVERIFIED — may be outdated`, and list what to check before spending money.
