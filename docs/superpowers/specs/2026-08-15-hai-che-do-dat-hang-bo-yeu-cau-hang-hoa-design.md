# Cổng chỉ còn hai chế độ đặt hàng — bỏ "Yêu cầu hàng hoá" khỏi cổng khách

Ngày 2026-08-15 · Chủ dự án đã duyệt qua đối thoại
**Thay thế §4.7** của `2026-08-14-mua-le-toan-danh-muc-design.md` (§4.1–4.6 của tài liệu đó vẫn còn hiệu lực).

---

## 1. Hiện trạng đã kiểm trên nhánh `feature/mua-le-toan-danh-muc`

Kiểm ngày 15/08, cây làm việc sạch, commit gần nhất `e96824a`.

**Đã xong ở back-end** (thiết kế 14/08 §4.1–4.6):

- `portal_catalog_ban_le` trả toàn bộ `Item` đang hoạt động, phân trang phía SQL, **không trả trường giá nào** (`api/portal.py:258–354`).
- Bảng con `Sales Order Dat Ngoai Item` + custom field `custom_dat_ngoai` tồn tại; `portal_order_place(mode="ban_le")` nhận tham số `dat_ngoai`, validate tên hàng/ĐVT/số lượng và ghi vào bảng con (`api/portal.py:546–710`).
- Chốt `before_submit` chặn xác nhận đơn khi còn dòng đặt ngoài chưa khớp mã (`portal_mua_le.kiem_dat_ngoai_da_xu_ly`).
- Job đóng báo giá quá hạn + email hai phía (`portal_bao_gia.quet_bao_gia_het_han`).

**Chưa xong — và đang làm màn Mua lẻ hỏng trên thực tế:**

| Sự thật đã kiểm | Hệ quả trên cổng hôm nay |
|---|---|
| `Catalog.vue:508` đọc `it.co_gia`, `it.gia_ban_le` — hai trường back-end **không còn trả** | Mọi mặt hàng rơi vào nhánh `v-else-if="!it.co_gia"` → hiện "Chưa có giá lẻ" + nút "Yêu cầu báo giá" |
| `store.js:86–95` tính `cartLeSubtotal`/`cartLeTotal` từ `l.rate` | Giỏ Mua lẻ luôn hiện **0 ₫** |
| `frontend/src` **không có một dòng `dat_ngoai` nào** | Khách **chưa** gõ được vật tư mới — bảng con back-end không có đường nào nhận dữ liệu từ cổng |
| `Catalog.vue:476, 508, 531` còn nguyên hai nút "Yêu cầu báo giá" và "Gửi yêu cầu cho Miyano" | §4.7 của thiết kế 14/08 được quyết nhưng **chưa bao giờ áp dụng** |

**Dữ liệu:** `Portal Item Request` có **0 bản ghi** trên `erptest.local`; `Sales Order` có `custom_yeu_cau_goc` khác rỗng: **0**. Bỏ khỏi cổng không mất dữ liệu nào.

**Màn dự trù (E5) chưa dựng ở SPA** — không có view nào cho nó, nên đường vào thứ ba "Nhờ Miyano tìm nguồn" chưa từng tồn tại để mà gỡ.

---

## 2. Bốn quyết định của chủ dự án

1. **"Yêu cầu hàng hoá" bỏ khỏi cổng khách, GIỮ phía Miyano Desk.** Lý do khách hàng nêu ra hoàn toàn hướng về phía khách ("khách không cần biết Miyano có gì"); back-office vẫn cần công cụ theo dõi nhu cầu.
2. **Cổng chỉ còn hai chế độ đặt hàng:** Theo hợp đồng khung | Mua lẻ.
3. **Mua lẻ mặc định BẬT cho mọi khách**, cờ giữ lại để tắt riêng khi cần.
4. **Có PDF báo giá tải được**, không dùng doctype `Quotation` của ERPNext.

Nguyên tắc nền, nhắc lại từ thiết kế 14/08 vì mọi quyết định dưới đây đều suy ra từ nó:

> **Khách không cần biết Miyano có gì; họ đặt hàng, Miyano có trách nhiệm gửi hàng.**

---

## 3. Thiết kế

### 3.1 Hai chế độ và cách gọi tên

Bộ chuyển trên màn Đặt hàng: **`Theo hợp đồng khung` | `Mua lẻ`**. Không còn đường thứ ba.

Chỉ đổi **nhãn hiển thị**. Mã nghiệp vụ và tên trường giữ nguyên "HĐNT" (`custom_hdnt`, `thuoc_hdnt`, `mode="hdnt"`, BR-O*, QT2, Blanket Order). Đổi mã sẽ cắt liên kết giữa code và toàn bộ tài liệu BA — cái giá không tương xứng với lợi ích của một từ.

Chuỗi cần đổi trên UI: `Catalog.vue` (nhãn bộ chuyển), badge `"Có trong HĐNT — đặt ở chế độ Theo HĐNT"` → `"Có trong hợp đồng khung — đặt ở chế độ Theo hợp đồng khung"`, tiêu đề ngăn giỏ trong `Cart.vue`, `Dashboard.vue`, `Orders.vue`, `OrderDetail.vue`.

### 3.2 Gỡ "Yêu cầu hàng hoá" khỏi cổng

**Xoá ở SPA:**

- `App.vue:15` mục nav `📨 Yêu cầu hàng hoá`; `App.vue:37` nhánh `isActive('yeu-cau')`; `App.vue:44` hai tên route trong nhánh `profile`.
- `router.js:22–23, 32–33` — hai import và hai route.
- Ba file: `views/YeuCauList.vue`, `views/YeuCauDetail.vue`, `components/YeuCauModal.vue`.
- `Profile.vue:107` nút "Xem yêu cầu hàng hoá →".
- `Catalog.vue`: import `YeuCauModal`, hai hàm `moYeuCauKhongThay`/`moYeuCauBaoGia`, state `ycModalOpen`/`ycPrefill`, hai nút ở dòng 476 và 508, khối `<p>` ở 531, thẻ `<YeuCauModal>` ở 544.
- `format.js:102 yeuCauBadge()` — chỉ còn màn Yêu cầu dùng; xoá cùng.

**Xoá ở back-end — 6 endpoint whitelist trong `api/portal.py`:**

`portal_yeu_cau_list` · `portal_yeu_cau_detail` · `portal_yeu_cau_save` · `portal_yeu_cau_cancel` · `portal_yeu_cau_tra_loi` · `portal_yeu_cau_file` · và hàm phụ trợ chỉ phục vụ chúng (`_yeu_cau_*`, kiểm trùng gần đúng tên).

**GIỮ NGUYÊN, không đụng:**

| Giữ | Vì sao |
|---|---|
| Doctype `Portal Item Request` + JSON | Nhân viên Miyano vẫn lập/xử lý trên Desk (quyết định 1) |
| Báo cáo `demand_pipeline_yêu_cầu_hàng_hoá` + `setup/install_e6_desk_reports.py` | Công cụ back-office, không liên quan cổng |
| Job `portal_sla.quet_yeu_cau_qua_han` + `Settings.sla_yeu_cau_gio` | SLA 48h vẫn áp cho yêu cầu do nhân viên lập |
| `hooks.py:153` `permission_query_conditions` và `hooks.py:192` `has_permission` | Gỡ đường vào, **không gỡ hàng rào**. Role `Customer` không còn endpoint nào chạm doctype này, nhưng bỏ chốt phân quyền là mở sẵn lỗ hổng cho lần sau |
| `Sales Order.custom_yeu_cau_goc` + `portal_mua_le.cap_nhat_yeu_cau_goc` | Sales vẫn lập SO từ một yêu cầu trên Desk; liên kết truy vết còn ý nghĩa |
| `test_kho_isolation.py:71` — `Portal Item Request` trong `KHO_DOCTYPES_KHAC` | Doctype vẫn thuộc module `Miyano Portal` và vẫn mang `customer`. Lưới an toàn `_nap_doctype_kho()` **ném lỗi** với doctype nó không phân loại được; bỏ tên này ra là làm hỏng chính cơ chế đó |

**Xoá test:** `tests/test_e6_yeu_cau.py` — mọi test trong đó gọi endpoint cổng đã biến mất.

### 3.3 Đồng bộ màn Mua lẻ với back-end không giá

Đây là **sửa lỗi**, không phải tính năng mới: front-end đang đọc trường back-end đã bỏ.

`Catalog.vue`, ngăn Mua lẻ:

- Bỏ hẳn nhánh `v-else-if="!it.co_gia"` và mọi tham chiếu `it.gia_ban_le`, `it.co_gia` (cả bảng desktop lẫn thẻ mobile).
- Mỗi dòng còn: mã · tên · quy cách · ĐVT · badge `trang_thai_hang` · stepper số lượng · nút thêm giỏ.
- Dòng `thuoc_hdnt` giữ nguyên: hiện mờ + badge lý do + link chuyển chế độ. **Chốt chống né hạn mức BR-R7 không được nới** — đây là thứ giữ cho toàn bộ cơ chế hạn mức của E1 có nghĩa; từng là lỗi Critical ở vòng review E6.
- Dòng `san_sang_ban = false` giữ nguyên khoá nút + thông báo "Miyano đang cập nhật".
- Ô tìm kiếm ngăn Mua lẻ gọi server (`tim_kiem`, `start`, `limit`) — **không** lọc phía client như ngăn hợp đồng khung, vì danh mục là toàn bộ `tabItem`, có thể vài nghìn mã. Debounce 300ms; nút "Tải thêm" theo `tong`.

`store.js`, ngăn `cartLe`:

- Bỏ `cartLeSubtotal`, `cartLeVat`, `cartLeTotal` — **không còn giá để cộng**. Ngăn lẻ chỉ đếm số dòng.
- `cartCount` giữ nguyên (tổng số dòng hai ngăn).
- Thanh giỏ nổi ở `Catalog.vue:540` đang hiện `store.cartTotal + store.cartLeTotal` → chỉ hiện tiền của ngăn hợp đồng khung, ngăn lẻ hiện số dòng.

`Cart.vue`, ngăn Mua lẻ:

- Bỏ cột đơn giá / thành tiền / VAT và khối tổng cộng.
- Thay bằng dòng chú thích: **"Miyano sẽ báo giá sau khi tiếp nhận đơn. Bạn xác nhận giá trước khi đơn được giao."**

Ngăn Theo hợp đồng khung **không đổi gì** — ở đó giá đến từ hợp đồng và vẫn hiện đầy đủ.

### 3.4 Khối "hàng chưa có trong kho, cần đặt ngoài"

Phần việc mới lớn nhất. Back-end đã sẵn sàng; đây là dựng đường vào cho khách.

**Ở `Catalog.vue`, ngăn Mua lẻ**, ngay chỗ nút "Gửi yêu cầu cho Miyano" cũ đứng — một khối gấp/mở:

> **Không tìm thấy vật tư cần mua?**
> Ghi thẳng vào đây. Miyano sẽ tìm nguồn và báo giá cho bạn.

Bảng nhập nhiều dòng, mỗi dòng: `Tên hàng` (bắt buộc) · `ĐVT` (bắt buộc) · `Số lượng` (bắt buộc, > 0) · `Ghi chú` · nút xoá dòng. Nút "+ Thêm dòng".

Khi ô tìm kiếm không ra kết quả: mở sẵn khối này và **prefill từ khoá vừa gõ vào `Tên hàng`** — đúng chỗ và đúng ý định mà nút "Gửi yêu cầu" cũ phục vụ, nhưng ở lại trên chính phiếu mua thay vì đẩy sang chứng từ khác.

**Ở `store.js`:** ngăn thứ ba `cartDatNgoai` — mảng, **không** phải map theo `item_code` (các dòng này chưa có mã; hai dòng cùng tên là hợp lệ). `cartCount` cộng thêm độ dài mảng này.

**Ở `Cart.vue`, ngăn Mua lẻ:** hiện các dòng đặt ngoài thành một nhóm riêng dưới nhóm hàng có mã, tiêu đề **"Hàng chưa có mã — Miyano sẽ tìm nguồn"**, sửa/xoá được tại chỗ. Gửi lên qua tham số `dat_ngoai` đã có sẵn của `portal_order_place`.

Đơn Mua lẻ **được phép chỉ có dòng đặt ngoài** (không có dòng hàng có mã nào)?
→ **Không.** `_xay_don_ban_le` hiện đã bắt `items` khác rỗng, và ERPNext bắt buộc `Sales Order` có ít nhất một dòng hợp lệ. Client phải chặn sớm với thông báo rõ: *"Đơn cần ít nhất một mặt hàng chọn từ danh mục. Nếu tất cả đều là hàng chưa có mã, vui lòng liên hệ Miyano."* Đây là **giới hạn kỹ thuật cứng của ERPNext**, không phải lựa chọn thiết kế — ghi rõ để không ai định "sửa cho tiện" về sau.

**Ở `OrderDetail.vue`:** đơn Mua lẻ hiện hai nhóm tách bạch — hàng có mã, và **"Đang chờ Miyano xác nhận nguồn"** cho các dòng `custom_dat_ngoai` chưa có `item_khop`. Dòng đã khớp mã chuyển sang nhóm trên, kèm ghi chú nhỏ "(từ yêu cầu: <tên khách gõ>)" để khách đối chiếu được cái mình gõ với cái Miyano khớp.

**Endpoint đọc:** `portal_order_track`/`portal_order_history` phải trả `custom_dat_ngoai` cho đơn Mua lẻ — kiểm và bổ sung nếu thiếu.

### 3.5 Mua lẻ mặc định BẬT

Patch mới (`patches/v1_13/`, idempotent):

1. Đổi `default` của custom field `Customer.custom_cho_phep_mua_le` thành `1`.
2. `UPDATE tabCustomer SET custom_cho_phep_mua_le = 1 WHERE ifnull(custom_cho_phep_mua_le, 0) = 0` — bật cho toàn bộ khách hiện hữu.

Chốt server `dam_bao_duoc_mua_le()` và mã lỗi 403 `khong_duoc_mua_le` **giữ nguyên**. Chỉ đổi giá trị mặc định, không bỏ chốt: sales vẫn tắt được cho một khách cụ thể (ví dụ khách đang nợ quá hạn, chỉ cho mua theo hợp đồng).

`Catalog.vue` bỏ điều kiện ẩn bộ chuyển khi `cho_phep_mua_le` sai? → **Không.** Cờ vẫn còn tác dụng; UI vẫn phải tôn trọng nó.

### 3.6 PDF báo giá

Luồng trạng thái **không đổi** (E2/E6.5): SO nháp → sales điền giá ở Desk → "Chờ khách đồng ý" → khách đồng ý trên cổng → duyệt theo ngưỡng → giao. Thêm đúng một chứng từ in.

**Print Format "Báo giá / Quotation"**, doc_type `Sales Order`, song ngữ, cài qua `setup/install_print_formats.py` theo đúng khuôn `FORMATS` hiện có + patch idempotent.

Nội dung bắt buộc: mã đơn · khách hàng · ngày lập · **hạn hiệu lực báo giá** (đọc từ `portal_mua_le.han_hieu_luc_bao_gia(so)`, tính từ `custom_ngay_gui_khach_duyet` — **không phải** `transaction_date`) · bảng hàng có mã (mã, tên, ĐVT, SL, đơn giá, VAT, thành tiền) · tổng cộng · tiền `1.234.567 ₫` không thập phân, ngày `dd/mm/yyyy`.

**Phải in cả dòng `custom_dat_ngoai` đã khớp mã.** Nếu không, khách nhận bản báo giá thiếu đúng những món họ tự gõ vào — chính phần họ lo nhất.

**Trên Desk:** nút `Gửi báo giá` trên `Sales Order` (client script hoặc `Notification`) — chuyển trạng thái sang "Chờ khách đồng ý" và gửi email kèm PDF cho khách + sales phụ trách, dùng lại `portal_bao_gia._email_khach()` / `_email_sales_phu_trach()`.

**Trên cổng:** khối "Chờ bạn đồng ý" trên `OrderDetail.vue` (đang có ở dòng ~247, cạnh nút "✔ Đồng ý đặt hàng") thêm nút **`Tải báo giá (PDF)`** → endpoint mới `portal_bao_gia_pdf(name)`:

- Suy khách từ **phiên đăng nhập** (`get_portal_customer()`), **không nhận `customer` từ client** — Quyết định nền số 7.
- Kiểm sở hữu đơn tường minh trước khi sinh PDF (`frappe.get_doc` **không** tự kiểm quyền trong bản này).
- Trả PDF qua response, **không sinh URL file công khai** — Quyết định nền số 8. Người dùng cổng không dùng được `/printview`.
- Chỉ cho tải khi đơn ở "Chờ khách đồng ý" trở đi — không lộ giá nháp sales chưa gửi.

---

## 4. Ràng buộc giữ nguyên

- **BR-R7** — hàng đang thuộc hợp đồng khung còn hiệu lực **không** đặt lẻ được. Server vẫn trả `417 thuoc_hdnt_hieu_luc`.
- **NL-10.3** — server từ chối payload trộn dòng hợp đồng khung và dòng lẻ trong một đơn.
- **Quyết định nền 7 và 8** — không endpoint nào nhận `customer`/`kho` từ client; không có URL file công khai.
- **Chốt `before_submit`** không cho xác nhận đơn còn dòng đặt ngoài chưa khớp mã.
- **339 test hiện có phải giữ xanh** (trừ `test_e6_yeu_cau.py` bị xoá theo tính năng).

---

## 5. Test

**Xoá:** `tests/test_e6_yeu_cau.py`.

**Sửa:** `tests/test_e6_mua_le.py` — bỏ mọi giả định về giá lẻ trong danh mục; `test_portal_settings.py` — bỏ phần `price_list_ban_le` cho đường mua lẻ nếu còn.

**Thêm:**

| Test | Chứng minh điều gì |
|---|---|
| Gọi từng endpoint `portal_yeu_cau_*` → `AttributeError`/404 | Đường vào từ cổng đã thật sự biến mất, không chỉ ẩn nút |
| `Portal Item Request` vẫn tạo/đọc được bằng tài khoản nhân viên Desk | Bỏ khỏi cổng không làm hỏng back-office |
| Khách MỚI tạo (chưa ai đụng cờ) gọi `portal_catalog_ban_le` → 200 | Mặc định BẬT có hiệu lực |
| Khách bị tắt cờ thủ công → vẫn 403 `khong_duoc_mua_le` | Đổi mặc định không phải bỏ chốt |
| `portal_order_place(mode="ban_le")` với chỉ dòng `dat_ngoai`, `items` rỗng → lỗi rõ ràng | Giới hạn ERPNext được xử lý tử tế, không nổ traceback |
| Đơn có dòng đặt ngoài đã khớp mã → PDF báo giá chứa dòng đó | Khách không nhận báo giá thiếu món |
| `portal_bao_gia_pdf` với tên đơn của khách KHÁC → chặn | Cách ly dữ liệu theo phiên |
| `portal_bao_gia_pdf` khi đơn còn nháp (chưa gửi khách) → chặn | Không lộ giá sales chưa chốt |
| `portal_order_track` trả `custom_dat_ngoai` cho đơn Mua lẻ | Khách theo dõi được dòng mình tự gõ |

---

## 6. Tài liệu BA phải cập nhật

Không sửa đè thiết kế 14/08 — nó là lịch sử của commit `554673d`.

| Tài liệu | Sửa gì |
|---|---|
| `DevHandoff/15_PRD_E6_MuaLe_YeuCauHang.md` | Đổi tên file → `15_PRD_E6_MuaLe.md`; bỏ US-E6.3, US-E6.4, US-E6.6 khỏi phạm vi cổng, chuyển thành mục "Desk-only"; sửa lại US-E6.1 (mặc định BẬT, danh mục không giá); thêm US mới cho khối đặt ngoài và PDF báo giá |
| `BA-miyano_portal_v2.md` | QT11, UC-16/17/52/53, BR-Y1…Y5, NL-11.x — đánh dấu **Desk-only**, không còn quy trình của cổng |
| `DevHandoff/30_API_Spec.md` | Xoá 6 endpoint `portal_yeu_cau_*`; thêm `portal_bao_gia_pdf`; cập nhật `portal_catalog_ban_le` (không trả giá) và `portal_order_place` (tham số `dat_ngoai`) |
| `DevHandoff/20_DataDict.md §1` | `Portal Item Request` chuyển sang mục Desk; thêm `Sales Order Dat Ngoai Item` |
| `DevHandoff/40_TestCases.md` | TC-E6-02 sửa; TC-E6-05/06 chuyển Desk-only; thêm các TC ở §5 |
| `FormSpec-miyano_portal_v2.md` | F-22, F-23 bỏ khỏi cổng; F-21 sửa theo §3.3/§3.4; F-07 thêm nút Tải báo giá |
| `CHANGELOG-khac-phuc-BA-v2.md` | Ghi quyết định này — tài liệu tự nhận là "nguồn sự thật duy nhất về trạng thái khắc phục" |
| `DevHandoff/00_INDEX.md` | Cập nhật tên file PRD E6 |

---

## 7. Việc KHÔNG làm

- Không xoá doctype `Portal Item Request`, báo cáo demand pipeline, job SLA, hay `Settings.sla_yeu_cau_gio`.
- Không đổi mã/tên trường HĐNT — chỉ đổi nhãn hiển thị.
- Không nới BR-R7.
- Không dùng doctype `Quotation` của ERPNext, không đổi máy trạng thái E2/E6.5.
- Không đụng `Settings.price_list_ban_le` — để nguyên, chỉ tiếp tục không phụ thuộc.
- Không xoá `custom_ban_le_portal` khỏi `Item` (dữ liệu cũ; xoá cột là việc riêng).
- Không dựng màn dự trù E5 — chưa có ở SPA, ngoài phạm vi đợt này.

---

## 8. Điểm cần chú ý khi triển khai

1. **Thứ tự làm quan trọng.** Sửa §3.3 (đồng bộ SPA với back-end không giá) **trước** §3.4 (khối đặt ngoài). Dựng tính năng mới lên trên một màn đang hỏng thì không phân biệt được lỗi mới với lỗi cũ.
2. **`Settings.hieu_luc_bao_gia_ngay` phải sống sót** — PDF báo giá và job đóng đơn quá hạn đều đọc nó. Chỉ `sla_yeu_cau_gio` là gắn với tính năng bị bỏ, và nó cũng được giữ (§3.2).
3. **Bỏ ba getter `cartLe*` khỏi `store.js` sẽ làm mọi chỗ đang gọi chúng thành `undefined` chứ không báo lỗi.** Grep toàn bộ `frontend/src` cho `cartLeTotal`, `cartLeSubtotal`, `cartLeVat` trước khi xoá.
4. **Build lại SPA** (`bench build --app miyano_portal`) — `public/frontend/index.js` là bản dựng sẵn, không tự cập nhật theo `frontend/src`.
5. **Chạy `bench migrate` trên site trước khi test** — patch đổi mặc định `custom_cho_phep_mua_le` phải chạy, nếu không test "khách mới mặc định mua lẻ được" sẽ đỏ vì lý do sai.
