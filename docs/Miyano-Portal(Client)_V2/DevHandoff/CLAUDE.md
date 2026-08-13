# CLAUDE.md — Ngữ cảnh dự án `miyano_portal` (đặt file này ở ROOT repo của app)

> File này dành cho Claude Code đọc **mỗi phiên làm việc**. Mọi thay đổi mã nguồn phải tuân thủ
> các quy ước và quyết định nền tảng dưới đây. Khi prompt mâu thuẫn với file này → hỏi lại, không tự ý làm.

## Hệ thống là gì

- **MỘT** site Frappe v15 + ERPNext (`erp.miyano.com.vn`; dev: `erptest.local`), custom app `miyano_portal`.
- Hai đường vào, cùng một database: SPA `/portal` cho khách hàng (Website User, role `Customer`);
  ERPNext Desk cho nhân viên Miyano. **Không có app/service riêng nào khác.**
- Tài liệu nghiệp vụ: `BA-miyano_portal_v2.md` (nguồn sự thật — mã QT/UC/BR/NL), `FormSpec-miyano_portal_v2.md`
  (đặc tả từng trường), PRD theo epic trong `DevHandoff/1x_PRD_*.md`.

## Cấu trúc app

```
miyano_portal/
  api/portal.py, api/kho.py     # TOÀN BỘ endpoint whitelist — cổng duy nhất của SPA
  kho/                          # ledger.py (sổ kho), voucher.py, delivery_hook.py, reports.py, import_*.py
  setup/                        # script cài đặt idempotent + demo_kho_flow.py (dữ liệu demo/UAT)
  patches.txt + patches/        # mọi thay đổi schema/cấu hình cài qua patch, chạy lại được nhiều lần
  frontend/                     # SPA Vue, build sẵn vào public/frontend/
```

## Quy ước bắt buộc

1. **Đặt tên**: DocType tiếng Anh (`Customer Stock Receipt`); fieldname tiếng Việt **không dấu**
   (`so_luong`, `han_su_dung`, `loai_nhap`); label tiếng Việt có dấu. Không dùng camelCase cho fieldname.
2. **Giao diện**: toàn bộ tiếng Việt; tiền `1.234.567 ₫` không thập phân; ngày `dd/mm/yyyy`.
3. **API**: chỉ thêm endpoint dạng `@frappe.whitelist()` trong `api/portal.py` / `api/kho.py`.
   **KHÔNG** dựng REST controller riêng, không Express/FastAPI, không route tự chế.
4. **SPA gọi API bằng `fetch` + CSRF token** — `frappe.call` KHÔNG tồn tại trên trang web.
5. Mọi chốt chặn nghiệp vụ nằm ở **server** (`validate`/`before_submit`/trong endpoint).
   Client chỉ làm UX (báo lỗi sớm) — không bao giờ là chốt duy nhất.
6. Patch/setup **idempotent**: chạy `bench migrate` nhiều lần không được sinh trùng/lỗi.
7. Test đặt trong app, chạy bằng `bench --site <site> run-tests --app miyano_portal`.
   339 test hiện có **phải giữ xanh**. Tính năng mới bắt buộc kèm test (cách ly dữ liệu + ngoại lệ NL).

## 10 quyết định nền tảng — KHÔNG ĐƯỢC VI PHẠM (dù prompt yêu cầu "gộp cho gọn")

1. **Kho khách hàng KHÔNG dùng tồn kho ERPNext**: không `Warehouse`, `Bin`, `Stock Entry`,
   `Stock Ledger Entry`, không gắn `Company`. Lý do: `enable_perpetual_inventory=1` — mọi giao dịch
   kho ERPNext ghi bút toán lên sổ kế toán Miyano, trong khi hàng trong kho khách là tài sản CỦA KHÁCH.
2. **Sổ kho khách (`Customer Stock Ledger Entry`) là append-only**: không sửa/xoá dòng sổ.
   Huỷ phiếu = sinh **phiếu đảo** ngược dấu (cờ `flags.dang_tao_dao` — điều kiện duy nhất được tạo
   loại "Phiếu đảo"; mọi điều kiện theo giá trị field đều giả được).
3. `Customer Stock Lot Balance` là **cache dẫn xuất** — luôn dựng lại được từ sổ. Sửa tồn = sửa qua
   phiếu, không bao giờ UPDATE thẳng balance.
4. **Hook `Delivery Note` không bao giờ ném lỗi ra ngoài** (`_chay_an_toan`): giao hàng của Miyano
   không được phụ thuộc kho khách. Hook chỉ sinh hiệu ứng phụ ở `on_submit`/`on_cancel`, không `before_*`.
5. Một DN → **một** phiếu nhập (docstatus < 2); phiếu tự sinh luôn ở trạng thái **NHÁP** — thủ kho
   kiểm hàng rồi mới ghi sổ.
6. **Không cho tồn âm** — chặn ở `before_submit` phiếu xuất, cộng dồn theo (vật tư, lô) trước khi so.
7. **Phân quyền kho = KHÔNG có DocPerm cho role `Customer`** trên các doctype kho/NCC/yêu cầu.
   Mọi truy cập qua endpoint whitelist tự suy khách/kho từ **phiên đăng nhập** (`get_portal_kho()`).
   KHÔNG endpoint nào nhận `customer`/`kho` từ client. `frappe.get_doc` KHÔNG tự check quyền —
   endpoint nhận tên chứng từ từ client **bắt buộc** gọi `check_permission` / tự kiểm sở hữu.
8. **Không có URL file công khai**: PDF/Excel/HĐĐT đều đi qua endpoint kiểm phiên + sở hữu từng lần
   (`kho_phieu_pdf`, `portal_einvoice_download`...). Người dùng cổng không dùng được `/printview`.
9. **Đơn giá đi theo lô**, bình quân gia quyền tính lại **cả khi delta âm** (phiếu đảo của phiếu nhập
   mang giá phiếu gốc) — bỏ bước này là giá trị sổ lệch vĩnh viễn.
10. **Hạn mức HĐNT**: kiểm sau khi GỘP dòng trùng mã; hạn mức khai **0 = không giới hạn** (BR-O15) —
    dòng đó KHÔNG gắn `against_blanket_order` (cơ chế gốc ERPNext coi 0 là cấm đặt) nhưng vẫn gắn
    `custom_hdnt` để truy vết.

## Chống lặp & an toàn dữ liệu

- Đặt hàng idempotent theo `custom_request_id` (unique) — nhận lại cùng id → trả đơn đã tạo.
- Workflow `Sales Order - Client Portal` áp cho **mọi** SO (chấp nhận — VĐ-4); duyệt theo ngưỡng
  `Miyano Portal Settings.nguong_duyet_2_tang` (rỗng = một tầng).
- Trước go-live: bọc `frappe.desk.search.search_link` chặn `ignore_user_permissions` với Website User (VĐ-1).

## Lệnh thường dùng

```bash
bench --site erptest.local migrate          # cài patch/schema
bench --site erptest.local run-tests --app miyano_portal
bench build --app miyano_portal             # build SPA
bench --site erptest.local execute miyano_portal.setup.demo_kho_flow.chay_tat_ca   # dữ liệu demo/UAT
```

## Thứ tự đọc khi nhận việc mới

1. `DevHandoff/00_INDEX.md` → chọn đúng PRD epic (`1x_PRD_*.md`).
2. Tra `20_DataDict.md` (trường/doctype) + `30_API_Spec.md` (endpoint) của epic đó.
3. Đối chiếu quy tắc gốc trong `BA-miyano_portal_v2.md` (mã BR/NL nêu trong PRD).
4. Viết code + test theo `40_TestCases.md`; UI theo `FormSpec` + `50_Prototype_ClientPortal_v2.html`.
