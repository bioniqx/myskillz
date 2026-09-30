# Research Playbook — fast, current, verified evidence

Read when a decision needs more than 3 web lanes, when sources conflict,
or when the user asks for the latest/best method. SKILL.md's rules and
web-lane prompt still apply; this file adds the how.

## 1. Research or skip (5 seconds)

Research when the recommendation depends on any of:
- choosing or upgrading a library, framework, runtime, database, cloud
  service, or model/API;
- how an external API/SDK behaves at a specific version;
- security, auth, crypto, privacy, or compliance practice;
- performance, scaling, or cost techniques and limits;
- a standard/spec (HTTP, OAuth, WCAG, SQL dialect, file formats);
- the user asking for "best", "latest", "modern", "recommended".

Skip when the answer lives in the repo (internal logic, conventions),
the user said offline/no web, or the question is pure product preference.
If a thorough multi-source report is itself the deliverable, suggest the
user run Claude Code's built-in `/deep-research <question>` in parallel.

## 2. Query design

- Decompose the decision into 2-6 precise questions before searching;
  each becomes a T0 query group or one web lane.
- Run 2-4 variants per question in parallel: official phrasing, error or
  API name, "[tech] [version] changelog", "[tech] vs [alt] [year]".
- Two batches, not a chain: batch 1 = all searches in parallel; batch 2 =
  all fetches of the best primary URLs in parallel; batch 3 only for
  conflicts. Start broad and short, then narrow.
- Pin to versions from Live context; ALSO query the latest release notes.
  Report the gap (breaking changes, deprecations, new built-ins).
- Target primary sources directly when you know them: docs domain,
  GitHub releases/issues, RFC editor, vendor status/pricing pages.
- Prefer fetch-friendly endpoints over HTML repo pages: raw README
  (`raw.githubusercontent.com/<org>/<repo>/HEAD/README.md`), package
  registries (`pypi.org/pypi/<pkg>/json`, `registry.npmjs.org/<pkg>/latest`,
  `proxy.golang.org/<module>/@latest`, `crates.io/api/v1/crates/<name>`)
  for latest version and release dates in one call.
- Web content only via WebSearch/WebFetch. A failed or denied fetch is
  never retried the same way (and never re-attempted through curl, gh, or
  scripts) — switch to another source in the next parallel batch.
- WebFetch prompts ask for extraction, not summary: "Quote verbatim the
  deprecation notice and its date", "List the version each option was
  added in".

## 3. Source tiers

| Tier | Examples | Use |
| --- | --- | --- |
| A | Official docs, changelogs/release notes, specs/RFCs, maintainer repos and issue threads, security advisories, peer-reviewed papers | Can carry a load-bearing claim alone |
| B | Maintainer/company engineering blogs, conference talks, benchmarks with published methodology, reputable preprints | Two independent B's = one A |
| C | Stack Overflow, Reddit, HN, Discord, personal blogs | Leads and pitfall signals only |
| Reject | Undated pages, SEO/listicle farms, AI-generated roundups, content scraped from docs | Never cite |

Agents drift toward SEO content over authoritative sources unless told
otherwise — the tier rule in every web-lane prompt is what prevents it.

## 4. Recency and version fit

- Every claim carries a date (published or last updated) and the version
  it applies to.
- Fast-moving tech (JS frameworks, AI SDKs/models, cloud services): treat
  >18 months as stale unless a newer A source confirms it.
- Slow-moving (SQL semantics, POSIX, HTTP, crypto primitives): age
  matters less; spec version matters more.
- A newer A source beats an older A source; an A source for our version
  beats a newer source for a version we don't run (note the upgrade path).

## 5. Verification (quality without slowing down)

- Deep-research systems often cite links that work while the claim isn't
  actually supported by the page, and accuracy degrades as tool calls
  pile up. So verify **load-bearing claims only** — those that would flip
  the recommendation — typically 2-5 per design.
- Load-bearing claim = 1 A source or 2 independent B sources, each with a
  ≤25-word verbatim quote.
- Conflicts: prefer A over B, newer over older, our version over others;
  if still unresolved, present both readings as a trade-off, not a
  confident answer.
- Architectural designs: the claim-verifier lane runs while the user
  reads the design (`architectural.md` §4) — zero added wait.

## 6. Budgets and stopping

| Question type | T0 calls | Web lane budget |
| --- | --- | --- |
| Single fact / API detail | 1-3 | none (T0) or 1 `haiku` lane, ≤4 calls |
| Comparison of 2-4 options | 4-8 searches + 2-6 fetches (two parallel batches) | 0-2 `sonnet` lanes, ≤6 calls each, only for multi-hop angles |
| Broad landscape / new domain | 4-8 | 4-16 `sonnet` lanes, ≤6 calls each |

Stop a lane when two consecutive searches add no new facts, the question
is answered with adequate support, or the budget is spent — report
UNVERIFIED rather than digging for sources that may not exist.

## 7. Privacy

Queries leave the machine. Use generic technical terms ("Next.js 15 app
router middleware auth pattern"), never proprietary code, file contents,
internal project/customer names, hostnames, keys, or data samples. If a
question can't be asked without them, make it an assumption or ask the
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
