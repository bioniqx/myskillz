---
name: glm-git-diff-summary
description: Use when the user wants to understand or summarize what the current branch changed versus the main branch — describing what the new code does, drafting a commit or PR/MR message, or reviewing branch changes before committing. Triggers on requests like "so sánh với main", "tóm tắt thay đổi", "mô tả code đã làm gì", "viết commit message", "what did this branch do", "summarize my changes vs main".
argument-hint: "[base-branch|tag|sha]"
allowed-tools: Read Bash(bash "${CLAUDE_SKILL_DIR}/scripts/gather.sh"*) Bash(git diff *) Bash(git log *) Bash(git show *)
---

# glm-git-diff-summary

Goal: diff **merge-base(fresh base) → working tree** (committed + staged + unstaged + untracked), then output **Part 1 change summary — Vietnamese first, English right below** + **Part 2 English commit message**.

## Context — already gathered (0 tool calls)

```!
bash "${CLAUDE_SKILL_DIR}/scripts/gather.sh" "$ARGUMENTS"
```

If the block above shows the raw command instead of output (harness without `!` injection), run it once with Bash: `bash <directory of this file>/scripts/gather.sh`. The block passes the user's argument as the base. If the user named a base (branch, tag or SHA) that differs from `REF`, first check it against the pattern `^[A-Za-z0-9][A-Za-z0-9._/@~^-]*$` (the pattern also rejects a leading `-`; if it does not match, ask for a different base and run nothing), then re-run once with the value single-quoted: `bash <directory of this file>/scripts/gather.sh '<base>'`. The script resolves the base with `git rev-parse`, so a branch, tag or SHA all work. Never run git commands one by one.

What the script already did (don't redo): background `git fetch` of only the base branch (6s hard timeout, no prompts, skipped if fetched <5 min ago) · speculative diff on the cached base in parallel (reused when merge-base is unchanged) · untracked files included · lockfiles/generated/minified/`*.meta`/dist excluded from content but listed in NUMSTAT · ticket parsed from branch · diff pre-split into chunks that each fit one Read.

## Act on the markers — pick the fastest path

| Marker | Action |
|---|---|
| `GATHER_FAILED` | The script couldn't create its temp dir. Fall back to a manual `git diff` against the base branch. |
| `NOT_A_REPO` / `EMPTY_DIFF` | Say so in one line. Stop. |
| `NO_BASE` / `NO_MERGE_BASE` | Ask the user for the base (branch, tag or SHA), validate it as described above, then re-run once. |
| `WARN_STALE_BASE*` / `WARN_BASE_ARG_IGNORED` | First line of the answer = one-line warning. Continue. |
| `(detached HEAD)` | Mention it; continue. |
| `ONLY_NOISE_OR_BINARY` | Describe from NUMSTAT paths. |
| `MODE=INLINE` | Diff is above. **Write the answer now** — no more tool calls. |
| `MODE=READ` | **One message, all Read calls in parallel** (one per chunk path). Then answer. |
| `MODE=FAN_OUT` | Step below. |

### FAN_OUT (big diffs only)

In **ONE message**, launch one lane per listed chunk (≤64; they run concurrently), then end the turn — every lane goes out together. Syntax per harness:
- Claude Code / ZCode — `Task` tool: `subagent_type: general-purpose`, description `diff chunk NNN` (ZCode's `Agent` tool takes no `model` parameter; if a model must be named, use the real id `glm-5.3-flash`).
- OpenCode — `subagent` tool: `agent: "general"`, `description: "diff chunk NNN"`, `background: true`, no `model` or `variant` field (there is no `general-purpose` or model alias on OpenCode; the lane runs on the model selected in the window).
Prompt (fill path):

> Read-only. Read `<chunk path>` fully (if the Read is truncated, continue with offset until the end). It is a git diff of one area of a branch. Reply ONLY with ≤10 bullets, ≤150 words, no code, no line numbers:
> `AREA: <feature/area name inferred from paths+code>`
> `- OLD→NEW: <behavior change a user/operator would notice>` (or `- ADD:` / `- REMOVE:` / `- INTERNAL:` for refactor-only)
> `- RISK: <migration, API/contract change, deleted behavior, config/env>` (only if real)

Then synthesize from lane bullets + `INTENT` + `NUMSTAT` only. Never Read chunks yourself in this mode; if one summary is unclear, re-dispatch just that one lane in your next message (SendMessage is Claude Code only).

## Output contract (both parts, this order, nothing else)

**Part 1 — Mô tả thay đổi (song ngữ: tiếng Việt trước, tiếng Anh ngay dưới)** for PM/QA/manager, non-technical:
1. One-sentence summary of what the branch delivers, from the player's/operator's side.
2. Groups named by **user-facing feature** (e.g. "Vòng quay Rush", "Ví tiền") — never file/class/module names.
3. 1–4 bullets per group: `Trước đây <cũ> → giờ <mới>` or `Thêm/Sửa <người dùng thấy gì> để <lợi ích>`.
4. **Ảnh hưởng** (only if real): 1–3 lines — what users notice + release risk.
5. **Then the same summary in English, directly below the Vietnamese block** under the heading `**Change summary (English)**`: translate the one-sentence summary, every group and every bullet — no new facts, no omissions, natural technical English instead of word-for-word.

Sentences ≲25 words, everyday words, user/game as subject; unavoidable jargon explained once. Wording: endpoint/API → "màn hình … lấy dữ liệu từ máy chủ" · cache/Redis → "bộ nhớ tạm để chạy nhanh hơn" · race condition → "hai thao tác cùng lúc gây kết quả sai" · refactor → "dọn lại code cho gọn, cách chạy giữ nguyên" · migration → "đổi cấu trúc dữ liệu đang lưu" · null/NPE → "thiếu dữ liệu nên hệ thống báo lỗi".

Quality bar:
> **Hũ thưởng (Jackpot)**
> - Trước đây nổ hũ xong số tiền vẫn hiện số cũ vài giây → giờ về 0 ngay khi trả thưởng.
> - Thêm hũ nhỏ, người chơi thấy đủ 4 mức thưởng thay vì 3.

> **Change summary (English)**
> **Jackpot prize**
> - The jackpot amount used to show the old value for a few seconds after a win → it now resets to 0 as soon as the prize is paid.
> - Added a mini jackpot tier, players now see all 4 prize tiers instead of 3.

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
- Part 1 as a dev changelog (files, classes, internals); English block above or instead of the Vietnamese one; missing ticket scope; silent stale-base.
