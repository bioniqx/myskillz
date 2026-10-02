# oc-dev-team v5.0 — chạy thuần trên OpenCode v2

Bộ điều phối nhiều lane song song trên OpenCode v2: mỗi programmer làm việc trong một git worktree riêng của lane, còn reviewer / investigator / leader chỉ đọc. Engine (`scripts/oc_devteam.py`) giữ trạng thái và kiểm tra bằng máy (guard + script), không dựa vào lời dặn. Conductor và mọi lane đều chạy trên model đang được chọn trong cửa sổ OpenCode: không đặt provider, model, variant hay effort nào, không gọi API trực tiếp và không mở tiến trình `opencode` nào.

## v5.0 thay đổi gì

| Hạng mục | v5.0 |
|---|---|
| **Lane** | Mỗi lane là một lần gọi tool `subagent` với `background=true` do Conductor phát ra từ dòng engine in. Không còn tiến trình `opencode run`, `lane-run`, file jsonl của lane hay `oc_harness.py run` |
| **Dispatch** | `dispatch`, review batch và `verify-brief` tạo worktree `.opencode/oc-dev-team/wt/<id>` (branch `oc-devteam/<id>`, từ base đã ghi của slice) rồi in một dòng dispatch. Prompt của programmer là lệnh `claim` kèm đường dẫn worktree. `resume` và `retry` in lại dòng |
| **Claim** | `claim <id> --worktree <path>` lấy worktree từ tham số thay vì thư mục hiện tại và in brief. Brief dặn programmer truyền `workdir=<worktree>` cho mọi lệnh `shell` và dùng đường dẫn tuyệt đối trong worktree cho `read`/`edit`/`write` (subagent không có cấu hình thư mục làm việc) |
| **Report** | `report <id> --file <report.md>` thay cho stop gate: gọi `guard_stop`, in lỗi ngay trong output khi exit 2 (programmer sửa rồi report lại), thành công thì ghi marker `slices/<id>.done` hoặc `.blocked`. `MAX_STOP_BLOCKS` (2) vẫn ép hoàn tất |
| **Guard** | `oc_guard.py` chỉ còn `oc` và `stop`. `guard_oc` xác định lane từ path của `edit`/`write` hoặc `workdir` của `shell` nằm dưới `.opencode/oc-dev-team/wt/<id>/`; role chỉ lấy từ `event.agent` của plugin. Ghi ra ngoài worktree, hoặc gọi `shell` không có `workdir`, bị TỪ CHỐI kèm thông báo nêu worktree |
| **Model** | Không còn định tuyến model. Một model duy nhất chạy mọi lane; agent `programmer-lite` bị xoá, slice `trivial` đi qua `oc-programmer`; `dispatch_route` chỉ trả về tên agent |
| **Song song** | Không còn governor. `concurrency_limit()` trả về `HARD_CAP`; không còn cắt đôi cửa sổ hay LANE DOWN |
| **Thư mục trạng thái** | `.opencode/oc-dev-team/` |
| **Biến môi trường** | Gỡ toàn bộ biến chọn provider, tier, governor, giờ cao điểm, harness, role và slice của lane. `ENGINE_VERSION` là `5.0` |
| **Tài liệu** | SKILL.md và README này được viết lại, không còn nội dung dành cho một provider cụ thể |

## Cài đặt

```
oc-dev-team/                    ← thư mục nguồn; được copy thành ~/.config/opencode/skills/oc-dev-team/
  SKILL.md  README.md
  scripts/oc_devteam.py  scripts/oc_guard.py  scripts/oc_harness.py  scripts/oc-selftest.sh
  opencode/agents/*.md          ← agent không có dòng model/effort
  opencode/plugins/devteam-guard.v2.js
```

1. Chạy `sh install-opencode.sh`: script copy skill, các agent và plugin guard vào thư mục cấu hình OpenCode.
2. Khởi động lại OpenCode một lần nếu agent hoặc plugin vừa thay đổi.

Yêu cầu: OpenCode 2.0.x (kiểm chứng với 2.0.20), git ≥ 2.31, python3; node là tuỳ chọn (chỉ để selftest chạy thử plugin).

## Cách hoạt động

1. **Bootstrap:** OpenCode không set biến thư mục skill, nên SKILL.md mở đầu bằng một vòng `for` tìm `scripts/oc_devteam.py` theo thứ tự: dòng "Base directory for this skill", `$OPENCODE_CONFIG_DIR/skills`, `.opencode/skills`, `~/.config/opencode/skills`, rồi `.agents`, `~/.agents`. Không tìm thấy thì báo lỗi rõ ràng và thoát với mã 1, không bao giờ chạy `python3 "" …`.
2. **Dispatch:** `devteam start <plan.md>` (rồi `devteam next` ở mỗi lần được đánh thức) tạo worktree của từng lane sẵn sàng tại `.opencode/oc-dev-team/wt/<id>` và in mỗi lane một dòng `subagent` chạy nền. Conductor phát tất cả các dòng trong MỘT message rồi kết thúc lượt.
3. **Claim:** programmer chạy `claim <id> --worktree <path>` để nhận brief. Mọi lệnh `shell` của nó phải có `workdir=<worktree>`; `read`/`edit`/`write` dùng đường dẫn tuyệt đối trong worktree.
4. **Report:** programmer ghi báo cáo cuối ra file rồi chạy `report <id> --file <report.md>`. Lệnh này đưa `{"cwd": <worktree>, "last_assistant_message": <nội dung báo cáo>}` vào `guard_stop`. Exit 2 nghĩa là bị chặn: các vấn đề được in ngay trong output, programmer sửa rồi report lại; sau 2 lần bị chặn thì ép hoàn tất. Thành công thì ghi marker `.opencode/oc-dev-team/slices/<id>.done` (hoặc `.blocked` với báo cáo `Blocked`).
5. **Vòng lặp:** `devteam wait` chỉ poll các marker (và checkpoint đã xong) rồi in `NEXT: devteam next`; tool `shell` của v2 có `background: true`, nên chạy `devteam wait --timeout 3600` ở nền rồi kết thúc lượt, thông báo hoàn tất chính là tín hiệu đánh thức. `devteam next` thu hoạch marker, file báo cáo và log checkpoint, merge, xếp hàng fix, dispatch lane mới và in phần endgame.
6. **Tool guards:** plugin v2 pipe JSON đến `oc_guard.py oc`. Programmer dùng bộ kiểm tra footprint; role khác chỉ được đọc nhưng vẫn chạy được `devteam status`/`devteam probe`. Một lệnh chưa được duyệt trước bị TỪ CHỐI thẳng chứ không chờ hỏi; thông báo từ chối liệt kê các dạng `.oc-slice/allow` đã pin. Lỗi phía plugin vẫn cho qua (fail-open, vì bước integrate kiểm tra lại), nhưng plugin cảnh báo rõ một lần.
7. **Sửa lỗi và retry:** lane chỉ chạy một lần. Câu trả lời cho `BLOCKED`, hay cách sửa cho `REJECTED` / `NOT READY` / `MERGE ERROR`, đi qua `devteam resume <id> --note "…"`: lệnh này in lại dòng dispatch cho **cùng** worktree và reset bộ đếm stop. Chỉ khi resume không cứu được mới dùng `devteam retry <id>`, lệnh tạo worktree mới và có thể mở rộng file scope; worktree cũ bị xoá, chỉ giữ branch `attempt/<id>-N` để cứu dữ liệu.
8. **Chỉ dispatch qua dòng của engine:** lane programmer / reviewer / investigator chỉ được khởi chạy từ dòng engine in ra, vì guard xác định lane từ đường dẫn worktree. Conductor tự chạy `oc-team-leader` (lập kế hoạch) và agent built-in `general` (đọc code). Ở OpenCode không có `general-purpose` hay `Explore`.

## Đã kiểm thử

- `bash scripts/oc-selftest.sh` — dựng repo git tạm, đi hết vòng đời (init, dispatch, claim `--worktree`, RED/GREEN, integrate, checkpoint, review, report, resume, retry, guard `oc`, plugin v2). Môi trường test cô lập (HOME tạm) và không khởi chạy tiến trình `opencode` nào. Đã bỏ phần governor/provider, các check hook của harness khác và toàn bộ check tiến trình lane; các check engine giữ nguyên. Trên macOS có 5 check lỗi từ trước do khác biệt userland BSD; hãy chạy trên Linux trước khi tin một kết quả đỏ.
- `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s _shared/tests -t _shared/tests` — bộ test Python chung.

## Lịch sử ngắn

- **v5.0** — chỉ OpenCode v2, chạy trên model của cửa sổ OpenCode; lane là lần gọi `subagent` chạy nền từ dòng engine in; `claim <id> --worktree`, `report <id> --file` thay stop gate; bỏ định tuyến model, governor, `programmer-lite` và mọi cấu hình provider; thư mục trạng thái `.opencode/oc-dev-team`; `oc_guard.py` chỉ còn `oc` và `stop`; selftest và tài liệu viết lại.
- **OpenCode hardening (2026-09-28)** — bootstrap tìm thư mục skill mà không cần biến môi trường; nhận v2 qua `OPENCODE_TERMINAL`; `resume <id> --note` để trả lời một lane đã thoát; stall theo role; checkpoint chạy tách nền; `wait` thoát khi không còn lane; `killpg` qua `lanes/<id>.pgid`; guard chặn `batch`/`question`/`execute` trong lane; báo LANE DOWN cho lane bị signal giết.
- **v3.2** — `permissionMode: dontAsk` + hook allow-list, Stop gate tự ghi marker (`next` không cần tham số),
  dispatch 1 dòng/agent, vá 7 lỗ allow-list sau review đối kháng.
- **v3.1** — vá 13 lỗ (giả mạo RED, prefix-match permission, `git -C`, verdict fail-closed, fix slice không tin cậy…).
- **v3** — profile `strict/balanced/turbo/spike`, 7 `kind` slice, `next` tự thu hoạch review/checkpoint,
  lập lịch theo critical path có trọng số, `probe`, `review-pr`, `brief-debug`.
