# 01 — Hướng dẫn Dev dùng Claude Code với bộ tài liệu này

> Dành cho Dev mới dùng Claude Code lần đầu. Đọc 10 phút, làm theo đúng thứ tự.
> Nguyên tắc số 1: **Claude Code viết code, BẠN chịu trách nhiệm** — luôn đọc diff, luôn chạy test.

## 1. Cài đặt (một lần)

```bash
npm install -g @anthropic-ai/claude-code
cd <thư-mục-repo-miyano_portal>
claude          # lần đầu sẽ hướng dẫn đăng nhập tài khoản
```

Gõ `claude` trong thư mục repo là vào phiên chat ngay trong terminal. Thoát: `Ctrl+C` hai lần.
Phím cần nhớ: `Esc` = ngắt khi AI đang làm sai hướng · `/clear` = xoá ngữ cảnh, bắt đầu việc mới ·
`/help` = xem lệnh.

## 2. Chuẩn bị repo (một lần)

1. Copy `CLAUDE.md` (trong thư mục này) vào **thư mục gốc của repo** — Claude Code tự đọc file này
   mỗi phiên. Không có nó, AI sẽ không biết các quy tắc cấm.
2. Copy cả thư mục `DevHandoff/` + 2 file `BA-miyano_portal_v2.md`, `FormSpec-miyano_portal_v2.md`
   vào repo (ví dụ để trong `docs/`).
3. Tạo nhánh riêng cho mỗi epic: `git checkout -b feature/e3-giao-nhieu-dot`.

## 3. Vòng làm việc chuẩn (lặp lại cho mỗi User Story)

```
Bước 1  ĐỌC TAY (không nhờ AI): mở PRD epic → đọc đúng 1 User Story + AC của nó
Bước 2  BẢO AI LẬP KẾ HOẠCH TRƯỚC — chưa cho viết code:
        "Đọc CLAUDE.md và docs/DevHandoff/12_PRD_E3_GiaoNhieuDot_DoiSoat.md.
         Lập kế hoạch hiện thực US-E3.3 (các file sẽ sửa, hàm sẽ thêm, test sẽ viết).
         CHƯA viết code."
Bước 3  Đọc kế hoạch. Thấy hợp lý (đúng file, đúng cách BA mô tả) → "OK, làm theo kế hoạch"
Bước 4  ĐỌC DIFF từng file AI sửa. Không hiểu dòng nào → hỏi ngay:
        "Giải thích tại sao sửa chỗ này?"
Bước 5  Chạy test:  bench --site erptest.local run-tests --app miyano_portal
        Đỏ → dán nguyên văn lỗi vào chat: "Test fail như sau, sửa đi: <paste>"
Bước 6  Xanh hết (kể cả 339 test cũ) → commit nhỏ:
        git add -A && git commit -m "E3: US-E3.3 chênh lệch nhận hàng"
Bước 7  Story tiếp theo → quay lại Bước 1. Xong epic → /clear rồi mới sang epic khác.
```

**Đừng** ném cả epic vào một prompt. Mỗi lần một User Story — AI làm chuẩn hơn, bạn review nổi.

## 4. Prompt mẫu theo tình huống (copy & sửa tên mã)

| Tình huống | Prompt |
|---|---|
| Bắt đầu epic | `Đọc CLAUDE.md, docs/DevHandoff/13_PRD_E4_KhoKhach_NCC_DotHang.md. Tóm tắt những gì phải làm và những gì ĐÃ CÓ SẴN không được viết lại.` |
| Tạo doctype mới | `Tạo DocType "Customer Supplier" đúng từng trường trong docs/DevHandoff/20_DataDict.md mục 1.1, kèm patch cài đặt idempotent. Không cấp DocPerm cho role Customer.` |
| Viết endpoint | `Viết endpoint kho_ncc_save trong api/kho.py đúng spec docs/DevHandoff/30_API_Spec.md mục 3.1: dùng get_portal_kho(), validate BR-N3, trả goi_y_trung. Kèm test.` |
| Viết test từ TC | `Viết test cho nhóm TC-E4 trong docs/DevHandoff/40_TestCases.md, đúng bộ số kỳ vọng (TC-E4-08: FIFO 100+50, xuất 120 → còn 0 và 30).` |
| Dựng UI | `Dựng màn /portal/kho/ncc theo FormSpec F-17. Tham chiếu markup mẫu trong docs/DevHandoff/50_Prototype_ClientPortal_v2.html (id pg-kncc). Gọi API bằng fetch + CSRF, không dùng frappe.call.` |
| Test fail | `bench run-tests fail: <dán nguyên văn>. Sửa CODE cho đúng AC, không sửa test cho qua — trừ khi test sai so với AC, khi đó giải thích trước.` |
| Hiểu code cũ | `Giải thích luồng delivery_hook.on_delivery_note_submit hiện tại: vào ra là gì, vì sao không được ném lỗi?` |
| Tự review | `/review` hoặc: `Review diff so với AC của US-E3.3 và 10 quyết định nền tảng trong CLAUDE.md. Liệt kê vi phạm nếu có.` |

## 5. Năm quy tắc an toàn — thuộc lòng

1. **Không bao giờ accept diff chưa đọc.** AI viết nhanh nhưng tự tin cả khi sai.
2. **AI đề xuất "gộp cho gọn" / dùng Warehouse, Stock Entry của ERPNext cho kho khách / sửa thẳng
   Lot Balance / bỏ qua check quyền → DỪNG.** Đó là vi phạm CLAUDE.md. Trả lời:
   `Vi phạm quyết định nền tảng số N trong CLAUDE.md. Làm lại theo đúng quy tắc.` Còn nghi ngờ → hỏi BA.
3. **Mỗi thay đổi = chạy lại toàn bộ test.** 339 test cũ đỏ là lỗi của thay đổi mới, không phải "kệ nó".
4. **`bench migrate` chạy 2 lần liên tiếp phải không lỗi** (patch idempotent) trước khi commit patch.
5. **Commit nhỏ theo từng US, nhánh riêng theo epic.** Sai thì revert 1 commit, không mất cả tuần.

## 6. Checklist trước khi tạo Pull Request

- [ ] Mọi AC của các US trong phạm vi PR đều có test và pass
- [ ] 339 test cũ + test mới: xanh · `bench migrate` ×2: sạch
- [ ] Thông điệp lỗi đúng nguyên văn FormSpec §5 (tiếng Việt, đúng biến)
- [ ] Endpoint mới: không nhận `customer`/`kho` từ client; đã có test cách ly 2 khách
- [ ] Không có DocPerm mới cho role `Customer`; không URL file công khai
- [ ] UI khớp Prototype (mở `50_Prototype...html` đặt cạnh mà so)
- [ ] Mô tả PR ghi rõ: mã US/AC đã làm, mã VĐ còn treo (nếu có)

## 7. Khi bí

Bí về **nghiệp vụ** (AC khó hiểu, hai tài liệu có vẻ vênh nhau) → hỏi BA, kèm mã (US-E3.3, BR-K17…).
Đừng đoán — tài liệu này được đánh mã để hỏi cho nhanh. Bí về **kỹ thuật** → hỏi chính Claude Code
trước ("giải thích", "cho 2 phương án kèm ưu nhược"), vẫn bí → hỏi team, kèm prompt đã dùng + diff.

Thứ tự làm việc đề xuất: P0 (vá VĐ-1, Settings, allowance=0) → E1 → E2 → E3 → E4 → E6 → E5 → E7
(E7 chỉ bắt đầu sau khi họp chốt data contract HĐĐT — VĐ-11).
