# dev-team v4.0 — bản tối ưu cho Z.ai GLM-5.3 / GLM-5.3-Flash

Skill Claude Code điều phối nhiều subagent song song (programmer trong git worktree riêng, reviewer /
investigator / leader chỉ đọc). Engine giữ trạng thái và kiểm tra bằng máy (hook + script), không dựa vào
lời dặn. v4 giữ nguyên toàn bộ cơ chế đảm bảo chất lượng của v3.2 và thay mọi giả định dành riêng cho
Anthropic bằng cấu hình đúng cho GLM, cộng thêm bộ **governor** tự điều chỉnh độ song song.

## Vì sao v3.2 chạy kém trên GLM (đã kiểm chứng)

| Giả định của v3.2 | Thực tế khi chạy qua Z.ai | Hệ quả |
|---|---|---|
| Lane chạy `sonnet` = model rẻ/nhanh | Z.ai map `opus` **và** `sonnet` → `glm-5.3`, chỉ `haiku` → `glm-5.3-flash` | Mọi lane chạy GLM-5.3: chậm hơn, tốn ~3× quota |
| `effort: medium/high` trong frontmatter | GLM luôn bật thinking, mặc định `max`; Claude Code chỉ gửi effort cho model bên thứ ba nếu `*_SUPPORTED_CAPABILITIES` có `effort` | Mọi lời gọi chạy ở mức `max`, chậm nhất |
| Mở 64 luồng cùng lúc | Z.ai không công bố giới hạn đồng thời; giới hạn theo gói, thay đổi động, thấp hơn giờ cao điểm | Dính 429/1302 hàng loạt, lane bị retry/backoff, bị treo |
| `subagentPromptCacheTtl: 1h`, `cacheTtl: 1h` | Z.ai tự cache ngầm, TTL 1h của Anthropic không áp dụng | Cấu hình vô ích |
| Mẹo `/fast` | Chỉ có với Opus của Anthropic | Không dùng được |
| Spawn bị runtime từ chối ("Concurrent subagent limit reached") | Slice vẫn đánh dấu đang chạy | Treo vĩnh viễn |

## v4 thay đổi gì

| Hạng mục | v4 |
|---|---|
| **Định tuyến model** | Lane mặc định: GLM-5.3-Flash (`haiku`, effort high). Slice `trivial`/`docs` nhỏ: agent mới **`programmer-lite`** (Flash, effort low; system prompt giống hệt byte-for-byte để dùng chung cache). `risk: high`, `size: large` và **mọi slice phải retry** → GLM-5.3 (`model: opus`). Leader GLM-5.3 effort max, code-reviewer GLM-5.3 high, spot-reviewer/investigator Flash high |
| **doctor --fix cho Z.ai** | Map alias → `glm-5.3` / `glm-5.3-flash`; `*_SUPPORTED_CAPABILITIES=effort,thinking` (để effort thật sự được gửi đi); `API_TIMEOUT_MS=3000000`, `CLAUDE_CODE_AUTO_COMPACT_WINDOW=1000000`, `CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1` (theo tài liệu Z.ai); bỏ TTL cache kiểu Anthropic. Không bao giờ ghi token hay base URL. Nâng cấp mapping GLM cũ, giữ nguyên mapping tuỳ chỉnh có chủ đích |
| **Governor (AIMD)** | Cửa sổ song song khởi đầu theo gói (`DEVTEAM_GLM_TIER`/`--tier`: lite 3/8, pro 6/20, max 10/40, api 16/64). Tăng dần khi lane hoàn thành (chỉ khi cửa sổ đang được dùng hết), **giảm một nửa** khi transcript có 429/1302/1305/overload (tối đa một lần mỗi 90 giây), trần giảm một nửa trong giờ cao điểm Z.ai (T2–T6, 14–18h UTC+8, tức 13–17h giờ Việt Nam) |
| **Tự phục hồi** | Spawn bị từ chối/lỗi → đưa slice về hàng đợi (không re-queue nếu Conductor đã tự launch lại thành công); lỗi "agent type not found" lặp lại → báo cần restart Claude Code; lane chết vì lỗi API → in `LANE DOWN` kèm cách sửa warm (`SendMessage "continue"`) |
| **`devteam stats`** | Số liệu **đo được** từ transcript của Claude Code theo role/model: số request (khử trùng lặp theo requestId), output token, tỉ lệ cache hit, effort thực gửi, lỗi API, thời gian chạy; cảnh báo nếu effort không được gửi |
| **SKILL.md** | 25,4 KB → ~17,9 KB: ngắn gọn, dạng mệnh lệnh, ưu tiên "mỗi turn = 1 lệnh engine + launch song song" (GLM luôn thinking nên mỗi turn thừa đều đắt), thêm `effort: high` cho Conductor |
| **Agent prompts** | Bỏ nhắc sonnet/opus/64; thêm quy tắc "ít turn, gộp đọc file thành tool call song song" (mỗi turn là một lần gọi model có thinking) |
| Anthropic | Vẫn chạy được (`DEVTEAM_PROVIDER=anthropic` hoặc tự nhận từ base URL): routing, chi phí và TTL cache giữ nguyên như v3 |

## Cài đặt

```
.claude/skills/dev-team/      ← copy nguyên thư mục (hoặc ~/.claude/skills/dev-team)
  SKILL.md  README.md
  scripts/devteam.py  scripts/guard.py  scripts/selftest.sh
  agents/*.md                 ← doctor --fix cài 6 agent vào .claude/agents/
```

1. Cấu hình Claude Code dùng Z.ai (theo docs.z.ai/devpack/tool/claude), trong `~/.claude/settings.json`:
   `ANTHROPIC_BASE_URL=https://api.z.ai/api/anthropic`, `ANTHROPIC_AUTH_TOKEN=<key>`.
2. Trong repo: `python3 .claude/skills/dev-team/scripts/devteam.py doctor --fix` (hoặc bỏ qua: `start` tự chạy).
3. **Khởi động lại Claude Code** (env và agent mới chỉ được nạp lúc khởi động). Kiểm tra bằng `/status`.
4. Khai báo gói: `export DEVTEAM_GLM_TIER=lite|pro|max|api` (hoặc `"glm": {"tier": "…"}` trong plan).
5. Sau run đầu tiên: `devteam stats` — kiểm tra cột "effort sent" có `high`/`low` (không phải `None`),
   xem cache hit và lỗi API để chọn tier hợp lý.

Yêu cầu: Claude Code ≥ 2.1.267, git ≥ 2.31, python3. Phải trust đúng thư mục repo (hook trong frontmatter
agent chỉ nạp khi thư mục đó được trust).

### OpenCode

Trên OpenCode, engine tự nhận harness qua `oc_harness.harness()` khi có một trong các dấu hiệu sau: `OPENCODE` hoặc `OPENCODE_TERMINAL` được set (v2 chỉ set `OPENCODE_TERMINAL=1`), `DEVTEAM_HARNESS=opencode`, skill nằm trong thư mục skills của OpenCode, hoặc có file `.oc-major` cạnh scripts. Khi đó devteam chạy mỗi lane trong một git worktree riêng qua `oc_harness run`:

1. **Cài đặt:** chạy `python3 devteam.py doctor --harness opencode --fix` (hoặc `sh install-opencode.sh --major 1|2` cho 5 skill GLM còn lại). Lệnh này copy plugin guard (v1 hoặc v2 tùy major version) và các agent vào home OpenCode.
2. **Bootstrap:** OpenCode không set `${CLAUDE_SKILL_DIR}`, nên SKILL.md mở đầu bằng một vòng `for` tìm `scripts/devteam.py` theo thứ tự: dòng "Base directory for this skill", `$OPENCODE_CONFIG_DIR/skills`, `.opencode/skills`, `~/.config/opencode/skills`, rồi `.agents`, `~/.agents`, `.claude`, `~/.claude`, `~/.zcode`. Không tìm thấy thì báo lỗi rõ ràng và thoát với mã 1, không bao giờ chạy `python3 "" …`.
3. **Worktree:** với mỗi lane programmer, `lane-run` (không phải `devteam start`) tạo worktree tại `.claude/dev-team/wt/<id>` trên branch `devteam/<id>` từ base của slice, rồi chạy `claim` trong worktree đó và ghi env `DEVTEAM_ROLE`/`DEVTEAM_SLICE`.
4. **Vòng lặp:** `devteam wait` chặn tối đa 100 s để đợi kết quả lane, rồi `devteam next` đọc output JSON và dispatch lane mới cùng các retry. `wait` trả về ngay khi không còn lane nào đang chạy. Trên v2, tool shell có `background: true` (không timeout, tự báo khi xong): chạy `devteam wait --timeout 3600` ở nền rồi kết thúc lượt. Thông báo hoàn tất chính là tín hiệu đánh thức, không cần hỏi vòng.
5. **Stop gate:** sau mỗi programmer lane, `lane-run` (không phải `devteam next`) gọi `guard.py stop` với `{"cwd": <worktree>, "last_assistant_message": <text>}`. Exit 2 nghĩa là bị chặn: lane chạy lại tối đa 2 lần, với stderr của gate thêm vào brief, và bộ đếm nằm ở `.slice/stop_blocks`. Nếu lane lỗi mà HEAD vẫn bằng base, engine ghi `.blocked` kèm lỗi của lane thay vì chạy lại vô ích.
6. **Markers:** `.done` và `.blocked` ghi vào `.claude/dev-team/slices/<id>.*` (stop gate). Output của lane ghi vào `.claude/dev-team/lanes/<id>.jsonl|.err|.done` (runner).
7. **Stall và tiến trình:** stall tính theo role, khoảng 900 s cho programmer/team-leader và 600 s cho reviewer, nên test/build dài không bị giết oan. Process group của opencode được ghi vào `lanes/<id>.pgid`, và engine `killpg` theo file đó nên không để lại process mồ côi. Checkpoint được chạy tách nền giống lane, và `wait` báo khi nó xong. Trần 20 agent của Claude không áp cho OpenCode, nên đạt được trần tier 40/64. Slice `programmer-lite` chạy đúng agent lite (effort low) trên cả v1.
8. **Tool guards:** plugin v1/v2 pipe JSON (giống hook của Claude) đến `guard.py oc`. Programmer dùng bộ kiểm tra hiện có. Role khác chỉ được đọc, nhưng vẫn chạy được `devteam status`/`devteam probe`. Khi thiếu `DEVTEAM_ROLE`, plugin v2 lấy role từ `agent` của event nếu đó là role dev-team. Trong lane, `batch`, `question` và `execute` bị chặn, vì `question` headless sẽ treo. OpenCode không có prompt tương tác, nên một lệnh chưa được duyệt trước, hoặc một lượt ghi của programmer ra ngoài worktree của chính slice đó, đều bị TỪ CHỐI thẳng chứ không chờ hỏi. Thông báo từ chối liệt kê các dạng `.slice/allow` đã pin. Lỗi phía plugin vẫn cho qua (fail-open, vì bước integrate kiểm tra lại), nhưng plugin cảnh báo rõ một lần mỗi lane và ghi lỗi vào log lane.
9. **Sửa lỗi và retry:** OpenCode không có SendMessage vì lane là process chạy một lần. Câu trả lời cho `BLOCKED`, hay cách sửa cho `REJECTED` / `NOT READY` / `MERGE ERROR`, đi qua `devteam resume <id> --note "…"`: lệnh này chạy một lane mới trong **cùng** worktree và reset `.slice/stop_blocks`. Chỉ khi resume không cứu được mới dùng `devteam retry <id>`, lệnh tạo worktree mới, nâng lên GLM-5.3 và có thể mở rộng file scope. Engine tự dừng lane cũ.
10. **Lane chết:** governor đọc file lane (`.claude/dev-team/lanes/<id>.done`) thay vì transcript. Lane kết thúc `FAIL`/`STALL`/`TIMEOUT`, hoặc pid đã chết mà không có `.end` hay marker (bị signal giết), thì engine in `LANE DOWN <id> (<kind>)` kèm cách sửa. Với slice: `fail <id>` rồi `retry <id>` (worktree bị xoá, chỉ giữ branch `attempt/<id>-N` để cứu dữ liệu). Với review/research: chạy lại lệnh engine in ra. Lệnh đó đã có tiền tố `python3`, chạy tách nền và xoá `.done` cũ; dấu `&` trơn sẽ làm tool bash của OpenCode v1 bị treo tới khi lane xong.
11. **Doctor:** `python3 devteam.py doctor --harness opencode` kiểm tra agent, plugin, config và việc major version có khớp không.
12. **Chỉ dispatch qua engine:** agent dev-team chỉ được khởi chạy qua lane của engine (`devteam next` / `lane-run`), nơi gán `DEVTEAM_ROLE`/`DEVTEAM_SLICE` cho từng lane. Không bao giờ dispatch role dev-team bằng tool `task` (v1) hay `subagent` (v2) của OpenCode. Agent built-in của OpenCode là `general`; ở đó không có `general-purpose` hay `Explore`.

## Biến môi trường

| Biến | Tác dụng |
|---|---|
| `DEVTEAM_GLM_TIER` | `lite` / `pro` (mặc định) / `max` / `api` — cửa sổ khởi đầu của governor |
| `DEVTEAM_MAX_PARALLEL=N` | Ghim cứng số agent chạy song song (tắt thích nghi) |
| `DEVTEAM_GOVERNOR=off` | Tắt governor (vẫn giữ re-queue spawn lỗi và LANE DOWN) |
| `DEVTEAM_PROVIDER` | `glm` / `anthropic` — ép provider |
| `DEVTEAM_PEAK=on/off` | Ép trạng thái giờ cao điểm (dùng cho test) |
| `DEVTEAM_TRANSCRIPTS_DIR` | Thư mục transcript nếu Claude Code lưu ở chỗ khác |

## Đã kiểm thử

- `bash scripts/selftest.sh` — **308 check, 308 pass** (247 check cũ vẫn giữ, 61 check mới cho v4). Dựng
  repo git tạm, đi hết vòng đời; môi trường test cô lập (HOME tạm, không đọc transcript thật).
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
`programmer-lite` và `programmer`). Hãy thử một task nhỏ trước khi chạy run lớn.

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

- **OpenCode hardening (2026-09-28)** — v1 1.18.x và v2 2.0.x: bootstrap tìm thư mục skill mà không cần `${CLAUDE_SKILL_DIR}`; nhận v2 qua `OPENCODE_TERMINAL`; `resume <id> --note` thay cho SendMessage; stall theo role; checkpoint chạy tách nền; `wait` thoát khi không còn lane; `killpg` qua `lanes/<id>.pgid`; guard chặn `batch`/`question`/`execute` trong lane; báo LANE DOWN cho lane bị signal giết.
- **v3.2** — `permissionMode: dontAsk` + hook allow-list, Stop gate tự ghi marker (`next` không cần tham số),
  dispatch 1 dòng/agent, vá 7 lỗ allow-list sau review đối kháng.
- **v3.1** — vá 13 lỗ (giả mạo RED, prefix-match permission, `git -C`, verdict fail-closed, fix slice không tin cậy…).
- **v3** — profile `strict/balanced/turbo/spike`, 7 `kind` slice, `next` tự thu hoạch review/checkpoint,
  lập lịch theo critical path có trọng số, `probe`, `review-pr`, `brief-debug`.
