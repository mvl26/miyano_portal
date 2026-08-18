# Hướng giải quyết 5 yêu cầu cải tiến của Hi-medic

**Ngày:** 17/08/2026 · **sửa đổi 18/08/2026** (xem §0 — bốn khẳng định bị bác, hai lỗi mới phát hiện)
**Nguồn:** tài liệu cải tiến do Hi-medic gửi (5 mục), có ghi chú "ý kiến của Thùy" ở mục 3.
**Trạng thái:** ĐỀ XUẤT — chưa viết code, chưa tạo custom field, chưa đụng schema.
Cần chủ đầu tư chốt các quyết định ở §3 trước khi làm.

Đánh số quyết định dùng tiền tố **QĐ-HM-** (không dùng "QĐ-n" trơn): trong bộ
tài liệu của dự án đã có hai dãy "QĐ" của hai văn bản khác nhau đang chọi số
nhau, thêm một dãy trơn nữa là thêm một chỗ để hiểu sai.

---

## 0. Bản sửa đổi 18/08/2026 — kiểm chứng lại

Bản 17/08 dựng trên một lượt đo nhanh. Lượt kiểm chứng sâu ngày 18/08 **bác bỏ
bốn khẳng định** trong đó và **tìm ra hai lỗi đang chạy thật trên cổng khách**.
Ghi lại nguyên văn cái sai, không sửa lặng lẽ:

| # | Bản 17/08 nói | Đo lại 18/08 | Hệ quả |
|---|---|---|---|
| 1 | §4 YC-4.4: "phải đảm bảo MỌI user của Hi-medic nhận được, không chỉ user tạo đơn" | `bao_hen_giao_lai()` gọi `_portal_users_cua_khach()` — **đã gửi cho mọi user enabled** từ trước | Gạch bỏ hạng mục. Không có việc phải làm |
| 2 | §2/§4 YC-5: "hệ thống ĐANG ghi vết, chỉ chưa có màn hình đọc nó" | **Nói quá.** 223/279 bản ghi `Version` là của `Administrator`; `Version` chỉ ghi THAY ĐỔI SAU khi tạo — hành vi "khách đặt đơn" **không sinh bản ghi nào** | Dòng thời gian truy vết phải ghép `owner`+`creation` (sự kiện tạo) VỚI `Version` (sự kiện sửa). Nhiều hơn "một màn hình" |
| 3 | §4 YC-3: "chức năng có sẵn, chỉ thiếu dữ liệu — nhập bảng `Item Supplier`" | **`Supplier` đang có 0 bản ghi.** Không có nhà cung cấp nào để mà gắn | Vẫn là mục rẻ nhất, nhưng bước 1 là **lập danh mục nhà cung cấp**, không phải nhập bảng liên kết |
| 4 | §1/§2: "nhiều user cho một khách **đã chạy được sẵn**" | **Chưa khách nào có 2 user.** 6 tài khoản cổng / 6 khách. Đường code hỗ trợ nhưng **chưa từng chạy thật** | Hạ xuống "hỗ trợ, chưa kiểm chứng" — cần một test dựng 2 user trên cùng Customer trước khi hứa với Hi-medic |

Ngoài ra: **hai lỗi** ở §2b, và **QĐ-HM-5** (mới) cần chốt.

---

## 1. Bối cảnh đã kiểm chứng trên hệ thống

Đã đối chiếu trên site `erptest.local` (không phỏng đoán từ ký ức):

| Việc | Hiện trạng đo được |
|---|---|
| Khách hàng Hi-medic | Customer **`Himedic`** đã tồn tại, chưa disabled, có kho `KKH-00006` ("kho himedic") đang hoạt động |
| Tài khoản cổng | **1 user** duy nhất: `himedic@demo.miyano` (Contact `Himedic-Himedic`). Còn 1 Contact `Himedic-Contact` KHÔNG gắn user |
| Đơn hàng của Hi-medic | 2 đơn (`SAL-ORD-2026-00016`, `SAL-ORD-2026-00004`), cả hai `owner = himedic@demo.miyano` |
| Tổng đơn trên site | 102 Sales Order, đánh số theo `naming_series` (`SAL-ORD-YYYY-NNNNN`) |
| Nhật ký sửa đổi | `track_changes = 1` → 279 bản ghi `Version` toàn site (95 Sales Order, 48 Customer Stock Receipt, 30 Delivery Note). **Nhưng 223/279 là của `Administrator`**; chỉ 41 bản ghi là của tài khoản cổng. Xem §0 mục 2 |
| Tài khoản cổng | **6 user / 6 khách hàng — chưa khách nào có 2 user.** Riêng "BVĐK Minh Đức" có **3 Contact cùng trỏ về MỘT user** (rác dữ liệu, dễ nhìn nhầm thành 3 tài khoản) |
| Giao nhiều đợt | **24 đơn đã có phiếu giao, 6 đơn (25%) giao nhiều hơn một đợt**, nhiều nhất **5 đợt/đơn** → YC-1/YC-4 không phải tình huống hiếm |
| Nhà cung cấp | **`Supplier` = 0 bản ghi**, `Item Supplier` = 0, `Item Default.default_supplier` = 0. Danh mục NCC chưa tồn tại |
| Danh mục nhóm | 33 `Item Group`, **cây phẳng hoàn toàn** (mọi nhóm đều là con trực tiếp của `All Item Groups`). Xem QĐ-HM-3 |

**Cần xác nhận (1 câu):** "Hi-medic" trong tài liệu đúng là Customer `Himedic`
đang có trên hệ thống, không phải một đơn vị mới cần tạo?

---

## 2. Hiện trạng từng yêu cầu — cái gì đã có, cái gì thiếu

| # | Yêu cầu | Đã có | Còn thiếu |
|---|---|---|---|
| 1 | Người đặt / người nhận / theo đợt / thời điểm nhận | `owner` trên mọi chứng từ; `dot_giao` trả về từng Delivery Note kèm `posting_date`, `status`, `lr_no`, `transporter_name`; biên bản kiểm hàng có `ngay_kiem`/`nguoi_kiem` | **Người nhận hàng THỰC TẾ** (không có field nào); **thời điểm KHÁCH nhận** (chỉ có ngày Miyano xuất); người đặt chưa hiện trên màn hình nào |
| 2 | Quy tắc mã đơn hàng dễ tra cứu | `naming_series` chuẩn ERPNext; `custom_so_po_khach` (số dự trù/PO của khách) | Mã theo cấu trúc `[Nhóm]-[Tên ngắn]-[YYMMDD]-[NN]`; **không có field "tên viết ngắn" trên Item**; `Item Group` có 33 nhóm nhưng chưa gom theo mục đích này |
| 3 | Phân loại vật tư + gắn nhà cung cấp | `Item.item_group` (33 nhóm); bảng `Item Supplier` của ERPNext có sẵn | **Cả `Supplier` LẪN `Item Supplier` đều 0 bản ghi** — không có NCC nào để gắn. Danh mục nhóm cần rà lại trước (QĐ-HM-3); chưa có báo cáo "mặt hàng ↔ nhà cung cấp" |
| 4 | Thông báo khi không giao đủ | `custom_loai_hen_giao` / `custom_ngay_hen_giao` / `custom_ly_do_hen_giao` / `custom_hen_giao_luc`; `hen_giao_lai()`; banner cam trên màn đơn hàng; `xu_ly_thieu` trên biên bản kiểm hàng; `delivered_qty` đã có trong payload từng dòng hàng | **Chiều khởi phát**: hôm nay thiếu hàng được phát hiện khi KHÁCH lập biên bản. Yêu cầu này muốn MIYANO chủ động khai báo trước. Ngoài ra "SL còn thiếu" chưa hiện thành một con số, và `dot_giao` không mang trạng thái các đợt SẮP tới. *(Việc "gửi cho mọi user" đã có sẵn — xem §0 mục 1)* |
| 5 | Nhiều user + truy vết | Nhiều user cho một khách **được code hỗ trợ** (mỗi user một Contact → Dynamic Link tới cùng Customer) nhưng **chưa từng chạy thật**; `owner`/`modified_by` trên mọi chứng từ; `Version` đang tích luỹ | Màn hình đọc vết (và `Version` **không cho role Customer đọc** — chỉ System Manager/Administrator); `Version` **không ghi sự kiện TẠO**; `nguoi_kiem` là `Data` options=Email và hiện **bằng đúng `owner` ở cả 7 biên bản** → đang là bản sao của tài khoản đăng nhập, không phải tên người kiểm; **không có chiều "bộ phận/khoa"** ở phía user |

---

## 2b. Ba lỗi ĐANG CHẠY (phát hiện khi rà YC-1)

Không phải bẫy tương lai — đã tái hiện bằng cách gọi thẳng
`portal_order_track` **dưới đúng tài khoản của khách**, trên dữ liệu đang có:

```
# đăng nhập bvminhduc@demo.miyano — đơn SAL-ORD-2026-00132
Đợt 1: MAT-DN-2026-00031   40.0%
Đợt 2: MAT-DN-2026-00032   50.0%
Đợt 3: MAT-DN-2026-00033   10.0%
Đợt 4: MAT-DN-2026-00034  -10.0%   ← phiếu TRẢ HÀNG (is_return=1)
Đợt 5: MAT-DN-2026-00035   10.0%

# đăng nhập bvbm@demo.miyano — đơn SAL-ORD-2026-00056
Đợt 1: MAT-DN-2026-00020  100.0%
Đợt 2: MAT-DN-2026-00022 -100.0%   ← phiếu TRẢ HÀNG, và còn đang NHÁP
```

**Lỗi 1 — phiếu trả hàng bị đếm thành một đợt giao.** Vòng lặp dựng
`deliveries`/`dot_giao` lọc `{"against_sales_order": so.name, "docstatus":
["<", 2]}`, **không loại `is_return = 1`**. Phiếu trả mang cùng
`against_sales_order` (đã kiểm: cả 3 phiếu trả trên site đều có), và dòng hàng
của nó mang `qty` **âm** → phần trăm âm. Khách thấy "Đợt 4, −10%".

**Lỗi 2 — phiếu NHÁP hiện ra với khách.** `docstatus < 2` cho cả `0` (nháp) đi
qua. `MAT-DN-2026-00022` đang là nháp mà vẫn hiện thành "Đợt 2" trên màn hình
Bạch Mai. Lỗi này **không giới hạn ở phiếu trả**: bất kỳ phiếu giao nháp nào
của đơn cũng hiện ra như một đợt đã giao. Không ai chọn hành vi này — không có
dòng nào trong `30_API_Spec` §1.2 khẳng định nó, và **không test nào** khẳng
định nó: mọi Delivery Note trong `test_e3_giao_dien.py`, `test_e7_hddt_nhap.py`
và `test_e9_kiem_hang.py` đều đã `submit()` trước khi gọi `portal_order_track`.
Chỗ duy nhất dùng phiếu nháp (`test_e9_kiem_hang.py:286`) khẳng định **ngược
lại**: phiếu giao còn nháp thì khách **không kiểm hàng được**.

**Lỗi 3 — SỐ ĐỢT SAI, và đã ghi xuống cơ sở dữ liệu.** Nặng hơn hai lỗi trên vì
nó không chỉ hiển thị sai: `delivery_hook._so_dot()` đếm
`len(danh_sach)` trên **mọi** Delivery Note `docstatus = 1` của đơn, **không
loại `is_return`** — rồi ghi con số đó vào `Customer Stock Receipt.so_dot`,
là phiếu nhập kho mà khách in và ký. Theo chính docstring của hàm, `so_dot` là
**ảnh chụp, không tính lại** → số sai nằm lại vĩnh viễn.

Đã đo trên dữ liệu đang có:

```
SAL-ORD-2026-00132 → phiếu nhập mang so_dot = 1, 2, 3, 5   (KHÔNG có đợt 4)
   vì MAT-DN-2026-00034 (trả hàng, đã ghi sổ) chiếm mất số 4
SAL-ORD-2026-00128 → phiếu nhập mang so_dot = 1, 3         (KHÔNG có đợt 2)
   vì MAT-DN-2026-00028 (trả hàng, đã ghi sổ) chiếm mất số 2
```

**Quy ước đúng đã có sẵn trong chính app này:** `portal_hen_giao._da_giao_sau()`
lọc `dn.docstatus = 1 and ifnull(dn.is_return, 0) = 0`, kèm chú thích giải
thích đúng lý do. `_so_dot()` chỉ thiếu vế thứ hai. Sửa là **chép quy ước đã
có**, không phải phát minh quy ước mới.

**Vì sao phải xử trước YC-1:** YC-1 gắn "người nhận thực tế + thời điểm nhận"
vào **từng đợt**. Xây trên một danh sách đợt đang lẫn phiếu trả và phiếu nháp
thì sẽ có ô "người nhận hàng" nằm trên một phiếu trả hàng.

**Sửa ở HAI chỗ** (đã grep toàn bộ `against_sales_order` trong app để chắc
không còn chỗ thứ ba):

| Chỗ | Lỗi | Ghi chú |
|---|---|---|
| `api/portal.py:1257` — bộ lọc `dn_names` | 1 + 2 | `deliveries` và `dot_giao` dựng từ chung một vòng lặp nên một sửa đổi chữa cả hai key |
| `kho/delivery_hook.py:369` — truy vấn trong `_so_dot()` | 3 | Chỉ thêm vế `is_return`; `docstatus = 1` đã đúng sẵn |

**Lỗi 2 và 3 sửa dứt điểm, KHÔNG cần ai quyết** — không có cách đọc nào khiến
một phiếu nháp hay một phiếu trả hàng là "đợt giao". **Chỉ lỗi 1 cần
QĐ-HM-5**, vì nó là câu hỏi "khách có nên nhìn thấy phiếu trả hàng ở đâu đó
không". Đừng gói cả ba sau một câu hỏi sản phẩm.

**Còn một việc riêng:** lỗi 3 đã ghi số sai vào các phiếu nhập đang tồn tại.
Sửa code không chữa dữ liệu cũ. Cần chốt riêng: viết patch tính lại `so_dot`,
hay để nguyên và ghi chú? (Docstring nói rõ `so_dot` vốn đã không tự tính lại
khi một phiếu giữa chừng bị huỷ — tức là dữ liệu cũ vốn đã có sai số biết
trước.)

---

## 3. Quyết định cần chốt

### QĐ-HM-1 — Các user của Hi-medic có phải NGĂN CÁCH nhau không? (quan trọng nhất)

Tài liệu yêu cầu *truy vết* ("ai tạo đơn", "ai kiểm nhập"), **không** yêu cầu
*phân quyền*. Nhưng nó cũng nói mỗi phòng một người, mỗi người một tài khoản.
Hai cách hiểu chênh nhau rất xa về khối lượng:

* **(A) Chỉ truy vết — ĐỀ XUẤT.** Mọi user của Hi-medic thấy toàn bộ đơn của
  Hi-medic, nhưng mỗi thao tác ghi rõ ai làm. Nền tảng đã sẵn: `owner` có trên
  mọi bản ghi, `Version` đã tích luỹ 95 bản ghi. Việc còn lại là **đưa ra màn
  hình** thứ đã ghi — thêm cột "Người đặt", một màn "Lịch sử thao tác".
  Bệnh viện thường muốn nhìn xuyên phòng (Phòng Vật tư/Kế toán phải thấy hết),
  nên đây gần như chắc chắn là ý thật.

* **(B) Ngăn cách theo phòng.** Phòng Huyết học chỉ thấy đơn của Huyết học.
  Việc này phải thêm một chiều "bộ phận" vào phía user rồi xuyên qua
  `get_allowed_customers()`, mọi hook `permission_query_conditions`, và mọi
  endpoint đang suy phạm vi từ phiên đăng nhập — tức là chạm vào đúng đường
  biên an ninh của cả cổng. Lớn hơn (A) khoảng một bậc, và có rủi ro: một đơn
  bị "mất" khỏi mắt người thay thế khi đồng nghiệp nghỉ phép.

**Nếu chọn (B) thì phải trả lời tiếp:** ai nhìn được xuyên phòng (Admin của
bệnh viện? Kế toán?), và đơn của người đã nghỉ việc thuộc về ai?

> Hiện Hi-medic mới có **1 user**. Có thể chốt (A) làm ngay, và để (B) lại khi
> nào họ thật sự cấp đủ tài khoản cho từng phòng — lúc đó nhu cầu sẽ tự rõ.

### QĐ-HM-2 — Mã đơn hàng: đổi tên chứng từ, hay thêm mã tra cứu?

Cấu trúc Hi-medic muốn: `Huyethoc-Hematology-260817-01`.

**Đề xuất: KHÔNG đổi tên chứng từ, mà thêm một trường "Mã tra cứu" riêng.**
Lý do cụ thể, không phải e dè chung:

1. 102 đơn đang mang `SAL-ORD-*`. Đổi `autoname` chỉ áp cho đơn MỚI → hai định
   dạng sống song song vĩnh viễn. Còn đổi tên đơn cũ thì phải sửa theo mọi chỗ
   đang trỏ tới nó: `against_sales_order` trên phiếu giao, `custom_yeu_cau_goc`,
   biên bản kiểm hàng (`sales_order` là Data), link trong Notification Log đã
   gửi, và mọi PDF đã in ra cho khách — bản in cũ sẽ không tra được nữa.
2. **"Tên viết ngắn của một sản phẩm trong đơn" hiện không tồn tại.** Không có
   field nào trên Item mang nó. Phải thêm field + nhập tay cho từng mặt hàng.
3. Còn phải chốt: đơn có nhiều mặt hàng thì lấy tên NÀO? (giá trị lớn nhất?
   dòng đầu?) — một quy tắc tuỳ ý, và nếu người dùng sửa dòng hàng sau khi đơn
   đã có mã thì mã trở nên sai mà không ai biết.
4. "Nhóm sản phẩm" sẽ phải lấy từ `Item Group` — 33 nhóm hiện có chưa từng
   được gom theo mục đích này (xem QĐ-HM-3).

Cách thêm "Mã tra cứu" (`custom_ma_tra_cuu`, unique, sinh tự động khi tạo đơn,
có index, hiện ở mọi nơi đơn xuất hiện: danh sách/chi tiết trên cổng, mẫu in,
thông báo, và ô tìm kiếm) **đáp ứng đúng cái Hi-medic cần** — một mã dễ đọc để
tra cứu — mà không nhận lấy một cuộc di trú tên chứng từ. Tên kỹ thuật
`SAL-ORD-*` vẫn còn để hệ thống tự tham chiếu.

*Nếu chủ đầu tư vẫn muốn đổi hẳn tên chứng từ:* làm được, nhưng phải chấp nhận
mốc "từ ngày X trở đi", không hồi tố, và cần một buổi rà soát mọi mẫu in.

### QĐ-HM-3 — Nhóm sản phẩm dùng `Item Group` sẵn có hay lập nhóm riêng?

Đây **không còn là phán đoán** — đã đếm trên 33 nhóm / 164 mặt hàng, và danh
mục hiện tại **không dùng được** làm tiền tố mã đơn:

1. **Cây phẳng hoàn toàn.** Cả 33 nhóm đều là con trực tiếp của
   `All Item Groups`, không có cấp nào. Không có khái niệm "nhóm sản phẩm lớn".
2. **Nhóm to nhất là một cái tên vô nghĩa.** `Sản phẩm` giữ **35/164 mặt hàng
   (21%)** → cứ 5 đơn thì 1 đơn mang tiền tố `Sanpham-`, không tra cứu được gì.
3. **Một khái niệm bị tách đôi bởi dấu tiếng Việt.** Tồn tại song song
   `Hóa chất sinh phẩm` (10 mặt hàng) và `Hoá chất xét nghiệm` — khác nhau ở
   đúng chữ `ó`/`oá`. Hai nhóm này sẽ sinh **hai tiền tố khác nhau cho cùng
   một loại hàng**, đúng thứ mà YC-2 tồn tại để chống.
4. **Sáu nhóm chồng lấn nhau:** `Vật tư y tế`, `Tất cả vật tư`, `Vật tư tiêu
   hao`, `Vật tư phụ trợ`, `Vật tư thay thế`, `Vật tư bảo hộ` — không có quy
   tắc nào nói mặt hàng nào thuộc nhóm nào.
5. **Rác còn nguyên:** `Consumable`, `Sub Assemblies`, `Services`,
   `Raw Material`, `Products` (nhóm mặc định của ERPNext, chưa dọn) và
   `Phụ kiện bảo hộ (TEST RP01)` (nhóm dựng để test).

→ **Phải rà và gom lại danh mục nhóm TRƯỚC khi làm YC-2.** Đây là việc dữ liệu,
cần Miyano cử người chốt cây nhóm — không phải việc code, và không code nào
chữa được điểm 2 và 3.

### QĐ-HM-4 — "Người nhận hàng thực tế" là chuỗi tên hay một bản ghi?

Tài liệu nói rõ: căn cứ **họ tên + chữ ký trên biên bản giao nhận**, hoặc thông
tin người nhận trên chứng từ của đơn vị chuyển phát. Đó là một cái tên trên
giấy, không phải một tài khoản trong hệ thống → **đề xuất lưu dạng Data (họ
tên) + một Datetime (thời điểm nhận)**, kèm ô ghi chú nguồn căn cứ. Cố ép nó
thành Link tới User/Contact sẽ chặn đúng trường hợp phổ biến nhất: người nhận
là hộ lý, bảo vệ, hoặc nhân viên chuyển phát — những người không có tài khoản.

**Có một chỗ đang sai sẵn theo đúng kiểu này:** `nguoi_kiem` trên biên bản kiểm
hàng là `Data` với `options = Email`, và ở **cả 7 biên bản đang có, giá trị của
nó bằng đúng `owner`** — tức nó đang chứa *email đăng nhập*, không phải *tên
người kiểm*. Người đọc trên Desk thấy một dòng ghi "Người kiểm" và tưởng đang
đọc tên một con người, trong khi đó là một tài khoản. Đây chính là cái nhập
nhằng mà tài liệu Hi-medic yêu cầu tách bạch, đã hiện diện sẵn trong hệ thống.

### QĐ-HM-5 — Phiếu trả hàng hiện thế nào trên màn hình khách? (mới, do §2b)

Lỗi 2 (phiếu nháp) sửa dứt điểm, không cần hỏi. Lỗi 1 thì cần chọn:

* **(A) Ẩn hẳn khỏi danh sách đợt giao — ĐỀ XUẤT.** "Đợt giao" đếm đúng số lần
  Miyano giao hàng. Đơn giản nhất, và trả lại đúng nghĩa cho con số.
* **(B) Vẫn hiện, nhưng NGOÀI cách đánh số đợt**, gắn nhãn "Trả hàng" và không
  cộng vào phần trăm. Minh bạch hơn với khách đã từng trả hàng, nhưng phải sửa
  thêm giao diện và phải chốt phần trăm hiển thị thế nào.

Chọn (A) thì hai đơn nêu ở §2b sẽ mất một dòng trên màn hình khách — cần biết
trước, không phải phát hiện sau khi lên bản.

---

## 4. Hướng giải quyết từng yêu cầu

### YC-1 — Thông tin đặt hàng & giao nhận của từng đơn

**Việc phải làm:**

1. **Người đặt hàng** — không thêm field. `owner` của Sales Order đã là người
   bấm đặt trên cổng (đã kiểm: 2 đơn của Hi-medic đều `owner = himedic@...`).
   Việc còn lại là *hiện* nó: thêm "Người đặt" vào màn chi tiết đơn (cổng
   khách) và vào Desk.
2. **Người nhận thực tế + thời điểm nhận, THEO TỪNG ĐỢT** — thêm custom field
   trên **Delivery Note** (mỗi đợt giao là một Delivery Note, nên "theo đợt" tự
   có, không cần cấu trúc mới):
   * `custom_nguoi_nhan_thuc_te` (Data) — họ tên trên biên bản;
   * `custom_thoi_diem_nhan` (Datetime) — thời điểm khách nhận thật;
   * `custom_can_cu_nhan` (Select: `Biên bản giao nhận` / `Chuyển phát nhanh`)
     + `custom_so_van_don` (Data, dùng khi qua chuyển phát).
   Nhân viên giao nhận Miyano cập nhật trên Desk sau khi có chứng từ.
3. **Đưa ra cổng khách** — bổ sung 4 khoá trên vào payload `dot_giao` của
   `portal_order_track`, hiện thành một dòng trong thẻ mỗi đợt: *"Đợt 2 —
   nhận 15/08/2026 14:30 — người nhận: Nguyễn Thị B (biên bản giao nhận)"*.
   Đợt chưa cập nhật thì hiện "chưa ghi nhận", không để trống im lặng.

**Điều kiện tiên quyết:** phải sửa xong hai lỗi ở **§2b** trước. Cách đánh
"đợt 1, đợt 2" hiện đang tính cả phiếu trả hàng và phiếu nháp — gắn "người nhận
thực tế" lên danh sách đó sẽ tạo ra một ô "người nhận hàng" trên một phiếu trả.
Đây đúng cái bẫy đã cắn ở tính năng hẹn giao (`_da_giao_sau`), lần này đã ở
trong sản phẩm chứ không còn là rủi ro.

**Không cần làm:** một doctype "Biên bản giao nhận" mới. Delivery Note đã là
chứng từ đó; thêm một lớp nữa là hai nguồn sự thật cho cùng một lần giao.

### YC-2 — Quy tắc mã đơn hàng

Theo QĐ-HM-2, hướng đề xuất:

1. Thêm `Item.custom_ten_ngan` (Data) — tên viết ngắn, nhập cho các mặt hàng
   chủ lực trước, không bắt buộc toàn danh mục.
2. Thêm `Sales Order.custom_ma_tra_cuu` (Data, **unique**, có index, read-only)
   sinh tự động khi tạo đơn theo `[Nhóm]-[Tên ngắn]-[YYMMDD]-[NN]`:
   * Nhóm: `Item Group` của dòng hàng có **giá trị lớn nhất** trong đơn, viết
     không dấu, bỏ khoảng trắng;
   * Tên ngắn: `custom_ten_ngan` của chính dòng đó; nếu trống → dùng `item_code`;
   * `YYMMDD`: `transaction_date`;
   * `NN`: số thứ tự trong ngày, **2 chữ số, tràn sang 3 khi vượt 99** (không
     quay vòng về 01 — trùng mã còn tệ hơn mã dài).
     **Cần Hi-medic chốt phạm vi đếm:** ví dụ `Huyethoc-Hematology-260817-01`
     đọc ra hai nghĩa — (a) đơn thứ 01 **của riêng cặp nhóm+tên ngắn đó** trong
     ngày, hay (b) đơn thứ 01 **của toàn hệ thống** trong ngày. Đề xuất (a):
     nó khớp cách đọc tự nhiên của ví dụ, giữ `NN` luôn nhỏ, và làm cho mã tự
     nói lên "lần đặt huyết học thứ mấy hôm nay" — thứ Hi-medic thật sự tra.
3. Mã **không đổi khi đơn được sửa** — sinh một lần lúc tạo và giữ nguyên. Một
   mã tra cứu tự thay đổi dưới tay người dùng là thứ không tra cứu được.
4. Hiện `custom_ma_tra_cuu` ở: danh sách đơn + chi tiết đơn trên cổng, mẫu in
   xác nhận đơn/báo giá, nội dung thông báo, và cho phép tìm theo nó.
5. **Nhãn phải khác "Mã tra cứu" trơn.** Delivery Note **đã có** một field
   `fast_key_search` mang đúng nhãn *"Mã tra cứu"* — của module hoá đơn điện tử
   Fast, không phải của app này. Hai thứ khác nhau cùng một tên trên hai chứng
   từ liền kề là một chỗ để hiểu sai. Đề xuất nhãn **"Mã đơn hàng (tra cứu)"**.

**Cần chốt thêm:** nếu đơn không có mặt hàng nào (đơn toàn dòng "đặt ngoài,
chưa có mã") thì nhóm/tên ngắn lấy ở đâu? Đề xuất: dùng `KHAC-<tên hàng đầu>`.

### YC-3 — Phân loại hoá chất/vật tư và gắn nhà cung cấp

**Vẫn là mục rẻ nhất trong 5 mục và nên làm trước** — chức năng đã có sẵn trong
ERPNext, không cần doctype mới. Nhưng khối lượng dữ liệu lớn hơn bản 17/08 nói:
**`Supplier` đang có 0 bản ghi**, tức là chưa có nhà cung cấp nào để mà gắn.

1. **Rà soát `Item Group`** (QĐ-HM-3) — việc dữ liệu, cần người của Miyano.
   Đọc kỹ 5 điểm ở QĐ-HM-3: danh mục hiện tại không dùng lại nguyên trạng được.
2. **Lập danh mục `Supplier`** — bước này bản 17/08 bỏ sót. Chưa có NCC nào.
3. **Nhập bảng `Item Supplier`** (đang 0 dòng): mỗi Item gắn một hoặc nhiều
   Supplier + mã hàng của NCC.
4. **Thêm 1 báo cáo Desk** "Mặt hàng theo nhóm và nhà cung cấp": lọc theo nhóm/
   NCC, cho ra mặt hàng ↔ nhóm ↔ NCC ↔ mã của NCC ↔ đã nhập lần cuối khi nào.
   Cùng khuôn 10 báo cáo kho hiện có (Script Report, `is_standard=Yes`, khoá
   theo role nhân viên).
5. **Nếu Hi-medic muốn tự xem** nguồn cung của vật tư trong kho họ: module kho
   khách hàng **đã có** doctype `Customer Supplier` và báo cáo "Tỷ trọng nguồn
   cung". Cần phân biệt rõ hai thứ khác nhau: NCC **của Miyano** (mục này) và
   NCC **của bệnh viện** (đã có). Đừng trộn.

### YC-4 — Thông báo khi không thể giao đủ trong một lần

Phần lớn cơ chế **đã có** (xem §2). Việc còn lại:

1. **Đổi chiều khởi phát.** Thêm nút trên Desk cho nhân viên Miyano: *"Báo giao
   thiếu"* trên Sales Order / Delivery Note, mở đúng cơ chế `hen_giao_lai()`
   đang dùng, nhưng cho phép khai báo **trước/ngay khi giao** thay vì chờ khách
   lập biên bản. Không viết cơ chế thứ hai — hai đường thông báo hẹn giao sẽ
   lệch nhau.
2. **Hiện "SL còn thiếu" thành con số.** `delivered_qty` đã có trong payload;
   thêm `con_thieu = qty - delivered_qty` cho từng dòng và hiện trên màn đơn.
   Tính ở server, không để client tự trừ — hai chỗ tính sẽ lệch khi có phiếu trả.
3. **Trạng thái các đợt sắp tới.** Mỗi thẻ đợt trên cổng hiện thêm: đợt này
   giao gì / còn nợ gì / hẹn ngày nào / lý do. Nguồn dữ liệu đã đủ
   (`custom_ngay_hen_giao`, `custom_ly_do_hen_giao`, `custom_loai_hen_giao`).
4. ~~**Thông báo cho khách** — phải đảm bảo mọi user của Hi-medic nhận được,
   không chỉ user tạo đơn.~~ **ĐÃ CÓ SẴN (kiểm 18/08).** `bao_hen_giao_lai()`
   gọi `_portal_users_cua_khach()`, hàm này trả **mọi User còn `enabled`** gắn
   với Customer qua Contact/Dynamic Link, và vòng gửi đã chống trùng theo
   (chủ đề + người nhận). Không có việc phải làm. Dùng lại nguyên cơ chế này.

### YC-5 — Quản lý User và truy vết

Theo QĐ-HM-1 phương án (A):

1. **Cấp tài khoản** — không cần code, nhưng **cần một test trước khi hứa**.
   Mỗi người một User + một Contact có Dynamic Link tới Customer `Himedic`.
   Đường code hỗ trợ việc này, **nhưng chưa khách nào trên hệ thống có 2 user**
   (6 tài khoản / 6 khách) → chưa từng chạy thật. Việc đầu tiên của YC-5 là
   dựng một test có **2 user trên cùng một Customer** và khẳng định: cả hai đọc
   được cùng bộ đơn, cả hai nhận được cùng thông báo, và không ai thấy đơn của
   khách khác.
   *Cảnh báo vận hành (2 việc dọn dữ liệu):* Contact `Himedic-Contact` **không
   gắn user** — dễ tưởng là một tài khoản; và "BVĐK Minh Đức" có **3 Contact
   cùng trỏ về một user** — `_portal_users_cua_khach()` khử trùng nên không
   sinh lỗi, nhưng màn hình quản trị sẽ đếm nhầm số người dùng.
2. **Sửa `nguoi_kiem` thành có thể truy vết.** Trường này đang là Data (chuỗi
   tự do). Giữ nguyên field (để ghi tên người kiểm thực tế) nhưng **căn cứ truy
   vết phải là `owner` của biên bản** — và phải hiện `owner` trên Desk, chứ
   không đọc `nguoi_kiem` như thể nó là user.
3. **Màn "Lịch sử thao tác" của đơn hàng — nhiều việc hơn bản 17/08 nói.**
   Ba điều đo được ngày 18/08 đổi hình dung về mục này:

   * **`Version` KHÔNG ghi sự kiện tạo.** Nó chỉ ghi thay đổi *sau* khi bản ghi
     đã tồn tại. Hành vi quan trọng nhất — "khách bấm đặt đơn lúc nào" — không
     nằm ở đó. Dòng thời gian phải **ghép hai nguồn**: `owner`+`creation` của
     từng chứng từ (sự kiện tạo) VỚI `Version` (sự kiện sửa). Có thêm
     `Comment` (388) và `Activity Log` (937) nếu cần chi tiết hơn.
   * **Phần lớn `Version` hiện có không phải hành vi người dùng.** 223/279 là
     của `Administrator`; riêng Sales Order, trường bị đổi nhiều nhất là
     `workflow_state` (74 lần), `status`/`docstatus` (29). Màn hình phải **lọc
     bỏ nhiễu kỹ thuật**, nếu không nó sẽ là một danh sách "docstatus: 0 → 1"
     mà không ai đọc.
   * **`Version` không cho role `Customer` đọc** (DocPerm chỉ có System Manager
     + Administrator). Nếu Hi-medic được xem lịch sử trên cổng thì phải qua một
     endpoint whitelist tự giới hạn phạm vi theo Customer, **không** mở quyền
     doctype.

   **Và phải lọc TRẮNG danh sách trường trước khi trả cho khách.** Đã đếm toàn
   bộ 95 `Version` của Sales Order: trong `row_changed` có **`gross_profit`
   (22 lần)**, cùng `company_total_stock`, `projected_qty`,
   `amount_eligible_for_commission`. Trả nguyên diff cho khách là **lộ lãi gộp
   từng dòng hàng và tồn kho của Miyano**. Danh sách trường được phép hiện phải
   khai tường minh (allow-list), không phải chặn theo danh sách cấm.
4. **Hiện "ai làm gì" ngay tại chỗ**, không chỉ trong màn lịch sử: người đặt
   trên đơn, người lập biên bản trên biên bản, người nhận thực tế trên từng đợt
   (YC-1), người cập nhật gần nhất.
5. **Phân biệt hai khái niệm** đúng như tài liệu nhấn mạnh: "User thao tác trên
   hệ thống" (tự động, `owner`/`modified_by`, không sửa được) ≠ "Người nhận hàng
   thực tế" (nhập tay từ chứng từ giấy, sửa được, có ghi nguồn căn cứ). Hai chỗ
   khác nhau trên màn hình, nhãn khác nhau, không bao giờ gộp vào một ô.

---

## 5. Thứ tự đề nghị làm

**Thứ tự này không còn là phán đoán ở hai chỗ.** (a) Bước 0 đứng trước YC-1 vì
YC-1 xây trực tiếp lên danh sách đợt giao đang lỗi (§2b). (b) YC-2 đứng cuối vì
danh mục nhóm hiện tại **sinh ra mã sai**, không phải vì "để dành làm sau": 21%
mặt hàng nằm trong nhóm tên `Sản phẩm`, và `Hóa chất sinh phẩm` / `Hoá chất xét
nghiệm` là hai nhóm khác nhau chỉ vì một dấu tiếng Việt (QĐ-HM-3). Sinh mã trên
danh mục đó là sinh ra đúng thứ hỗn loạn mà YC-2 tồn tại để dẹp.

| Bước | Nội dung | Phụ thuộc | Ghi chú |
|---|---|---|---|
| **0a** | **Sửa lỗi 2 + 3 ở §2b** (phiếu nháp lọt ra cổng; số đợt đếm cả phiếu trả) | **không chặn gì — làm được ngay** | **Việc sửa lỗi, không phải tính năng mới.** Hai vế `WHERE`, chép quy ước đã có ở `_da_giao_sau()`. Lỗi 3 ghi số sai xuống DB |
| **0b** | **Sửa lỗi 1** (phiếu trả hàng hiện thành đợt giao, %% âm) | QĐ-HM-5 | Chặn YC-1 |
| 1 | YC-3 (nhóm + NCC): rà `Item Group`, **lập danh mục `Supplier`**, nhập `Item Supplier`, 1 báo cáo | cần người Miyano chốt cây nhóm | Rẻ nhất về code, nhưng **nặng về dữ liệu** — `Supplier` đang 0 bản ghi. YC-2 phụ thuộc kết quả rà nhóm |
| 2 | YC-1 (người nhận thực tế + thời điểm nhận theo đợt) | **bước 0**, QĐ-HM-4 | Giá trị thấy ngay: 25% đơn có phiếu giao là giao nhiều đợt (6/24, nhiều nhất 5 đợt) |
| 3 | YC-4 (báo giao thiếu chủ động + SL còn thiếu) | — | Dùng lại cơ chế hẹn giao đã có. Phần "gửi cho mọi user" **đã xong sẵn** |
| 4 | YC-5 (truy vết + màn lịch sử) | QĐ-HM-1 | Lớn hơn bản 17/08 ước: ghép 2 nguồn sự kiện + allow-list trường + endpoint riêng cho khách |
| 5 | YC-2 (mã tra cứu đơn hàng) | QĐ-HM-2, QĐ-HM-3, bước 1 | Làm sau cùng vì phụ thuộc danh mục nhóm đã dọn |

---

## 6. Những gì bản đề xuất này CỐ Ý không làm

1. **Không đổi tên 102 đơn hàng đang có.** Xem QĐ-HM-2 — cái giá là mọi PDF đã
   phát cho khách trở nên không tra được.
2. **Không thêm doctype "Biên bản giao nhận".** Delivery Note đã là chứng từ đó.
3. **Không ngăn cách user theo khoa/phòng** chừng nào chưa có QĐ-HM-1 phương án
   (B) — nó chạm vào đường biên an ninh của cả cổng khách.
4. **Không viết cơ chế thông báo giao thiếu thứ hai.** Mở rộng
   `hen_giao_lai()`, không dựng song song.
5. **Không trộn NCC của Miyano với NCC của bệnh viện.** Hai danh mục, hai chủ
   sở hữu dữ liệu, hai màn hình.
6. **Không suy "người nhận hàng" từ user đăng nhập.** Tài liệu nói rõ hai thông
   tin này có thể là hai người khác nhau. `nguoi_kiem` trên biên bản kiểm hàng
   đang mắc đúng lỗi đó (§QĐ-HM-4) — đừng nhân bản nó sang chỗ mới.
7. **Không trả nguyên `Version` diff cho khách.** Có `gross_profit` và tồn kho
   Miyano trong đó (§YC-5.3). Allow-list trường, không blocklist.
8. **Không hứa "nhiều user cho một khách" trước khi có test.** Đường code hỗ
   trợ nhưng chưa khách nào chạy thật (§0 mục 4).

---

## 7. Câu hỏi cần Hi-medic / chủ đầu tư trả lời

Gom lại ở một chỗ để không phải đọc lại cả tài liệu:

| # | Câu hỏi | Chặn việc gì |
|---|---|---|
| 1 | "Hi-medic" đúng là Customer `Himedic` đang có, không phải đơn vị mới? | mọi thứ |
| 2 | **QĐ-HM-1** — các user của Hi-medic chỉ cần *truy vết* (A), hay phải *ngăn cách* theo khoa/phòng (B)? | YC-5 |
| 3 | **QĐ-HM-2** — thêm "Mã đơn hàng (tra cứu)" bên cạnh `SAL-ORD-*` (đề xuất), hay đổi hẳn tên chứng từ? | YC-2 |
| 4 | **QĐ-HM-3** — ai bên Miyano chốt lại cây `Item Group`? | YC-2, YC-3 |
| 5 | **QĐ-HM-4** — "người nhận thực tế" lưu dạng họ tên tự do + thời điểm nhận (đề xuất)? | YC-1 |
| 6 | **QĐ-HM-5** — phiếu trả hàng: ẩn khỏi danh sách đợt (đề xuất) hay hiện có nhãn riêng? | bước 0 |
| 7 | `NN` trong mã đơn đếm theo cặp nhóm+tên ngắn trong ngày (đề xuất), hay theo toàn hệ thống trong ngày? | YC-2 |
| 8 | Đơn không có mặt hàng trong danh mục (toàn dòng "đặt ngoài") thì mã lấy nhóm/tên ngắn ở đâu? | YC-2 |
