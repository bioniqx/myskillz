# Ghi chú tối ưu — systematic-debugging (Parallel Edition)

Ngày: 2026-08-19. Mục tiêu: tốc độ 10/10, chất lượng 8/10, song song tối đa 64 luồng.

## 1. Nguyên tắc tối ưu cốt lõi

**"Tăng tốc bằng song song hóa điều tra, không bao giờ bằng cắt bớt quy trình."**
Phase 0–2 chỉ đọc (read-only) → fan-out tối đa 64 probe/subagent đồng thời trong MỘT message. Phase 3–4 thay đổi trạng thái → tuần tự nghiêm ngặt (bất biến chất lượng: mỗi lần chỉ đổi 1 biến).

## 2. Thay đổi cụ thể

### SKILL.md (giảm ~55% token nạp vào context)
- 284 dòng → ~120 dòng. Token nạp khi trigger giảm tương ứng → skill kích hoạt và được đọc nhanh hơn, tiết kiệm context cho việc debug thật.
- Thêm **Phase 0 Triage (≤60s)**: bảng tín hiệu → kế hoạch fan-out, quyết định độ rộng song song ngay từ đầu.
- Phase 1 chuyển thành **6 probe P1–P6 độc lập, dispatch đồng thời** thay vì checklist tuần tự. Thêm "merge gate": phải nêu được 1 câu WHERE + WHY kèm bằng chứng mới được sang phase sau.
- Phase 4: **fix tuần tự, verify song song** (shard test suite + lint + build + repro chạy đồng thời).
- Giữ nguyên các yếu tố "bulletproof" đã pass 4 pressure-test: Iron Law, Red Flags, bảng Rationalizations, quy tắc 3 lần fix hỏng → xét lại kiến trúc. Bảng ngụy biện được cập nhật: lý do "khẩn cấp không kịp làm quy trình" bị vô hiệu vì fan-out song song chỉ mất vài phút.
- Cấu trúc chuẩn mới: `references/` + `scripts/` (progressive disclosure — chỉ nạp khi cần).

### scripts/find-polluter.sh (cải thiện lớn nhất về tốc độ thực thi)
- Bản cũ: chạy từng test tuần tự trong repo thật → O(n) lần chạy, và pollution của test trước làm nhiễu test sau.
- Bản mới, 2 chế độ:
  - **scan** (mặc định): mỗi test chạy trong **git worktree cô lập riêng**, tối đa `-j 64` worker đồng thời → tìm TẤT CẢ polluter độc lập trong 1 vòng. Wall-clock: O(n/64). Ví dụ 640 file test × 5s: ~53 phút → ~50 giây.
  - **bisect**: cho pollution phụ thuộc thứ tự — tìm kiếm tiền tố k-ary với các probe chạy song song → O(log n) vòng thay vì O(n).
- Cô lập bằng `git worktree` (rẻ, chia sẻ object store), tự apply thay đổi chưa commit, symlink `node_modules`, retry khi git lock contention, tự dọn dẹp qua trap.
- Tương thích bash 3.2 (macOS mặc định), xargs -P (BSD/GNU đều có).

### references/ (gọn hơn ~45–55%)
- `root-cause-tracing.md`, `defense-in-depth.md`, `condition-based-waiting.md`: bỏ flowchart DOT và phần trùng lặp, giữ toàn bộ quy trình, code mẫu, số liệu thực tế. `defense-in-depth`: ghi chú 4 layer validation độc lập → viết/test song song được.
- `condition-based-waiting-example.ts` giữ nguyên (code chạy được, chỉ nạp theo nhu cầu).

## 3. Đánh đổi có chủ đích (chất lượng 8/10)
- Bỏ redundancy 4 lần lặp "NEVER fix symptom" xuống ~2 vị trí chiến lược (Iron Law + Red Flags) — cognitive friction chính vẫn giữ.
- Phase 3 KHÔNG song song hóa thí nghiệm thay đổi trạng thái (chỉ cho phép điều tra read-only các giả thuyết đối thủ chạy song song) — đây là ranh giới bảo toàn chất lượng.

## 4. Kiểm chứng
- `bash -n` pass; smoke test trên repo giả lập: scan tìm đúng polluter độc lập, bisect tìm đúng polluter phụ thuộc thứ tự (xem log phiên).
- Bộ test chất lượng gốc giữ trong `tests/` (1 academic + 3 pressure) để tái kiểm tra khả năng chống ngụy biện sau mỗi lần chỉnh sửa.
