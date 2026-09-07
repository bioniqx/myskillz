# dev-team v2 — event-driven, 64-wide, test-first

Skill Claude Code điều phối tối đa 64 subagent song song (programmer trong git worktree
riêng, reviewer/leader read-only), tối ưu cho **tốc độ wall-clock (10/10)** với chất
lượng giữ ở **8/10** bằng các gate cơ học (hook + script) thay vì bằng prose.

## Cài đặt (1 phút)

```
.claude/
  skills/dev-team/          ← copy nguyên thư mục này vào đây (hoặc ~/.claude/skills/dev-team)
    SKILL.md
    scripts/devteam.py      ← engine: scheduler / integrator / worktree helper (stdlib Python)
    scripts/guard.py        ← hook guards (footprint, frozen tests, read-only roles, stop gate)
    agents/*.md             ← nguồn của 3 agent
  agents/                   ← doctor --fix sẽ cài 3 agent vào đây
```

Trong repo, chạy một lần:

```bash
python3 .claude/skills/dev-team/scripts/devteam.py doctor --fix
```

Lệnh này: cài 3 agent vào `.claude/agents/` (và trỏ hook về đúng `guard.py`), ghi
`.claude/settings.local.json` với:

```json
{
  "env": { "CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS": "64", "CLAUDE_CODE_MAX_TOOL_USE_CONCURRENCY": "64" },
  "worktree": { "baseRef": "head", "symlinkDirectories": ["node_modules"] },
  "permissions": { "allow": ["Bash(python3 <abs>/devteam.py:*)"] }
}
```

và thêm `.claude/worktrees/`, `.claude/dev-team/`, `.slice/` vào `.git/info/exclude`.
**Khởi động lại Claude Code** sau `--fix` (env chỉ áp dụng lúc start). Yêu cầu:
Claude Code ≥ 2.1.250, git ≥ 2.31, python3. Không cài agent qua plugin (plugin bỏ
qua `hooks`/`permissionMode`).

## Vì sao bản này nhanh hơn bản cũ

| Vấn đề ở bản cũ | Bản v2 |
|---|---|
| Claude Code mặc định chỉ cho **20 subagent đồng thời** → "64 luồng" thực tế chết ở luồng 21 | `doctor --fix` set `CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS=64`; engine tự cap theo giới hạn đang chạy |
| "Mỗi message dispatch mọi slice sẵn sàng" nhưng Agent call foreground → **wave barrier ngầm** (turn chờ slice chậm nhất) | Worker chạy **background** (`background: true` + fork mode) → mỗi completion là một notification → dispatch dependents ngay, không đợi anh em |
| Programmer "cd vào worktree" — nhưng `cd` **không tồn tại giữa các lệnh Bash** trong subagent → chạy test/commit nhầm cây chính | `isolation: worktree` native: Claude Code tự chạy Bash trong worktree và **chặn cứng** mọi ghi/git vào checkout chính |
| Conductor tự tay `git worktree add`, merge, diff-check, đếm slot, tính DAG bằng prose → tốn turn + token output | `devteam.py`: 1 lệnh/wake-up (`integrate` → `dispatch`), scheduler critical-path, kiểm RED/frozen/footprint, merge, dọn worktree, in đúng thứ cần launch |
| Briefing 1–2 KB × 64 slice = hàng chục nghìn token output của Conductor (phút) | Prompt 3 dòng; briefing là file do engine sinh, programmer đọc qua `claim` |
| Worktree mới không có `node_modules` → mỗi slice phải install lại | `worktree.symlinkDirectories` + `claim` tự symlink dep dirs, copy `.env*` |
| Footprint / "không sửa test sau RED" chỉ là lời dặn | Hook `PreToolUse` từ chối edit ngoài footprint và edit test đã đóng băng; hook `Bash` chặn merge/rebase/amend/reset; hook `Stop` không cho agent kết thúc khi chưa có RED commit, chưa commit GREEN, cây bẩn, hoặc thiếu report; `integrate` kiểm lại lần nữa khi merge |
| Fix loop = dispatch lạnh, review lại = dispatch lạnh, BLOCKING = dispatch lại | `SendMessage` tới agent id → resume **ấm** với đủ context và worktree cũ |
| Leader/reviewer trả plan/report qua tin nhắn → Conductor phải chép lại | Leader ghi `.claude/dev-team/plan.md`, reviewer ghi `reviews/rN.report.md` (Write bị hook giới hạn đúng thư mục); fix slices là JSON → `add-fixes` xếp thẳng vào hàng đợi |
| Leader phân tích lại repo mỗi lần | `memory: project` — leader nhớ bản đồ codebase/lệnh/convention giữa các session |
| Subagent nền gặp permission prompt → treo (không ai trả lời) | `init` ghi allow-rule cho mọi lệnh test/lint/build của plan (cả dạng có prefix PORT/DB/TMPDIR) + git read-only; merge/commit chạy `--no-verify` và tắt gpgsign |
| Checkpoint full-suite chạy trên cây đang bị merge liên tục → kết quả không rõ của sha nào | `checkpoint` snapshot HEAD vào worktree detached riêng; merge tiếp tục song song; ghi đúng sha đã test |
| Slice bị reject → phải dispatch lại từ đầu | Reject giữ slice ở trạng thái in-flight cùng worktree → `SendMessage` sửa ấm → `integrate` lại |
| Tier A/B, EXPLORER mode, TaskCreate… | Một cơ chế duy nhất (worktree + engine); explore dùng agent `Explore` built-in; progress = `devteam status` (Task tools không còn mặc định trên các model mới) |

Ba luật không đổi: test commit trước implementation (và đóng băng), review độc lập
mọi dòng, không bao giờ hai writer trên một path.

## Vòng đời một run (Conductor)

```
doctor → (baseline test background) → plan.md → init → dispatch → [wake-up: integrate → dispatch/review-batch/checkpoint]* → review-batch --force ∥ verify-brief → add-fixes → … → finish
```

Xem `SKILL.md` (được nạp vào Conductor) — mỗi bước là một lệnh engine in ra chính xác
Agent call cần gọi. `python3 scripts/devteam.py --help` liệt kê mọi lệnh.

## Đã kiểm thử

`bash scripts/selftest.sh` (34 check, chạy ~10 s, cần git ≥ 2.31 + python3) dựng repo
git tạm và đi hết vòng đời: init/validate + cảnh báo footprint trùng, ready-set tách
rời đôi một, cap slot theo env, allow-rule, symlink node_modules không thành file lạ,
high-risk RED→GREEN (worktree GREEN bắt đầu đúng ở RED tip), reject khi sửa test đã
đóng băng / file ngoài footprint (giữ in-flight, sửa ấm rồi integrate lại), merge với
gpgsign+hooks tắt, checkpoint snapshot detached, review batch shard, add-fixes từ
report, retry nạp lại plan.md, 5 chế độ hook với JSON stdin thật, doctor --fix pin hook,
đường dẫn có dấu cách. Một reviewer độc lập (subagent) đã rà lại toàn bộ package và 15
phát hiện của nó đã được sửa. Chưa chạy bên trong một phiên Claude Code thật — hãy
chạy thử trên một task nhỏ trước khi mở rộng 64 luồng.

## Dial khi cần chỉnh

- Plan: `review_batch` (mặc định 8), `checkpoint_every` (8), `test_globs`, `dep_dirs`.
- `agents/programmer.md`: `effort: medium` → `low` cho việc boilerplate; `maxTurns`.
- `agents/team-leader.md`: `model: fable` nếu tài khoản có; `effort: xhigh` cho plan rất lớn.
- Agent Teams (experimental) và Workflow tool không dùng làm mặc định: teams không resume
  được, workflow giới hạn 16 agent và không có shell để merge.
