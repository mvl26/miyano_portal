# Đối sánh tồn kho trên Sales Order và Material Request cho phần thiếu

**Ngày:** 12/10/2026 · **Chủ đầu tư chốt trong phiên** · Nguồn: mục 2 tài liệu
yêu cầu "Kiểm tra và đáp ứng tồn kho khi tạo Sale Order"

## 1. Vấn đề

Đơn của khách vào ERP thành Sales Order, và nhân viên Miyano phải trả lời một
câu trước khi xác nhận: *"kho mình có đủ hàng cho đơn này không, thiếu bao
nhiêu?"*. Hôm nay form Sales Order không trả lời câu đó. Nhân viên phải mở báo
cáo tồn từng mặt hàng, tự trừ phần đã hứa cho đơn khác, rồi tự lập yêu cầu mua.

Mục 2 yêu cầu một bảng đối sánh ngay trên Sales Order và một đường tạo
Material Request cho phần thiếu.

Miyano **có giữ tồn tại kho riêng** để giao cho khách (chủ đầu tư xác nhận
12/10/2026), nên bảng tồn có giá trị thật với phần lớn dòng hàng.

## 2. Các quyết định đã chốt

| # | Quyết định |
|---|---|
| Q1 | **Giữ mềm.** Không bật Stock Reservation, không đổi Stock Settings. Đơn đã Submit tự trừ vào "tồn có thể sử dụng" của các đơn khác qua `Bin.reserved_qty` mà ERPNext đã ghi sẵn. |
| Q2 | **MR do người bấm, và là MR nháp.** Bảng hiện số thiếu và nút "Tạo MR cho phần thiếu". Không tự sinh MR khi Submit đơn. |
| Q3 | **Ngày giao dự kiến do nhân viên xác nhận tay**, dùng nút "Hẹn lịch giao mới" đã có (`portal_hen_giao.hen_giao_lai`). Không tự tính theo số ngày mua hàng. |
| Q4 | Bảng chỉ nằm trên **Desk**. Cổng khách hàng không hiện gì về tồn của Miyano. |
| Q5 | Tồn tra theo **đúng kho của dòng đơn** (`Sales Order Item.warehouse`), không cộng các kho khác của Miyano. Hàng nằm ở kho khác sẽ hiện là thiếu; muốn dùng thì nhân viên đổi kho trên dòng đơn. *(Em đề xuất, chờ chị xác nhận khi xem lại spec.)* |

## 3. Hai loại tồn, không được lẫn

CR-04 (`kho/can_cu_duyet.py`) đã đặt số tồn cạnh dòng hàng, nhưng đó là tồn
tại kho của **bệnh viện** (`Customer Stock Ledger Entry`), phục vụ quản lý
bệnh viện duyệt số lượng đặt.

Bản này là tồn tại kho của **Miyano** (`Bin`, `Batch` của ERPNext), phục vụ
nhân viên Miyano xác nhận đơn. Hai nguồn, hai người đọc, hai màn. Không dùng
lại số hay hàm của CR-04.

## 4. Dữ kiện đã đo

Đo trên site thử `erptest.local` ngày 12/10/2026, **không phải** hệ thống thật.

| Dữ kiện | Số đo | Hệ quả |
|---|---|---|
| Dòng `Bin` có tồn thực > 0 | 118 / 143 | Đủ dữ liệu để tính |
| Mặt hàng có kho mặc định (`Item Default`) | 186 / 193 | Dòng đơn có kho rõ ràng để tra |
| Mặt hàng quản lý theo lô | 89 | Tồn thô gồm cả lô hết hạn, phải trừ |
| `Bin` có `reserved_qty` > 0 | 18 | Giữ mềm đang chạy sẵn |
| Stock Reservation Entry | 0, tính năng đang tắt | Giữ nguyên (Q1) |
| Sales Order nháp | 96 / 142 | Đơn nháp không giữ hàng, xem §5.3 |
| Mặt hàng có `lead_time_days` | 0 | Không tự tính ngày giao (Q3) |

## 5. Bảng đối sánh tồn kho

### 5.1 Vị trí và thời điểm

Một khối chỉ đọc trên form Sales Order ở Desk, hiện từ lúc đơn còn **nháp**
cho tới khi giao xong. Số được tính lại mỗi lần form tải; không lưu vào đơn.

Phía trên bảng có một dòng tổng kết: "Đủ hàng cả đơn" hoặc "Thiếu k/n dòng".

### 5.2 Các cột

Mỗi dòng `Sales Order Item` một hàng. Mọi số lượng quy về **đơn vị tồn kho**
của mặt hàng (`stock_qty`), và cột đơn vị hiện đúng đơn vị đó.

| Cột | Cách tính |
|---|---|
| Mặt hàng / Kho | `item_code`, `item_name`, `warehouse` của dòng đơn |
| SL yêu cầu | Phần **còn phải giao** của dòng: `stock_qty × (qty − delivered_qty) / qty`. Đơn chưa giao gì thì bằng `stock_qty`. |
| Tồn hiện tại | `Bin.actual_qty` tại kho của dòng |
| Tồn có thể sử dụng | `Tồn hiện tại − lô đã hết hạn − đã giữ cho đơn khác`, không âm |
| SL thiếu | `SL yêu cầu − Tồn có thể sử dụng`, không âm |
| Đề xuất | Xem §5.4 |

**Lô đã hết hạn** — tổng tồn tại kho đó của các lô có `expiry_date` trước hôm
nay. Chỉ áp cho mặt hàng quản lý theo lô. Lô cận hạn vẫn tính là dùng được:
chưa có quy tắc cận hạn nào được chốt.

Chỉ trừ lô **biết chắc** đã hết hạn. Mặt hàng theo lô mà tồn không có sổ lô
đi kèm (đo 12/10/2026 trên site thử: 1/60 mặt hàng theo lô đang có tồn) thì
không trừ gì, không coi là tồn 0.

**Đã giữ cho đơn khác** — phần còn phải giao của các Sales Order **khác** đã
Submit (không On Hold / Closed) có cùng mặt hàng, cùng kho. Tính thẳng bằng
đúng phép tính của `erpnext.stock.stock_balance.get_reserved_qty` (nguồn của
`Bin.reserved_qty`), thêm điều kiện loại đơn đang xem — kể cả cách hàm đó xử
hàng trả lại và hàng nằm trong Product Bundle của đơn khác.

KHÔNG lấy `Bin.reserved_qty` rồi tự trừ phần của đơn đang xem: khi đơn đã
Submit, con số đó gồm cả chính nó, và một phép trừ viết tay phải khớp từng
nhánh của hàm gốc mới không lệch. Lệch thì đơn tự tranh hàng với chính mình.

**Nhiều dòng cùng mặt hàng, cùng kho trong một đơn** dùng chung một lượng tồn:
dòng trước lấy trước, dòng sau chỉ thấy phần còn lại. Không được để hai dòng
cùng báo "đủ" trên cùng một lượng hàng.

**Ghi chú "Đơn khác đã giữ: n".** Dòng nào có đơn đã Submit khác đang giữ
hàng cùng mặt hàng, cùng kho thì hiện thêm ghi chú này dưới ô tồn có thể sử
dụng (chủ đầu tư chốt 12/10/2026). Lý do: hai đơn đã Submit tranh cùng một
lượng tồn thì mỗi đơn trừ trọn phần của đơn kia và cả hai đều báo thiếu — tồn
10, hai đơn cùng cần 7, mỗi đơn thấy thiếu 4, hai MR cộng lại 8 cho chỗ thiếu
thật là 4. Bảng không tự phân tồn theo thứ tự đơn; ghi chú để nhân viên thấy
và tự cân trước khi lập MR.

**Bổ sung sau lượt soát (12/10/2026).**

* Lô bị vô hiệu hoá (`Batch.disabled`) cũng bị trừ như lô hết hạn: ERPNext
  không cho chọn lô đó để xuất.
* Thành phần Product Bundle của **chính đơn đang xem** được trừ khỏi tồn mà
  dòng lẻ cùng mặt hàng, cùng kho nhìn thấy, kèm ghi chú "Bộ sản phẩm trong
  đơn này dùng: n".
* Bảng không hiện trên đơn đã huỷ hoặc đã đóng.
* Số lượng trên MR làm tròn **lên** khi đơn vị tồn kho chỉ nhận số nguyên.
* `tao_mr_phan_thieu` chỉ nhận POST.

### 5.3 Đơn nháp khác

Đơn nháp không giữ hàng, nên hai đơn nháp cùng mặt hàng có thể cùng thấy "đủ".
Bảng **không trừ** đơn nháp vào tồn có thể sử dụng: phần lớn đơn trên hệ thống
đang ở trạng thái nháp, trừ hết thì gần như dòng nào cũng báo thiếu.

Thay vào đó, dòng nào có đơn nháp khác cùng mặt hàng, cùng kho thì hiện thêm
ghi chú "Đơn nháp khác đang chờ: n <đơn vị> (k đơn)" — n là tổng số lượng
theo đơn vị tồn kho, k là số đơn — để nhân viên biết có tranh chấp và xác
nhận đơn theo thứ tự mình muốn.

### 5.4 Cột Đề xuất

| Tình huống | Hiện |
|---|---|
| SL thiếu = 0 | Đủ hàng |
| SL thiếu > 0, chưa có MR | Cần mua n |
| SL thiếu > 0, MR đã phủ một phần | Đã có MR a · cần mua thêm b |
| SL thiếu > 0, MR đã phủ hết | Đã có MR n, kèm liên kết tới MR |
| Không tra được | — |

**"MR đã phủ"** của một dòng đơn = tổng `stock_qty − received_qty` trên các
dòng Material Request nối về dòng đơn đó, tức phần MR **chưa nhận về kho**.
Hàng đã nhận thì đã nằm trong tồn hiện tại; đếm cả số MR gốc là đếm hai lần.
Ví dụ: cần 10, tồn 0, MR 10; hàng về đủ 10 rồi 6 cái bị xuất cho đơn khác →
thiếu 6 và MR không còn phủ gì, bảng phải hiện "Cần mua 6".

### 5.5 Không có dữ liệu thì hiện gạch ngang, không hiện 0

Cùng nguyên tắc với CR-04: "tồn 0" nghĩa là hết hàng, "không biết" là chuyện
khác. Hiện `—` ở các cột tồn và kèm một dòng lý do ngắn khi:

1. Dòng đặt ngoài chưa khớp mã hàng (nằm ở `custom_dat_ngoai`, không có
   `item_code`).
2. Mặt hàng không quản lý tồn kho (`is_stock_item = 0`).
3. Dòng đơn không có kho.
4. Dòng do nhà cung cấp giao thẳng (`delivered_by_supplier = 1`): hàng không
   đi qua kho Miyano.
5. Dòng là Product Bundle: tồn nằm ở các mặt hàng thành phần, không ở mã gộp.

Các dòng này không tính vào số "thiếu" ở dòng tổng kết và không vào MR.

## 6. Nút "Tạo MR cho phần thiếu"

Nằm trong nhóm nút "Miyano" trên form, cạnh "Hẹn lịch giao mới".

**Điều kiện hiện nút:** đơn đã Submit, chưa Closed / On Hold, và còn ít nhất
một dòng có phần thiếu chưa được MR phủ. ERPNext chỉ cho sinh Material Request
từ Sales Order đã Submit; đơn còn nháp thì bảng vẫn hiện số thiếu nhưng không
có nút.

**Kết quả:** một Material Request **nháp** (`docstatus = 0`), loại Purchase:

- chỉ gồm các dòng thiếu, số lượng đúng bằng phần thiếu chưa được phủ, theo
  đơn vị tồn kho;
- mỗi dòng nối về đơn qua `sales_order` và `sales_order_item`;
- kho nhận là kho của dòng đơn;
- ngày cần hàng (`schedule_date`) lấy theo ngày giao của dòng đơn; ngày đó đã
  qua thì lấy hôm nay.

Tạo xong mở thẳng MR đó để bộ phận mua kiểm tra và Submit. Hệ thống không tự
Submit.

**Không sinh trùng.** Phần "MR đã phủ" (§5.4) của chính dòng đơn đó được trừ
ra trước khi tính. Tính cả MR **nháp** lẫn MR đã Submit; MR đã huỷ hoặc đã
Stopped thì không tính. Đây là chỗ khác với `make_material_request` gốc của ERPNext,
vốn chỉ đếm MR đã Submit và lấy toàn bộ số lượng đơn chứ không trừ tồn. Vì hai
khác biệt đó, bản này tự dựng MR chứ không gọi mapper gốc.

Số thiếu được tính lại ở máy chủ tại thời điểm bấm, không tin số trình duyệt
gửi lên: giữa lúc bảng hiện và lúc bấm, tồn có thể đã đổi.

## 7. Luồng sau khi làm xong

1. Khách đặt trên cổng → Sales Order nháp.
2. Nhân viên mở đơn, đọc bảng đối sánh.
3. Nhân viên Submit đơn. Hàng được giữ mềm: các đơn sau thấy tồn có thể sử
   dụng giảm đi.
4. **Đủ hàng** → lập phiếu giao như hiện nay.
5. **Thiếu hàng** → bấm "Tạo MR cho phần thiếu", rồi bấm "Hẹn lịch giao mới"
   để báo khách ngày giao dự kiến (cổng và email, cơ chế đã có).
6. Hàng mua về, nhập kho → bảng trên đơn tự chuyển sang "Đủ hàng".

So với luồng trong tài liệu yêu cầu, bước "Reserve hàng" đổi chỗ với "Xác nhận
SO": ERPNext chỉ ghi nhận giữ hàng sau khi đơn đã Submit.

## 8. Quyền và an toàn

- Tài khoản cổng khách hàng (`user_type = Website User`, đúng định nghĩa
  `permissions._is_restricted_user` của app) bị từ chối trước tiên, kể cả khi
  lỡ được gán thêm vai nội bộ.
- Hai endpoint (đọc bảng, tạo MR) kiểm **danh sách vai nội bộ đặt tên rõ**,
  theo tiền lệ `ROLE_HEN_GIAO`: System Manager, Sales Manager, Sales User,
  Stock Manager, Stock User, Purchase Manager, Purchase User. Không có vai
  nào trong đó thì từ chối.
- KHÔNG dựa vào "có quyền đọc Sales Order": tài khoản cổng khách hàng đọc được
  đơn của chính họ (`permissions.sales_has_permission`), nên phép kiểm đó để
  lọt đúng người cần chặn. Tồn kho của Miyano không được lộ sang khách.
- Sau chốt vai vẫn kiểm quyền đọc chính Sales Order đó; tạo MR còn đòi quyền
  tạo `Material Request`.
- Tính bảng hỏng **không được làm chết form Sales Order**: khối bảng hiện một
  dòng báo lỗi, phần còn lại của form vẫn dùng được. Cùng ràng buộc với các
  khối khác app này gắn lên form.
- Không thêm hook nào vào `validate` / `before_submit` của Sales Order: bảng
  là thông tin để người quyết, không chặn việc xác nhận đơn thiếu hàng.

## 9. Mã nguồn

| Tệp | Việc |
|---|---|
| `miyano_portal/doi_sanh_ton.py` (mới) | Tính bảng cho một đơn; tạo MR nháp cho phần thiếu; hai endpoint whitelist |
| `miyano_portal/public/js/sales_order.js` | Dựng khối bảng trên form; thêm nút "Tạo MR cho phần thiếu" |
| `miyano_portal/tests/test_doi_sanh_ton.py` (mới) | Kiểm thử §10 |

Không thêm doctype, không thêm custom field, không đổi cấu hình ERP.

Phần tính toán tách thành hàm thuần (nhận số, trả số) để kiểm thử không cần
dựng chứng từ; phần đọc `Bin` / `Batch` / `Material Request Item` nằm riêng.

## 10. Kiểm thử

1. Đủ hàng: thiếu = 0, đề xuất "Đủ hàng".
2. Thiếu toàn bộ và thiếu một phần: số thiếu đúng.
3. Lô hết hạn bị loại khỏi tồn có thể sử dụng; lô còn hạn và lô không có hạn
   vẫn tính.
4. Đơn khác đã Submit làm giảm tồn có thể sử dụng; đơn khác còn nháp thì
   không, nhưng hiện ghi chú.
5. Đơn đang xem đã Submit không tự trừ chính mình.
6. Hai dòng cùng mặt hàng, cùng kho chia nhau một lượng tồn.
7. Đơn đã giao một phần: SL yêu cầu chỉ còn phần chưa giao.
8. Đơn vị bán khác đơn vị tồn kho: mọi số quy đúng về đơn vị tồn kho.
9. Dòng đặt ngoài, hàng không quản lý tồn, dòng không kho, dòng giao thẳng,
   dòng Product Bundle: hiện `—`, không vào MR.
10. Tạo MR: chỉ dòng thiếu, đúng số, đúng liên kết, ở trạng thái nháp.
11. Bấm tạo MR lần hai không sinh trùng; MR nháp cũ được tính; MR đã huỷ thì
    không. MR đã nhận hàng về kho thì phần đã nhận không còn tính là phủ.
12. Đơn nháp không tạo được MR.
13. Tài khoản cổng khách hàng bị từ chối ở cả hai endpoint, kể cả với đơn
    của chính họ.

## 11. Ngoài phạm vi

- Giữ cứng theo lô (Stock Reservation Entry).
- Tự tính ngày giao dự kiến theo số ngày mua hàng của mặt hàng / nhà cung cấp.
- Gom phần thiếu của nhiều đơn vào một MR theo ngày hoặc theo nhà cung cấp.
- Hiện đủ / thiếu trên cổng khách hàng.
- Quy tắc loại lô cận hạn.
- Trừ hàng đang đặt mua (`Bin.ordered_qty`) vào số thiếu.
- Hàng mua về bằng Purchase Order KHÔNG nối với MR: `received_qty` của MR không
  tăng, nên MR đó vẫn được tính là đang phủ. Bộ phận mua cần lập PO từ MR.
