# Bàn giao — Cổng khách hàng (E7) ⇄ Module HĐĐT (Fast)

| Meta | Nội dung |
|---|---|
| Từ | Team cổng khách hàng (`miyano_portal`, epic E7 — HĐĐT trên cổng, chỉ đọc) |
| Đến | Team Dev module HĐĐT (`apps/erpnext/erpnext/einvoice/`) |
| Mục đích | PRD E7 chặn code bằng câu *"họp team Dev module HĐĐT chốt tên trường thực tế"*. Việc đó được thay bằng đọc thẳng mã nguồn module (JSON doctype + toàn bộ `erpnext/einvoice/*.py`) thay vì họp — tài liệu này là kết quả đọc đó, cộng với các khoảng trống/câu hỏi cần team HĐĐT xác nhận trước go-live. |
| Trạng thái | Cổng đã code xong phần đọc; **mục 3 và mục 11 cần team HĐĐT hành động trước khi go-live**, các mục còn lại là thông tin tham khảo. |

Toàn bộ phát hiện dưới đây trích từ code thật (đường dẫn file kèm theo), không suy đoán.

---

## 1. Không có XML — ở cả hai tầng

**Tầng lưu trữ:** không field nào trên `Fast EInvoice Document`
(`erpnext/einvoice/doctype/fast_einvoice_document/fast_einvoice_document.json`,
110 field) chứa chuỗi `xml`. Chỉ có `draft_pdf`, `official_pdf`, `converted_pdf`
(đều là PDF).

**Tầng API Fast:** đã rà toàn bộ method Fast được gọi trong `gateway.py`/
`actions.py`/`issue.py` (310 tạo nháp, 320 điều chỉnh, 350 thay thế, 380 PDF
chính thức, 385 PDF chuyển đổi, 700 truy vấn trạng thái, 8200 xác thực) —
không method nào trả XML. Kể cả muốn vá phía cổng cũng không có nguồn để lấy.

**Hệ quả ở cổng:** không dựng nút [⬇ XML gốc]; không lặp lại câu chú thích cố
định của bản mẫu *"File XML là bản gốc có giá trị pháp lý; PDF là bản thể
hiện"* (in câu đó mà chỉ giao PDF là nói sai giá trị pháp lý của file khách
vừa tải — một chứng từ thuế không được phép nói sai điều này). Thay bằng câu
trung thực: PDF là bản thể hiện, cần bản gốc XML thì liên hệ kế toán Miyano.

## 2. Không có URL tra cứu công khai

Không field URL nào trên `Fast EInvoice Document`. Cổng dùng
`tax_verification_code` (Mã CQT cấp) — khách tự dán mã này vào trang tra cứu
của Tổng cục Thuế. Không hard-code một URL tra cứu tự nghĩ ra.

## 3. ⚠️ Không có sự kiện nào hook được khi HĐĐT phát hành — CẦN TEAM HĐĐT

US-E7.3 (PRD E7) muốn cổng gửi email khách ngay khi HĐĐT phát hành thành công.
Đã kiểm thực nghiệm: **mọi lần đổi `status` sang `"06 - Đã phát hành"` đều qua
`frappe.db.set_value(FEI, doc.name, values, update_modified=False)`**
(`issue.py::_store_issue_result`, dòng ~348) — ghi thẳng xuống DB, **không**
chạy qua vòng đời `Document`. Đăng ký `doc_events["Fast EInvoice Document"]
["on_update"]` ở app cổng (hoàn toàn hợp lệ về mặt kỹ thuật — không cần sửa
`apps/erpnext`) **không bao giờ được gọi** cho sự kiện này, vì `set_value` bỏ
qua toàn bộ hook document (`validate`, `on_update`, `on_change`, ...).

Cổng đã **descope** US-E7.3 (không viết job poll vá lỗ — nằm ngoài phạm vi
brief E7 cho vòng này). Hai lựa chọn cho team HĐĐT, xin phản hồi trước
go-live:

1. **Team HĐĐT tự bắn một sự kiện thật** (Frappe realtime, hoặc gọi một
   whitelist method của app cổng ngay sau khi `_store_issue_result` chạy
   thành công) — cách sạch nhất, cổng sẵn sàng nhận.
2. **Cổng tự poll** theo `issued_time`/`modified` mỗi N phút (module đã có
   tiền lệ — `poll_pending_tax_status` chạy 20 phút/lần) — khả thi nhưng
   NGOÀI phạm vi đã duyệt cho epic này, cần một yêu cầu riêng.

Không hành động thì US-E7.3 (email báo khách khi HĐĐT xong) không bao giờ
chạy — khách chỉ biết hoá đơn đã phát hành khi tự vào cổng xem.

## 4. `sales_invoice` gần như không bao giờ được điền

`builder.py::create_from_delivery_note` (luồng tạo bản ghi HĐĐT gốc, method
310) chỉ gán `fei.delivery_note = source.name` — **không bao giờ** gán
`fei.sales_invoice`. Field này tồn tại trên doctype nhưng không `reqd`, và
docstring của chính module (`lookup.py`, dòng 1-14) xác nhận: đường CHÍNH nối
`Fast EInvoice Document` với `Sales Invoice` là bắc cầu qua
`Sales Invoice Item.delivery_note`, `sales_invoice` chỉ là đường PHỤ ("kế
toán tự điền"). Cổng đã implement đúng thứ tự ưu tiên đó
(`miyano_portal/einvoice.py::resolve_all`).

## 5. `amended_from_fei` thiếu trong mọi tài liệu BA/PRD

Bảng "hợp đồng dữ liệu (tên tạm)" trong BA §7.3/PRD E7 chỉ liệt
`einvoice_lien_ket_goc` (ánh xạ dự kiến sang `original_document`) — không
nhắc tới nửa CÒN LẠI của liên kết hai chiều. `lineage.py::
mark_original_superseded` set `amended_from_fei` trên bản ghi GỐC, trỏ TỚI
bản ghi điều chỉnh/thay thế, ngay khi bản ghi con phát hành xong (method
310/320/350 thành công). Không có field này thì không dựng được "link hai
chiều" mà NL-12.2/12.3 yêu cầu.

## 6. Một Sales Invoice có thể khớp NHIỀU `Fast EInvoice Document`

`lineage.py::_COPIED_FIELDS` (dòng 60-97) copy **cả** `delivery_note` **lẫn**
`sales_invoice` từ bản gốc sang bản điều chỉnh/thay thế khi tạo bản con
(`_create_child`). Hệ quả: bản gốc và mọi bản điều chỉnh/thay thế của nó LUÔN
cùng khớp một Sales Invoice (qua cùng `delivery_note`, và cùng `sales_invoice`
nếu giá trị đó có được điền).

Cổng ban đầu chỉ lấy MỘT bản ghi (bản mới nhất theo `creation`) — lỗi Critical
tự phát hiện ở vòng review nội bộ: kế toán vừa bấm "Lập hoá đơn điều chỉnh"
cho một hoá đơn ĐÃ ĐƯỢC CQT CHẤP NHẬN khiến bản GỐC (còn nguyên giá trị pháp
lý, khách đang tải bình thường) biến mất khỏi cổng ngay lập tức, badge lật
sang "Đang phát hành HĐĐT" — sai sự thật. Đã sửa: cổng giờ trả **toàn bộ** tập
bản ghi khớp một Sales Invoice, chọn một bản "chính" cho badge thu gọn theo
độ ưu tiên "còn hiệu lực" > "đang có bản mới soạn dở" > "đã bị thay thế/huỷ",
và hiển thị mọi bản còn lại kèm nút tải riêng.

**Lưu ý cho team HĐĐT:** bất kỳ báo cáo/tra cứu nào khác của các anh dùng
`lookup.py::invoice_numbers_for()` hoặc suy luận "1 Sales Invoice = 1 HĐĐT"
nên rà lại — cùng giả định đó chính là gốc rễ lỗi ở cổng.

## 7. Huỷ nội bộ (status 12) không để lại liên kết sang hoá đơn lập lại

`cancel.py::cancel_internally` chỉ huỷ được hoá đơn đang ở `09 - CQT từ chối`
(method 330), và `_unlock_delivery_note` xoá `fast_invoice_no`/
`fast_key_search` trên `Delivery Note` để cho phép lập một `Fast EInvoice
Document` MỚI cho CÙNG phiếu giao — nhưng **không field nào nối bản ghi cũ
(đã huỷ) với bản ghi mới**. Khác hẳn trường hợp điều chỉnh/thay thế (có
`original_document`/`amended_from_fei`).

Cổng xử lý bằng cách: cả hai bản ghi vẫn cùng xuất hiện trong danh sách (cùng
khớp một `delivery_note`) nên khách vẫn THẤY cả hai, nhưng **không bịa** một
mũi tên "thay bằng" giữa chúng (không có field nào chứng minh điều đó). Nếu
team HĐĐT muốn cổng hiển thị lineage rõ ràng hơn cho trường hợp này, cần thêm
một field nối tường minh (ví dụ trên bản ghi mới: "huỷ và lập lại từ
{tên bản ghi cũ}").

## 8. `tax_verification_code` rỗng trong cửa sổ khách cần nó nhất

`tax_status.py::_normalise` chỉ ghi `tax_verification_code` từ phản hồi CQT —
tức chỉ có giá trị khi trạng thái lên `08 - CQT chấp nhận`. Trong toàn bộ cửa
sổ `06 - Đã phát hành`/`07 - Đã gửi khách` (ngay sau khi khách nhận hoá đơn,
lúc cần tra cứu nhất), mã này RỖNG. Job nền `poll_pending_tax_status` chạy 20
phút/lần, nhưng cửa sổ trễ vẫn có thật (đến vài giờ nếu CQT phản hồi chậm).

Cổng hiện mã này khi có (ẩn cả khối khi rỗng, không phơi ô trống). **Câu hỏi
cho team HĐĐT:** mã tra cứu (`fast_key_search`/keySearch) có được IN NGAY
TRÊN chính bản PDF khách đang cầm không? Nếu có, khách vẫn tự tra được từ
PDF ngay cả khi cổng chưa kịp hiện `tax_verification_code` — không có gì phải
vá thêm. Nếu không, đây là một khoảng trống trải nghiệm thật trong vài giờ
đầu sau phát hành.

## 9. `fast_pattern` (Mẫu số) và `fast_serial` (Ký hiệu) là hai field tách rời

PRD ghi *"Số + mẫu số–ký hiệu (VD `1C26TAA`)"* — dễ đọc nhầm thành một chuỗi,
nhưng trên doctype đây là hai field riêng (`fast_pattern`, `fast_serial`).
Trang tra cứu CQT cũng đòi nhập cả hai tách biệt. Cổng đã bổ sung hiện đầy đủ
(bản đầu chỉ có ký hiệu, thiếu mẫu số).

## 10. `official_pdf` đính qua job nền, có độ trễ

`issue.py::_queue_pdf_download` chạy NỀN sau khi có số hoá đơn thật (đợi ký số
HSM) — nghĩa là trạng thái `06 - Đã phát hành` có thể tồn tại một khoảng thời
gian TRƯỚC KHI PDF thực sự được đính. Cổng xử lý bằng một trạng thái phụ
("... — file đang xử lý") + nút Yêu cầu hỗ trợ, nhưng khách có thể bấm nút đó
nhiều lần trong lúc chờ — nếu độ trễ thường xuyên dài quá vài phút, nên cân
nhắc team HĐĐT thông báo trước hoặc rút ngắn hàng đợi.

## 11. ⚠️ Chưa ai được gán role "Kế toán HĐĐT" trên site — CẦN HÀNH ĐỘNG TRƯỚC GO-LIVE

Đã kiểm trên site thật: `Role` "Kế toán HĐĐT" và "Kế toán trưởng HĐĐT" tồn
tại (do `erpnext.einvoice.setup._make_roles()` tạo khi `bench migrate`) nhưng
**không có User nào được gán hai role này**. Nút [Yêu cầu hỗ trợ] của khách
trên cổng (NL-12.4 — hoá đơn lỗi hoặc thiếu file) tìm người nhận qua chính
hai role đó; hiện tại yêu cầu của khách sẽ rơi vào hư không (không ai nhận
được thông báo, dù bản thân yêu cầu vẫn được ghi nhận thành công phía khách).
**Phải gán ít nhất một người vào một trong hai role trước khi tính năng này
đi live.**

---

## 12. Cổng nay GỌI THẲNG hai hàm của module, và HIỂN THỊ bản nháp cho khách

Từ E7b, hook `Sales Invoice.on_submit` của app cổng (job nền
`miyano_portal/hddt_tu_dong.py`) gọi **hai hàm whitelist của module HĐĐT**:

- `builder.create_from_delivery_note(delivery_note)`
- `actions.preview_draft(fei, client=None)`

Đổi chữ ký hai hàm đó — **kể cả đổi tên tham số `client`** — là vỡ luồng tự
động này. Tham số `client` đang được dùng để tiêm `FastClient` giả trong test
của cổng (không gọi mạng thật khi chạy CI); xin giữ nó.

Cổng **KHÔNG** gọi `send_draft_to_customer`: việc gửi bản nháp cho khách vẫn do
kế toán bấm tay, đúng thiết kế. Job dừng ở `02 - Đã xem nháp`, và nút "Gửi bản
nháp cho khách" mở đúng từ trạng thái đó (`form_state.py::BUTTONS`) — nếu sau
này nút ấy phụ thuộc thêm một cờ chỉ thao tác tay mới đặt được, xin báo trước,
vì cả quyết định "dừng ở 02" dựa vào điều đó.

**Khách hàng nay NHÌN THẤY bản nháp trên cổng.** Bốn thứ cổng đang phụ thuộc —
đổi thì báo trước:

1. **Vùng trạng thái 01–04** là ranh giới "bản nháp khách xem được". Thêm/bớt
   mã trong vùng này là đổi cái khách nhìn thấy.
2. **`draft_pdf`** — cổng phục vụ đúng file này (không phải `official_pdf`) qua
   endpoint riêng có kiểm sở hữu + ghi `Access Log`. Đây là thứ khách thấy
   TRƯỚC HẾT: file PDF do chính Fast dựng.
3. **`Fast EInvoice Line`** (`item_code/item_name/uom/qty/price/amount/
   discount_amount/tax_rate/tax_amount/note`) — bảng dòng hàng DỰ PHÒNG, chỉ
   hiện khi chưa có `draft_pdf`.
4. **`amount` / `tax_amount` / `total_amount` / `amount_in_words`** trên master.

**Hệ quả nghiệp vụ:** `resync_from_delivery_note` ghi đè dòng hàng bất cứ lúc
nào bản ghi còn ở 01–04, nên số liệu khách đang xem có thể đổi giữa hai lần mở.
Cổng đã nói rõ điều đó trong cảnh báo cố định kèm mỗi bản nháp; nếu kế toán cần
khách xem một bản "đóng băng" thì phải có cơ chế khác.

---

## Tóm tắt hành động

| # | Việc | Ai làm | Chặn go-live? |
|---|---|---|---|
| 3 | Cấp một sự kiện thật khi HĐĐT phát hành (hoặc duyệt cho cổng tự poll) | Team HĐĐT | Không chặn go-live E7 (US-E7.3 đã descope), nhưng chặn US-E7.3 |
| 8 | Xác nhận `fast_key_search` có in trên PDF không | Team HĐĐT | Không chặn |
| 7 | Cân nhắc thêm field nối "huỷ và lập lại" | Team HĐĐT | Không chặn |
| 11 | Gán người vào role "Kế toán HĐĐT" | Vận hành/Miyano | **Chặn** — nếu không, [Yêu cầu hỗ trợ] vô nghĩa |
| 12 | Báo trước nếu đổi chữ ký `create_from_delivery_note` / `preview_draft` (gồm tham số `client`) | Team HĐĐT | Không chặn — nhưng đổi ngầm là vỡ luồng tự lập HĐĐT |
| 12 | Báo trước nếu đổi vùng trạng thái 01–04, `draft_pdf`, `Fast EInvoice Line` hoặc các trường tổng tiền | Team HĐĐT | Không chặn — nhưng đổi ngầm là vỡ khối "Hoá đơn nháp" trên cổng |
| 12 | Chốt có đưa vòng duyệt bản nháp (03/04) lên cổng hay giữ qua email | Team HĐĐT + Kế toán | Không chặn |
