# claude-writing-plans v8 (max-parallel) — thay đổi so với v7

Ghi chú nhãn phiên bản: `claude-writing-plans-6.2` là tên thư mục cài đặt; `v8` là số phiên bản nội bộ của skill (cùng một bản phát hành).

## Sửa lỗi nghiêm trọng về song song
- Claude Code mặc định chỉ cho **20 subagent chạy cùng lúc** (`CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS`). v7 bắn 64 writer trong một message → từ writer thứ 21 bị từ chối "Concurrent subagent limit reached". v8 đọc giới hạn thật, tự gom task vào ≤ cap writer (chia cân bằng theo khối lượng), và `setup --apply` nâng lên 64.

## Nhanh hơn ở orchestrator (nút thắt tuần tự)
- Context repo + bản đồ heading của spec được **inject lúc load skill** (`!` command) → bỏ 1 vòng tool.
- Orchestrator không còn gõ Execution Protocol, File Structure, Waves, `Parallel:`, Depends suy ra từ Consumes, Interfaces — script sinh hết.
- Prompt mỗi writer còn 1 dòng (`Read <brief> and follow it exactly.`).

## Nhanh hơn ở writer
- Script tạo **brief riêng cho từng writer**: hợp đồng, dòng spec đã cắt sẵn, file hiện có đã inline kèm số dòng, luật lint đầy đủ → writer chỉ đọc 1 file.
- Luật cứng cấm writer đọc script/khám phá repo (đo thực tế: đây là nguyên nhân chính làm writer chậm).
- Agent tùy chọn `claude-plan-task-writer`: sonnet, effort medium, không nạp CLAUDE.md, hook PostToolUse tự lint sau Write/Edit → bớt 1 lượt/writer.
- `Tier: light|deep` chỉ ảnh hưởng việc chọn task để review (deep luôn được review); mọi writer đều chạy sonnet.
- `wait` chặn đến khi mọi task lint OK (không phải xử lý 64 notification).

## Kiểm tra máy móc mạnh hơn (thay review bằng model)
- Kiểm cú pháp code block: Python, JSON, TOML, bash, JS (`fragment` để bỏ qua đoạn cố ý dở dang).
- File trong task ⊆ Files của hợp đồng; `git add` chỉ đường dẫn tường minh thuộc task; mỗi `Run:` có `Expected:`; bước đánh số liên tục; Create/Modify khớp trạng thái đĩa.
- Task dùng chung file tự được xếp thứ tự (`Runs after`), cảnh báo "hot file" làm tuần tự hóa.
- Review theo rủi ro (deep / dài / nhiều phụ thuộc / có WARN), `--thorough` để review tất cả; mỗi reviewer 1 slot riêng.

## Benchmark A/B (cùng repo, cùng 4 hợp đồng, n=1 — sai số LLM lớn)
| | v7 | v8 |
|---|---|---|
| Wall-clock fan-out (task chậm nhất) | 275 s | 163 s |
| Tổng thời gian writer | 543 s | 314 s |
| Tool calls | 33 | 12 (3/writer) |
Script: `contracts` 70 task < 0.25 s, `assemble` 70 task 0.3 s.

## Cài đặt
1. Giải nén vào `~/.claude/skills/claude-writing-plans-6.2/` (skill sync từ claude.ai sẽ không chạy lệnh `!`).
2. Một lần: `python3 ~/.claude/skills/claude-writing-plans-6.2/scripts/plan_tool.py setup` (xem trước) → `--apply` → khởi động lại Claude Code.

## W8 — preload không bao giờ hủy skill, context bị giới hạn, hash hợp đồng, mark warn/fail, phát hiện agent cũ, assemble/wait nhanh hơn
- Preload `!` giờ truyền `"$ARGUMENTS"` như MỘT token đã quote; `context` luôn thoát mã 0 kể cả với đối số rỗng, dấu ngoặc kép bên trong, đường dẫn không tồn tại, HEAD detached, repo chưa có commit, hoặc ngoài git repo — không còn nguy cơ hủy cả skill vì lỗi shell-split.
- `context` dùng `git --no-optional-locks` cho mọi lệnh git (không đụng mtime của index) và giới hạn danh sách file hiển thị còn ≤30 (tổng đầu ra ≤~55 dòng) kể cả trên repo 300+ file.
- `contracts` giờ băm (sha256) nội dung từng hợp đồng; nếu một hợp đồng đổi, script xóa đúng `TXX.md` + `TXX.md.ok` (và các mark khác) của task đó, giữ nguyên các task khác không đổi.
- `lint-task` và `hook-lint` dùng chung một hàm đánh dấu: lint có warning ghi `.warn`, lint sạch xóa `.warn` cũ, lint lỗi ghi `.fail` (và `.fail` được xóa khi lint lại sạch).
- `context` phát hiện agent `claude-plan-task-writer` cài sẵn nhưng còn dính placeholder `__PLAN_TOOL__` (chưa chạy `setup --apply`) và luôn cảnh báo, kể cả khi cap subagent đã ở mức tối đa.
- `wait` trả về `PENDING` sớm khi mọi task còn lại đều đang `.fail` và không đổi ≥45 giây, thay vì đợi hết `--idle`/`--timeout`.
- `assemble` chạy `node --check` cho các code block song song giữa các task thay vì tuần tự.
- Reviewer brief giờ inline sẵn nội dung file đích hiện có (giống writer brief), reviewer không cần đọc thêm.
- SKILL.md: bỏ nhắc "ultracode", thêm lời khuyên `--allow` ngay ở Phase 1, hand-off trỏ về skill `claude-dev-team` thay vì `superpowers:*` (không còn tồn tại), và mục "One-time speed setup" nêu rõ nó cũng xử lý agent cũ/placeholder.
