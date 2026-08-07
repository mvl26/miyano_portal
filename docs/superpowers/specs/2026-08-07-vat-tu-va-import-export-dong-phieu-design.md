# Thiết kế: Danh mục vật tư trên cổng + import/export bảng dòng phiếu

Ngày: 2026-08-07 · App: `miyano_portal` · Nối tiếp
[Kho Khách Hàng](2026-08-06-kho-khach-hang-design.md)

## 1. Bài toán

Hôm nay khách chỉ có **một** đường tạo vật tư trong kho của mình: file nhập tồn
đầu kỳ, vốn dùng một lần lúc mở kho. Sau đó, muốn thêm một mã mới (hàng mua
ngoài, mã nội bộ mới của bệnh viện) thì không có nút nào — phải gọi nhân viên
Miyano vào desk làm hộ. Đồng thời, bảng dòng của phiếu nhập/phiếu xuất chỉ gõ
tay được từng dòng, trong khi dữ liệu của bệnh viện thường đã nằm sẵn trên Excel.

Cần ba việc, cho cùng một nhóm người dùng (thủ kho của bệnh viện):

1. Một màn **danh mục vật tư** để khách tự thêm, sửa, bật/tắt, import và export.
2. **Import/export bảng dòng** ngay trong phiếu nhập và phiếu xuất.
3. Khi import mà gặp mã chưa có, hiện **nút tạo nhanh ngay tại dòng đó** — bấm là
   vật tư được tạo và gán vào dòng, không phải rời màn hình đang soạn dở.

## 2. Quyết định nền tảng

**Không thêm doctype nào.** `Customer Warehouse Item` đã đủ trường (`ma_vat_tu`,
`ten_vat_tu`, `dvt`, `item_code`, `quy_cach`, `nhom`, `ghi_chu`, `active`) và
controller của nó đã tự chặn trùng mã trong cùng kho
(`_unique_within_warehouse`).

**Dùng lại bộ đọc file đã có.** `kho/import_ton_dau.py` đã có `_read_header`,
`_coerce_date`, `_coerce_num` và — quan trọng nhất — `_match_vat_tu()`, hàm phân
loại một mã thành *đã có trong kho* / *khớp Item Miyano* / *mã riêng*. Đó chính là
phép phân loại mà nút "tạo vật tư mới" cần. Viết lần thứ hai là chấp nhận hai bộ
quy tắc đọc cùng một file, chắc chắn lệch nhau sau vài lần sửa.

**Đọc file ở server, không ở trình duyệt.** Phương án đọc `.xlsx` bằng JavaScript
cho phản hồi nhanh hơn nhưng buộc phải chép lại toàn bộ quy tắc đọc ngày/số/tiêu
đề cột sang JS, mà việc kiểm mã vật tư vẫn phải hỏi server — không tiết kiệm được
vòng gọi mạng nào đáng kể.

**Tạo vật tư là một lời gọi riêng, không phải hiệu ứng phụ của việc lưu phiếu.**
Phương án "gửi dòng kèm `ma_vat_tu_moi`, server tự tạo khi lưu nháp" ít endpoint
hơn nhưng xoá mất chính thao tác người dùng yêu cầu (bấm OK cho từng dòng), và
biến "Lưu nháp" thành hành động âm thầm sinh bản ghi danh mục.

## 3. Kiến trúc

### 3.1 Module mới

| Module | Trách nhiệm | Không làm |
|---|---|---|
| `kho/vat_tu.py` | tạo · sửa có rào · `co_phat_sinh()` · đọc/ghi file danh mục | không chạm tới sổ, không biết gì về phiếu |
| `kho/dong_phieu.py` | đọc file thành dòng phiếu · xuất dòng phiếu ra `.xlsx` · sinh file mẫu | không ghi database |

Cả hai chỉ nhận `kho` đã được resolve từ nơi gọi, đúng khuôn `ledger.py` /
`reports.py` / `import_ton_dau.py` hiện có: tầng `api/kho.py` lo phiên và quyền,
tầng `kho/*.py` lo nghiệp vụ.

### 3.2 Endpoint mới trong `api/kho.py`

```
kho_vat_tu_tao(payload)                  → tạo 1 vật tư, trả bản ghi để gắn vào dòng
kho_vat_tu_sua(name, payload)            → sửa có rào
kho_vat_tu_list(tim=None, ca_tat=0)      → MỞ RỘNG: thêm quy_cach, nhom, active, co_phat_sinh
kho_vat_tu_export()                      → .xlsx danh mục
kho_vat_tu_import_preview(file_url)      → xem trước, không ghi
kho_vat_tu_import_commit(file_url)       → ghi, tất-cả-hoặc-không
kho_dong_phieu_mau(loai)                 → .xlsx rỗng đúng cột
kho_dong_phieu_doc_file(loai, file_url)  → đọc file → dòng + trạng thái, KHÔNG ghi
kho_dong_phieu_export(doctype, name)     → .xlsx các dòng của một phiếu đã lưu
```

`loai` chỉ nhận `"nhap"` / `"xuat"`, qua đúng danh sách trắng `_LOAI_TO_DOCTYPE`
đang dùng cho `kho_phieu_list`.

`kho_vat_tu_list` **mở rộng chứ không thay thế**: hai màn phiếu đang gọi nó và
chỉ đọc `name`/`ma_vat_tu`/`ten_vat_tu`/`dvt`/`item_code`; các trường mới là phần
thêm vào, tham số mới đều có mặc định giữ nguyên hành vi cũ (`ca_tat=0` → vẫn chỉ
trả vật tư đang dùng).

## 4. Quy tắc nghiệp vụ

### 4.1 Tạo vật tư

1. `kho` lấy từ phiên, không bao giờ từ payload.
2. `item_code` **không nhận từ client**. Server tự suy qua `_match_vat_tu`:
   - mã trùng `Item.item_code` của Miyano (không phân biệt hoa thường) → gắn
     `item_code`, và ghi mã theo **chính tả chuẩn trong hệ thống Miyano**, không
     theo cách khách gõ;
   - không trùng → mã riêng, `item_code` để trống.
   Nhận `item_code` từ client cho phép khách nối vật tư của mình vào một mặt hàng
   Miyano bất kỳ, và từ đó hook Delivery Note sẽ cộng hàng vào đúng dòng danh mục
   sai đó. Không rò rỉ dữ liệu của khách khác, nhưng làm bẩn sổ của chính họ theo
   cách không ai lần ra được.
3. Trùng mã trong cùng kho: controller đã chặn. Ở tầng API, khi mã đã tồn tại thì
   **trả về chính vật tư đang có** thay vì ném lỗi — vì luồng thật là khách bấm
   "Tạo vật tư" ở dòng 2 sau khi đã tạo từ dòng 1 cùng mã. Kiểm **trước** bằng
   `_match_vat_tu` (nhánh `existing`), không bắt ngoại lệ của controller: bắt
   `ValidationError` giữa một transaction đang mở là cách chắc chắn để lại trạng
   thái nửa vời.
4. Trường nhận từ client là danh sách trắng: `ma_vat_tu`, `ten_vat_tu`, `dvt`,
   `quy_cach`, `nhom`, `ghi_chu`. Không `doc.update(payload)`.

### 4.2 Sửa có rào

`co_phat_sinh(vat_tu)` = tồn tại ít nhất một `Customer Stock Ledger Entry` của
vật tư đó.

| Trường | Khi chưa có phát sinh | Khi đã có phát sinh |
|---|---|---|
| `ten_vat_tu`, `quy_cach`, `nhom`, `ghi_chu` | sửa được | sửa được |
| `ma_vat_tu`, `dvt` | sửa được | **khoá** |
| `active` | bật/tắt được | bật/tắt được, trừ ràng buộc §4.3 |

`dvt` bị khoá vì mọi dòng sổ cũ đã tính theo ĐVT đó và hệ thống **không quy đổi**
— đổi ĐVT làm tồn 133 Hộp đọc thành 133 Cái mà không có gì tự lộ ra. `ma_vat_tu`
bị khoá vì nó là thứ file import và người đọc chứng từ dùng để nhận diện.

Giao diện hiện 🔒 kèm lý do đọc được ("đã có 12 phát sinh trong sổ"), không phải
ô xám không giải thích.

### 4.3 Không tắt vật tư còn tồn

`active = 0` khi tồn > 0 bị chặn:
*"… còn tồn 133 Hộp. Hãy xuất hết trước khi ngừng dùng."*

Lý do: `kho_vat_tu_list` lọc `active = 1` nên vật tư tắt biến mất khỏi ô chọn,
trong khi báo cáo tồn đọc từ `Customer Stock Lot Balance` và vẫn hiện số của nó —
một trạng thái không ai giải thích được sau vài tháng.

### 4.3b Import danh mục: mã đã có thì cập nhật, chưa có thì tạo

File danh mục là file **xuất ra sửa rồi nạp lại**, nên mỗi dòng xử lý theo mã:

- **Mã chưa có** → tạo mới theo §4.1.
- **Mã đã có** → cập nhật `ten_vat_tu`, `quy_cach`, `nhom`, `ghi_chu`, `active`.
  `ma_vat_tu` là khoá đối chiếu nên không đổi được bằng đường này; `ĐVT` chỉ được
  cập nhật khi vật tư **chưa có phát sinh**, đúng rào §4.2.
- Dòng vi phạm rào (đổi ĐVT của vật tư đã có phát sinh, hoặc `Đang dùng = 0` cho
  vật tư còn tồn theo §4.3) là **dòng lỗi trong bản xem trước**, nêu rõ lý do —
  không phải một thay đổi bị bỏ qua im lặng.

Toàn bộ file vẫn theo nguyên tắc tất-cả-hoặc-không: còn một dòng lỗi thì không
bản ghi nào được ghi.

### 4.4 Đọc file vào bảng dòng phiếu

`kho_dong_phieu_doc_file` **không ghi gì**. Mỗi dòng trả về mang một trạng thái:

| Trạng thái | Nghĩa | Giao diện |
|---|---|---|
| `khop` | mã đã có trong kho, `vat_tu` đã gán sẵn | dòng bình thường |
| `ma_moi` | mã chưa có (kể cả mã khớp Item Miyano nhưng kho chưa khai) | nền vàng + nút **Tạo vật tư** |
| `loi` | thiếu trường bắt buộc, hoặc ngày/số sai định dạng | nền đỏ, nêu **số dòng trong Excel** và lý do |

Các dòng **nối vào cuối bảng đang có**, không xoá dòng nào đã gõ tay.

**Các cột mô tả (`Tên vật tư`, `ĐVT`, `Quy cách`, `Nhóm`) chỉ dùng khi tạo vật tư
mới.** Mã đã có trong danh mục thì lấy theo danh mục và bỏ qua các cột đó. Nếu
không, một file cũ nạp lại sẽ âm thầm đổi ĐVT của vật tư đang có phát sinh — đúng
cái bẫy mà khoá 🔒 ở §4.2 dựng lên để tránh.

Bấm **Tạo vật tư** ở một dòng → modal điền sẵn từ chính dòng đó → OK → gọi
`kho_vat_tu_tao` → gán `vat_tu` vào dòng, và **cập nhật danh mục trong bộ nhớ**
để mọi dòng khác cùng mã tự chuyển sang `khop`. Import 20 dòng cùng một mã lạ chỉ
phải bấm OK một lần.

### 4.5 Riêng phiếu xuất

- File **không có** cột `Đơn giá` và `Hạn sử dụng`: controller luôn lấy hai giá
  trị này từ lô (`_lay_gia_va_han_tu_lo`), nhận từ file là mở đường ghi sai giá vốn.
- Dòng có số lô không tồn tại hoặc đã hết tồn → cảnh báo tại dòng; vẫn lưu nháp
  được, vẫn bị `_chan_xuat_qua_ton` chặn ở bước ghi sổ như hiện nay.
- Vật tư vừa tạo nhanh chưa có lô nào → cảnh báo *"vật tư mới, kho chưa có tồn;
  phải nhập kho trước khi ghi sổ phiếu xuất này"*. **Không chặn lưu nháp** — khách
  soạn trước rồi bổ sung sau là việc bình thường.

### 4.6 Chặn lưu nháp

Còn dòng `loi` hoặc dòng chưa có `vat_tu` → chặn, nêu số dòng còn lại. Chặn ở
client cho phản hồi nhanh **và** chặn lại ở server trong `kho_phieu_*_save`, vì
client không bao giờ là chốt.

## 5. Bộ cột file

Xuất ra nạp lại được (round-trip). Nhận cột theo **tên tiêu đề**, không theo thứ
tự, không phân biệt hoa thường — dùng lại `_read_header` sẵn có.

| File | Cột |
|---|---|
| Danh mục | `Mã vật tư` · `Tên vật tư` · `ĐVT` · `Mã hàng Miyano` · `Quy cách` · `Nhóm` · `Đang dùng` |
| Phiếu nhập | `Mã vật tư` · `Tên vật tư` · `ĐVT` · `Số lô` · `Hạn sử dụng` · `Số lượng` · `Đơn giá` · `Quy cách` · `Nhóm` · `Ghi chú` |
| Phiếu xuất | `Mã vật tư` · `Tên vật tư` · `ĐVT` · `Số lô` · `Số lượng` · `Quy cách` · `Nhóm` · `Ghi chú` |

Chín cột đầu của file phiếu nhập trùng khít file nhập tồn đầu kỳ hiện có, nên một
file tồn đầu kỳ thả thẳng vào phiếu nhập cũng chạy — khách không phải học hai
định dạng.

Cột bắt buộc có giá trị: `Mã vật tư`, `Số lượng` (và `Đơn giá` cho phiếu nhập).
`Tên vật tư`/`ĐVT` bắt buộc **chỉ khi** mã đó chưa có trong kho — không có chúng
thì không tạo nhanh được.

Trong file danh mục, cột `Mã hàng Miyano` là **chỉ đọc**: nó được xuất ra cho
khách đối chiếu, nhưng khi nạp lại thì bỏ qua (server tự suy, §4.1).

## 6. Giao diện

### 6.1 Màn danh mục vật tư — `/kho/vat-tu`

Vào từ **Kho của tôi**, thêm nút thứ năm cạnh *Phiếu nhập · Phiếu xuất · Nhập tồn
đầu kỳ · Báo cáo*.

Bảng: Mã · Tên · ĐVT · Mã hàng Miyano · Quy cách · Nhóm · Đang dùng · [Sửa].
Có ô tìm và công tắc "hiện cả vật tư đã tắt". Ba nút: **+ Thêm vật tư** ·
**⬇ Xuất danh mục** · **⬆ Nhập danh mục**.

Form thêm/sửa là modal trên desktop và sheet trượt trên mobile — đúng khuôn màn
Giỏ hàng đang dùng, qua `useIsMobile()`.

**Nhập danh mục giữ khuôn ba bước** của màn Nhập tồn đầu kỳ (chọn tệp → xem trước
→ xác nhận, tất-cả-hoặc-không). Khác với bảng dòng phiếu vì nó ghi thẳng vào danh
mục dùng chung, không phải vào một bảng nháp trên màn hình.

### 6.2 Bảng dòng phiếu nhập / phiếu xuất

Thêm một hàng nút trên bảng: **⬇ Xuất Excel** · **⬆ Nhập từ Excel** ·
**Tải file mẫu** · **+ Thêm dòng**.

**Xuất Excel chỉ bật khi phiếu đã lưu.** Server đọc dòng từ database, không nhận
dòng từ client rồi xuất lại. Phiếu mới chưa lưu thì dùng **Tải file mẫu**.

Ô chọn vật tư có thêm mục cuối **➕ Tạo vật tư mới…**, mở đúng modal của §4.4 —
để người gõ tay cũng tạo được vật tư không cần đi qua import.

Trên mobile, mỗi dòng render thành một thẻ, cảnh báo và nút "Tạo vật tư" nằm
trong thẻ đó — theo đúng khuôn hai màn phiếu hiện có.

## 7. Cách ly dữ liệu

Tính năng này thêm bảy endpoint nhận tham số từ client, nên các ràng buộc của
[thiết kế kho](2026-08-06-kho-khach-hang-design.md) §6 phải được giữ nguyên vẹn:

- Mọi endpoint suy kho từ `get_portal_kho()`. Không cái nào nhận tên kho.
- `kho_vat_tu_sua(name, …)` và `kho_dong_phieu_export(doctype, name)` nhận định
  danh từ client → qua `_vat_tu_cua_kho()` / `_phieu_cua_kho()` **trước** mọi
  `frappe.get_doc`. `get_doc` không tự chạy hook `has_permission` ở build này.
- `doctype` do client gửi phải nằm trong `voucher.VOUCHER_DOCTYPES`.
- File upload qua `_resolve_owned_spreadsheet()`: kiểm `owner == session.user`,
  đuôi `.xlsx`, thông điệp tiếng Việt khi tệp không tồn tại.
- **Không cấp thêm bất kỳ DocPerm nào cho role `Customer`.** Thêm một cái là mở
  lại đúng lỗ cách ly mà kiến trúc này dựng lên để bịt.
- `frappe.get_all` / `frappe.db.get_value` với filter `kho` tường minh là đúng ở
  đây, không phải lỗ hổng — xem khối comment đầu `api/kho.py`.

## 8. Xử lý lỗi

- Toàn bộ thông điệp tiếng Việt, không lộ tên doctype. Bọc `_phieu_action` cho
  các endpoint mới để lỗi ngoài dự kiến thành một câu chung + ghi Error Log.
- **Tham số số không gắn type hint.** `frappe.utils.typing_validations` kích hoạt
  cả trong test và ném lỗi tiếng Anh trước khi hàm chạy — bẫy này đã được ghi rõ
  trong `api/kho.py`.
- Lỗi đọc file nêu **số dòng trong Excel**, không phải chỉ số mảng.
- Validation đặt ở `before_save`/`validate`, không ở `on_update`: `db_update()`
  chạy trước `run_post_save_methods()`, guard đặt sai chỗ chặn sau khi dữ liệu đã
  ghi.

## 9. Kiểm thử

Bốn nhóm, theo khuôn `FrappeTestCase` + `seed_kho_demo()` của các test hiện có.
Không sửa test cũ.

| File | Ca chính |
|---|---|
| `test_kho_vat_tu_api.py` | mã khớp Item → tự gắn `item_code` và chuẩn hoá chính tả · mã riêng → `item_code` trống · `item_code` do client gửi bị bỏ qua · tạo trùng mã → trả về vật tư đang có · sửa tên khi đã có phát sinh → được · sửa `dvt`/`ma_vat_tu` khi đã có phát sinh → chặn · tắt vật tư còn tồn → chặn · vật tư của kho khác → `PermissionError` |
| `test_kho_dong_phieu_import.py` | ba trạng thái dòng đúng · thiếu cột bắt buộc · ngày/số sai định dạng nêu đúng số dòng · file phiếu xuất không nhận `Đơn giá` · file của người dùng khác → `PermissionError` · `loai` lạ → lỗi tiếng Việt |
| `test_kho_vat_tu_import.py` | preview không ghi gì · commit tất-cả-hoặc-không · một dòng lỗi → không bản ghi nào được tạo · mã đã có → cập nhật chứ không tạo trùng · đổi ĐVT của vật tư đã có phát sinh → dòng lỗi · round-trip: xuất danh mục rồi nạp lại không đổi dữ liệu |
| bổ sung `test_kho_phieu_api.py` | server chặn lưu phiếu có dòng thiếu `vat_tu` (không chỉ chặn ở client) |

## 10. Không làm

Xoá vật tư (chỉ tắt) · sửa hàng loạt trên bảng danh mục · file `.csv` · gộp/tách
vật tư · đổi mã của vật tư đã có phát sinh · quy đổi ĐVT.

## 11. Thứ tự triển khai đề xuất

Ba mảng độc lập nhau về mã nguồn, nên chạy được theo thứ tự nào cũng xong, nhưng
thứ tự dưới đây cho ra thứ dùng được sớm nhất ở mỗi bước:

1. `kho/vat_tu.py` + `kho_vat_tu_tao/sua` + mở rộng `kho_vat_tu_list` → nút
   **➕ Tạo vật tư mới…** trong ô chọn vật tư của hai màn phiếu đã dùng được ngay.
2. Màn danh mục `/kho/vat-tu` + export + import danh mục.
3. `kho/dong_phieu.py` + import/export bảng dòng ở phiếu nhập, rồi phiếu xuất.

## 12. Rủi ro

| Rủi ro | Giảm thiểu |
|---|---|
| Khách tạo hàng loạt mã trùng nghĩa (`KIM-22G`, `Kim 22G`, `kim22g`) làm rối danh mục | Ngoài phạm vi bản này; màn danh mục có ô tìm để tự phát hiện. Việc gộp vật tư nằm ở §10. |
| File Excel lớn (vài nghìn dòng) làm chậm request | Đọc file vốn đã ở server và đồng bộ như màn tồn đầu kỳ hiện tại; nếu chạm ngưỡng thì giới hạn số dòng mỗi lần import và báo rõ, không âm thầm cắt |
| `kho_vat_tu_list` bị mở rộng làm chậm hai màn phiếu | `co_phat_sinh` tính bằng một truy vấn gộp theo kho, không phải mỗi vật tư một truy vấn |
