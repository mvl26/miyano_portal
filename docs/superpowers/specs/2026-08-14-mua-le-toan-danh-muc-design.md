# Thiết kế lại luồng mua lẻ — toàn danh mục + dòng tự nhập + báo giá

Ngày 2026-08-14 · Thay thế thiết kế mua lẻ hiện tại của E6 (US-E6.1, E6.2)
Chủ dự án đã duyệt qua đối thoại; ba quyết định nền ở §2.

## 1. Vấn đề với thiết kế hiện tại

Bản E6 đang chạy cho khách thấy **một danh mục tuyển chọn**: chỉ mặt hàng có cờ `custom_ban_le_portal = 1` **và** có giá trong bảng giá bán lẻ. Mặt hàng thiếu giá thì hiện nút "Yêu cầu báo giá" dẫn sang một chứng từ khác (`Portal Item Request`).

Điều đó buộc khách phải **biết Miyano có gì** trước khi đặt được hàng, và tách một nhu cầu duy nhất thành hai loại chứng từ tuỳ theo việc Miyano đã kịp khai giá hay chưa — một chi tiết vận hành nội bộ mà khách không nên nhìn thấy.

Nguyên tắc chủ dự án đặt ra: **khách không cần biết Miyano có gì; họ đặt hàng, Miyano có trách nhiệm gửi hàng.**

## 2. Ba quyết định nền

1. **Dòng khách tự nhập nằm trên chính phiếu mua**, thành một nhóm riêng — không sinh chứng từ thứ hai cho khách nhìn thấy.
2. **Danh mục hiện toàn bộ vật tư, KHÔNG hiện giá.** Mọi phiếu mua lẻ đều đi qua báo giá.
3. **Luồng dùng lại máy trạng thái đã có** (E2/E6.5): SO nháp → sales điền giá → "Chờ khách đồng ý" → khách đồng ý → duyệt theo ngưỡng → giao.

## 3. Ràng buộc kỹ thuật cứng

ERPNext bắt buộc `item_code` trên mỗi `Sales Order Item`. Nên dòng khách tự nhập **không thể** là dòng đơn hàng bình thường cho tới khi có mã hàng thật. Đây là lý do bắt buộc phải có nhóm riêng, không phải lựa chọn thẩm mỹ.

## 4. Thiết kế

### 4.1 Danh mục (`portal_catalog_ban_le`)

- Trả **toàn bộ `Item`** với `disabled = 0`. **Bỏ** bộ lọc `custom_ban_le_portal`.
- **Không trả giá.** Bỏ phụ thuộc vào `Miyano Portal Settings.price_list_ban_le` cho đường này.
- Tìm theo mã hoặc tên; lọc theo `item_group`; **phân trang phía server** — danh mục Miyano có thể vài nghìn mã, khác hẳn danh mục tuyển chọn cũ.
- Giữ nguyên cờ `thuoc_hdnt` (xem §4.2).

**Hệ quả:** VĐ-12 ("Price List bán lẻ phải chuẩn hoá trước khi bật nhánh A") **tự tan** — không hiện giá thì không cần bảng giá.

### 4.2 Chống né hạn mức (BR-R7) — GIỮ NGUYÊN

Mặt hàng đang thuộc hợp đồng nguyên tắc **còn hiệu lực** của khách vẫn **không đặt lẻ được**. Đây là chốt bảo vệ toàn bộ cơ chế hạn mức của E1; bỏ nó là khách hết hạn mức chỉ cần chuyển sang mua lẻ là mua tiếp. Đã từng là lỗi Critical ở vòng review E6.

Khác trước: giờ khách **nhìn thấy** những mặt hàng đó trong danh mục, nên dòng hiện **mờ kèm lý do** "Có trong HĐNT — đặt ở chế độ Theo HĐNT", thay vì biến mất im lặng.

Server vẫn trả `417 thuoc_hdnt_hieu_luc` nếu payload cố gửi lên.

### 4.3 Nhóm "chưa có trong kho, cần đặt ngoài"

Bảng con mới trên `Sales Order`, fieldname không dấu theo quy ước dự án:

| Trường | Kiểu | Ai điền |
|---|---|---|
| `ten_hang` | Data, reqd | Khách |
| `dvt` | Data, reqd | Khách |
| `so_luong` | Float, reqd, > 0 | Khách |
| `ghi_chu` | Small Text | Khách |
| `item_khop` | Link → Item | Nhân viên Miyano |
| `da_xu_ly` | Check, read-only | Hệ đặt khi `item_khop` có giá trị |

Nhân viên khi báo giá: khớp dòng vào mã có sẵn, hoặc tạo mã mới, rồi chuyển thành dòng hàng thật trên đơn.

### 4.4 Chốt chặn mới: không xác nhận đơn khi còn dòng chưa xử lý

`before_submit` chặn nếu còn dòng "đặt ngoài" chưa có `item_khop`.

**Vì sao cần:** không có nó, một đơn có thể được duyệt và giao trong khi hai dòng khách yêu cầu chưa ai đụng tới — khách trả tiền cho thứ họ không nhận được, và không có tín hiệu nào báo.

### 4.5 Giá

`portal_order_place(mode="ban_le")` **không còn đòi giá**. Dòng vào đơn với `rate = 0`; sales điền sau. Bỏ nhánh trả `thieu_gia` cho đường bán lẻ (đường HĐNT giữ nguyên — ở đó giá đến từ hợp đồng).

Ngưỡng duyệt của E2 kiểm ở `before_submit`, lúc đó giá đã điền — không ảnh hưởng.

### 4.6 Thông báo khi báo giá sẵn sàng

Khi đơn chuyển vào **"Chờ khách đồng ý"**, khách nhận thông báo trên chính đơn đặt hàng (kèm email theo khuôn `Notification` đã có).

Nội dung phải nêu: mã đơn, tổng giá trị, và **hạn hiệu lực báo giá** — vì quá hạn thì job tự đóng đơn, khách cần biết mình có bao nhiêu ngày.

Mốc hạn đọc từ `custom_ngay_gui_khach_duyet` đã có (E6 vòng sửa 2), **không phải** `transaction_date`.

### 4.7 Ba đường vào "Yêu cầu hàng hoá"

| Đường | Quyết định |
|---|---|
| Danh mục lẻ → "Yêu cầu báo giá" | **Bỏ** — mọi mặt hàng giờ đều phải báo giá, nút này thừa |
| Tìm không ra kết quả → "Gửi yêu cầu" | **Bỏ** — khách gõ thẳng vào nhóm "đặt ngoài" |
| Màn dự trù → "Nhờ Miyano tìm nguồn" | **GIỮ** — ở đó khách đang xem tồn kho của mình, chưa muốn đặt ngay, chỉ muốn Miyano đi tìm nguồn. Nhu cầu khác hẳn. |

`Portal Item Request` cùng job SLA 48h, báo cáo demand pipeline và luồng phản hồi hai chiều **giữ nguyên** cho đường còn lại.

## 5. Test case bị ảnh hưởng

| TC | Thay đổi |
|---|---|
| TC-E6-01 | **Giữ** — khách chưa bật cờ vẫn 403 |
| TC-E6-02 | **Đổi** — không còn khái niệm "item có giá lẻ"; đơn vào "Chờ xác nhận" với `rate = 0` |
| TC-E6-03 | **Giữ nguyên ý nghĩa** — BR-R7 là chốt an ninh, không được nới |
| TC-E6-04 | **Giữ** — vẫn không trộn dòng HĐNT và lẻ trong một đơn |
| TC-E6-05/06 | **Giữ** cho đường dự trù còn lại |

**Test mới cần có:** danh mục trả mặt hàng **không** có cờ `custom_ban_le_portal` (chứng minh đã bỏ lọc) · dòng đặt ngoài lưu đúng qua endpoint · chốt `before_submit` chặn khi còn dòng chưa xử lý · thông báo sinh ra khi vào "Chờ khách đồng ý" và mang đúng hạn hiệu lực.

## 6. Việc KHÔNG làm

- Không tạo doctype mới cho phiếu mua lẻ — dùng `Sales Order` như đã chốt.
- Không xoá `custom_ban_le_portal` khỏi `Item` ở đợt này (dữ liệu cũ, xoá cột là việc riêng); chỉ **ngừng dùng** nó để lọc.
- Không đụng `Miyano Portal Settings.price_list_ban_le` — để nguyên, chỉ ngừng phụ thuộc.
