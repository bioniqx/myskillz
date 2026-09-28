---
name: git-diff-summary
description: Use when the user wants to understand or summarize what the current branch changed versus the main branch — describing what the new code does, drafting a commit or PR/MR message, or reviewing branch changes before committing. Triggers on requests like "so sánh với main", "tóm tắt thay đổi", "mô tả code đã làm gì", "viết commit message", "what did this branch do", "summarize my changes vs main".
argument-hint: "[base-branch]"
allowed-tools: Read Bash(bash *gather.sh*) Bash(git diff *) Bash(git log *) Bash(git show *)
---

# git-diff-summary

Goal: diff **merge-base(fresh base) → working tree** (committed + staged + unstaged + untracked), then output **Part 1 Vietnamese description** + **Part 2 English commit message**.

## Context — already gathered (0 tool calls)

```!
bash "${CLAUDE_SKILL_DIR}/scripts/gather.sh" $ARGUMENTS
```

If the block above shows the raw command instead of output (harness without `!` injection), run it once with Bash: `bash <this skill dir>/scripts/gather.sh [base]`. If the user named a base branch that differs from `REF`, re-run with it. Never run git commands one by one.

What the script already did (don't redo): background `git fetch` of only the base branch (6s hard timeout, no prompts, skipped if fetched <5 min ago) · speculative diff on the cached base in parallel (reused when merge-base is unchanged) · untracked files included · lockfiles/generated/minified/`*.meta`/dist excluded from content but listed in NUMSTAT · ticket parsed from branch · diff pre-split into chunks that each fit one Read.

## Act on the markers — pick the fastest path

| Marker | Action |
|---|---|
| `NOT_A_REPO` / `EMPTY_DIFF` | Say so in one line. Stop. |
| `NO_BASE` / `NO_MERGE_BASE` | Ask the user for the base branch. |
| `WARN_STALE_BASE*` / `WARN_BASE_ARG_IGNORED` | First line of the answer = one-line warning. Continue. |
| `(detached HEAD)` | Mention it; continue. |
| `ONLY_NOISE_OR_BINARY` | Describe from NUMSTAT paths. |
| `MODE=INLINE` | Diff is above. **Write the answer now** — no more tool calls. |
| `MODE=READ` | **One message, all Read calls in parallel** (one per chunk path). Then answer. |
| `MODE=FAN_OUT` | Step below. |

### FAN_OUT (big diffs only)

In **ONE message**, launch one `Agent` per listed chunk (≤64; they run concurrently): `subagent_type: general-purpose`, `model: haiku`, description `diff chunk NNN`. Prompt (fill path):

> Read-only. Read `<chunk path>` fully (if the Read is truncated, continue with offset until the end). It is a git diff of one area of a branch. Reply ONLY with ≤10 bullets, ≤150 words, no code, no line numbers:
> `AREA: <feature/area name inferred from paths+code>`
> `- OLD→NEW: <behavior change a user/operator would notice>` (or `- ADD:` / `- REMOVE:` / `- INTERNAL:` for refactor-only)
> `- RISK: <migration, API/contract change, deleted behavior, config/env>` (only if real)

Then synthesize from subagent bullets + `INTENT` + `NUMSTAT` only. Never Read chunks yourself in this mode; if one summary is unclear, re-ask that one agent (SendMessage).

## Output contract (both parts, this order, nothing else)

**Part 1 — Mô tả thay đổi (luôn tiếng Việt)** for PM/QA/manager, non-technical:
1. One-sentence summary of what the branch delivers, from the player's/operator's side.
2. Groups named by **user-facing feature** (e.g. "Vòng quay Rush", "Ví tiền") — never file/class/module names.
3. 1–4 bullets per group: `Trước đây <cũ> → giờ <mới>` or `Thêm/Sửa <người dùng thấy gì> để <lợi ích>`.
4. **Ảnh hưởng** (only if real): 1–3 lines — what users notice + release risk.

Sentences ≲25 words, everyday words, user/game as subject; unavoidable jargon explained once. Wording: endpoint/API → "màn hình … lấy dữ liệu từ máy chủ" · cache/Redis → "bộ nhớ tạm để chạy nhanh hơn" · race condition → "hai thao tác cùng lúc gây kết quả sai" · refactor → "dọn lại code cho gọn, cách chạy giữ nguyên" · migration → "đổi cấu trúc dữ liệu đang lưu" · null/NPE → "thiếu dữ liệu nên hệ thống báo lỗi".

Quality bar:
> **Hũ thưởng (Jackpot)**
> - Trước đây nổ hũ xong số tiền vẫn hiện số cũ vài giây → giờ về 0 ngay khi trả thưởng.
> - Thêm hũ nhỏ, người chơi thấy đủ 4 mức thưởng thay vì 3.

**Part 2 — English commit message**, fenced code block:

```
type(scope): imperative summary ≤72 chars

- key change
- key change
```

- type = dominant change: `feat` (new functionality) / `fix` / `refactor` / `perf` / `chore` / `docs` / `test` / `build`.
- scope = `TICKET` from the header; if `none` → short area name or omit.
- Mirror the tone/format of `STYLE` subjects.

## Don'ts

- Extra git/bash calls "to double-check" — the header is authoritative.
- `git diff main HEAD` (misses uncommitted work, pulls in main's newer commits).
- Reading FAN_OUT chunks in the main context, or launching subagents across several messages.
- Part 1 as a dev changelog (files, classes, internals); swapped languages; missing ticket scope; silent stale-base.
