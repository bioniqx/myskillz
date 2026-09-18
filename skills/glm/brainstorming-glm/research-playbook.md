# Research Playbook — fast, current, verified evidence

Read when a decision needs more than 3 web lanes, when sources conflict,
or when the user asks for the latest or best method. SKILL.md's R10 and
the web-lane prompt still apply; this file adds the how.

## 1. Research or skip (5 seconds)

Research when the recommendation depends on any of:

- choosing or upgrading a library, framework, runtime, database, cloud
  service, or model/API;
- how an external API or SDK behaves at a specific version;
- security, auth, crypto, privacy, or compliance practice;
- performance, scaling, or cost techniques and limits;
- a standard or spec (HTTP, OAuth, WCAG, SQL dialect, file formats);
- the user asking for "best", "latest", "modern", or "recommended".

Skip when the answer lives in the repo (internal logic, conventions), the
user said offline, or the question is pure product preference. If a
thorough multi-source report is itself the deliverable, suggest the user
run a deep-research command in parallel.

## 2. Query design

- Decompose the decision into 2-6 precise questions before searching.
  Each becomes one direct query group or one web lane.
- Run 2-4 variants per question in parallel: official phrasing, the error
  or API name, "[tech] [version] changelog", "[tech] vs [alt] [year]".
- Two batches, not a chain. Batch 1 = all searches in parallel; batch 2 =
  all fetches of the best primary URLs in parallel; batch 3 only for
  conflicts. Start broad and short, then narrow.
- Pin to the versions in Live context AND query the latest release notes.
  Report the gap: breaking changes, deprecations, new built-ins.
- Target primary sources directly when you know them: the docs domain,
  GitHub releases and issues, the RFC editor, vendor status and pricing
  pages.
- Prefer fetch-friendly endpoints over HTML repo pages — raw README
  (`raw.githubusercontent.com/<org>/<repo>/HEAD/README.md`) and package
  registries (`pypi.org/pypi/<pkg>/json`,
  `registry.npmjs.org/<pkg>/latest`, `proxy.golang.org/<module>/@latest`,
  `crates.io/api/v1/crates/<name>`) give latest version and release date
  in one call.
- Web content only via WebSearch/WebFetch. A failed or denied fetch is
  never retried the same way, and never re-attempted through curl, gh, or
  scripts — switch to another source in the next parallel batch.
- WebFetch prompts ask for extraction, not summary: "Quote verbatim the
  deprecation notice and its date", "List the version each option was
  added in".

## 3. Source tiers

| Tier | Examples | Use |
| --- | --- | --- |
| A | Official docs, changelogs and release notes, specs and RFCs, maintainer repos and issue threads, security advisories, peer-reviewed papers | Can carry a load-bearing claim alone |
| B | Maintainer or company engineering blogs, conference talks, benchmarks with published methodology, reputable preprints | Two independent B's equal one A |
| C | Stack Overflow, Reddit, HN, Discord, personal blogs | Leads and pitfall signals only |
| Reject | Undated pages, SEO and listicle farms, AI-generated roundups, content scraped from docs | Never cite |

Agents drift toward SEO content over authoritative sources unless told
otherwise. The tier rule in every web-lane prompt is what prevents it,
and Flash lanes need it stated explicitly, not implied.

## 4. Recency and version fit

- Every claim carries a date (published or last updated) and the version
  it applies to.
- Fast-moving tech (JS frameworks, AI SDKs and models, cloud services):
  treat anything over 18 months as stale unless a newer A source confirms
  it.
- Slow-moving (SQL semantics, POSIX, HTTP, crypto primitives): age
  matters less, spec version matters more.
- A newer A source beats an older A source. An A source for our version
  beats a newer source for a version we do not run — note the upgrade
  path.

## 5. Verification without slowing down

- Cited links often resolve while the page does not support the claim,
  and accuracy degrades as tool calls pile up. So verify load-bearing
  claims only — the ones that would flip the recommendation. Typically
  2-5 per design.
- A load-bearing claim needs 1 A source or 2 independent B sources, each
  with a verbatim quote of 25 words or less.
- Conflicts: prefer A over B, newer over older, our version over others.
  If still unresolved, present both readings as a trade-off, not a
  confident answer.
- On architectural designs the claim-verifier lane runs while the user
  reads the design (`architectural.md` §3), so verification adds no wait.

## 6. Budgets and stopping

| Question type | Direct calls | Lane budget |
| --- | --- | --- |
| Single fact or API detail | 1-3 | none, or 1 Flash lane at ≤4 calls |
| Comparison of 2-4 options | 4-8 searches + 2-6 fetches, two parallel batches | 0-2 Flash lanes at ≤5 calls each, only for multi-hop angles |
| Broad landscape or new domain | 4-8 | 4-16 Flash lanes at ≤5 calls each |

Promote one lane to GLM-5.3 only when the comparison is contested and its
outcome picks the approach.

Stop a lane when two consecutive searches add no new facts, when the
question is answered with adequate support, or when the budget is spent.
Report UNVERIFIED rather than digging for sources that may not exist.

## 7. Privacy

Queries leave the machine. Use generic technical terms ("Next.js 15 app
router middleware auth pattern"), never proprietary code, file contents,
internal project or customer names, hostnames, keys, or data samples. If
a question cannot be asked without them, make it an assumption or ask the
user.

## 8. How evidence reaches the user

Inside the design, not as a research report:

```
Evidence (checked YYYY-MM-DD)
- <claim that drives the choice> — [<source title>](<url>) (<YYYY-MM>)
- <our version vs latest: what changes> — [<release notes>](<url>) (<YYYY-MM>)
- UNVERIFIED: <claim> — only a tier-C source
```

Evidence lines are short; trade-offs cite them by content. Unverified
items appear as assumptions the user can veto.
