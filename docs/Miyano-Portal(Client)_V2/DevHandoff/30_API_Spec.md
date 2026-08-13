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
chặn item đang thuộc HĐNT hiệu lực (BR-R7).

### 1.2 `api.portal.portal_order_track` — thêm `dot_giao[]`, `chap_nhan{}` (E3, E6)
```jsonc
// Response bổ sung
{ "dot_giao": [ { "so_dot": 1, "delivery_note": "MAT-DN-2026-00201", "ngay": "2026-07-27",
                  "phan_tram": 60, "van_chuyen": "Nhất Tín", "awb": "NT8829134VN",
                  "phieu_nhap": {"name": "PNK-00031", "trang_thai": "Nháp", "co_chenh_lech": false} } ],
  "chap_nhan": { "can_dong_y": true, "han_hieu_luc": "2026-08-19" } }   // chỉ đơn Chờ khách đồng ý
```

### 1.3 `api.kho.kho_phieu_nhap_save` — thêm trường E3/E4
Nhận thêm: `loai_nhap` mới, `ncc`, `so_chung_tu_ncc`, `ngay_chung_tu`, dòng `ly_do_chenh_lech`.
Validate server: BR-N1 (thiếu NCC → chặn), BR-K17 (`so_luong ≤ sl_giao`, lệch → bắt lý do),
BR-K10, BR-K2 như cũ. Ghi sổ đặt cờ `co_chenh_lech`/`thieu_chung_tu` + bắn notification.

### 1.4 `api.kho.kho_canh_bao_han` — tách nhóm (E4/VĐ-2)
Response thêm nhóm `khong_han_dung[]` riêng; các nhóm hạn chỉ chứa lô có `han_su_dung` thật.

---

## 2. Endpoint MỚI — `api.portal`

### 2.1 `portal_reorder(order)` (E1)
```jsonc
// Request:  { "order": "SAL-ORD-2026-00131" }
// Response: { "gio_hang": [{"item_code":"VT0001","qty":10,"gia_hien_hanh":45000}],
//             "bi_loai": [{"item_code":"HC0002","ly_do":"het_han_muc"}] }
```
Kiểm sở hữu đơn theo phiên; giá lấy hiện hành; dòng hết hạn mức/ngoài HĐNT vào `bi_loai`.

### 2.2 `portal_catalog_ban_le(tim_kiem=None, nhom=None)` (E6)
403 nếu `custom_cho_phep_mua_le = 0`. Trả item `custom_ban_le_portal=1`:
`{ "items": [{"item_code","ten","quy_cach","dvt","gia_ban_le","vat","trang_thai_hang",
  "thuoc_hdnt": false, "co_gia": true}] }` — `thuoc_hdnt: true` → client disable (BR-R7);
`co_gia: false` → hiện nút Yêu cầu báo giá.

### 2.3 `portal_yeu_cau_save(data)` / `portal_yeu_cau_list(trang_thai=None)` / `portal_yeu_cau_cancel(name, ly_do)` (E6)
```jsonc
// save Request (tạo mới hoặc sửa khi trạng thái "Mới"; kèm files upload chuẩn Frappe, is_private=1)
{ "loai": "Tìm nguồn hàng mới", "ten_hang": "Que thử HbA1c", "quy_cach": "Hộp 25 test",
  "dvt": "Hộp", "so_luong_du_kien": 20, "tan_suat": "Định kỳ", "chu_ky_thang": 1,
  "ngay_can": "2026-08-25", "hang_xuat_xu": "Abbott", "ghi_chu": "", "vat_tu_kho": "VTK-00012" }
// save Response: { "name": "YCH-00007", "canh_bao_trung": ["YCH-00003"] }   // NL-11.1, không chặn
// list Response: [ { "name","ngay","ten_hang","loai","so_luong_du_kien","trang_thai",
//                    "sla_den_han","qua_sla": false, "don_lien_ket": null } ]
// cancel: chỉ khi trạng thái chưa kết thúc; ly_do bắt buộc → trạng thái "Khách huỷ"
```

### 2.4 `portal_order_accept(order, action, ly_do=None)` (E2/E6)
```jsonc
// Request: { "order": "SAL-ORD-2026-00150", "action": "dong_y" }        // hoặc "khong_dong_y" + ly_do ≥10 ký tự
// Response: { "trang_thai_moi": "Chờ Miyano xác nhận" }
```
Chặn: đơn không thuộc khách của phiên / không ở "Chờ khách đồng ý" / quá `han_hieu_luc` (→ 417
"Báo giá cho đơn … đã hết hiệu lực…"). Chuyển trạng thái dưới quyền hệ thống + Comment log.

### 2.5 `portal_einvoice_download(invoice, loai)` (E7)
`loai`: `"xml" | "pdf"`. Kiểm: SI thuộc customer phiên + `einvoice_trang_thai = "Đã phát hành"` +
file tồn tại → stream (Content-Disposition attachment); ghi log lượt tải. Sai điều kiện → 403/417.

---

## 3. Endpoint MỚI — `api.kho` (tất cả đi qua `get_portal_kho()`)

### 3.1 `kho_ncc_list(tim_kiem=None, ca_inactive=False)` / `kho_ncc_save(data)` (E4)
```jsonc
// save Request: { "name": null, "ten_ncc": "Cty TNHH ABC", "mst": "0101234567",
//                 "dien_thoai": "0243...", "email": "sales@abc.vn", "dia_chi": "...", "active": 1 }
// save Response: { "name": "NCC-00004", "goi_y_trung": ["NCC-00002: Công ty ABC"] }  // NL-7.3
// list Response: [ { "name","ten_ncc","mst","so_phieu","gia_tri_90n","active" } ]
```

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
