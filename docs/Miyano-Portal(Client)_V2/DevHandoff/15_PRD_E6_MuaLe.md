# PRD E6 — Mua lẻ ngoài hợp đồng khung (QT10)

| Meta | Nội dung |
|---|---|
| Phạm vi cổng | UC-15 · BR-R1…R7 · NL-10.x · QĐ-5 |
| Desk-only | UC-16, 17, 52, 53 · BR-Y1…Y5 · NL-11.x · QĐ-6 (xem mục riêng bên dưới) |
| Tham chiếu | BA §4.10, §4.11 (đánh dấu Desk-only) · FormSpec F-21 (danh mục), F-03 (bộ chuyển), F-04
  (giỏ 2 ngăn), F-07 (Chờ bạn đồng ý + tải PDF) · Spec 2026-08-15 §3.1–§3.6 |
| Phụ thuộc | E2 (trạng thái "Chờ khách đồng ý") |

> **Đổi tên 15/08:** "Mua lẻ ngoài hợp đồng nguyên tắc/HĐNT" → "Mua lẻ ngoài hợp đồng khung" trong
> mọi chữ hiển thị (xem `CHANGELOG-khac-phuc-BA-v2.md` §2026-08-15). Mã BR/NL/UC không đổi.

## Mục tiêu (bản 15/08 — thiết kế lại)
Khách không cần biết trước Miyano có mặt hàng gì: danh mục Mua lẻ là **toàn bộ** `Item` đang hoạt
động, không hiện giá (giá đến sau qua báo giá của sales). Khách không tìm được mã cũng đặt được —
gõ thẳng tên hàng vào chính phiếu đang mở, không phải sang một chứng từ khác. "Portal Item Request"
(US-E6.3/E6.4/E6.6 bản gốc) rút khỏi cổng, giữ lại cho nhân viên Miyano dùng trên Desk.

## User stories & AC — phạm vi CỔNG

### US-E6.1 — Mua lẻ mặc định BẬT, danh mục toàn bộ Item, không giá (BR-R1, R6, R7) [SỬA 15/08]
```gherkin
Given Customer.custom_cho_phep_mua_le mặc định = 1 (đổi từ 0 — §3.5; khách hiện hữu được UPDATE
      qua patch, khách tạo mới nhận default mới)
Then bộ chuyển "Theo hợp đồng khung | Mua lẻ" luôn hiện; sales vẫn tắt được cho một khách cụ thể
     (khách nợ quá hạn, chỉ cho mua theo hợp đồng) — đổi GIÁ TRỊ MẶC ĐỊNH, không bỏ chốt server
When khách vào ngăn Mua lẻ
Then danh mục = TOÀN BỘ Item đang hoạt động (không còn lọc theo custom_ban_le_portal), phân trang
     server-side (start/limit=50, "Tải thêm"), tìm kiếm không dấu server-side
And danh mục KHÔNG hiện đơn giá — mọi phiếu Mua lẻ đều đi qua báo giá của sales (§3.6, US-E6.5)
And item đang thuộc hợp đồng khung còn hiệu lực của khách → dòng mờ, badge "Có trong hợp đồng
    khung — đặt ở chế độ Theo hợp đồng khung" bấm để chuyển tab (BR-R7, chống né hạn mức NL-10.7)
```

### US-E6.2 — Giỏ 2 ngăn, đặt đơn lẻ (BR-R2, R3, R4) [Hiện có, không đổi]
```gherkin
When khách thêm hàng lẻ vào giỏ
Then vào ngăn "Mua lẻ" riêng; badge nav = tổng dòng 2 ngăn; mỗi ngăn xác nhận riêng → 2 SO riêng
When đặt ngăn Mua lẻ
Then SO có custom_loai_don="Mua lẻ", KHÔNG kiểm hạn mức, KHÔNG gắn against_blanket_order/custom_hdnt;
     vẫn kiểm sở hữu địa chỉ, bội số, ngày giao, request_id; đơn đi vào QT2 (duyệt ngưỡng áp dụng)
And server từ chối payload trộn dòng hợp đồng khung + lẻ trong một đơn (NL-10.3)
```

### US-E6.7 — Khối "hàng chưa có mã" trên chính phiếu mua lẻ (BR-R... , §3.4) [MỚI 15/08]
```gherkin
Given khách tìm một từ khoá không khớp mã nào trong danh mục
Then khối "Không tìm thấy vật tư cần mua?" tự mở, dòng đầu prefill sẵn từ khoá vào Tên hàng
When khách điền Tên hàng + ĐVT + Số lượng (Ghi chú tuỳ chọn) cho một hoặc nhiều dòng, không chọn
     mặt hàng có mã nào khác
Then đặt đơn Mua lẻ THÀNH CÔNG — server chèn thêm một dòng Item kỹ thuật `HANG-DAT-NGOAI`
     (is_stock_item=0) vào `items` CHỈ để ERPNext lưu được SO không dòng "items" thật nào; các dòng
     khách gõ tay lưu vào bảng con `custom_dat_ngoai` (Sales Order Dat Ngoai Item, DataDict §…)
And dòng `HANG-DAT-NGOAI` KHÔNG BAO GIỜ lọt ra chi tiết đơn của khách, mẫu in Xác nhận đơn hàng,
    hay mẫu in Báo giá — lọc tại nguồn bằng `la_dong_giu_cho()`, dùng chung một hàm ở mọi nơi in
When Miyano khớp được mã cho một dòng đặt ngoài (điền `item_khop`, bật `da_xu_ly` trên Desk)
Then dòng đó tính vào báo giá (bảng "Hàng đặt ngoài đã khớp mã" trên PDF, §3.6); còn dòng CHƯA khớp
     hiện ở nhóm "Đang chờ Miyano xác nhận nguồn" trên chi tiết đơn của khách (`portal_order_track`)
```

### US-E6.5 — Báo giá → khách đồng ý trên cổng, có PDF (BR-R5) [SỬA 15/08 — thêm PDF]
```gherkin
Given sales điền giá cho các dòng "items", khớp mã cho dòng đặt ngoài, rồi chuyển trạng thái
      "Chờ khách đồng ý" (transition "Gửi khách duyệt", chung workflow E2, không riêng Mua lẻ)
When khách vào chi tiết đơn hoặc nhận email
Then thấy banner "Báo giá hiệu lực đến dd/mm/yyyy" (= ngày gửi + Settings.hieu_luc_bao_gia_ngay,
     mặc định 7) và nút [Tải báo giá PDF] (`portal_bao_gia_pdf`, mẫu in "Miyano - Báo giá", §3.6)
When khách bấm Đồng ý → portal_order_accept
Then chuyển "Chờ Miyano xác nhận"; Comment log user + timestamp
When khách Không đồng ý (lý do ≥10 ký tự)
Then về "Chờ xác nhận" cho sales sửa (NL-10.4)
When quá hạn hiệu lực
Then job daily huỷ nháp + email 2 phía; chỉ áp cho đơn "Mua lẻ" — đơn hợp đồng khung ở "Chờ khách
     đồng ý" (luồng E2 gốc) không có khái niệm hiệu lực N ngày (NL-10.5)
```

## Desk-only — không còn trên cổng khách

Ba user story sau của bản PRD gốc mô tả tính năng "Yêu cầu hàng hoá" (`Portal Item Request`) —
**đã gỡ khỏi cổng ở Task 1/2** của kế hoạch 2026-08-15 (không còn màn nào để khách gửi/xem/trả lời
yêu cầu). Doctype và quy trình vẫn sống **trên Desk** cho nhân viên Miyano dùng nội bộ (báo giá thủ
công, quản lý demand pipeline) — mã BR-Y1…Y5/NL-11.x, UC-16/17/52/53 vẫn mô tả đúng quy trình đó,
chỉ không còn lối vào từ cổng khách.

- **US-E6.3 — Yêu cầu hàng hoá: tạo từ 3 đường (UC-16, BR-Y5)** — hai trong ba đường vào (từ khoá
  không kết quả, thiếu tồn ở dự trù) đã được thay bằng US-E6.7 (khối tự nhập ngay trên phiếu). Đường
  thứ ba ("[Yêu cầu báo giá]" khi danh mục thiếu giá) không còn ý nghĩa: danh mục Mua lẻ không hiện
  giá nữa (US-E6.1), mọi phiếu đều đi qua báo giá. `Portal Item Request` vẫn tạo được **trên Desk**.
- **US-E6.4 — Miyano xử lý yêu cầu (UC-52, BR-Y1…Y3)** — quy trình xử lý trạng thái/SLA/leo thang
  không đổi, chạy trên Desk. Nút "trả lời trên cổng" (F-23) không còn — sửa Notification liên quan
  thành hướng dẫn liên hệ nhân viên phụ trách hoặc trả lời email (xem CHANGELOG).
- **US-E6.6 — Báo cáo demand pipeline (UC-53)** — báo cáo Desk không đổi.

## Luồng (Mermaid) — cổng, bản 15/08

```mermaid
flowchart TD
  A[Khách vào ngăn Mua lẻ] --> B{Tìm thấy mã?}
  B -->|có, không thuộc hợp đồng khung| C[Thêm giỏ Mua lẻ — không giá]
  B -->|không tìm ra| D[Khối tự nhập mở sẵn, prefill từ khoá]
  D --> E[Điền Tên hàng/ĐVT/SL — không cần mã]
  C --> F[Xác nhận → SO Mua lẻ, rate=0]
  E --> F
  F -->|dòng có mã| G["items" — chờ sales điền giá]
  F -->|dòng không mã| H["custom_dat_ngoai" — chờ Miyano tìm nguồn/khớp mã]
  G --> I[Sales điền giá + khớp mã còn lại → Gửi khách duyệt]
  H --> I
  I --> J["Chờ khách đồng ý" — banner hiệu lực + Tải PDF"]
  J -->|Đồng ý| K[Chờ Miyano xác nhận → QT2]
  J -->|quá hạn| L[Tự đóng + email]
```

## Dữ liệu & API — cổng

- Custom field: `Customer.custom_cho_phep_mua_le` (mặc định 1, §3.5), `Sales Order.custom_loai_don`
  + `custom_dat_ngoai` (Table, §3.4), `Item HANG-DAT-NGOAI` giữ chỗ (is_stock_item=0, §3.4).
- Doctype mới: `Sales Order Dat Ngoai Item` (child table — 6 trường, DataDict §…).
- Endpoint: `portal_catalog_ban_le` (không trả giá; start/limit/tong), `portal_order_place`
  (tham số `dat_ngoai`, mode="ban_le"), `portal_order_track` (khoá `dat_ngoai`, `items` đã lọc dòng
  giữ chỗ), `portal_order_accept`, `portal_bao_gia_pdf` (§3.6, API Spec).
- `Portal Item Request` và các endpoint `portal_yeu_cau_*` — **đã xoá khỏi API Spec cổng**, vẫn tồn
  tại làm doctype Desk.

## DoD
AC pass (TC-E6, đã cập nhật cho §3.1–§3.6) · test cách ly khách A/B trên đường tìm nguồn · test né
hạn mức BR-R7 · mặc định BẬT mua lẻ không phá vỡ khách đã tắt cờ thủ công · khách đặt được đơn toàn
dòng "chưa có mã" mà không cần biết mã hàng nào.
