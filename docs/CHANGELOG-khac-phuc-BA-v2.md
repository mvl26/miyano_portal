# Sổ theo dõi khắc phục BA v2 — sửa cái gì, sửa thành gì

> **File này là nguồn sự thật duy nhất về trạng thái khắc phục.** Trước khi sửa bất kỳ
> mã `NG-xx` / `UX-xx` / `API-xx` nào, **đọc file này trước** để biết chỗ đó đã bị ai
> động vào chưa và động thành gì. Sau khi sửa xong, **ghi vào đây trong cùng commit**.
>
> Lý do tồn tại: 47 luồng ngoại lệ chạm vào cùng một nhúm hàm (`portal_order_place`,
> `portal_catalog`, `remaining_qty`, `delivery_hook`). Hai người sửa hai mã số khác nhau
> rất dễ đè lên nhau. Bảng dưới đây cho biết **hàm nào đã đổi hình dạng** trước khi
> ai đó mở nó ra lần nữa.

**Tài liệu nguồn:** [`BA-v2-ngoai-le-va-UX-miyano_portal.md`](BA-v2-ngoai-le-va-UX-miyano_portal.md)
**Lộ trình:** [`superpowers/plans/2026-08-12-BA-v2-lo-trinh-khac-phuc.md`](superpowers/plans/2026-08-12-BA-v2-lo-trinh-khac-phuc.md)

---

## 0. Cách ghi

Mỗi mục đã sửa ghi **năm dòng**, không hơn:

```
### NG-xx · <tên ngắn> — <ngày> · commit <sha ngắn>
**Trước:** <hành vi cũ, một câu>
**Sau:** <hành vi mới, một câu>
**Đụng vào:** <file:dòng hoặc file:hàm — liệt kê hết, kể cả file JSON và patch>
**Phá vỡ:** <ai/cái gì phải đổi theo — API, frontend, dữ liệu. Ghi "không" nếu không>
**Test:** <đường dẫn module test chứng minh>
```

Nếu một task đụng vào một hàm mà **task khác cũng sẽ đụng**, ghi thêm dòng:
`**Cảnh báo chồng lấn:** <mã số khác> cũng sẽ sửa hàm này — <điều cần biết>`

---

## 1. Trạng thái hiện tại

| | |
|---|---|
| Nhánh | `develop` |
| Điểm gốc (chưa sửa gì) | `0ba68b4` — *docs(portal): bộ tài liệu BA và sơ đồ quy trình cho cổng khách hàng* |
| Đợt đang chạy | **Đợt 1 — Chặn máu (P0)**, chưa bắt đầu |
| Cập nhật lần cuối | 2026-08-12 |

### Bảng tiến độ

Trạng thái: ⬜ chưa làm · 🟨 đang làm · ✅ xong · ⏸️ hoãn

| Đợt | Mã | Trạng thái | Ghi chú |
|---|---|---|---|
| 1 | NG-37 rò rỉ sổ hoá đơn | ✅ | Phạm vi rộng hơn BA v2: phải bọc **cả** `search_widget`, không chỉ `search_link` |
| 1 | NG-37b rò rỉ dòng chi tiết chứng từ qua `frappe.client.get_list`/`get` | ✅ | Round 1 (2026-08-12) đóng **chỉ** trục route (hai route định tuyến bằng chuỗi tên) và fail OPEN trên trục doctype (liệt kê 3 tên → Critical C1, xem §4 "Fix round 1"). Round 2 (cùng ngày, sau review) đóng **cả hai trục**: route (`/api/method`, `/api/v2/method`) VÀ doctype (`frappe.is_table`, mọi doctype con). Route REST (`/api/resource`, `/api/v2/document`) đã đóng riêng ở NG-37c (Task 1c). **CÒN MỞ, ngoài phạm vi NG-37b/NG-37c — trục HÀM `get_value`/`validate_link`/`has_permission`**, xem NG-37d. |
| 1 | NG-37c rò rỉ cùng họ qua REST `/api/resource` và `/api/v2/document` (list + đọc đơn) | ✅ | Task 1c (2026-08-12). Chặn ở `before_request` (`miyano_portal/rest_guard.py::chan_rest_doctype_con`), theo THUỘC TÍNH `frappe.is_table(doctype)` — không liệt kê tên (giữ nguyên nguyên tắc NG-37b round 2). Phủ ba prefix `/api/resource/`, `/api/v1/resource/`, `/api/v2/document/`, cả dạng list lẫn dạng `<name>` đơn lẻ. Xem §4. |
| 1 | NG-37d rò rỉ/kết quả sai qua `frappe.client.get_value` · `validate_link` · `has_permission` (docname dạng chuỗi) trên MỌI doctype con | ⬜ **còn mở, đã re-xác nhận độc lập ở Task 1c Step 7** | Phát hiện khi quét Step 7 của NG-37b, KHÔNG thuộc phạm vi NG-37b lẫn NG-37c (route `/api/method/frappe.client.get_value`\|`validate_link`\|`has_permission` — không phải REST resource/document nên `rest_guard.py` không chạm tới; không có entry trong `override_whitelisted_methods` nên `search_guard.py` cũng không chạm tới). **Re-probe HTTP thật, 2026-08-12, phiên `bvbm@demo.miyano`, doctype `Payment Schedule` (không phải ba doctype PoC gốc — cố ý chọn khác để xác nhận đây là lỗ theo TRỤC HÀM, không phụ thuộc doctype):** `GET /api/method/frappe.client.get_value?doctype=Payment+Schedule&parent=Sales+Invoice&fieldname=["parent","parenttype","payment_amount","outstanding"]` → `{"message":{"parent":"ACC-SINV-2026-00001",...,"outstanding":13900000.0}}` — dòng của khách KHÁC. **Chi tiết dễ hiểu lầm:** gọi KHÔNG kèm `parent=` thì `get_value`/`get` tự ném `PermissionError` (vì `check_parent_permission(None, doctype)` luôn `raise` khi `parent` rỗng — `db_query.py:1305-1318`) — trông giống như "đã chặn", nhưng chỉ cần client thêm đúng `parent=<parenttype thật>` là lọt hoàn toàn; đây KHÔNG phải phòng thủ, chỉ là tác dụng phụ tình cờ. `has_permission` re-probe: `GET /api/method/frappe.client.has_permission?doctype=Sales+Order+Item&docname=<dòng khách khác>&perm_type=read` → `{"has_permission": true}` (oracle sai, không lộ field nhưng xác nhận quyền sai). `validate_link` re-probe: `GET /api/method/frappe.client.validate_link?doctype=Payment+Schedule&docname=<dòng khách khác>` → trả `{"name": ...}` (không ném lỗi) thay vì `PermissionError`. Cả ba đều CHƯA sửa trong Task 1c (đúng brief: không lặng lẽ mở rộng phạm vi) — cần một task riêng, có thể port tiếp mẫu `search_guard.client_get_list`/`client_get` (đăng ký qua `override_whitelisted_methods`, KHÔNG cần `before_request` vì route này định tuyến bằng chuỗi tên) cho ba hàm này. |
| 1 | NG-37e cùng cơ chế có thể áp dụng cho `Blanket Order Item` | ⬜ | Cha `Blanket Order` đã có `blanket_query`/`generic_has_permission` giống ba doctype con NG-37b, nên lý thuyết cùng một lỗ `check_parent_permission` doctype-level. **Chưa xác nhận bằng probe** (ngoài phạm vi NG-37b, không mở rộng brief). Người sau cần kiểm `frappe.get_meta("Blanket Order Item").fields` xem có trường tiền (`rate`/`amount`) hay chỉ số lượng trước khi xếp mức độ nghiêm trọng. |
| 1 | NG-37f bảo vệ ghi (`bulk_update`/`save` trên doctype con gọi trực tiếp bằng docname) hiện AN TOÀN nhưng KHÔNG theo thiết kế | ⬜ (ghi nhận, không phải lỗ đang mở) | `set_value`/`insert`/`delete` an toàn NHỜ đi qua `.save()`/`.has_permission()` của DOCTYPE CHA thật (đúng `sales_has_permission`, đã xác nhận bằng probe: `PermissionError`/`DoesNotExistError`). `bulk_update` và `save` khi gọi trực tiếp bằng docname của DOCTYPE CON lại kiểm quyền ở MỨC DOCTYPE CON (role permission thô, không theo khách hàng) — hiện chặn được **chỉ vì** role `Customer` tình cờ không có `write` DocPerm trên `Sales Order Item`/`Delivery Note Item`/`Sales Invoice Item`. Nếu sau này ai cấp `write` cho role đó trên một trong ba doctype con (kể cả vô tình, qua Role Permission Manager) thì `bulk_update` cho phép ghi đè `rate`/`qty` của dòng hàng khách KHÁC mà không kiểm chủ sở hữu — leo thang quyền, không phải rò rỉ đọc. Xác nhận bằng probe (`PermissionError` từ `check_doctype_permission`, không phải từ so khớp khách hàng). |
| 1 | NG-12 precision tiền | ⬜ | 10 trường / **6** doctype (BA v2 ghi 8 — xem đính chính ở lộ trình §2) |
| 1 | NG-10 giá không lọc ngày | ⬜ | |
| 1 | NG-11 giá lấy tuỳ ý | ⬜ | Phải làm cùng NG-10, cùng một hàm |
| 1 | NG-09 VAT | ⬜ | QĐ-02 = **A** (có VAT, mẫu thuế theo khách hàng) |
| 1 | NG-08 báo giá chốt | ⬜ | Phụ thuộc NG-09, NG-10, NG-11 |
| 1 | NG-02 hợp đồng nháp | ⬜ | |
| 1 | NG-03 hợp đồng chưa hiệu lực | ⬜ | |
| 1 | NG-04 hợp đồng hết hạn giữa chừng | ⬜ | |
| 1 | NG-05 mặt hàng bị gỡ khỏi hợp đồng | ⬜ | |
| 1 | NG-01 hạn mức đơn nháp | ⬜ | QĐ-01 = **A** (giữ chỗ mềm, 3 ngày làm việc) |
| 1 | NG-31 huỷ phiếu giao không đảo được | ⬜ | Ba lớp: ToDo · cờ trên phiếu · báo cáo đối soát (API-08) |
| 1 | Giao diện: giỏ hàng + danh mục | ⬜ | Task 11 — bỏ phép tính VAT phía trình duyệt |
| 1 | UX-08 (khung + 3 mã) | ⬜ | Task 12 — bảng đầy đủ `MYN-E101…E107` để đợt 2 |
| 2–5 | *(xem lộ trình)* | ⬜ | |

**Thứ tự thi công đợt 1.** Task 1 và 2 độc lập, làm song song và ship riêng được. Từ
Task 3 là một chuỗi phụ thuộc trên cùng vài hàm — đảo thứ tự sẽ phải sửa lại thứ vừa viết:

```
T1 NG-37 ─┐ độc lập          T10 NG-31 ─ độc lập
T2 NG-12 ─┘                  T11 giao diện · T12 bản đồ lỗi

T3 NG-10/11 → T4 NG-09 → T5 NG-08(API-03) → T6 NG-08(API-04)
   → T7 NG-02…05 → T8 NG-01 (đọc) → T9 NG-01 (nhả chỗ)
```

---

## 2. Quyết định đã chốt — KHÔNG mở lại nếu chưa bàn

| Mã | Chốt ngày | Phương án | Ràng buộc kéo theo |
|---|---|---|---|
| **QĐ-01** | 2026-08-12 | **A** — giữ chỗ mềm, hết hạn **3 ngày làm việc** | Không sửa `blanket_order.py` của ERPNext. Hạn mức "thật" tính ở tầng cổng. |
| **QĐ-02** | 2026-08-12 | **A** — có VAT, `Sales Taxes and Charges Template` theo Customer | Dữ liệu 0/7 hoá đơn không thuế trên `erptest.local` là **dữ liệu thử**, không phải chủ ý nghiệp vụ. Cổng đang báo tổng tiền **thấp hơn** số phải trả. |
| **QĐ-03** | 2026-08-12 | **B** — lô chưa khai HSD nhóm riêng cuối báo cáo | Không loại khỏi báo cáo. Không bắt buộc nhập HSD khi ghi sổ. |
| **QĐ-04** | 2026-08-12 | **A** — giữ một tầng duyệt | Vẫn còn bước Miyano xác nhận → khoảng đơn nháp vẫn tồn tại → QĐ-01 A là cần thiết. Loại QĐ-01 B khỏi bàn. |

---

## 3. Các điểm chồng lấn đã biết — đọc trước khi mở file

Bốn chỗ này bị nhiều mã số cùng chạm. Ghi ra để người sau không sửa lại thứ vừa đổi hình dạng.

| Vị trí | Các mã cùng chạm | Thứ tự bắt buộc |
|---|---|---|
| `api/portal.py::portal_catalog` | NG-02, NG-03, NG-05, NG-09, NG-10, NG-11, NG-01, API-01 | NG-10/11 (hàm đọc giá) → NG-09 (thuế) → NG-02/03/05 (lọc) → NG-01 (cột giữ chỗ) → API-01 (đổi hình dạng trả về) |
| `api/portal.py::portal_order_place` | NG-01, NG-04, NG-08, NG-09, NG-10, NG-11, API-04 | NG-10/11 → NG-09 → NG-08/API-04 (nhận mã chốt) → NG-04 (kiểm ngày) → NG-01 (kiểm hạn mức thật) |
| `portal_context.py::remaining_qty` | NG-01, NG-05, NG-06 | NG-05 (tách "hết hạn mức" khỏi "không có trong hợp đồng") → NG-01 (trừ phần giữ chỗ) → NG-06 (quy đổi đơn vị, đợt 2) |
| `kho/delivery_hook.py::_chay_an_toan` | NG-31, NG-32 | NG-31 (báo động ba lớp). NG-32 **đang đúng** — ghi vào đây để không ai "sửa" chỗ đang đúng. |

**Ranh giới triển khai của đợt 1.** Task 3→11 là **một** đơn vị lên site: Task 6 làm
`quote` thành bắt buộc trên `portal_order_place`, Task 11 mới dạy giao diện gửi nó.
Giữa hai commit ấy **không khách nào đặt hàng được**. Chỉ `bench migrate` + restart trên
site thật khi cả chín task xong và bundle đã build. Task 1 · 2 · 10 · 12 lên riêng được.

**Ba chỗ tuyệt đối không đụng** (BA v2 đã kết luận là đang đúng):

- `kho/delivery_hook.py:245-255` `_phieu_dang_song()` khoá theo từng phiếu giao — **đúng**, đừng gộp.
- `kho/delivery_hook.py:225-230` xoá phiếu nháp mồ côi — **đúng** (NG-32), chỉ còn thiếu thông báo.
- `Customer Stock Ledger Entry` / `Customer Stock Lot Balance` **cố ý không** bật `track_changes` — đừng bật (BA v2 §NG-21).

---

## 4. Nhật ký thay đổi

### NG-37 · Rò rỉ sổ hoá đơn giữa các khách hàng — 2026-08-12 · commit a062f32
**Trước:** `frappe.desk.search.search_link` và `search_widget` nhận `ignore_user_permissions` từ client và chuyển thẳng xuống `get_list(ignore_permissions=True)`, bỏ qua toàn bộ `permission_query_conditions`. Một tài khoản cổng bất kỳ đọc được `Sales Order` / `Delivery Note` / `Sales Invoice` của khách khác, kèm `grand_total` và `outstanding_amount` qua `filter_fields`.
**Sau:** Cả hai endpoint được bọc qua `override_whitelisted_methods`. Với Website User: ép `ignore_user_permissions=False` (đây là dòng bịt lỗ thật sự — khôi phục `permission_query_conditions` theo hàng), null `query`/`filter_fields` như phòng thủ theo chiều sâu bổ sung, trả `[]` cho 8 doctype kho, nuốt `PermissionError` thành `[]`. Desk user đi thẳng qua bản gốc, không đổi hành vi.
**Đụng vào:** `miyano_portal/search_guard.py` (mới) · `miyano_portal/hooks.py` khối `override_whitelisted_methods` (số dòng đã lệch khỏi 279-288 ban đầu sau khi NG-37b mở rộng comment — dùng `grep -n override_whitelisted_methods` thay vì số dòng cứng)
**Phá vỡ:** Không. SPA không gọi hai endpoint này (đã grep). Desk không đổi.
**Test:** `miyano_portal/tests/test_search_guard.py` — 7 test, gồm một test RED đã chứng minh lỗ trước khi vá, một test assert Desk user không bị chặn, một test assert hooks đăng ký đủ cả hai.
**Cảnh báo chồng lấn:** `override_whitelisted_methods` từ nay **đã mở**. Ai thêm override sau này thì thêm khoá vào cùng dict, đừng khai lại biến.
**Phát hiện thêm khi quét 40 endpoint của app** (`@frappe.whitelist` trong `apps/miyano_portal`, không tính endpoint whitelist của bản thân framework Frappe/ERPNext): Grep thô `@frappe.whitelist` ra 41 dòng, nhưng một dòng là chuỗi nằm trong docstring của `search_guard.py` (không phải decorator thật) — số hàm whitelist thật là **40** (11 ở `api/portal.py`, 27 ở `api/kho.py`, 2 ở `search_guard.py`), đúng như kỳ vọng của brief (38 cũ + 2 mới). Đã đọc toàn bộ 40 hàm, trả lời hai câu (a) gọi được từ phiên cổng? (b) có kiểm gì ngoài quyền doctype? cho từng hàm:
  - Mọi hàm trong `api/portal.py` đều tự suy `customer` qua `get_portal_customer()` (dựa trên `frappe.session.user`), và một trong ba cách: dùng `frappe.get_list` (tôn trọng `permission_query_conditions` của `miyano_portal/permissions.py`), gọi tường minh `doc.check_permission("read")` trước khi trả dữ liệu (`portal_order_track`, `portal_request_cancel`, `portal_document_download`), hoặc kiểm sở hữu tham số client gửi trước khi dùng (`portal_catalog`, `portal_order_place` kiểm `contract`/`address` thuộc đúng khách). `portal_provision` có guard vai trò rõ ràng (chỉ `System Manager`/`Sales Manager`/`Sales User`), nên khách cổng gọi được nhưng bị chặn ngay ở dòng đầu.
  - Mọi hàm trong `api/kho.py` đều tự suy `kho` qua `get_portal_kho()` và kiểm sở hữu từng định danh do client gửi (`vat_tu`, `name` phiếu, `file_url`) qua `_vat_tu_cua_kho()` / `_phieu_cua_kho()` / so sánh `owner` trước khi chạm `frappe.get_doc`/`frappe.get_all` — đúng nguyên tắc "an toàn nhờ cấu trúc" đã ghi ở đầu file (role `Customer` không còn DocPerm nào trên 8 doctype kho).
  - **Phạm vi đã quét: đúng 40 endpoint `@frappe.whitelist` của app `miyano_portal`.** Trong phạm vi đó — sạch, không lỗ nào khác.
  - **Ngoài phạm vi đã quét (không phải endpoint của app), review vòng 1 phát hiện thêm một đường rò rỉ CẤP FRAMEWORK, độc lập với NG-37:** `frappe.client.get_list("Sales Order Item", fields=["parent","item_code","rate","amount"], parent="Sales Order")` — gọi được từ một tài khoản cổng bất kỳ — trả về dòng chi tiết (kèm `rate`/`amount`) của NHIỀU khách hàng khác nhau, trong khi `frappe.get_list("Sales Order")` (bảng cha) đã lọc đúng chỉ còn khách của người gọi. Cơ chế: `db_query.py:1305-1317` `check_parent_permission` chỉ gọi `has_permission("Sales Order")` KHÔNG kèm `doc` cụ thể (nên luôn True ở cấp doctype); `Sales Order Item` không có `permission_query_conditions` riêng trong `hooks.py:131-155`; và nhánh `istable` tại `db_query.py:1004-1008` bỏ qua luôn kiểm tra chia sẻ (shared-only) áp dụng cho bảng thường. Cùng họ lỗ áp dụng cho `Delivery Note Item` / `Sales Invoice Item`. **Không sửa trong task này** — đã mở dòng riêng ở bảng tiến độ §1 để bàn quyết định xử lý.
  - **Tiền lệ đã có trên bench này, nhưng KHÔNG cùng một điểm vào:** app `supplycore` (site khác, cùng bench) đã gặp và giải quyết một biến thể của họ lỗ này qua `frappe.client.get` (đọc MỘT bản ghi con theo tên/filter) — `supplycore/supplycore/hooks.py:170-175` override thành `supplycore.api.portal.guarded_client_get`, comment nêu đích danh SO Item / DN Item / SI Item (và SFC Item), cộng một `before_request` hook chặn riêng đường REST `/api/resource/<child>/<name>` (residual RSK-01) vì đường đó không đi qua `frappe.client.get`. Phát hiện lần này ở `miyano_portal` là qua `frappe.client.get_list` (đọc NHIỀU bản ghi con theo `parent=`) — một whitelisted method khác, dùng chung cơ chế `check_parent_permission` bên dưới nhưng KHÔNG bị chặn bởi bản vá `frappe.client.get` của supplycore. Bản `miyano_portal` này còn có 8 doctype kho, không phải 5 doctype cha kiểu supplycore. Hướng vá cần tự thiết kế lại (ít nhất phải cân nhắc cả `get` lẫn `get_list`, và cả đường REST list `/api/resource/<child>?parent=...`), không copy thẳng — nhưng cơ chế lỗ và cách chặn theo method-override + REST-path của supplycore là tài liệu tham khảo trực tiếp cho quyết định sắp tới.

### NG-37b · Rò rỉ dòng chi tiết chứng từ qua `frappe.client.get_list`/`get` — 2026-08-12 · commit 0b3cebb
**Trước:** `frappe.client.get_list`/`frappe.client.get` gọi `check_parent_permission(parent, doctype)` cho ba doctype con `Sales Order Item`/`Delivery Note Item`/`Sales Invoice Item`, hàm đó chỉ hỏi `has_permission(parent_doctype)` KHÔNG kèm `doc` cụ thể nên chỉ kiểm ở mức doctype, bỏ qua khách hàng của đơn. Đã chứng minh bằng probe HTTP thật: một tài khoản cổng đọc được `rate`/`amount` của dòng hàng thuộc năm khách hàng khác nhau.
**Sau:** Hai wrapper `client_get_list`/`client_get` (đăng ký qua `override_whitelisted_methods`, cùng dict NG-37 đã mở): với Website User, mọi lời gọi trên ba doctype con bị CHẶN THẲNG (không lọc) — `get_list` trả `[]`, `get` ném `frappe.PermissionError` tiếng Việt. Doctype khác và người dùng khác đi thẳng qua bản gốc, không đổi hành vi.
**Đụng vào:** `miyano_portal/search_guard.py` (thêm `_TU_CHOI_DONG_HANG`, `client_get_list`, `client_get`) · `miyano_portal/hooks.py` (thêm 2 khoá vào `override_whitelisted_methods` đã có sẵn)
**Phá vỡ:** Không. SPA không gọi `frappe.client.*` (đã grep `frontend/src`, `www/portal`). Desk không đổi (xác nhận bằng test `sales_user@demo.miyano`, System User thật không phải Administrator).
**Test:** `miyano_portal/tests/test_client_guard.py` — 8 test, gồm RED gate (throwaway, gọi thẳng `frappe.client.get_list`/`get` GỐC, xác nhận FAIL trước khi vá — log verbatim ở `task-1b-report.md`), test chặn cả ba doctype con, test doctype khác vẫn lọc đúng theo `permission_query_conditions` sẵn có, test Desk user không bị chặn nhầm, và **hai test kiểm dispatch thật** (`frappe.override_whitelisted_method(...)`) chứ không chỉ nội dung dict `frappe.get_hooks(...)` — vì Task 1 tự ghi nhận đây là khoảng trống chưa kiểm.
**Cảnh báo chồng lấn:** `override_whitelisted_methods` tiếp tục dùng chung dict với NG-37. Đừng khai lại biến.

**PHẠM VI CHƯA ĐÓNG — quan trọng, đọc trước khi coi lỗ đã bịt xong.** `override_whitelisted_method()` (`frappe/__init__.py:2543`) chỉ được gọi ở `handler.py:67` (route `/api/method/<cmd>`) và `v2.py:36` (route `/api/v2/method/<cmd>`) — hai route NG-37b vừa đóng. Trong lúc làm Step 7 của brief, đã dò thêm và **xác nhận bằng probe HTTP thật** (đọc, không ghi — an toàn với dữ liệu thật trên `erptest.local`) ba nhóm đường vòng KHÁC, ghi thành các dòng sổ theo dõi riêng ở bảng §1 (không sửa trong task này, đúng yêu cầu "không mở rộng phạm vi âm thầm"):

- **NG-37c — REST list/đọc đơn.** `/api/resource/<doctype>` (v1, `api/v1.py::document_list`) và `/api/v2/document/<doctype>` (v2) đều gọi `frappe.call(frappe.client.get_list, doctype, **form_dict)` bằng THAM CHIẾU HÀM trực tiếp, không qua tra cứu chuỗi tên → override không bao giờ được gọi tới. Probe thật: `GET /api/resource/Sales%20Order%20Item?parent=Sales%20Order&limit_page_length=0` với phiên `bvbm@demo.miyano` trả **41 dòng** hàng của ít nhất năm mã đơn khác nhau (SAL-ORD-2026-00004 .. 00018), kèm `rate`/`amount` — y hệt lỗ NG-37b nhưng qua cổng vào khác. Tương tự, `/api/resource/<doctype>/<name>/` và `/api/v2/document/<doctype>/<name>/` (đọc MỘT bản ghi) không hề gọi `frappe.client.get` — gọi thẳng `frappe.get_doc()` rồi `doc.has_permission("read")`/`check_permission("read")`, dính đúng lỗi `has_child_permission()` mô tả ở dòng dưới. Probe thật: `GET /api/resource/Sales%20Order%20Item/2r7asrt84t/` (dòng hàng thuộc đơn của khách "Bệnh viện Minh Đức") trả đầy đủ field kể cả `rate`/`amount`/`valuation_rate`/`gross_profit` cho phiên `bvbm@demo.miyano`.
- **NG-37d — `get_value`/`validate_link`/`has_permission` cùng họ.** `frappe.client.get_value` (client.py:146) gọi hàm `get_list` **nội bộ của chính module `client.py`** (tham chiếu Python cùng file, không phải bản đã override) — probe thật: `GET /api/method/frappe.client.get_value?doctype=Sales+Order+Item&fieldname=rate&filters={"parent":"SAL-ORD-2026-00018"}&parent=Sales+Order` trả `{"message":{"rate":1250000.0}}` cho phiên `bvbm@demo.miyano` (đơn thuộc khách khác). `validate_link` (client.py:476) gọi `get_value` nên cùng cơ chế. `frappe.client.has_permission(doctype, docname, perm_type)` truyền `docname` dạng CHUỖI vào `has_child_permission()` — nhánh này tưởng an toàn hơn (tự fetch lại `parent`/`parenttype` thật từ DB qua `frappe.db.get_value(..., as_dict=True)`) nhưng vẫn dính bẫy: kết quả fetch là `frappe._dict`, và `_dict.__getattr__ = dict.get` (`frappe/types/frappedict.py:5`) không bao giờ ném `AttributeError`, nên `getattr(child_doc, "parent_doc", child_doc.parent)` (`permissions.py:841`) đọc `child_doc.parent_doc` → `dict.get(..., "parent_doc")` → `None` thành công (không rơi về giá trị mặc định `child_doc.parent` như tưởng) → vẫn resolve `doc=None` → vẫn suy biến về kiểm mức doctype. Xác nhận bằng probe trực tiếp trong test harness: `client.has_permission("Sales Order Item", <dòng hàng khách khác>, "read")` trả `{"has_permission": True}` — sai.
- **NG-37e — `Blanket Order Item` chưa xác nhận.** Cha `Blanket Order` cũng có `blanket_query`/`generic_has_permission` giống ba doctype con NG-37b đã vá, nên lý thuyết cùng họ lỗ. KHÔNG thêm vào deny-list của NG-37b vì đó là mở rộng phạm vi âm thầm ngoài ba doctype brief giao — mở dòng riêng, chưa probe.
- **NG-37f — bảo vệ GHI hiện an toàn nhưng "tình cờ", không theo thiết kế.** Đã probe (an toàn, trong `FrappeTestCase`, rollback theo lớp): `set_value`/`insert`/`delete` trên dòng hàng của khách khác đều bị chặn (`PermissionError`/`DoesNotExistError`) VÌ cả ba đều load DOCTYPE CHA thật rồi gọi `.save()`/`.has_permission("write")` trên đó — đi đúng qua `sales_has_permission` đã có. Nhưng `bulk_update` và `save` khi được gọi TRỰC TIẾP bằng docname của doctype CON (không qua cha) thì kiểm quyền ở MỨC DOCTYPE CON — hiện bị chặn (`check_doctype_permission` → `PermissionError`) chỉ vì role `Customer` tình cờ không có `write` DocPerm trên ba doctype con này. Nếu sau này ai cấp `write` cho role đó (kể cả vô tình) thì `bulk_update`/`save` sẽ cho ghi đè `rate`/`qty` của dòng hàng THUỘC KHÁCH KHÁC mà không kiểm chủ sở hữu — leo thang quyền, đúng loại "tệ hơn rò rỉ" mà brief cảnh báo. Ghi nhận, không sửa (không có write DocPerm nào đang mở để khai thác ngay bây giờ).

**Kết luận trung thực cho người đọc sổ này (cập nhật sau Task 1c, 2026-08-12 — xem entry NG-37c bên dưới):** NG-37b đóng đúng hai route mà brief giao (`/api/method`, `/api/v2/method`, cho `get_list`/`get`) — **trên CẢ HAI trục**: trục ROUTE (chỉ hai route đó) VÀ trục DOCTYPE (mọi doctype con `frappe.is_table`, không riêng ba doctype PoC gốc — round 1 chỉ đóng trục route và fail OPEN trên trục doctype, đã sửa thành Critical C1 round 1, xem bên dưới). Task 1c đã đóng thêm trục ROUTE REST (`/api/resource`, `/api/v1/resource`, `/api/v2/document`, xem entry NG-37c). **VẪN CÒN MỞ, không phụ thuộc doctype nào: trục HÀM `get_value`/`validate_link`/`has_permission` (NG-37d)** — một kẻ tấn công biết route `/api/method/frappe.client.get_value` (kèm `parent=` đúng) vẫn khai thác được y hệt PoC gốc, trên bất kỳ doctype con nào. Đừng báo cáo lỗ "đã đóng" mà không kèm theo dòng NG-37d này.

#### Fix round 1 — review round 1, 2026-08-12 · commit 880c032

**Critical C1 — guard fail OPEN trên trục doctype.** Bản vá NG-37b ban đầu (commit
`0b3cebb`) dùng deny-set liệt kê tên (`_TU_CHOI_DONG_HANG = {"Sales Order Item",
"Delivery Note Item", "Sales Invoice Item"}`) — allow-by-omission: MỌI doctype con
KHÁC ba tên đó vẫn lọt qua nguyên trạng, dù cùng dính một lỗ `check_parent_
permission()` y hệt. Reviewer probe thật, gọi thẳng wrapper đã vá:
```
client_get_list("Payment Schedule", parent="Sales Invoice",
                fields=["parent","parenttype","payment_amount","outstanding"],
                limit_page_length=0)   → 26 rows
  ACC-SINV-2026-00001  13,900,000 / 13,900,000  → Bệnh viện Đa khoa Miyano
  SAL-ORD-2026-00018    4,394,000 /  4,394,000  → Bệnh viện Đa khoa Minh Đức
client_get("Payment Schedule", name="2c95j77b6v", parent="Sales Invoice")
  → {'parent': 'ACC-SINV-2026-00003', 'payment_amount': 14760000.0, 'outstanding': 14760000.0}
```
`outstanding` là chính loại field NG-37 tồn tại để chặn. Cũng còn lộ: `Sales Taxes
and Charges` (`rate`/`tax_amount`/`total`/`base_total`), `Sales Invoice Payment`,
`Sales Invoice Advance`, `Packed Item`, `Sales Team`, `Pricing Rule Detail`. Reviewer
còn chỉ ra: `parent=` do client gửi chỉ là CHÌA KHOÁ TRA QUYỀN cho
`check_parent_permission()`, không phải điều kiện lọc hàng — một `parenttype` mà
role có read là đủ mở TOÀN BỘ bảng con dùng chung, kể cả dòng thuộc `parenttype`
khác mà role không có read (thấy rõ trong output trên: gọi `parent="Sales Invoice"`
nhưng có dòng `parenttype: Sales Order`).

**Sửa:** đổi gate từ `doctype in _TU_CHOI_DONG_HANG` sang `frappe.is_table(doctype)`
trong cả `client_get_list` và `client_get` — bỏ hẳn deny-set liệt kê tên. Đúng nguyên
tắc Step 3 của brief ("deny-list role cổng trên endpoint nội bộ, đừng allow-list
từng hàm") áp dụng luôn cho trục doctype, không chỉ trục hàm.

**Critical C2 (hệ quả C1) — ba chỗ ghi ngược sự thật, sửa cùng lúc:** cập nhật
`docs/CHANGELOG-khac-phuc-BA-v2.md` (mục này + bảng tiến độ §1 + "Kết luận trung
thực" ở trên), `miyano_portal/hooks.py` (khối `CẢNH BÁO PHẠM VI`), và docstring đầu
`miyano_portal/search_guard.py` — cả ba giờ nêu đủ HAI trục còn mở (route, hàm),
không chỉ liệt kê theo route/hàm như trước khiến người đọc tưởng trục doctype đã an
toàn.

**Test:** thêm `TestClientGuardC1Regression` (3 test) vào `test_client_guard.py`,
dùng `Payment Schedule` — CỐ Ý một doctype ngoài tập ba tên cũ, dữ liệu THẬT có sẵn
trên site, chỉ đọc — để chứng minh gate mới không phụ thuộc danh sách tên lẫn giá
trị `parent=` client gửi. RED cho C1 KHÔNG tự tái tạo trong task này (bản vá round 1
đã bị ghi đè trước khi review tới) — bằng chứng RED là probe thật của reviewer,
trích nguyên văn ở trên.

**Minor bundle (M2-M4):**
- M2: sửa câu "ba doctype con của bốn doctype cha" ở `search_guard.py` (số đếm sai
  từ trước, giờ moot vì gate không còn liệt kê tên, nhưng câu văn đã sửa).
- M3: sửa comment ở `search_guard.py` nói ngược thứ tự thực thi (tưởng framework
  role-check chạy TRƯỚC wrapper — thực ra wrapper chạy trước, framework check chỉ
  chạy bên trong nhánh delegate nếu wrapper không chặn). Với gate mới, mọi doctype
  con của 8 doctype kho cũng bị wrapper tự chặn trực tiếp (không cần lý luận qua
  vai trò `Customer` thiếu DocPerm nữa) — đơn giản hơn, comment đã viết lại.
- M4: `test_client_guard.py` thêm tiền điều kiện `frappe.get_all(...) ` không rỗng
  trước khi assert `client_get_list(...) == []` cho `Delivery Note Item`/`Sales
  Invoice Item` — tránh pass vô nghĩa nếu site không có dữ liệu.
- M1: thêm dòng `frappe.client.get_count` vào bảng Step 7 trong `task-1b-report.md`
  (đã bỏ sót trong báo cáo trước) — reviewer probe: `PermissionError` khi thiếu
  `parent`, không rò rỉ.

### NG-37c · Chặn REST resource/document cho doctype con — 2026-08-12 · commit 040c929

**Trước:** `/api/resource/<doctype>` (v1, hai submount `/api` và `/api/v1`) và
`/api/v2/document/<doctype>` (v2) gọi thẳng `frappe.client.get_list`/dispatch tới
`has_child_permission()` bằng THAM CHIẾU HÀM Python, không qua tra cứu chuỗi tên —
`override_whitelisted_methods` (NG-37b) không bao giờ được hỏi tới, dù doctype có
`is_table` hay không. Probe thật xác nhận cả list lẫn `<name>` đơn lẻ đều lộ
`rate`/`amount`/`outstanding`/`payment_amount` của khách khác — xem entry NG-37b ở
trên, mục "NG-37c — REST list/đọc đơn".

**Sau:** hook `before_request` mới (`miyano_portal.rest_guard.chan_rest_doctype_con`)
chặn Ở TẦNG ĐỊNH TUYẾN HTTP, trước khi request kịp rẽ vào một trong hai đường lỗ
trên: với khách cổng (`search_guard._la_khach_cong()`, TÁI SỬ DỤNG, không viết bản
thứ ba) và MỘT doctype con bất kỳ (`frappe.is_table(doctype)` — KHÔNG liệt kê tên,
đúng nguyên tắc NG-37b round 2 áp dụng tiếp cho trục ROUTE), mọi GET trên ba prefix
`/api/resource/`, `/api/v1/resource/`, `/api/v2/document/` (list lẫn `<name>` đơn
lẻ) đều bị `frappe.PermissionError` tiếng Việt, HTTP 403. Doctype CHA (`frappe.
is_table()` == False) không đụng tới — đã có `permission_query_conditions` lọc
đúng từ Task 1.

**Đụng vào:** `miyano_portal/rest_guard.py` (mới) · `miyano_portal/hooks.py` khối
`before_request` (mới) + cập nhật comment `CẢNH BÁO PHẠM VI` ở khối
`override_whitelisted_methods` (ghi rõ trục ROUTE nay đã đóng, chỉ còn trục HÀM
NG-37d mở).

**Phá vỡ:** không. SPA không dùng `/api/resource`/`/api/v2/document` (đã grep
`frontend/src/` xác nhận trước khi chặn — mọi lời gọi từ SPA đều qua
`/api/method/miyano_portal.api.*`). Desk user (`sales_user@demo.miyano`, System
User thật) đọc REST child doctype bình thường sau fix — đã probe HTTP thật xác
nhận.

**Test:** `miyano_portal/tests/test_rest_guard.py` — 5 test method HTTP THẬT (không
gọi hàm Python trong tiến trình — lỗ nằm ở tầng định tuyến, gọi thẳng hàm sẽ pass vô
nghĩa), đăng nhập thật `bvbm@demo.miyano` qua `/api/method/login`, GET cả ba prefix
× cả hai dạng (list, `<name>` đơn lẻ) cho `Sales Order Item` VÀ `Payment Schedule`
(ca bắt buộc theo brief, mang `outstanding`/`payment_amount`, doctype đã lật tẩy
Critical C1 của Task 1b), cộng một test doctype CHA (`Sales Order`) vẫn hoạt động
đúng. RED gate commit riêng trước fix (`efebf95` — 5 test method, 15 subTest
failures), giữ nguyên trong lịch sử git, không bị ghi đè.

**RED (verbatim, trích, xem `task-1c-report.md` cho đầy đủ):**
```
AssertionError: 200 != 403 : /api/v2/document/Payment Schedule (parent=Sales Order)
phải trả 403, thực tế 200: {"data":[{"parent":"ACC-SINV-2026-00001",
"parenttype":"Sales Invoice","payment_amount":13900000.0,"outstanding":13900000.0},
...
Ran 5 tests in 2.785s
FAILED (failures=15)
```

**GREEN (verbatim curl, sau fix + restart gunicorn):**
```
$ curl ... "http://127.0.0.1:8002/api/v2/document/Payment%20Schedule" \
    --data-urlencode "parent=Sales Invoice" \
    --data-urlencode "fields=[\"parent\",\"parenttype\",\"payment_amount\",\"outstanding\"]"
HTTP 403
{"errors":[{"type":"PermissionError", ...,
  "message":"Không có quyền truy cập dữ liệu này", ...}]}
```

**Cảnh báo chồng lấn:** `before_request` là danh sách mới (app này chưa có entry
nào trước Task 1c) — nếu một task khác cần thêm `before_request` hook riêng, PHẢI
nối vào cùng list này (`hooks.py` chỉ đọc MỘT khối `before_request = [...]` cho mỗi
app), không khai một khối `before_request` thứ hai đè lên khối này.

**Step 7 (bắt buộc theo brief) — quét nốt trục HÀM còn lại của NG-37d:** re-probe
độc lập, dùng `Payment Schedule` (không phải ba doctype PoC gốc) thay vì tin lại kết
quả Step 7 của Task 1b:
- `frappe.client.get_value` — **CÒN MỞ.** `GET /api/method/frappe.client.get_value
  ?doctype=Payment+Schedule&parent=Sales+Invoice&fieldname=["parent","parenttype",
  "payment_amount","outstanding"]` (phiên `bvbm@demo.miyano`) → trả dòng của khách
  KHÁC (`ACC-SINV-2026-00001`, `outstanding: 13900000.0`). Lưu ý dễ hiểu lầm: gọi
  THIẾU `parent=` thì tự `PermissionError` (do `check_parent_permission(None, ...)`
  luôn `raise` khi `parent` rỗng, `db_query.py:1318`) — trông như đã chặn, nhưng chỉ
  cần thêm đúng `parent=<parenttype thật>` là lọt hoàn toàn. KHÔNG phải phòng thủ
  thật, không được coi là "đã đóng một phần".
- `frappe.client.validate_link` — **CÒN MỞ.** `GET /api/method/frappe.client.
  validate_link?doctype=Payment+Schedule&docname=<dòng khách khác>` → trả
  `{"message":{"name": ...}}` (không ném lỗi) thay vì `PermissionError`.
- `frappe.client.has_permission` — **CÒN MỞ (oracle, không lộ field).** `GET /api/
  method/frappe.client.has_permission?doctype=Sales+Order+Item&docname=<dòng khách
  khác>&perm_type=read` → `{"message":{"has_permission": true}}` — sai, nhưng chỉ
  lộ một boolean, không lộ `rate`/`amount` trực tiếp như hai hàm trên.

Cả ba **CHƯA sửa trong Task 1c** — đúng brief "nếu còn mở thì ghi mã số riêng, đừng
lặng lẽ mở rộng task". Đã cập nhật bảng tiến độ §1 (NG-37d) với bằng chứng re-probe
này; mã số NG-37d đã tồn tại từ Step 7 của NG-37b nên không mở số mới.
