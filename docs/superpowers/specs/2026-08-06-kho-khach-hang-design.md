# Thiết kế: Kho Khách Hàng trên Miyano Portal

Ngày: 2026-08-06
Trạng thái: đã duyệt (chờ viết kế hoạch thực thi)
App: `miyano_portal` — site `erptest.local`

## 1. Bài toán

Khách hàng của Miyano (bệnh viện, phòng xét nghiệm) cần tự quản lý kho vật tư của
chính họ ngay trên cổng khách hàng: nhập kho, xuất kho, xem tồn, in phiếu theo mẫu
kế toán của đơn vị mình. Hàng Miyano giao phải tự chảy vào kho đó. Miyano nhìn được
dữ liệu tiêu hao để sau này lập kế hoạch cấp vật tư.

## 2. Quyết định nền tảng

Các quyết định dưới đây đã được chốt với chủ dự án và là ràng buộc của thiết kế.

| # | Quyết định | Ghi chú |
|---|---|---|
| 1 | Hàng **bán đứt** tại thời điểm Delivery Note | Kho khách là sổ của khách; Miyano chỉ xem |
| 2 | Báo cáo N-X-T có **cả số lượng và thành tiền** | Giá bám vào lô, không cần engine định giá |
| 3 | Sổ kho là **doctype riêng của `miyano_portal`** | KHÔNG dùng Warehouse / Bin / Stock Entry / Stock Ledger Entry của ERPNext |
| 4 | Kho khách **không thuộc Company nào** | Không tạo Company mới, không sinh bút toán kế toán |
| 5 | **Mỗi khách đúng 1 kho**, không phân cấp kho con | Cây kho nhiều tầng trong `doc/Warehouse.xlsx` là của Miyano, không áp dụng ở đây |
| 6 | Theo dõi **số lô + hạn sử dụng** đầy đủ | 26/59 mặt hàng trên hệ thống đã bật theo lô; pilot là Khoa Dược |
| 7 | Mã vật tư khách tự thêm **chỉ nằm trong kho khách** | Không tạo `Item` trong ERPNext → Item master của Miyano sạch |
| 8 | **Không** quản lý nhà cung cấp khác của khách | Nhập ngoài chỉ là một loại phiếu, không có Supplier |
| 9 | Xuất kho **không** cần biết đi đâu | Chỉ ô text tự do; không dựng master khoa/phòng |
| 10 | Mẫu phiếu in **cấu hình theo từng khách** | Ship sẵn mẫu TT 107 và TT 200, gán ở cấp kho |
| 11 | Pilot **1 khách** (BV Bạch Mai), kiến trúc vẫn đa khách | Provision thêm khách chỉ là tạo thêm 1 bản ghi kho |

### Vì sao không dùng Stock Ledger của ERPNext

`enable_perpetual_inventory = 1` trên cả hai company (`Miyano`, `Miyano Việt Nam`).
Nếu kho khách là một `Warehouse` thuộc company của Miyano thì mỗi lần bệnh viện xuất
kho sẽ ghi bút toán giá vốn vào sổ kế toán của Miyano, và Delivery Note giao vào kho
đó chỉ là chuyển kho nội bộ chứ không giảm tồn thật của Miyano. Sổ sách Miyano sẽ sai.

Tạo Company riêng thì tránh được điều đó nhưng mỗi Company đẻ ~100 tài khoản kế toán
và mọi báo cáo tổng hợp phải quét qua N company.

Sổ kho riêng loại bỏ cả hai vấn đề. Chi phí phải trả là mất lưới an toàn sẵn có của
ERPNext (chặn tồn âm, định giá, báo cáo kho) — mục 7 dựng lại tường minh phần cần thiết.

## 3. Mô hình dữ liệu

Sáu doctype mới, tất cả thuộc module `Miyano Portal`.

### 3.1 `Kho Khách Hàng`

Một bản ghi cho mỗi Customer. Autoname `KKH-.#####`.

| Field | Kiểu | Ghi chú |
|---|---|---|
| `customer` | Link Customer | reqd, **unique** |
| `ten_kho` | Data | reqd, ví dụ "Kho Khoa Dược" |
| `ma_kho` | Data | reqd, unique, viết tắt dùng trong số phiếu (ví dụ `BM`) |
| `thu_kho` | Data | tên thủ kho, in lên phiếu |
| `dia_chi_kho` | Small Text | |
| `ten_don_vi_in` | Data | tên đơn vị in trên phiếu, mặc định = `customer_name` |
| `bo_phan_in` | Data | ô "Bộ phận" trên mẫu phiếu |
| `mau_phieu_nhap` | Link Print Format | để trống = dùng mẫu mặc định |
| `mau_phieu_xuat` | Link Print Format | để trống = dùng mẫu mặc định |
| `ngay_bat_dau` | Date | reqd, chặn mọi phiếu có ngày trước mốc này |
| `active` | Check | default 1 |

### 3.2 `Vật Tư Kho Khách`

Danh mục vật tư bên trong kho của một khách. Autoname `VTK-.#####`.

| Field | Kiểu | Ghi chú |
|---|---|---|
| `kho` | Link Kho Khách Hàng | reqd |
| `ma_vat_tu` | Data | reqd, unique trong phạm vi `kho` |
| `ten_vat_tu` | Data | reqd |
| `dvt` | Data | reqd |
| `item_code` | Link Item | **nullable** — chỉ set khi khớp catalog Miyano |
| `quy_cach` | Data | |
| `nhom` | Data | phân nhóm tự do của khách |
| `ghi_chu` | Small Text | |
| `active` | Check | default 1 |

`item_code` là cầu nối duy nhất sang dữ liệu Miyano. Dòng xuất kho của vật tư có
`item_code` chính là dữ liệu tiêu hao mà Miyano dùng cho phase phân tích sau này.
Mã khách tự thêm để trống field này và không bao giờ tạo `Item`.

Ràng buộc unique `(kho, ma_vat_tu)` cài bằng index ở tầng doctype.

### 3.3 `Phiếu Nhập Kho`

Submittable (`is_submittable = 1`). Autoname: `PN-{ma_kho}-{YYYY}-{#####}` sinh bằng
hàm `autoname` tự viết, đếm theo `(kho, năm)`.

| Field | Kiểu | Ghi chú |
|---|---|---|
| `kho` | Link Kho Khách Hàng | reqd |
| `ngay` | Date | reqd, default hôm nay |
| `loai_nhap` | Select | `Tồn đầu kỳ` / `Từ đơn hàng Miyano` / `Nhập khác` / `Phiếu đảo` |
| `delivery_note` | Data | read-only, tên DN nguồn — dùng để chống nhập trùng |
| `sales_order` | Data | read-only, tiện tra cứu |
| `nguoi_giao` | Data | text tự do |
| `chung_tu_kem` | Data | số hoá đơn/chứng từ kèm, text tự do |
| `dien_giai` | Small Text | |
| `phieu_goc` | Link Phiếu Nhập Kho | chỉ có khi `loai_nhap = Phiếu đảo` |
| `tong_tien` | Currency | read-only, tính từ dòng |
| `items` | Table `Phiếu Nhập Kho Item` | reqd, ít nhất 1 dòng |

`Phiếu Nhập Kho Item`: `vat_tu` (Link, reqd) · `ten_vat_tu` `dvt` (fetch, read-only) ·
`so_lo` (Data, reqd) · `han_su_dung` (Date) · `so_luong` (Float, reqd) ·
`don_gia` (Currency, reqd) · `thanh_tien` (Currency, read-only) · `ghi_chu` (Data).

### 3.4 `Phiếu Xuất Kho`

Submittable. Autoname `PX-{ma_kho}-{YYYY}-{#####}`.

| Field | Kiểu | Ghi chú |
|---|---|---|
| `kho` | Link Kho Khách Hàng | reqd |
| `ngay` | Date | reqd |
| `loai_xuat` | Select | `Xuất sử dụng` / `Xuất huỷ - hết hạn` / `Xuất trả lại` / `Điều chỉnh kiểm kê` / `Phiếu đảo` |
| `noi_nhan` | Data | **text tự do** — không có master khoa/phòng |
| `nguoi_nhan` | Data | text tự do |
| `dien_giai` | Small Text | lý do xuất |
| `phieu_goc` | Link Phiếu Xuất Kho | chỉ có khi là phiếu đảo |
| `tong_tien` | Currency | read-only |
| `items` | Table `Phiếu Xuất Kho Item` | reqd |

`Phiếu Xuất Kho Item`: `vat_tu` (Link, reqd) · `ten_vat_tu` `dvt` (fetch, ro) ·
`so_lo` (Data, reqd) · `han_su_dung` (Date, read-only, lấy từ lô) ·
`so_luong` (Float, reqd) · `don_gia` (Currency, read-only, lấy từ lô) ·
`thanh_tien` (Currency, ro) · `xac_nhan_het_han` (Check) · `ghi_chu` (Data).

### 3.5 `Sổ Kho Khách` — sổ ghi tăng dần

Nguồn sự thật duy nhất. Không submittable, **chỉ insert, không sửa, không xoá**.
Autoname `SKK-.#########`.

| Field | Kiểu | Ghi chú |
|---|---|---|
| `kho` | Link Kho Khách Hàng | reqd |
| `ngay` | Date | ngày hạch toán, lấy từ phiếu |
| `vat_tu` | Link Vật Tư Kho Khách | reqd |
| `so_lo` | Data | reqd |
| `han_su_dung` | Date | |
| `so_luong` | Float | **dương = nhập, âm = xuất** |
| `don_gia` | Currency | |
| `gia_tri` | Currency | `so_luong * don_gia`, âm khi xuất |
| `chung_tu_type` | Select | `Phiếu Nhập Kho` / `Phiếu Xuất Kho` |
| `chung_tu` | Data | tên phiếu |
| `chung_tu_row` | Data | `name` của dòng con — khoá chống ghi trùng |
| `da_dao` | Check | **field duy nhất được phép sửa sau khi insert** |

Thứ tự sổ theo `creation`. Huỷ phiếu không xoá dòng nào: hệ thống sinh phiếu đảo với
số lượng ngược dấu, và bật `da_dao` trên các dòng gốc để truy vấn nhanh.

### 3.6 `Tồn Theo Lô` — cache dẫn xuất

Tương đương `Bin` của ERPNext. Autoname theo tổ hợp `(kho, vat_tu, so_lo)`.

| Field | Kiểu |
|---|---|
| `kho` | Link Kho Khách Hàng |
| `vat_tu` | Link Vật Tư Kho Khách |
| `so_lo` | Data |
| `han_su_dung` | Date |
| `so_luong` | Float |
| `don_gia` | Currency |
| `gia_tri` | Currency |

Toàn bộ bảng này tái dựng được từ `Sổ Kho Khách`. Cung cấp lệnh sửa chữa:

```
bench --site erptest.local execute miyano_portal.kho.ledger.rebuild_lot_balance
```

**Đơn giá của lô** khi cùng một lô được nhập nhiều lần với giá khác nhau: bình quân
gia quyền theo số lượng. Phiếu xuất luôn lấy đơn giá hiện hành của lô, nên với phiếu
xuất phép tính lại bình quân cho ra chính con số cũ — không đổi gì.

**Ghi giảm cũng tính lại bình quân.** Điều này chỉ có tác dụng thật khi dòng ghi giảm
mang đơn giá KHÁC bình quân hiện hành, mà trường hợp duy nhất như vậy là phiếu đảo của
một phiếu nhập: nó hoàn lại đúng đơn giá lúc nhập. Ví dụ lô đang có 200 đơn vị bình
quân 60.000 (12.000.000), huỷ phiếu nhập 100 @ 50.000 thì 100 đơn vị còn lại mang đơn
giá `(12.000.000 − 5.000.000) / 100 = 70.000`. Đúng thực tế: hàng còn lại chính là lô
đã nhập giá 70.000. Nếu không tính lại, cache đứng ở 60.000 trong khi sổ đã trừ
5.000.000 — hai bên lệch 1.000.000 vĩnh viễn, và `rebuild_lot_balance` không cứu được
vì nó chạy lại đúng phép tính đó.

**Bất biến bắt buộc phải có test:** với mọi lô, tổng `gia_tri` của các dòng
`Sổ Kho Khách` luôn bằng `gia_tri` của `Tồn Theo Lô`, kể cả sau khi huỷ phiếu và sau
khi rebuild.

## 4. Luồng nghiệp vụ

### 4.1 Mở kho

Nhân viên Miyano tạo `Kho Khách Hàng` cho một Customer, đặt `ma_kho`, `ngay_bat_dau`
và mẫu phiếu in. Khách không tự mở kho. Quyền tạo thuộc về `System Manager` và
`Sales Manager`; `Sales User` chỉ được đọc — cố ý hẹp hơn, vì mở kho là việc hiếm và
hệ quả lớn hơn việc cấp một tài khoản portal.

**Role `Customer` không có quyền doctype nào trên các doctype kho.** Portal chạm tới
dữ liệu kho duy nhất qua API `miyano_portal.api.kho.*`, vốn tự suy kho từ phiên đăng
nhập. Lý do ở §6.

### 4.2 Import danh mục + tồn đầu kỳ

1. Khách tải file mẫu `.xlsx` từ portal. Cột: `Mã vật tư` · `Tên vật tư` · `ĐVT` ·
   `Số lô` · `Hạn sử dụng` · `Số lượng` · `Đơn giá` · `Quy cách` · `Nhóm`.
2. Upload → backend đọc và trả về **preview**, không ghi gì:
   - số dòng khớp mã Miyano (sẽ set `item_code`)
   - số dòng là mã riêng sẽ tạo mới
   - số dòng khớp vật tư đã có trong kho
   - danh sách dòng lỗi kèm số dòng và lý do bằng tiếng Việt
3. Khách bấm xác nhận → ghi **hoặc tất cả hoặc không** trong một transaction:
   tạo các `Vật Tư Kho Khách` còn thiếu, rồi tạo **một** `Phiếu Nhập Kho`
   `loai_nhap = Tồn đầu kỳ` và submit.
4. File mẫu tải xuống và file import dùng **cùng bộ cột theo đúng thứ tự**, để file
   xuất ra nạp lại được.

Skill áp dụng: `previewing-imports-before-writing`, `round-tripping-spreadsheets`.

Khớp mã Miyano: so `Mã vật tư` với `Item.item_code`, không phân biệt hoa thường, đã
trim khoảng trắng. Không khớp thì coi là mã riêng, `item_code` để trống.

### 4.3 Nhập từ đơn hàng Miyano

`Delivery Note.on_submit` → sinh `Phiếu Nhập Kho` ở trạng thái **nháp**
(`loai_nhap = Từ đơn hàng Miyano`, `delivery_note` = tên DN).

Nháp chứ không submit thẳng: thủ kho phải đối chiếu hàng thực nhận rồi mới xác nhận.
Giao thiếu hoặc vỡ mà tự cộng tồn thì sổ sai ngay từ ngày đầu. Thủ kho được sửa số
lượng trên phiếu nháp trước khi submit.

- **Chống trùng:** trước khi tạo, kiểm tra đã có phiếu nào (docstatus < 2) mang
  `delivery_note` đó chưa. Có rồi thì bỏ qua.
- **Khách chưa mở kho:** bỏ qua im lặng, ghi log. Delivery Note không được phép fail
  vì lý do này.
- **Dòng DN có `item_code` chưa có trong kho khách:** tự tạo `Vật Tư Kho Khách` tương
  ứng, `item_code` trỏ về Item thật.
- **Lô/HSD:** build này bật **cả hai** cơ chế lô của ERPNext v15
  (`Stock Settings.use_serial_batch_fields = 1` *và* doctype `Serial and Batch Bundle`
  đều tồn tại), nên hook phải đọc theo thứ tự: `Delivery Note Item.serial_and_batch_bundle`
  trước (một dòng DN có thể tách thành nhiều lô → sinh nhiều dòng phiếu nhập), rồi mới
  đến `Delivery Note Item.batch_no`. Hạn dùng lấy từ `Batch.expiry_date`. Dòng không có
  lô ở cả hai chỗ thì `so_lo = "KHONG-LO"`, `han_su_dung` để trống — trường hợp này có
  thật, các Delivery Note đang có trên `erptest.local` đều không gắn lô.
- **Đơn giá:** `rate` trên dòng Delivery Note.
- **`Delivery Note.on_cancel`:** nếu phiếu nhập tương ứng còn nháp thì huỷ phiếu; nếu
  đã submit thì sinh phiếu đảo.

Toàn bộ hook chạy trong `try/except`, lỗi được log chứ không chặn nghiệp vụ bán hàng
của Miyano.

**`api/portal.py` không đổi.** `_resolve_item_warehouse` vẫn giao hàng từ kho của
Miyano như hiện tại; kho khách là sổ độc lập, không phải đích đến của Delivery Note.

### 4.4 Xuất kho

Chọn vật tư → hệ thống gợi ý lô theo **FEFO** (hạn dùng gần nhất trước, lô không có
hạn xếp cuối) → nhập số lượng → điền `nơi nhận`, `người nhận` → submit.

- Chặn cứng xuất quá tồn của lô: `Lô {so_lo} của {ten_vat_tu} chỉ còn {n} {dvt}.`
- Lô đã quá hạn: cảnh báo và bắt tick `xac_nhan_het_han`, **không chặn** — thực tế có
  nghiệp vụ xuất huỷ hàng hết hạn.
- Nhiều dòng cùng một `(vật tư, lô)` trong một phiếu được cộng dồn trước khi kiểm tra
  tồn, tránh lách bằng cách tách dòng.

Skill áp dụng: `picking-and-tracing-batches`.

### 4.5 Huỷ phiếu

Không xoá dòng sổ. `on_cancel` của phiếu sinh một phiếu đảo cùng loại
(`loai_* = Phiếu đảo`, `phieu_goc` trỏ về phiếu gốc) với số lượng ngược dấu, rồi bật
`da_dao` trên các dòng sổ gốc. Phiếu đã submit không sửa được, chỉ huỷ.

Huỷ phiếu nhập bị **chặn** nếu hàng của lô đó đã bị xuất mất rồi và đảo lại sẽ làm tồn
âm. Thông báo chỉ rõ lô nào và phiếu xuất nào đang giữ hàng.

Skill áp dụng: `reversing-ledger-entries`.

### 4.6 Báo cáo

- **Nhập – Xuất – Tồn** theo khoảng ngày: mỗi vật tư một dòng, 8 cột
  (tồn đầu SL+TT, nhập SL+TT, xuất SL+TT, tồn cuối SL+TT). Bung được xuống mức lô.
  Tồn đầu = tổng `Sổ Kho Khách` trước `tu_ngay`.
- **Thẻ kho** theo vật tư: liệt kê từng chứng từ theo thời gian, cột tồn luỹ kế.
- **Cảnh báo hạn dùng:** lô hết hạn trong N ngày tới (N cấu hình được, mặc định 90) và
  lô đã hết hạn còn tồn.
- Cả ba xuất được Excel với cùng bộ cột đang hiển thị.

## 5. API

Module mới `miyano_portal/api/kho.py`. Mọi endpoint đều whitelist và **tự resolve kho
từ `get_portal_customer()`** — không endpoint nào nhận `customer` hay `kho` từ client.

| Endpoint | Vai trò |
|---|---|
| `kho_me` | thông tin kho của khách đang đăng nhập |
| `kho_ton` | tồn hiện tại theo vật tư, bung được xuống lô |
| `kho_vat_tu_list` / `kho_vat_tu_upsert` | danh mục vật tư trong kho |
| `kho_import_template` | tải file mẫu `.xlsx` |
| `kho_import_preview` | nhận `file_url`, đọc file, trả kết quả phân tích, **không ghi** |
| `kho_import_commit` | nhận lại chính `file_url` đó, đọc lại và kiểm tra lại từ đầu ở phía server rồi mới ghi, tất-cả-hoặc-không |
| `kho_phieu_list` / `kho_phieu_get` | danh sách và chi tiết phiếu (nhập và xuất) |
| `kho_phieu_nhap_save` / `kho_phieu_nhap_submit` | tạo/sửa nháp, xác nhận |
| `kho_phieu_xuat_save` / `kho_phieu_xuat_submit` | tạo/sửa nháp, xác nhận |
| `kho_phieu_cancel` | huỷ phiếu (sinh phiếu đảo) |
| `kho_lo_goi_y` | gợi ý lô theo FEFO cho một vật tư |
| `kho_bao_cao_nxt` | báo cáo Nhập-Xuất-Tồn |
| `kho_the_kho` | thẻ kho một vật tư |
| `kho_canh_bao_han` | lô sắp và đã hết hạn |
| `kho_bao_cao_excel` | xuất Excel báo cáo đang xem |
| `kho_phieu_pdf` | in phiếu theo mẫu của khách |

## 6. Cách ly dữ liệu

Đây là mặt phẳng dễ thủng nhất của tính năng này.

- Bổ sung `permission_query_conditions` và `has_permission` trong `hooks.py` cho cả
  sáu doctype mới, dùng lại `miyano_portal/permissions.py`.
- `Kho Khách Hàng` lọc theo `customer in get_allowed_customers()`. Năm doctype còn lại
  lọc theo `kho in (kho của các customer được phép)`.
- Thêm helper `get_portal_kho(user)` trong `portal_context.py`, ném `PermissionError`
  nếu khách chưa được mở kho.
- **Bài học đã ghi trong code này:** `frappe.get_doc` **không** tự chạy `has_permission`
  ở build này. Mọi chỗ lấy doc theo tên do client gửi phải gọi `check_permission()`
  tường minh — xem `api/portal.py:351` và `api/portal.py:490`.

**Bổ sung sau khi thực thi — hai điều chỉ lộ ra khi đi tấn công thật:**

1. **Bảng con của chứng từ cũng phải cách ly.** `Phiếu Nhập Kho Item` và
   `Phiếu Xuất Kho Item` là doctype `istable`, không có field `kho` của riêng chúng.
   Nếu bỏ sót, `frappe.client.get_list` trả về toàn bộ dòng phiếu kèm đơn giá của mọi
   khách — kể cả cho tài khoản không gắn khách hàng nào. Điều kiện lọc của chúng phải
   suy kho qua chứng từ cha bằng truy vấn con.

2. **Hook `has_permission` KHÔNG BAO GIỜ chạy với doctype `istable`.**
   `frappe/permissions.py` rẽ sang `has_child_permission()` trước, và phép suy
   `parent_doc` ở đó trả `None` cho mọi dòng con nạp rời. Override method trên
   controller cũng chỉ chặn được `doc.check_permission()`, không chặn được hàm cấp
   module `frappe.has_permission(doctype, ptype, doc)` mà `/printview` và
   `download_pdf` đang dùng.

   Vì vậy chốt chặn thật là **gỡ hẳn quyền doctype của role `Customer`** trên các
   doctype kho: cổng của bảng con quy về kiểm quyền mức doctype của chứng từ cha, nên
   không cấp quyền là đóng mọi đường. Hook và override vẫn giữ làm lớp thứ hai.

   **Hệ quả cần nhớ:** cấp lại `DocPerm` cho role `Customer` (kể cả role `All`) trên
   bất kỳ doctype kho nào là mở lại lỗ ngay lập tức. `TestKhoDocPermConfig` và
   `test_portal_user_has_no_doctype_level_read` canh việc này.
- Nhân viên Miyano (không phải `Website User`) thấy toàn bộ, đúng cơ chế
  `_is_restricted_user` sẵn có.

Skill áp dụng: `isolating-portal-tenant-data`.

## 7. Ràng buộc phải tự dựng lại

Sổ kho tự viết nên không có lưới an toàn của ERPNext. Những thứ sau phải cài tường minh:

| Ràng buộc | Xử lý |
|---|---|
| Xuất quá tồn | Chặn cứng, thông báo nêu rõ lô và số còn lại |
| Số lượng ≤ 0, đơn giá < 0 | Chặn ở `validate` |
| Ngày phiếu trước `ngay_bat_dau` của kho | Chặn |
| Sửa/xoá phiếu đã submit | Chặn, chỉ cho huỷ |
| Ghi trùng dòng sổ | Khoá theo `chung_tu_row` |
| Trùng `(kho, ma_vat_tu)` | Unique index |
| Trùng phiếu nhập từ một DN | Kiểm tra `delivery_note` trước khi tạo |
| Tồn theo lô lệch sổ | Lệnh `rebuild_ton_theo_lo` + test bất biến |

Mọi thông báo lỗi ra tiếng Việt, không để lộ tên doctype tiếng Anh hay traceback.
Skill áp dụng: `translating-backend-errors`.

## 8. Giao diện portal

Thêm nhóm "Kho của tôi" vào sidebar SPA Vue hiện có (`frontend/src/`).

| Route | View | Nội dung |
|---|---|---|
| `/portal/kho` | `Kho.vue` | tồn hiện tại, tìm kiếm, badge cảnh báo hết hạn |
| `/portal/kho/nhap` | `PhieuNhap.vue` | danh sách phiếu nhập, tạo phiếu |
| `/portal/kho/nhap/:name` | `PhieuNhapDetail.vue` | chi tiết, sửa nháp, submit, in |
| `/portal/kho/xuat` | `PhieuXuat.vue` | danh sách phiếu xuất, tạo phiếu |
| `/portal/kho/xuat/:name` | `PhieuXuatDetail.vue` | chi tiết, chọn lô FEFO, submit, in |
| `/portal/kho/import` | `ImportTonDau.vue` | tải mẫu, upload, preview, xác nhận |
| `/portal/kho/bao-cao` | `BaoCaoNXT.vue` | N-X-T, thẻ kho, cảnh báo hạn, xuất Excel |

Bám theo các quy ước sẵn có: gọi API bằng `fetch` + CSRF (`frontend/src/api.js`) chứ
không dùng `frappe.call` — hàm đó không tồn tại trên web page. Tiền hiển thị theo
định dạng VND không thập phân của `frontend/src/format.js`.

Skill áp dụng: `formatting-money-fields`, `showing-names-not-codes`.

## 9. Mẫu phiếu in

Ship sẵn bốn Print Format, cài qua `setup/install_kho_print_formats.py` và một patch:

- `Miyano - Phiếu nhập kho (TT107)` — mẫu hành chính sự nghiệp, cho bệnh viện công
- `Miyano - Phiếu xuất kho (TT107)`
- `Miyano - Phiếu nhập kho (TT200)` — mẫu doanh nghiệp
- `Miyano - Phiếu xuất kho (TT200)`

Kho nào để trống `mau_phieu_nhap` / `mau_phieu_xuat` thì dùng mẫu TT107 mặc định.

**Việc còn thiếu, không chặn tiến độ:** chưa có file mẫu Phiếu nhập / Phiếu xuất mà
BV Bạch Mai đang dùng thật. Bốn mẫu trên dựng theo bố cục chuẩn để chạy được ngay;
khi có file thật sẽ chỉnh mẫu của riêng kho Bạch Mai cho khớp 1-1. Kiến trúc đã cho
phép làm việc đó mà không đụng vào các khách khác.

## 10. Kiểm thử

Làm theo TDD: test trước, code sau.

**Sổ kho** (`tests/test_kho_so.py`)
- nhập rồi xuất, tồn theo lô luôn bằng tổng sổ
- `rebuild_ton_theo_lo` cho ra đúng kết quả đang có
- huỷ phiếu sinh dòng đảo đúng dấu, không xoá dòng nào
- nhập cùng một lô hai lần giá khác nhau → đơn giá bình quân đúng
- không dòng sổ nào bị ghi trùng khi submit lại

**Ràng buộc** (`tests/test_kho_rang_buoc.py`)
- xuất quá tồn bị chặn, thông báo nêu đúng lô và số còn
- tách hai dòng cùng lô để lách hạn mức vẫn bị chặn
- xuất lô hết hạn không tick xác nhận thì bị chặn
- ngày phiếu trước `ngay_bat_dau` bị chặn
- huỷ phiếu nhập khi hàng đã xuất mất thì bị chặn

**Cách ly** (`tests/test_kho_isolation.py`)
- khách A không đọc được kho, vật tư, phiếu, sổ, tồn của khách B
- gọi thẳng từng endpoint với `name` của khách B đều bị `PermissionError`
- khách chưa được mở kho gọi API thì nhận lỗi tiếng Việt rõ ràng

**Import** (`tests/test_kho_import.py`)
- preview không ghi gì vào database
- một dòng lỗi thì không dòng nào được ghi
- khớp mã Miyano set `item_code`, mã riêng để trống
- file xuất ra nạp lại được

**Nhập từ Delivery Note** (`tests/test_kho_delivery.py`)
- DN submit sinh đúng một phiếu nháp
- submit lại/chạy lại hook không sinh phiếu thứ hai
- lô và hạn dùng lấy đúng từ batch của DN
- khách chưa mở kho thì DN vẫn submit thành công
- DN huỷ khi phiếu còn nháp → huỷ phiếu; khi đã submit → sinh phiếu đảo

**E2E** (`tests/test_kho_e2e.py`)
- mở kho → import tồn đầu → đặt hàng qua portal → DN submit → xác nhận phiếu nhập →
  xuất kho → báo cáo N-X-T khớp từng con số

## 11. Giai đoạn triển khai

| P | Nội dung | Xong khi |
|---|---|---|
| 1 | Sáu doctype, sổ kho, tồn theo lô, mở kho, cách ly | test sổ kho + test cách ly xanh |
| 2 | Import danh mục + tồn đầu kỳ có preview | test import xanh, thử được trên trình duyệt |
| 3 | Phiếu nhập/xuất, FEFO, chặn âm, huỷ đảo, in phiếu | test ràng buộc xanh, in ra PDF đúng mẫu |
| 4 | Tự sinh phiếu nhập từ Delivery Note | test delivery xanh |
| 5 | Báo cáo N-X-T, thẻ kho, cảnh báo hạn, xuất Excel | test E2E xanh |
| 6 | Màn hình Miyano xem kho khách trên desk | xem được kho của mọi khách |

Phân tích tiêu hao và lập kế hoạch cấp vật tư **không** nằm trong spec này. Đó là bài
toán dự báo riêng và cần vài tháng dữ liệu xuất kho thực tế trước khi làm.

## 12. Rủi ro

| Rủi ro | Giảm thiểu |
|---|---|
| Rò rỉ dữ liệu giữa các khách | Test cách ly cho từng endpoint, không chỉ ở list view |
| Tồn theo lô lệch sổ do lỗi lập trình | Sổ là nguồn sự thật, có lệnh rebuild + test bất biến |
| Hook Delivery Note làm hỏng nghiệp vụ bán hàng | Bọc `try/except`, log lỗi, không bao giờ chặn DN |
| Mẫu phiếu in sai so với phiếu thật của bệnh viện | Mẫu cấu hình theo từng kho, sửa được mà không ảnh hưởng khách khác |
| Khách import file rác | Preview bắt buộc trước khi ghi, tất-cả-hoặc-không |
