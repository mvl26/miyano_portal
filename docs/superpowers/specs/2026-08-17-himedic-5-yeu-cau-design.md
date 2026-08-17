# Hướng giải quyết 5 yêu cầu cải tiến của Hi-medic

**Ngày:** 17/08/2026
**Nguồn:** tài liệu cải tiến do Hi-medic gửi (5 mục), có ghi chú "ý kiến của Thùy" ở mục 3.
**Trạng thái:** ĐỀ XUẤT — chưa viết code, chưa tạo custom field, chưa đụng schema.
Cần chủ đầu tư chốt các quyết định ở §3 trước khi làm.

Đánh số quyết định dùng tiền tố **QĐ-HM-** (không dùng "QĐ-n" trơn): trong bộ
tài liệu của dự án đã có hai dãy "QĐ" của hai văn bản khác nhau đang chọi số
nhau, thêm một dãy trơn nữa là thêm một chỗ để hiểu sai.

---

## 1. Bối cảnh đã kiểm chứng trên hệ thống

Đã đối chiếu trên site `erptest.local` (không phỏng đoán từ ký ức):

| Việc | Hiện trạng đo được |
|---|---|
| Khách hàng Hi-medic | Customer **`Himedic`** đã tồn tại, chưa disabled, có kho `KKH-00006` ("kho himedic") đang hoạt động |
| Tài khoản cổng | **1 user** duy nhất: `himedic@demo.miyano` (Contact `Himedic-Himedic`). Còn 1 Contact `Himedic-Contact` KHÔNG gắn user |
| Đơn hàng của Hi-medic | 2 đơn (`SAL-ORD-2026-00016`, `SAL-ORD-2026-00004`), cả hai `owner = himedic@demo.miyano` |
| Tổng đơn trên site | 102 Sales Order, đánh số theo `naming_series` (`SAL-ORD-YYYY-NNNNN`) |
| Nhật ký sửa đổi | `track_changes = 1` trên Sales Order / Delivery Note / Portal Delivery Inspection → **đã có 95 bản ghi `Version` cho Sales Order**, 30 cho Delivery Note. Tức là hệ thống ĐANG ghi vết, chỉ chưa có màn hình đọc nó |

**Cần xác nhận (1 câu):** "Hi-medic" trong tài liệu đúng là Customer `Himedic`
đang có trên hệ thống, không phải một đơn vị mới cần tạo?

---

## 2. Hiện trạng từng yêu cầu — cái gì đã có, cái gì thiếu

| # | Yêu cầu | Đã có | Còn thiếu |
|---|---|---|---|
| 1 | Người đặt / người nhận / theo đợt / thời điểm nhận | `owner` trên mọi chứng từ; `dot_giao` trả về từng Delivery Note kèm `posting_date`, `status`, `lr_no`, `transporter_name`; biên bản kiểm hàng có `ngay_kiem`/`nguoi_kiem` | **Người nhận hàng THỰC TẾ** (không có field nào); **thời điểm KHÁCH nhận** (chỉ có ngày Miyano xuất); người đặt chưa hiện trên màn hình nào |
| 2 | Quy tắc mã đơn hàng dễ tra cứu | `naming_series` chuẩn ERPNext; `custom_so_po_khach` (số dự trù/PO của khách) | Mã theo cấu trúc `[Nhóm]-[Tên ngắn]-[YYMMDD]-[NN]`; **không có field "tên viết ngắn" trên Item**; `Item Group` có 33 nhóm nhưng chưa gom theo mục đích này |
| 3 | Phân loại vật tư + gắn nhà cung cấp | `Item.item_group` (33 nhóm); bảng `Item Supplier` của ERPNext có sẵn | **`Item Supplier` đang RỖNG (0 dòng)** — chức năng có, dữ liệu chưa nhập; chưa có báo cáo "mặt hàng ↔ nhà cung cấp" |
| 4 | Thông báo khi không giao đủ | `custom_loai_hen_giao` / `custom_ngay_hen_giao` / `custom_ly_do_hen_giao` / `custom_hen_giao_luc`; `hen_giao_lai()`; banner cam trên màn đơn hàng; `xu_ly_thieu` trên biên bản kiểm hàng; `delivered_qty` đã có trong payload từng dòng hàng | **Chiều khởi phát**: hôm nay thiếu hàng được phát hiện khi KHÁCH lập biên bản. Yêu cầu này muốn MIYANO chủ động khai báo trước. Ngoài ra "SL còn thiếu" chưa hiện thành một con số, và `dot_giao` không mang trạng thái các đợt SẮP tới |
| 5 | Nhiều user + truy vết | Nhiều user cho một khách **đã chạy được sẵn** (mỗi user một Contact → Dynamic Link tới cùng Customer); `owner`/`modified_by` trên mọi chứng từ; `Version` đang tích luỹ | Màn hình cho Admin đọc vết; `nguoi_kiem` trên biên bản là **Data (chuỗi tự do)**, không phải Link tới User → không dùng làm căn cứ truy vết được; **không có chiều "bộ phận/khoa"** ở phía user |

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

`Item Group` đang có 33 nhóm nhưng phục vụ mục đích khác. Nếu mã đơn và báo cáo
phân loại đều dựa vào nó thì phải **rà soát và gom lại danh mục nhóm trước**
(việc dữ liệu, không phải việc code). Cần Miyano cử người chốt cây nhóm.

### QĐ-HM-4 — "Người nhận hàng thực tế" là chuỗi tên hay một bản ghi?

Tài liệu nói rõ: căn cứ **họ tên + chữ ký trên biên bản giao nhận**, hoặc thông
tin người nhận trên chứng từ của đơn vị chuyển phát. Đó là một cái tên trên
giấy, không phải một tài khoản trong hệ thống → **đề xuất lưu dạng Data (họ
tên) + một Datetime (thời điểm nhận)**, kèm ô ghi chú nguồn căn cứ. Cố ép nó
thành Link tới User/Contact sẽ chặn đúng trường hợp phổ biến nhất: người nhận
là hộ lý, bảo vệ, hoặc nhân viên chuyển phát — những người không có tài khoản.

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

**Lưu ý nghiệp vụ phải giữ đúng:** "đợt 1, đợt 2" đánh theo thứ tự
`posting_date` của các Delivery Note **đã ghi sổ** của đơn, và phải **loại phiếu
trả hàng** (`is_return = 1`) — phiếu trả mang cùng `against_sales_order` nên
nếu không loại, một lần trả hàng hỏng sẽ hiện thành "đợt 3" trên màn khách.
Đây đúng cái bẫy đã cắn ở tính năng hẹn giao (`_da_giao_sau`).

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
   * `NN`: số thứ tự trong ngày, đếm theo ngày đặt, **2 chữ số, tràn sang 3 khi
     vượt 99** (không quay vòng về 01 — trùng mã còn tệ hơn mã dài).
3. Mã **không đổi khi đơn được sửa** — sinh một lần lúc tạo và giữ nguyên. Một
   mã tra cứu tự thay đổi dưới tay người dùng là thứ không tra cứu được.
4. Hiện `custom_ma_tra_cuu` ở: danh sách đơn + chi tiết đơn trên cổng, mẫu in
   xác nhận đơn/báo giá, nội dung thông báo, và cho phép tìm theo nó.

**Cần chốt thêm:** nếu đơn không có mặt hàng nào (đơn toàn dòng "đặt ngoài,
chưa có mã") thì nhóm/tên ngắn lấy ở đâu? Đề xuất: dùng `KHAC-<tên hàng đầu>`.

### YC-3 — Phân loại hoá chất/vật tư và gắn nhà cung cấp

**Đây là mục rẻ nhất trong 5 mục và nên làm trước** — chức năng đã có sẵn trong
ERPNext, chỉ thiếu dữ liệu:

1. **Rà soát `Item Group`** (QĐ-HM-3) — việc dữ liệu, cần người của Miyano.
2. **Nhập bảng `Item Supplier`** (đang 0 dòng): mỗi Item gắn một hoặc nhiều
   Supplier + mã hàng của NCC. Không cần doctype mới.
3. **Thêm 1 báo cáo Desk** "Mặt hàng theo nhóm và nhà cung cấp": lọc theo nhóm/
   NCC, cho ra mặt hàng ↔ nhóm ↔ NCC ↔ mã của NCC ↔ đã nhập lần cuối khi nào.
   Cùng khuôn 10 báo cáo kho hiện có (Script Report, `is_standard=Yes`, khoá
   theo role nhân viên).
4. **Nếu Hi-medic muốn tự xem** nguồn cung của vật tư trong kho họ: module kho
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
4. **Thông báo cho khách** — dùng lại `bao_hen_giao_lai()` (đã chống trùng theo
   ĐƠN+LOẠI+NGÀY). Chỉ cần đảm bảo **mọi user của Hi-medic** nhận được, không
   chỉ user tạo đơn: hiện `_nguoi_nhan_*` gửi theo user; với nhiều tài khoản thì
   phải gửi cho tất cả user gắn với Customer đó, nếu không người trực hôm đó sẽ
   không thấy gì.

### YC-5 — Quản lý User và truy vết

Theo QĐ-HM-1 phương án (A):

1. **Cấp tài khoản** — không cần code. Mỗi người một User + một Contact có
   Dynamic Link tới Customer `Himedic`. Cơ chế đã chạy được sẵn.
   *Cảnh báo vận hành:* Contact `Himedic-Contact` hiện **không gắn user** — cần
   dọn để không ai tưởng đó là một tài khoản.
2. **Sửa `nguoi_kiem` thành có thể truy vết.** Trường này đang là Data (chuỗi
   tự do). Giữ nguyên field (để ghi tên người kiểm thực tế) nhưng **căn cứ truy
   vết phải là `owner` của biên bản** — và phải hiện `owner` trên Desk, chứ
   không đọc `nguoi_kiem` như thể nó là user.
3. **Màn "Lịch sử thao tác" của đơn hàng.** Dữ liệu **đã có** (95 bản ghi
   `Version` cho Sales Order). Cần một màn hình đọc nó: ai, lúc nào, đổi field
   nào, từ giá trị nào sang giá trị nào — cho cả Sales Order, Delivery Note và
   biên bản kiểm hàng của đơn đó, xếp theo thời gian trên MỘT dòng thời gian.
4. **Hiện "ai làm gì" ngay tại chỗ**, không chỉ trong màn lịch sử: người đặt
   trên đơn, người lập biên bản trên biên bản, người nhận thực tế trên từng đợt
   (YC-1), người cập nhật gần nhất.
5. **Phân biệt hai khái niệm** đúng như tài liệu nhấn mạnh: "User thao tác trên
   hệ thống" (tự động, `owner`/`modified_by`, không sửa được) ≠ "Người nhận hàng
   thực tế" (nhập tay từ chứng từ giấy, sửa được, có ghi nguồn căn cứ). Hai chỗ
   khác nhau trên màn hình, nhãn khác nhau, không bao giờ gộp vào một ô.

---

## 5. Thứ tự đề nghị làm

| Bước | Nội dung | Phụ thuộc | Ghi chú |
|---|---|---|---|
| 1 | YC-3 (nhóm + NCC): rà `Item Group`, nhập `Item Supplier`, 1 báo cáo | cần người Miyano chốt cây nhóm | Rẻ nhất, và YC-2 phụ thuộc kết quả rà nhóm |
| 2 | YC-1 (người nhận thực tế + thời điểm nhận theo đợt) | QĐ-HM-4 | Độc lập, giá trị thấy ngay |
| 3 | YC-4 (báo giao thiếu chủ động + SL còn thiếu) | — | Dùng lại cơ chế hẹn giao đã có |
| 4 | YC-5 (truy vết + màn lịch sử) | QĐ-HM-1 | Nếu chốt (A) thì phần lớn là màn hình |
| 5 | YC-2 (mã tra cứu đơn hàng) | QĐ-HM-2, QĐ-HM-3, bước 1 | Làm sau cùng vì phụ thuộc danh mục nhóm |

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
   tin này có thể là hai người khác nhau.
