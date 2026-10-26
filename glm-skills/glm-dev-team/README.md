# glm-dev-team v4.2 — bản tối ưu cho Z.ai GLM-5.3 / GLM-5.3-Flash (chỉ ZCode)

Skill ZCode điều phối nhiều subagent song song (glm-programmer-lite / glm-programmer-strong trong git
worktree riêng, reviewer / glm-investigator / leader chỉ đọc). Engine giữ trạng thái và kiểm tra bằng máy
(hook + script), không dựa vào lời dặn. v4 giữ nguyên toàn bộ cơ chế đảm bảo chất lượng của v3.2, định tuyến
mô hình theo frontmatter agent của ZCode, cộng thêm bộ **governor** tự điều chỉnh độ song song.

## Vì sao v3.2 chạy kém trên GLM (đã kiểm chứng)

| Giả định của v3.2 | Thực tế khi chạy qua Z.ai | Hệ quả |
|---|---|---|
| Lane chạy `sonnet` = model rẻ/nhanh | Z.ai map `opus` **và** `sonnet` → `glm-5.3`, chỉ `haiku` → `glm-5.3-flash` | Mọi lane chạy GLM-5.3: chậm hơn, tốn ~3× quota |
| `effort: medium/high` trong frontmatter | GLM luôn bật thinking, mặc định `max`; harness cũ chỉ gửi effort cho model bên thứ ba nếu `*_SUPPORTED_CAPABILITIES` có `effort` | Mọi lời gọi chạy ở mức `max`, chậm nhất |
| Mở 64 luồng cùng lúc | Provider chỉ cho 8 lời gọi API đồng thời; giới hạn theo gói còn có thể thấp hơn và thay đổi động, thấp hơn giờ cao điểm | Dính 429/1302 hàng loạt, lane bị retry/backoff, bị treo |
| `subagentPromptCacheTtl: 1h`, `cacheTtl: 1h` | Z.ai tự cache ngầm, TTL 1h của Anthropic không áp dụng | Cấu hình vô ích |
| Mẹo `/fast` | Chỉ có với Opus của Anthropic | Không dùng được |
| Spawn bị runtime từ chối ("Concurrent subagent limit reached") | Slice vẫn đánh dấu đang chạy | Treo vĩnh viễn |

## v4 thay đổi gì

| Hạng mục | v4 |
|---|---|
| **Định tuyến model (chỉ ZCode)** | Mọi lane mặc định chạy **`glm-programmer-lite`** (GLM-5.3-Flash, thoughtLevel high). `risk: high`, `size: large` và **mọi slice phải retry** → **`glm-programmer-strong`** (GLM-5.3, thoughtLevel max). Tool `Agent` của ZCode không nhận `model` theo từng lần gọi — model id và `thoughtLevel` ghim sẵn trong frontmatter từng file agent (thiếu `model` thì ZCode bỏ qua `thoughtLevel`): glm-code-reviewer GLM-5.3 high, glm-spot-reviewer/glm-investigator Flash high, leader GLM-5.3 max. `injectAgentsMd: false` để rule của lane không bị chôn dưới AGENTS.md của repo |
| **doctor --harness zcode --fix** | Copy nguyên văn **6 agent** vào `~/.zcode/agents/` và merge hook guard (PreToolUse + Stop) vào `~/.zcode/cli/config.json` (`hooks.enabled: true`, giữ nguyên mọi key user, chạy lại là no-op, không tạo `.bak`); không ghi gì dưới thư mục repo |
| **Governor (AIMD)** | Cửa sổ song song: mặc định tier `api` mở đủ 8 lời gọi đồng thời ngay từ đợt đầu (provider chỉ cho 8; leader/reviewer cũng nằm trong 8 đó); `DEVTEAM_GLM_TIER`/`--tier lite|pro|max` hạ xuống 3/6/7 khi muốn nhẹ rate limit. Tăng dần khi lane hoàn thành (chỉ khi cửa sổ đang được dùng hết), **giảm một nửa** khi transcript có 429/1302/1305/overload (tối đa một lần mỗi 90 giây); trần giờ cao điểm Z.ai (T2–T6, 14–18h UTC+8, tức 13–17h giờ Việt Nam) chỉ giảm khi bật `DEVTEAM_PEAK=on` |
| **Tự phục hồi** | Spawn bị từ chối/lỗi → đưa slice về hàng đợi (không re-queue nếu Conductor đã tự launch lại thành công); lỗi "agent type not found" lặp lại → báo cần mở phiên ZCode mới; lane chết vì lỗi API → in `LANE DOWN` kèm cách sửa warm (`SendMessage "continue"`) |
| **`devteam stats`** | Số liệu **đo được** từ transcript (định dạng Claude Code) theo role/model: số request (khử trùng lặp theo requestId), output token, tỉ lệ cache hit, effort thực gửi, lỗi API, thời gian chạy; cảnh báo nếu effort không được gửi |
| **Agent prompts** | Bỏ nhắc sonnet/opus/64; thêm quy tắc "ít turn, gộp đọc file thành tool call song song" (mỗi turn là một lần gọi model có thinking) |
| Anthropic | Provider vẫn nhận diện được (`DEVTEAM_PROVIDER=anthropic` hoặc tự nhận từ base URL) — chỉ còn ảnh hưởng nhãn stats; định tuyến strong/lite như nhau và trần vẫn là 8 |

## v4.1 - giảm sai sót cho GLM

v4.1 không đổi kiến trúc. Nó thêm các lớp chặn cho những lỗi mà GLM-5.3 / GLM-5.3-Flash hay mắc: engine tự chạy lại và kiểm tra thay vì tin lời báo cáo của lane, còn prompt được viết lại thành quy tắc đánh số, đặt điều quan trọng ở đầu và nhắc lại bằng checklist ở cuối.

| Điểm yếu GLM | Cơ chế chặn |
|---|---|
| Báo "xong / test pass" mà chưa chạy gì | **Proof run**: trước khi merge (profile `strict`/`balanced`) engine tự chạy lại test của slice, `verify` (chore/docs/perf), toàn bộ test (refactor) và lint/typecheck theo file trong worktree; exit khác 0 thì `PROOF FAILED`. **Stop gate**: `## Gate:` phải ghi lệnh đã chạy, `## Criteria:` bắt buộc, `Complete` kèm tiêu chí "not met" bị từ chối. Prompt: mục "What gets a slice rejected" và checklist "Before you finish" |
| Bịa API, symbol, đường dẫn | Rule "Verified symbols only" (đã có); reviewer phải mở mọi vị trí bằng Read/grep trước khi trích dòng nguyên văn, vị trí chưa mở thì loại; unknown symbol là `Blocked` |
| Viết test rỗng hoặc yếu | **Red proof** (strict: mọi slice; balanced: risk high): test mới phải FAIL trên commit RED. **Static check** lúc `commit-red`/`commit-work`: chặn skip/xfail/only/todo, assert tautology, thân test rỗng |
| Để lại TODO, placeholder, giá trị expected hard-code | **Static check** lúc `commit-green`/`commit-work`: chặn dòng thêm có TODO/FIXME, "not implemented", debugger/pdb; reviewer có danh sách kiểm tra tường minh |
| Nuốt lỗi | Static check chặn empty catch và `except ...: pass`; rule "Fail loudly"; reviewer kiểm swallowed errors từng mục |
| Lặp mãi một lệnh lỗi | Mục "Tool mechanics" trong agent: lỗi giống nhau lần 2 thì đổi cách, lần 3 thì `Blocked` kèm lỗi; investigator có loop guard tương tự. **Reject escalation**: sau 2 lần bị từ chối cùng một dispatch, engine in `retry <id>` (khởi động lạnh trên `glm-programmer-strong`) |
| Edit với `old_string` chưa đọc lại | "Tool mechanics": Read lại vùng cần sửa trước mỗi Edit, Edit lỗi thì Read lại, hai lần lỗi thì dùng Write (chỉ trong footprint) hoặc `Blocked` |
| Reviewer đóng dấu APPROVED không bằng chứng, bịa vị trí finding | **Review fail-closed**: APPROVED/PASS mà thiếu `## Evidence` bị coi là UNKNOWN (changes required); báo cáo reviewer có mục `## Evidence`; mỗi finding phải trích dòng nguyên văn tại vị trí đã mở |
| Diễn đạt lại prompt phải dán nguyên văn; chỉ launch một phần số lane được in | Mục "Conductor discipline" (9 quy tắc) trong SKILL.md; dòng cuối `LAUNCH N: <ids>` cho biết đúng N lời gọi `Agent` phải phát trong MỘT message; mục "Final check" cuối file |
| Plan sai ngay từ đầu (slice code không có test, đường dẫn tuyệt đối, tiêu chí mơ hồ) | **Plan validation**: slice `code` không có đường dẫn test hoặc `files` tuyệt đối/`..` là lỗi; cảnh báo cho tiêu chí dưới 4 từ, risk high thiếu `edge_cases`, `test_file` thiếu `{files}`, `commands.test` là none mà vẫn có slice `code`; leader có "Plan self-check" |

Khi bị từ chối, Conductor gửi nguyên văn lệnh và đoạn cuối output cho lane qua `SendMessage` để sửa nguyên nhân, không bao giờ nới test, gate, footprint hay profile để qua.

## v4.2 — ghim model lại, và chặn thêm ba lỗi GLM bằng máy

v4.1 đã có proof run và static check. v4.2 vá lỗ mà prompt không chặn được:

| Điểm yếu GLM | Cơ chế |
|---|---|
| Frontmatter mất `model` / `thoughtLevel` (lane chạy model của session, effort không có tác dụng) | Sáu agent ghim lại `account:zai-individual-coding-plan/GLM-5.3` hoặc `GLM-5.3-Flash`. Lane code mặc định là Flash ở **high** (coding cần effort; `low` là chỗ Flash bịa API). Strong / leader vẫn `max` |
| AGENTS.md của repo chèn vào giữa prompt, rule của slice bị rơi | `injectAgentsMd: false`. Leader đọc AGENTS.md / CLAUDE.md một lần và chép convention vào `notes`; lane chỉ thấy briefing |
| Bịa import / tên stdlib không tồn tại | `commit-red` / `commit-green` / `commit-work` từ chối import thêm mà không nằm trong repo, stdlib (đúng attribute), `requirements`/`pyproject`, `package.json` hoặc `go.mod`. `--force` là lối thoát |
| Viết đủ số test nhưng không dùng đúng giá trị của tiêu chí | Tiêu chí có số (≥2 chữ số) hoặc chuỗi trong ngoặc mà test không chứa literal đó thì `commit-red` từ chối. Comment một mình không tính |
| Conductor chỉ launch một phần các Agent (GLM ít tool call song song) | Slice inflight quá 120 giây (`DEVTEAM_UNCLAIMED_S`) mà không có file claim thì `next` in `UNCLAIMED` và in lại đúng dòng Agent. Không in lại ở wake-up ngay sau đó |

## Cài đặt

```
sh install-zcode.sh            ← cài cả tám skill vào ~/.zcode/skills/ và mọi agents/*.md vào ~/.zcode/agents/
```

1. Chạy `sh install-zcode.sh` từ thư mục gốc repo (thêm `--home DIR` để chỉ định HOME, `--dry-run` để xem trước).
2. Trong repo: `python3 ~/.zcode/skills/glm-dev-team/scripts/devteam.py doctor --harness zcode --fix`
   (hoặc bỏ qua: `start` tự chạy) — copy 6 agent vào `~/.zcode/agents/` và merge hook guard vào
   `~/.zcode/cli/config.json`.
3. **Mở một phiên ZCode MỚI** (khởi động lại app là chưa đủ — skill/agent/hook chỉ nạp lúc mở phiên).
4. Mặc định đã mở đủ 8 lane (tier `api`). Chỉ đặt `export DEVTEAM_GLM_TIER=lite|pro|max` (hoặc `"glm": {"tier": "…"}` trong plan) khi muốn đổi width lấy độ nhẹ rate limit.
5. Sau run đầu tiên: `devteam stats` — xem cache hit và lỗi API để chọn tier hợp lý.

Yêu cầu: ZCode, git ≥ 2.31, python3.

### ZCode

Trên ZCode, engine tự nhận harness qua `is_zcode()`: `DEVTEAM_HARNESS=zcode` thắng trước, nếu không có thì detector theo đường dẫn quyết định (skill nằm trong `~/.zcode/skills`). Provider mặc định là `glm` (trần 8 lời gọi đồng thời). Agent được cài cấp user: `python3 devteam.py doctor --harness zcode --fix` copy nguyên văn sáu file `agents/` (frontmatter ZCode cuối — model id và `thoughtLevel` cố định sẵn trong file, không còn cờ `--flash/--main`) vào `~/.zcode/agents/` và merge hook guard vào `~/.zcode/cli/config.json` (`hooks.enabled: true`, không giữ bản sao lưu, chạy lại là no-op; `start` tự chạy doctor). Mỗi lane chạy qua tool `Agent` của harness:

1. **Dispatch:** tool `Agent` (alias của Task) nhận `subagent_type`, `description`, `prompt`, `run_in_background` — không có tham số `model` theo từng lần gọi. Mọi dòng `Agent →` in ra đều không có `model:`: slice mạnh (`risk: high` / `size: large` / bị retry) chạy `glm-programmer-strong`, còn lại chạy `glm-programmer-lite`; frontmatter của agent tự chọn model thật (`glm-5.3` / `glm-5.3-flash`, không có alias haiku/sonnet/opus). Launch mọi dòng trong MỘT message với `run_in_background: true`, prompt giữ nguyên, rồi kết thúc lượt.
2. **Đánh thức:** thông báo hoàn tất của lane chính là tín hiệu đánh thức. Dù ZCode không có event SubagentStop, stop gate vẫn có: `doctor --harness zcode --fix` cài Stop hook vào `~/.zcode/cli/config.json`, route Stop của programmer qua `guard.py`, và guard.py ghi marker `.done`/`.blocked` — chạy `devteam next [<id>]` với id của slice vừa xong, engine tự kiểm tra claim, worktree, RED/GREEN và footprint.
3. **Nhắn tin:** `SendMessage` và `TaskStop` tồn tại. Trả lời câu hỏi `BLOCKED`, hay gửi cách sửa cho `REJECTED` / `NOT READY` / `MERGE ERROR`, bằng `SendMessage` đến agent đó. `TaskStop` lane bị treo trước, rồi retry lạnh bằng `devteam retry <id>`.
4. **Cài đặt cần phiên mới:** agent và hook config mới chỉ được nạp trong một phiên ZCode MỚI (không phải khởi động lại app). Sau khi `doctor --fix` cài hoặc thay đổi gì, hãy bảo người dùng mở phiên mới một lần.

Hook là cấp user: cầu `guard.py zcode` routing theo `agent_type` của payload — role programmer chạy bộ kiểm tra edit/bash, role reviewer/leader/investigator chạy bộ chỉ-đọc, còn mọi role lạ được cho qua im lặng, nên hook không bao giờ ảnh hưởng phiên thường.

## Biến môi trường

| Biến | Tác dụng |
|---|---|
| `DEVTEAM_GLM_TIER` | `lite` / `pro` / `max` / `api` (mặc định) — cửa sổ khởi đầu của governor |
| `DEVTEAM_MAX_PARALLEL=N` | Ghim cứng số agent chạy song song (tắt thích nghi); tối đa 8, giá trị lớn hơn bị kẹp về 8 |
| `DEVTEAM_GOVERNOR=off` | Tắt governor (vẫn giữ re-queue spawn lỗi và LANE DOWN) |
| `DEVTEAM_PROVIDER` | `glm` / `anthropic` — ép provider (chỉ ảnh hưởng nhãn stats và peak) |
| `DEVTEAM_PEAK=on/off` | `on`: bật giảm trần một nửa trong giờ cao điểm Z.ai (T2–T6, 14–18h UTC+8) để tiết kiệm credit; mặc định tắt — chạy đủ 8 cả ngày |
| `DEVTEAM_PROOF=off/on` | Ghi đè profile cho proof run: engine tự chạy lại test/verify/lint trong worktree trước khi merge. Mặc định bật ở `strict`/`balanced`, tắt ở `turbo`/`spike` |
| `DEVTEAM_PROOF_TIMEOUT` | Số giây tối đa cho mỗi lệnh của proof run (mặc định 600) |
| `DEVTEAM_UNCLAIMED_S` | Số giây một slice inflight không có claim thì `next` in lại Agent line (mặc định 120; `0` tắt) |
| `DEVTEAM_TRANSCRIPTS_DIR` | Thư mục transcript (định dạng Claude Code) nếu nằm ngoài vị trí mặc định |

## Đã kiểm thử

- `bash scripts/selftest.sh` — **336 check, 336 pass, 0 fail**. Dựng repo git tạm, đi hết vòng đời;
  chạy toàn bộ dưới harness zcode; môi trường test cô lập (HOME tạm, không đọc transcript thật).
- Phần ZCode được kiểm thử bằng `class TestDevteamZcodeCore` (engine/guard chế độ zcode: dispatch bỏ model, chọn strong, provider mặc định glm; guard định tuyến, fail-open, no-op với role lạ) và `class TestDevteamZcodeDoctor` (doctor: cài 6 agent vào `~/.zcode/agents/`, merge hook giữ nguyên key user, re-run no-op, không tạo `.bak`, không ghi `.claude/settings.local.json`), tách khỏi `bash scripts/selftest.sh`.
- **Mutation test**: cố tình phá 13 cơ chế mới (halving, re-queue, leo thang khi retry, effort lite,
  capability, offset transcript, cửa sổ tier, peak, khử trùng request, baseline run mới, relaunch, điều
  kiện tăng, nhận diện hostname) → cả **13/13** đều bị đúng check tương ứng bắt.
- **Review đối kháng độc lập**: 11 phát hiện (5 MAJOR, 6 MINOR: lịch sử run cũ bị tính lại, cắt cửa sổ
  không có tác dụng lúc cao điểm, re-queue nhầm slice đã chạy, dòng JSON lạ làm hỏng `next`, …) — **tất cả đã
  vá**, mỗi lỗi có check hồi quy riêng.
- Định dạng transcript (`api_error`, `isApiErrorMessage`, `attributionAgent`, `perTurnEffort`, `usage`) được
  đối chiếu với transcript thật của Claude Code 2.1.274.

**Giới hạn cần biết:** chưa chạy với tài khoản GLM thật trong môi trường này (không có API key). Các con số
tier là điểm khởi đầu kỹ thuật (Z.ai không công bố), governor sẽ tự chỉnh. Việc Z.ai ánh xạ effort
low/high/max chưa có tài liệu chính thức chi tiết → dùng `devteam stats` để đo (so output token giữa
`glm-programmer-lite` và `glm-programmer-strong`). Hãy thử một task nhỏ trước khi chạy run lớn.

## Nguồn

- Z.ai — GLM-5.3 (1M context, 128K output, thinking luôn bật, effort low/high/max, mặc định max): https://docs.z.ai/guides/llm/glm-5.3
- Z.ai — GLM-5.3-Flash (320B/18B active, DeepSWE 63.4 so với 66.9 của GLM-5.3, quota gấp 3): https://docs.z.ai/guides/llm/glm-5.3-flash
- Z.ai — Claude Code (mapping model, `API_TIMEOUT_MS`, `CLAUDE_CODE_AUTO_COMPACT_WINDOW`): https://docs.z.ai/devpack/tool/claude
- Z.ai — Usage policy (giới hạn đồng thời theo gói, thay đổi động): https://docs.z.ai/devpack/usage-policy
- OpenClaw — mã lỗi 1302/1305, giờ cao điểm: https://docs.openclaw.ai/providers/zai
- Claude Code — biến môi trường (`*_SUPPORTED_CAPABILITIES`, timeout): https://code.claude.com/docs/en/env-vars
- Artificial Analysis qua Qubrid (Flash 57 vs 60, $0.09 vs $0.68/task, output dài hơn trung vị): https://www.qubrid.com/blog/glm-53-flash-benchmarks-official-and-independent-results
- Định dạng lỗi API trong transcript Claude Code: https://github.com/ingo-eichhorst/Irrlicht/issues/1799

## Lịch sử ngắn

- **v4.2 (2026-10-26)** — ghim lại `model` + `thoughtLevel` (lite là Flash/high; thiếu model thì ZCode bỏ qua effort), tắt `injectAgentsMd`, static check import và literal của tiêu chí, `UNCLAIMED` khi launch bị rơi.
- **v4.1 (2026-10-26)** — giảm sai sót cho GLM: engine tự proof run trước khi merge, red proof, static check lúc commit (skip/tautology/TODO/nuốt lỗi), stop gate bắt `## Gate:` có lệnh thật và `## Criteria:`, review fail-closed (APPROVED không có `## Evidence` bị coi là UNKNOWN), validate plan chặt hơn, dòng `LAUNCH N: <ids>` và leo thang `retry <id>` sau 2 lần bị từ chối; biến môi trường `DEVTEAM_PROOF`, `DEVTEAM_PROOF_TIMEOUT`. Prompt: SKILL.md thêm "Conductor discipline" và "Final check" (bảng hành vi đổi thành quy tắc đánh số), programmer thêm "What gets a slice rejected", "Tool mechanics" và checklist cuối, reviewer bắt buộc có `## Evidence` và trích dòng nguyên văn, investigator có loop guard, leader có "Plan self-check".
- **Protocol alignment (2026-10-11)** — theo GLM coding protocol của user: programmer thêm "Verified symbols only" (chỉ gọi API/ký hiệu đã thấy trong repo, contract hoặc source/types của dependency — không bịa API, không tự thêm dependency) và "Fail loudly" (không nuốt lỗi, validate ở biên, không ghi secret); reviewer/spot-reviewer phát hiện API bịa, test bị nới lỏng/skip/mock để pass, lỗi bị nuốt, secret trong log, thiếu authz theo từng resource, flag money/auth/privacy cần human review; leader chạy baseline trước khi lập plan (failure có sẵn ghi vào `notes`), liệt kê stop-and-ask trigger thật, verification report kèm mục Evidence; investigator ghi rõ version đã verify cho claim dependency/API.
- **Agent copy nguyên văn (2026-10-08)** — `doctor --harness zcode` bỏ renderer: bảy file trong `agents/` là bản cuối (frontmatter ZCode, model id thật, `thoughtLevel`), doctor chỉ copy và so sánh byte; bỏ cờ `--flash/--main`; `install-zcode.sh` cũng chỉ copy mọi `agents/*.md` của cả tám skill (không merge hook — hook guard giờ là opt-in qua doctor).
- **thoughtLevel về lại correct ladder (2026-10-08)** — `glm-code-reviewer`, `glm-investigator`, `glm-spot-reviewer` hạ `max` → `high` đúng bảng định tuyến (chỉ leader chạy `max`); `max` giữ cho lane quyết định trên GLM-5.3.
- **Chỉ ZCode (2026-10-08)** — xoá toàn bộ hỗ trợ OpenCode: lane runner (`lane-run`/`wait`/`resume`), file pid/pgid, `doctor --harness opencode`, plugin guard, `oc_harness.py` và các bản vendored; hook ZCode và `selftest.sh` gọi thẳng `guard.py stop`.
- **Tốc độ (2026-10-07)** — tier mặc định `pro` → `api`: cửa sổ mở đủ 8 lời gọi ngay từ đợt đầu; giảm trần giờ cao điểm Z.ai chuyển sang opt-in qua `DEVTEAM_PEAK=on`.
- **ZCode hardening (2026-10-06)** — thêm chế độ harness `zcode`: `is_zcode()` tự nhận, provider mặc định glm; `doctor --harness zcode [--fix] [--flash ID] [--main ID]` cài 7 agent render đúng frontmatter ZCode vào `~/.zcode/agents/` và merge hook PreToolUse/Stop vào `~/.zcode/cli/config.json` (giữ key user, `.bak`, chạy lại là no-op); dispatch bỏ model và chọn strong.
- **v3.2** — `permissionMode: dontAsk` + hook allow-list, Stop gate tự ghi marker (`next` không cần tham số),
  dispatch 1 dòng/agent, vá 7 lỗ allow-list sau review đối kháng.
- **v3.1** — vá 13 lỗ (giả mạo RED, prefix-match permission, `git -C`, verdict fail-closed, fix slice không tin cậy…).
- **v3** — profile `strict/balanced/turbo/spike`, 7 `kind` slice, `next` tự thu hoạch review/checkpoint,
  lập lịch theo critical path có trọng số, `probe`, `review-pr`, `brief-debug`.
