# Kiểm tra hạn sử dụng tối thiểu theo yêu cầu khách hàng — thiết kế

Ngày: 19/10/2026. Nguồn yêu cầu: mục 4 "Kiểm tra hạn sử dụng hàng hóa theo yêu
cầu của Khách hàng" (4.1–4.4 và Business Rule) do anh gửi trong phiên làm việc.

## 1. Mục tiêu

Khách hàng có thể yêu cầu hàng giao phải còn tối thiểu N tháng hạn sử dụng (HSD).
Hệ thống phải:

1. Ghi nhận yêu cầu khi khách đặt hàng trên cổng (hoặc nhân viên nhập trên Desk).
2. Cảnh báo sớm ở Sales Order (SO) khi tồn kho hiện có không đáp ứng.
3. Không để lô không đạt được giao đi mà chưa có xác nhận ngoại lệ của khách,
   do nhân viên Miyano ghi trên hệ thống.

Đơn/dòng KHÔNG có yêu cầu HSD thì mọi thứ chạy y như hiện tại — kể cả FEFO.

## 2. Quy tắc nghiệp vụ

Ký hiệu cho một dòng SO:

- `N` = số tháng HSD tối thiểu của dòng (số nguyên, 1–60). Rỗng hoặc 0 = không yêu cầu.
- `ngay_du_kien` = `Sales Order Item.delivery_date`.
- `cong_thang(ngay, N)` = cộng N tháng lịch (`frappe.utils.add_months`):
  15/10/2026 + 3 = 15/01/2027; 31/01 + 1 = 28/02 (hoặc 29/02 năm nhuận).

**Ở SO:** `hsd_yeu_cau_den = cong_thang(ngay_du_kien, N)`.

**Ở phiếu giao (Delivery Note, DN):**
`ngay_moc = max(ngay_du_kien, DN.posting_date)` và
`hsd_yeu_cau_den = cong_thang(ngay_moc, N)` — giao trễ thì khách vẫn nhận đủ N tháng.

**Mức sàn được phép giao** của dòng:

- Không có ngoại lệ: `san = hsd_yeu_cau_den`.
- Có ngoại lệ: `san = ngoai_le_hsd_den` (HSD thấp nhất khách đã chấp nhận).

**Đánh giá một lô:**

- `expiry_date >= san` → ĐẠT (bằng nhau là đạt).
- `expiry_date < san` → KHÔNG ĐẠT.
- Lô không có `expiry_date` trong khi dòng có yêu cầu → KHÔNG ĐẠT (không biết hạn
  thì không khẳng định được là đạt).

**Không áp dụng** (bỏ qua mọi bước kiểm, không đổi hành vi hiện có):

- `N` rỗng/0.
- Mặt hàng không quản lý lô (`Item.has_batch_no = 0`).
- Dòng DN không lập từ SO (không có `so_detail`), và phiếu trả hàng (`is_return = 1`).

Mặt hàng có lô nhưng `has_expiry_date = 0` vẫn áp dụng: lô của nó thường không có
hạn → KHÔNG ĐẠT, nhân viên xử lý bằng ngoại lệ. Đây là quyết định có chủ ý.

## 3. Dữ liệu

Custom field tạo bằng patch `miyano_portal.patches.v1_46.hsd_toi_thieu`
(`create_custom_fields`, cùng mẫu patch v1_45).

### Sales Order

| Trường | Kiểu | Ghi chú |
|---|---|---|
| `custom_hsd_toi_thieu_thang` | Int | Nhãn "HSD tối thiểu (tháng)". Giá trị mặc định cho các dòng. |

### Sales Order Item

| Trường | Kiểu | Ghi chú |
|---|---|---|
| `custom_hsd_toi_thieu_thang` | Int | Lấy từ đầu phiếu khi dòng để trống; sửa riêng được. |
| `custom_hsd_yeu_cau_den` | Date, read only | Tính ở SO (§2). |
| `custom_ket_qua_hsd` | Select read only: `Đạt` / `Không đạt` / `Không áp dụng` | Kết quả kiểm tồn ở SO. |
| `custom_hsd_ton_tot_nhat` | Date, read only | HSD xa nhất trong tồn kho của dòng lúc kiểm. |
| `custom_ngoai_le_hsd` | Check, allow_on_submit | Khách đồng ý nhận HSD thấp hơn yêu cầu. |
| `custom_ngoai_le_hsd_den` | Date, allow_on_submit | HSD thấp nhất khách chấp nhận. Bắt buộc khi tick. |
| `custom_ngoai_le_ly_do` | Small Text, allow_on_submit | Lý do / hình thức khách xác nhận. Bắt buộc khi tick. |
| `custom_ngoai_le_boi` | Link User, read only, allow_on_submit | Ai ghi/gỡ ngoại lệ gần nhất. |
| `custom_ngoai_le_luc` | Datetime, read only, allow_on_submit | Lúc ghi/gỡ. |

Không thêm trường cho Batch: dùng `Batch.expiry_date` sẵn có của ERPNext.

## 4. Thành phần

### 4.1 Module `miyano_portal/han_dung_khach.py` (logic thuần, một nguồn duy nhất)

- `hsd_yeu_cau_den(ngay, so_thang) -> date | None`
- `san_cho_phep(dong_so, ngay_moc) -> date | None` — áp ngoại lệ nếu có.
- `danh_gia_lo(expiry_date, san) -> bool`
- `mo_ta_chenh_lech(hsd_yeu_cau, hsd_thuc_te, tu_ngay) -> dict` — số tháng/ngày còn
  lại và mức thiếu, dùng chung cho cảnh báo SO và lỗi DN.
- `kiem_ton_cho_dong(item_code, warehouse, qty, san) -> dict` — tổng tồn các lô đạt,
  HSD tốt nhất hiện có.

Mọi chỗ khác (hook SO, hook DN, API, FEFO) gọi qua module này, không tự viết lại
công thức.

### 4.2 Hook Sales Order (`validate`)

- Điền `custom_hsd_toi_thieu_thang` của dòng từ đầu phiếu khi dòng để trống.
- Kiểm số tháng nằm trong 0–60.
- Tính `hsd_yeu_cau_den`, `ket_qua_hsd`, `hsd_ton_tot_nhat` cho từng dòng.
  Dòng ĐẠT khi tổng tồn (theo `Bin`/lô trong `warehouse` của dòng) của các lô có
  `expiry_date >= san` ≥ `stock_qty` của dòng. Chưa trừ phần đã giữ cho SO khác.
- Chỉ cảnh báo (`msgprint` gom một lần), KHÔNG chặn lưu/submit.

Khi tick ngoại lệ qua form (trước submit): bắt buộc `ngoai_le_hsd_den` và
`ngoai_le_ly_do`, tự ghi `ngoai_le_boi`/`ngoai_le_luc`.

### 4.3 API ghi ngoại lệ sau submit

`miyano_portal.han_dung_khach.ghi_ngoai_le(so, dong, chap_nhan_den, ly_do)` và
`go_ngoai_le(so, dong, ly_do)`:

- Quyền: Sales User, Sales Manager, System Manager. Người khác → `PermissionError`.
- SO phải `docstatus = 1` và chưa Closed/Completed.
- Ghi bằng `db_set` các trường allow_on_submit; thêm comment vào timeline SO
  ("Ghi ngoại lệ HSD dòng X: chấp nhận đến dd/mm/yyyy — lý do…, bởi …").

### 4.4 Chọn lô khi xuất

Có hai nơi hệ thống tự chọn lô cho phiếu giao, cả hai phải tôn trọng `san`:

1. **ERPNext tự tạo Serial and Batch Bundle** khi dòng DN chưa có lô
   (Stock Settings: `pick_serial_and_batch_based_on = Expiry`, auto-create outward bật).
2. **FEFO của PDA** — `erpnext.warehouse_operations.vitri.fefo.chon_o_xuat` (fork
   erpnext), khi gợi ý ô/lô lấy hàng cho dòng chưa chốt lô.

Yêu cầu: với dòng có `san`, chỉ chọn lô có `expiry_date >= san`; còn lô đạt thì
không bao giờ gợi ý lô không đạt. Hết lô đạt thì báo thiếu hàng **nêu rõ lý do là
HSD** (không phải "không đủ hàng").

Bất biến: dòng không có `san` → kết quả chọn lô giống hệt hiện tại (cùng lô, cùng
ô, cùng thứ tự). Có test riêng khoá điều này.

Cơ chế cụ thể (tham số mới `han_toi_thieu` cho `chon_o_xuat`; cách lọc lô ở bước
tạo bundle) do plan quyết sau khi đọc kỹ code, ưu tiên thay đổi nhỏ nhất trong fork
erpnext. Lưới chặn ở §4.5 vẫn đảm bảo đúng kể cả khi một nơi chọn lô bị sót.

### 4.5 Chặn duyệt Delivery Note

Hook `before_submit` của DN (sau khi bundle đã được tạo), với mỗi dòng áp dụng:

- Đọc mọi lô thực xuất của dòng (`batch_no` hoặc các dòng trong
  `serial_and_batch_bundle`).
- Lô nào KHÔNG ĐẠT so với `san` → gom lỗi, cuối cùng `frappe.throw` một lần.

Nội dung lỗi mỗi dòng theo mẫu tài liệu, ví dụ:

> Dòng 2 – VT-001, lô L2409: Khách hàng yêu cầu hàng còn tối thiểu 03 tháng HSD
> (đến 15/01/2027). Lô này HSD 30/12/2026, chỉ còn 02 tháng 15 ngày → Không đáp
> ứng (thiếu 16 ngày). Vui lòng xác nhận với Khách hàng và ghi ngoại lệ trên SO
> SO-0001 trước khi giao.

Không có cờ bỏ qua nào ngoài ngoại lệ trên dòng SO.

### 4.6 Cổng khách hàng (frontend + `tao_sales_order`)

- Màn đặt hàng trực tiếp: ô "HSD tối thiểu (tháng)" cho cả đơn; mỗi dòng có ô sửa
  riêng (để trống = theo đơn). Số nguyên 0–60, kiểm cả client lẫn server.
- `dat_hang.tao_sales_order` nhận và ghi `custom_hsd_toi_thieu_thang` lên SO và dòng.
- Chi tiết đơn: hiện yêu cầu HSD từng dòng. Khách KHÔNG thấy kết quả Đạt/Không
  đạt, HSD tồn kho hay ngoại lệ — đó là dữ liệu nội bộ của Miyano; nhân viên kinh
  doanh liên hệ khách.

### 4.7 Desk Sales Order

- Lưới dòng: tô đỏ dòng `Không đạt`.
- Khung cảnh báo đầu phiếu: mỗi dòng không đạt — HSD yêu cầu, HSD tốt nhất trong
  kho, số tháng/ngày còn lại, chênh lệch; dòng đã có ngoại lệ ghi rõ "đã ngoại lệ
  đến dd/mm/yyyy".
- Nút "Ghi ngoại lệ HSD" (SO đã submit): hộp thoại chọn dòng, ngày chấp nhận (điền
  sẵn bằng `hsd_ton_tot_nhat`), lý do bắt buộc → gọi API §4.3. Có nút gỡ tương ứng.

## 5. Phạm vi

Trong phạm vi:

- Đặt hàng trực tiếp trên cổng, và SO nhập/sửa trên Desk.
- Cảnh báo SO, ngoại lệ theo dòng, lọc lô ở hai nơi chọn lô, chặn duyệt DN.

Ngoài phạm vi (làm sau):

- Đường "đề xuất mua → báo giá (kể cả báo giá theo đợt) → SO": chưa mang yêu cầu
  HSD đi qua Quotation. Nhân viên vẫn nhập được trên SO tạo ra từ đường này.
- Mặc định HSD theo hồ sơ khách hàng.
- Khách tự xác nhận ngoại lệ trên cổng.
- Trừ tồn đã giữ cho SO khác khi cảnh báo.

## 6. Kiểm thử

Python (`bench run-tests --app miyano_portal`, và test của fork erpnext cho FEFO):

- `cong_thang`: ngày thường, cuối tháng (31/01 + 1), năm nhuận.
- Biên: HSD bằng đúng ngày yêu cầu → ĐẠT; sớm hơn 1 ngày → KHÔNG ĐẠT.
- Lô không có hạn khi dòng có yêu cầu → KHÔNG ĐẠT.
- Giao trễ: `ngay_moc` lấy `posting_date` khi muộn hơn ngày dự kiến.
- Ngoại lệ: lô ≥ `ngoai_le_hsd_den` qua; lô thấp hơn nữa vẫn bị chặn.
- SO: dòng thừa hưởng số tháng từ đầu phiếu; dòng sửa riêng được giữ; ngoài 0–60 bị từ chối.
- SO cảnh báo không chặn submit.
- DN: chặn khi lô không đạt, gom nhiều dòng một lỗi; không kiểm `is_return`, dòng
  không `so_detail`, mặt hàng không lô, dòng không yêu cầu.
- Chọn lô: bỏ lô không đạt khi còn lô đạt; hết lô đạt báo lý do HSD.
- **Bất biến FEFO**: không yêu cầu HSD → kết quả `chon_o_xuat` và bundle tự tạo
  giống hệt trước khi đổi.
- API ngoại lệ: phân quyền (khách cổng, Stock User bị từ chối), SO chưa submit/đã
  đóng bị từ chối, ghi người/thời điểm và comment timeline.
- Cổng: `tao_sales_order` mang số tháng lên SO/dòng; API chi tiết đơn không trả
  các trường kết quả/ngoại lệ (cách ly dữ liệu nội bộ).

Frontend (`yarn test`): kiểm ô nhập 0–60, dòng trống theo đơn.

## 7. Triển khai

- Hai repo: `miyano_portal` (nhánh `feat/hsd-toi-thieu`) và fork `erpnext` (nhánh
  riêng cho phần chọn lô).
- Production: `bench --site miyano migrate` chạy patch v1_46; `bench build` cho
  frontend cổng và `sales_order.js`.
