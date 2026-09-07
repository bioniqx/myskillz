---
name: git-diff-summary
description: Use when the user wants to understand or summarize what the current branch changed versus the main branch — describing what the new code does, drafting a commit or PR/MR message, or reviewing branch changes before committing. Triggers on requests like "so sánh với main", "tóm tắt thay đổi", "mô tả code đã làm gì", "viết commit message", "what did this branch do", "summarize my changes vs main".
---

# git-diff-summary (speed-optimized)

Compare **current branch (incl. uncommitted changes)** vs a **freshly-updated main**, then emit:
1. **Mô tả tiếng Việt** (non-technical) — 2. **English conventional commit message**.

Core diff rule: always diff from **merge-base → working tree** (`git diff "$(git merge-base REF HEAD)"`). Never `git diff main HEAD` — it misses uncommitted work and pulls in main's later commits.

## Performance rules (read first)

1. **ONE tool call for all context.** Never run git commands one-by-one across multiple bash calls — round-trips are the #1 latency cost. Run the single gather script below; it returns everything (branch, intent, stat, size, and the full diff when small).
2. **Fetch never blocks.** The script backgrounds `git fetch` behind a 10s `timeout` while local state is read in parallel; on failure it falls back to cached `origin/main` → local `main` and prints `WARN_STALE_BASE`.
3. **Size-gated reading.** Small diff → already in the script output, analyze immediately, zero extra calls. Only large diffs pay for more work.
4. **Fan-out, max 64.** Large diffs are partitioned and read by parallel subagents — **spawn all Task calls in a single message** so they run concurrently. Cap at 64.
5. **Never dump a huge diff into main context.** Main agent sees numstat + subagent summaries only.
6. **Exclude noise up front.** Lockfiles / generated / minified files are excluded from content reads (still counted in numstat).

## Step 1 — One-shot gather (single bash call)

Defaults: `REMOTE=origin`, `BASE_BRANCH=main`. If the user names another base (`master`, `develop`…), set it. Run exactly this in **one** bash call:

```bash
set -u; export GIT_PAGER=cat GIT_OPTIONAL_LOCKS=0
REMOTE=${REMOTE:-origin}; BASE_BRANCH=${BASE_BRANCH:-main}
EXC=':(exclude)**/package-lock.json' ; EXC2=':(exclude)**/*.min.*' ; EXC3=':(exclude)**/yarn.lock' ; EXC4=':(exclude)**/pnpm-lock.yaml' ; EXC5=':(exclude)**/*.snap' ; EXC6=':(exclude)dist/**' ; EXC7=':(exclude)build/**'

git rev-parse --is-inside-work-tree >/dev/null 2>&1 || { echo NOT_A_REPO; exit 0; }
# fetch in background while we read local state
( timeout 10 git fetch --no-tags --quiet "$REMOTE" "$BASE_BRANCH" 2>/dev/null ) & FP=$!
echo "== BRANCH =="; git branch --show-current
echo "== STYLE =="; git log -n 5 --format='%s'
wait "$FP"; FRC=$?

if [ "$FRC" -eq 0 ] || git rev-parse -q --verify "$REMOTE/$BASE_BRANCH" >/dev/null; then
  REF="$REMOTE/$BASE_BRANCH"; [ "$FRC" -ne 0 ] && echo WARN_STALE_BASE
elif git rev-parse -q --verify "$BASE_BRANCH" >/dev/null; then
  REF="$BASE_BRANCH"; echo WARN_STALE_BASE_LOCAL
else echo NO_BASE; exit 0; fi

MB=$(git merge-base "$REF" HEAD) || { echo NO_MERGE_BASE; exit 0; }
echo "== REF == $REF"; echo "== MB == $MB"
echo "== INTENT =="; git log "$REF"..HEAD --format='%s%n%b'
echo "== NUMSTAT =="; git diff --numstat "$MB"
F=$(git diff --name-only "$MB" | wc -l | tr -d ' ')
L=$(git diff --numstat "$MB" -- . "$EXC" "$EXC2" "$EXC3" "$EXC4" "$EXC5" "$EXC6" "$EXC7" | awk '{s+=$1+$2} END{print s+0}')
echo "== SIZE == files=$F lines=$L"
if [ "$F" -eq 0 ]; then echo EMPTY_DIFF
elif [ "$L" -le 1500 ] && [ "$F" -le 30 ]; then
  echo "== DIFF =="; git diff --find-renames "$MB" -- . "$EXC" "$EXC2" "$EXC3" "$EXC4" "$EXC5" "$EXC6" "$EXC7"
else echo FAN_OUT
fi
```

Interpret markers:
- `NOT_A_REPO` → tell the user, stop. Empty `== BRANCH ==` → detached HEAD: warn, ask how to proceed.
- `NO_BASE` → ask for the correct base branch (or auto-detect: `git symbolic-ref refs/remotes/$REMOTE/HEAD`).
- `WARN_STALE_BASE*` → prepend a one-line stale-base warning to the final answer.
- `EMPTY_DIFF` → say there are no changes vs base, stop.
- `== DIFF ==` present → **fast path**: skip Step 2, write the answer now.
- `FAN_OUT` → Step 2.

## Step 2 — Parallel fan-out (only when `FAN_OUT`)

**Partition** files from `== NUMSTAT ==` (no extra git calls needed):
- Group by top-level directory / feature area so related context stays together.
- Greedy bin-pack groups into buckets of **~1500–2500 changed lines** each.
- `N = min(64, number_of_buckets)`. Typical repos need 2–8; never exceed 64.

**Dispatch all N subagents in ONE message** (parallel Task calls). Use the fastest available model (haiku if offered, else sonnet) — extraction is mechanical; synthesis quality lives in the main agent. Each brief:

> Read-only task. Run: `GIT_OPTIONAL_LOCKS=0 git --no-pager diff --find-renames <MB> -- <file list>`. Return ≤15 bullets: per feature/area — what changed behaviorally (user-visible effect old→new), plus notable risks (migrations, API changes, deleted behavior). No code quotes, no line numbers. ≤200 words.

(`git diff` reads are lock-free and safe at 64-way concurrency with `GIT_OPTIONAL_LOCKS=0`.)

**Synthesize** subagent bullets + `== INTENT ==` into the two output parts. If a bucket's summary is ambiguous, prefer re-briefing that one subagent over reading the raw diff yourself.

## Output contract (produce BOTH, in this order)

**Part 1 — Mô tả thay đổi (tiếng Việt), luôn luôn tiếng Việt**, for a non-technical reader (PM/QA/manager). Structure, exactly:
1. One-sentence summary — what the branch delivers, from the player's/operator's side.
2. Groups by **user-facing feature name** (e.g. "Vòng quay Rush", "Ví tiền") — never file/class/module names.
3. 1–4 bullets per group, each shaped as:
   - `Trước đây <old behaviour> → giờ <new behaviour>`
   - `Thêm/Sửa <what the user sees> để <benefit>`
4. **"Ảnh hưởng"** (only when real) — 1–3 lines: what users notice + release risk/caveat.

Style: sentences ≲25 words, everyday vocabulary, user/game as subject. Jargon only when unavoidable, first occurrence explained in Vietnamese. Plain-wording table (extend as needed):

| Technical | Part 1 wording |
|---|---|
| endpoint / API | màn hình … lấy dữ liệu từ máy chủ |
| cache / Redis | bộ nhớ tạm để chạy nhanh hơn |
| race condition | hai thao tác cùng lúc gây ra kết quả sai |
| refactor | dọn lại code cho gọn, cách chạy giữ nguyên |
| migration | đổi cấu trúc dữ liệu đang lưu |
| null / NPE | thiếu dữ liệu nên hệ thống báo lỗi |

Bullet quality bar:
> **Hũ thưởng (Jackpot)**
> - Trước đây nổ hũ xong số tiền hiển thị vẫn là số cũ trong vài giây → giờ về 0 ngay khi trả thưởng.
> - Thêm hũ nhỏ vào danh sách hũ, người chơi thấy đủ 4 mức thưởng thay vì 3.

**Part 2 — English commit message**, in a fenced code block:

```
type(scope): imperative summary ≤ ~72 chars

- key change
- key change
```

- **type**: dominant change wins — `feat`/`fix`/`refactor`/`perf`/`chore`/`docs`/`test`/`build`; brand-new functionality → `feat`.
- **scope**: ticket from branch name via `[A-Z][A-Z0-9]+-[0-9]+` (branch `FRUITS-7029-...` → `FRUITS-7029`); no ticket → short area name or omit.
- Imperative, English; mirror the repo style seen in `== STYLE ==` (already gathered — no extra call).

## Common mistakes

- Multiple sequential bash calls for context — everything belongs in the Step 1 single call.
- `git diff main HEAD` / `git diff main` — wrong base; use merge-base → working tree.
- Silent stale base — always surface `WARN_STALE_BASE`.
- Dumping a `FAN_OUT`-sized diff into main context instead of parallel subagents.
- Part 1 written as a developer changelog (files/classes/internals) — audience is PM/QA.
- Swapped languages (Part 1 must be Vietnamese, Part 2 English) or a forgotten ticket scope.
