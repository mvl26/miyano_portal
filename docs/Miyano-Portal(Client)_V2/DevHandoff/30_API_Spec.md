# 30_API_Spec — Endpoint whitelist (Frappe `@frappe.whitelist()`)

Quy tắc chung cho MỌI endpoint (đọc kỹ trước khi viết cái mới):

- Đường gọi: `POST /api/method/miyano_portal.api.<module>.<ten_ham>` — session cookie + header
  `X-Frappe-CSRF-Token`. **Không** REST controller riêng, không route tự chế.
- Auth: Website User role `Customer`. Khách/kho suy từ **phiên** (`portal_context.get_portal_kho()` /
  contact→customer) — **không endpoint nào nhận `customer`/`kho` từ client**.
- Nhận tên chứng từ từ client (`name`) → bắt buộc tự kiểm sở hữu trước khi đọc/ghi (get_doc không tự check).
- Response chuẩn Frappe: `{"message": <payload>}`. Lỗi nghiệp vụ: `frappe.throw(msg)` với **nguyên văn**
  thông điệp trong FormSpec §5 → HTTP 417/403. Dưới đây chỉ viết phần `<payload>`.
- Danh sách [Hiện có] (giữ nguyên chữ ký, xem BA §14): `portal_me/contracts/catalog/order_place/
  order_history/order_track/deliveries/invoices/request_cancel/provision/document_download` ·
  `kho_me/ton/lo/vat_tu_*/import_*/phieu_*/dong_phieu_*/lo_goi_y/bao_cao_nxt/the_kho/canh_bao_han/bao_cao_excel`.

---

## 1. Mở rộng endpoint [Hiện có]

### 1.1 `api.portal.portal_order_place` — thêm `request_id`, `mode` (E1, E6)
```jsonc
// Request
{ "hdnt": "BO-TEST-001",            // bỏ trống khi mode=ban_le
  "mode": "hdnt",                    // "hdnt" (mặc định) | "ban_le" (E6, kiểm custom_cho_phep_mua_le)
  "request_id": "9f2c-…-uuid",       // BR-O12, bắt buộc
  "items": [{"item_code": "VT0001", "qty": 10}],
  "ngay_giao": "2026-08-20", "dia_chi": "ADDR-0001",
  "so_po": "DT-2026-0715", "ghi_chu": "Giao giờ hành chính" }
// Response (payload)
{ "sales_order": "SAL-ORD-2026-00145", "da_ton_tai": false, "trang_thai": "Chờ xác nhận" }
// Lỗi gom một lần (BR-O3) — HTTP 417:
{ "loi": [ {"item_code": "VT0002", "ly_do": "vuot_han_muc", "con_lai": 5},
           {"item_code": "VT0003", "ly_do": "sai_boi_so", "boi_so": 10} ] }
```
Ghi chú: `request_id` trùng → trả đơn cũ, `da_ton_tai: true` (không lỗi). Dòng hạn mức 0 → bỏ kiểm,
không gắn `against_blanket_order` (BR-O15). `mode=ban_le`: bỏ kiểm hạn mức, `custom_loai_don="Mua lẻ"`,
chặn item đang thuộc hợp đồng khung hiệu lực (BR-R7).

**Tham số `dat_ngoai` (MỚI 15/08, §3.4)** — chỉ dùng với `mode=ban_le`: JSON-string mảng các dòng
"chưa có mã" (`[{"ten_hang","dvt","so_luong","ghi_chu"}]`), lưu vào `custom_dat_ngoai` (Table, xem
DataDict §1.2b). Nếu sau khi gộp `items` (có mã) + `dat_ngoai` (không mã) mà bảng `items` **rỗng**
(khách chỉ gõ dòng không mã, không chọn mặt hàng có mã nào), server tự chèn thêm đúng một dòng Item
kỹ thuật `HANG-DAT-NGOAI` vào `items` để SO lưu được (ERPNext không cho `items` rỗng) — dòng này
**không bao giờ** trả về cho khách qua `portal_order_track` hay mẫu in (lọc bằng `la_dong_giu_cho()`).

**M-5 (review E6 phần B) — LỆCH TÀI LIỆU đã có TỪ TRƯỚC E6, ghi nhận chứ không sửa:** tham số thân
request thật sự tên là **`contract`**, không phải `hdnt` như JSON mẫu ở trên — `frontend/src/views/
Cart.vue` (đã chạy thật, từ E1) gọi `portal_order_place({ contract: ..., ... })`. Đổi tên tham số cho
khớp tài liệu sẽ vỡ SPA đang chạy mà không có gì buộc Phần C phải đổi theo cùng lúc; giữ nguyên `contract`
là quyết định có chủ đích, không phải nợ kỹ thuật. Khi mode=ban_le, gửi `contract: null`/bỏ trống.

### 1.2 `api.portal.portal_order_track` — thêm `dot_giao[]`, `chap_nhan{}` (E3, E6); `dat_ngoai[]` (15/08)
```jsonc
// Response bổ sung
{ "dot_giao": [ { "so_dot": 1, "delivery_note": "MAT-DN-2026-00201", "ngay": "2026-07-27",
                  "phan_tram": 60, "van_chuyen": "Nhất Tín", "awb": "NT8829134VN",
                  "co_hoa_don_nhap": true,
                  "phieu_nhap": {"name": "PNK-00031", "trang_thai": "Nháp", "co_chenh_lech": false} } ],
  "chap_nhan": { "can_dong_y": true, "han_hieu_luc": "2026-08-19" },   // chỉ đơn Chờ khách đồng ý
  "hdnt": "BO-2026-00020",   // (giữ tên khoá cũ — response key, không phải chữ hiển thị)
  "loai_don": "Mua lẻ",
  // MỚI 15/08 (§3.4) — TOÀN BỘ dòng "chưa có mã" của đơn Mua lẻ (custom_dat_ngoai), cả đã và
  // chưa khớp — client tự tách bằng da_xu_ly (nhóm "Đang chờ Miyano xác nhận nguồn" = false):
  "dat_ngoai": [ { "ten_hang": "Kim luồn tĩnh mạch 22G", "dvt": "Cái", "so_luong": 50,
                    "ghi_chu": "", "da_xu_ly": false, "item_khop": "" } ],
  "items": [ /* … */ ]   // Item kỹ thuật HANG-DAT-NGOAI đã LỌC KHỎI mảng này (la_dong_giu_cho()) }
```
**`co_hoa_don_nhap`** (E7b) — có mặt trên CẢ `dot_giao[]` lẫn `deliveries[]`: phiếu giao này đã có
chứng từ HĐĐT còn ở vòng nháp (trạng thái 01–04). Chỉ là CỜ; nội dung lấy qua `portal_einvoice_nhap`
khi khách bấm xem. Lỗi ở module HĐĐT bị nuốt thành `false` (khuôn bọc lỗi giống `portal_invoices`) —
chi tiết đơn hàng không được phụ thuộc module của team khác.

### 1.3 `api.kho.kho_phieu_nhap_save` — thêm trường E3/E4
Nhận thêm: `loai_nhap` mới, `ncc`, `so_chung_tu_ncc`, `ngay_chung_tu`, dòng `ly_do_chenh_lech`.
Validate server: BR-N1 (thiếu NCC → chặn), BR-K17 (`so_luong ≤ sl_giao`, lệch → bắt lý do),
BR-K10, BR-K2 như cũ. Ghi sổ đặt cờ `co_chenh_lech`/`thieu_chung_tu` + bắn notification.

### 1.4 `api.kho.kho_canh_bao_han` — tách nhóm (E4/VĐ-2)
**Quyết định triển khai (review E4 phần B, I-3)** — GIỮ response dạng **mảng phẳng** (`list[dict]`)
như trước E4, KHÔNG đổi sang `{da_het_han, sap_het_han, khong_han_dung}`: `kho_canh_bao_han` và
`kho_bao_cao_excel(loai="canh_bao")` là một hợp đồng ĐANG SỐNG — frontend (`BaoCaoNXT.vue`,
tab "Cảnh báo hạn dùng"), report desk (`desk_reports.canh_bao_han_khach_hang_rows`) và bộ xuất
Excel (`reports.build_xlsx` + `CANH_BAO_COLUMNS`) đều đã tiêu thụ mảng phẳng này TỪ TRƯỚC E4; đổi
sang dict sẽ vỡ cả ba nơi cùng lúc mà không có gì báo trước (không phải lỗi type, là dữ liệu sai
hình dạng render thành bảng rác). Mỗi dòng vẫn mang đủ thông tin để CLIENT tự nhóm: `trang_thai`
nhận đúng BA giá trị `"Đã hết hạn"` / `"Sắp hết hạn"` / `"Không có hạn dùng"`; hai dòng đầu là
`han_su_dung`/`so_ngay_con_lai` NULL cho nhóm thứ ba.

Ràng buộc dữ liệu (không đổi từ khi sửa VĐ-2): nhóm `"Không có hạn dùng"` **không bị giới hạn** bởi
tham số `so_ngay` (một lô không khai hạn luôn hiện, bất kể ngưỡng) và **không được tính** vào hai
nhóm hạn dùng thật — hai nhóm đó CHỈ chứa lô có `han_su_dung` thật, đúng tinh thần câu spec gốc.

---

## 2. Endpoint MỚI — `api.portal`

### 2.1 `portal_reorder(order)` (E1)
```jsonc
// Request:  { "order": "SAL-ORD-2026-00131" }
// Response: { "gio_hang": [{"item_code":"VT0001","qty":10,"gia_hien_hanh":45000}],
//             "bi_loai": [{"item_code":"HC0002","ly_do":"het_han_muc"}] }
```
Kiểm sở hữu đơn theo phiên; giá lấy hiện hành; dòng hết hạn mức/ngoài hợp đồng khung vào `bi_loai`.

### 2.2 `portal_catalog_ban_le(tim_kiem=None, nhom=None, start=0, limit=50)` (E6, **thiết kế lại 15/08**)
```jsonc
// Request: { "tim_kiem": "gang tay", "start": 0, "limit": 50 }
// Response: { "items": [{"item_code","ten","quy_cach","dvt","trang_thai_hang",
//              "thuoc_hdnt": false, "san_sang_ban": true}],
//            "tong": 137, "start": 0, "limit": 50 }
```
403 nếu `custom_cho_phep_mua_le = 0`. Danh mục là **TOÀN BỘ** `Item` đang hoạt động (`disabled = 0`)
— không còn lọc `custom_ban_le_portal` (sửa 15/08, BR-R6). Phân trang server-side qua `start`/`limit`;
client cộng dồn khi bấm "Tải thêm", nạp lại từ đầu khi đổi từ khoá. **Không còn trả giá** — bỏ hẳn
key `gia_ban_le`/`co_gia`; mọi phiếu Mua lẻ đi qua báo giá của sales (§4.5, không phải cổng). `tong`
= tổng số dòng khớp bộ lọc hiện tại (không phải tổng toàn danh mục), dùng để tính còn bao nhiêu dòng
chưa tải. `thuoc_hdnt: true` → client disable + badge chuyển tab (BR-R7).

### 2.3 *(GỠ 15/08 — Desk-only)* ~~`portal_yeu_cau_save/list/detail/cancel/tra_loi/file`~~

Sáu endpoint này (và route `/portal/yeu-cau*`) **đã xoá khỏi API cổng** ở kế hoạch 2026-08-15
(Task 1–2). Lý do và thay thế: xem `BA-miyano_portal_v2.md` §4.11 (Desk-only) và
`FormSpec-miyano_portal_v2.md` F-22/F-23. `Portal Item Request` vẫn là doctype sống — nhân viên
Miyano tạo/sửa/huỷ trực tiếp trên Desk, không qua endpoint whitelist cổng nữa.

### 2.4 `portal_order_accept(order, action, ly_do=None)` (E2/E6)
```jsonc
// Request: { "order": "SAL-ORD-2026-00150", "action": "dong_y" }        // hoặc "khong_dong_y" + ly_do ≥10 ký tự
// Response: { "trang_thai_moi": "Chờ Miyano xác nhận" }
```
Chặn: đơn không thuộc khách của phiên / không ở "Chờ khách đồng ý" / quá `han_hieu_luc` (→ 417
"Báo giá cho đơn … đã hết hiệu lực…"). Chuyển trạng thái dưới quyền hệ thống + Comment log.

### 2.5 `portal_einvoice_download(invoice, loai, fei=None)` (E7 / E7b)
`loai`: `"pdf"` (bản thể hiện hoá đơn ĐÃ phát hành, `official_pdf`, chốt trạng thái 06+) hoặc
`"nhap"` (bản in thử Fast dựng khi chứng từ còn ở 01–04, `draft_pdf`). Hai chốt trạng thái **ngược
nhau** nên cài đặt tách nhánh rõ ràng, không gộp điều kiện.

Kiểm TỪNG LẦN tải: SI thuộc customer của phiên + chứng từ HĐĐT khớp đúng hoá đơn đó + trạng thái cho
phép + `File` thật sự đọc được và đính đúng chứng từ → stream (Content-Disposition attachment); ghi
`Access Log`. Sai điều kiện → 403/417.

`fei` TUỲ CHỌN — một hoá đơn có thể khớp NHIỀU chứng từ HĐĐT. Tham số này **chỉ dùng để LỌC** trong
tập đã tự suy từ phiên, không bao giờ `get_doc` thẳng tên client gửi.

### 2.6 `portal_bao_gia_pdf(order)` (E6, **MỚI 15/08 — §3.6**)
```jsonc
// Request: { "order": "SAL-ORD-2026-00150" }
// Response: file nhị phân (Content-Disposition attachment), KHÔNG trả JSON
```
Kiểm sở hữu đơn theo phiên (cùng khuôn `portal_order_track`). Trả PDF render từ Print Format
"Miyano - Báo giá" (`portal.setup.install_print_formats`) — bảng dòng "items" thật (lọc dòng giữ chỗ
`HANG-DAT-NGOAI` qua `la_dong_giu_cho()`), bảng "Hàng đang tìm nguồn" cho dòng `custom_dat_ngoai`
chưa khớp mã (`da_xu_ly=0`), bảng "Hàng đặt ngoài đã khớp mã" cho dòng đã khớp (`da_xu_ly=1`), và
hạn hiệu lực (`han_hieu_luc_bao_gia(doc)`). Cùng mẫu in được đính kèm tự động vào email Notification
"Portal - Báo giá sẵn sàng" khi đơn chuyển "Chờ khách đồng ý" — endpoint này chỉ là đường TẢI LẠI
theo yêu cầu trên F-07, không phải đường phát sinh báo giá.

> **Lệch tài liệu, ghi nhận chứ không sửa mã:** `loai="xml"` KHÔNG tồn tại. Module HĐĐT không lưu XML
> ở bất kỳ field nào (đã kiểm JSON doctype) — không có gì để giao. Tên field cũng khác bảng "tên tạm"
> của BA (`einvoice_trang_thai` không tồn tại); bản đồ thật ở `miyano_portal/einvoice.py`.

### 2.6 `portal_einvoice_nhap(delivery_note)` (E7b) — MỚI
```jsonc
// Response (null nếu kế toán chưa lập chứng từ HĐĐT cho phiếu giao này)
{ "fei": "FEI-2026-00042", "nhan": "Hoá đơn nháp", "loai": "Hóa đơn gốc",
  "canh_bao": "Bản nháp — chưa có số hoá đơn, chưa ký số, chưa gửi Cơ quan Thuế…",
  "ngay": "2026-07-27", "tien_hang": 250000, "tien_thue": 22500, "chiet_khau": 0,
  "tong_tien": 272500, "bang_chu": "…", "cap_nhat_luc": "2026-07-27 10:12:03",
  "nhap_tai_duoc": true,
  "dong": [ { "stt": 1, "ma": "VT0005", "ten": "…", "dvt": "Cái", "so_luong": 2,
              "don_gia": 100000, "thanh_tien": 200000, "chiet_khau": 0,
              "thue_suat": "10", "tien_thue": 20000, "ghi_chu": "" } ] }
```
Neo theo **Delivery Note**, KHÔNG theo Sales Invoice: `builder.create_from_delivery_note` (luồng thật
sinh chứng từ HĐĐT) chỉ gán `fei.delivery_note`, và phiếu giao có thể chưa được lập hoá đơn bán hàng
tại thời điểm đó — neo theo SI thì khách không thấy gì đúng lúc chứng từ vừa được lập.

Kiểm: phiếu giao thuộc customer của phiên (`check_permission` + đối chiếu `dn.customer`) + bản ghi
HĐĐT khớp phải đúng `fei.customer`. Trạng thái đủ điều kiện: **01–04**. `canh_bao` do SERVER trả để
một lần sửa giao diện không làm rơi mất cảnh báo pháp lý. KHÔNG bao giờ trả đường dẫn file (BR-E4) —
chỉ cờ `nhap_tai_duoc`.

`dong[]` là **DỰ PHÒNG** cho giao diện: thứ khách cần thấy trước hết là chính file PDF do Fast dựng;
bảng số liệu này chỉ để có cái mà xem khi Fast chưa dựng xong (trạng thái 01) hoặc gọi Fast lỗi.

### 2.7 `portal_einvoice_nhap_pdf(delivery_note)` (E7b) — MỚI
Stream bản in thử PDF (`draft_pdf`; Fast dựng với `action=600` — không ký số, không cấp số, không gửi
CQT). Cùng ràng buộc §2.6: kiểm sở hữu từng lần, không nhận tên chứng từ từ client, ghi `Access Log`.
Dùng ở màn chi tiết đơn hàng, nơi phiếu giao có thể chưa có Sales Invoice để bám vào.

> **Chưa có trên cổng:** nút Duyệt / Yêu cầu sửa bản nháp. Vòng duyệt của module HĐĐT
> (`send_draft_to_customer` → 03 → `record_customer_feedback` / `mark_customer_approved`) hiện chạy
> qua **email + nhân viên tự ghi nhận**. Site đang bật `require_customer_approval = 1` nên không hoá
> đơn nào phát hành được cho tới khi bản ghi ở `04 - Khách đã duyệt` — đưa vòng duyệt lên cổng là
> thay đổi chạm interface của team HĐĐT, phải chốt riêng.

---

## 3. Endpoint MỚI — `api.kho` (tất cả đi qua `get_portal_kho()`)

### 3.1 `kho_ncc_list(tim_kiem=None, ca_inactive=False)` / `kho_ncc_save(data)` (E4)
```jsonc
// save Request: { "name": null, "ten_ncc": "Cty TNHH ABC", "mst": "0101234567",
//                 "dien_thoai": "0243...", "email": "sales@abc.vn", "dia_chi": "...", "active": 1 }
// save Response: { "name": "NCC-00004", "goi_y_trung": ["NCC-00002: Công ty ABC"] }  // NL-7.3
// list Response: [ { "name","ten_ncc","mst","dien_thoai","email","dia_chi","ghi_chu",
//                    "so_phieu","gia_tri_90n","active" } ]
```
List trả ĐỦ chi tiết mô tả (không chỉ cột hiển thị bảng, review E4 phần B Gap 1) — cùng khuôn
`kho_vat_tu_list`: màn Sửa dùng lại đúng dữ liệu đã tải để điền form, không cần round-trip thứ hai.

**`chi_kiem_tra`** (review E4 phần B, Gap 3): thêm vào payload của `kho_ncc_save` (và tương tự
`kho_vat_tu_tao`) — `data.chi_kiem_tra = true` chạy đúng các kiểm tra thường lệ (khớp mã/trùng tuyệt
đối/gợi ý gần giống) rồi **DỪNG TRƯỚC khi ghi**, trả `{ "name": null, "goi_y_trung"/"canh_bao_trung":
[...] }` — cho phép bản mẫu hỏi "[Vẫn tạo]/[Huỷ]" TRƯỚC khi bản ghi tồn tại thật (trước bản này,
bản ghi đã được tạo ngay khi hàm trả về nên "Huỷ" không rollback được gì). Bỏ trống/`false` giữ
nguyên hành vi cũ (ghi ngay). Chỉ áp cho TẠO MỚI — sửa bản ghi có sẵn không cần xem trước.

### 3.2 `kho_nhat_ky(vat_tu, tu_ngay, den_ngay, lo=None, loai=None, nguon=None, trang=1)` (E4)
```jsonc
// Response
{ "tong_dong": 132, "trang": 1, "so_dong_moi_trang": 50,
  "dong": [ { "ngay": "2026-08-05", "phieu": "PNK-00031", "loai": "Nhập", "nguon": "Miyano",
              "dot": "PNK-00031", "lo": "L2408A", "han": "2027-02-01", "sl_nhap": 100, "sl_xuat": 0,
              "don_gia": 45000, "ton_sau": 180, "nguoi_ghi_so": "duoc@bv.vn", "da_dao": false } ] }
```
Chỉ đọc, dựng từ `Customer Stock Ledger Entry`; `da_dao=true` client hiển thị mờ (BR-D2).

### 3.3 `kho_bao_cao_dot(tu_ngay, den_ngay, vat_tu=None, nguon=None)` (E4)
```jsonc
// Response — phân bổ FIFO trong (vật tư, lô) — BR-D1
[ { "dot": "PNK-001", "ngay_nhan": "2026-08-01", "nguon": "Miyano", "chung_tu": "MAT-DN-00201",
    "vat_tu": "VT-A", "lo": "L1", "sl_nhap": 100, "gia_tri_nhap": 4500000,
    "da_xuat": 100, "con_lai": 0, "tuoi_ton_ngay": 60, "pct_tieu_thu": 100, "cham_luan_chuyen": false },
  { "dot": "PNK-005", "sl_nhap": 50, "da_xuat": 20, "con_lai": 30, "tuoi_ton_ngay": 51,
    "pct_tieu_thu": 40, "cham_luan_chuyen": true } ]
```

### 3.3b Cấp phát khoa phòng (E8 — QĐ-9)

`kho_khoa_phong_list(tim_kiem=None, ca_inactive=False)` / `kho_khoa_phong_save(data)` — khuôn như
`kho_ncc_*`; save trả `goi_y_trung[]` (NL-4.13). List trả thêm `so_phieu_90n`, `gia_tri_90n`.

`kho_nguoi_nhan_goi_y(khoa_phong, tu_khoa)` → `["BS. Tuấn", "ĐD. Lan"]` — distinct `nguoi_nhan` từ
phiếu Xuất sử dụng đã ghi sổ của **chính khoa đó**, 12 tháng, khớp không dấu, tối đa 10.

```jsonc
// kho_bao_cao_cap_phat(tu_ngay, den_ngay, khoa_phong=None, vat_tu=None) — Response
{ "tong_gia_tri": 1320000,
  "nhom": [ { "khoa_phong": "Khoa Hồi sức", "gia_tri": 538000, "pct": 40.8,
              "dong": [ { "phieu": "PXK-00051", "ngay": "2026-08-05", "vat_tu": "Găng nitrile M",
                          "dvt": "hộp", "sl": 8, "gia_tri": 368000, "nguoi_nhan": "BS. Tuấn" } ] },
            { "khoa_phong": null, "ten_hien_thi": "Chưa gắn khoa", "gia_tri": 230000, "pct": 17.4,
              "dong": [ /* … */ ] } ] }
```
Join sổ kho ↔ phiếu xuất (BR-CP4); loại trừ phiếu đảo/dòng `da_dao`; nhóm "Chưa gắn khoa" tách riêng.

### 3.4 `kho_canh_bao_ton()` / `kho_min_max_goi_y(vat_tu_list)` (E5)
```jsonc
// canh_bao_ton Response
{ "thieu": 3, "cham_rop": 5, "chua_thiet_lap": 12,
  "dong": [ { "vat_tu": "VTK-00012", "ten": "Găng nitrile M", "ton": 22, "adu_30": 5.2, "adu_90": 5.0,
              "ngay_phu": 4.4, "min": 10, "rop": 25, "max": 60, "trang_thai": "sap_thieu",
              "sl_goi_y": 40, "dat_duoc_hdnt": true, "item_code": "VT0001" } ] }
// min_max_goi_y Request:  { "vat_tu_list": ["VTK-00012"] }
// Response: { "VTK-00012": { "adu_90": 5.0, "min": 10, "rop": 25, "max": 60 } }
//           hoặc { "VTK-00099": { "du_lieu": false } }        // NL-9.1 (<30 ngày)
```

---

## 4. Notification & Job (đăng ký trong `hooks.py`)

| Tên | Kênh | Trigger | Người nhận |
|---|---|---|---|
| Portal - Thiếu giá | Notification | NL-1.4, tối đa 1/(khách,item)/ngày | Sales phụ trách |
| Portal - Chênh lệch nhận hàng | Notification | Ghi sổ phiếu `co_chenh_lech=1` | Sales phụ trách |
| Portal - Đơn treo SLA | Job hourly → Notification | NL-2.6 | Sales Manager |
| Portal - Yêu cầu hàng hoá mới / đổi trạng thái | Notification + email | E6 | Sales + Purchase User / Khách |
| Portal - Báo giá hết hiệu lực | Job daily | NL-10.5 | Khách + sales |
| Portal - Cảnh báo thiếu tồn | Job daily (+email tuỳ chọn) | E5 | Khách |
| Portal - HĐĐT phát hành | Event từ module HĐĐT | E7 | Khách |

## 5. Mã lỗi `ly_do` chuẩn (client dịch ra thông điệp FormSpec §5)

`vuot_han_muc` · `het_han_muc` · `thieu_gia` · `sai_boi_so` · `ngay_giao_khong_hop_le` ·
`khong_so_huu` (403) · `thieu_ncc` · `ton_khong_du` · `phieu_dao_khong_huy` · `dao_lam_am_ton` ·
`ton_dau_da_nhap` · `qua_han_hieu_luc` · `chua_phat_hanh_hddt` · `khong_duoc_mua_le` (403) ·
`thuoc_hdnt_hieu_luc`
