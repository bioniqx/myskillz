# writing-plans v8 (max-parallel) — thay đổi so với v7

## Sửa lỗi nghiêm trọng về song song
- Claude Code mặc định chỉ cho **20 subagent chạy cùng lúc** (`CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS`). v7 bắn 64 writer trong một message → từ writer thứ 21 bị từ chối "Concurrent subagent limit reached". v8 đọc giới hạn thật, tự gom task vào ≤ cap writer (chia cân bằng theo khối lượng), và `setup --apply` nâng lên 64.

## Nhanh hơn ở orchestrator (nút thắt tuần tự)
- Context repo + bản đồ heading của spec được **inject lúc load skill** (`!` command) → bỏ 1 vòng tool.
- Orchestrator không còn gõ Execution Protocol, File Structure, Waves, `Parallel:`, Depends suy ra từ Consumes, Interfaces — script sinh hết.
- Prompt mỗi writer còn 1 dòng (`Read <brief> and follow it exactly.`).

## Nhanh hơn ở writer
- Script tạo **brief riêng cho từng writer**: hợp đồng, dòng spec đã cắt sẵn, file hiện có đã inline kèm số dòng, luật lint đầy đủ → writer chỉ đọc 1 file.
- Luật cứng cấm writer đọc script/khám phá repo (đo thực tế: đây là nguyên nhân chính làm writer chậm).
- Agent tùy chọn `plan-task-writer`: sonnet, effort medium, không nạp CLAUDE.md, hook PostToolUse tự lint sau Write/Edit → bớt 1 lượt/writer.
- `Tier: light|deep` → haiku / sonnet / opus theo độ khó.
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
1. Giải nén vào `~/.claude/skills/writing-plans/` (skill sync từ claude.ai sẽ không chạy lệnh `!`).
2. Một lần: `python3 ~/.claude/skills/writing-plans/scripts/plan_tool.py setup` (xem trước) → `--apply` → khởi động lại Claude Code.
