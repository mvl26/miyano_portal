# Yêu cầu báo giá bằng Quotation, tách khỏi đơn hàng

**Ngày:** 12/10/2026 · **Chủ đầu tư chốt trong phiên** · Nguồn: mục 5 tài liệu
yêu cầu "Yêu cầu báo giá đối với hàng hóa chưa có"

**Phụ thuộc:** spec `2026-10-09-gia-theo-price-list-design.md` và nhánh
`feat/thoi-gian-giao-hang-va-gia-bang-gia`. Bản này xây TRÊN những gì nhánh đó
tạo ra (`bang_gia_khach`, `tach_phieu`, `chot_bao_gia`, trường
`custom_nguon_gia`, `custom_gia_khach_dong_y`). Việc viết mã chỉ bắt đầu khi
nhánh đó đã vào `main`.

## 1. Vấn đề

Hàng chưa có giá trong Price List và hàng mới chưa có mã hôm nay đi "vòng báo
giá" ngay trên một **Sales Order** loại `"Mua lẻ"`: đơn được tạo trước, Miyano
điền giá lên đơn, khách đồng ý trên đơn. Báo giá và đơn hàng là cùng một chứng
từ, nên:

- một báo giá khách từ chối hay để hết hạn vẫn nằm lại như một đơn hàng nháp;
- danh sách đơn hàng trên cổng lẫn cả thứ chưa phải đơn hàng;
- bộ phận báo giá không có hàng việc riêng trên ERP.

Mục 5 yêu cầu chuỗi **Khách yêu cầu → Yêu cầu báo giá → ERP tạo Quotation
(nháp) → bộ phận phụ trách xử lý → gửi báo giá cho khách**, và một tab "Yêu
cầu báo giá" riêng trên cổng.

Phần "hàng có giá thì đặt được luôn, tách riêng" của mục 5 đã do spec 09/10
giải quyết (tách giỏ trộn thành hai phiếu, quyết định Q6). Bản này không làm
lại phần đó.

## 2. Các quyết định đã chốt

| # | Quyết định |
|---|---|
| Q1 | Yêu cầu báo giá là chứng từ **Quotation** của ERPNext, không phải Sales Order. Sales Order chỉ sinh ra khi khách đồng ý. |
| Q2 | **Thay hẳn** luồng cũ cho mọi yêu cầu mới. Đơn `"Mua lẻ"` đang dở chạy nốt theo luồng cũ; không chuyển đổi dữ liệu. |
| Q3 | Khách duyệt **cả báo giá** (đồng ý hoặc từ chối), và được **sửa số lượng** trước khi đồng ý. Không chọn từng dòng. |
| Q4 | Hàng khách gõ tay phải được **khớp hoặc tạo mã trước khi gửi báo giá**. Báo giá khách nhận chỉ gồm hàng có mã thật. |
| Q5 | Cổng **tách hẳn hai tab**: "Đơn hàng" và "Yêu cầu báo giá". Yêu cầu báo giá không nằm trong tab Đơn hàng. |
| Q6 | Workflow mới phủ **mọi** Quotation trên ERP, kể cả báo giá nhân viên tự lập ngoài cổng (§4.1). *(Em đề xuất vì Frappe không cho giới hạn workflow theo từng chứng từ; chờ anh xác nhận khi xem lại spec.)* |

## 3. Chứng từ

### 3.1 Quotation

Mỗi phiếu `Portal De Xuat Mua` thuộc nhóm chờ báo giá sinh đúng **một**
Quotation:

- `quotation_to = "Customer"`, `party_name` = khách, `order_type = "Sales"`.
- `company` chọn bằng `resolve_ban_le_company` (như đơn từ cổng hiện nay).
- `selling_price_list` = Price List riêng của khách
  (`bang_gia_khach.dam_bao_bang_gia_rieng`).
- `valid_till` để trống lúc tạo; được đặt khi gửi khách (§4.2).

Trường thêm trên `Quotation` (custom field, cùng tên với trường tương ứng trên
Sales Order để mã và mẫu in dùng chung được):

| Trường | Kiểu | Việc |
|---|---|---|
| `custom_nguon_don` | Select | `"Client Portal"` — phân biệt với Quotation nhân viên tự lập |
| `custom_de_xuat` | Link → Portal De Xuat Mua | Phiếu gốc |
| `custom_khoa_phong` | Link → Customer Department | Trục phân quyền khoa trên cổng |
| `custom_ten_don_hang` | Data | Tên khách đặt cho lần đặt |
| `custom_request_id` | Data, unique, `no_copy` | Chống tạo trùng. Bằng `request_id` của phiếu gốc (giá trị hôm nay truyền cho `tao_sales_order`) |
| `custom_dat_ngoai` | Table → Sales Order Dat Ngoai Item | Dòng khách gõ tay chưa khớp mã |
| `custom_ngay_gui_khach_duyet` | Datetime, `no_copy` | Mốc tính hạn hiệu lực |
| `custom_ly_do_tu_choi` | Small Text, `no_copy` | Lý do khi Miyano hoặc khách từ chối |

Ba trường `no_copy` là bắt buộc, không phải cho gọn: mapper Quotation → Sales
Order chép mọi trường cùng tên. Không chặn thì đơn sinh ra mang
`custom_request_id` của báo giá (trường đó unique trên Sales Order và là khoá
`_insert_so_idempotent` tra đơn), cùng một ngày gửi duyệt và một lý do từ chối
không thuộc về nó.

`Portal De Xuat Mua` thêm trường `bao_gia` (Link → Quotation, chỉ đọc).

### 3.2 Chuỗi một-một

`Portal De Xuat Mua` → `Quotation` → `Sales Order`. Phiếu giữ cả `bao_gia` và
`sales_order`; `sales_order` chỉ được điền khi khách đồng ý. Quy tắc "một
phiếu một đơn" của hệ thống giữ nguyên, chỉ thêm một mắt xích ở giữa cho phiếu
chờ báo giá.

### 3.3 Dòng gõ tay và dòng giữ chỗ

Dòng khách gõ tay đi theo đúng cơ chế đang chạy trên Sales Order: nằm ở
`custom_dat_ngoai`, nhân viên khớp mã thì dòng chuyển thành một dòng `items`
thật. ERPNext không lưu được Quotation với bảng `items` rỗng, nên báo giá chỉ
gồm dòng gõ tay vẫn mang **dòng giữ chỗ** như Sales Order hôm nay.

Phần mã khớp dòng và giữ chỗ trong `portal_mua_le.py` hiện viết cho Sales
Order. Nó được tổng quát hoá để nhận cả hai doctype, không sao chép thành bản
thứ hai.

## 4. Trạng thái và các bước

### 4.1 Workflow `Quotation - Client Portal`

Frappe chỉ cho MỘT workflow hoạt động trên mỗi doctype và nó phủ mọi chứng từ
của doctype đó (`frappe.model.workflow.get_workflow_name`); không giới hạn
được theo `custom_nguon_don`. Workflow này vì thế phủ **mọi** Quotation, đúng
như "Sales Order - Client Portal" đang phủ mọi Sales Order (Q6). Báo giá nhân
viên tự lập ngoài cổng đi cùng các trạng thái, với một bước riêng ở dòng cuối
bảng chuyển tiếp.

| Trạng thái | `docstatus` | Ai giữ việc |
|---|---|---|
| Chờ Miyano báo giá | 0 | Bộ phận báo giá |
| Chờ khách đồng ý | 0 | Khách |
| Khách đã đồng ý | 1 | Hệ thống (sinh đơn) |
| Khách từ chối | 0 | Kết thúc |
| Miyano từ chối | 0 | Kết thúc |
| Báo giá hết hạn | 0 | Kết thúc |

| Từ | Hành động | Tới | Ai |
|---|---|---|---|
| Chờ Miyano báo giá | Gửi khách duyệt | Chờ khách đồng ý | Sales User |
| Chờ Miyano báo giá | Từ chối (bắt buộc lý do) | Miyano từ chối | Sales User |
| Chờ khách đồng ý | Thu hồi để sửa | Chờ Miyano báo giá | Sales User |
| Chờ khách đồng ý | Khách đồng ý | Khách đã đồng ý | System Manager (endpoint cổng) |
| Chờ khách đồng ý | Khách từ chối | Khách từ chối | System Manager (endpoint cổng) |
| Chờ khách đồng ý | Khách sửa số lượng | Chờ Miyano báo giá | System Manager (endpoint cổng) |
| Chờ khách đồng ý | Báo giá hết hạn | Báo giá hết hạn | System Manager (job hằng ngày) |
| Chờ khách đồng ý | Ghi nhận khách đồng ý | Khách đã đồng ý | Sales User, chỉ khi `custom_nguon_don` khác `"Client Portal"` |

**Khách không có vai nào trong workflow.** Bốn bước phía khách khai
`allowed = System Manager`, đúng như các bước "Khách đồng ý" / "Khách huỷ" /
"Báo giá hết hạn" của workflow Sales Order hôm nay. Endpoint cổng tự kiểm
quyền của khách trên chính báo giá đó rồi mới chạy `apply_workflow` bằng cơ
chế nâng quyền có sẵn trong `portal_order_accept`: tạm đổi
`frappe.session.user` trong một khối `try/finally`, không gọi
`frappe.set_user()` (lý do ghi tại hàm đó). Cơ chế này được tách thành một hàm
dùng chung thay vì chép lần thứ hai.

Dòng cuối là đường cho báo giá ngoài cổng: khách của các báo giá đó không có
tài khoản cổng, nên nhân viên tự ghi nhận. Điều kiện trên bước chuyển chặn
nhân viên bấm thay khách của cổng.

Quotation ở dạng nháp cho tới khi khách đồng ý, để giá và số lượng còn sửa
được. ERPNext chỉ cho sinh Sales Order từ Quotation đã Submit, nên Submit xảy
ra đúng lúc khách bấm đồng ý — cùng cách đơn hàng hiện nay ở dạng nháp cho tới
khi Miyano xác nhận.

Ba trạng thái kết thúc để `docstatus = 0` theo tiền lệ `"Từ chối"` của workflow
Sales Order: một chứng từ nháp không huỷ được, và chúng không còn hành động
nào.

### 4.2 Chốt khi gửi khách duyệt

Hook `validate` của Quotation, đọc sự chuyển sang "Chờ khách đồng ý". Chặn và
nêu rõ dòng nào khi:

1. còn dòng trong `custom_dat_ngoai` chưa khớp mã (Q4);
2. còn dòng giữ chỗ;
3. còn dòng `rate <= 0`.

Qua chốt thì ghi `custom_ngay_gui_khach_duyet` = lúc này và
`valid_till` = ngày đó + số ngày hiệu lực trong Portal Settings
(`hieu_luc_bao_gia_ngay`, hàm hiện có).

### 4.3 Khách sửa số lượng

Chỉ sửa số lượng các dòng đã có trên báo giá; không thêm, không xoá dòng, không
đặt về 0 (muốn bỏ thì từ chối). Sau khi sửa:

- báo giá quay về "Chờ Miyano báo giá";
- **đơn giá giữ nguyên** làm gợi ý, `valid_till` và
  `custom_ngay_gui_khach_duyet` bị xoá;
- nhân viên phụ trách được báo, kèm danh sách dòng đổi
  (`portal_thong_bao.bao_khach_sua_so_luong`).

Khác luồng cũ ở chỗ giá không bị đưa về 0. Miyano vẫn phải bấm "Gửi khách
duyệt" lại, nên vẫn có một lần xem lại giá theo số lượng mới; không bắt gõ lại
mọi giá khi phần lớn không đổi.

### 4.4 Khách đồng ý

Trong một giao dịch:

1. Từ chối nếu báo giá đã quá `valid_till` — báo "báo giá đã hết hạn", không
   đồng ý được dù job hết hạn chưa kịp chạy.
2. Chuyển workflow sang "Khách đã đồng ý" (Submit Quotation).
3. Sinh Sales Order bằng mapper gốc của ERPNext, gọi bản nội bộ
   `quotation._make_sales_order(ten, ignore_permissions=True)`: bản whitelist
   `make_sales_order` kiểm quyền của người gọi, mà khách không có quyền nào
   trên Quotation (§8). Rồi điền phần của cổng:
   - `custom_request_id` = `<request_id của báo giá>:don`;
   - trạng thái "Chờ Miyano xác nhận". Workflow không cho chèn chứng từ mới
     thẳng vào một trạng thái khác trạng thái đầu, nên đơn được chèn ở trạng
     thái đầu rồi đặt trạng thái bằng `frappe.db.set_value`, theo đúng tiền lệ
     trong `de_xuat_duyet.duyet_va_tao_don`;
   - `custom_loai_don = "Theo báo giá"` (giá trị mới);
   - `custom_nguon_don`, `custom_khoa_phong`, `custom_de_xuat`,
     `custom_ten_don_hang`, ngày giao và địa chỉ từ phiếu gốc;
   - mỗi dòng: `custom_nguon_gia = "Báo giá"`,
     `custom_gia_khach_dong_y = rate`, kho theo `_resolve_item_warehouse`.
4. Ghi `sales_order` lên phiếu gốc; chuyển phiếu sang trạng thái có đơn.
5. Ghi giá vào Price List của khách: `bang_gia_khach.ghi_gia_da_dong_y`, cho
   nhận cả Quotation. Lỗi ở bước này **không** làm hỏng việc đồng ý (nguyên
   tắc hiện có: bọc lại, ghi Error Log, báo nhân viên phụ trách).

Bước 1–4 hỏng thì cả giao dịch lùi lại: không có báo giá "đã đồng ý" mà không
có đơn.

Gọi lại "đồng ý" trên báo giá đã đồng ý trả về đúng đơn đã sinh, không sinh
đơn thứ hai.

### 4.5 Sau khi có đơn

`"Theo báo giá"` cố ý là một giá trị KHÁC `"Mua lẻ"`. Mọi chốt của luồng cũ
hỏi `portal_mua_le.di_vong_bao_gia()`, và hàm đó đọc đúng dấu
`custom_loai_don == "Mua lẻ"` chứ không suy từ dòng. Đơn `"Theo báo giá"` vì
thế là đơn thường đối với tất cả chúng — vòng báo giá của nó đã xong trên
Quotation:

| Nơi đọc dấu `"Mua lẻ"` | Với đơn `"Theo báo giá"` |
|---|---|
| `portal_order_track` (banner hạn hiệu lực) | Không hiện banner |
| `portal_bao_gia_pdf` trên đơn | Không áp dụng; PDF báo giá lấy từ Quotation |
| `portal_order_accept`, `portal_order_sua_so_luong` | Từ chối như với mọi đơn thường |
| `portal_bao_gia.quet_bao_gia_het_han` (lọc CSDL) | Không quét |
| Notification "Portal - Báo giá sẵn sàng" trên Sales Order | Không gửi |
| `chot_bao_gia.kiem_chuyen_trang_thai` | Không áp dụng (đơn không qua "Chờ xác nhận") |
| `Portal De Xuat Mua._kiem_don_dung_duoc_xin_sua` | Như đơn thường |
| `KhoiBaoGia.vue`, `don-actions.js` (so chuỗi cứng) | Không hiện khối báo giá, không hiện nút của vòng báo giá |
| `chot_bao_gia.kiem_gia_khop_gia_da_dong_y` | **Mở rộng** để áp cho cả `"Theo báo giá"` |

Mỗi dòng trong bảng có một test khẳng định đúng hành vi đó (§11).

Đơn `"Theo báo giá"` đi tiếp như mọi đơn: Miyano xác nhận, giao, hoá đơn. Chốt
`chot_bao_gia.kiem_gia_khop_gia_da_dong_y` (đơn giá khác giá khách đã đồng ý
thì không xác nhận được) mở rộng cho loại đơn này. Bảng đối sánh tồn kho trên
Sales Order hoạt động bình thường vì đơn chỉ gồm hàng có mã.

### 4.6 Hết hạn

Job hằng ngày `portal_bao_gia.quet_bao_gia_het_han` quét thêm Quotation ở "Chờ
khách đồng ý" có `valid_till` trước hôm nay: chuyển "Báo giá hết hạn", gửi
email hai phía như hiện nay, cập nhật phiếu gốc. Job vẫn quét Sales Order
`"Mua lẻ"` cũ cho tới khi hết đơn dở.

Job gốc của ERPNext (`set_expired_status`) chỉ đụng Quotation đã Submit nên
không tranh việc với job này.

## 5. Tạo báo giá

Hai đường tạo phiếu (khoa gửi đề xuất và được duyệt; quản lý đặt trực tiếp)
hôm nay đều gọi `dat_hang.tao_sales_order`. Sau bản này, tại đúng chỗ đó:

| Phiếu | Tạo |
|---|---|
| Nhóm có giá (`nguon_gia = "Bảng giá"`) | Sales Order `"Theo bảng giá"`, như spec 09/10 |
| Nhóm chờ báo giá, mọi dòng **vừa có giá** lúc duyệt và không có dòng gõ tay | Sales Order `"Theo bảng giá"`, như spec 09/10 §4.3 |
| Nhóm chờ báo giá, còn lại | **Quotation** ở "Chờ Miyano báo giá" |

Một module mới `miyano_portal/bao_gia.py` dựng Quotation: dòng đã có giá trong
Price List nhận sẵn giá đó, dòng chưa có giá `rate = 0`, dòng gõ tay vào
`custom_dat_ngoai`. Chống tạo trùng bằng `custom_request_id`, cùng luật với
`_insert_so_idempotent`.

Sales Order `"Mua lẻ"` **không còn được tạo mới**. Giá trị đó giữ trong danh
sách lựa chọn để đơn cũ mở được.

Khi báo giá được tạo, nhân viên phụ trách khách được báo
(`portal_thong_bao.bao_yeu_cau_moi`, thêm đường dẫn tới Quotation).

## 6. Cổng khách hàng

### 6.1 Hai tab

Màn "Danh sách đơn hàng" có hai tab:

- **Đơn hàng** — như hiện nay, gồm phiếu có giá, đơn hàng, và đơn `"Mua lẻ"`
  cũ đang dở.
- **Yêu cầu báo giá** — phiếu chờ báo giá và Quotation của chúng.

Luật xếp tab cho một phiếu chờ báo giá (`nguon_gia = "Chờ báo giá"`):

| Phiếu | Tab |
|---|---|
| Có `sales_order`, không có `bao_gia` (đơn `"Mua lẻ"` cũ) | Đơn hàng, như hôm nay |
| Có `bao_gia` | Yêu cầu báo giá |
| Chưa có cả hai (nháp, chờ duyệt nội bộ, bị từ chối nội bộ) | Yêu cầu báo giá |

Dòng đầu là điều giữ cho đơn dở của luồng cũ không biến mất khỏi tab Đơn hàng
và không bị xếp nhầm vào nhóm nháp của tab kia. Phiếu chưa có Quotation nằm ở
tab Yêu cầu báo giá ngay từ đầu để khách không phải tìm ở hai nơi.

Khi khách đồng ý, đơn sinh ra xuất hiện ở tab Đơn hàng; báo giá ở lại tab của
nó ở nhóm "Đã đồng ý", hai bên có đường dẫn qua lại.

### 6.2 Nhóm lọc trong tab Yêu cầu báo giá

Tab là lọc theo **loại**, bên trong vẫn có vòng đời riêng:

| Nhóm | Gồm |
|---|---|
| Nháp / chờ duyệt nội bộ | Phiếu chưa có `bao_gia` **và** chưa có `sales_order` |
| Miyano đang báo giá | Chờ Miyano báo giá |
| Chờ anh/chị đồng ý | Chờ khách đồng ý |
| Đã đồng ý | Khách đã đồng ý |
| Đã đóng | Khách từ chối, Miyano từ chối, Báo giá hết hạn |

Không dùng lại nhãn "Chờ báo giá": nhãn đó đã từng bị đọc ngược (khách tưởng
mình đang chờ, trong khi việc đang ở phía họ) và đã được đổi thành "chờ khách
đồng ý". Hai nhóm ở giữa nói rõ việc đang ở phía ai.

Số đếm trên tab Yêu cầu báo giá là số báo giá đang "Chờ anh/chị đồng ý".

### 6.3 Màn chi tiết báo giá

Dùng lại màn chi tiết hiện có (`ChiTietYeuCau.vue`) với nguồn dữ liệu là
Quotation: bảng mặt hàng kèm đơn giá và thành tiền, hạn hiệu lực, dòng thời
gian, tải PDF. Hành động theo trạng thái:

- Chờ khách đồng ý: **Đồng ý**, **Từ chối** (lý do tuỳ chọn), **Sửa số lượng**.
- Khách đã đồng ý: đường dẫn "Xem đơn hàng".
- Các trạng thái khác: chỉ xem.

Chờ Miyano báo giá thì khách **không** thấy đơn giá, kể cả giá gợi ý còn giữ
sau khi sửa số lượng: giá chưa được Miyano xác nhận lại không phải là báo giá.

### 6.4 Endpoint

Endpoint mới trong `api/portal.py`, đi qua đúng chốt hai trục (khách và khoa)
như mọi endpoint cổng:

- `portal_bao_gia_danh_sach(nhom, khoa_phong, limit, start)`
- `portal_bao_gia_chi_tiet(ten)`
- `portal_bao_gia_dong_y(ten)`
- `portal_bao_gia_tu_choi(ten, ly_do)`
- `portal_bao_gia_sua_so_luong(ten, dong)`
- `portal_bao_gia_pdf` (đã có) nhận thêm Quotation.

`portal_yeu_cau_cua_toi` (tab Đơn hàng) loại phiếu chờ báo giá khỏi kết quả
theo luật ở §6.1 — chỉ loại phiếu KHÔNG có `sales_order`.
Thẻ tổng quan trên Dashboard đếm báo giá chờ đồng ý từ Quotation, cộng đơn
`"Mua lẻ"` cũ còn dở.

## 7. Phía ERP

- **Hàng việc:** danh sách Quotation lọc `custom_nguon_don = "Client Portal"`
  và trạng thái "Chờ Miyano báo giá", gắn vào workspace của app.
- **Form Quotation:** khối "Hàng chưa có mã — thông tin khách khai" (ảnh, hãng,
  quy cách) hiện như trên Sales Order; hàm dựng khối dùng chung.
- **Mẫu in:** thêm mẫu "Miyano - Báo giá" cho doctype Quotation. Mẫu trên Sales
  Order giữ lại cho đơn `"Mua lẻ"` cũ.
- **Thông báo:** "Portal - Báo giá sẵn sàng" có thêm bản cho Quotation (sự kiện
  chuyển sang "Chờ khách đồng ý"), đính PDF mẫu mới.
- **Quá hạn xử lý:** `portal_sla.quet_don_treo` quét thêm Quotation ở "Chờ
  Miyano báo giá" quá ngưỡng, cùng ngưỡng với đơn chờ báo giá hiện nay.

## 8. Phân quyền và cách ly

Quotation là doctype mới đối với cổng, nên mọi chốt đang có cho Sales Order
phải có bản tương ứng. Thiếu một chốt là lộ báo giá của bệnh viện này sang
bệnh viện khác.

- **Tài khoản cổng không có DocPerm nào trên Quotation**, kể cả đọc. Hôm nay
  chỉ các vai nội bộ (Sales, Maintenance) có quyền trên doctype này, và bản
  này giữ nguyên. Đây là khác biệt cố ý so với Sales Order (vai Customer có
  quyền đọc): mọi đường đọc chung của Frappe — REST, `frappe.client`, mapper
  whitelist `make_sales_order`, `run_doc_method` — đóng sẵn với khách mà không
  cần thêm chốt nào. Cổng chỉ đọc và ghi Quotation qua sáu endpoint ở §6.4.
- Mỗi endpoint tự kiểm hai trục trước khi làm gì: `quotation_to = "Customer"`
  **và** `party_name` thuộc khách của tài khoản; với nhân viên khoa, thêm đúng
  `custom_khoa_phong`. Các hàm kiểm hiện có giả định cột `customer`; Quotation
  dùng `party_name`, nên phải có bản riêng, không truyền thẳng vào hàm cũ.
- Quotation không có `custom_nguon_don = "Client Portal"` (nhân viên tự lập
  cho khách ngoài cổng) **không** hiện trên cổng, kể cả khi cùng khách.
- `permission_query_conditions` và `has_permission` cho `Quotation` vẫn được
  đăng ký với đúng hai trục trên, làm lớp thứ hai: nếu về sau ai đó cấp quyền
  đọc cho một vai của cổng, họ vẫn chỉ thấy báo giá của mình.
- **Trang báo giá có sẵn của ERPNext phải bị chặn.** ERPNext đăng ký sẵn
  `/quotations` và `/quotations/<tên>` cho vai Customer, kiểm quyền bằng
  `has_website_permission` riêng — đường này KHÔNG đi qua DocPerm, không biết
  trục khoa, và hiện cả đơn giá khi báo giá còn ở "Chờ Miyano báo giá". Tài
  khoản cổng gọi hai đường dẫn đó phải nhận từ chối. Cách chặn cụ thể chốt ở
  bước lập kế hoạch, sau khi đo xem tài khoản cổng hiện có vào được
  `/orders` (cùng cơ chế, cho Sales Order) hay không.

## 9. Chuyển tiếp

- Không chuyển đổi dữ liệu (Q2). Đơn `"Mua lẻ"` đang dở giữ nguyên trạng thái
  và chạy nốt bằng mã luồng cũ.
- Mã luồng cũ (`portal_order_accept` nhánh báo giá, `portal_order_sua_so_luong`,
  phần Sales Order của job hết hạn, chốt `chot_bao_gia.kiem_chuyen_trang_thai`)
  **giữ nguyên** trong đợt này. Gỡ ở một đợt riêng khi không còn đơn `"Mua lẻ"`
  nào ở trạng thái mở.
- Một patch thêm custom field (§3.1), giá trị `"Theo báo giá"` cho
  `custom_loai_don`, workflow mới, mẫu in và thông báo mới. Chạy hai lần cho
  cùng kết quả.

## 10. Mã nguồn

| Tệp | Việc |
|---|---|
| `miyano_portal/bao_gia.py` (mới) | Dựng Quotation từ phiếu; đồng ý / từ chối / sửa số lượng; chốt gửi khách |
| `miyano_portal/portal_mua_le.py` | Tổng quát hoá khớp dòng gõ tay và dòng giữ chỗ cho cả Quotation. Các hook đang gắn trên Sales Order có bản gắn trên Quotation: `chuyen_dong_dat_ngoai_thanh_hang` (`before_validate`), `dong_bo_da_xu_ly_dat_ngoai` (`validate`); ba chốt `before_submit` (`kiem_dat_ngoai_da_xu_ly`, `kiem_dong_chuyen_con_tren_don`, `kiem_khong_con_dong_giu_cho`) chuyển thành chốt gửi khách ở §4.2 |
| `miyano_portal/de_xuat_duyet.py`, `api/portal.py` (`portal_order_place`) | Rẽ nhánh tạo Quotation thay vì Sales Order `"Mua lẻ"` |
| `miyano_portal/api/portal.py` | Sáu endpoint §6.4; tab Đơn hàng loại phiếu chờ báo giá; số đếm Dashboard; tách cơ chế nâng quyền của `portal_order_accept` thành hàm dùng chung |
| `miyano_portal/bang_gia_khach.py` | `ghi_gia_da_dong_y` nhận Quotation |
| `miyano_portal/chot_bao_gia.py` | Chốt giá khớp giá đã đồng ý cho đơn `"Theo báo giá"` |
| `miyano_portal/portal_bao_gia.py`, `portal_sla.py`, `portal_thong_bao.py` | Hết hạn, quá hạn xử lý, thông báo cho Quotation |
| `miyano_portal/permissions.py`, `rest_guard.py`, `search_guard.py`, `hooks.py` | §8 |
| `miyano_portal/setup/install_workflow.py`, `install_print_formats.py`, `install_notifications.py`, patch mới | §9 |
| `miyano_portal/public/js/` | Khối thông tin khách khai trên form Quotation |
| `frontend/src/views/YeuCauList.vue`, `ChiTietYeuCau.vue`, `Dashboard.vue`, `components/chi-tiet/*` | §6 |

## 11. Kiểm thử

Viết test trước cho từng phần.

- **Tạo:** phiếu chờ báo giá sinh Quotation, không sinh Sales Order; phiếu có
  giá vẫn sinh Sales Order; mọi dòng vừa có giá thì đi thẳng đơn; dòng gõ tay
  vào `custom_dat_ngoai`; chỉ có dòng gõ tay thì có dòng giữ chỗ; gửi trùng
  `request_id` không sinh báo giá thứ hai.
- **Chốt gửi khách:** chặn khi còn dòng gõ tay chưa khớp, còn dòng giữ chỗ,
  còn dòng giá 0; qua chốt thì có `valid_till` đúng số ngày cấu hình.
- **Sửa số lượng:** về "Chờ Miyano báo giá", giữ đơn giá, xoá hạn; không thêm,
  xoá hay đặt 0 được; nhân viên được báo.
- **Đồng ý:** Quotation Submit, sinh đúng một đơn `"Theo báo giá"` ở "Chờ
  Miyano xác nhận" với giá, dấu nguồn giá và giá đã đồng ý trên từng dòng;
  phiếu có `sales_order`; giá ghi vào Price List; gọi lại không sinh đơn thứ
  hai; quá hạn thì không đồng ý được; lỗi ghi giá không làm hỏng việc đồng ý;
  lỗi sinh đơn thì báo giá không ở trạng thái đã đồng ý.
- **Từ chối và hết hạn:** không sinh đơn, không ghi giá; job hết hạn chuyển
  đúng báo giá quá hạn và không đụng báo giá còn hạn.
- **Cách ly:** khách A không đọc, không đồng ý, không sửa được báo giá của
  khách B; nhân viên khoa X không thấy báo giá của khoa Y; đọc thẳng qua REST,
  `frappe.client`, `make_sales_order` và `run_doc_method` bị từ chối;
  `/quotations` và `/quotations/<tên>` bị từ chối; Quotation không phải của
  cổng không hiện.
- **Đơn sinh từ báo giá:** không mang `custom_request_id`, ngày gửi duyệt hay
  lý do từ chối của báo giá; mỗi dòng của bảng ở §4.5 có một test.
- **Báo giá ngoài cổng:** nhân viên ghi nhận khách đồng ý được; không ghi nhận
  thay được cho báo giá của cổng.
- **Cổng:** tab Đơn hàng không còn phiếu chờ báo giá; tab Yêu cầu báo giá có
  đủ năm nhóm; khách không thấy đơn giá khi báo giá ở "Chờ Miyano báo giá".
- **Luồng cũ:** một đơn `"Mua lẻ"` đang ở "Chờ khách đồng ý" vẫn đồng ý được
  và vẫn ghi giá sau bản này.
- **Patch:** chạy hai lần cho cùng kết quả.

## 12. Ngoài phạm vi

- Khách chọn lấy hoặc bỏ từng dòng của báo giá.
- Chuyển đơn `"Mua lẻ"` đang dở thành Quotation.
- Gỡ mã luồng báo giá cũ.
- Báo giá Miyano tự lập trên ERP rồi đẩy lên cổng (không bắt nguồn từ một yêu
  cầu của khách).
- Nhiều phiên bản báo giá cho cùng một yêu cầu (amend). Sửa giá xảy ra trên
  chính bản nháp qua "Thu hồi để sửa".
- Dùng trạng thái `Lost` và lý do mất đơn của ERPNext cho báo giá bị từ chối.
