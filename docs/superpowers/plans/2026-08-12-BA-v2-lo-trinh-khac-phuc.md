# BA v2 — Lộ trình khắc phục 47 luồng ngoại lệ · Bản điều phối

> Đây là **tài liệu điều phối**, không phải plan thi công. Mỗi đợt có một plan
> chi tiết riêng. Đợt 1 đã có: [`2026-08-12-dot-1-chan-mau-P0.md`](2026-08-12-dot-1-chan-mau-P0.md).

**Tài liệu nguồn:** [`docs/BA-v2-ngoai-le-va-UX-miyano_portal.md`](../../BA-v2-ngoai-le-va-UX-miyano_portal.md) (2026-08-11)
**Ngày lập lộ trình:** 2026-08-12 · nhánh `develop` @ `0ba68b4`

---

## 1. Bốn quyết định — ĐÃ CHỐT

Tài liệu BA v2 để treo bốn quyết định và nói rõ đợt 1 không khởi động được nếu
chưa có. Ngày 2026-08-12 chủ đầu tư đã chốt:

| Mã | Quyết định | Hệ quả thi công |
|---|---|---|
| **QĐ-01** | **A — Giữ chỗ mềm, hết hạn 3 ngày làm việc** | Cổng tự tính hạn mức còn lại thật = `qty − ordered_qty − đang giữ chỗ`. Không đụng `blanket_order.py` của ERPNext. Cần job nhả giữ chỗ + thông báo. Công sức L → là task lớn nhất đợt 1. |
| **QĐ-02** | **A — Có VAT, mẫu thuế theo khách hàng** | `Sales Taxes and Charges Template` gắn trên `Customer`. Cổng đọc và tính đúng theo đó. `portal_order_place` **phải** gắn `taxes_and_charges` lên Sales Order. NG-09 là P0 thật: mọi tổng tiền cổng đang báo cho khách đều **thấp hơn số phải trả**. |
| **QĐ-03** | **B — Nhóm riêng ở cuối báo cáo** | Lô không khai HSD hiện thành nhóm riêng, nhãn "Chưa khai hạn dùng", có nút đi tới chỗ khai bổ sung. Không loại khỏi báo cáo, không bắt buộc nhập. Công sức S → xếp đợt 2. |
| **QĐ-04** | **A — Giữ một tầng duyệt** | Không đổi workflow. **Loại bỏ QĐ-01 phương án B** khỏi bàn (nhất quán: vẫn còn bước Miyano xác nhận, nên vẫn còn khoảng nháp cần giữ chỗ). Không có task nào cho QĐ-04. |

> **Lưu ý về QĐ-02.** Con số "0/7 hoá đơn, 0/10 đơn hàng không có thuế" trong BA v2
> đo trên `erptest.local` — site chơi thử. Chủ đầu tư xác nhận thực tế sản xuất **có**
> xuất hoá đơn VAT. Vậy dữ liệu site là dữ liệu thử, và kết luận đúng là **nhánh thứ hai**
> trong bảng ở NG-09: *"Cổng đang thiếu hẳn phần thuế, và mọi tổng tiền hiển thị cho
> khách đều thấp hơn số phải trả."*

---

## 2. Trạng thái kiểm chứng lại (2026-08-12)

Đọc lại mã nguồn trên `develop @ 0ba68b4`. **Toàn bộ phát hiện ✅ của BA v2 vẫn đúng nguyên.**
Không có mục nào đã được sửa trong lúc chờ duyệt. Các điểm đã đọc lại tận nơi:

| Mã | Xác nhận lại | Vị trí |
|---|---|---|
| NG-37 | `override_whitelisted_methods` vẫn nằm trong khối comment | `miyano_portal/hooks.py:282` |
| NG-02 | `portal_contracts` lọc `customer` + `blanket_order_type` + `to_date`, **không** có `docstatus` | `api/portal.py:131-139` |
| NG-03 | không có `from_date` trong bộ lọc | `api/portal.py:135` |
| NG-04 | `portal_order_place` chỉ kiểm `bo.customer`, không kiểm ngày | `api/portal.py:193-197` |
| NG-09 | `"vat_pct": 0` gán cứng; không gắn `taxes_and_charges` | `api/portal.py:181` · `:234-280` |
| NG-10/11 | `get_value("Item Price", {...})` không `valid_from`, không `order_by` | `api/portal.py:172-175` · `:255-259` |
| NG-08 | đơn giá đọc lại tại thời điểm đặt trong vòng lặp `aggregated` | `api/portal.py:254-259` |
| NG-12 | 10 trường Currency, tất cả `precision = None` | 6 file JSON (xem dưới) |
| NG-31 | `_chay_an_toan` nuốt lỗi, chỉ ghi Error Log | `kho/delivery_hook.py:49-84` |
| NG-01 | `remaining_qty` = `qty − ordered_qty`, không biết đơn nháp | `portal_context.py:82-91` |

**Một đính chính nhỏ với BA v2 §NG-12.** Tài liệu ghi *"10 trường Currency của 8 doctype kho"*.
Đúng là **10 trường**, nhưng chúng nằm trên **6** doctype — `Customer Warehouse` và
`Customer Warehouse Item` không có trường Currency nào. Bảng đầy đủ:

| Doctype | Trường Currency |
|---|---|
| `Customer Stock Receipt` | `tong_tien` |
| `Customer Stock Receipt Item` | `don_gia`, `thanh_tien` |
| `Customer Stock Issue` | `tong_tien` |
| `Customer Stock Issue Item` | `don_gia`, `thanh_tien` |
| `Customer Stock Ledger Entry` | `don_gia`, `gia_tri` |
| `Customer Stock Lot Balance` | `don_gia`, `gia_tri` |

Không đổi phạm vi công việc, chỉ đổi số file phải sửa.

**Một phát hiện mới, làm rộng NG-37.** BA v2 chỉ nêu `frappe.desk.search.search_link`.
Đọc `frappe/desk/search.py` thì `search_link` chỉ là lớp mỏng gọi
`search_widget`, và **`search_widget` cũng là `@frappe.whitelist()` trần** — gọi thẳng
được, và nó còn nhận thêm tham số `filter_fields` cho phép người gọi chọn cột trả về
(đây chính là đường lấy `grand_total` / `outstanding_amount` mà BA v2 mô tả).
**Bọc mỗi `search_link` là vá nửa vời.** Phải bọc cả hai. Chi tiết ở plan đợt 1, Task 1.

---

## 3. Sắp xếp lại các đợt

Giữ nguyên nguyên tắc chia theo rủi ro của BA v2 §E. Ba điều chỉnh so với bản gốc,
đều có lý do:

| Điều chỉnh | Lý do |
|---|---|
| **NG-02…NG-05 (lọc hợp đồng) chuyển từ đợt 2 lên đợt 1** | Chúng là bốn dòng lọc trong cùng một hàm mà đợt 1 đã phải mở ra sửa cho NG-08/NG-09. Sửa riêng ở đợt 2 nghĩa là đọc và kiểm thử lại cùng một hàm hai lần. Công sức cận biên ≈ 0. |
| **NG-10, NG-11 (giá) chuyển lên đợt 1** | Báo giá chốt của NG-08 vô nghĩa nếu hàm đọc giá vẫn trả về bản ghi ngẫu nhiên. NG-08 **không thể** nghiệm thu khi NG-10/11 còn sống. |
| **UX-08 (bản đồ lỗi) giữ ở đợt 2 nhưng dựng khung ở đợt 1** | Đợt 1 sinh ra loại lỗi mới ("giá đã đổi, xác nhận lại"). Cần chỗ đặt nó ngay. Chỉ dựng `errors.js` + 3 mã đầu ở đợt 1; bảng đầy đủ `MYN-E101…E107` ở đợt 2. |

### Đợt 1 — Chặn máu (P0) · ước 2 tuần

`NG-37` · `NG-12` · `NG-10` `NG-11` · `NG-09` · `NG-08` · `NG-02`→`NG-05` · `NG-01` · `NG-31`

Dài hơn ước lượng 1–1,5 tuần của BA v2 vì QĐ-01 chốt phương án **A** (công sức L,
không phải S của phương án B) và QĐ-02 chốt **có VAT** (phải dựng phần tính thuế thật,
không phải chỉ bỏ dòng hiển thị).

**Plan chi tiết:** [`2026-08-12-dot-1-chan-mau-P0.md`](2026-08-12-dot-1-chan-mau-P0.md)

### Đợt 2 — Chặn mất mát và chặn lệch số · ~1,5 tuần

| Mã | Tiêu chí nghiệm thu |
|---|---|
| `NG-06` | Hợp đồng ký theo Thùng, tồn theo Hộp, hệ số 10 → đặt 1 Thùng trừ đúng 1 khỏi hạn mức hợp đồng (không phải 10). Hạn mức hiển thị kèm đơn vị. Test có `conversion_factor ≠ 1`. |
| `NG-26` | Chỉ số duy nhất `(kho, ma_vat_tu)` ở tầng CSDL. Hai lời gọi `kho_vat_tu_tao` đồng thời cùng mã → một thành công, một nhận lỗi tiếng Việt. Patch dọn trùng chạy được trên dữ liệu có sẵn. |
| `NG-28` (QĐ-03 **B**) | Báo cáo cảnh báo hạn: lô có `han_su_dung` rỗng nằm ở nhóm cuối, nhãn "Chưa khai hạn dùng", **không** mang trạng thái "Sắp hết hạn". Lô có hạn thật vẫn phân loại đúng. |
| `NG-30` | Kho đã có phiếu "Tồn đầu kỳ" đã ghi sổ → `kho_import_commit` chặn và yêu cầu xác nhận có chủ ý. Xác nhận rồi mới chạy. |
| `NG-38` | Tài khoản gắn 2 Customer → bắt buộc chọn đơn vị khi đăng nhập; tên đơn vị đang xem hiện thường trực trên thanh bên; đổi được. Tài khoản gắn 1 Customer: hành vi không đổi. |
| `NG-23` `NG-24` `NG-25` | Xem `UX-11`. Ba kịch bản: tắt kho giữa chừng · hai người sửa cùng phiếu · hết phiên — cả ba **không mất dữ liệu đang nhập**. |
| `UX-08` | Bảng đầy đủ `MYN-E101…E107`, áp ở cả bốn kênh `_server_messages` / `exception` / `_error_message` / `message`. Lỗi chưa ánh xạ **giữ nguyên văn**. Lỗi nghiệp vụ tự ném **không** bị ánh xạ lại. |
| `UX-11` | Tự lưu nháp cục bộ 30s · khôi phục khi mở lại · cảnh báo rời trang · đăng nhập lại ngay trên hộp thoại · lỗi khi lưu giữ nguyên nội dung. |
| `UX-01` | Ô nhập tiền tự chấm nhóm nghìn — xem mục riêng ở dưới. Đợt 1 `NG-12` chỉ phủ một phần ba của UX-01 (số lưu trong CSDL); hai phần còn lại nằm ở đây. |

### Đợt 3 — Danh sách dùng được ở quy mô thật · ~1,5 tuần

| Mã | Tiêu chí nghiệm thu |
|---|---|
| `API-01` | **Mọi** endpoint danh sách trả `{rows: [...], total: N}`. Kiểm bằng một test liệt kê endpoint danh sách và assert hình dạng — để endpoint mới sau này không lọt. |
| `API-02` | Mọi endpoint danh sách nhận `tim`, `tu_ngay`, `den_ngay`, `sap_xep`, xử lý **ở máy chủ**. |
| `NG-33` `NG-34` `NG-35` | Bệnh viện có 312 phiếu → thấy đủ 312 qua phân trang; gõ mã đơn năm ngoái **tìm thấy**; lọc được quý III. Màn Kho không còn dựng toàn bộ danh sách một lượt. |
| `UX-05` | 25/50/100 · luôn hiện tổng số · nút Xem thêm biến mất khi hết · quay lại từ chi tiết về đúng trang và đúng bộ lọc · khung xám giữ chiều cao. |
| `UX-06` `UX-07` | Số căn phải · đơn vị đi cùng số · cột hành động cố định cuối · ba loại trạng thái rỗng ba thông điệp khác nhau. |

### Đợt 4 — Trám các ngõ cụt nghiệp vụ · ~2 tuần

| Mã | Tiêu chí nghiệm thu |
|---|---|
| `NG-13` | Gửi yêu cầu huỷ được ở **mọi** trạng thái trước khi giao. Đơn không tự huỷ; sinh việc cần xử lý cho Miyano; khách thấy "Đã gửi yêu cầu huỷ — chờ Miyano phản hồi". |
| `NG-14` | Đơn Từ chối có nút "Đặt lại đơn này" → sao chép toàn bộ dòng sang giỏ mới; hiện lý do từ chối Miyano đã ghi. |
| `NG-18` / `API-05` | `portal_deliveries` trả thêm đơn hàng nguồn · số PO · tỷ lệ hoàn thành · **đợt thứ mấy / tổng mấy đợt**. Ba phiếu cùng ngày phân biệt được thuộc đơn nào. |
| `NG-19` | Chi tiết đơn hiện "còn lại chưa giao: N đơn vị"; gửi thắc mắc được ngay tại dòng đó. |
| `NG-21` / `API-06` | `kho_vat_tu_lich_su(name)` suy kho từ phiên, kiểm sở hữu, đọc `Version`, dịch nhãn tiếng Việt. **Không** bật `track_changes` trên `Customer Stock Ledger Entry` / `Customer Stock Lot Balance`. |
| `NG-22` | Màn "Nhật ký kho" dựng từ sổ kho + trạng thái phiếu, **không** thêm bảng mới. |
| `NG-29` | Chứng từ "điều chỉnh thông tin lô" sửa được HSD/số lô của lô đã có tồn, **không** đụng số lượng và giá trị, **không** phá tính append-only. |
| `UX-03` `UX-04` | Bảng hành động khai theo trạng thái, **ẩn** chứ không làm mờ; kiểm `docstatus` **trước** `status`; bố cục ba tầng một khung nhiều bản khai. |

### Đợt 5 — Hoàn thiện thao tác · ~2 tuần

`UX-12` bàn phím đi hết bảng nhập · `UX-13` xem nhanh không rời màn · `UX-14` tạo nhanh tại chỗ ·
`UX-16` giao diện nhật ký · `NG-15` `NG-16` `NG-17` `NG-27` `NG-32` `NG-40` `NG-42`

### Năm chuẩn UX mà BA v2 §E bỏ sót — xếp lại ở đây

BA v2 §E chia đợt cho `UX-03` `UX-04` `UX-05` `UX-06` `UX-07` `UX-08` `UX-11` `UX-12`
`UX-13` `UX-14` `UX-16`. **Năm chuẩn không có trong đợt nào:** `UX-01` `UX-02` `UX-09`
`UX-10` `UX-15`. Vì §Xin ý kiến duyệt đề nghị duyệt cả cụm `UX-01…UX-16`, để trống năm
mục nghĩa là duyệt xong rồi không ai làm.

Bốn trong năm mục là **chuẩn xuyên suốt, không phải hạng mục đứng riêng** — chúng được
áp bên trong từng task màn hình chứ không có task của mình:

| Mã | Áp ở đâu | Nghiệm thu |
|---|---|---|
| `UX-02` hiển thị tên, giữ mã tra được | Mọi task đụng danh sách hoặc ô chọn (đợt 3 `API-01`/`API-02`, đợt 4 `NG-18`, đợt 5 `UX-13`/`UX-14`) | Tên đính bằng **một** truy vấn cho cả trang, không truy vấn từng dòng. Thiếu tên thì lùi về mã rút gọn, **không bao giờ để ô trống**. |
| `UX-09` hộp thoại xác nhận | Mọi task thêm nút hành động (đợt 1 Task 11, đợt 4 `UX-03`) | Ghi sổ / huỷ phiếu / đặt hàng **có** xác nhận kèm tóm tắt. Lưu nháp và xoá dòng khỏi giỏ **không** — thay bằng hoàn tác 5 giây. |
| `UX-10` phản hồi khi đang xử lý | Mọi task thêm nút gọi máy chủ (đã áp ở đợt 1 Task 11 và Task 12) | Nút tự khoá và đổi chữ · <1s không hiện gì · >3s có thanh tiến trình huỷ được · toast lỗi ở lại tới khi đóng. |
| `UX-15` xem trước rồi mới ghi | Đợt 2 `NG-30` (tồn đầu kỳ) và mọi thao tác hàng loạt | Bảng xem trước nói rõ **ba con số**: tạo mới bao nhiêu · cập nhật bao nhiêu · lỗi bao nhiêu — trước khi nút Ghi được bật. |

`UX-01` thì **khác**, và cần một task riêng ở **đợt 2**:

> **UX-01 · Ô nhập tiền tự chấm nhóm nghìn** — đợt 2, công sức S
>
> BA v2 §UX-01 chia vấn đề tiền VND làm ba phần và gọi ô nhập là *"phần nguy hiểm nhất"*:
> người dùng gõ `1500000` vào ô số trơn **thật sự không phân biệt được** với `150000`;
> họ nhập sai đơn giá và không ai phát hiện cho tới lúc đối chiếu. Đợt 1 `NG-12` chỉ phủ
> **một phần ba** (số lưu trong CSDL). Hai phần còn lại — một hàm định dạng dùng chung và
> một component ô nhập — chưa có ai làm.
>
> Nghiệm thu: `type="text"` + `inputmode="numeric"` (**không** `type="number"` — ô số từ
> chối ký tự phân cách và làm hỏng toàn bộ cơ chế) · tự chấm nhóm nghìn khi đang gõ nhưng
> gửi đi số thô · **giữ đúng vị trí con trỏ** sau khi chèn dấu chấm · áp cho mọi ô đơn giá
> và thành tiền của phiếu nhập / phiếu xuất. Không rút gọn (`1,5 tr ₫`) ở bất kỳ con số nào
> người dùng phải kiểm chứng — chỉ ô KPI trang tổng quan, và luôn kèm số đầy đủ ở dòng phụ.
>
> Đặt ở đợt 2 vì `UX-11` (tự lưu nháp) cũng đụng đúng các biểu mẫu nhiều dòng đó — mở một lần.

### Để sau, cần bàn riêng

`NG-20` luồng trả hàng (L) · `NG-39` khách tự quản lý tài khoản (L) · `NG-36` sắp xếp cột ·
đặc tả 12 màn còn lại · **nhóm A8** (`NG-43`…`NG-47`)

> **Nhóm A8 chưa vào đợt nào, và đó là cố ý.** BA v2 §A8 nói rõ: cần một buổi ngồi
> cùng phòng kinh doanh trước khi ước lượng. Xếp lịch buổi đó **song song với đợt 1**
> để kết quả kịp đưa vào đợt 3. Năm mục này có thể co lại còn một hoặc hai.

---

## 4. Việc cần làm ngoài code

Ba việc không phải task lập trình nhưng chặn hoặc làm hỏng kết quả nếu bỏ:

1. **Khai `Sales Taxes and Charges Template` cho từng Customer** (QĐ-02 A). Không có
   template thì phần tính thuế đợt 1 không có gì để đọc. Cần danh sách khách + thuế suất
   từ kế toán **trước Task 4 của đợt 1**.
2. **Buổi khảo sát nhóm A8** với phòng kinh doanh (BA v2 §A8, §F.2).
3. **Dựng lại thực nghiệm 19 mục 🔎** (BA v2 §F.1). Đợt 1 đã kiểm chứng lại toàn bộ mục
   ✅ liên quan; 19 mục 🔎 nằm rải ở đợt 2, 4, 5 — cần buổi kiểm chứng trước khi ước lượng
   chính xác các đợt đó.

## 5. Những gì lộ trình này KHÔNG phủ

Nguyên văn theo BA v2 §F, chưa có gì thay đổi: chưa khảo sát hiệu năng · chưa xét
điện thoại · chưa xét khả năng tiếp cận · chưa xét đa ngôn ngữ · chưa xét đối soát
công nợ · 12/17 màn chưa có đặc tả trường.
