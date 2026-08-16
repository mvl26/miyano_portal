# Kiểm hàng khi nhận & trả lại phần hàng hỏng — Design

Ngày: 2026-08-16 · Nhánh: `feature/mua-le-toan-danh-muc` (nối tiếp)

## 1. Yêu cầu gốc (lời chủ đầu tư, 2026-08-16)

> "kiểm tra hàng hóa, trong trường hợp 1 phần hàng bị hỏng, tôi muốn nhận 1
> phần và trả lại phần hàng bị hỏng" — áp cho **cả** đơn theo hợp đồng khung
> **và** đơn mua lẻ.

Kèm theo là một danh sách 11 nhu cầu đã được đối chiếu với code (§2).

## 2. Đối chiếu hiện trạng

| Nhu cầu | Hiện trạng |
|---|---|
| Đặt hàng theo hợp đồng khung | ✅ `portal_contracts` / `portal_catalog` / `portal_order_place` |
| Theo dõi đơn hàng | ✅ `portal_order_track` — 5 mốc |
| Xem đơn | ✅ `OrderDetail.vue` |
| Mua lẻ, thấy danh sách hàng hoá | ✅ `portal_catalog_ban_le` (toàn danh mục, không giá) |
| Tạo mặt hàng chưa có + gửi yêu cầu | ✅ `Sales Order Dat Ngoai Item` + `HANG-DAT-NGOAI` |
| Xem báo giá của Miyano | ✅ `portal_bao_gia_pdf` + `portal_order_accept` |
| Sửa số lượng → Miyano báo giá lại | ✅ `portal_order_sua_so_luong` |
| Xác nhận → thành đơn hàng | ✅ `portal_order_accept(action="dong_y")` |
| **Xem hoá đơn CỦA ĐƠN ĐÓ** | ❌ chỉ có mốc bật/tắt + trang Hoá đơn toàn cục |
| **Kiểm hàng khi nhận** | ⚠ chỉ 5/21 khách có kho mới có phiếu nhập tự sinh |
| **Trả lại phần hàng hỏng** | ❌ không có luồng khách khởi tạo |

Chi tiết hai điểm ⚠/❌ cuối:

- Cơ chế đối soát hiện có (`Customer Stock Receipt.sl_giao` vs `so_luong`,
  `ly_do_chenh_lech`, `co_chenh_lech`, BR-K17) **chỉ tồn tại khi khách đã mở
  kho** — `delivery_hook._tu_delivery_note()` bỏ qua im lặng khi
  `_kho_cua_khach()` trả `None`. Trên site: 5/21 khách có kho.
- Ghi "thực nhận 7 / giao 10" **làm mất 3 cái hỏng**: sổ ghi 7, không đâu ghi
  nhận "3 cái đang ở chỗ khách, chờ Miyano thu hồi". Chênh lệch ≠ trả hàng.
- Nửa hạch toán của trả hàng thì ĐÃ CÓ: `kho/delivery_hook.py:100,235` xử lý
  `is_return` — nhân viên lập phiếu giao ngược ở Desk là kho khách tự đảo.
  Thiếu đúng **cái nút khởi tạo phía khách** và **trạng thái để khách theo dõi**.

## 3. Quyết định của chủ đầu tư (2026-08-16)

**QĐ-1. Kiểm hàng áp cho MỌI khách, tách khỏi module kho.**
Không bắt khách mở kho chỉ để báo hàng hỏng. Khách có kho vẫn giữ nguyên phiếu
nhập kho tự sinh như cũ — hai thứ song song, không thay thế nhau (§4.4).

**QĐ-2. Nhân viên quyết, khách theo dõi được trạng thái.**
Yêu cầu trả hàng về Desk ở trạng thái "Chờ xử lý"; nhân viên duyệt (→ sinh
phiếu giao ngược nháp) hoặc từ chối kèm lý do. Khách thấy trạng thái trên cổng
và nhận thông báo. KHÔNG tự động đảo sổ ngay khi khách bấm — hàng chưa thu hồi
thật mà sổ đã đảo là một lỗ hổng kho.

## 4. Thiết kế

### 4.1 Doctype `Portal Delivery Inspection` (label "Biên bản kiểm hàng")

Đặt tên `Portal ...` theo đúng họ với `Portal Item Request`: doctype mang
`customer` TRỰC TIẾP (hình dạng Sales Order / Delivery Note), **không** phải
hình dạng kho (lọc theo `kho`). Đây là lý do nó vào `KHO_DOCTYPES_KHAC` của
`test_kho_isolation.py` chứ không vào `KHO_PREFIXES`.

Header:

| Field | Kiểu | Ghi chú |
|---|---|---|
| `customer` | Link Customer | reqd, read_only — trục cách ly |
| `delivery_note` | Link Delivery Note | reqd, unique-per-customer (§4.3) |
| `sales_order` | Data | denormalise để cổng link ngược về đơn |
| `ngay_kiem` | Date | mặc định hôm nay |
| `nguoi_kiem` | Data (Email) | read_only, lấy từ session |
| `trang_thai` | Select | xem §4.2 |
| `co_hang_hong` | Check | read_only, tự tính |
| `ly_do_tu_choi` | Small Text | |
| `phieu_tra_hang` | Data | tên DN trả hàng nhân viên đã lập |
| `ghi_chu` | Small Text | |
| `items` | Table | `Portal Delivery Inspection Item` |

Dòng (`Portal Delivery Inspection Item`):

| Field | Kiểu | Ghi chú |
|---|---|---|
| `item_code` | Link Item | |
| `item_name`, `uom` | Data | chụp lại tại thời điểm kiểm |
| `sl_giao` | Float | read_only — mốc lấy từ Delivery Note Item |
| `sl_nhan` | Float | khách nhập — nhận tốt |
| `sl_tra` | Float | khách nhập — hỏng, trả lại |
| `ly_do` | Data | bắt buộc khi `sl_nhan + sl_tra != sl_giao` hoặc `sl_tra > 0` |

Phần còn lại `sl_giao − sl_nhan − sl_tra` = **thiếu, không tới nơi** — suy ra,
KHÔNG lưu thành field riêng (một con số suy được mà đem lưu là một con số sẽ
lệch).

Ràng buộc (`validate`):
1. `sl_nhan ≥ 0`, `sl_tra ≥ 0`.
2. `sl_nhan + sl_tra ≤ sl_giao + EPS` — không ai "nhận thừa" trên biên bản
   này, cùng nguyên tắc NL-3.10 của phiếu nhập kho.
3. `sl_tra > 0` hoặc lệch so với `sl_giao` → bắt `ly_do`.
4. `co_hang_hong = 1` khi có bất kỳ dòng nào `sl_tra > 0`.

### 4.2 Máy trạng thái

```
(nháp, docstatus=0)
   │ khách bấm "Gửi biên bản"  → submit
   ▼
"Chờ xử lý"  ──nhân viên duyệt──►  "Đã duyệt trả"  (sinh DN trả hàng nháp)
   │                                      │ nhân viên submit DN trả hàng
   │                                      ▼
   │                                "Đã thu hồi"
   └──nhân viên từ chối──►  "Từ chối"  (bắt `ly_do_tu_choi`)
```

Biên bản KHÔNG có hàng hỏng (`co_hang_hong = 0`) đi thẳng vào **"Đã xác nhận"**
khi gửi — không làm phiền nhân viên vì một lần nhận đủ.

Dùng `Select` + hàm whitelist có kiểm role, **không** dùng Frappe Workflow:
máy trạng thái này 5 nút, thêm một Workflow doctype nữa chỉ để có 3 transition
là chi phí không đổi lại được gì (bài học chi phí quy trình, phiên 2026-08-15).

### 4.3 Một biên bản cho một phiếu giao

`delivery_note` unique. Khách gửi nhầm rồi muốn sửa: bản đã gửi không sửa
được; nhân viên "Từ chối" thì khách gửi lại được (biên bản cũ giữ nguyên làm
lịch sử, bản mới là amend — dùng `amended_from` sẵn có của Frappe).

### 4.4 Quan hệ với phiếu nhập kho (khách có kho)

Hai chứng từ, hai mục đích, **không** đồng bộ số liệu tự động:

- **Phiếu nhập kho** — ghi sổ tồn kho NỘI BỘ của khách. Chỉ khách có kho.
- **Biên bản kiểm hàng** — đối thoại với Miyano về đợt giao. Mọi khách.

Cố tình không cho cái này ghi đè cái kia: một lần sửa nhầm trên biên bản mà
kéo theo bút toán kho là đúng loại lỗi mà `_chan_tu_tao_phieu_dao()` tồn tại
để chặn. Màn kiểm hàng CÓ hiển thị link sang phiếu nhập khi có, để thủ kho tự
đối chiếu.

### 4.5 Sinh phiếu trả hàng

`erpnext.controllers.sales_and_purchase_return.make_return_doc("Delivery Note",
<dn>)` → chỉnh `qty` từng dòng về `-sl_tra` (ERPNext dùng SL ÂM cho phiếu trả),
xoá dòng `sl_tra = 0`, **để nháp** cho nhân viên kiểm rồi tự submit. Không
submit hộ: tồn kho Miyano chỉ được cộng lại khi hàng về thật.

### 4.6 Bịt khoảng trống "xem hoá đơn của đơn đó"

`portal_order_track` trả thêm `hoa_don`: các `Sales Invoice` có
`Sales Invoice Item.sales_order = <đơn>`, kèm `name / posting_date / status /
grand_total / outstanding_amount`. `OrderDetail.vue` hiện danh sách + nút tải
PDF qua `portal_document_download` sẵn có. KHÔNG đụng `portal_invoices`.

## 5. Quyền

Theo Quyết định #7 của dự án: **không cấp DocPerm nào cho role `Customer`** trên
hai doctype mới. Cổng thật là các endpoint trong `api/portal.py`, tự suy
`customer` từ session. Đăng ký `permission_query_conditions` +
`has_permission` làm lớp phòng thủ thứ hai, đúng khuôn `Portal Item Request`.

Desk: `System Manager` (đủ quyền), `Sales Manager` (đủ), `Sales User`
(read/write, không xoá).

## 6. Không làm

- Không đụng vào `Customer Stock Receipt` / `kho/*` — module kho đứng yên.
- Không tự submit phiếu trả hàng.
- Không thêm Frappe Workflow doctype.
- Không gộp biên bản kiểm hàng vào phiếu nhập kho (§4.4).
- Không đổi hình dạng trả về của `portal_invoices`.
