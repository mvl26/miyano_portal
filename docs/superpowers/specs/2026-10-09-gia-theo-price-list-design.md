# Hàng hoá và đơn giá theo Price List của khách hàng

**Ngày:** 09/10/2026 · **Chủ đầu tư chốt trong phiên** · Nguồn: mục 7 tài liệu
yêu cầu "Hiển thị hàng hóa và đơn giá theo Price List của Khách hàng"

## 1. Vấn đề

Cổng hiện định giá và kiểm soát việc đặt hàng theo **hợp đồng nguyên tắc**
(Blanket Order): mặt hàng thuộc một hợp đồng còn hiệu lực thì có giá và có hạn
mức; mọi mặt hàng khác không có giá và đi vòng báo giá. Một mặt hàng đã có giá
trong bảng giá của khách nhưng không thuộc hợp đồng nào vẫn bị coi là chưa có
giá.

Mục 7 yêu cầu chuỗi **Khách hàng → Price List → Mặt hàng + Đơn giá → Đơn
hàng**: giá khách thấy và giá trên đơn đến từ Price List gán cho khách.

## 2. Các quyết định đã chốt

| # | Quyết định |
|---|---|
| Q1 | Khách vẫn thấy **toàn bộ** vật tư. Mặt hàng có giá trong Price List thì hiện giá; chưa có giá thì vẫn chọn được và đi vòng báo giá. (Khác nguyên văn mục 7.1, theo lời chủ đầu tư.) |
| Q2 | Mặt hàng có giá trong Price List được **đặt ngay** theo giá đó, không qua báo giá. |
| Q3 | Cổng **không còn kiểm soát theo hợp đồng**: bỏ hạn mức, bỏ giá hợp đồng, bỏ mọi hiển thị hợp đồng. Hợp đồng vẫn lập được trên ERP và khi ký vẫn chép giá sang Price List — nó trở thành một cách nạp giá. |
| Q4 | Giá Miyano báo được ghi vào Price List của khách **khi khách bấm đồng ý báo giá**. |
| Q5 | Khách chưa có Price List riêng thì hệ thống **tự tạo** "Bảng giá <tên khách>" và gán. Khách đang dùng chung bảng với khách khác được tách ra bảng riêng. |
| Q6 | Giỏ trộn hàng có giá và hàng chưa có giá được **tách thành hai phiếu ngay lúc gửi**, mỗi phiếu sinh một đơn (giữ quan hệ một phiếu ↔ một đơn). |

Q3 và Q6 thay các quy tắc đã chốt trước đây; danh sách ở §9.

## 3. Nguồn giá

### 3.1 Một hàm tra duy nhất

`gia_bang_gia(customer, item_code) -> float | None`, đặt trong một module mới
`bang_gia_khach.py`. Mọi nơi cần giá gọi hàm này: danh mục, phiếu đề xuất,
dựng đơn, khớp mã hàng gõ tay, đặt lại đơn cũ.

- Đọc `Item Price` với `price_list = Customer.default_price_list`, `selling = 1`.
- Chỉ nhận dòng có `uom` rỗng hoặc bằng `Item.stock_uom` — cổng luôn đặt theo
  đơn vị tính gốc.
- Tôn trọng `valid_from` / `valid_upto` so với ngày hôm nay. Nhiều dòng hợp lệ
  thì lấy dòng có `valid_from` mới nhất.
- `price_list_rate <= 0` là **chưa khai giá**, trả `None` — cùng quy ước
  `gia_hdnt.dong_bo()` đang dùng.
- Khách chưa có `default_price_list` → `None` cho mọi mặt hàng.

Có thêm một hàm tra theo lô `gia_bang_gia_nhieu(customer, item_codes) -> dict`
cho danh mục (một truy vấn cho cả trang).

`gia_hdnt.gia_dong_hop_dong()` không còn người gọi từ phía cổng và được xoá.
`gia_hdnt.dong_bo()`, `dong_bo_khach()`, `tu_hdnt()` giữ nguyên (Q3).

### 3.2 Hai tầng

| | Có giá | Chưa có giá |
|---|---|---|
| `tang` của `portal_catalog_gop` | `"bang_gia"` | `"cho_bao_gia"` |
| `nguon_gia` trên dòng phiếu | `"Bảng giá"` | `"Chờ báo giá"` |
| Dấu trên dòng đơn (§4.2) | `"Bảng giá"` | `"Báo giá"` |
| Loại đơn `custom_loai_don` | `"Theo bảng giá"` | `"Mua lẻ"` (giữ giá trị cũ) |
| Luồng | Thẳng tới Miyano xác nhận | Vòng báo giá |

`tang = "hop_dong"` không còn được trả về. Khoá `nguon_don_gia` thêm ở bản xem
trước ngày 09/10 bị gỡ — `tang` đã nói đủ. Các khoá `blanket_order`, `total`,
`used`, `remaining`, `khong_gioi_han` bị gỡ khỏi response. Danh mục không còn
xếp "hàng hợp đồng trước"; thứ tự là `item_name asc, name asc`.

Giá trị cũ `"Hợp đồng"` (dòng phiếu) và `"Theo HĐNT"` (đơn) giữ trong danh sách
lựa chọn để phiếu và đơn cũ vẫn mở được; không phiếu mới nào nhận chúng.
`"Mua lẻ"` giữ nguyên chữ vì nhiều chốt đang đọc đúng chuỗi đó (hết hạn báo
giá, PDF báo giá, sửa số lượng, thông báo "Báo giá sẵn sàng", và hai chỗ viết
cứng ở `KhoiBaoGia.vue`, `don-actions.js`).

## 4. Phiếu và đơn

### 4.1 Tách giỏ trộn (Q6)

Áp cho cả hai đường tạo phiếu: quản lý đặt trực tiếp (`portal_order_place`) và
khoa gửi đề xuất.

- Lúc gửi, các dòng được chia theo §3.2. Dòng gõ tay "hàng chưa có mã" luôn
  thuộc nhóm chờ báo giá.
- Cả hai nhóm đều có dòng → tạo **hai** `Portal De Xuat Mua`. Chỉ một nhóm có
  dòng → một phiếu như hiện nay.
- Hai phiếu mang chung `ma_lan_dat` (trường mới, Data, chỉ đọc) và mỗi phiếu có
  `phieu_cung_lan_dat` (Link tới phiếu kia). Phiếu đơn lẻ để trống cả hai.
- Thông tin chung (lý do, ngày cần, địa chỉ, ghi chú, khoa) chép sang cả hai.
- Chống gửi trùng (`request_id`): một `request_id` của client ứng với một lần
  đặt; hai phiếu nhận `request_id` gốc kèm hậu tố `:gia` và `:baogia`. Gửi lại
  cùng `request_id` trả về đúng hai phiếu đã tạo.
- Việc tách chạy trong một giao dịch: hoặc cả hai phiếu được tạo, hoặc không
  phiếu nào.

Phiếu nháp chưa gửi vẫn là một phiếu; việc tách xảy ra ở bước gửi duyệt (khoa)
hoặc bước đặt (quản lý). Màn Đặt hàng báo trước cho người dùng (§7).

### 4.2 Dựng đơn (`dat_hang._xay_don`)

- Dòng có giá: `rate = price_list_rate = gia_bang_gia(...)`.
- Dòng chưa có giá: `rate = 0`, `price_list_rate = 0` như hiện nay.
- Mỗi dòng `Sales Order Item` nhận `custom_nguon_gia` (trường mới, Select
  `Bảng giá` / `Báo giá`, chỉ đọc). Dòng do nhân viên thêm tay trên ERP để
  trống.
- `selling_price_list` của đơn luôn là `Customer.default_price_list` (mục 7.3).
  Khách chưa có bảng giá thì gọi `dam_bao_bang_gia_rieng()` (§5.3) trước.
- **Không** đặt `blanket_order` / `against_blanket_order` trên dòng: ERPNext
  tự chặn đặt vượt số lượng hợp đồng khi dòng có liên kết đó
  (`validate_against_blanket_order`). Hệ quả đã được chấp nhận: `ordered_qty`
  trên hợp đồng ở ERP không còn tăng theo đơn từ cổng.
- Gỡ: kiểm hạn mức (`het_han_muc`, `vuot_han_muc`), lỗi `thieu_gia`, thông báo
  `bao_thieu_gia`, `custom_hdnt` trên đơn mới, và việc chọn công ty theo hợp
  đồng (dùng `resolve_ban_le_company` cho mọi đơn).
- `custom_loai_don` theo §3.2: còn ít nhất một dòng `"Báo giá"` hoặc một dòng
  gõ tay thì là `"Mua lẻ"`, ngược lại là `"Theo bảng giá"`. Nhờ §4.1 đơn
  thường chỉ có một loại dòng; ngoại lệ duy nhất là ca giá xuất hiện giữa lúc
  gửi và lúc duyệt (§4.3).

### 4.3 Giá đổi giữa lúc gửi và lúc duyệt

- `_dong_dau_gia` (lúc gửi duyệt) đóng dấu `don_gia` cho dòng `"Bảng giá"`.
- Lúc duyệt, đơn lấy giá Price List tại thời điểm đó (hành vi hiện có: giá được
  suy lại khi dựng đơn).
- `_kiem_gia_doi` so giá đóng dấu với giá hiện hành và trả `canh_bao_gia`.
  Phần hợp đồng trong hàm này bị gỡ; chỉ còn loại `gia_doi`. Màn duyệt hiện
  cảnh báo này (hiện chưa màn nào đọc nó).
- Phiếu `"Bảng giá"` có dòng **mất giá** lúc duyệt → chặn duyệt, nêu tên mặt
  hàng, yêu cầu khoa gửi lại. Không tự chuyển sang vòng báo giá.
- Phiếu `"Chờ báo giá"` có dòng **vừa có giá** lúc duyệt → dòng đó nhận giá
  Price List và dấu `"Bảng giá"`; đơn vẫn là đơn báo giá. Nếu **mọi** dòng đều
  đã có giá thì đơn là `"Theo bảng giá"` và đi thẳng.
- `_kiem_han_muc` lúc duyệt bị xoá.

### 4.4 Các đường phụ

- **Khớp mã hàng gõ tay** (`_gop_hoac_them_dong_hang`): mã khớp có giá trong
  Price List của khách → dòng nhận giá đó và dấu `"Bảng giá"`. Chưa có giá →
  `rate = 0`, dấu `"Báo giá"`.
- **Đặt lại đơn cũ** (`portal_reorder`): bỏ các lý do loại `ngoai_hdnt`,
  `het_han_muc`, `thieu_gia`. Mọi dòng còn bán được vào giỏ kèm `tang` hiện
  hành; giỏ được tách theo §4.1 khi gửi.
- **Khách sửa số lượng ở "Chờ khách đồng ý"** (`portal_order_sua_so_luong`):
  chỉ áp cho đơn `"Mua lẻ"` như hiện nay. Dòng dấu `"Bảng giá"` bị sửa số
  lượng thì đọc lại giá Price List thay vì về 0; dòng `"Báo giá"` về 0 như cũ.

## 5. Luồng báo giá và ghi giá

### 5.1 Hai chốt mới trên workflow

Cài bằng hook `validate` của `Sales Order` (cùng chỗ với
`ghi_ngay_gui_khach_duyet`), đọc sự chuyển trạng thái:

1. **Đơn báo giá bắt buộc qua khách.** `custom_loai_don == "Mua lẻ"` và đơn
   chuyển từ "Chờ xác nhận" sang "Chờ Miyano xác nhận" (nút "Gửi duyệt") →
   chặn: "Đơn có hàng chờ báo giá — dùng «Gửi khách duyệt»."
2. **Chưa đủ giá thì chưa gửi khách.** Đơn chuyển sang "Chờ khách đồng ý" mà
   còn dòng `rate == 0` (trừ dòng giữ chỗ) → chặn, nêu dòng nào.

### 5.2 Ghi giá khi khách đồng ý (Q4)

Trong `portal_order_accept`, nhánh `dong_y`, sau khi `apply_workflow` thành
công, gọi `bang_gia_khach.ghi_gia_da_dong_y(so)`:

- Chỉ chạy cho đơn `"Mua lẻ"`. Chỉ xét dòng `custom_nguon_gia == "Báo giá"`
  và `rate > 0`.
- Bảo đảm khách có bảng giá riêng (§5.3).
- Giá ghi theo đơn vị gốc: `rate / conversion_factor` khi dòng dùng đơn vị
  khác `stock_uom`.
- Khoá ghi `{item_code, price_list, selling: 1}` trong các dòng có `uom` rỗng
  hoặc bằng `stock_uom`. Có dòng → cập nhật `price_list_rate`, đặt
  `valid_from` = hôm nay, xoá `valid_upto`. Chưa có → tạo mới với
  `uom = stock_uom`, tiền tệ của Price List.
- Một mặt hàng xuất hiện trên nhiều dòng với giá khác nhau → lấy dòng sau cùng
  và ghi cảnh báo vào nhật ký.
- Đóng dấu `custom_gia_khach_dong_y` (trường mới, Currency, chỉ đọc) trên dòng
  đơn bằng đúng `rate` lúc đồng ý — nguồn so sánh của §5.4.
- Ghi một Comment trên đơn và một dòng nhật ký thao tác liệt kê: mặt hàng,
  giá cũ (hoặc "chưa có"), giá mới, người đồng ý.

Lỗi trong bước này **không** làm hỏng việc đồng ý: bọc `try/except`, ghi
Error Log gắn với đơn, và gửi thông báo cho nhân viên phụ trách. Cùng nguyên
tắc với mọi bước phụ khác của app.

Khách không đồng ý, hoặc báo giá hết hạn: không ghi gì.

### 5.3 Bảng giá riêng (Q5)

`bang_gia_khach.dam_bao_bang_gia_rieng(customer) -> str`:

- Khách có `default_price_list` và bảng đó chỉ là mặc định của **một** khách
  đang hoạt động → trả về nguyên.
- Chưa có → tạo Price List `Bảng giá <tên khách>` (selling, VND, enabled), gán
  vào `default_price_list`.
- Đang dùng chung → tạo bảng riêng như trên, chép mọi `Item Price` selling của
  bảng chung sang, gán lại.
- Tên trùng một bảng đã tồn tại → thêm hậu tố mã ngắn của khách.

Người gọi: `ghi_gia_da_dong_y` (§5.2), `_xay_don` (§4.2), `gia_hdnt.dong_bo`
(thay cho việc từ chối ghi khi bảng dùng chung hoặc khách chưa có bảng), và
patch chuyển đổi (§6).

### 5.4 Giá bị sửa sau khi khách đồng ý

`before_submit` của `Sales Order`: với đơn `"Mua lẻ"`, dòng nào có
`custom_gia_khach_dong_y > 0` mà `rate` khác giá đó → chặn xác nhận: "Đơn giá
dòng … khác giá khách đã đồng ý — gửi khách duyệt lại." Khi đơn quay về "Chờ
xác nhận" (khách sửa số lượng, hoặc nhân viên gửi lại), `custom_gia_khach_
dong_y` của các dòng bị xoá để vòng đồng ý sau đóng dấu lại.

## 6. Chuyển đổi dữ liệu

Một patch `v1_41`, chạy một lần, theo thứ tự:

1. Thêm trường: `Sales Order Item.custom_nguon_gia`,
   `Sales Order Item.custom_gia_khach_dong_y`,
   `Portal De Xuat Mua.ma_lan_dat`, `Portal De Xuat Mua.phieu_cung_lan_dat`;
   thêm lựa chọn `"Bảng giá"` cho `nguon_gia` của dòng phiếu và
   `"Theo bảng giá"` cho `custom_loai_don`.
2. Gọi `dam_bao_bang_gia_rieng()` cho mọi khách đang hoạt động.
3. Gọi `gia_hdnt.dong_bo_khach()` cho mọi khách có hợp đồng Selling đã ký còn
   hiệu lực. **Bắt buộc và phải sau bước 2**: nhiều khách hiện chỉ có giá nhờ
   hợp đồng (bảng giá của họ không có dòng `Item Price` nào), bỏ đọc giá hợp
   đồng mà không chép trước thì hàng của họ rơi về "chờ báo giá".
4. Cập nhật workflow nếu cần cho §5.1 (không thêm trạng thái mới).

Ngoài patch: `migration/import_erpnext.py` thôi gán lại
`Customer.default_price_list` về bảng theo hợp đồng mới nhất; thay vào đó ghi
giá hợp đồng vào bảng riêng của khách qua `dam_bao_bang_gia_rieng()`.

Phiếu và đơn đang dở lúc chuyển đổi giữ nguyên `nguon_gia`, `blanket_order`,
giá và loại đơn đã đóng dấu. Dòng đơn cũ có `custom_nguon_gia` rỗng; §5.2 bỏ
qua chúng, nên đơn báo giá đang chờ khách lúc chuyển đổi sẽ không ghi giá khi
được đồng ý. Patch điền dấu `"Báo giá"` cho các dòng của đơn `"Mua lẻ"` đang
ở "Chờ xác nhận" hoặc "Chờ khách đồng ý" mà không có `blanket_order`, để chúng
đi đúng luật mới.

**Kiểm sau patch:** với Bệnh viện Đa khoa Minh Đức (DEMO), ba mặt hàng hợp đồng
MYN-SYR-10, MYN-GLOVE-M, MYN-ALT phải hiện `tang = "bang_gia"` với giá 88.000,
95.000 và 1.250.000.

## 7. Giao diện

| Màn | Thay đổi |
|---|---|
| `LapPhieu.vue` | Nhãn tầng còn "Bảng giá <giá>" và "Chờ báo giá". Gỡ cột "Hạn mức", cảnh báo vượt hạn mức, cột tên hợp đồng trong giỏ. Giỏ hiện thành tiền từng dòng có giá và tổng tạm tính của phần có giá. Giỏ trộn hiện thông báo trước khi gửi: "Lần đặt này sẽ tách thành 2 phiếu: N mặt hàng đặt ngay, M mặt hàng chờ báo giá." Sau khi gửi, điều hướng về danh sách (hai phiếu) thay vì chi tiết một phiếu. |
| Danh sách yêu cầu | Hai phiếu cùng lần đặt hiện `ma_lan_dat`. |
| `ChiTietYeuCau.vue` | Đường dẫn "Phiếu cùng lần đặt". Gỡ tên hợp đồng ở đầu trang. Màn duyệt hiện `canh_bao_gia` và nút "Duyệt cả hai" khi phiếu kia cũng đang chờ duyệt. |
| `BangMatHang.vue` | Phiếu chưa có đơn hiện `don_gia` đã đóng dấu của dòng `"Bảng giá"`. |
| `Dashboard.vue` | Gỡ thẻ "Hợp đồng khung" và thanh "Hạn mức đã sử dụng". |
| `Profile.vue` | Gỡ bảng hợp đồng. |
| Đặt lại đơn cũ | Gỡ các lý do loại theo hợp đồng và hạn mức. |
| ERP (Desk) | Cột `custom_nguon_gia` trên lưới dòng đơn. |

Các endpoint không còn màn nào gọi (`portal_contracts`, `portal_catalog`,
`portal_catalog_ban_le`) bị xoá cùng test của chúng.

## 8. Kiểm thử

Viết test trước cho từng phần. Test mới:

- `bang_gia_khach`: tra giá (không bảng, giá 0, đơn vị khác, hết hiệu lực,
  nhiều dòng), bảng giá riêng (chưa có, dùng chung, trùng tên), cách ly giữa
  hai khách.
- Tách giỏ: chỉ có giá, chỉ chờ báo giá, trộn, có dòng gõ tay, gửi trùng
  `request_id`, lỗi giữa chừng không để lại phiếu mồ côi.
- Dựng đơn: dấu nguồn giá, `selling_price_list`, không liên kết hợp đồng, đặt
  vượt số lượng hợp đồng không còn bị chặn.
- Duyệt: mất giá thì chặn, vừa có giá thì nhận giá, cảnh báo đổi giá.
- Workflow: hai chốt §5.1, chốt §5.4.
- Ghi giá: tạo mới, cập nhật, quy đổi đơn vị, không ghi khi từ chối/hết hạn,
  không ghi dòng `"Bảng giá"`, lỗi ghi không làm hỏng việc đồng ý.
- Patch: chạy hai lần cho cùng kết quả; phép kiểm Minh Đức ở §6.

Test hiện có phải viết lại theo luật mới (không xoá, trừ test của endpoint bị
xoá): `test_nguon_gia_dong`, `test_catalog_gop`, `test_gia_tu_hop_dong`,
`test_han_muc_don_tron`, `test_dat_hang_gop`, `test_e1_loi_co_cau_truc`,
`test_e1_thieu_gia_va_reorder`, `test_e1_han_muc_khong_gioi_han`,
`test_order_place`, `test_portal_read`, `test_portal_context`, và một phần của
`test_e6_mua_le`, `test_de_xuat_duyet`, `test_khop_ma_dat_ngoai`,
`test_don_tron_bao_gia`, `test_e2_workflow_va_accept`,
`test_gia_bang_gia_tren_danh_muc`. Test khẳng định đúng điều bị đảo (ví dụ
`test_hang_ngoai_hop_dong_khong_nhat_gia_cu_trong_bang_gia`) được đảo kỳ vọng
kèm ghi chú dẫn về spec này. `test_e1_dong_bo_gia_hdnt` phần lớn giữ nguyên.

## 9. Quy tắc bị thay

Ghi "đã thay bởi quyết định 09/10/2026" tại nguồn, cập nhật trong đợt này cho
BA và bản đồ chức năng:

- QĐ-8, BR-O15 (hạn mức, `qty = 0` là không giới hạn); BR-O2, BR-O3; NL-1.1 –
  NL-1.4, NL-1.11; BR-R3 ("dòng mua lẻ luôn rate = 0"); VĐ-7.
- QĐ-G1 (nguồn giá suy từ hợp đồng), QĐ-G3 (đơn trộn đi một vòng báo giá),
  QĐ-G8, QĐ-G9, QĐ-G10 (hàng hợp đồng đứng trước), QĐ-G12 (giá hợp đồng trước,
  Item Price sau), QĐ-G14; Ruling P14, P28, P31.
- Ruling P32 (không ghi vào bảng giá dùng chung) được thay bằng việc tách bảng
  riêng (§5.3).

Ba tài liệu hướng dẫn sử dụng (`HDSD-*.md`) cập nhật sau khi tính năng chạy ổn.

## 10. Ngoài phạm vi

- Hạn sử dụng tối thiểu theo từng dòng (mục 7.2, 7.4).
- Kiểm tồn kho và hạn dùng, giữ hàng, đề xuất Material Request (mục 7.4).
- Khoá không cho nhân viên Miyano sửa giá dòng `"Bảng giá"` trên ERP.
- Lịch sử giá ngoài Comment và nhật ký thao tác của §5.2.
