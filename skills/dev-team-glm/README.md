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

- **v3.2** — `permissionMode: dontAsk` + hook allow-list, Stop gate tự ghi marker (`next` không cần tham số),
  dispatch 1 dòng/agent, vá 7 lỗ allow-list sau review đối kháng.
- **v3.1** — vá 13 lỗ (giả mạo RED, prefix-match permission, `git -C`, verdict fail-closed, fix slice không tin cậy…).
- **v3** — profile `strict/balanced/turbo/spike`, 7 `kind` slice, `next` tự thu hoạch review/checkpoint,
  lập lịch theo critical path có trọng số, `probe`, `review-pr`, `brief-debug`.
