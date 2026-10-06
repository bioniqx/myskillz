# Research Playbook

Goal: gather current, trustworthy, citable evidence that answers one question above all — **will someone pay for this, and how much?**

## Contents
1. Tools · 2. Always date your queries · 3. Sources by question · 4. Proof-of-payment hunt · 5. Verification rules · 6. Notes format · 7. Competitor table · 8. When to stop

## 1. Tools (use whatever is available)

- `WebSearch` to find, `WebFetch` to read full pages. Snippets are often truncated or stale — fetch any page you will cite.
- Search/scrape MCP servers if installed (e.g. Exa, Brave, Perplexity, Tavily, Firecrawl) — prefer them for deep research.
- Domain MCPs if installed: GitHub (competitor repos, library popularity), academic search (health/science products), finance data.
- Subagents (Task/Agent tool): split research into parallel branches; each returns findings + source list.

## 2. Always date your queries

Check today's date first (`date` or context). Put the current year in queries: "X pricing 2026", "best X tools 2026", "X market size 2026". Undated queries surface stale content.

## 3. Sources by question

| Question | Preferred sources |
|---|---|
| Who competes? | Product Hunt, G2, Capterra, AlternativeTo, SaaSHub, App Store / Google Play, Chrome Web Store, GitHub, Crunchbase, YC company directory |
| What do they charge? | Competitors' own pricing pages (fetch them), Wayback Machine for price history |
| Real pain? | Reddit (industry subreddits, r/SaaS, r/Entrepreneur, r/smallbusiness), Hacker News, 1–3 star reviews on stores/G2, X/Twitter, Facebook groups, niche forums, Indie Hackers |
| Demand trend | Google Trends, Exploding Topics, search-volume tools if available, Product Hunt monthly top |
| Market size | Government statistics offices, World Bank, public-company annual reports (SEC 10-K), public summaries from Gartner/IDC/McKinsey/Statista (say if only a summary was seen) |
| Vietnam market | GSO (General Statistics Office), Ministry of Industry and Trade e-commerce reports, e-Conomy SEA (Google–Temasek–Bain), Decision Lab, Q&Me, Metric.vn, VnExpress/CafeF for news |
| Traction & revenue of others | Indie Hackers, Starter Story, open-startup dashboards (public MRR), founder interviews, Sensor Tower/AppMagic estimates, Similarweb traffic estimates |
| Tech & API cost | Official docs, changelogs, official pricing pages, GitHub releases, npm/PyPI latest versions |
| Legal | Primary legal texts and regulator guidance (e.g. thuvienphapluat.vn / luatvietnam.vn for Vietnam; official GDPR, CCPA texts); law-firm summaries as secondary |
| Platform rules | Apple App Store Review Guidelines, Google Play policies, payment-provider terms — fetch current versions |

## 4. Proof-of-payment hunt (do this every time)

Look for at least three of:
- Competitors with public paid plans and signs of customers (reviews, case studies, logos).
- Public revenue/MRR numbers or credible estimates.
- People hiring freelancers/agencies to do this manually (Upwork, Fiverr, local job boards) — strong signal.
- Posts like "I'd pay for…", "is there a tool that…" with engagement.
- Spending in adjacent tools the product would replace.

If none found, report it as a red flag, not a neutral fact.

## 5. Verification rules

- Key numbers (market size, prices, user counts, revenue): ≥ 2 independent sources, or 1 primary/official source. If sources conflict, give the range and both sources.
- Prefer primary sources over aggregators and SEO listicles.
- Check publication date. Tech, pricing and AI-model data older than ~12 months: re-verify. Market data older than ~2 years: flag as dated.
- Be skeptical of: "Top 10" lists written by a competitor, round market-size numbers with no methodology, statistics that cite each other in a circle.
- Rules of thumb (e.g. LTV/CAC ≥ 3, SaaS gross margin 70%+) are heuristics — label them as such, never as laws.
- No data → say "no reliable data found". Offer a bottom-up estimate with the formula and assumptions.

## 6. Notes format (`research-notes.md`)

```markdown
## [Topic]
- Finding: ...
- Money relevance: why this matters for revenue
- Source: [Title](URL) — published YYYY-MM, accessed YYYY-MM-DD
- Confidence: High / Medium / Low — why
```

## 7. Competitor table

| Name | Direct/indirect | Target customer | Price | Key strengths | Weaknesses (from reviews) | Traction/revenue signal | Source |
|---|---|---|---|---|---|---|---|

Always include a "Doing it without software" row (spreadsheet, chat group, paper, hiring someone). That is often the real competitor.

## 8. When to stop

Stop a research branch when new searches keep returning the same players and numbers, or when the remaining uncertainty can only be resolved by talking to customers (then turn it into a validation test). Don't burn the user's time on research that won't change a decision.
