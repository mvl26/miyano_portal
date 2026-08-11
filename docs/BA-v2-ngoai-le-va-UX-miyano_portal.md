# Tài liệu phân tích nghiệp vụ v2 — Luồng ngoại lệ & Chuẩn giao diện

**Cổng khách hàng Miyano (`miyano_portal`)** · bản trình duyệt

| | |
|---|---|
| Mục đích | Bắt trọn các luồng **ngoại lệ** mà giai đoạn 1 bỏ sót, và chuẩn hoá cách hiển thị / thao tác trên từng form |
| Trạng thái | **Bản thảo chờ duyệt** — chưa sửa một dòng mã nào |
| Nhánh khảo sát | `feature/vat-tu-danh-muc` (`971cc4b`) · site `erptest.local` |
| Ngày lập | 2026-08-11 |
| Tài liệu nền | [`BA-miyano_portal.md`](BA-miyano_portal.md) (luồng chuẩn) · [`Workflow-miyano_portal.html`](Workflow-miyano_portal.html) · [`Workflow-UI-miyano_portal.html`](Workflow-UI-miyano_portal.html) |

---

## 0. Cách đọc và cách duyệt tài liệu này

### 0.1 Ba loại mã số

| Mã | Nghĩa | Anh cần làm gì |
|---|---|---|
| **NG-xx** | Một luồng ngoại lệ chưa được xử lý | Duyệt / hoãn / bác từng mã |
| **QĐ-xx** | Một quyết định nghiệp vụ chỉ chủ đầu tư quyết được | Chọn phương án |
| **UX-xx** | Một chuẩn giao diện áp cho toàn cổng | Duyệt / sửa |

Anh có thể duyệt bằng cách trả lời gọn: *“Duyệt NG-01…NG-12, QĐ-01 chọn phương án A, hoãn NG-33…NG-42, UX duyệt hết.”*

### 0.2 Cột “Kiểm chứng” — đọc kỹ cột này

Tài liệu phân biệt rạch ròi hai loại phát hiện. **Đừng duyệt ngân sách cho hai loại như nhau.**

| Ký hiệu | Nghĩa |
|---|---|
| ✅ **Đã kiểm chứng** | Đã đọc thẳng mã nguồn (có `file:dòng`) và/hoặc truy vấn dữ liệu thật trên site. Có thể coi là sự thật. |
| 🔎 **Cần kiểm chứng** | Suy ra từ cấu trúc mã nguồn, chưa dựng lại được hiện tượng. Cần một buổi thử nghiệm ngắn trước khi ước lượng công. |

### 0.3 Mức độ và công sức

| Mức | Nghĩa |
|---|---|
| **P0** | Sai số liệu / sai tiền / rò rỉ dữ liệu giữa các khách hàng. Sửa trước mọi thứ khác. |
| **P1** | Chặn nghiệp vụ, hoặc làm người dùng mất việc đang làm, hoặc số liệu lệch âm thầm |
| **P2** | Khó dùng, phải gọi điện cho nhân viên Miyano để giải quyết |
| **P3** | Hoàn thiện thêm |

Công sức: **S** ≈ dưới 1 ngày · **M** ≈ 1–3 ngày · **L** ≈ trên 3 ngày (đã tính cả kiểm thử).

### 0.4 Phương pháp

Danh mục dưới đây **không** dựng từ tưởng tượng. Cách làm: đi ngược từng luồng chuẩn của tài liệu BA v1, tại mỗi bước đặt bốn câu hỏi —

1. Nếu dữ liệu nền **đổi giữa chừng** (hợp đồng hết hạn, giá đổi, kho bị tắt) thì sao?
2. Nếu **hai người cùng làm một lúc** thì sao?
3. Nếu bước **thất bại giữa chừng** (mất mạng, hết phiên, lỗi ràng buộc) thì sao?
4. Nếu người dùng làm **đúng chức năng nhưng sai thứ tự** (huỷ trước, xuất trước, nhập lại lần hai) thì sao?

Sau đó xác minh từng nghi vấn bằng mã nguồn và dữ liệu trên site.

### 0.5 Tóm tắt kết quả

**47 luồng ngoại lệ** (NG-01…NG-47), trong đó **28 đã kiểm chứng bằng mã nguồn hoặc dữ liệu thật**, 19 mục còn lại là suy luận cần dựng lại thực nghiệm — riêng nhóm A8 (nhân viên Miyano thao tác sai thứ tự) cần khảo sát cùng phòng kinh doanh trước.
Kèm **4 quyết định** cần chủ đầu tư chốt và **16 chuẩn giao diện** áp cho toàn cổng.

Bốn phát hiện mức P0:

> **NG-37 — Rò rỉ sổ hoá đơn giữa các khách hàng.** Đã biết từ giai đoạn 1, vẫn chưa sửa. Là lỗi bảo mật, đề nghị xếp trước mọi thứ.

> **NG-01 — Hạn mức hợp đồng không hề bị trừ bởi đơn hàng chưa xác nhận.** Một bệnh viện có thể đặt liên tiếp nhiều đơn, mỗi đơn đều “trong hạn mức”, tổng cộng vượt xa hạn mức đã ký. Đã xác minh bằng cả mã nguồn ERPNext lẫn dữ liệu thật trên site.

> **NG-08 — Số tiền khách bấm xác nhận không được bảo đảm bằng số tiền của đơn hàng.** Đơn giá được đọc lại tại thời điểm đặt, không phải giá khách vừa nhìn thấy.

> **NG-09 — Toàn hệ thống hiện không tính VAT ở bất kỳ chứng từ nào**, trong khi giỏ hàng vẫn hiển thị dòng “VAT (5–8%)”. Đã kiểm trên dữ liệu site: **0/7 hoá đơn và 0/10 đơn hàng đã ghi sổ** có thuế. Đây là câu hỏi kế toán cần chủ đầu tư trả lời trước khi bàn tới phần mềm.

> **NG-31 — Miyano huỷ phiếu giao hàng nhưng kho bệnh viện vẫn giữ nguyên hàng, âm thầm.** Xảy ra khi bệnh viện đã xuất mất số hàng đó. Không ai được báo; dấu vết duy nhất nằm trong Error Log.

---

# PHẦN A — DANH MỤC LUỒNG NGOẠI LỆ

## A1. Hợp đồng nguyên tắc và hạn mức

### NG-01 · Hạn mức không tính đơn hàng chưa xác nhận ⚠️ P0

| | |
|---|---|
| **Kiểm chứng** | ✅ Chứng minh bằng **mã nguồn ERPNext** (kết luận không phụ thuộc dữ liệu), có dữ liệu thật đối chứng |
| **Công sức** | M–L (tuỳ phương án ở QĐ-01) |

**Chứng minh.** Cổng kiểm hạn mức bằng `remaining_qty()` = `Blanket Order Item.qty − ordered_qty`
(`portal_context.py:82-91`). Còn `ordered_qty` được tính ở `blanket_order.py:97-119`, và câu truy vấn ở đó có **điều kiện cứng**:

```python
.where(
    (trans.name == trans_item.parent)
    & (trans_item.blanket_order == self.name)
    & (trans.docstatus == 1)                      # ← chỉ đếm đơn ĐÃ GHI SỔ
    & (trans.status.notin(["Stopped", "Closed"]))
)
```

Hàm này lại chỉ được gọi từ `sales_order.py:431` (`on_submit`) và `:464` (`on_cancel`).

Trong khi đó `portal_order_place` tạo đơn ở trạng thái **nháp** (`docstatus = 0`).

**Kết luận là tất yếu, không cần diễn giải dữ liệu:** đơn hàng chưa được Miyano xác nhận **không thể** ảnh hưởng tới `ordered_qty`, nên **không thể** làm giảm con số hạn mức mà cổng báo cho khách.

**Đối chứng trên dữ liệu site `erptest.local`** — hợp đồng `MFG-BLR-2026-00004`, mặt hàng `VTTH-GAUZE-5`:

| Hạn mức ký (`qty`) | `ordered_qty` | SL trong đơn **nháp** | SL trong đơn **đã ghi sổ** |
|---|---|---|---|
| 5 | **2** | **1** | 2 |

`ordered_qty` bằng đúng phần đã ghi sổ; 1 đơn vị trong đơn nháp hoàn toàn vô hình với bộ kiểm hạn mức — khớp với điều mã nguồn đã khẳng định.

**Hậu quả nghiệp vụ.** Hạn mức còn lại mà cổng báo cho khách là **3**, trong khi thực tế chỉ còn **2**. Khách đặt tiếp 3 → tổng cam kết 6 trên hợp đồng 5. Nhân viên Miyano phát hiện khi xác nhận đơn thứ hai và ERPNext báo lỗi — tức là **đẩy va chạm về phía nhân viên và về phía khách đã đặt xong**, đúng thứ mà việc kiểm hạn mức sinh ra để tránh. Với hợp đồng thầu có ràng buộc pháp lý về số lượng, đây là rủi ro hợp đồng chứ không chỉ là lỗi phần mềm.

**Càng nghiêm trọng khi:** khách đặt nhiều đơn trong ngày; Miyano xác nhận theo lô cuối ngày; hoặc nhiều người của cùng bệnh viện cùng đặt.

→ **Quyết định: QĐ-01.**

---

### NG-02 · Hợp đồng nháp vẫn hiện trên cổng · P1 · S

**Kiểm chứng:** ✅ `api/portal.py:128-137` — `portal_contracts` lọc `customer`, `blanket_order_type`, `to_date` nhưng **không lọc `docstatus = 1`**.

Một Blanket Order còn đang soạn (nháp) hiện ngay cho khách và đặt hàng được theo nó. Nghiệp vụ: khách nhìn thấy điều khoản chưa được duyệt nội bộ, có thể là giá đang đàm phán.

**Đề xuất.** Thêm `docstatus: 1` vào bộ lọc của cả `portal_contracts` và `portal_catalog`, và kiểm lại trong `portal_order_place`.

---

### NG-03 · Hợp đồng chưa tới ngày hiệu lực vẫn đặt được · P1 · S

**Kiểm chứng:** ✅ `api/portal.py:132` — chỉ lọc `to_date >= today`, **không lọc `from_date <= today`**.

Hợp đồng năm sau đã nhập trước sẽ hiện và đặt được ngay hôm nay.

---

### NG-04 · Hợp đồng hết hạn giữa lúc khách đang có giỏ hàng · P1 · S

**Kiểm chứng:** ✅ `api/portal.py:191-197` — `portal_order_place` chỉ kiểm `bo.customer`, **không kiểm ngày hiệu lực**.

Khách mở cổng lúc 23h50 ngày 31/12, bấm đặt lúc 00h05 ngày 01/01 → đơn vẫn tạo trên hợp đồng đã hết hạn. Cũng xảy ra khi tab để mở qua đêm — không hiếm ở khoa dược.

**Đề xuất.** Kiểm ngày hiệu lực tại thời điểm đặt (server), báo lỗi rõ ràng và mời chọn hợp đồng khác.

---

### NG-05 · Mặt hàng bị gỡ khỏi hợp đồng sau khi đã vào giỏ · P2 · S

**Kiểm chứng:** ✅ `portal_context.py:83-91` — `remaining_qty` trả về `0.0` khi không tìm thấy dòng hợp đồng.

Hệ quả: khách nhận thông báo **“vượt hạn mức (còn 0)”** trong khi bản chất là **mặt hàng không còn trong hợp đồng**. Thông báo sai bản chất khiến khách gọi điện hỏi “sao hết hạn mức, tôi mới đặt có 5 hộp”.

**Đề xuất.** Tách hai trường hợp thành hai thông báo khác nhau. Đây là ví dụ điển hình cho UX-08.

---

### NG-06 · Hạn mức tính theo `stock_qty`, cổng gửi `qty` · P1 · M

**Kiểm chứng:** ✅ cấu trúc đã xác minh, ⚠️ **chưa kích hoạt trên dữ liệu hiện tại**.

Ba dữ kiện, đọc cùng nhau:

1. `blanket_order.py:107` cộng `Sum(trans_item.stock_qty)` — tức số lượng đã **quy đổi về đơn vị tồn kho**.
2. `Blanket Order Item` **không hề có cột `uom`** (đã xác minh trực tiếp trên CSDL — truy vấn cột này báo `Unknown column`). Nghĩa là `qty` của hợp đồng không mang đơn vị nào cả, và ERPNext ngầm coi nó cùng thang với `stock_qty`.
3. `portal_order_place` gửi `qty` theo **đơn vị bán**, còn `remaining_qty` so trực tiếp với `Blanket Order Item.qty`.

Khi đơn vị bán khác đơn vị tồn kho (hợp đồng ký theo **Thùng**, tồn kho theo **Hộp**, 1 Thùng = 10 Hộp), hai con số nằm trên hai thang đo khác nhau và **phép kiểm hạn mức lệch đúng bằng hệ số quy đổi**.

**Vì sao chưa vỡ, và vì sao sẽ vỡ:**

| Đo trên site | Kết quả |
|---|---|
| Dòng đơn hàng có `conversion_factor ≠ 1` | **0 / 38** — nên hiện chưa sai ở đâu |
| Bản ghi quy đổi đơn vị đã khai trong hệ thống (`UOM Conversion Detail`) | **59** — tức mìn đã cài sẵn |

Sẽ sai ngay ở **mặt hàng đầu tiên** được bán theo đơn vị khác đơn vị tồn. Với 59 bản ghi quy đổi đã tồn tại, đây là chuyện *khi nào*, không phải *có hay không*.

**Đề xuất.** Thống nhất một thang đo — quy đổi ở cổng trước khi so, và hiển thị rõ đơn vị của hạn mức.

---

### NG-07 · Đơn bị Đóng / Dừng thì hạn mức tự trả lại, khách không hay · P3 · S

**Kiểm chứng:** ✅ `blanket_order.py:112` loại trừ đơn có trạng thái `Stopped`/`Closed`.

Hành vi này **đúng** về nghiệp vụ. Vấn đề là khách không được báo, nên hạn mức trên cổng tự nhiên tăng lại mà không rõ lý do.

**Đề xuất.** Nhật ký biến động hạn mức (xem NG-21 và UX-16).

---

## A2. Giá, thuế và số tiền

### NG-08 · Số tiền khách xác nhận không bảo đảm khớp với đơn hàng ⚠️ P0 · M

**Kiểm chứng:** ✅ `api/portal.py:257-261` — `portal_order_place` **đọc lại đơn giá từ `Item Price` tại thời điểm đặt**, trong khi giỏ hàng đang giữ đơn giá lấy về lúc mở danh mục (có thể từ nhiều giờ trước, hoặc từ một tab để mở qua đêm).

**Hậu quả.** Khách bấm “Xác nhận đặt hàng” trên một tổng tiền, đơn hàng được tạo với một tổng tiền khác. **Không có thông báo, không có bước xác nhận lại.** Khoa dược trình duyệt chi theo con số đã chụp màn hình, rồi hoá đơn về với con số khác.

Kết hợp với NG-10 và NG-11 (giá không lọc ngày hiệu lực, nhiều bản ghi giá thì lấy tuỳ ý), độ lệch này **không dự đoán được**.

Đây là loại sai lệch **không tự lộ ra** — nó chỉ xuất hiện ở khâu thanh toán, hàng tuần sau, khi việc đối chiếu đã tốn nhiều người.

**Đề xuất.** Xây một **“phiếu báo giá chốt”** do máy chủ tính:
`POST` giỏ hàng → máy chủ trả về bảng giá, thuế, tổng cộng **kèm một mã chốt và thời hạn** → khách xác nhận đúng mã đó → `portal_order_place` nhận mã chốt, so lại, và **từ chối nếu giá đã đổi**, hiện bảng so sánh cũ/mới và mời xác nhận lại.

---

### NG-09 · Toàn hệ thống không tính VAT, nhưng giao diện hứa có ⚠️ P0 · M

**Kiểm chứng:** ✅ mã nguồn **và** dữ liệu thật.

Mã nguồn, hai điểm:
1. `api/portal.py:180` — `portal_catalog` trả về **`"vat_pct": 0`** gán cứng cho mọi mặt hàng.
2. `api/portal.py:234-280` — `portal_order_place` **không gắn `taxes_and_charges`**, nên `grand_total` của Sales Order bằng đúng tiền hàng.

Dữ liệu trên site `erptest.local`:

| Loại chứng từ đã ghi sổ | Tổng số | Có tiền thuế > 0 | Có gắn mẫu thuế |
|---|---|---|---|
| Sales Invoice | 7 | **0** | **0** |
| Sales Order | 10 | **0** | **0** |

**Nghĩa là gì.** Không phải “cổng tính thiếu thuế so với hoá đơn” — mà là **chưa có chứng từ nào trong hệ thống tính thuế cả**. Trong khi đó màn giỏ hàng hiển thị hẳn một dòng **“VAT (5–8%)”** và danh mục có trường `vat_pct`, tức giao diện đang hứa một thứ mà phía sau không có.

Hai khả năng, hệ quả rất khác nhau:

| Nếu… | Thì… |
|---|---|
| Miyano **thật sự** không tính VAT trên các chứng từ này (ví dụ giá đã gồm thuế, hoặc mặt hàng thuộc diện không chịu thuế) | Phần mềm đúng, **giao diện sai** — phải bỏ dòng VAT và ghi rõ điều khoản giá |
| Miyano **có** tính VAT nhưng dữ liệu trên site này là dữ liệu thử | Cổng đang thiếu hẳn phần thuế, và mọi tổng tiền hiển thị cho khách đều thấp hơn số phải trả |

**Em không tự kết luận được — đây là câu hỏi kế toán.** Dữ liệu site chỉ nói được rằng hiện tại không có thuế ở đâu cả.

→ **Quyết định: QĐ-02.**

---

### NG-10 · Bảng giá không lọc theo ngày hiệu lực · P1 · S

**Kiểm chứng:** ✅ `api/portal.py:170-174` và `:257-261` — truy vấn `Item Price` chỉ theo `item_code`, `price_list`, `selling`; **không lọc `valid_from` / `valid_upto`**.

Một mức giá đã hết hiệu lực vẫn được dùng để báo cho khách và để tạo đơn.

---

### NG-11 · Nhiều bản ghi giá cùng điều kiện → lấy tuỳ ý · P1 · S

**Kiểm chứng:** ✅ cùng hai vị trí trên — `frappe.db.get_value` **không có `order_by`**, nên khi tồn tại nhiều `Item Price` thoả điều kiện, bản ghi nào được trả về là **không xác định**.

Kết hợp với NG-10: sửa giá bằng cách thêm bản ghi mới (cách làm phổ biến) sẽ khiến cổng báo giá cũ hay giá mới **một cách ngẫu nhiên**.

**Đề xuất.** Lọc theo ngày hiệu lực và sắp xếp xác định (`valid_from desc, modified desc`), lấy bản đầu.

---

### NG-12 · Trường tiền chưa đặt `precision = 0` · P1 · S

**Phạm vi: chỉ 8 doctype kho của `miyano_portal`.** Không đụng tới trường tiền của `Sales Order` / `Sales Invoice` — đó là doctype lõi ERPNext, sửa `precision` ở đó kéo theo hệ quả trên toàn hệ thống kế toán và là một câu hỏi riêng, không thuộc tài liệu này.

**Kiểm chứng:** ✅ toàn bộ 10 trường Currency của 8 doctype kho đều có `precision = None` (mặc định 2 chữ số thập phân).

VND không có phần thập phân. Hệ quả theo đúng thứ tự nó xảy ra: đơn giá lô mang phần lẻ → thành tiền từng dòng làm tròn khác nhau → **tổng tiền trên đầu phiếu không bằng tổng các dòng**; và giá trị tồn trong sổ lệch dần khỏi giá trị trong bảng cache.

**Đề xuất.** Đặt `precision: "0"` cho **10 trường Currency của 8 doctype kho**, kèm một patch làm tròn dữ liệu đã có và dựng lại bảng tồn theo lô. Xem UX-01. Việc làm tròn phía chứng từ bán hàng của ERPNext là hạng mục riêng, cần bàn với kế toán.

> Phiếu báo giá chốt ở NG-08, nếu được **lưu lại**, giải quyết luôn một nhu cầu nữa: khi khách thắc mắc *“lúc tôi đặt giá là 78.000”*, hiện không có gì để tra.

---

## A3. Vòng đời đơn hàng

### NG-13 · Không yêu cầu huỷ được sau khi đơn đã xác nhận · P1 · M

**Kiểm chứng:** ✅ `api/portal.py:442-444` — `portal_request_cancel` chặn cứng khi `docstatus != 0`.

Nhưng thực tế bệnh viện đổi ý **sau khi Miyano xác nhận** mới là trường hợp thường gặp: khoa báo lại, bệnh nhân chuyển viện, phát hiện đặt trùng. Hiện tại con đường duy nhất là gọi điện — tức là toàn bộ nhu cầu này nằm ngoài hệ thống, không có dấu vết.

**Đề xuất.** Cho phép gửi **yêu cầu huỷ / yêu cầu sửa** ở mọi trạng thái trước khi giao hàng; đơn không tự huỷ, mà sinh một việc cần xử lý cho Miyano, và hiển thị cho khách trạng thái “Đã gửi yêu cầu huỷ — chờ Miyano phản hồi”.

---

### NG-14 · Đơn bị từ chối là ngõ cụt · P2 · S

Khách nhận email “đã bị từ chối”, mở cổng thấy đơn ở trạng thái Từ chối, và **không có nút nào**. Muốn đặt lại phải chọn tay từng mặt hàng.

**Đề xuất.** Nút **“Đặt lại đơn này”** sao chép toàn bộ dòng hàng sang giỏ mới, kèm hiển thị lý do từ chối mà Miyano ghi.

---

### NG-15 · Đơn sửa lại sau khi huỷ đổi mã, đường dẫn cũ chết · P2 · S

**Kiểm chứng:** 🔎 Cơ chế `amended_from` của Frappe đặt mã mới dạng `SAL-ORD-2026-00042-1`. Email đã gửi cho khách trỏ tới mã cũ.

Khách bấm vào link trong email → mở đơn đã huỷ, hoặc lỗi không tìm thấy. Cần dựng lại để xác nhận biểu hiện chính xác trên cổng.

**Đề xuất.** Màn chi tiết đơn nhận biết đơn đã bị thay thế và tự chỉ sang bản mới.

---

### NG-16 · Không có thông báo khi đơn bị Đóng / Dừng · P2 · S

Năm mẫu thông báo hiện có phủ: đơn mới, đơn xác nhận, đơn từ chối, xuất giao, hoá đơn. **Không có** mẫu cho trạng thái `Stopped`/`Closed`, dù hai trạng thái này trả lại hạn mức (NG-07) và dừng việc giao hàng.

---

### NG-17 · Mã đơn sai trả về lỗi tiếng Anh của framework · P2 · S

**Kiểm chứng:** ✅ `api/portal.py:346-348` — `frappe.get_doc("Sales Order", order)` chạy **trước** `check_permission`. Mã không tồn tại → `DoesNotExistError` nguyên văn tiếng Anh.

Thuộc nhóm NG-40 (bản đồ lỗi).

---

### NG-18 · Giao nhiều đợt: phần sổ sách **đúng**, phần hiển thị **thiếu** · P1 · M

Đây là ví dụ anh nêu. Kết luận sau khi kiểm chứng: **chia đôi**.

| Phần | Kết luận | Kiểm chứng |
|---|---|---|
| Kho khách hàng | ✅ **Đúng.** `_phieu_dang_song()` khoá theo **từng phiếu giao**, nên mỗi đợt giao sinh một phiếu nhập riêng, không đè nhau, không trùng | ✅ `kho/delivery_hook.py:245-255` |
| Màn theo dõi đơn | ✅ **Đúng.** `portal_order_track` gom các phiếu giao theo `against_sales_order` và tính đúng tỷ lệ từng đợt | ✅ `api/portal.py:369-400` |
| Màn “Phiếu giao hàng” | ❌ **Thiếu.** `portal_deliveries` trả về danh sách `Delivery Note` phẳng, **không có trường nào trỏ về đơn hàng** | ✅ `api/portal.py:417-424` |

**Hậu quả.** Khách mở màn phiếu giao, thấy ba phiếu trong cùng một ngày và **không cách nào biết phiếu nào thuộc đơn nào**. Với bệnh viện đặt nhiều đơn/tuần thì màn này gần như vô dụng.

**Đề xuất.** Bổ sung vào mỗi dòng: đơn hàng nguồn, số PO của bệnh viện, tỷ lệ hoàn thành của đơn, và **đợt giao thứ mấy / tổng mấy đợt**. Xem đặc tả màn ở Phần C.

---

### NG-19 · Giao thiếu so với đơn — không ai báo khách · P2 · M

Khi đợt giao cuối vẫn chưa đủ số lượng đã đặt, đơn ở trạng thái “Đang giao” vô thời hạn. Khách không biết là *sẽ có đợt nữa* hay *Miyano giao thiếu và đã dừng*.

**Đề xuất.** Hiển thị rõ **“còn lại chưa giao: N đơn vị”** trên chi tiết đơn, và cho phép khách gửi thắc mắc ngay tại dòng đó.

---

### NG-20 · Trả hàng và giấy báo có chưa có luồng · P2 · L

**Kiểm chứng:** ✅ `kho/delivery_hook.py:90` — hook **bỏ qua** phiếu giao hoàn (`dn.get("is_return")`), tức chủ động không xử lý.

Về phía kho khách hàng, quyết định này đúng (trả hàng phải do thủ kho lập phiếu xuất trả). Nhưng phía cổng: `portal_invoices` sẽ hiển thị giấy báo có với **số tiền âm** và trạng thái “Trả hàng”, không có giải thích, không nối được với phiếu trả nào.

**Đề xuất.** Định nghĩa luồng trả hàng đầu-cuối như một hạng mục riêng — gồm cả đường khách **đề nghị trả hàng** từ cổng.

---

## A4. Kho khách hàng

### NG-21 · Không có nhật ký thay đổi vật tư trên cổng · P1 · M

Đây là ví dụ thứ hai anh nêu. Kết quả kiểm chứng **khác với dự đoán thông thường**:

**Kiểm chứng:** ✅ `Customer Warehouse Item`, `Customer Warehouse`, `Customer Stock Receipt`, `Customer Stock Issue` đều đã bật **`track_changes = 1`**. Frappe **đang ghi** lịch sử vào doctype `Version`.

**Vậy thiếu ở đâu.** Thiếu ở chỗ **khách không đọc được nó**. Theo mô hình cách ly hiện tại (BA v1 mục 8.2), role `Customer` không có quyền trên bất kỳ doctype kho nào, càng không có trên `Version`; và trong danh sách 27 endpoint whitelist **không có endpoint nào trả về lịch sử**.

Nghĩa là: dữ liệu đã có sẵn, chỉ chưa có cửa. Đây là tin tốt — công sức thấp hơn nhiều so với việc phải dựng cơ chế ghi log từ đầu.

**Đề xuất.** Endpoint `kho_vat_tu_lich_su(name)` suy kho từ phiên đăng nhập, kiểm sở hữu, đọc `Version` của đúng bản ghi đó, dịch tên trường sang nhãn tiếng Việt và trả về dạng *“ai · lúc nào · đổi trường gì · từ giá trị nào sang giá trị nào”*. Giao diện: xem UX-16.

**Lưu ý quan trọng cho người triển khai.** `Customer Stock Ledger Entry` và `Customer Stock Lot Balance` **cố ý không bật** `track_changes`, và **đừng bật**: sổ là append-only nên không có “thay đổi” để ghi, còn bảng tồn theo lô là cache dựng lại được. Bật `track_changes` ở đó chỉ làm phình bảng `Version` và tạo ảo giác rằng bảng cache là dữ liệu gốc.

---

### NG-22 · Không có nhật ký cho chính hoạt động kho · P2 · M

Khác với NG-21 (lịch sử **một bản ghi**), đây là nhu cầu **dòng thời gian của cả kho**: hôm nay ai ghi sổ phiếu nào, ai huỷ phiếu nào, phiếu tự sinh nào chưa xử lý. Thủ kho trưởng cần nó để bàn giao ca.

**Đề xuất.** Màn “Nhật ký kho” dựng từ sổ kho + trạng thái phiếu — không cần bảng mới.

---

### NG-23 · Kho bị tắt giữa lúc thủ kho đang nhập liệu · P2 · S

**Kiểm chứng:** ✅ `portal_context.py:42-52` — `get_portal_kho` ném `PermissionError` khi kho `active = 0`.

Quản trị viên tắt kho lúc 10h; thủ kho đang nhập dở phiếu 30 dòng bấm Lưu → lỗi quyền, **mất trắng dữ liệu đang nhập**.

**Đề xuất.** Thuộc nhóm UX-11 (không bao giờ để người dùng mất dữ liệu đang nhập). Thông báo riêng, giữ lại nội dung, cho tải về Excel.

---

### NG-24 · Hai người của cùng bệnh viện sửa cùng một phiếu · P1 · M

**Kiểm chứng:** 🔎 Cả bệnh viện dùng chung một tài khoản cổng (mô hình hiện tại), hoặc nhiều tài khoản cùng trỏ về một `Customer`. Hai người mở cùng phiếu nháp → người lưu sau nhận `TimestampMismatchError`.

Cần dựng lại để biết thông báo hiện ra là tiếng Anh nguyên văn hay đã bị bắt ở đâu đó.

**Đề xuất.** Dịch lỗi (mã `MYN-E102`, xem UX-08) **cộng với** cảnh báo sớm: khi mở một phiếu người khác đang mở, báo ngay chứ đừng đợi tới lúc lưu.

---

### NG-25 · Hết phiên đăng nhập giữa chừng · P1 · M

**Kiểm chứng:** 🔎 Phiếu xuất 30 dòng nhập trong 40 phút; phiên hết hạn; bấm Ghi sổ → 403. Cần đo thời hạn phiên thực tế trên site.

**Đề xuất.** Ba lớp: tự lưu nháp cục bộ theo chu kỳ; cảnh báo trước khi hết phiên; và nếu đã lỡ, cho đăng nhập lại **ngay trên hộp thoại** rồi gửi lại đúng dữ liệu đó thay vì trả về trang đăng nhập trắng.

---

### NG-26 · Mã vật tư không có ràng buộc duy nhất ở tầng CSDL · P1 · S

**Kiểm chứng:** ✅ `customer_warehouse_item.json` — `ma_vat_tu` có `reqd = 1` nhưng **`unique` để trống**. Có kiểm trùng ở tầng ứng dụng khi nhập từ Excel (`kho/vat_tu.py:283` gấp chuỗi để so), nhưng không có gì chặn hai lời gọi đồng thời, hay việc tạo trùng qua hai đường khác nhau.

**Hậu quả.** Hai vật tư cùng mã trong một kho → tồn bị chia đôi, báo cáo cộng sai, người dùng chọn nhầm dòng.

**Đề xuất.** Chỉ số duy nhất trên cặp `(kho, ma_vat_tu)` ở tầng CSDL, kèm patch dọn dữ liệu trùng nếu có. Ràng buộc ở tầng ứng dụng là lớp hai, không phải lớp chính.

---

### NG-27 · Vật tư bị vô hiệu nhưng vẫn còn tồn · P2 · S

`Customer Warehouse Item.active = 0` trong khi lô của nó còn số dư. Câu hỏi chưa có lời đáp: báo cáo tồn kho có tính nó không? Có xuất được không? Có hiện trong gợi ý lô không?

**Đề xuất.** Chọn một quy tắc và áp nhất quán: **vô hiệu = không nhập thêm được, nhưng vẫn xuất được cho tới khi hết tồn**, và vẫn hiện trong mọi báo cáo tồn. Kèm chặn không cho vô hiệu khi còn tồn nếu chủ đầu tư muốn chặt hơn.

---

### NG-28 · Lô không có hạn dùng bị báo là hết hạn hôm nay · P1 · S

**Kiểm chứng:** ✅ `kho/reports.py:355-363` — bộ lọc `han_su_dung <= han_toi` được trình dựng truy vấn của Frappe bọc trong `ifnull()`, nên lô có hạn dùng rỗng **lọt qua**; sau đó `getdate(None)` khiến chúng hiện ra như hết hạn **đúng hôm nay**, trạng thái “Sắp hết hạn”.

Vì mọi lô đến từ phiếu giao hàng trên site này đều là `KHONG-LO` không hạn, **phần lớn nội dung báo cáo cảnh báo hạn dùng hiện là nhiễu**. (Màn tồn kho thì hiển thị đúng: “Không thời hạn”.)

Đây là VĐ-2 trong BA v1, vẫn chưa sửa.

→ **Quyết định: QĐ-03.**

---

### NG-29 · Không sửa được hạn dùng của lô đã có tồn · P2 · M

Thủ kho nhập nhầm hạn dùng, ghi sổ xong mới phát hiện. Hiện chỉ còn cách huỷ phiếu và làm lại — nhưng nếu đã xuất một phần thì BR-K8 chặn huỷ. **Bế tắc thật sự.**

**Đề xuất.** Một chứng từ “điều chỉnh thông tin lô” chỉ sửa thuộc tính mô tả (hạn dùng, số lô), không đụng tới số lượng và giá trị — nên không phá tính append-only của sổ.

---

### NG-30 · Nhập tồn đầu kỳ lần thứ hai · P1 · S

**Kiểm chứng:** 🔎 `kho_import_commit` sinh phiếu nhập loại “Tồn đầu kỳ”. Chưa thấy chốt chặn nào ngăn chạy lần hai → tồn **cộng dồn gấp đôi**.

Kịch bản thật: thủ kho nhập xong, không chắc đã lưu, làm lại lần nữa.

**Đề xuất.** Cảnh báo rõ ràng khi kho đã có phiếu tồn đầu kỳ được ghi sổ, và yêu cầu xác nhận có chủ ý.

---

### NG-31 · Miyano huỷ phiếu giao nhưng kho bệnh viện không đảo được — âm thầm ⚠️ P0 · M

**Kiểm chứng:** ✅ hai đoạn mã, đọc cùng nhau:

- `kho/delivery_hook.py:201-232` — `_huy_theo_delivery_note` gọi `phieu.cancel()` với phiếu đã ghi sổ.
- `customer_stock_receipt.py` → `before_cancel` → `_chan_neu_dao_lam_am_ton()` — **ném lỗi** nếu hàng của lô đó đã bị xuất mất (đúng theo BR-K8).
- `kho/delivery_hook.py:49-84` — `_chay_an_toan` **nuốt mọi lỗi**, quay lui về điểm lưu, ghi Error Log, và **không báo ai cả** (đúng theo BR-K12).

**Chuỗi sự kiện đầy đủ:**

```
Miyano giao 200 hộp  →  thủ kho ghi sổ phiếu nhập  →  bệnh viện xuất 150 hộp dùng
                     →  Miyano phát hiện giao nhầm, huỷ phiếu giao
                     →  hook chạy → cancel() → BR-K8 chặn (đã xuất mất 150)
                     →  _chay_an_toan nuốt lỗi, quay lui
                     →  KẾT QUẢ: phiếu giao ĐÃ HUỶ bên Miyano
                                 phiếu nhập VẪN GHI SỔ bên bệnh viện
                                 200 hộp vẫn nằm trong sổ kho bệnh viện
```

**Đây không phải lỗi lập trình — đây là hai quy tắc đúng va nhau.** BR-K12 (móc không được chặn việc giao hàng) và BR-K8 (không cho đảo làm âm tồn) đều cần thiết, nhưng chưa ai định nghĩa chuyện gì xảy ra khi chúng gặp nhau.

**Hậu quả.** Hai sổ lệch nhau, **không ai được báo**. Dấu vết duy nhất là một dòng Error Log mà thủ kho không có quyền xem và nhân viên Miyano không có lý do để mở. Phát hiện ra khi kiểm kê — có thể vài tháng sau.

**Đề xuất.** Việc nuốt lỗi phải giữ nguyên, nhưng **không được im lặng**. Ba lớp:

1. Sinh một **việc cần xử lý** cho nhân viên kinh doanh phụ trách: *“Phiếu giao X đã huỷ nhưng kho khách Y không đảo được — cần xử lý tay.”*
2. Hiển thị một **cờ cảnh báo trên phiếu nhập** của bệnh viện: *“Phiếu giao hàng nguồn đã bị huỷ. Vui lòng liên hệ Miyano.”*
3. Một **báo cáo đối soát** liệt kê mọi phiếu nhập mà phiếu giao nguồn đã bị huỷ — chạy được bất cứ lúc nào.

---

### NG-32 · Phiếu nhập nháp mồ côi khi phiếu giao bị huỷ trước lúc thủ kho ghi sổ · P3 · S

**Kiểm chứng:** ✅ `kho/delivery_hook.py:225-230` — trường hợp này **đã xử lý đúng**: phiếu nháp bị xoá hẳn.

Ghi vào đây để khép kín danh mục và để không ai “sửa” lại chỗ đang đúng. Còn thiếu duy nhất: thủ kho thấy phiếu biến mất mà không hiểu vì sao → cần một thông báo.

---

## A5. Danh sách, phân trang và tìm kiếm

### NG-33 · Không có phân trang thật ở bất kỳ màn nào · P1 · M

**Kiểm chứng:** ✅ giới hạn cứng ở phía giao diện, không có nút xem thêm, không có tổng số:

| Màn | Giới hạn | Vị trí |
|---|---|---|
| Đơn hàng của tôi | 100 | `views/Orders.vue:31` |
| Hoá đơn & công nợ | 100 | `views/Invoices.vue:41` |
| Phiếu nhập / phiếu xuất | 50 | `views/PhieuNhap.vue:20` |
| Kho của tôi | không giới hạn | `views/Kho.vue` |

**Hậu quả.** Bệnh viện dùng sang năm thứ hai sẽ **im lặng mất phần dữ liệu cũ**. Không có thông báo, không có dấu hiệu — danh sách chỉ đơn giản dừng lại. Đây là loại lỗi người dùng không báo cáo được vì họ không biết mình đang thiếu gì.

Đồng thời màn Kho không giới hạn: kho vài nghìn vật tư sẽ dựng hết một lượt, treo trình duyệt của máy tính cấu hình thấp ở khoa dược.

**Đề xuất.** Xem **UX-05** (chuẩn phân trang) và **API-01** (các endpoint phải trả về tổng số bản ghi — hiện chưa endpoint nào trả về).

---

### NG-34 · Tìm kiếm và lọc chỉ chạy trên phần đã tải · P1 · S

Ô tìm kiếm ở màn Đơn hàng và Kho lọc trên mảng đang có trong trình duyệt. Khi đã có phân trang, khách gõ mã đơn của năm ngoái sẽ **không tìm thấy** dù đơn đó tồn tại — kết quả tệ hơn cả không có ô tìm kiếm, vì nó khẳng định sai rằng đơn không tồn tại.

**Đề xuất.** Tìm kiếm phải chạy ở máy chủ ngay khi có phân trang. Hai việc này phải đi cùng nhau, không tách.

---

### NG-35 · Không lọc được theo khoảng thời gian · P2 · M

Câu hỏi thường trực của kế toán bệnh viện — *“cho tôi mọi hoá đơn quý III”* — hiện không trả lời được trên cổng.

---

### NG-36 · Không sắp xếp được theo cột · P3 · M

---

## A6. Tài khoản và phân quyền

### NG-37 · Rò rỉ sổ hoá đơn giữa các khách hàng ⚠️ P0 · M

**Kiểm chứng:** ✅ vẫn chưa sửa — `hooks.py:282` cho thấy `override_whitelisted_methods` vẫn đang bị chú thích.

`frappe.desk.search.search_link` với `ignore_user_permissions=1` cho phép **một tài khoản cổng bất kỳ** kéo về sổ `Sales Invoice` của **khách hàng khác**, gồm cả tổng tiền và số còn phải trả. Ảnh hưởng `Sales Order`, `Delivery Note`, `Sales Invoice`.

Đây là VĐ-1 trong BA v1. **Là lỗi bảo mật, không phải lỗi tiện dụng** — đề nghị xếp trước mọi hạng mục khác trong danh sách này.

**Đề xuất.** Bọc bằng `override_whitelisted_methods`, ép tắt cờ `ignore_user_permissions` và bỏ `filter_fields` đối với Website User.

---

### NG-38 · Tài khoản gắn nhiều khách hàng thì im lặng chọn cái đầu · P1 · S

**Kiểm chứng:** ✅ `portal_context.py:26-30` — `get_portal_customer` trả về `customers[0]`.

Với bệnh viện có nhiều pháp nhân, hoặc chuỗi phòng khám, người dùng sẽ thấy dữ liệu của **một** đơn vị mà không biết là đơn vị nào, cũng không có cách chuyển. Không rò rỉ ra ngoài phạm vi cho phép, nhưng là hành vi âm thầm và sai.

**Đề xuất.** Nếu chỉ một khách hàng: giữ nguyên. Nếu nhiều: bắt buộc chọn đơn vị khi đăng nhập, và hiện tên đơn vị đang xem thường trực trên thanh bên.

---

### NG-39 · Bệnh viện không tự quản lý được tài khoản của mình · P2 · L

Nhân sự khoa dược nghỉ việc; tài khoản vẫn hoạt động cho tới khi ai đó nhớ ra và gọi Miyano. Không có màn nào cho bệnh viện xem *ai đang có quyền vào cổng của đơn vị mình*.

**Đề xuất.** Vai trò “quản trị viên phía khách hàng”: xem danh sách người dùng của đơn vị, mời thêm, khoá. Kèm nhật ký đăng nhập.

---

### NG-40 · Mã Contact ghép từ tên khách hàng · P2 · S

**Kiểm chứng:** ✅ `api/portal.py:466` — `contact_name = f"{customer}-{email}"`.

Tên khách hàng tiếng Việt có dấu, có ký tự đặc biệt, và có thể rất dài. Ghép thẳng vào tên bản ghi dễ chạm giới hạn độ dài hoặc sinh mã khó đọc. `"Bệnh viện Đa khoa Minh Đức (DEMO)-bvminhduc@demo.miyano"` đã dài 56 ký tự cho một trường hợp còn ngắn.

---

## A7. Lỗi và thông báo

### NG-41 · Không có bản đồ lỗi — lỗi framework tiếng Anh lọt tới khách · P1 · M

**Kiểm chứng:** ✅ không tìm thấy cơ chế dịch lỗi nào trong `frontend/src/api.js` hay `toast.js`.

Mọi lỗi không do mã của mình chủ động ném ra sẽ hiện nguyên văn tiếng Anh, kèm tên lớp ngoại lệ. Người dùng ở khoa dược không đọc được, không mô tả lại được, nên phiếu hỗ trợ chỉ ghi *“nó báo lỗi”*.

**Đề xuất.** Xem **UX-08** — bản đồ lỗi có mã tra cứu, và nguyên tắc **giữ nguyên lỗi chưa ánh xạ**.

---

### NG-42 · Hai thông báo gửi cho cả khách không dùng cổng · P2 · S

**Kiểm chứng:** ✅ `setup/install_notifications.py:33` và `:41` — hai mẫu “Portal - Xuất giao” và “Portal - Hoá đơn phát hành” có `"condition": ""`, tức áp cho **mọi** `Delivery Note` và **mọi** `Sales Invoice` của toàn hệ thống.

Ba mẫu còn lại đều lọc `custom_nguon_don == "Client Portal"`.

**Hậu quả.** Khách hàng chưa bao giờ dùng cổng vẫn nhận email nói về cổng khách hàng. Với khách lớn thì đây là chuyện đối ngoại chứ không chỉ là phiền.

---

## A8. Nhân viên Miyano thao tác sai thứ tự

Bảy nhóm trên đều nhìn từ phía **khách hàng**. Nhóm này nhìn từ phía **Miyano trên Desk** — nơi hệ thống gần như không ràng buộc gì, vì ERPNext vốn cho phép nhân viên có quyền làm mọi thứ theo mọi thứ tự.

NG-31 là một trường hợp đã kiểm chứng của lớp này. Năm mục dưới đây **chưa dựng lại thực nghiệm** — em nêu ra vì chúng cùng một họ với NG-31, và vì bỏ trống mảng này sẽ khiến tài liệu bị đọc nhầm là đã phủ hết.

### NG-43 · Lập phiếu giao hàng khi đơn chưa được xác nhận · 🔎 P1 · S

Workflow đặt đơn ở `docstatus = 0` cho tới bước “Xác nhận”. ERPNext về nguyên tắc không cho tạo `Delivery Note` từ một `Sales Order` chưa ghi sổ, **nhưng nhân viên có thể tạo phiếu giao độc lập** (không tham chiếu đơn nào) rồi giao hàng.

Hệ quả nếu xảy ra: móc kho vẫn chạy và sinh phiếu nhập cho bệnh viện, nhưng đơn hàng trên cổng vẫn hiện “Chờ xác nhận” với tiến độ giao 0%. Khách nhận hàng thật mà cổng nói chưa giao gì.

### NG-44 · Phát hành hoá đơn không có phiếu giao · 🔎 P2 · S

Khách nhận email hoá đơn cho hàng chưa từng thấy phiếu giao trên cổng. Cần xác định Miyano có thực sự làm vậy không (bán hàng thu tiền ngay, hàng giao tay ba…) trước khi quyết định chặn hay chỉ hiển thị cho rõ.

### NG-45 · Huỷ hoá đơn sau khi khách đã xem · 🔎 P2 · M

Khách đã tải PDF hoá đơn, đã trình duyệt chi nội bộ; Miyano huỷ và phát hành lại số khác. Cổng hiện không có thông báo nào cho việc này, cũng không đánh dấu bản đã tải là hết hiệu lực.

### NG-46 · Sửa đơn hàng sau khi khách đã đặt · 🔎 P1 · M

Nhân viên sửa số lượng hoặc đơn giá trên đơn nháp trước khi xác nhận. **Không có dấu vết nào cho khách biết đơn đã bị sửa khác với thứ mình đặt.**

Đây có thể là nghiệp vụ hợp lệ (Miyano điều chỉnh theo tồn thực tế), nhưng nếu vậy thì khách phải được báo và được xác nhận lại. Liên quan chặt với NG-08.

### NG-47 · Đóng / dừng đơn mà không cho khách biết lý do · 🔎 P2 · S

Bổ sung cho NG-07 và NG-16 nhìn từ phía Miyano: hiện không có ô nhập lý do bắt buộc khi đóng đơn, nên dù có làm thông báo thì cũng không có nội dung để gửi.

---

**Đề nghị chung cho cả nhóm A8.** Trước khi làm gì, cần **một buổi ngồi cùng nhân viên kinh doanh** để biết trong năm thao tác trên, cái nào thực sự xảy ra và tần suất ra sao. Rất có thể một nửa là chuyện không bao giờ có, và nửa còn lại là quy trình bình thường của Miyano mà cổng chỉ cần **phản ánh trung thực** chứ không cần chặn.

---

# PHẦN B — CÁC QUYẾT ĐỊNH CẦN CHỦ ĐẦU TƯ

Bốn quyết định dưới đây **không có đáp án kỹ thuật đúng**. Chúng phụ thuộc vào cách Miyano muốn làm ăn với khách. Em nêu phương án và hệ quả, anh chọn.

---

## QĐ-01 · Đơn hàng chưa xác nhận có chiếm hạn mức không? *(giải quyết NG-01)*

| | Phương án A — Giữ chỗ mềm, có thời hạn | Phương án B — Tự ghi sổ đơn ngay khi đặt | Phương án C — Chỉ cảnh báo, không chặn |
|---|---|---|---|
| **Cách làm** | Cổng tự tính “hạn mức còn lại thật” = hạn mức − đã ghi sổ − **đang giữ chỗ trong đơn nháp**. Giữ chỗ tự hết hạn sau N ngày nếu Miyano chưa xác nhận | `portal_order_place` gọi luôn `submit()`, đơn vào thẳng “Đã xác nhận” | Vẫn cho đặt, nhưng báo rõ *“Đơn này sẽ vượt hạn mức nếu các đơn đang chờ đều được duyệt”* |
| **Ưu** | Đúng bản chất nghiệp vụ. Không đụng vào ERPNext. Khách thấy con số thật | Đơn giản nhất. Hạn mức luôn chính xác | Rẻ nhất. Giữ nguyên quyền quyết định cho Miyano |
| **Nhược** | Phải định nghĩa thời hạn giữ chỗ và xử lý khi hết hạn | **Xoá bỏ bước Miyano xác nhận** — va thẳng vào QĐ-04 và vào cả thiết kế workflow hiện tại | Vẫn có thể vượt hạn mức thật. Chỉ chuyển trách nhiệm sang khách |
| **Công sức** | L | S | M |
| **Đề xuất của em** | ✅ **Nên chọn A** | Chỉ chọn nếu Miyano quyết định bỏ luôn bước xác nhận | Chọn nếu cần vá nhanh trước khi làm A |

**Nếu chọn A, cần anh trả lời thêm:** giữ chỗ có thời hạn bao lâu? (đề xuất: **3 ngày làm việc**, sau đó tự nhả và báo cho khách).

---

## QĐ-02 · Hàng bán qua cổng có chịu VAT không, và lấy thuế suất từ đâu? *(giải quyết NG-09)*

**Câu hỏi phải trả lời trước:** trên site hiện tại **không một chứng từ nào tính thuế** (0/7 hoá đơn, 0/10 đơn hàng). Đó là đúng chủ ý, hay là do dữ liệu thử?

- Nếu **đúng chủ ý** (giá đã gồm thuế, hoặc mặt hàng không chịu thuế) → chọn **phương án C** và sửa giao diện cho khớp thực tế. Không cần làm gì thêm.
- Nếu **do dữ liệu thử**, tức thực tế Miyano có xuất hoá đơn VAT → chọn A hoặc B, và đây là hạng mục P0 vì mọi tổng tiền cổng đang hiển thị cho khách đều **thấp hơn số phải trả**.

| | Phương án A — Mẫu thuế theo khách hàng | Phương án B — Thuế suất theo từng mặt hàng | Phương án C — Cổng không hiển thị thuế |
|---|---|---|---|
| **Cách làm** | Gắn `Sales Taxes and Charges Template` cho từng khách; cổng lấy về và tính đúng theo đó | Đọc `Item Tax Template` của từng mặt hàng, cộng dồn theo dòng | Bỏ hẳn dòng VAT khỏi giỏ hàng, ghi rõ *“Giá chưa gồm VAT — hoá đơn sẽ tính theo quy định”* |
| **Ưu** | Chuẩn ERPNext, một chỗ khai báo, khớp hoá đơn | Chính xác nhất khi các mặt hàng khác thuế suất | Rẻ nhất, và **trung thực** — không hứa con số mình không chắc |
| **Nhược** | Sai khi trong cùng đơn có nhiều thuế suất | Phải khai `Item Tax Template` cho toàn bộ danh mục | Khách vẫn không biết trước phải trả bao nhiêu |
| **Công sức** | M | L | S |
| **Chọn khi** | Miyano có tính VAT, phần lớn hàng cùng thuế suất | Miyano có tính VAT, nhiều thuế suất trong một đơn | Miyano **không** tính VAT trên các chứng từ này |

**Đề xuất của em:** xác nhận thực tế kế toán trước; nếu có VAT thì **A làm mặc định, cho phép B ghi đè ở mức mặt hàng**. Dù chọn gì, **dòng “VAT (5–8%)” trên giỏ hàng phải sửa lại cho khớp sự thật** — hiện nó luôn bằng 0 và đó là điều duy nhất chắc chắn sai.

---

## QĐ-03 · Lô không có hạn dùng thì báo cáo cảnh báo hạn xử lý thế nào? *(giải quyết NG-28)*

| | A — Loại khỏi báo cáo | B — Nhóm riêng ở cuối | C — Bắt buộc nhập hạn dùng khi ghi sổ |
|---|---|---|---|
| **Ưu** | Báo cáo sạch, đúng mục đích | Không giấu dữ liệu; thủ kho thấy được phần chưa khai hạn | Giải quyết tận gốc |
| **Nhược** | Giấu mất phần vật tư chưa khai hạn dùng | Báo cáo dài hơn | Chặn đường phiếu tự sinh, vì hàng Miyano giao đến vốn không có lô |
| **Công sức** | S | S | M |
| **Đề xuất của em** | | ✅ **Nên chọn B**, kèm nhãn “Chưa khai hạn dùng” và nút đi thẳng tới chỗ khai bổ sung | |

---

## QĐ-04 · Có duyệt hai tầng cho đơn hàng không? *(VĐ-3 của BA v1, vẫn treo)*

Hiện cả ba chuyển tiếp của workflow đều mở cho `Sales User`, kể cả chuyển tiếp vào trạng thái mà quyền sửa thuộc `Sales Manager`. Tức **nhân viên kinh doanh tự xác nhận được đơn của mình**.

| | A — Giữ một tầng | B — Duyệt hai tầng | C — Hai tầng theo ngưỡng giá trị |
|---|---|---|---|
| **Ưu** | Nhanh, không đổi gì | Có kiểm soát nội bộ | Cân bằng: đơn nhỏ chạy nhanh, đơn lớn có người duyệt |
| **Nhược** | Không có ai soát | Chậm, quản lý thành nút thắt | Phải chọn ngưỡng |
| **Công sức** | — | S | M |

**Quyết định này ràng buộc với QĐ-01 phương án B** — nếu tự ghi sổ đơn ngay khi đặt thì không còn tầng duyệt nào cả. Đề nghị chốt QĐ-04 trước.

---

# PHẦN C — CHUẨN GIAO DIỆN VÀ THAO TÁC

Phần này trả lời câu hỏi *“hiển thị và thao tác từng trường thế nào cho tốt nhất”*. Chia hai tầng: **chuẩn xuyên suốt** (UX-01…UX-16) áp cho mọi màn, và **đặc tả từng màn** cho các màn có lưu lượng cao nhất.

## C1. Chuẩn xuyên suốt

### UX-01 · Tiền tệ VND — ba việc tách bạch

Định dạng chỉ là một phần ba của vấn đề. Phần nguy hiểm nhất là **ô nhập liệu**: người dùng gõ `1500000` vào ô số trơn thì thật sự không phân biệt được với `150000`. Họ nhập sai giá và không ai phát hiện cho tới lúc đối chiếu.

| Vấn đề | Cách xử lý | Áp ở đâu |
|---|---|---|
| Số lưu có phần thập phân vô nghĩa | `precision: "0"` cho **mọi** trường Currency | Schema — làm trước, xem NG-12 |
| Hiển thị số trơn | Một hàm định dạng dùng chung | Toàn bộ cổng |
| Gõ sai số chữ số | Ô nhập **tự chấm nhóm nghìn khi đang gõ**, nhưng gửi đi số thô | Mọi ô đơn giá, thành tiền |

Ba nguyên tắc bắt buộc:

- **Không bao giờ rút gọn con số mà người dùng phải kiểm chứng.** `1,5 tr ₫` chỉ được dùng cho ô KPI trên trang tổng quan, và luôn kèm số đầy đủ ở dòng phụ. Dòng hàng, đơn giá, tổng phiếu — luôn đủ số.
- **Dùng `type="text"` kèm `inputmode="numeric"`**, không dùng `type="number"` (ô số từ chối ký tự phân cách, làm hỏng toàn bộ cơ chế).
- **Giữ đúng vị trí con trỏ sau khi chèn dấu chấm.** Không làm điều này thì con trỏ nhảy về cuối sau mỗi phím và ô nhập không dùng được.

### UX-02 · Hiển thị **tên**, giữ **mã** ở nơi tra được

Người dùng nhận ra “Găng tay khám nitrile size M”, không nhận ra `VTK-00042`. Nhưng mã vẫn phải với tới được — nhân viên hỗ trợ cần nó để đối chiếu với chứng từ in.

| Tầng | Yêu cầu |
|---|---|
| API danh sách | Đính kèm tên hiển thị bằng **một truy vấn cho cả trang**, không truy vấn theo từng dòng |
| API chi tiết | Đính kèm tên cho bản ghi đang mở |
| Cột bảng | Hiện **tên**; **mã vẫn là khoá** để sắp xếp và mở chi tiết; mã hiện khi rê chuột |
| Ô chọn | Tìm được bằng **cả tên lẫn mã**; nhãn hiển thị tên |

Khi thiếu tên (bản ghi đã xoá, bị lọc quyền) thì **lùi về mã rút gọn**, tuyệt đối không để ô trống — ô trống bị đọc thành mất dữ liệu.

### UX-03 · Nút hành động: **ẩn, đừng làm mờ**

Một nút bị làm mờ đặt ra câu hỏi mà chính nó không trả lời được: *tại sao?* Người dùng rê chuột, không thấy giải thích, rồi gọi điện. Một nút vắng mặt thì không đặt ra câu hỏi nào — thanh công cụ đơn giản là chỉ hiện những gì đang làm được.

Mỗi màn chứng từ khai một **bảng hành động**, mỗi hành động kèm điều kiện hiển thị theo trạng thái tài liệu:

| Hành động | Chỉ hiện khi |
|---|---|
| Ghi sổ | `docstatus = 0` |
| Lưu nháp | `docstatus = 0` |
| Huỷ phiếu | `docstatus = 1` **và** không phải phiếu đảo |
| In phiếu (PDF) | `docstatus ≥ 1` |
| Đặt lại đơn này | đơn ở trạng thái Từ chối *(NG-14)* |
| Yêu cầu huỷ | đơn chưa giao *(NG-13)* |

Hai điều kèm theo, đều đã có tiền lệ gây lỗi:

- **Kiểm `docstatus` trước `status`.** Một chứng từ đã huỷ thường vẫn giữ nguyên `status` cũ; đọc `status` trước sẽ hiện nút của tài liệu còn sống trên một tài liệu đã huỷ.
- **Bảng hành động là trình bày, không phải phân quyền.** Máy chủ vẫn phải kiểm độc lập. Điều kiện hiển thị ở giao diện không bao giờ được là thứ duy nhất ngăn một chuyển trạng thái sai.
- **Đỏ chỉ dành cho việc không lùi lại được.** Dùng đỏ cho việc lùi được thì người dùng thôi đọc màu đỏ.

Sau mỗi hành động thành công: hiện thông báo **và tải lại tài liệu**. Màn hình còn hiện trạng thái cũ sau khi ghi sổ thành công là than phiền phổ biến nhất của kiểu giao diện này.

### UX-04 · Bố cục ba tầng cho mọi màn chi tiết

Cổng hiện có bảy loại màn chi tiết và sẽ còn thêm. Làm bảy màn riêng thì chúng sẽ trôi dạt khỏi nhau; làm một màn chung phẳng thì đơn hàng và phiếu kho trông y hệt nhau và **không gì nổi bật lên nữa**.

Cách làm: **một bộ khung, nhiều bản khai**. Bản khai nói *tài liệu này nhấn mạnh cái gì*; bộ khung quyết định *mọi thứ trông thế nào*.

| Khoang | Nội dung | Ví dụ với phiếu nhập |
|---|---|---|
| **Đầu trang** | Nhận diện tức thì | Số phiếu · loại nhập · huy hiệu trạng thái · ngày |
| **Ô số** | 2–4 con số đáng quan tâm | Tổng tiền · số dòng · số lô |
| **Khối trường** | Chi tiết, 1–2 cột | Ngày, loại, người giao, tham chiếu phiếu giao / đơn hàng |
| **Dòng thời gian** | Tiến độ | *(dùng cho đơn hàng, không dùng cho phiếu kho)* |
| **Bảng dòng** | Bảng con | Vật tư · lô · hạn · SL · đơn giá · thành tiền **+ dòng tổng** |

Bốn điều bắt buộc:

- Ô trống thì **bỏ hẳn khoang đó**, đừng hiện nhãn với giá trị rỗng — tài liệu ít dữ liệu sẽ trông như bị vỡ.
- **Dòng tổng của bảng phải thẳng cột với thân bảng.** Lệch 2px là lỗi hiển thị bị báo nhiều nhất của kiểu bố cục này.
- **Trạng thái phải giải quyết ở một chỗ dùng chung**, nếu không màn này ghi “Đã huỷ” còn màn kia ghi “Huỷ bỏ”.
- Luôn giữ một bố cục dự phòng cho loại tài liệu chưa khai, để không bao giờ có màn trắng.

### UX-05 · Phân trang — một kiểu duy nhất, và phải **trung thực**

Áp cho: đơn hàng, hoá đơn, phiếu giao, phiếu nhập, phiếu xuất, danh mục vật tư, tồn kho, mọi báo cáo.

| Yêu cầu | Chi tiết |
|---|---|
| Kích thước trang | 25 dòng mặc định, cho chọn 25 / 50 / 100 |
| Luôn hiện **tổng số** | *“Đang xem 1–25 trong 312 phiếu”* — không có con số này thì người dùng không biết mình đang thiếu gì |
| Kiểu điều hướng | **Xem thêm** cho danh sách xem lướt · **số trang** cho danh sách cần tra cứu |
| Nút Xem thêm biến mất | khi đã hết dữ liệu — không để nút bấm ra rỗng |
| Tìm kiếm và lọc | chạy ở **máy chủ**, trên toàn bộ dữ liệu, không phải trên trang hiện tại *(NG-34)* |
| Giữ trạng thái | quay lại từ màn chi tiết phải về đúng trang, đúng bộ lọc |
| Đang tải | khung xám giữ nguyên chiều cao, không để nội dung nhảy |

> ⚠️ **Việc này cần đổi API.** Toàn bộ endpoint danh sách hiện trả về mảng thuần, **không có tổng số**. Xem API-01.

### UX-06 · Bảng dữ liệu

- **Số căn phải, chữ căn trái.** Không có ngoại lệ — cột số căn trái thì mắt không so sánh được các hàng.
- **Đơn vị đi cùng số** ở cột số lượng (`200 Hộp`), không nằm ở tiêu đề cột.
- **Cột quan trọng nhất đứng thứ hai**, sau cột mã. Người đọc quét cột trái đầu tiên.
- **Cột hành động luôn ở cuối**, cố định khi cuộn ngang.
- **Bảng rộng thì tự cuộn ngang trong khung của nó**, không bao giờ để cả trang cuộn ngang.
- **Rê chuột đổi màu cả dòng** khi dòng bấm được; con trỏ đổi hình.

### UX-07 · Trạng thái rỗng phải nói được bước tiếp theo

Ba loại rỗng khác nhau, ba thông điệp khác nhau — hiện đang bị gộp làm một:

| Loại | Thông điệp | Kèm |
|---|---|---|
| Chưa có gì bao giờ | *“Kho chưa có vật tư nào.”* | Nút **Nhập danh mục từ Excel** |
| Lọc không ra kết quả | *“Không có vật tư nào khớp «bơm tiêm».”* | Nút **Xoá bộ lọc** |
| Không có quyền / chưa mở kho | *“Đơn vị của bạn chưa được mở kho trên cổng.”* | Thông tin liên hệ nhân viên phụ trách |

Loại thứ hai bị nhầm thành loại thứ nhất là nguyên nhân của rất nhiều phiếu hỗ trợ kiểu “mất hết dữ liệu”.

### UX-08 · Bản đồ lỗi — **hai người đọc, hai kênh** *(giải quyết NG-41)*

Người dùng cần câu tiếng Việt nói rõ **phải làm gì**, kèm một mã để đọc qua điện thoại. Lập trình viên cần **nguyên văn** lỗi gốc. Không được hy sinh bên nào cho bên nào.

| Mã | Lỗi gốc | Hiện cho người dùng |
|---|---|---|
| `MYN-E101` | `TimestampMismatchError` | Bản ghi đã được người khác cập nhật. Vui lòng tải lại trang và thử lại. |
| `MYN-E102` | `PermissionError` / 403 | Bạn không còn quyền thao tác trên mục này. Có thể phiên đăng nhập đã hết hạn — vui lòng đăng nhập lại. |
| `MYN-E103` | `DoesNotExistError` | Không tìm thấy bản ghi. Có thể nó đã bị xoá hoặc bạn mở từ một đường dẫn cũ. |
| `MYN-E104` | `MandatoryError` / `Value missing for` | Thiếu thông tin bắt buộc. Vui lòng kiểm tra các ô có dấu * trên biểu mẫu. |
| `MYN-E105` | `DuplicateEntryError` | Bản ghi đã tồn tại — mã bị trùng. |
| `MYN-E106` | `LinkValidationError` | Tham chiếu không hợp lệ — bản ghi liên kết không còn tồn tại. |
| `MYN-E107` | Hết phiên / CSRF | Phiên làm việc đã hết hạn. Dữ liệu bạn nhập vẫn được giữ — đăng nhập lại để gửi tiếp. |

Ba nguyên tắc, mỗi cái đều đã có tiền lệ hỏng ở nơi khác:

1. **Mỗi thông báo phải nói việc cần làm.** “Bản ghi đã được người khác cập nhật” mới chỉ mô tả. Thêm “Vui lòng tải lại trang và thử lại” mới là giải quyết.
2. **Lỗi chưa ánh xạ thì giữ nguyên văn.** Tuyệt đối không thay bằng “Đã có lỗi xảy ra” — một lỗi tiếng Anh xấu xí vẫn chẩn đoán được, còn câu chung chung thì giấu đi mọi thứ chưa ánh xạ.
3. **Không ánh xạ các lỗi nghiệp vụ do chính mình ném ra.** *“Găng tay: cần xuất 500 Hộp nhưng tồn chỉ còn 398 Hộp”* đã là thông báo tốt nhất có thể — dịch lại chỉ làm nó tệ đi.

Phải áp ở **mọi kênh** máy chủ dùng để trả lỗi (`_server_messages`, `exception`, `_error_message`, `message`) — bỏ sót một kênh thì lỗi thô vẫn lọt qua đúng đường đó, và người dùng thấy nó ngẫu nhiên.

### UX-09 · Hộp thoại xác nhận — chỉ khi thật sự cần

Hiện tại xác nhận cả những việc lùi lại được. Xin xác nhận quá nhiều thì người dùng bấm “Đồng ý” theo phản xạ, và lần thật sự quan trọng cũng bị bấm qua.

| Việc | Xác nhận? |
|---|---|
| Lưu nháp | ❌ |
| Ghi sổ phiếu | ✅ — kèm tóm tắt: *“Ghi sổ 12 dòng, tổng 22.800.000 ₫”* |
| Huỷ phiếu đã ghi sổ | ✅ — nêu rõ sẽ sinh phiếu đảo |
| Đặt hàng | ✅ — kèm tổng tiền và tên hợp đồng |
| Xoá dòng khỏi giỏ | ❌ — thay bằng **hoàn tác** trong 5 giây |
| Rời trang khi đang nhập dở | ✅ — xem UX-11 |

### UX-10 · Phản hồi khi đang xử lý

- Nút đã bấm **tự khoá và đổi chữ** (`Ghi sổ` → `Đang ghi sổ…`) — chặn bấm hai lần, vốn là nguyên nhân sinh chứng từ trùng.
- Việc dưới 1 giây: không hiện gì (nhấp nháy còn khó chịu hơn).
- Việc trên 3 giây (xuất Excel, dựng PDF): thanh tiến trình kèm khả năng huỷ.
- Thông báo thành công **tự tắt sau 4 giây**; thông báo lỗi **ở lại cho tới khi người dùng đóng**.

### UX-11 · Không bao giờ để người dùng mất dữ liệu đang nhập

Áp cho mọi biểu mẫu nhiều dòng — đây là nơi mất mát đau nhất *(NG-23, NG-25)*.

1. **Tự lưu cục bộ** mỗi 30 giây vào bộ nhớ trình duyệt, gắn khoá theo phiếu.
2. **Khôi phục khi mở lại**: *“Bạn có bản nháp chưa gửi từ 14:32 hôm nay — khôi phục?”*
3. **Cảnh báo trước khi rời trang** nếu có thay đổi chưa lưu.
4. **Hết phiên thì đăng nhập lại ngay trên hộp thoại**, rồi gửi lại đúng dữ liệu đó — không trả về trang đăng nhập trắng.
5. **Lỗi khi lưu thì giữ nguyên nội dung đã nhập** và nêu đúng dòng sai. Không bao giờ dựng lại biểu mẫu rỗng.

### UX-12 · Bảng nhập nhiều dòng

- **Bàn phím đi hết được**: `Tab` sang ô kế, `Enter` xuống dòng dưới cùng cột, `Ctrl+Enter` thêm dòng mới. Thủ kho nhập 30 dòng bằng bàn phím nhanh gấp nhiều lần bằng chuột.
- **Dòng lỗi tô đỏ tại chỗ và sửa được ngay**, không đẩy sang màn khác. Đây là cách làm hiện đã đúng trong phần nhập Excel — cần áp cho cả nhập tay.
- **Dòng tổng cập nhật tức thì** khi gõ.
- **Xoá dòng có hoàn tác**, không hỏi xác nhận.
- **Dán từ Excel vào bảng** phải hiểu được nhiều dòng nhiều cột.

### UX-13 · Xem nhanh không rời màn

Khi một dòng nhắc tới chứng từ khác (phiếu nhập trỏ về phiếu giao, phiếu giao trỏ về đơn hàng), người dùng cần **xác nhận đúng chứng từ đó** chứ chưa muốn rời khỏi việc đang làm.

Cách làm: bấm vào mã → mở **lớp phủ xem nhanh** dùng lại đúng bản khai của UX-04, kèm nút “Mở đầy đủ”. Tránh được kiểu người dùng mở tab thứ hai rồi bỏ dở biểu mẫu đang điền.

### UX-14 · Tạo nhanh ngay tại chỗ

Thủ kho đang lập phiếu nhập, gặp vật tư chưa có trong danh mục. Hiện phải rời phiếu (mất nội dung đang nhập), sang màn danh mục, tạo, rồi quay lại làm từ đầu.

Ô chọn vật tư khi không tìm thấy phải hiện **“＋ Tạo vật tư «BONG-05»”** ngay trong danh sách xổ xuống, mở hộp thoại nhỏ với đúng ba trường bắt buộc, tạo xong **điền thẳng vào dòng đang đứng**. Phần nhập Excel đã có sẵn cơ chế này — cần đưa sang cả nhập tay.

### UX-15 · Xem trước rồi mới ghi — áp cho mọi thao tác hàng loạt

Nguyên tắc này đã đúng ở ba chỗ nhập Excel. Cần áp thêm cho: nhập tồn đầu kỳ *(NG-30)*, và mọi thao tác trên nhiều dòng cùng lúc.

Bảng xem trước phải nói rõ **ba con số**: sẽ tạo mới bao nhiêu, sẽ cập nhật bao nhiêu, bao nhiêu dòng lỗi — trước khi nút Ghi được bật.

### UX-16 · Nhật ký thay đổi *(giải quyết NG-21, NG-07)*

Hiện ở **hai chỗ**:

| Chỗ | Nội dung |
|---|---|
| Tab “Lịch sử” trong màn chi tiết vật tư / phiếu | *ai · lúc nào · đổi trường gì · từ giá trị nào sang giá trị nào* — nhãn trường bằng tiếng Việt, không hiện tên trường kỹ thuật |
| Màn “Nhật ký kho” | Dòng thời gian toàn kho: phiếu được ghi sổ, phiếu bị huỷ, phiếu tự sinh chưa xử lý, hạn mức biến động |

Không hiện tên trường thô (`ma_vat_tu`) — dịch sang nhãn (`Mã vật tư`). Không hiện dòng thay đổi của các trường hệ thống (`modified`, `modified_by`).

---

## C2. Đặc tả từng màn

Đợt này đặc tả **năm màn có lưu lượng cao nhất**. Các màn còn lại (Nhập tồn đầu kỳ, Nhập danh mục, Báo cáo, Hồ sơ, Tổng quan) đề nghị để đợt sau — em nói rõ chỗ này thay vì làm mỏng cả mười bảy màn.

Ký hiệu: **B** = bắt buộc · **T** = tự động điền · **K** = chỉ đọc.

### Màn 1 — Đặt hàng (danh mục theo hợp đồng)

| Trường | Kiểu hiển thị | Ràng buộc | Rỗng | Lỗi |
|---|---|---|---|---|
| Hợp đồng nguyên tắc | Ô chọn, nhãn = `mã · hiệu lực đến dd/mm/yyyy` | B. Chỉ hợp đồng **đã ghi sổ, đang trong hiệu lực** *(NG-02, NG-03)* | “Đơn vị chưa có hợp đồng còn hiệu lực” + liên hệ | — |
| Tìm kiếm | Ô nhập, tìm ở máy chủ, chờ 300ms | Tìm cả **mã và tên** | — | — |
| Nhóm hàng | Dãy nút chọn | Nhiều lựa chọn | — | — |
| Mã | Chữ đều nét, đậm | K | — | — |
| Tên / quy cách | **Tên chính, nhóm + VAT ở dòng phụ** | K | — | — |
| Đơn giá | Căn phải, đủ số, kèm ₫ | K | — | — |
| Hạn mức còn lại | `còn N/M ĐVT` + thanh tiến trình | Đỏ khi dùng ≥80% | — | — |
| Số lượng | Ô tăng giảm, chỉ nhập số nguyên dương | Chặn vượt hạn mức **còn lại thật** *(NG-01)* | mặc định 0 | Viền đỏ + lý do ngay dưới ô |
| Thêm vào giỏ | Nút | **Ẩn** khi hết hạn mức, không làm mờ *(UX-03)* | — | — |

**Bổ sung so với hiện tại:** phân trang máy chủ *(UX-05)*; cột **“Đã đặt nhưng chưa xác nhận”** để khách thấy phần đang giữ chỗ *(NG-01 phương án A)*; xem nhanh lịch sử giá của mặt hàng *(UX-13)*.

### Màn 2 — Giỏ hàng và xác nhận đơn

| Trường | Kiểu hiển thị | Ràng buộc | Lỗi |
|---|---|---|---|
| Dòng hàng | Bảng, số căn phải | Xoá dòng có **hoàn tác** *(UX-09)* | — |
| Số lượng | Ô tăng giảm | Kiểm lại hạn mức **khi đổi**, không đợi tới lúc gửi | Viền đỏ tại dòng |
| Ngày giao mong muốn | Ô chọn ngày | B. Không cho chọn quá khứ. Mặc định hôm nay + 2 | “Ngày giao không được ở quá khứ” |
| Địa chỉ giao | Ô chọn | B. Chỉ địa chỉ của đơn vị. **Một địa chỉ thì chọn sẵn** | — |
| Số dự trù / PO | Ô nhập | Tuỳ chọn, tối đa 140 ký tự | — |
| Ghi chú | Ô nhiều dòng | Tuỳ chọn | — |
| Tạm tính / VAT / Tổng | Khối tổng kết, đủ số | **Do máy chủ tính** *(NG-08)* | — |

**Bổ sung:** khối tổng kết phải là **bản báo giá chốt từ máy chủ**, có thời hạn, hiện rõ *“Giá có hiệu lực đến hh:mm”*. Nếu giá đổi trong lúc đó, hộp thoại xác nhận **hiện bảng so sánh cũ/mới** và buộc xác nhận lại — chứ không âm thầm đặt theo giá mới.

### Màn 3 — Chi tiết đơn hàng

Bố cục theo UX-04.

| Khoang | Nội dung |
|---|---|
| Đầu trang | Số đơn · huy hiệu trạng thái · ngày đặt · số PO của bệnh viện |
| Ô số | Tổng tiền · đã giao % · **còn lại chưa giao** *(NG-19)* · số đợt giao |
| Dòng thời gian | Đặt hàng → Xác nhận → Soạn hàng → Giao hàng → Hoá đơn |
| Khối trường | Hợp đồng · địa chỉ giao · ngày giao mong muốn · ghi chú |
| Bảng dòng | Mặt hàng · SL đặt · **SL đã giao** · SL còn lại · đơn giá · thành tiền |
| Các đợt giao | Bảng riêng: số phiếu · ngày · tỷ lệ · đơn vị vận chuyển · **nút xem nhanh** |
| Hành động | Tải PDF · **Yêu cầu huỷ** *(NG-13)* · **Đặt lại đơn này** *(NG-14)* — mỗi nút có điều kiện hiện riêng |

### Màn 4 — Phiếu nhập / phiếu xuất (chi tiết)

| Trường | Kiểu hiển thị | Ràng buộc |
|---|---|---|
| Ngày | Chọn ngày | B. Không trước ngày bắt đầu quản lý kho — **báo ngay khi chọn**, không đợi tới lúc ghi sổ |
| Loại nhập / xuất | Ô chọn | B. **“Phiếu đảo” không bao giờ xuất hiện trong danh sách chọn** *(BR-K9)* |
| Người giao / nơi nhận | Ô nhập | Tuỳ chọn, có gợi ý từ lần nhập trước |
| Tham chiếu | Chỉ đọc + **xem nhanh** | K |
| Diễn giải | Nhiều dòng | Tuỳ chọn |
| **Bảng dòng** | | |
| Vật tư | Ô chọn tìm theo mã và tên | B. **Có “＋ Tạo vật tư” ngay trong danh sách** *(UX-14)* |
| Số lô | Ô nhập có gợi ý | Nhập: tuỳ chọn. Xuất: B, chọn từ danh sách lô còn tồn |
| Hạn dùng | Chọn ngày | Tự điền theo lô; cảnh báo màu khi đã/sắp hết hạn |
| Số lượng | Ô số | B, > 0. Xuất: cảnh báo **ngay tại dòng** khi vượt tồn lô |
| Đơn giá | **Ô tiền có chấm nhóm nghìn** *(UX-01)* | B khi nhập; tự điền khi xuất |
| Thành tiền | Chỉ đọc, tính tức thì | K |

**Riêng phiếu xuất:** bảng gợi ý lô FEFO hiện **ngay dưới dòng đang chọn**, không phải cuối trang, để mắt không phải nhảy. Lô đã hết hạn có ô xác nhận riêng. Khi thiếu tồn, hiện rõ thiếu bao nhiêu **nhưng không chặn** — chốt chặn ở bước ghi sổ.

**Hành động** theo UX-03; sau khi ghi sổ, tải lại và hiện huy hiệu mới.

### Màn 5 — Kho của tôi (tồn kho)

| Cột | Hiển thị |
|---|---|
| Mã vật tư | Chữ đều nét, đậm |
| Tên vật tư | **Cột chính**, rộng nhất |
| ĐVT | — |
| SL tồn | Căn phải, đậm |
| Giá trị | Căn phải, đủ số |
| Số lô | Căn phải |
| Hạn gần nhất | Ngày + huy hiệu (⛔ Đã hết hạn / ⚠ Sắp hết hạn / *Không thời hạn*) |
| Mở rộng | Bảng lô con: số lô · hạn · SL · đơn giá |

**Bổ sung:** phân trang *(NG-33 — màn này hiện không giới hạn)*; lọc nhanh theo huy hiệu hạn dùng; tìm kiếm ở máy chủ; **tab “Lịch sử”** trong chi tiết vật tư *(NG-21)*.

---

# PHẦN D — THAY ĐỔI API BẮT BUỘC

| Mã | Thay đổi | Vì |
|---|---|---|
| **API-01** | Mọi endpoint danh sách trả về `{rows: [...], total: N}` thay vì mảng thuần | UX-05 không thể trung thực nếu không biết tổng số |
| **API-02** | Mọi endpoint danh sách nhận tham số `tim`, `tu_ngay`, `den_ngay`, `sap_xep` và xử lý ở máy chủ | NG-34, NG-35, NG-36 |
| **API-03** | Endpoint mới: báo giá chốt (nhận giỏ hàng → trả bảng giá + thuế + tổng + mã chốt + thời hạn) | NG-08 |
| **API-04** | `portal_order_place` nhận mã báo giá chốt và từ chối nếu giá đã đổi | NG-08 |
| **API-05** | `portal_deliveries` trả thêm: đơn hàng nguồn, số PO, tỷ lệ, đợt thứ mấy | NG-18 |
| **API-06** | Endpoint mới: lịch sử thay đổi của một bản ghi kho | NG-21 |
| **API-07** | Bọc `search_link` để chặn rò rỉ giữa các khách hàng | NG-37 |
| **API-08** | Endpoint mới: đối soát phiếu nhập có phiếu giao nguồn đã huỷ | NG-31 |

---

# PHẦN E — ĐỀ XUẤT LỘ TRÌNH

Chia đợt theo **rủi ro**, không theo màn hình. Mỗi đợt tự đứng được và bàn giao được.

### Đợt 1 — Chặn máu (P0) · ước lượng 1–1,5 tuần
`NG-37` rò rỉ dữ liệu · `NG-01` hạn mức · `NG-08` giá lệch lúc đặt · `NG-09` VAT · `NG-31` phiếu giao huỷ không đảo được · `NG-12` precision tiền

> Bốn hạng mục đầu là những thứ đang sinh ra dữ liệu sai hoặc rủi ro pháp lý **ngay lúc này**. Đề nghị không xếp gì khác chen vào đợt này.
> **Cần chốt QĐ-01, QĐ-02, QĐ-04 trước khi bắt đầu.**

### Đợt 2 — Chặn mất mát và chặn lệch số · ~1,5 tuần
`NG-02`→`NG-06` lọc hợp đồng · `NG-10`, `NG-11` giá · `NG-26` mã trùng · `NG-28` cảnh báo hạn · `NG-30` tồn đầu kỳ · `NG-38` nhiều khách hàng · `NG-24`, `NG-25`, `NG-23` mất dữ liệu đang nhập · `UX-08` bản đồ lỗi · `UX-11` tự lưu nháp

### Đợt 3 — Danh sách dùng được ở quy mô thật · ~1,5 tuần
`API-01`, `API-02` · `NG-33`, `NG-34`, `NG-35` · `UX-05`, `UX-06`, `UX-07`

### Đợt 4 — Trám các ngõ cụt nghiệp vụ · ~2 tuần
`NG-13` yêu cầu huỷ · `NG-14` đặt lại đơn · `NG-18` phiếu giao gắn đơn · `NG-19` giao thiếu · `NG-21`, `NG-22` nhật ký · `NG-29` sửa hạn lô · `UX-03`, `UX-04` chuẩn hành động và bố cục

### Đợt 5 — Hoàn thiện thao tác · ~2 tuần
`UX-12` bảng nhập bằng bàn phím · `UX-13` xem nhanh · `UX-14` tạo nhanh tại chỗ · `UX-16` giao diện nhật ký · `NG-15`, `NG-16`, `NG-17`, `NG-27`, `NG-32`, `NG-40`, `NG-42`

### Để sau, cần bàn riêng
`NG-20` luồng trả hàng (L) · `NG-39` khách tự quản lý tài khoản (L) · `NG-36` sắp xếp cột · đặc tả 12 màn còn lại

---

# PHẦN F — NHỮNG GÌ TÀI LIỆU NÀY **CHƯA** BAO PHỦ

Nêu thẳng để anh biết mình đang duyệt cái gì và chưa duyệt cái gì:

1. **Chưa dựng lại thực nghiệm 19 mục đánh dấu 🔎.** Cần một buổi kiểm chứng trước khi ước lượng công chính xác.
2. **Nhóm A8 mới chỉ nhận diện, chưa khảo sát.** Năm mục NG-43…NG-47 cần ngồi cùng phòng kinh doanh để biết thao tác nào thực sự xảy ra; danh sách này gần như chắc chắn còn thiếu.
2. **Chưa khảo sát hiệu năng.** Kho vài nghìn vật tư, sổ vài trăm nghìn dòng — chưa đo. Việc dựng lại bảng tồn theo lô trên dữ liệu lớn có thể là vấn đề riêng.
3. **Chưa xét trên điện thoại.** Cổng có nhánh giao diện di động; toàn bộ Phần C viết cho máy tính. Các bảng nhập nhiều dòng cần thiết kế riêng cho màn hình nhỏ.
4. **Chưa xét khả năng tiếp cận** (bàn phím, trình đọc màn hình, tương phản màu).
5. **Chưa xét đa ngôn ngữ.** Toàn bộ cổng đang cứng tiếng Việt.
6. **Chưa xét đối soát công nợ** — màn hoá đơn hiện chỉ liệt kê, chưa có bảng đối chiếu theo kỳ.
7. **12/17 màn chưa có đặc tả trường** (xem C2).

---

## Xin ý kiến duyệt

Đề nghị anh cho ý kiến theo ba nhóm:

1. **Bốn quyết định QĐ-01…QĐ-04** — đây là phần chặn, chưa có thì đợt 1 không khởi động được.
2. **Phạm vi đợt 1 và đợt 2** — giữ nguyên, hay bỏ bớt / thêm mã nào.
3. **Chuẩn UX-01…UX-16** — duyệt cả cụm hay có mục nào muốn sửa.

Sau khi anh duyệt, em sẽ tách thành kế hoạch triển khai theo từng đợt kèm tiêu chí nghiệm thu cho mỗi mã số.
