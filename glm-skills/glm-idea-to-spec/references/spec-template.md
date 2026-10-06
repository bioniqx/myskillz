# Spec Template

Use this structure. Replace every `[...]` with real content. If a section doesn't apply, write "Not applicable — [reason]" instead of deleting it, so readers know it was considered. Mark unsourced figures `ASSUMPTION` or `ESTIMATE`.

## Contents
0 Metadata · 1 Executive summary · 2 Market & evidence · 3 Verdict & path to money · 4 Customers · 5 Scope · 6 Functional requirements · 7 Monetization & billing spec · 8 Flows & UX · 9 Non-functional requirements · 10 Architecture & stack · 11 Data model · 12 API · 13 Integrations · 14 Security, privacy & legal · 15 Analytics & metrics · 16 Go-to-market · 17 Roadmap · 18 Risks · 19 Instructions for AI coding agents · 20 Open questions & assumptions · 21 References

---

```markdown
# [Product name] — Product & Technical Specification

## 0. Metadata
| | |
|---|---|
| Version | 1.0 |
| Date | YYYY-MM-DD |
| Status | Draft / Approved |
| Authors | [User] + Claude |
| Research date | YYYY-MM-DD |
| Changelog | v1.0 — initial |

## 1. Executive summary
- **One-liner:** [Product] helps [who] [do what] by [how], unlike [alternative] because [edge].
- **Problem:** …
- **Solution:** …
- **Paying customer:** …
- **Revenue model & price:** …
- **Verdict:** [BUILD / BUILD WITH CHANGES] — X.X/5
- **Money targets:** first payment by [date]; [N] paying customers / $[X] MRR by month 3, 6, 12

## 2. Market & evidence
### 2.1 Problem evidence (quotes/links from reviews, forums; data)
### 2.2 Proof people pay (competitor revenue, pricing, manual services)
### 2.3 Market size (bottom-up formula + top-down reference, sourced)
### 2.4 Competitors & substitutes
| Name | Type | Price | Strengths | Weaknesses | Traction | Source |
### 2.5 Gap & positioning

## 3. Verdict & path to money
[Scorecard, revenue scenarios, unit economics, risks, beachhead, pricing, channels, first-10/first-100 plan, validation test, kill criteria — from evaluation-framework.md]

## 4. Customers
### 4.1 Personas (1–3): role, context, goal, pain, current tools, budget, who pays/approves
### 4.2 Jobs-to-be-done: "When [situation], I want to [motivation], so I can [outcome]."

## 5. Scope
### 5.1 Goals (measurable)
### 5.2 Non-goals (explicit — the AI agent must not build these)
### 5.3 Feature priority
| ID | Feature | Priority (P0/P1/P2) | Release | Revenue role (acquire/activate/monetize/retain) | Reason |

## 6. Functional requirements
### F-01: [Feature name] (P0)
- **Description:** …
- **User story:** As a [persona], I want to [action] so that [benefit].
- **Acceptance criteria:**
  - Given [context], When [action], Then [specific, testable result]
- **Edge cases & errors:** …
- **Dependencies:** F-xx, API, data
- **Plan gating:** which plans can use it, limits

## 7. Monetization & billing spec
- Plans table: name, price (currency, monthly/annual), limits, features
- Trial/freemium rules and conversion trigger (paywall moments)
- Payment provider(s) and why; hosted checkout to avoid handling card data
- Flows: upgrade, downgrade, cancel, refund, failed payment/dunning, receipts/invoices, tax/VAT handling
- Entitlement checks: where and how plan limits are enforced (server-side)
- Webhooks to handle and idempotency
- If manual payment for early customers: process and how it maps to accounts

## 8. Flows & UX
### 8.1 Main flows (Mermaid flowchart): signup → aha → pay → repeat use
### 8.2 Screens
| Screen | Purpose | Key components | States (loading/empty/error/paywall) |
### 8.3 UI principles: language(s), responsive, accessibility, design system

## 9. Non-functional requirements
| Type | Requirement |
|---|---|
| Performance | e.g. p95 API < 300 ms; page load < 2 s on 4G |
| Scale | users/records in year 1 and 2 |
| Availability | uptime %, backups, RPO/RTO |
| Security | … |
| i18n / time zone / currency | … |
| Supported browsers/devices | … |

## 10. Architecture & stack
### 10.1 Architecture diagram (Mermaid)
### 10.2 Stack
| Layer | Choice | Version (verified YYYY-MM-DD) | Why | Alternative |
### 10.3 Hosting & monthly cost at 100 / 1k / 10k users
### 10.4 Repository structure

## 11. Data model
### 11.1 ERD (Mermaid erDiagram)
### 11.2 Tables/collections
#### `users`
| Field | Type | Constraints | Description |
|---|---|---|---|
| id | uuid | PK | |
Indexes, relations, delete rules (soft/hard), data retention.

## 12. API
Conventions: base URL, auth, error format, pagination, versioning, rate limits.
### `POST /api/v1/[resource]`
- Purpose · Auth · Request (JSON example) · Response 200 (JSON example) · Errors (code + meaning)

## 13. Integrations
| Service | Purpose | Plan/price (source, date) | Limits/notes |

## 14. Security, privacy & legal
- Authentication, authorization (role × permission matrix)
- Sensitive data, encryption at rest/in transit, secrets management
- Applicable laws/regulations and concrete obligations (consent, data-subject rights, cross-border transfer, impact assessment)
- Required documents: Terms of Service, Privacy Policy, refund policy

## 15. Analytics & metrics
- North Star Metric: …
| Metric | Definition | Target M3 | Target M12 | Event(s) tracked |
- Funnel events: visit → signup → activation (aha) → trial → paid → retained month 2
- Revenue metrics: MRR, ARPU, churn, LTV, CAC per channel

## 16. Go-to-market
- Beachhead, positioning, messaging
- Validation test (before/alongside build) with pass threshold
- First 10 → 100 → 1,000 paying customers: channel, tactic, budget
- Launch checklist

## 17. Roadmap
| Milestone | Content | Features (F-xx) | Estimate | Done when |
|---|---|---|---|---|
| M0 | Project setup, CI/CD, auth, deploy | | | |
| M1 | Core value (aha) | | | |
| M2 | Payments + paywall + analytics → first paying customer | | | |
| M3 | Retention & growth features | | | |

## 18. Risks
| Risk | Likelihood | Impact | Mitigation | Kill/pivot trigger |

## 19. Instructions for AI coding agents
- Build order (M0 → F-01 → …) and why
- Code conventions: language, style guide, naming, folder structure
- Testing: types, minimum coverage, how to run
- Required environment variables (`.env.example`), never commit secrets
- Definition of Done per feature: meets acceptance criteria + tests pass + lint clean + deployed to staging
- Do NOT: add features outside scope, change the stack, or store card data without asking
- When the spec is ambiguous: follow the stated assumption in section 20; if none, ask before building

## 20. Open questions & assumptions
| # | Assumption / question | Impact if wrong | How to verify | Owner | Deadline |

## 21. References
1. [Title](URL) — published YYYY-MM, accessed YYYY-MM-DD
```
