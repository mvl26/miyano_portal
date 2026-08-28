# Quản lý vật tư theo thiết bị và khoa phòng trên cổng khách

**Ngày:** 27/08/2026
**App:** `miyano_portal` (cổng khách hàng)
**Nguồn:** yêu cầu của chủ đầu tư, nêu trực tiếp trong phiên làm việc 27/08/2026.
**Trạng thái:** ĐỀ XUẤT ĐÃ CHỐT QUA ĐỐI THOẠI — chưa viết code, chưa tạo doctype,
chưa đụng schema. Cần chủ đầu tư đọc lại file này trước khi lập kế hoạch thi công.

Đánh số quyết định dùng tiền tố **QĐ-TB-**. Bộ tài liệu dự án đã có ba dãy "QĐ"
của ba văn bản khác nhau, cộng dãy `QĐ-KP-` của spec khoa phòng ngày 18/08 —
dùng tiền tố riêng để không thêm một chỗ hiểu sai nữa.

> **Đây là yêu cầu MỚI, không có trong bộ BA.** Grep toàn bộ 4 tài liệu BA đang
> chi phối chỉ ra đúng một chỗ chứa chữ "Thiết bị"
> (`BA-miyano_portal_v2.md:987`) và chỗ đó nói về **responsive trên điện thoại**,
> không phải máy móc y tế. Tài liệu này **không gán số hiệu US/UC nào** cho yêu
> cầu này; nếu chủ đầu tư muốn nó có số trong bộ BA thì cấp số riêng, đừng mượn
> số cũ.

---

## 1. Vấn đề

Chủ đầu tư muốn báo cáo trên cổng khách trả lời được:

> *"Vật tư này đã nhập về bao nhiêu, để dùng cho **máy nào**, và **khoa phòng
> nào**?"*

Hôm nay cổng đã trả lời được **một nửa**: chiều **khoa phòng** đã có đủ
(doctype `Customer Department`, ô `khoa_phong` trên đầu `Customer Stock Issue`,
cờ bắt buộc kèm mốc thời gian, và ba báo cáo cấp phát). Chiều **thiết bị** thì
**chưa tồn tại một dòng dữ liệu nào** — không có master máy, không có ô chọn máy
trên phiếu, không có báo cáo theo máy.

Bài toán của tài liệu này là bổ sung **đúng chiều còn thiếu**, và ghép nó vào
chiều khoa phòng đã có mà không phá số liệu cũ.

## 2. Hiện trạng đã đo trên `erptest.local`

Đo ngày 27/08/2026 bằng truy vấn thật, không suy từ ký ức:

| Việc | Số đo |
|---|---|
| `Customer` | 21 |
| `Customer Warehouse` | 5 — mỗi khách hàng **đúng một kho** (ràng buộc `_one_per_customer`, unique ở tầng CSDL) |
| `Customer Department` | 2, trong đó 2 bản ghi có gắn `kho` |
| `Portal Member` | 7, trong đó **1** là `Nhân viên khoa` |
| `Customer Warehouse Item` | 22 |
| `Customer Stock Issue` | 4 (3 phiếu `Xuất sử dụng`), **1** phiếu có `khoa_phong` |
| `Customer Stock Issue Item` | 5 dòng |
| Kho đang bật `bat_buoc_khoa_phong` | **0** |
| Dấu vết tên máy gõ tay trong dữ liệu cũ | **KHÔNG CÓ.** `Customer Warehouse Item.nhom` chứa nhóm hàng (`Hoá chất xét nghiệm`, `Dịch truyền`, `Vật tư sát khuẩn`...), `Customer Stock Issue.noi_nhan` chứa tên khoa (`Khoa Xét nghiệm`, `Khoa hóa sinh`) và rác (`a`) |
| `Customer Stock Ledger Entry.chung_tu_row` | Là **docname của dòng con** thật (`kho/ledger.py:181, 308`), không phải số thứ tự → join sổ ↔ dòng phiếu được |

**Hai hệ quả quan trọng rút ra từ bảng trên:**

1. **Không có gì để backfill.** Không nơi nào trong dữ liệu hiện có đang chứa tên
   máy. Mọi phiếu xuất cũ sẽ vào nhóm *"Chưa gắn máy"* và phải ở đó — không đoán,
   không suy diễn từ `nhom` hay `noi_nhan`.
2. **Khối lượng dữ liệu còn rất nhỏ** (4 phiếu, 5 dòng, 22 vật tư). Đây là thời
   điểm rẻ nhất để thêm một chiều dữ liệu; làm sau khi đã có vài nghìn phiếu thì
   nhóm "Chưa gắn máy" sẽ nuốt phần lớn báo cáo trong nhiều tháng.

## 3. Quyết định đã chốt

| # | Câu hỏi | Đã chốt |
|---|---|---|
| **QĐ-TB-1** | Gắn "máy" ở đâu trong mô hình? | Có **master thiết bị riêng**, và vật tư khai được **danh sách máy dùng được** |
| **QĐ-TB-2** | Một vật tư dùng cho mấy máy? | **Nhiều máy** — quan hệ n–n, để ở **bảng con trên vật tư** |
| **QĐ-TB-3** | Phiếu **nhập** có phải chọn máy không? | **KHÔNG.** "Nhập thì cứ nhập" — cột *đã nhập* là tổng theo vật tư, không tách theo máy |
| **QĐ-TB-4** | Số lượng theo máy lấy ở đâu? | Ở **phiếu xuất** — "xuất ra phải biết máy nào dùng" |
| **QĐ-TB-5** | Ô chọn máy đặt ở đầu phiếu hay từng dòng? | **Từng dòng vật tư**, cộng một ô *máy mặc định* ở đầu phiếu chỉ để điền nhanh |
| **QĐ-TB-6** | Cách chọn máy trên giao diện | **Dropdown**, lọc sẵn |
| **QĐ-TB-7** | Master máy treo vào đâu? | Vào **`Customer`** (bệnh viện), **không** vào kho — bám theo `Customer Department` đã chuyển chủ sở hữu sang bệnh viện từ 18/08 |
| **QĐ-TB-8** | Có ô `kho` trên master máy không? | **KHÔNG** — chủ đầu tư bỏ. Máy đặt ở khoa, không đặt ở kho; và mỗi khách hàng vốn chỉ có một kho |
| **QĐ-TB-9** | Master máy có những thông tin gì? | Xuất xứ, hãng, số serial, model, năm SX, ngày lắp đặt, khoa phòng |
| **QĐ-TB-10** | Ai được khai máy? | **Cả nhân viên khoa** — nhưng chỉ máy **của khoa mình**. Quản lý khai/sửa mọi máy |
| **QĐ-TB-11** | Chọn máy ngoài danh mục của vật tư thì sao? | **Không chặn cứng.** Cảnh báo kèm nút *"Gắn máy này vào vật tư"*, một bấm là xong |
| **QĐ-TB-12** | Có nút tạo nhanh máy ngay trong form không? | **Có** — cả trong dropdown máy ở phiếu xuất lẫn trong ô "Máy sử dụng" của modal vật tư |
| **QĐ-TB-13** | Khoa phòng trong báo cáo lấy từ đâu? | Từ **phiếu**, **không** suy từ khoa của master máy |
| **QĐ-TB-14** | Có sửa schema sổ kho không? | **KHÔNG** — BR-CP4 cấm. Báo cáo join qua `chung_tu_row` |

### 3.1 Ba quyết định cần giải thích, vì chúng chống lại trực giác

**QĐ-TB-3 + QĐ-TB-4 — vì sao "nhập" không tách theo máy.**
Vật tư dùng chung nhiều máy (QĐ-TB-2) làm cho câu "nhập 100 hộp cho máy nào"
không có câu trả lời đúng ở thời điểm nhập:

- gán 100 cho cả máy A và máy B → cột theo máy cộng thành 200 trên tổng nhập
  100, **báo cáo tự mâu thuẫn**;
- chia 50/50 → **con số bịa**, không ai ký được;
- bắt thủ kho tách dòng lúc nhận hàng → họ **chưa biết** sẽ chạy máy nào.

Chốt: nhập giữ nguyên tổng theo vật tư; số theo máy lấy ở lúc xuất, là số **có
thật do người dùng khai**. Tổng các máy luôn bằng tổng xuất — báo cáo không bao
giờ tự mâu thuẫn, và **không có một con số ước lượng nào** trong hệ thống.

**QĐ-TB-13 — vì sao khoa lấy từ phiếu chứ không từ máy.**
Nếu báo cáo suy khoa theo `Customer Equipment.khoa_phong` tại thời điểm chạy,
thì ngày máy XN-500 chuyển từ Khoa Hóa sinh sang Khoa Xét nghiệm, **toàn bộ số
liệu các năm trước tự viết lại** — bản in tháng trước và bản in lại hôm nay ra
hai con số khác nhau, không ai đối chiếu được. Khoa trên phiếu là ảnh chụp tại
thời điểm cấp phát và phải giữ nguyên như vậy. Khoa của máy chỉ dùng để **gợi
ý** lúc lập phiếu và để **lọc dropdown**.

**QĐ-TB-2 + bảng con không dùng để cộng.**
Bảng "Máy sử dụng" trên vật tư là **danh mục tương thích**, không phải số liệu.
Nó phục vụ ba việc: lọc dropdown lúc xuất, tra ngược *"máy A cần những vật tư
gì"*, và làm cơ sở cho cảnh báo QĐ-TB-11. **Không có báo cáo nào được cộng số
lượng qua bảng này** — làm thế là cộng trùng đúng theo kịch bản đã mô tả ở trên.

---

## 4. Mô hình dữ liệu

### 4.1 Doctype mới: `Customer Equipment` (Thiết bị)

Đặt tên: `TBK-.#####`. Submittable: **không**. Module: `Miyano Portal`.

| Fieldname | Kiểu | Nhãn | Ghi chú |
|---|---|---|---|
| `customer` | Link → Customer | Khách hàng | **Bắt buộc.** Chốt phân quyền |
| `ma_thiet_bi` | Data | Mã máy | **Bắt buộc** — nhập phiếu hàng loạt bằng Excel khớp máy theo mã này (§7.5), để trống là không nhập Excel được. Không trùng trong cùng bệnh viện. Tự viết hoa, bỏ khoảng trắng thừa |
| `ten_thiet_bi` | Data | Tên máy | **Bắt buộc.** Không trùng trong cùng bệnh viện. So sánh dựa thẳng vào collation `utf8mb4_unicode_ci` của CSDL (spec 18/08 đã đo: đã sẵn không dấu, không phân biệt hoa thường) — **không** thêm cột chuẩn hoá |
| `khoa_phong` | Link → Customer Department | Khoa phòng đặt máy | Để trống = **máy dùng chung** |
| `hang_san_xuat` | Data | Hãng sản xuất | vd `Sysmex` |
| `xuat_xu` | Data | Xuất xứ | vd `Nhật Bản` |
| `model` | Data | Model | vd `XN-550` |
| `so_serial` | Data | Số serial | |
| `nam_san_xuat` | Int | Năm sản xuất | |
| `ngay_lap_dat` | Date | Ngày lắp đặt | |
| `active` | Check | Đang hoạt động | Mặc định 1. Máy thanh lý thì **bỏ tích, không xoá** |
| `ghi_chu` | Small Text | Ghi chú | |

Trường hiển thị trên dropdown: `ten_thiet_bi` kèm `ma_thiet_bi` và tên khoa —
người dùng nhận ra máy bằng tên, không bằng `TBK-00007`.

**Không có ô `kho`** (QĐ-TB-8).

### 4.2 Bảng con mới: `Customer Warehouse Item Equipment`

`istable = 1`, một cột duy nhất:

| Fieldname | Kiểu | Nhãn |
|---|---|---|
| `thiet_bi` | Link → Customer Equipment | Máy |

Gắn vào `Customer Warehouse Item` qua field `may_su_dung` (Table), trong một
Section mới *"Máy sử dụng"*.

Bảng trống = vật tư dùng chung, không thuộc máy nào (găng tay, nước cất).

### 4.3 Sửa `Customer Stock Issue Item`

Thêm **một** field:

| Fieldname | Kiểu | Nhãn |
|---|---|---|
| `thiet_bi` | Link → Customer Equipment | Máy sử dụng |

### 4.4 Sửa `Customer Stock Issue` (đầu phiếu)

Thêm **một** field, đặt cạnh `khoa_phong`:

| Fieldname | Kiểu | Nhãn | Ghi chú |
|---|---|---|---|
| `thiet_bi_mac_dinh` | Link → Customer Equipment | Máy mặc định | **Không ghi sổ.** Chỉ để điền nhanh xuống các dòng đang trống |

`thiet_bi_mac_dinh` là **tiện ích nhập liệu**, tuyệt đối không được đọc trong
bất kỳ báo cáo nào — báo cáo chỉ đọc `thiet_bi` trên **dòng**. (Nếu đọc cả hai,
một phiếu đổi máy mặc định sau khi các dòng đã chọn tay sẽ ra hai con số khác
nhau tuỳ báo cáo nào chạy.)

### 4.5 Sửa `Customer Warehouse`

Thêm cặp field sao y cặp `bat_buoc_khoa_phong` đang chạy:

| Fieldname | Kiểu | Nhãn |
|---|---|---|
| `bat_buoc_thiet_bi` | Check | Bắt buộc chọn máy khi Xuất sử dụng |
| `bat_buoc_thiet_bi_tu` | Datetime, read-only | Bắt buộc từ |

### 4.6 KHÔNG sửa

- `Customer Stock Ledger Entry` — BR-CP4 cấm, và không cần (§9.1).
- `Customer Stock Lot Balance` — cache tồn theo lô, không liên quan chiều máy.
- `Customer Stock Receipt` / `Customer Stock Receipt Item` — QĐ-TB-3.

---

## 5. Luật nghiệp vụ và ràng buộc

Tất cả kiểm ở **server**, trong `CustomerStockIssue.validate()` /
`before_submit()`. Không tin client — cổng khách là môi trường thù địch.

| # | Luật | Xử lý |
|---|---|---|
| **BR-TB-1** | Máy phải thuộc **cùng bệnh viện** với kho của phiếu | **Chặn** |
| **BR-TB-2** | Máy chọn không nằm trong bảng "Máy sử dụng" của vật tư (bảng **không** rỗng) | **Cảnh báo**, kèm nút *Gắn máy này vào vật tư* (QĐ-TB-11) |
| **BR-TB-3** | Kho bật `bat_buoc_thiet_bi` **và** phiếu tạo **sau** `bat_buoc_thiet_bi_tu` **và** `loai_xuat = "Xuất sử dụng"` → thiếu máy | **Chặn** |
| **BR-TB-4** | Khoa của máy ≠ khoa trên phiếu | **Cảnh báo mềm**, không chặn |
| **BR-TB-5** | Máy `active = 0` | Chặn với phiếu **mới**; phiếu cũ giữ nguyên |
| **BR-TB-6** | Nhân viên khoa tạo/sửa máy | Server **ép** `khoa_phong` = khoa của phiên; bỏ qua giá trị client gửi lên |
| **BR-TB-7** | Nhân viên khoa sửa máy của khoa khác | **Chặn** |
| **BR-TB-8** | Đổi `khoa_phong` của một máy đã tồn tại (điều chuyển máy) | Chỉ **Quản lý**. Số liệu kỳ cũ **không đổi** (QĐ-TB-13) |
| **BR-TB-8b** | Nhân viên khoa sửa **máy dùng chung** (`khoa_phong` trống) | **Chặn** — họ *thấy* và *chọn* được máy dùng chung, nhưng chỉ **Quản lý** sửa được. Máy dùng chung không thuộc khoa nào nên không có khoa nào được quyền đổi nó |
| **BR-TB-9** | Xoá máy đã xuất hiện trên phiếu xuất | **Chặn**; bảo người dùng bỏ tích `active` |

### 5.1 BR-TB-3 chi tiết — sao y cơ chế mốc thời gian của khoa phòng

Đây là chỗ tinh tế nhất và **bắt buộc phải copy nguyên hành vi** của
`_chan_thieu_khoa_phong()` (`customer_stock_issue.py:128`), gồm cả phần tự lành:

1. So `self.creation` (**thời điểm tạo phiếu**, không phải thời điểm ghi sổ) với
   `bat_buoc_thiet_bi_tu`. Phiếu nháp tạo **trước** khi bật cờ vẫn ghi sổ được —
   tránh khoá tồn đọng.
2. Cờ bật mà mốc rỗng (bật qua patch/Data Import/`db.set_value`, không đi qua
   `validate()`) → **coi thời điểm phát hiện là mốc**, ghi luôn xuống kho, ân hạn
   mọi phiếu nháp đang tồn. Fail-open có kiểm soát, đúng như E8 đã quyết.
3. Mốc chỉ được ghi ở **đúng một nơi**: `_ghi_moc_bat_buoc_thiet_bi()` trong
   `CustomerWarehouse.validate()`, bắt cả hai ca (kho cũ bật lần đầu; kho mới tạo
   với cờ bật sẵn).
4. **Phiếu đảo không bao giờ rơi vào chốt này.** `on_cancel` không được phép ném
   lỗi — một máy bị tắt giữa lúc xuất và lúc huỷ không được làm sập thao tác huỷ.

---

## 6. Phân quyền và cách ly khách hàng

Cách ly dựng trên **bốn lớp cùng lúc**, thiếu một lớp là hở
(xem `frappe-v15-gotchas` và spec kho 06/08):

1. `permission_query_conditions` cho `Customer Equipment` — lọc theo `customer`
   của phiên; nếu là **Nhân viên khoa** thì lọc thêm
   `khoa_phong = <khoa của phiên> OR khoa_phong IS NULL`.
2. `has_permission()` controller override cho bảng con
   `Customer Warehouse Item Equipment` (`istable` không đi qua
   `permission_query_conditions`).
3. **KHÔNG tạo DocPerm cho role `Customer`** trên `Customer Equipment` — đây là
   lớp **chịu lực**; hai lớp trên một mình không đóng được lỗ.
4. API suy `customer` và `khoa_phong` **từ session** qua
   `portal_context.get_portal_member()` / `khoa_phong_cho_don()`, không nhận từ
   tham số.

**Hệ quả đã biết, không phải lỗi mới:** portal user không dùng được
`/printview`; mọi bản in đi qua endpoint whitelist tự kiểm sở hữu rồi render
server-side. Máy không thêm bản in mới nên không phát sinh gì.

**Cảnh báo lặp lại từ spec kho 06/08:** mọi endpoint mới phải **tự gọi
`check_permission` tường minh** — trong build này `frappe.get_doc` **không** tự
enforce `has_permission`.

---

## 7. Màn hình và luồng thao tác

### 7.1 Màn danh mục "Thiết bị" (mới)

Sao y cặp `KhoaPhongList.vue` + `KhoaPhongModal.vue`:

- `views/ThietBiList.vue` — bảng: Mã máy · Tên máy · Khoa phòng · Hãng · Xuất xứ
  · Serial · Trạng thái. Có ô tìm, có phân trang (`PhanTrang.vue`), có bộ lọc
  *"cả máy đã tắt"*.
- `components/ThietBiModal.vue` — form đầy đủ.
- Vào cùng nhóm **Danh mục** với Vật tư / NCC / Khoa phòng.
- **Nhân viên khoa**: chỉ thấy máy khoa mình + máy dùng chung; thêm/sửa được máy
  **khoa mình**; ô Khoa phòng **khoá cứng** ở khoa của họ.
- **Quản lý**: thấy và sửa mọi máy; là người duy nhất đổi được khoa của máy.

### 7.2 Gắn máy vào vật tư (`VatTuModal.vue`)

Thêm section *"Máy sử dụng"* với ô chọn nhiều máy. Không bắt buộc. Có nút tạo
nhanh (§7.4).

### 7.3 Lập phiếu xuất (`PhieuXuatDetail.vue`)

- Đầu phiếu: ô **Máy mặc định** đặt cạnh ô **Khoa phòng nhận**.
- Bảng dòng: thêm cột **Máy** (dropdown) ngay sau cột vật tư.
- Dropdown máy **chỉ** gọi `kho_thiet_bi_list`, **tuyệt đối không** dùng Link
  field chuẩn / `frappe.desk.search.search_link`. Lý do: đường `search_link` với
  `ignore_user_permissions=1` là **lỗ đã biết, chưa vá** của site này — bất kỳ
  tài khoản cổng nào cũng liệt kê được bản ghi của khách khác. Dùng nó ở đây vừa
  đẻ thêm một ca của lỗi cũ, vừa biến bộ lọc hai tầng thành thứ do **client tự
  khai** nên bỏ qua được.
- Chọn vật tư xong, dropdown máy lọc **hai tầng, giao nhau**:
  - *tầng tài khoản*: máy của khoa mình + máy dùng chung (Nhân viên khoa) /
    toàn bộ máy bệnh viện (Quản lý);
  - *tầng vật tư*: nếu vật tư có bảng "Máy sử dụng" thì chỉ hiện máy trong bảng
    đó; bảng trống thì bỏ qua tầng này.
- Còn **đúng một máy hợp lệ** → **tự điền**, thủ kho không phải bấm.
- Đổi **Máy mặc định** → điền xuống các dòng **đang trống**, **không ghi đè**
  dòng đã chọn tay.
- Chọn máy ngoài bảng của vật tư (BR-TB-2) → dòng cảnh báo màu vàng ngay dưới ô,
  kèm nút **"Gắn máy này vào vật tư"**; bấm là ghi vào bảng con rồi cảnh báo tắt.

### 7.4 Tạo nhanh máy ngay trong form

Áp dụng đúng khuôn *inline quick create*:

- Nút **"+ Tạo nhanh máy «chữ vừa gõ»"** ghim ở **dòng đầu dropdown**, hiện **cả
  khi đang gõ và đã có kết quả** — người dùng hay thấy vài kết quả gần đúng mà
  vẫn cần máy mới.
- Dùng **`@mousedown.prevent`**, **không** dùng `@click`: blur của input đóng
  dropdown trước, `@click` sẽ không bao giờ chạy và nút trông như hỏng.
- Nhãn tiếng Việt lấy từ map, không phơi tên doctype.
- **Điền sẵn** chữ vừa gõ vào ô *Tên máy*.
- Form tạo nhanh **đúng 6 ô**: Tên máy · Mã máy · Hãng · Xuất xứ · Số serial ·
  Khoa phòng *(khoá sẵn với Nhân viên khoa)*. Model / năm SX / ngày lắp đặt để
  màn danh mục sửa sau — quick create là **ít ô**, không phải một form thứ hai.
- **Validate server y hệt** form đầy đủ. "Nhanh" nói về số ô, không nói về độ
  chặt.
- Tạo xong: máy mới **trả thẳng vào ô đang điền**, và nếu đang ở phiếu xuất thì
  đồng thời hỏi *"Gắn luôn vào danh mục máy của vật tư này?"*.

### 7.5 Nhập phiếu hàng loạt bằng Excel

`kho_dong_phieu_mau` / `kho_dong_phieu_doc_file`: thêm cột **Mã máy**, khớp theo
`ma_thiet_bi` trong phạm vi bệnh viện. Mã sai → **báo ở bản xem trước**, không
lặng lẽ bỏ qua rồi ghi sổ thiếu máy.

---

## 8. API

Thêm vào `api/kho.py` (tất cả `@frappe.whitelist()`, tất cả suy bệnh viện/khoa
từ session):

| Endpoint | Việc |
|---|---|
| `kho_thiet_bi_list(tim_kiem, ca_inactive, khoa_phong, vat_tu, limit, start)` | Danh sách máy, đã lọc hai tầng. `vat_tu` là tham số lọc tầng 2 |
| `kho_thiet_bi_save(data)` | Tạo/sửa. Ép `customer` và (với Nhân viên khoa) `khoa_phong` từ phiên |
| `kho_thiet_bi_tao_nhanh(data)` | Tạo nhanh 6 ô; trả về bản ghi đủ để điền vào dropdown |
| `kho_vat_tu_gan_thiet_bi(vat_tu, thiet_bi)` | Nút *Gắn máy này vào vật tư* — ghi một dòng vào bảng con, idempotent |
| `kho_bao_cao_thiet_bi(tu_ngay, den_ngay, thiet_bi, khoa_phong, vat_tu, limit, start)` | Báo cáo §9.2 |

**Đường ghi dữ liệu — chỗ dễ phá cách ly nhất, ghi rõ để không ai "sửa" nhầm:**
Nhân viên khoa là `Website User` và **không có DocPerm** trên `Customer
Equipment` (§6.3, lớp chịu lực). Vậy họ ghi bằng cách nào? Ba endpoint
`kho_thiet_bi_save` / `kho_thiet_bi_tao_nhanh` / `kho_vat_tu_gan_thiet_bi` **tự
kiểm tenant và khoa tường minh trước**, rồi ghi bằng
`insert(ignore_permissions=True)` / `save(ignore_permissions=True)` — đúng khuôn
`kho/khoa_phong.py:184` đang chạy.

> **THÊM DOCPERM KHÔNG BAO GIỜ LÀ CÁCH SỬA.** Một người triển khai gặp lỗi
> `PermissionError` rất dễ "sửa" bằng cách cấp DocPerm cho role `Customer` —
> thao tác đó **âm thầm gỡ mất lớp cách ly duy nhất thật sự đóng được lỗ**, và
> mọi test phân quyền vẫn xanh vì chúng đi qua chính các endpoint này.

Sửa: `kho_phieu_xuat_save` nhận thêm `thiet_bi` trên mỗi dòng và
`thiet_bi_mac_dinh` ở đầu phiếu; `kho_vat_tu_list` / `kho_vat_tu_tao` /
`kho_vat_tu_sua` nhận thêm `may_su_dung`; `kho_bao_cao_excel` nhận thêm loại báo
cáo mới.

---

## 9. Báo cáo

### 9.1 Cách lấy số — bắt buộc theo đúng khuôn đang chạy

- Nguồn là **sổ kho** `Customer Stock Ledger Entry`, join
  `chung_tu_row` → `Customer Stock Issue Item.thiet_bi`. **Không sửa schema sổ**
  (QĐ-TB-14, BR-CP4).
- **Loại trừ hai lớp, không được gộp làm một** — sao y `bao_cao_cap_phat_rows`:
  - `da_dao = 0` ở tầng **sổ** → bỏ dòng gốc của phiếu đã huỷ;
  - `loai_xuat = "Xuất sử dụng"` ở tầng **phiếu** → bỏ chính **dòng bù trừ** của
    phiếu đảo (`loai_xuat = "Phiếu đảo"`, `da_dao = 0` vì bản thân nó không bị
    đảo) và mọi loại xuất khác.
  Lọc một lớp là **lọt lớp còn lại**. Đây là lỗi đã từng bị bắt trong E8.
- Gộp theo **docname** của máy và vật tư, **không gộp theo tên** — trong cùng một
  kho, `ten_vat_tu` không duy nhất, gộp theo tên sẽ âm thầm cộng hai vật tư khác
  ĐVT vào một dòng.
- Khoa lấy từ **phiếu** (QĐ-TB-13).
- Số lượng dòng xuất trong sổ mang **dấu âm** → đảo dấu khi hiển thị.
- Xuất Excel dùng `build_xlsx` sẵn có.

### 9.2 Báo cáo chính — "Vật tư · Máy · Khoa phòng"

Màn Báo cáo trên cổng, chọn kỳ. Một dòng = **một vật tư**:

| Mã VT | Tên vật tư | ĐVT | Tồn đầu | Đã nhập | **Đã cấp phát** | **Xuất khác** | Tồn cuối | Máy sử dụng |

Mở rộng một dòng → tách theo **máy**:

| Máy | Khoa phòng | SL xuất | Giá trị | % |

**Vì sao có hai cột xuất, không phải một** *(sửa sau soát lại — bản nháp đầu đã
sai chỗ này)*: module đang chạy **hai quy ước đếm khác nhau và cố ý khác nhau**:

- NXT / thẻ kho / `nxt_data`: *"`da_dao = 1` **KHÔNG** bị lọc khỏi bất kỳ tổng
  nào"* — câu hỏi kế toán lịch sử, "mọi biến động trong kỳ, kể cả phần sau đó bị
  đảo".
- `bao_cao_cap_phat_rows`: lọc **hai lớp** — câu hỏi nghiệp vụ khác, "khoa nào
  **đang thực sự giữ** hàng đã cấp phát".

Đặt một cột *Đã xuất* kiểu NXT cạnh phần tách theo máy kiểu cấp phát thì hai bên
lệch nhau vì **hai lý do độc lập**: (1) phiếu bị đảo trong kỳ, và (2) phiếu
`Xuất huỷ - hết hạn` / `Xuất trả lại` / `Điều chỉnh kiểm kê` — vốn **không mang
máy** theo thiết kế (BR-TB-3 chỉ áp cho `Xuất sử dụng`). Đây **không phải ca
biên**: §2 đo được ngay trên site demo hôm nay **4 phiếu xuất, chỉ 3 là `Xuất sử
dụng`**.

Chốt: tách làm hai cột.

- **Đã cấp phát** = lọc hai lớp, **đúng bằng** tổng SL xuất của phần tách theo
  máy. Bất biến này **có thật** và đáng ghi ra.
- **Xuất khác** = huỷ / trả lại / điều chỉnh / phần đã bị đảo. Không tách theo
  máy, và không cần.
- Nhờ vậy hàng vẫn **cân**: `Tồn đầu + Đã nhập − Đã cấp phát − Xuất khác = Tồn
  cuối`. Trưởng khoa cộng tay ra đúng số.
- Cột *Đã nhập* **không tách theo máy** (QĐ-TB-3).
- Cột *Máy sử dụng* ở bảng ngoài hiện danh sách máy khai trong bảng con — là
  **danh mục tương thích**, không phải số liệu.
- Nhóm **"Chưa gắn máy"** luôn ở **cuối**, không lẫn vào máy thật, **không bị
  giấu** (cùng lý lẽ với "Chưa gắn khoa" của US-E8.5: đó là dữ liệu thật).

### 9.3 Báo cáo xoay chiều — "Theo máy"

Một dòng = **một máy** → tiêu thụ những vật tư gì, bao nhiêu, giá trị bao nhiêu
trong kỳ. Đây là câu hỏi của trưởng khoa: *"máy XN-500 tháng này ngốn bao nhiêu
tiền hóa chất"*.

### 9.4 Mở rộng báo cáo cấp phát theo khoa đã có

Thêm cấp thứ ba vào `bao_cao_cap_phat_rows`: **Khoa → Máy → Vật tư**. Không viết
báo cáo mới, không đổi chữ ký hàm theo hướng phá tương thích.

### 9.5 Bên Desk (Miyano nhìn nhiều bệnh viện)

Thêm `tieu_thu_theo_thiet_bi_rows(customer, tu_ngay, den_ngay)` vào
`kho/desk_reports.py`, lọc theo `customer` như các hàm sẵn có — để Miyano biết
máy nào ở bệnh viện nào đang tiêu thụ gì, phục vụ dự trù và bán hàng.

---

## 10. Di trú và tương thích ngược

- **Không backfill.** Dữ liệu hiện có không chứa tên máy ở bất cứ đâu (§2), nên
  không có gì để suy. Mọi phiếu xuất cũ có `thiet_bi` rỗng → nhóm *"Chưa gắn
  máy"*.
- **Không có ngày "cả hệ thống đổi cách hoạt động".** Cờ `bat_buoc_thiet_bi` mặc
  định **tắt** ở mọi kho; bệnh viện nào sẵn sàng thì bật riêng, đúng như cách
  khoa phòng đã triển khai.
- Patch thêm field đi theo `patches.txt` như thường lệ. **Lưu ý đã có tiền lệ
  đau:** `install_app` trên site đã tồn tại có thể **đánh dấu patch là xong mà
  không chạy** — sau khi triển khai phải đối chiếu `Patch Log.creation`, và mọi
  chỗ đọc field mới phải **fail-closed khi thiếu cột** giống
  `portal_context._cot_khoa_phong_ton_tai()`.
- Báo cáo cũ (`kho_bao_cao_cap_phat`, `kho_bao_cao_nxt`, thẻ kho, nhật ký) **giữ
  nguyên đầu ra** khi chưa ai khai máy.

---

## 11. Kiểm thử

Viết test **trước** (lệ của app). Các ca bắt buộc có:

| # | Ca | Kỳ vọng |
|---|---|---|
| 1 | Vật tư dùng 3 máy, xuất cho 2 trong 3 | Tổng theo máy = tổng xuất; **không cộng trùng**; máy thứ ba không xuất hiện với số 0 giả |
| 2 | Phiếu xuất bị huỷ (sinh phiếu đảo) | Không lọt qua **cả hai** lớp lọc; tổng theo máy không đổi |
| 3 | Phiếu cũ không có `thiet_bi` | Vào *"Chưa gắn máy"*, không biến mất, không lẫn vào máy thật |
| 4 | Máy chuyển khoa giữa kỳ | Số liệu kỳ trước **không đổi** |
| 5 | Nhân viên khoa A | Không thấy máy khoa B trong dropdown, trong danh mục, và trong báo cáo |
| 6 | Nhân viên khoa gọi thẳng `kho_thiet_bi_save` với `khoa_phong` của khoa khác | Bị ép về khoa của phiên hoặc bị chặn — **không** tạo được |
| 7 | Máy của bệnh viện khác truyền vào phiếu xuất | Chặn (BR-TB-1) |
| 8 | Bật `bat_buoc_thiet_bi` khi đang có phiếu nháp | Phiếu nháp cũ **vẫn ghi sổ được**; phiếu tạo sau bị chặn |
| 9 | Cờ bật nhưng mốc rỗng | Tự lành: ghi mốc = now, ân hạn phiếu đang tồn |
| 10 | Hai vật tư khác ĐVT cùng tên trong một kho | Báo cáo tách **hai dòng** (gộp theo docname) |
| 11 | Xoá máy đã dùng trên phiếu | Bị chặn kèm thông báo tiếng Việt hướng dẫn bỏ tích `active` |
| 12 | Tạo nhanh máy trùng tên (khác dấu/hoa thường) | Bị chặn như form đầy đủ |
| **13** | Một kỳ chứa **cả** một phiếu `Xuất huỷ - hết hạn` **và** một phiếu đã bị đảo | Hàng vật tư vẫn **cân**: `Tồn đầu + Đã nhập − Đã cấp phát − Xuất khác = Tồn cuối`; tổng theo máy = đúng cột *Đã cấp phát*, **không** bằng tổng xuất thô |
| 14 | Gọi thẳng `frappe.desk.search.search_link` để liệt kê `Customer Equipment` | Không lấy được máy của bệnh viện khác (§7.3, §8) |

---

## 12. Cố ý KHÔNG làm

- **Không** phân bổ ước lượng số nhập theo tỉ lệ tiêu thụ. Chủ đầu tư đã chốt
  "nhập thì cứ nhập". Mọi con số trong báo cáo là số có người khai.
- **Không** thêm chiều máy vào phiếu nhập, sổ kho, hay cache tồn theo lô.
- **Không** quản lý lý lịch thiết bị: bảo trì, hiệu chuẩn, hỏng hóc, hợp đồng
  bảo hành, nhật ký sử dụng. Đó là một hệ thống khác.
- **Không** tính định mức tiêu hao trên mỗi lượt chạy máy / mỗi xét nghiệm.
- **Không** gắn máy vào `Item` của ERPNext hay vào `Asset`.
- **Không** backfill máy cho phiếu cũ bằng suy đoán.

## 13. Mở sau, nếu chủ đầu tư muốn

- Cảnh báo *"máy A tiêu thụ vượt trung bình 3 tháng gần nhất"* — ghép vào bộ
  cảnh báo tồn đã có.
- Gợi ý dự trù theo máy (nối vào `dutru.py` / min-max sẵn có).
- Màn *"Máy của tôi"* cho nhân viên khoa: máy khoa mình đang dùng vật tư gì,
  còn tồn bao nhiêu.

---

## 14. Việc phải làm trước khi lập kế hoạch thi công

Chủ đầu tư đọc lại tài liệu này, đặc biệt **§3.1** (ba quyết định chống trực
giác) và **§12** (những thứ cố ý không làm). Có chỗ nào sai ý thì sửa ở đây,
trước khi có một dòng code nào.
