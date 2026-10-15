# Báo giá theo đợt trên một yêu cầu báo giá

**Ngày:** 15/10/2026 · **Chủ đầu tư chốt trong phiên**

**Phụ thuộc:** spec `2026-10-12-yeu-cau-bao-gia-quotation-design.md` (yêu cầu
báo giá là Quotation, workflow "Quotation - Client Portal"). Bản này xây TRÊN
luồng đó, không thay nó.

## 1. Vấn đề

Hôm nay một yêu cầu báo giá là **một** Quotation, gửi khách **một lần**, khách
đồng ý thì sinh **đúng một** Sales Order (`chan_don_thu_hai_tu_bao_gia_cong`).
Phiếu có 5 mặt hàng mà Miyano mới có giá cho 2 thì hoặc phải chờ đủ 5, hoặc
khách phải gửi lại yêu cầu mới cho phần còn lại.

Nhu cầu: báo giá **từng đợt** — hôm nay 2 mặt hàng, mai 1, tuần sau 2 — mỗi đợt
khách đồng ý là có đơn ngay; mặt hàng chưa báo vẫn nằm trên phiếu để báo tiếp
hoặc huỷ.

## 2. Các quyết định đã chốt

| # | Quyết định |
|---|---|
| D1 | Mỗi đợt là một **Quotation con** tách từ phiếu gốc, đi nguyên workflow "Quotation - Client Portal" hiện có (gửi khách → đồng ý → sinh đơn / từ chối / hết hạn). Quy tắc "1 Quotation → 1 Sales Order" giữ nguyên. |
| D2 | Khách đồng ý hoặc từ chối **cả đợt**, không chọn từng dòng. |
| D3 | Đợt bị **từ chối hoặc hết hạn** thì các dòng của đợt **quay về phiếu gốc** để báo lại hoặc huỷ. |
| D4 | **Cả khách và Miyano** được "Huỷ phần còn lại" của phiếu gốc. Miyano phải ghi lý do (≥ 10 ký tự); khách ghi lý do tuỳ chọn. Huỷ cả phần còn lại một lần, không huỷ từng dòng. |
| D5 | Trên cổng, danh sách "Yêu cầu báo giá" chỉ hiện **phiếu gốc**; các đợt **gom trong trang chi tiết** của phiếu gốc. |
| D6 | Báo cả phiếu một lần (không tách đợt) chạy **y như hôm nay**. Tách đợt là tuỳ chọn của nhân viên. |
| D7 | Phiếu gốc **đã tách ít nhất một đợt thì không bao giờ gửi khách nữa**; nó chỉ giữ các mặt hàng chưa báo. |
| D8 | Chỉ áp dụng cho Quotation `custom_nguon_don = "Client Portal"`. Báo giá nhân viên tự lập ngoài cổng không có nút tách đợt. |

## 3. Dữ liệu

### 3.1 Trường mới trên Quotation (Custom Field, patch `v1_45`)

| Trường | Kiểu | Ý nghĩa |
|---|---|---|
| `custom_phieu_goc` | Link Quotation, read-only | Trên đợt: trỏ về phiếu gốc. Trống trên phiếu gốc và trên báo giá thường. |
| `custom_so_dot` | Int, read-only | Số thứ tự đợt (1, 2, 3…), cấp tăng dần theo phiếu gốc. |
| `custom_ly_do_huy_con_lai` | Small Text, read-only | Lý do huỷ phần còn lại. |
| `custom_nguoi_huy_con_lai` | Data, read-only | "Khách" hoặc user nhân viên đã huỷ. |
| `custom_da_tra_ve` | Check, read-only | Trên đợt: đã trả dòng về phiếu gốc (chống trả hai lần). |

Đợt chép từ phiếu gốc: `party_name`/khách, `custom_khoa_phong`,
`custom_ten_don_hang`, `custom_nguon_don`, `custom_de_xuat`, `selling_price_list`,
`currency`, công ty. `custom_request_id` của đợt = `<request_id gốc>:dot<N>`.

### 3.2 Workflow "Quotation - Client Portal" — thêm 2 trạng thái

| Trạng thái | docstatus | Đặt bởi |
|---|---|---|
| **Đã báo hết** | 0 | Code: phiếu gốc đã tách đợt và không còn dòng nào. |
| **Đã huỷ phần còn lại** | 0 | Hành động mới **"Huỷ phần còn lại"** (Miyano trên Desk) hoặc API cổng (khách). Trạng thái cuối. |

- `Chờ Miyano báo giá ⇄ Đã báo hết` do code chuyển (tách hết dòng / dòng quay
  về), không hiện thành nút.
- `Chờ Miyano báo giá → Đã huỷ phần còn lại`: hành động "Huỷ phần còn lại",
  vai trò như "Từ chối" hiện có; chỉ hợp lệ khi phiếu gốc đã có ít nhất một đợt
  (tồn tại Quotation có `custom_phieu_goc` = phiếu này; kiểm trong
  `before_transition`) — phiếu chưa tách đợt dùng "Từ chối" như cũ.
- Không đổi docstatus phiếu gốc: nó luôn là nháp, để dòng quay về thêm vào được.

### 3.3 Phiếu đề xuất mua (`Portal De Xuat Mua`)

- Thêm bảng con **`don_hang`** (child doctype mới `Portal De Xuat Mua Don Hang`:
  `sales_order` Link, `bao_gia` Link, `so_dot` Int).
- `sales_order` cũ giữ lại, luôn trỏ **đơn đầu tiên** để báo cáo/màn hình cũ không gãy.
- Patch chép liên kết `sales_order`/`bao_gia` đang có vào bảng `don_hang`.

## 4. Luồng

### 4.1 Tách đợt (Desk)

1. Phiếu gốc ở "Chờ Miyano báo giá" có nút **"Báo giá đợt này"** → hộp thoại
   liệt kê các dòng `items` có `rate > 0`; nhân viên tick chọn.
2. Whitelisted `bao_gia_theo_dot.tach_dot(phieu_goc, dong: list[str])`, trong
   **một giao dịch**:
   - `SELECT … FOR UPDATE` phiếu gốc; kiểm mọi dòng được chọn còn nằm trên
     phiếu gốc (không thì báo "dòng đã được báo ở đợt khác").
   - Tạo Quotation con (`custom_phieu_goc`, `custom_so_dot = max+1`, request_id
     `:dot<N>`), chép các dòng (giữ `rate`, `custom_nguon_gia`, `qty`, `uom`…).
   - Xoá các dòng đó khỏi phiếu gốc; lưu phiếu gốc.
   - Áp hành động **"Gửi khách duyệt"** cho đợt → các chốt hiện có
     (`chot_gui_khach`: đủ giá, không dòng chưa khớp, đặt `valid_till`).
   - Lỗi ở bất kỳ bước nào → rollback cả ba.
3. Nếu phiếu gốc không còn dòng `items` nào **và** không còn dòng đặt ngoài
   chưa xử lý → chuyển "Đã báo hết".
4. Chọn **tất cả** dòng khi phiếu chưa tách đợt nào: vẫn tạo đợt 1 (đơn giản,
   một luồng). Muốn báo cả phiếu theo kiểu cũ thì dùng nút "Gửi khách duyệt"
   trên phiếu gốc như hôm nay (D6).
5. Dòng đặt ngoài (`custom_dat_ngoai`) chưa khớp mã không vào đợt được; ở lại
   phiếu gốc tới khi khớp (luồng khớp hiện có biến nó thành dòng `items`).

Phiếu gốc đã có đợt: chặn "Gửi khách duyệt" trên phiếu gốc (`before_transition`,
thông báo "Phiếu đã báo theo đợt — dùng nút Báo giá đợt này").

### 4.2 Khách đồng ý một đợt

Đúng `bao_gia.dong_y` hiện có trên Quotation đợt → `_sinh_don` sinh Sales Order
(`request_id` `<gốc>:dot<N>:don`). Thêm: ghi một dòng vào `don_hang` của phiếu
đề xuất mua (nếu có) thay vì ghi đè `sales_order`; `sales_order` chỉ đặt khi đang trống.

### 4.3 Đợt bị từ chối hoặc hết hạn → dòng quay về

Hook trên đợt khi `workflow_state` đổi sang **Khách từ chối**, **Miyano từ
chối** hoặc **Báo giá hết hạn** (áp dụng cho nút, job `quet_het_han`, và
chuyển tay), cùng giao dịch:

- Nếu phiếu gốc ở "Đã huỷ phần còn lại" → không trả gì; đợt kết thúc.
- Ngược lại: chép các dòng của đợt vào cuối `items` phiếu gốc (giữ giá vừa báo,
  **không gộp** với dòng trùng mặt hàng), ghi Comment trên phiếu gốc
  "Đợt N bị … — đã trả về X dòng"; nếu phiếu gốc đang "Đã báo hết" → về
  "Chờ Miyano báo giá".
- Đợt cũ giữ nguyên trạng thái để tra lịch sử. Đánh dấu đã trả
  (`custom_da_tra_ve = 1`) để chạy lại hook không trả hai lần.
- Hành động "Mở lại" (Hết hạn → Chờ Miyano báo giá) **bị chặn trên đợt đã trả
  dòng về**; muốn báo lại thì tách đợt mới từ phiếu gốc.

### 4.4 Huỷ phần còn lại

- **Miyano:** nút/hành động "Huỷ phần còn lại" trên phiếu gốc, bắt buộc lý do
  ≥ 10 ký tự (dùng lại `kiem_ly_do_tu_choi`).
- **Khách:** API `portal_bao_gia_huy_con_lai(ten, ly_do=None)`, quyền như
  `portal_bao_gia_dong_y`, kiểm `_bao_gia_cua_toi`.
- Chỉ đụng các dòng còn trên phiếu gốc. Đợt đang "Chờ khách đồng ý" vẫn còn
  hiệu lực; nếu sau đó bị từ chối/hết hạn thì không trả dòng về (4.3).
- Phiếu gốc chưa tách đợt nào: khách dùng "Từ chối" như cũ; không hiện nút này.

### 4.5 Sửa số lượng

`portal_bao_gia_sua_so_luong` áp trên **đợt**: đợt về "Chờ Miyano báo giá" để
Miyano báo lại (y như hôm nay), số lượng vẫn đồng bộ về phiếu đề xuất qua
`_dong_bo_so_luong_duyet_ve_phieu`. Dòng còn ở phiếu gốc chưa có giá thì không sửa.

## 5. Cổng (frontend)

### 5.1 Danh sách (`BaoGiaList.vue`, `portal_bao_gia_danh_sach`)

- Lọc bỏ đợt (`custom_phieu_goc` có giá trị).
- Nhóm của phiếu gốc **đã tách đợt** tính theo thứ tự:
  1. có đợt "Chờ khách đồng ý" → `cho_dong_y`;
  2. còn dòng chưa báo (trạng thái "Chờ Miyano báo giá") → `dang_bao_gia`;
  3. "Đã báo hết" hoặc "Đã huỷ phần còn lại" → `da_dong`.
- `portal_bao_gia_dem` đếm **số đợt** đang chờ khách đồng ý.
- Phiếu chưa tách đợt: tính nhóm như hôm nay.

### 5.2 Chi tiết (`ChiTietBaoGia.vue`, `portal_bao_gia_chi_tiet`)

API trả thêm `dot: [...]` (mỗi đợt: tên, số đợt, trạng thái, `valid_till`,
dòng + giá nếu được xem giá, tổng, `sales_order`, `duoc_dong_y`,
`duoc_sua_so_luong`, `da_tra_ve`) và `con_lai: [...]` (dòng chưa báo, không giá),
`duoc_huy_con_lai`.

- Mỗi đợt một khối: giá, hạn, link PDF (`portal_bao_gia_pdf` theo tên đợt),
  nút **Đồng ý cả đợt / Từ chối / Sửa số lượng** (dùng lại `hanhDongBaoGia`).
  Đợt đã đồng ý → link đơn. Đợt từ chối/hết hạn → nhãn "đã trả về phiếu".
- Khối **"Chờ Miyano báo giá"** liệt kê dòng chưa báo + nút **"Huỷ phần còn
  lại"** (hộp nhập lý do tuỳ chọn).
- Các endpoint đồng ý/từ chối/sửa/PDF nhận tên **đợt**; `_bao_gia_cua_toi` kiểm
  quyền qua phiếu gốc của đợt (đợt chép khách/khoa nên kiểm trực tiếp cũng đúng).

## 6. Email

- "Báo giá sẵn sàng" gửi theo **đợt**, tiêu đề thêm "đợt N" khi `custom_so_dot`.
- Email hết hạn (`bao_gia.py:786`) theo đợt, thêm câu "các mặt hàng đã trả về
  phiếu {gốc}" khi đã trả về.
- Email mới khi **huỷ phần còn lại**: báo bên kia (khách huỷ → nhân viên phụ
  trách; Miyano huỷ → khách), kèm lý do.

## 7. Trường hợp dễ lỗi

| Tình huống | Xử lý |
|---|---|
| Hai nhân viên tách cùng lúc các dòng trùng | `FOR UPDATE` phiếu gốc; người sau nhận lỗi rõ ràng, không đợt trùng. |
| Lỗi giữa chừng khi tách | Một giao dịch; rollback cả tạo đợt, xoá dòng, gửi khách. |
| Bấm "Báo giá đợt này" hai lần | Lần hai không còn dòng được chọn trên phiếu gốc → báo lỗi; `request_id` `:dot<N>` unique chặn tầng DB. |
| Hook trả dòng chạy hai lần | Cờ `custom_da_tra_ve`. |
| Đồng ý đợt cùng lúc huỷ phần còn lại | Hai Quotation khác nhau, không xung đột. |
| Đơn của đợt bị huỷ sau khi sinh | Như hôm nay: dòng **không** quay về phiếu gốc. |
| Phiếu gốc bị xoá/huỷ (docstatus 2) khi còn đợt sống | Chặn bằng kiểm tra tương tự `chan_huy_khi_con_don`. |

## 8. Kiểm thử

Test mới (`miyano_portal/tests/test_bao_gia_theo_dot*.py`, dựng dữ liệu qua `nen_bao_gia.py`):

- tách đợt: hợp lệ; dòng thiếu giá; dòng đặt ngoài chưa khớp; tách hết → "Đã
  báo hết"; tách tranh chấp (giả lập dòng đã bị lấy); chặn "Gửi khách duyệt" phiếu gốc đã có đợt;
- đồng ý đợt → Sales Order đúng `request_id`, bảng `don_hang` phiếu đề xuất,
  `sales_order` cũ chỉ đặt lần đầu;
- từ chối (khách, Miyano) và hết hạn (job) → dòng về phiếu gốc, giữ giá, phiếu
  "Đã báo hết" mở lại; không trả hai lần; chặn "Mở lại" trên đợt đã trả;
- huỷ phần còn lại: Miyano (bắt lý do), khách (lý do tuỳ chọn), khi đang có đợt
  chờ khách, rồi đợt đó bị từ chối → không trả về;
- API cổng: nhóm danh sách, đếm, chi tiết có `dot`/`con_lai`, cách ly khách khác;
- email theo đợt và email huỷ phần còn lại;
- patch `v1_45`: trường, trạng thái workflow, chép `sales_order` vào `don_hang`.

Hồi quy: toàn bộ test miyano_portal (2404 hiện tại) + test frontend
(`bao-gia.js`: nhóm, nút hành động theo đợt).

## 9. Ngoài phạm vi

- Khách chọn từng dòng trong một đợt (D2).
- Huỷ từng mặt hàng lẻ của phần còn lại (D4).
- Tách đợt cho báo giá nội bộ (D8).
- Gộp nhiều đợt vào một Sales Order.
