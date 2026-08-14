# Tự lập HĐĐT khi submit Sales Invoice + cho khách xem PDF Fast — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Submit một `Sales Invoice` → job nền tự lập chứng từ HĐĐT từ từng phiếu giao của hoá đơn và lấy về bản in thử PDF do Fast dựng; khách mở cổng thấy chính file PDF đó ở cả trang *Hoá đơn & công nợ* lẫn *chi tiết đơn hàng*.

**Architecture:** Hook `Sales Invoice.on_submit` chỉ đẩy `frappe.enqueue`, không bao giờ ném lỗi ra ngoài. Job gọi hai hàm whitelist sẵn có của module HĐĐT (`builder.create_from_delivery_note` → `actions.preview_draft`) cho từng phiếu giao, dừng ở trạng thái `02 - Đã xem nháp`, ghi kết quả thành Comment trên Sales Invoice. Cổng có hai đường đọc: khối cũ neo theo `Sales Invoice` (thêm nhóm trạng thái `nhap`) và một đường mới neo theo `Delivery Note` (vì chứng từ HĐĐT sinh ra chỉ có `delivery_note`, chưa chắc có `sales_invoice`). Hai đường tải file dùng chung một helper phục vụ file.

**Tech Stack:** Frappe v15 / ERPNext (Python), Vue 3 SPA (`frontend/`), module HĐĐT `apps/erpnext/erpnext/einvoice/` (của team khác — chỉ gọi API whitelist, không sửa).

**Spec:** `docs/superpowers/specs/2026-08-14-hddt-tu-dong-tu-sales-invoice-design.md`

## Global Constraints

- Fieldname tiếng Việt **không dấu** (`so_luong`, `han_su_dung`); DocType tiếng Anh; label tiếng Việt có dấu. Không camelCase cho fieldname.
- Giao diện toàn tiếng Việt; tiền `1.234.567 ₫` không thập phân; ngày `dd/mm/yyyy`.
- Chỉ thêm endpoint `@frappe.whitelist()` trong `api/portal.py` / `api/kho.py`. Không REST controller riêng.
- SPA gọi API bằng `fetch` + CSRF (`frontend/src/api.js`); `frappe.call` KHÔNG tồn tại trên trang web.
- **Quyết định nền tảng #7:** role `Customer` không có DocPerm nào trên `Fast EInvoice Document`. Không endpoint nào nhận `customer` từ client; khách suy từ phiên. Tham số tên chứng từ do client gửi **chỉ được dùng để LỌC trong tập đã tự suy ra và đã đối chiếu `customer`**, không bao giờ `frappe.get_doc` thẳng.
- **Quyết định nền tảng #8:** không có URL file công khai. JSON trả về chỉ mang cờ boolean, không mang đường dẫn file. Kiểm quyền + kiểm `File` đính đúng chứng từ ở **từng lần** tải. Ghi `Access Log` mỗi lần phục vụ file.
- **Quyết định nền tảng #4 (áp cho hook mới):** hook sinh hiệu ứng phụ không bao giờ ném lỗi ra ngoài — lập HĐĐT không có quyền chặn việc submit hoá đơn bán hàng.
- Patch/setup idempotent; `bench migrate` chạy lại nhiều lần không lỗi.
- Test chạy bằng `bench --site erptest.local run-tests --app miyano_portal`. **836 test hiện có phải giữ xanh** trừ đúng một ca được sửa có chủ ý ở Task 1.
- Không gọi `check_enabled()` trên bất kỳ đường ĐỌC nào của cổng — module HĐĐT có thể tắt, tắt không được làm chết trang.
- Câu cảnh báo pháp lý do **server** trả (`einvoice.CANH_BAO_NHAP`), frontend không gõ lại.

## Bối cảnh cần biết trước khi bắt đầu

**Vòng đời chứng từ HĐĐT** (`erpnext/einvoice/constants.py`): `01 - Nháp` → `02 - Đã xem nháp` → `03 - Chờ khách duyệt` → `04 - Khách đã duyệt` → `05 - Đang phát hành` → `06 - Đã phát hành` → `07` → `08` → (`09` CQT từ chối / `10` đã điều chỉnh / `11` đã thay thế / `12` huỷ nội bộ / `98` cần đối soát / `99` lỗi).

**Ba nút thủ công sẵn có** — plan này tự động hoá hai nút đầu:
- `erpnext.einvoice.builder.create_from_delivery_note(delivery_note)` → trả tên chứng từ, trạng thái `01`, **không kèm file nào**.
- `erpnext.einvoice.actions.preview_draft(fei, client=None)` → gọi Fast `action=600`, đính PDF vào field `draft_pdf`, chuyển sang `02`. **Tham số `client` cho phép tiêm FastClient giả trong test** — dùng nó, không mock mạng.
- `erpnext.einvoice.actions.send_draft_to_customer(...)` → **KHÔNG gọi trong plan này.**

**Đã kiểm trên site `erptest.local`:** `Fast EInvoice Settings.enabled = 1`, `require_customer_approval = 1`, đã có credential Fast. Nút "Gửi bản nháp cho khách" ở Desk chỉ mở theo `doc.status ∈ {02,03,04}` (`form_state.py::BUTTONS`) — không cờ ẩn nào khác, nên dừng job ở `02` là kế toán bấm gửi được ngay.

---

## File Structure

| File | Trách nhiệm |
|---|---|
| `miyano_portal/hddt_tu_dong.py` **(tạo)** | Hook `on_submit` + job nền. Nơi DUY NHẤT gọi `builder`/`actions` của module HĐĐT. |
| `miyano_portal/einvoice.py` **(sửa)** | Adapter đọc: nhóm trạng thái `nhap`, đường đọc neo theo Delivery Note. Nơi DUY NHẤT ánh xạ tên trường module HĐĐT. |
| `miyano_portal/api/portal.py` **(sửa)** | Endpoint whitelist + helper phục vụ file dùng chung. |
| `miyano_portal/hooks.py` **(sửa)** | Đăng ký `doc_events["Sales Invoice"]["on_submit"]`. |
| `frontend/src/components/HoaDonNhap.vue` **(tạo)** | Component hiển thị bản nháp dùng chung cho HAI màn hình: PDF nhúng là chính, bảng dòng hàng là dự phòng. |
| `frontend/src/views/Invoices.vue` **(sửa)** | Gắn component vào khối HĐĐT của trang Hoá đơn & công nợ. |
| `frontend/src/views/OrderDetail.vue` **(sửa)** | Gắn component vào khối từng đợt giao. |
| `miyano_portal/tests/test_e7b_tu_dong.py` **(tạo)** | Test job tự động. |
| `miyano_portal/tests/test_e7_hddt_nhap.py` **(tạo)** | Test đường đọc + tải neo theo Delivery Note. |
| `miyano_portal/tests/test_e7_hddt.py` **(sửa 1 ca)** | Ca TC-E7-01 đổi kỳ vọng theo nhóm `nhap`. |
| `miyano_portal/tests/test_e3_giao_dien.py` **(sửa 1 assertion)** | Thêm khoá `co_hoa_don_nhap` vào bộ so sánh chính xác `dot_giao`. |

**Mã tái dùng được:** commit `7d84b11` (nhánh riêng, **chưa review**) đã dựng phần lớn Task 2/3/5. Lấy ra bằng `git show 7d84b11 -- <đường dẫn>`. Coi như code mới: đọc lại từng dòng, không cherry-pick mù.

---

## Task 1: Nhóm trạng thái `nhap` trong adapter

Tách 01–04 khỏi nhóm mờ `dang_phat_hanh` để trang Hoá đơn & công nợ gọi đúng tên "Hoá đơn nháp".

**Files:**
- Modify: `miyano_portal/einvoice.py` (`_STATUS_META`, `_CHUA_PHAT_HANH`, `_UU_TIEN_CHINH`, `_FIELDS`, `_muc_cho`, `co_the_tai`)
- Modify: `miyano_portal/tests/test_e7_hddt.py` (đúng 1 ca)
- Test: `miyano_portal/tests/test_e7_hddt.py`

**Interfaces:**
- Consumes: không có (task đầu tiên)
- Produces: nhóm hiển thị `"nhap"`; khoá mới `nhap_tai_duoc: bool` trong dict do `_muc_cho()` trả về; hằng `einvoice.CANH_BAO_NHAP: str`; `co_the_tai(fei_row) -> bool` giữ nguyên chữ ký nhưng **loại thêm** nhóm `nhap`.

### CÁI BẪY phải xử lý trong task này

`co_the_tai()` hiện là `group not in _CHUA_PHAT_HANH and group not in _NHOM_LOI`. Nếu 01–04 rời `dang_phat_hanh` sang nhóm mới mà không sửa hàm này, `co_the_tai()` sẽ trả **True** cho một bản nháp → `portal_einvoice_download(loai="pdf")` cho phép tải **hoá đơn chính thức** trên một chứng từ chưa phát hành. Đó là lỗi nghiêm trọng, và test `test_trang_thai_chua_phat_hanh_chan_du_co_file_that` sẽ bắt được — **đừng sửa test đó cho xanh, hãy sửa `co_the_tai`**.

- [ ] **Step 1: Viết test mới cho nhóm `nhap`**

Thêm vào cuối `miyano_portal/tests/test_e7_hddt.py`:

```python
class TestNhomNhap(_E7Fixture):
    """01–04 là BẢN NHÁP có thật, khách xem được — khác hẳn "đang phát hành"
    (05, nội dung đã chốt, đang chờ Fast) và khác "chưa có chứng từ nào"
    (NL-12.1 — công nợ vẫn hiện bình thường)."""

    def _dinh_pdf_nhap(self, fei_doc):
        from erpnext.einvoice.test_fixtures import minimal_pdf_bytes
        from frappe.utils.file_manager import save_file

        f = save_file(f"Nhap_{fei_doc.name}.pdf", minimal_pdf_bytes(), FEI, fei_doc.name, is_private=1)
        frappe.db.set_value(FEI, fei_doc.name, "draft_pdf", f.file_url, update_modified=False)
        fei_doc.reload()
        return f

    def test_bon_trang_thai_nhap_deu_vao_nhom_nhap(self):
        for status in ("01 - Nháp", "02 - Đã xem nháp", "03 - Chờ khách duyệt", "04 - Khách đã duyệt"):
            with self.subTest(status=status):
                si, fei = self._chain(CUSTOMER_BM, status=status, dinh_pdf=False)
                block = einvoice.block_for(si.name, CUSTOMER_BM)["chinh"]
                self.assertEqual(block["trang_thai"], "nhap")
                self.assertEqual(block["nhan"], "Hoá đơn nháp")

    def test_co_pdf_nhap_thi_nhap_tai_duoc(self):
        si, fei = self._chain(CUSTOMER_BM, status="02 - Đã xem nháp", dinh_pdf=False)
        self._dinh_pdf_nhap(fei)
        block = einvoice.block_for(si.name, CUSTOMER_BM)["chinh"]
        self.assertTrue(block["nhap_tai_duoc"])
        self.assertFalse(block["tai_duoc"], "nút PDF CHÍNH THỨC vẫn phải tắt")

    def test_chua_co_pdf_nhap_thi_khong_tai_duoc(self):
        si, fei = self._chain(CUSTOMER_BM, status="01 - Nháp", dinh_pdf=False)
        block = einvoice.block_for(si.name, CUSTOMER_BM)["chinh"]
        self.assertFalse(block["nhap_tai_duoc"])

    def test_05_van_la_dang_phat_hanh(self):
        si, fei = self._chain(CUSTOMER_BM, status="05 - Đang phát hành", dinh_pdf=False)
        block = einvoice.block_for(si.name, CUSTOMER_BM)["chinh"]
        self.assertEqual(block["trang_thai"], "dang_phat_hanh")

    def test_co_the_tai_van_chan_ban_nhap(self):
        """Chốt chống lỗi nghiêm trọng: nhóm `nhap` KHÔNG được mở đường tải
        PDF CHÍNH THỨC. `co_the_tai` phục vụ `portal_einvoice_download`."""
        for status in ("01 - Nháp", "02 - Đã xem nháp", "03 - Chờ khách duyệt", "04 - Khách đã duyệt"):
            with self.subTest(status=status):
                self.assertFalse(einvoice.co_the_tai(frappe._dict(status=status)))

    def test_khoi_json_khong_lo_duong_dan_draft_pdf(self):  # BR-E4
        import json

        si, fei = self._chain(CUSTOMER_BM, status="02 - Đã xem nháp", dinh_pdf=False)
        f = self._dinh_pdf_nhap(fei)
        block = einvoice.block_for(si.name, CUSTOMER_BM)
        self.assertNotIn(f.file_url, json.dumps(block, default=str))

    def test_canh_bao_phap_ly_do_server_tra(self):
        self.assertIn("KHÔNG có giá trị pháp lý", einvoice.CANH_BAO_NHAP)
        self.assertIn("chưa ký số", einvoice.CANH_BAO_NHAP)
```

- [ ] **Step 2: Chạy test để chắc chắn nó ĐỎ**

```bash
cd /home/hoangvietyeuem/frappe-bench-yhct
bench --site erptest.local run-tests --app miyano_portal --module miyano_portal.tests.test_e7_hddt
```
Kỳ vọng: các ca của `TestNhomNhap` đỏ (`'dang_phat_hanh' != 'nhap'`, `KeyError: 'nhap_tai_duoc'`, `AttributeError: CANH_BAO_NHAP`).

- [ ] **Step 3: Sửa `_STATUS_META` và các tập nhóm**

Trong `miyano_portal/einvoice.py`, đổi 4 dòng đầu của `_STATUS_META` và bổ sung nhóm:

```python
_STATUS_META = {
    # 01–04 là BẢN NHÁP có thật — khách xem được nội dung và tải được bản in
    # thử khi Fast đã dựng (`draft_pdf`). Gọi chúng là "Đang phát hành HĐĐT"
    # như bản trước là nói sai: chưa ai bấm phát hành cả, và giấu mất thứ
    # khách đang có quyền xem.
    "01 - Nháp": ("nhap", "Hoá đơn nháp", "b-gray"),
    "02 - Đã xem nháp": ("nhap", "Hoá đơn nháp", "b-gray"),
    "03 - Chờ khách duyệt": ("nhap", "Hoá đơn nháp", "b-gray"),
    "04 - Khách đã duyệt": ("nhap", "Hoá đơn nháp", "b-gray"),
    # 05 mới thật sự là "đã bấm phát hành, đang chờ Fast": nội dung đã chốt,
    # không còn là bản để khách góp ý.
    "05 - Đang phát hành": ("dang_phat_hanh", "Đang phát hành HĐĐT", "b-gray"),
    # ... (8 dòng còn lại giữ NGUYÊN)
}
```

Bổ sung ngay dưới `_NHOM_LOI`:

```python
# NL-12.1: nhóm "chưa có gì để xem" — không nút tải, không phải lỗi. Nhóm này
# cũng là mặc định khi CHƯA có chứng từ HĐĐT nào (`khoi_mac_dinh`).
_CHUA_PHAT_HANH = {"dang_phat_hanh"}
_NHOM_LOI = {"loi"}
# MỚI: bản nháp — có nội dung để xem, có thể có PDF nháp, nhưng TUYỆT ĐỐI
# không phải hoá đơn chính thức.
_NHOM_NHAP = {"nhap"}

# Câu cảnh báo đi CÙNG dữ liệu, không để riêng bên frontend: chính docstring
# `actions.send_draft_to_customer` của module HĐĐT chốt rằng gửi bản nháp mà
# không nói rõ là để khách hiểu nhầm đã có hoá đơn. Một lần sửa giao diện làm
# rơi mất câu này là một lần khách tưởng mình đang cầm chứng từ thuế.
CANH_BAO_NHAP = (
    "Bản nháp — chưa có số hoá đơn, chưa ký số, chưa gửi Cơ quan Thuế, "
    "KHÔNG có giá trị pháp lý. Số liệu có thể thay đổi trước khi phát hành."
)
```

Trong `_UU_TIEN_CHINH`, thêm `nhap` **cùng hạng 1** với `dang_phat_hanh`:

```python
_UU_TIEN_CHINH = {
    "da_phat_hanh": 0, "cqt_tu_choi": 0,
    # `nhap` cùng hạng 1: một bản điều chỉnh đang soạn (01) KHÔNG được che
    # bản gốc còn nguyên giá trị pháp lý — đúng lỗi C-1 đã sửa ở review vòng 1.
    "dang_phat_hanh": 1, "loi": 1, "nhap": 1,
    "da_dieu_chinh": 2, "da_thay_the": 2, "da_huy": 2,
}
```

- [ ] **Step 4: Thêm `draft_pdf` vào `_FIELDS` và cờ `nhap_tai_duoc` vào `_muc_cho`**

Trong `_FIELDS`, thêm `"draft_pdf"` (khối hiển thị cần biết CÓ file hay không, nhưng không bao giờ trả đường dẫn ra ngoài).

Trong `_muc_cho()`, ngay sau dòng `tai_duoc = ...`, thêm:

```python
    # Nút tải BẢN NHÁP — tách hẳn khỏi `tai_duoc` (PDF chính thức). Hai nút
    # phục vụ hai file khác nhau, hai chốt trạng thái NGƯỢC nhau; gộp một cờ
    # là sớm muộn cũng giao nhầm bản nháp như một chứng từ thuế.
    nhap_tai_duoc = group in _NHOM_NHAP and bool(fei.draft_pdf)
```

và thêm `"nhap_tai_duoc": nhap_tai_duoc,` vào dict `muc`.

- [ ] **Step 5: Sửa `co_the_tai` — chốt chống lỗi nghiêm trọng**

```python
def co_the_tai(fei_row):
    """`True` nếu bản ghi được phép tải **PDF CHÍNH THỨC** (`official_pdf`).

    Loại cả `_NHOM_NHAP`: bản nháp có thể ĐÃ có file (`draft_pdf`) và trạng
    thái của nó không nằm trong `_CHUA_PHAT_HANH` nữa kể từ khi tách nhóm —
    quên dòng đó là mở đường giao một bản in thử cho khách như thể nó là
    chứng từ thuế. Bản nháp đi đường riêng (`nhap_tai_duoc` + endpoint
    `loai="nhap"`)."""
    group, _label, _badge = _meta(fei_row.status)
    return group not in _CHUA_PHAT_HANH and group not in _NHOM_LOI and group not in _NHOM_NHAP
```

- [ ] **Step 6: Sửa `khoi_mac_dinh` cho đúng nhóm**

`khoi_mac_dinh()` (chưa có chứng từ HĐĐT nào) **giữ nguyên** `_MAC_DINH = ("dang_phat_hanh", "Đang phát hành HĐĐT", "b-gray")` — NL-12.1. Chỉ thêm khoá mới cho đồng dạng với `_muc_cho`:

```python
        "chinh": {
            "fei": None, "trang_thai": group, "nhan": label, "badge": badge,
            "tai_duoc": False, "nhap_tai_duoc": False, "ho_tro": False,
        },
```

- [ ] **Step 7: Sửa ĐÚNG MỘT ca test cũ**

`test_chua_ghi_so_hddt_khong_nut_tai_cong_no_van_hien` (TC-E7-01) — đây là ca DUY NHẤT trong 40 test E7 đổi kỳ vọng:

```python
    def test_chua_ghi_so_hddt_khong_nut_tai_cong_no_van_hien(self):  # TC-E7-01
        si, fei = self._chain(CUSTOMER_BM, status="01 - Nháp", dinh_pdf=False)
        block = einvoice.block_for(si.name, si.customer)["chinh"]
        # ĐỔI CÓ CHỦ Ý (E7b): 01–04 nay là nhóm "nhap" chứ không còn gộp vào
        # "dang_phat_hanh" — khách được XEM bản nháp. Điều KHÔNG đổi, và là
        # thứ ca này thật sự canh giữ: chưa có số hoá đơn thì không có nút tải
        # PDF chính thức, và công nợ vẫn hiển thị bình thường.
        self.assertEqual(block["trang_thai"], "nhap")
        self.assertFalse(block["tai_duoc"])
        self.assertFalse(block["ho_tro"])
        frappe.set_user(BM_USER)
        rows = {r["name"]: r for r in portal.portal_invoices(limit=200)}
        self.assertIn(si.name, rows)
        self.assertIn("outstanding_amount", rows[si.name])
```

**KHÔNG sửa các ca sau — chúng phải tự xanh, và đỏ nghĩa là code sai:**
`test_khong_co_fei_cung_la_dang_phat_hanh` (không có FEI → `khoi_mac_dinh`) ·
`test_status_meta_khop_dung_14_ma_that` (chỉ so tập KHOÁ, không so nhóm) ·
`test_a_dieu_chinh_dang_soan_khong_che_ban_goc` (xanh nhờ `nhap` hạng 1) ·
`test_bao_loi_khong_lam_mat_ca_danh_sach_hoa_don` (đi qua `khoi_mac_dinh`) ·
`test_trang_thai_chua_phat_hanh_khong_tai_duoc` và
`test_trang_thai_chua_phat_hanh_chan_du_co_file_that` (xanh nhờ Step 5).

- [ ] **Step 8: Chạy toàn bộ test E7**

```bash
bench --site erptest.local run-tests --app miyano_portal --module miyano_portal.tests.test_e7_hddt
```
Kỳ vọng: OK. Nếu `test_trang_thai_chua_phat_hanh_chan_du_co_file_that` đỏ → Step 5 chưa đúng, **sửa `co_the_tai`, không sửa test**.

- [ ] **Step 9: Commit**

```bash
git add miyano_portal/einvoice.py miyano_portal/tests/test_e7_hddt.py
git commit -m "feat(portal): E7b — tách nhóm trạng thái 'nhap' (01–04) khỏi 'dang_phat_hanh'

Khách được XEM bản nháp thay vì thấy một nhãn mờ. co_the_tai() loại thêm
nhóm nhap để nút PDF chính thức không bao giờ phục vụ một bản in thử.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

## Task 2: Đường đọc neo theo Delivery Note

Chứng từ HĐĐT sinh từ phiếu giao **chỉ** có `fei.delivery_note`, không có `fei.sales_invoice` (`builder.create_from_delivery_note`). Phiếu giao có thể chưa được lập Sales Invoice nào → khối cũ không bám vào đâu.

**Files:**
- Modify: `miyano_portal/einvoice.py` (thêm khối cuối file)
- Modify: `miyano_portal/api/portal.py` (`portal_order_track`, endpoint mới)
- Test: `miyano_portal/tests/test_e7_hddt_nhap.py` (tạo)
- Modify: `miyano_portal/tests/test_e3_giao_dien.py` (1 assertion)

**Interfaces:**
- Consumes: `einvoice.CANH_BAO_NHAP` (Task 1)
- Produces:
  - `einvoice.ban_nhap_tho(delivery_note: str, dn_customer: str, fields=_FIELDS_NHAP) -> frappe._dict | None`
  - `einvoice.dn_co_hoa_don_nhap(delivery_notes: list[str], dn_customer: str) -> set[str]`
  - `einvoice.nhap_cho_delivery_note(delivery_note: str, dn_customer: str) -> dict | None`
  - `portal._dn_cua_khach(delivery_note: str) -> Document`
  - `portal.portal_einvoice_nhap(delivery_note: str) -> dict | None`
  - khoá `co_hoa_don_nhap: bool` trên mỗi phần tử `deliveries[]` và `dot_giao[]` của `portal_order_track`

- [ ] **Step 1: Lấy mã đã dựng ở nhánh riêng ra để đọc**

```bash
cd /home/hoangvietyeuem/frappe-bench-yhct/apps/miyano_portal
git show 7d84b11 -- miyano_portal/einvoice.py > /tmp/e7b-einvoice.diff
git show 7d84b11 -- miyano_portal/api/portal.py > /tmp/e7b-portal.diff
git show 7d84b11 -- miyano_portal/tests/test_e7_hddt_nhap.py > /tmp/e7b-test.diff
```

Commit `7d84b11` **chưa được review**. Đọc từng dòng trước khi dùng. Bốn chỗ **phải sửa** so với bản đó:
1. Bản cũ tự khai `_NHAP_STATUSES` và `CANH_BAO_NHAP` trong khối riêng — nay `CANH_BAO_NHAP` đã có từ Task 1, **không khai lần hai**.
2. Bản cũ ghi trong comment rằng "cố ý KHÔNG đụng `_STATUS_META`" — nay Task 1 đã đụng rồi, sửa lại comment cho khỏi nói sai.
3. `_NHAP_STATUSES` phải suy ra từ `_STATUS_META` (mọi mã có nhóm `nhap`) thay vì khai tay lần thứ hai — hai nơi khai cùng một tập là hai nơi lệch nhau được.
4. Bản cũ trả khoá `pdf_tai_duoc`; đổi thành **`nhap_tai_duoc`** cho khớp tên Task 1 đã đặt ở `_muc_cho`.

- [ ] **Step 2: Viết test (dựa trên `/tmp/e7b-test.diff`, sửa theo 4 điểm trên)**

Tạo `miyano_portal/tests/test_e7_hddt_nhap.py`. Lấy nguyên bộ test của commit cũ, rồi sửa: đổi mọi `pdf_tai_duoc` → `nhap_tai_duoc`; bỏ ca `test_khong_phu_thuoc_cong_tac_fast` nếu nó assert `enabled == 0` (site này bật thật — thay bằng cách **tự tắt** `frappe.db.set_single_value("Fast EInvoice Settings", "enabled", 0)` rồi mới assert). Thêm ca mới khoá điểm 3:

```python
    def test_nhap_statuses_suy_tu_status_meta(self):
        """Một tập trạng thái khai ở hai nơi là hai nơi lệch nhau được. Nếu
        `_STATUS_META` đổi nhóm một mã, đường đọc theo phiếu giao phải đổi
        theo NGAY, không cần ai nhớ sửa chỗ thứ hai."""
        tu_meta = {ma for ma, (nhom, _l, _b) in einvoice._STATUS_META.items() if nhom == "nhap"}
        self.assertEqual(set(einvoice._NHAP_STATUSES), tu_meta)
        self.assertEqual(len(tu_meta), 4)
```

- [ ] **Step 3: Chạy test để chắc chắn nó ĐỎ**

```bash
bench --site erptest.local run-tests --app miyano_portal --module miyano_portal.tests.test_e7_hddt_nhap
```
Kỳ vọng: `AttributeError: module 'miyano_portal.einvoice' has no attribute 'ban_nhap_tho'`.

- [ ] **Step 4: Thêm khối đọc theo Delivery Note vào `einvoice.py`**

Dán phần thêm của `/tmp/e7b-einvoice.diff` vào cuối `miyano_portal/einvoice.py`, với 4 sửa đổi ở Step 1. Riêng `_NHAP_STATUSES` viết lại thành:

```python
# Suy TỪ `_STATUS_META` chứ không khai tay lần thứ hai — xem
# `test_nhap_statuses_suy_tu_status_meta`.
_NHAP_STATUSES = tuple(ma for ma, (nhom, _l, _b) in _STATUS_META.items() if nhom == "nhap")
```

và trong `nhap_cho_delivery_note()`, khoá trả về đổi thành:

```python
        "canh_bao": CANH_BAO_NHAP,
        "nhap_tai_duoc": bool(fei.draft_pdf),
```

- [ ] **Step 5: Thêm endpoint + cờ vào `api/portal.py`**

Hai hàm này ngắn và là chốt quyền — viết thẳng, đừng dán mù:

```python
def _dn_cua_khach(delivery_note):
    """Kiểm sở hữu MỘT phiếu giao qua phiên — khuôn giống `_ho_so_cua_hoa_don`
    (Sales Invoice). `frappe.get_doc` KHÔNG tự kiểm quyền: `check_permission`
    mới là nơi hook `has_permission` (`permissions.generic_has_permission`)
    thật sự chạy, và chốt `dn.customer` là lớp thứ hai không phụ thuộc cấu
    hình DocPerm/User Permission."""
    customer = get_portal_customer()
    dn = frappe.get_doc("Delivery Note", delivery_note)
    dn.check_permission("read")
    if dn.customer != customer:
        raise frappe.PermissionError("Phiếu giao không thuộc đơn vị của bạn.")
    return dn


@frappe.whitelist()
def portal_einvoice_nhap(delivery_note):
    """Khối "Hoá đơn nháp" của một phiếu giao — dòng hàng + tổng tiền của
    chứng từ HĐĐT, kèm câu cảnh báo pháp lý đi CÙNG dữ liệu
    (`einvoice.CANH_BAO_NHAP`). `None` khi chưa lập.

    Neo theo Delivery Note chứ không theo Sales Invoice: bản ghi HĐĐT do
    `builder.create_from_delivery_note` sinh ra chỉ có `delivery_note`, và
    phiếu giao có thể chưa được lập hoá đơn bán hàng tại thời điểm đó."""
    dn = _dn_cua_khach(delivery_note)
    return einvoice.nhap_cho_delivery_note(dn.name, dn.customer)
```

Trong `portal_order_track`, ngay sau `dn_names = list(dict.fromkeys(dn_names))`:

```python
    # E7b — cờ "đợt giao này đã có hoá đơn nháp", MỘT truy vấn cho cả danh
    # sách (không hỏi từng phiếu trong vòng lặp bên dưới). Chỉ là CỜ; nội
    # dung đầy đủ lấy qua `portal_einvoice_nhap` khi khách bấm xem.
    #
    # Bọc lỗi CỐ Ý, cùng nguyên tắc với khối HĐĐT ở `portal_invoices` và
    # `delivery_hook._chay_an_toan`: module HĐĐT là của team khác — nó hỏng
    # thì mất CÁI CỜ, không được mất cả trang chi tiết đơn hàng. Bọc ở đây
    # (ngoài vòng lặp) nên một lần hỏng ghi đúng MỘT log, không N log.
    try:
        dn_co_nhap = einvoice.dn_co_hoa_don_nhap(dn_names, so.customer)
    except Exception:
        frappe.log_error(title=f"HĐĐT: không kiểm được hoá đơn nháp cho đơn {so.name}")
        dn_co_nhap = set()
```

Trong vòng lặp, thêm `"co_hoa_don_nhap": dn_name in dn_co_nhap,` vào **cả** dict `row` (`deliveries[]`) lẫn dict `dot` (`dot_giao[]`).

- [ ] **Step 6: Sửa assertion so-sánh-chính-xác ở `test_e3_giao_dien.py`**

Ca `test_TC_E3_06_hai_dot_du_thong_tin_dung_ty_le_dung_trang_thai_phieu` so `dot_giao` bằng `assertEqual` với dict đầy đủ. Thêm khoá mới vào **cả hai** dict kỳ vọng `g1`, `g2`:

```python
		# `co_hoa_don_nhap` (E7b): cờ "phiếu giao này đã có hoá đơn nháp" —
		# False ở đây vì chưa lập chứng từ HĐĐT nào. Nằm trong bộ so sánh
		# CHÍNH XÁC này là cố ý: một field mới lặng lẽ chui vào hợp đồng API
		# §1.2 phải làm test đỏ.
		self.assertEqual(g1, {
			"so_dot": 1, "delivery_note": dn1.name, "ngay": dn1.posting_date,
			"phan_tram": 60, "van_chuyen": "", "awb": "", "co_hoa_don_nhap": False,
			"phieu_nhap": {"name": phieu1.name, "trang_thai": "Nháp", "co_chenh_lech": False},
		})
```
(làm tương tự cho `g2` với `so_dot: 2`, `dn2`, `phan_tram: 40`, `phieu2`, `"Đã ghi sổ"`.)

- [ ] **Step 7: Chạy test**

```bash
bench --site erptest.local run-tests --app miyano_portal --module miyano_portal.tests.test_e7_hddt_nhap
bench --site erptest.local run-tests --app miyano_portal --module miyano_portal.tests.test_e3_giao_dien
```
Kỳ vọng: cả hai OK.

- [ ] **Step 8: Commit**

```bash
git add miyano_portal/einvoice.py miyano_portal/api/portal.py \
        miyano_portal/tests/test_e7_hddt_nhap.py miyano_portal/tests/test_e3_giao_dien.py
git commit -m "feat(portal): E7b — đường đọc hoá đơn nháp neo theo Delivery Note

Chứng từ HĐĐT sinh từ phiếu giao chỉ có delivery_note, chưa chắc có
sales_invoice — khối cũ neo theo Sales Invoice không bám vào đâu.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

## Task 3: Phục vụ file PDF nháp — helper dùng chung + hai đường tải

**Files:**
- Modify: `miyano_portal/api/portal.py`
- Test: `miyano_portal/tests/test_e7_hddt_nhap.py`, `miyano_portal/tests/test_e7_hddt.py`

**Interfaces:**
- Consumes: `einvoice.ban_nhap_tho`, `einvoice.resolve_all`, `einvoice.co_the_tai` (Task 1, 2); `portal._dn_cua_khach`, `portal._ho_so_cua_hoa_don`
- Produces:
  - `portal._phuc_vu_file(fei_row, field: str, ten_file: str, method: str) -> None` (ghi vào `frappe.local.response`)
  - `portal.portal_einvoice_nhap_pdf(delivery_note: str) -> None`
  - `portal.portal_einvoice_download(invoice, loai="pdf"|"nhap", fei=None) -> None` (thêm nhánh `"nhap"`)

- [ ] **Step 1: Viết test cho cả hai đường tải**

Thêm vào `miyano_portal/tests/test_e7_hddt_nhap.py`:

```python
class TestTaiPdfNhapTheoHoaDon(_NhapFixture):
    """Đường tải neo theo Sales Invoice — dùng ở trang Hoá đơn & công nợ."""

    def test_tai_duoc_ban_nhap_qua_hoa_don(self):
        from erpnext.einvoice.test_fixtures import minimal_pdf_bytes

        dn = self._tao_dn(CUSTOMER_BM)
        si = self._tao_si(CUSTOMER_BM, dn=dn)
        fei = self._tao_fei_nhap(CUSTOMER_BM, dn, status="02 - Đã xem nháp")
        self._dinh_pdf_nhap(fei)

        frappe.set_user(BM_USER)
        truoc = frappe.db.count("Access Log", {"export_from": FEI, "reference_document": fei.name})
        frappe.local.response = frappe._dict()
        portal.portal_einvoice_download(si.name, loai="nhap")

        noi_dung = frappe.local.response.filecontent
        if isinstance(noi_dung, str):
            noi_dung = noi_dung.encode()
        self.assertEqual(noi_dung, minimal_pdf_bytes())
        self.assertEqual(frappe.local.response.type, "pdf")
        sau = frappe.db.count("Access Log", {"export_from": FEI, "reference_document": fei.name})
        self.assertEqual(sau, truoc + 1)

    def test_da_phat_hanh_thi_loai_nhap_bi_chan(self):
        """Hai chốt NGƯỢC nhau: `loai="pdf"` phục vụ 06+, `loai="nhap"` phục
        vụ 01–04. Một chứng từ đã phát hành không còn bản nháp để giao."""
        dn = self._tao_dn(CUSTOMER_BM)
        si = self._tao_si(CUSTOMER_BM, dn=dn)
        fei = self._tao_fei_nhap(CUSTOMER_BM, dn, status="02 - Đã xem nháp")
        self._dinh_pdf_nhap(fei)
        frappe.db.set_value(FEI, fei.name, "status", "06 - Đã phát hành", update_modified=False)
        frappe.set_user(BM_USER)
        with self.assertRaises(frappe.ValidationError):
            portal.portal_einvoice_download(si.name, loai="nhap")

    def test_khach_khac_bi_chan(self):
        dn = self._tao_dn(CUSTOMER_BM)
        si = self._tao_si(CUSTOMER_BM, dn=dn)
        fei = self._tao_fei_nhap(CUSTOMER_BM, dn, status="02 - Đã xem nháp")
        self._dinh_pdf_nhap(fei)
        frappe.set_user(PXN_USER)
        with self.assertRaises(frappe.PermissionError):
            portal.portal_einvoice_download(si.name, loai="nhap")

    def test_loai_la_bi_tu_choi(self):
        dn = self._tao_dn(CUSTOMER_BM)
        si = self._tao_si(CUSTOMER_BM, dn=dn)
        self._tao_fei_nhap(CUSTOMER_BM, dn, status="02 - Đã xem nháp")
        frappe.set_user(BM_USER)
        with self.assertRaises(frappe.ValidationError):
            portal.portal_einvoice_download(si.name, loai="xml")
```

Và giữ nguyên bộ `TestTaiPdfNhap` (neo theo Delivery Note) lấy từ `/tmp/e7b-test.diff`. Trong đó **bắt buộc giữ** ca `test_chot_fei_customer_doc_lap_voi_chot_so_huu_phieu_giao`: nó dựng tình huống hai chốt đầu (`check_permission` + `dn.customer`) ĐỀU CHO QUA — phiếu giao đúng là của khách đang đăng nhập — trong khi bản ghi HĐĐT bị gán nhầm sang khách khác. Không có ca đó thì chốt `fei.customer` bên trong `ban_nhap_tho` chưa từng được kiểm ở tầng endpoint, mà đó chính là chốt mà quyết định nền tảng #7 dựa vào.

- [ ] **Step 2: Chạy test để chắc chắn ĐỎ**

```bash
bench --site erptest.local run-tests --app miyano_portal --module miyano_portal.tests.test_e7_hddt_nhap
```
Kỳ vọng: đỏ ở `loai="nhap"` (hiện bị từ chối vì `loai != "pdf"`).

- [ ] **Step 3: Tách helper phục vụ file dùng chung**

Thêm vào `miyano_portal/api/portal.py`, ngay trước `portal_einvoice_download`:

```python
def _phuc_vu_file(fei_row, field, ten_file, method):
    """Đọc một file đính kèm chứng từ HĐĐT rồi đẩy vào response.

    Dùng CHUNG cho cả bản chính thức (`official_pdf`) lẫn bản nháp
    (`draft_pdf`) — hai đường gọi có chốt TRẠNG THÁI ngược nhau nhưng phần
    "kiểm file thật sự đọc được rồi phục vụ" thì giống hệt; viết hai lần là
    hai chỗ có thể quên `make_access_log` hoặc quên lọc `attached_to_*`.

    Người gọi PHẢI tự kiểm sở hữu và trạng thái TRƯỚC khi gọi hàm này — hàm
    này không biết gì về khách của phiên.
    """
    duong_dan = fei_row.get(field)
    if not duong_dan:
        frappe.throw(
            "File đang được tạo, vui lòng thử lại sau ít phút.", frappe.ValidationError
        )

    # Lọc cả `attached_to_*` chứ không chỉ `file_url`: Frappe gộp file trùng
    # nội dung theo content hash nên nhiều `File` khác nhau có thể trỏ CHUNG
    # một url — chỉ lọc theo url sẽ tìm thấy record của chứng từ KHÁC dù bản
    # ghi của chính chứng từ này đã bị xoá.
    file_doc = frappe.db.get_value(
        "File",
        {
            "file_url": duong_dan,
            "attached_to_doctype": einvoice.FEI,
            "attached_to_name": fei_row.name,
        },
        "name",
    )
    if not file_doc:
        frappe.throw(
            "File bị thiếu hoặc hỏng trên hệ thống. Vui lòng liên hệ kế toán Miyano.",
            frappe.ValidationError,
        )
    content = frappe.get_doc("File", file_doc).get_content()

    from frappe.core.doctype.access_log.access_log import make_access_log

    make_access_log(
        doctype=einvoice.FEI, document=fei_row.name, file_type="pdf", method=method,
    )
    frappe.local.response.filename = ten_file
    frappe.local.response.filecontent = content
    frappe.local.response.type = "pdf"
```

- [ ] **Step 4: Viết lại `portal_einvoice_download` với hai nhánh tách bạch**

```python
@frappe.whitelist()
def portal_einvoice_download(invoice, loai="pdf", fei=None) -> None:
    """Tải file HĐĐT của một hoá đơn. `loai`:

    - `"pdf"`  — bản thể hiện hoá đơn ĐÃ PHÁT HÀNH (`official_pdf`), chốt
      trạng thái `einvoice.co_the_tai()` (06+).
    - `"nhap"` — bản in thử Fast dựng khi chứng từ còn ở 01–04
      (`draft_pdf`), chốt trạng thái NGƯỢC LẠI.

    Hai chốt ngược nhau nên tách nhánh rõ ràng, KHÔNG gộp điều kiện: gộp là
    sớm muộn cũng giao một bản in thử cho khách như thể nó là chứng từ thuế,
    hoặc chặn nhầm hoá đơn thật.

    Module HĐĐT không lưu XML ở đâu cả (không field nào chứa 'xml', đã kiểm
    JSON doctype) — `loai="xml"` bị từ chối kèm hướng dẫn liên hệ kế toán.

    Kiểm TỪNG LẦN tải (BR-E4, NL-12.5), không tin cờ đã tính lúc liệt kê.
    `fei` do client gửi CHỈ dùng để LỌC trong tập `resolve_all(invoice)` đã
    tự suy từ phiên và đã lọc đúng khách.
    """
    if loai not in ("pdf", "nhap"):
        frappe.throw(
            "Cổng chỉ cung cấp bản PDF thể hiện và bản nháp. Cần bản gốc XML "
            "có giá trị pháp lý, vui lòng liên hệ kế toán Miyano.",
            frappe.ValidationError,
        )

    _si, ho_so = _ho_so_cua_hoa_don(invoice)
    if not ho_so:
        frappe.throw("Chưa có hoá đơn điện tử cho chứng từ này.", frappe.ValidationError)

    if fei:
        muc = next((f for f in ho_so if f.name == fei), None)
        if not muc:
            raise frappe.PermissionError("Chứng từ HĐĐT không thuộc hoá đơn này.")
    else:
        muc = einvoice.chon_ban_ghi_chinh(ho_so)

    if loai == "nhap":
        if not einvoice.la_ban_nhap(muc):
            frappe.throw(
                "Chứng từ này không còn ở dạng nháp. Dùng nút tải hoá đơn điện tử.",
                frappe.ValidationError,
            )
        _phuc_vu_file(
            muc, "draft_pdf", f"Nhap_{muc.name}.pdf", "portal_einvoice_download_nhap"
        )
        return

    if not einvoice.co_the_tai(muc):
        frappe.throw(
            "Hoá đơn điện tử này chưa có file để tải. Bấm [Yêu cầu hỗ trợ] "
            "nếu cần Miyano hỗ trợ.",
            frappe.ValidationError,
        )
    _phuc_vu_file(
        muc, "official_pdf", f"{muc.fast_invoice_no or muc.name}.pdf",
        "portal_einvoice_download",
    )
```

- [ ] **Step 5: Thêm `la_ban_nhap` vào adapter**

Trong `miyano_portal/einvoice.py`, cạnh `co_the_tai`:

```python
def la_ban_nhap(fei_row):
    """`True` nếu bản ghi còn ở vòng nháp (01–04). Cặp đối xứng với
    `co_the_tai` — một hàm cho đường hoá đơn chính thức, một cho đường bản
    nháp, cùng đọc `_meta` nên không bao giờ lệch định nghĩa nhóm."""
    group, _label, _badge = _meta(fei_row.status)
    return group in _NHOM_NHAP
```

- [ ] **Step 6: Thêm `portal_einvoice_nhap_pdf` (neo theo Delivery Note)**

```python
@frappe.whitelist()
def portal_einvoice_nhap_pdf(delivery_note) -> None:
    """Tải bản in thử PDF theo PHIẾU GIAO — dùng ở màn chi tiết đơn hàng,
    nơi phiếu giao có thể chưa có Sales Invoice nào để bám vào.

    Cùng ràng buộc với `portal_einvoice_download`: kiểm sở hữu từng lần,
    không nhận tên chứng từ từ client, ghi `Access Log`."""
    dn = _dn_cua_khach(delivery_note)
    ban = einvoice.ban_nhap_tho(dn.name, dn.customer)
    if not ban:
        frappe.throw(
            "Phiếu giao này chưa có hoá đơn nháp. Nếu hoá đơn đã phát hành, "
            "xem ở mục Hoá đơn & công nợ.",
            frappe.ValidationError,
        )
    _phuc_vu_file(ban, "draft_pdf", f"Nhap_{dn.name}.pdf", "portal_einvoice_nhap_pdf")
```

- [ ] **Step 7: Chạy test**

```bash
bench --site erptest.local run-tests --app miyano_portal --module miyano_portal.tests.test_e7_hddt_nhap
bench --site erptest.local run-tests --app miyano_portal --module miyano_portal.tests.test_e7_hddt
```
Kỳ vọng: cả hai OK. Đặc biệt `test_tai_thanh_cong_ghi_log_va_dung_noi_dung` (đường cũ) phải còn xanh — helper mới không được đổi hành vi đường chính thức.

- [ ] **Step 8: Commit**

```bash
git add miyano_portal/api/portal.py miyano_portal/einvoice.py miyano_portal/tests/test_e7_hddt_nhap.py
git commit -m "feat(portal): E7b — phục vụ PDF bản nháp qua cả hai đường, helper dùng chung

loai='nhap' cho endpoint neo Sales Invoice + endpoint riêng neo Delivery
Note; hai chốt trạng thái ngược nhau nên tách nhánh, phần đọc file dùng chung.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

## Task 4: Job tự động khi submit Sales Invoice

**Files:**
- Create: `miyano_portal/hddt_tu_dong.py`
- Modify: `miyano_portal/hooks.py`
- Test: `miyano_portal/tests/test_e7b_tu_dong.py` (tạo)

**Interfaces:**
- Consumes: `erpnext.einvoice.builder.create_from_delivery_note(delivery_note) -> str`; `erpnext.einvoice.actions.preview_draft(fei, client=None) -> dict`
- Produces:
  - `hddt_tu_dong.tu_sales_invoice(doc, method=None) -> None` (hook)
  - `hddt_tu_dong.lap_hddt_cho_hoa_don(sales_invoice: str, client=None) -> dict` với khoá `{"tao": list[str], "bo_qua": list[dict(delivery_note, ly_do)], "ly_do": str | None}`

- [ ] **Step 1: Viết test**

Tạo `miyano_portal/tests/test_e7b_tu_dong.py`:

```python
"""E7b — submit Sales Invoice thì tự lập HĐĐT từ từng phiếu giao.

KHÔNG gọi mạng: `actions.preview_draft` nhận tham số `client`, nên test tiêm
một `FastClient` dùng `FakeTransport` của chính module HĐĐT
(`erpnext/einvoice/test_fast_client.py`) thay vì monkeypatch.

Ranh giới quan trọng nhất mà bộ test này canh giữ: job DỪNG ở `02 - Đã xem
nháp`. Không bao giờ tự gửi email cho khách — kế toán phải được liếc bản nháp
trước khi nó vào hộp thư khách hàng (quyết định Q1 của spec).
"""

import base64

import frappe
from frappe.tests.utils import FrappeTestCase

from erpnext.einvoice.fast_client import FastClient
from erpnext.einvoice.test_fast_client import FakeTransport, checkkey_ok, configure, envelope
from erpnext.einvoice.test_fixtures import make_delivery_note, minimal_pdf_bytes

from miyano_portal import hddt_tu_dong

FEI = "Fast EInvoice Document"


def pdf_response():
    return envelope(1, base64.b64encode(minimal_pdf_bytes()).decode())


class _TuDongFixture(FrappeTestCase):
    def setUp(self):
        frappe.db.rollback()
        configure(token="TOKEN-E7B", token_time=frappe.utils.now_datetime())

    def tearDown(self):
        frappe.db.rollback()

    def _client(self, so_lan=1):
        """FastClient giả trả `so_lan` phản hồi PDF — một cho mỗi phiếu giao."""
        return FastClient(transport=FakeTransport(checkkey_ok(), *([pdf_response()] * so_lan)))

    def _si_tu_dn(self, dn_list):
        si = frappe.new_doc("Sales Invoice")
        si.company = dn_list[0].company
        si.customer = dn_list[0].customer
        si.posting_date = frappe.utils.today()
        si.set_posting_time = 1
        si.update_stock = 0
        for dn in dn_list:
            for d in dn.items:
                si.append("items", {
                    "item_code": d.item_code, "qty": d.qty, "rate": d.rate,
                    "delivery_note": dn.name, "dn_detail": d.name,
                })
        si.insert(ignore_permissions=True)
        si.submit()
        return si

    def _fei_cua(self, dn_name):
        return frappe.get_all(
            FEI, filters={"delivery_note": dn_name}, fields=["name", "status", "draft_pdf"]
        )


class TestLapTuDong(_TuDongFixture):
    def test_mot_phieu_giao_ra_mot_chung_tu_o_02(self):
        dn = make_delivery_note()
        si = self._si_tu_dn([dn])
        ket_qua = hddt_tu_dong.lap_hddt_cho_hoa_don(si.name, client=self._client())

        self.assertEqual(len(ket_qua["tao"]), 1)
        rows = self._fei_cua(dn.name)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].status, "02 - Đã xem nháp")
        self.assertTrue(rows[0].draft_pdf, "phải có PDF do Fast dựng")

    def test_si_gop_nhieu_dot_giao_ra_nhieu_chung_tu(self):
        dn1, dn2 = make_delivery_note(), make_delivery_note()
        si = self._si_tu_dn([dn1, dn2])
        ket_qua = hddt_tu_dong.lap_hddt_cho_hoa_don(si.name, client=self._client(so_lan=2))

        self.assertEqual(len(ket_qua["tao"]), 2)
        self.assertEqual(len(self._fei_cua(dn1.name)), 1)
        self.assertEqual(len(self._fei_cua(dn2.name)), 1)

    def test_khong_bao_gio_tu_gui_email(self):
        """Ranh giới Q1. Trạng thái dừng ở 02, `draft_sent_time` phải rỗng —
        03 chỉ đặt được bằng `send_draft_to_customer`, mà job không gọi."""
        dn = make_delivery_note()
        si = self._si_tu_dn([dn])
        hddt_tu_dong.lap_hddt_cho_hoa_don(si.name, client=self._client())

        fei = frappe.get_doc(FEI, self._fei_cua(dn.name)[0].name)
        self.assertEqual(fei.status, "02 - Đã xem nháp")
        self.assertFalse(fei.draft_sent_time)
        self.assertFalse(fei.draft_sent_to)

    def test_chay_lai_khong_lap_trung(self):
        dn = make_delivery_note()
        si = self._si_tu_dn([dn])
        hddt_tu_dong.lap_hddt_cho_hoa_don(si.name, client=self._client())
        lan_hai = hddt_tu_dong.lap_hddt_cho_hoa_don(si.name, client=self._client())

        self.assertEqual(len(self._fei_cua(dn.name)), 1)
        self.assertEqual(lan_hai["tao"], [])
        self.assertEqual(len(lan_hai["bo_qua"]), 1)

    def test_si_khong_qua_phieu_giao_thi_khong_tao_gi(self):
        dn = make_delivery_note()
        si = frappe.new_doc("Sales Invoice")
        si.company, si.customer = dn.company, dn.customer
        si.posting_date = frappe.utils.today()
        si.append("items", {"item_code": dn.items[0].item_code, "qty": 1, "rate": 1000})
        si.insert(ignore_permissions=True)
        si.submit()

        ket_qua = hddt_tu_dong.lap_hddt_cho_hoa_don(si.name, client=self._client())
        self.assertEqual(ket_qua["tao"], [])
        self.assertIn("phiếu giao", ket_qua["ly_do"])

    def test_ghi_comment_len_sales_invoice(self):
        dn = make_delivery_note()
        si = self._si_tu_dn([dn])
        hddt_tu_dong.lap_hddt_cho_hoa_don(si.name, client=self._client())
        self.assertTrue(frappe.db.exists(
            "Comment", {"reference_doctype": "Sales Invoice", "reference_name": si.name}
        ))


class TestKhongLamVoSubmit(_TuDongFixture):
    def test_fast_tat_thi_submit_van_thanh_cong(self):
        frappe.db.set_single_value("Fast EInvoice Settings", "enabled", 0)
        dn = make_delivery_note()
        si = self._si_tu_dn([dn])          # submit KHÔNG được ném lỗi
        self.assertEqual(si.docstatus, 1)

        ket_qua = hddt_tu_dong.lap_hddt_cho_hoa_don(si.name, client=self._client())
        self.assertEqual(ket_qua["tao"], [])
        self.assertTrue(ket_qua["ly_do"])
        self.assertEqual(self._fei_cua(dn.name), [])

    def test_hook_nuot_loi_khong_chan_submit(self):
        from unittest.mock import patch

        dn = make_delivery_note()
        with patch.object(hddt_tu_dong.frappe, "enqueue", side_effect=Exception("hàng đợi chết")):
            si = self._si_tu_dn([dn])
        self.assertEqual(si.docstatus, 1)

    def test_si_tra_hang_khong_day_job(self):
        """Phiếu trả hàng bị `builder._load_delivery_note` từ chối thẳng
        ("dùng hóa đơn điều chỉnh giảm từ hóa đơn gốc"). Không lọc sớm thì
        mỗi giấy báo có là một Comment lỗi vô nghĩa.

        Kiểm THẲNG hàm hook với một doc giả thay vì dựng một giấy báo có
        thật: dựng credit note thật kéo theo `return_against`, số lượng âm và
        cả chuỗi validate của ERPNext — toàn thứ không liên quan đến điều ca
        này muốn khẳng định, và mỗi thứ là một cách để test đỏ vì lý do khác."""
        from unittest.mock import patch

        doc = frappe._dict(name="SI-TRA-TEST", is_return=1)
        with patch.object(hddt_tu_dong.frappe, "enqueue") as day_hang_doi:
            hddt_tu_dong.tu_sales_invoice(doc)
        day_hang_doi.assert_not_called()

    def test_si_thuong_thi_co_day_job(self):
        """Ca đối chứng của ca trên — nếu thiếu, một hàm `tu_sales_invoice`
        return sớm vô điều kiện cũng làm ca trên xanh."""
        from unittest.mock import patch

        doc = frappe._dict(name="SI-THUONG-TEST", is_return=0)
        with patch.object(hddt_tu_dong.frappe, "enqueue") as day_hang_doi:
            hddt_tu_dong.tu_sales_invoice(doc)
        day_hang_doi.assert_called_once()


class TestLoiTungPhieuKhongKeoTheoNhau(_TuDongFixture):
    def test_mot_phieu_hong_phieu_con_lai_van_chay(self):
        """Phiếu 1 đã có chứng từ HĐĐT sống → bỏ qua. Phiếu 2 vẫn phải ra
        chứng từ. Bọc lỗi phải nằm TRONG vòng lặp, không bọc cả vòng."""
        from erpnext.einvoice.builder import create_from_delivery_note

        dn1, dn2 = make_delivery_note(), make_delivery_note()
        create_from_delivery_note(dn1.name)          # dựng sẵn cho phiếu 1
        si = self._si_tu_dn([dn1, dn2])

        ket_qua = hddt_tu_dong.lap_hddt_cho_hoa_don(si.name, client=self._client())
        self.assertEqual(len(ket_qua["tao"]), 1)
        self.assertEqual(len(ket_qua["bo_qua"]), 1)
        self.assertEqual(ket_qua["bo_qua"][0]["delivery_note"], dn1.name)
        self.assertEqual(len(self._fei_cua(dn2.name)), 1)
```

- [ ] **Step 2: Chạy test để chắc chắn ĐỎ**

```bash
bench --site erptest.local run-tests --app miyano_portal --module miyano_portal.tests.test_e7b_tu_dong
```
Kỳ vọng: `ModuleNotFoundError: No module named 'miyano_portal.hddt_tu_dong'`.

- [ ] **Step 3: Viết `miyano_portal/hddt_tu_dong.py`**

```python
"""Tự lập chứng từ HĐĐT khi submit Sales Invoice — E7b.

Nơi DUY NHẤT của app này gọi vào module HĐĐT của team khác
(`erpnext/einvoice/`). Đổi chữ ký `builder.create_from_delivery_note` hay
`actions.preview_draft` là vỡ đúng file này, không rải ra chỗ khác.

Tự động tới đâu và VÌ SAO dừng ở đó (quyết định Q1 của spec): job chạy hai
nút đầu của quy trình — tạo chứng từ, rồi lấy bản in thử PDF từ Fast — và
**dừng ở `02 - Đã xem nháp`**. KHÔNG gọi `send_draft_to_customer`. Kế toán
phải được liếc bản nháp trước khi nó vào hộp thư khách; khách thì vẫn xem
được ngay trên cổng nên không ai phải chờ email. Nút "Gửi bản nháp cho khách"
ở Desk mở đúng từ trạng thái 02 (`form_state.py::BUTTONS`) nên kế toán bấm
tiếp được ngay.
"""

import frappe
from frappe import _

SI = "Sales Invoice"


def tu_sales_invoice(doc, method=None):
    """Hook `Sales Invoice.on_submit` — CHỈ đẩy việc vào hàng đợi.

    Không bao giờ ném lỗi ra ngoài (quyết định nền tảng #4): lập HĐĐT là hiệu
    ứng phụ, không có quyền chặn việc xuất hoá đơn bán hàng. Cũng không gọi
    Fast tại đây — một lời gọi Fast có thể mất tới 120 giây
    (`fast_client.REQUEST_TIMEOUT_SECONDS`), đặt trong `on_submit` là bắt kế
    toán ngồi chờ và biến sự cố mạng thành lỗi không submit được hoá đơn.

    Bỏ qua hoá đơn trả hàng: `builder._load_delivery_note` từ chối thẳng
    phiếu trả hàng ("dùng hóa đơn điều chỉnh giảm từ hóa đơn gốc"), nên không
    lọc sớm thì mỗi lần lập giấy báo có là một Comment lỗi vô nghĩa.
    """
    if doc.get("is_return"):
        return
    try:
        frappe.enqueue(
            "miyano_portal.hddt_tu_dong.lap_hddt_cho_hoa_don",
            queue="long",
            timeout=600,
            sales_invoice=doc.name,
        )
    except Exception:
        frappe.log_error(title=f"HĐĐT: không đẩy được job lập hoá đơn cho {doc.name}")


def lap_hddt_cho_hoa_don(sales_invoice, client=None) -> dict:
    """Lập chứng từ HĐĐT + lấy bản in thử PDF cho từng phiếu giao của hoá đơn.

    Trả `{"tao": [tên chứng từ], "bo_qua": [{delivery_note, ly_do}],
    "ly_do": str | None}`. `ly_do` chỉ có giá trị khi dừng cho CẢ hoá đơn
    (không có phiếu giao nào, hoặc tích hợp Fast đang tắt).

    `client` để test tiêm `FastClient` giả — đường sản xuất luôn để `None`.
    """
    from erpnext.einvoice.actions import preview_draft
    from erpnext.einvoice.builder import create_from_delivery_note
    from erpnext.einvoice.fast_settings import check_enabled

    ket_qua = {"tao": [], "bo_qua": [], "ly_do": None}

    dn_names = frappe.get_all(
        "Sales Invoice Item",
        filters={"parent": sales_invoice, "delivery_note": ["!=", ""]},
        pluck="delivery_note",
    )
    dn_names = list(dict.fromkeys(dn_names))
    if not dn_names:
        ket_qua["ly_do"] = _("Hoá đơn không qua phiếu giao nào — không lập HĐĐT tự động.")
        _ghi_comment(sales_invoice, ket_qua)
        return ket_qua

    # Kiểm công tắc MỘT lần cho cả hoá đơn: tắt là tắt cho mọi phiếu giao, và
    # đây là cấu hình chứ không phải sự cố nên không `log_error`.
    try:
        check_enabled()
    except Exception as e:
        ket_qua["ly_do"] = str(e)
        _ghi_comment(sales_invoice, ket_qua)
        return ket_qua

    for dn in dn_names:
        # Bọc lỗi TỪNG PHIẾU: một phiếu vướng luật kiểm không được kéo theo
        # các phiếu còn lại của cùng hoá đơn.
        try:
            fei = create_from_delivery_note(dn)
        except Exception as e:
            ket_qua["bo_qua"].append({"delivery_note": dn, "ly_do": str(e)})
            continue

        try:
            preview_draft(fei, client=client)
            ket_qua["tao"].append(fei)
        except Exception as e:
            # Chứng từ ĐÃ tạo được, chỉ chưa có PDF — để nguyên ở `01 - Nháp`
            # cho kế toán sửa dữ liệu rồi bấm lại nút "Xem bản nháp".
            ket_qua["tao"].append(fei)
            ket_qua["bo_qua"].append({
                "delivery_note": dn,
                "ly_do": _("đã tạo {0} nhưng chưa dựng được PDF nháp: {1}").format(fei, e),
            })
            frappe.log_error(title=f"HĐĐT {fei}: không dựng được bản nháp PDF")

    _ghi_comment(sales_invoice, ket_qua)
    return ket_qua


def _ghi_comment(sales_invoice, ket_qua):
    """Một Comment tổng kết trên chính Sales Invoice — đây là nơi DUY NHẤT kế
    toán biết job đã chạy hay chưa và vì sao phiếu nào bị bỏ. Chủ dự án đã
    chốt: giữ Comment, không bắn Notification."""
    dong = []
    if ket_qua["ly_do"]:
        dong.append(ket_qua["ly_do"])
    if ket_qua["tao"]:
        dong.append(_("Đã lập chứng từ HĐĐT: {0}").format(", ".join(ket_qua["tao"])))
    for b in ket_qua["bo_qua"]:
        dong.append(_("Phiếu giao {0}: {1}").format(b["delivery_note"], b["ly_do"]))
    if not dong:
        return
    frappe.get_doc(SI, sales_invoice).add_comment("Comment", "<br>".join(dong))
```

- [ ] **Step 4: Đăng ký hook**

Trong `miyano_portal/hooks.py`, thêm vào `doc_events` (đặt ngay sau khối `"Delivery Note"`):

```python
	# E7b — ký hoá đơn bán hàng thì tự lập chứng từ HĐĐT từ phiếu giao của nó
	# và lấy luôn bản in thử PDF từ Fast, để khách mở cổng là thấy hoá đơn.
	#
	# CHỈ đẩy hàng đợi, không gọi Fast tại đây: một lời gọi Fast có thể mất
	# tới 120 giây. Và hook không bao giờ ném lỗi ra ngoài — lập HĐĐT không
	# có quyền chặn việc xuất hoá đơn bán hàng (cùng nguyên tắc Delivery Note
	# ở trên).
	"Sales Invoice": {
		"on_submit": "miyano_portal.hddt_tu_dong.tu_sales_invoice",
	},
```

- [ ] **Step 5: Chạy test**

```bash
bench --site erptest.local run-tests --app miyano_portal --module miyano_portal.tests.test_e7b_tu_dong
```
Kỳ vọng: OK.

- [ ] **Step 6: Chạy TOÀN BỘ suite — hook mới chạm mọi test có submit Sales Invoice**

```bash
bench --site erptest.local run-tests --app miyano_portal 2>&1 | tail -5
```
Kỳ vọng: OK. Hook giờ chạy trên **mọi** `Sales Invoice.submit()` trong toàn bộ suite (`test_e7_hddt.py` submit rất nhiều SI). `frappe.enqueue` trong test chạy đồng bộ hoặc bị nuốt tuỳ cấu hình — nếu suite chậm hẳn hoặc sinh chứng từ HĐĐT ngoài ý muốn, **đó là phát hiện thật**: cân nhắc thêm chốt `if frappe.flags.in_test: return` vào `tu_sales_invoice` và ghi rõ lý do.

- [ ] **Step 7: Commit**

```bash
git add miyano_portal/hddt_tu_dong.py miyano_portal/hooks.py miyano_portal/tests/test_e7b_tu_dong.py
git commit -m "feat(portal): E7b — submit Sales Invoice thì tự lập HĐĐT + lấy PDF nháp

Hook chỉ đẩy hàng đợi (gọi Fast mất tới 120s, không được chặn submit).
Job dừng ở 02, không bao giờ tự gửi email cho khách.

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

## Task 5: Giao diện — PDF Fast là thứ chính

**Files:**
- Create: `frontend/src/components/HoaDonNhap.vue`
- Modify: `frontend/src/views/Invoices.vue`, `frontend/src/views/OrderDetail.vue`
- Modify: `frontend/src/api.js` (thêm hàm nạp file thành blob URL)

**Interfaces:**
- Consumes: `portal.portal_einvoice_nhap`, `portal.portal_einvoice_nhap_pdf`, `portal.portal_einvoice_download(loai="nhap")`; khoá `nhap_tai_duoc`, `co_hoa_don_nhap`, `canh_bao`
- Produces: component `<HoaDonNhap :url-pdf="..." :du-lieu="..." />`

- [ ] **Step 1: Thêm hàm nạp blob vào `frontend/src/api.js`**

Ngay sau `downloadFile`:

```js
// Nạp một file qua GET rồi trả blob URL để NHÚNG (không tải về máy). Dùng cho
// khối xem hoá đơn nháp: thứ khách cần thấy là chính file PDF của Fast, nên
// nó phải hiện ngay trong trang chứ không phải nằm trong thư mục Downloads.
// Nơi gọi có trách nhiệm URL.revokeObjectURL() khi rời màn hình.
export async function fetchBlobUrl(url) {
  const res = await fetch(url, { headers: { 'X-Frappe-CSRF-Token': csrfToken() } })
  if (!res.ok) {
    let msg = 'Không mở được file.'
    try {
      const data = await res.json()
      const raw = data && (data.exception || data._server_messages || data.message)
      if (typeof raw === 'string') {
        const m = raw.match(/^([\w.]*Error):\s*(.+)$/s)
        msg = m ? m[2] : raw
      }
    } catch {
      // Thân response không phải JSON — giữ thông điệp mặc định.
    }
    throw new Error(msg)
  }
  return URL.createObjectURL(await res.blob())
}
```

Và thêm `fetchBlobUrl` vào `export default { ... }` ở cuối file (giữ đúng khuôn các hàm sẵn có).

- [ ] **Step 2: Viết `frontend/src/components/HoaDonNhap.vue`**

```vue
<script setup>
// Khối "Hoá đơn nháp" dùng chung cho HAI màn hình (Hoá đơn & công nợ, Chi
// tiết đơn hàng). Thứ tự ưu tiên là RÀNG BUỘC nghiệp vụ, không phải sở thích:
// thứ khách phải thấy là CHÍNH FILE PDF DO FAST DỰNG. Bảng dòng hàng do cổng
// tự vẽ chỉ là DỰ PHÒNG cho lúc Fast chưa dựng xong (trạng thái 01) hoặc gọi
// Fast lỗi — không bao giờ là mặc định.
import { ref, onBeforeUnmount, watch } from 'vue'
import api from '../api'
import { fmtVND, fmtDate } from '../format'
import { useIsMobile } from '../useMobile'
import { showToast } from '../toast'

const props = defineProps({
  // URL endpoint tải PDF nháp (đã kèm tham số), hoặc '' nếu chưa có file.
  urlPdf: { type: String, default: '' },
  // Khối dữ liệu dự phòng: { canh_bao, loai, ngay, dong[], tien_hang, ... }
  duLieu: { type: Object, default: null },
})

const isMobile = useIsMobile()
const blobUrl = ref('')
const dangTai = ref(false)

function huyBlob() {
  if (blobUrl.value) {
    URL.revokeObjectURL(blobUrl.value)
    blobUrl.value = ''
  }
}
onBeforeUnmount(huyBlob)

// Trên màn hình hẹp KHÔNG dựng <iframe>: Chrome/Safari trên Android/iOS phần
// lớn không render PDF trong iframe — khung sẽ trắng hoặc tự tải file, và một
// khung trắng trông y hệt "hệ thống hỏng". Ở đó dùng nút mở tab mới.
watch(
  () => props.urlPdf,
  async (url) => {
    huyBlob()
    if (!url || isMobile.value) return
    dangTai.value = true
    try {
      blobUrl.value = await api.fetchBlobUrl(url)
    } catch (e) {
      showToast(e.message || 'Không mở được hoá đơn nháp.', 'error')
    } finally {
      dangTai.value = false
    }
  },
  { immediate: true }
)

async function moTabMoi() {
  try {
    const url = blobUrl.value || (await api.fetchBlobUrl(props.urlPdf))
    blobUrl.value = url
    window.open(url, '_blank', 'noopener')
  } catch (e) {
    showToast(e.message || 'Không mở được hoá đơn nháp.', 'error')
  }
}

async function taiVe() {
  try {
    await api.downloadFile(props.urlPdf, 'hoa-don-nhap.pdf')
  } catch (e) {
    showToast(e.message || 'Không tải được hoá đơn nháp.', 'error')
  }
}
</script>

<template>
  <div>
    <!-- Cảnh báo pháp lý do SERVER trả (einvoice.CANH_BAO_NHAP) — không gõ
         lại ở đây: một lần sửa giao diện làm rơi mất nó là một lần khách
         tưởng mình đang cầm chứng từ thuế. -->
    <div v-if="duLieu && duLieu.canh_bao" class="note">⚠ {{ duLieu.canh_bao }}</div>

    <template v-if="urlPdf">
      <p v-if="dangTai" class="tag">Đang mở hoá đơn nháp…</p>
      <iframe
        v-else-if="blobUrl && !isMobile"
        :src="blobUrl"
        title="Hoá đơn nháp"
        style="width: 100%; height: 70vh; border: 1px solid var(--line); border-radius: 8px"
      ></iframe>
      <button v-else class="btn-o btn-sm" @click="moTabMoi">📄 Mở hoá đơn nháp</button>
      <p style="margin-top: 8px">
        <button class="btn-o btn-sm" @click="taiVe">⬇ Tải hoá đơn nháp</button>
      </p>
    </template>

    <!-- DỰ PHÒNG: chưa có file Fast dựng. -->
    <template v-else-if="duLieu">
      <p class="tag">
        Bản in thử PDF đang được tạo — nội dung hoá đơn nháp xem đầy đủ bên dưới.
      </p>
      <p class="tag">
        {{ duLieu.loai || 'Hoá đơn gốc' }}
        <template v-if="duLieu.ngay"> · Ngày hoá đơn dự kiến: {{ fmtDate(duLieu.ngay) }}</template>
      </p>
      <div style="overflow-x: auto; margin-top: 8px">
        <table>
          <thead>
            <tr>
              <th>#</th><th>Mặt hàng</th><th class="right">SL</th>
              <th class="right">Đơn giá</th><th class="right">Thành tiền</th><th class="right">Thuế</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="dong in duLieu.dong" :key="dong.stt">
              <td>{{ dong.stt }}</td>
              <td>
                <b class="mono">{{ dong.ma }}</b>
                <template v-if="dong.ten"><br /><span style="font-size: 13px">{{ dong.ten }}</span></template>
              </td>
              <td class="right">{{ dong.so_luong }} {{ dong.dvt }}</td>
              <td class="right">{{ fmtVND(dong.don_gia) }}</td>
              <td class="right">{{ fmtVND(dong.thanh_tien) }}</td>
              <td class="right">
                {{ dong.thue_suat ? dong.thue_suat + '%' : '—' }}<br />
                <span class="tag">{{ fmtVND(dong.tien_thue) }}</span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <p style="margin-top: 8px; text-align: right">
        <span class="tag">
          Tiền hàng {{ fmtVND(duLieu.tien_hang) }} · Thuế GTGT {{ fmtVND(duLieu.tien_thue) }}
        </span><br />
        <b>Tổng thanh toán: {{ fmtVND(duLieu.tong_tien) }}</b>
      </p>
    </template>
  </div>
</template>
```

- [ ] **Step 3: Gắn vào `OrderDetail.vue`**

Lấy phần script + template của `git show 7d84b11 -- frontend/src/views/OrderDetail.vue`, nhưng **thay toàn bộ phần vẽ bảng bằng `<HoaDonNhap>`**:

```vue
<HoaDonNhap
  :du-lieu="nhapData[d.name]"
  :url-pdf="nhapData[d.name] && nhapData[d.name].nhap_tai_duoc
    ? '/api/method/miyano_portal.api.portal.portal_einvoice_nhap_pdf?delivery_note=' + encodeURIComponent(d.name)
    : ''"
/>
```

Nhớ `import HoaDonNhap from '../components/HoaDonNhap.vue'` và giữ nguyên hàm `toggleNhap()` (nạp `portal_einvoice_nhap` khi khách bấm xem, không nhúng sẵn dòng hàng của mọi đợt giao vào response chi tiết đơn).

- [ ] **Step 4: Gắn vào `Invoices.vue`**

Trong khối xổ HĐĐT (`einvOpen === inv.name`), thêm ngay trước danh sách `dsHddt(inv)`:

```vue
<HoaDonNhap
  v-if="muc.trang_thai === 'nhap'"
  :du-lieu="{ canh_bao: inv.einvoice.canh_bao }"
  :url-pdf="muc.nhap_tai_duoc
    ? '/api/method/miyano_portal.api.portal.portal_einvoice_download?invoice='
      + encodeURIComponent(inv.name) + '&loai=nhap&fei=' + encodeURIComponent(muc.fei)
    : ''"
/>
```

`block_for` phải trả thêm khoá `canh_bao` ở cấp khối để chỗ này dùng — bổ sung trong `einvoice.block_for`:

```python
    return {"chinh": chinh, "khac": khac, "canh_bao": CANH_BAO_NHAP}
```

- [ ] **Step 5: Build SPA và kiểm bundle**

```bash
cd /home/hoangvietyeuem/frappe-bench-yhct/apps/miyano_portal/frontend
yarn build
cd .. && grep -c "portal_einvoice_nhap_pdf" miyano_portal/public/frontend/index.js
```
Kỳ vọng: build xong, grep ≥ 1.

**Lưu ý:** `bench build --app miyano_portal` KHÔNG chạy vite build cho SPA này (app không có `package.json` ở gốc). Phải chạy `yarn build` trong `frontend/`.

- [ ] **Step 6: Chạy test suite (kiểm `test_index_build_version`)**

```bash
cd /home/hoangvietyeuem/frappe-bench-yhct
bench --site erptest.local run-tests --app miyano_portal 2>&1 | tail -5
```

- [ ] **Step 7: Commit**

```bash
git add frontend/src miyano_portal/public/frontend miyano_portal/einvoice.py
git commit -m "feat(portal): E7b — khối xem hoá đơn nháp, PDF Fast nhúng thẳng trong trang

Component dùng chung cho trang Hoá đơn & công nợ và chi tiết đơn hàng. PDF do
Fast dựng là thứ chính; bảng dòng hàng chỉ dự phòng khi chưa có file. Màn hình
hẹp bỏ iframe (trình duyệt di động không render PDF trong iframe).

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

## Task 6: Tài liệu

**Files:**
- Modify: `docs/Miyano-Portal(Client)_V2/DevHandoff/30_API_Spec.md`
- Modify: `docs/HDDT-ban-giao-team-module.md`

- [ ] **Step 1: Bổ sung hợp đồng API**

Trong `30_API_Spec.md`: thêm khoá `co_hoa_don_nhap` vào §1.2 (`portal_order_track`), thêm mục §2.6 `portal_einvoice_nhap(delivery_note)` và §2.7 `portal_einvoice_nhap_pdf(delivery_note)`, và cập nhật §2.5 để nêu `loai` nay nhận `"pdf" | "nhap"` (không còn `"xml"` — module không lưu XML).

- [ ] **Step 2: Bổ sung tài liệu bàn giao team HĐĐT**

Trong `docs/HDDT-ban-giao-team-module.md`, mục 12 (đã mở sẵn), thêm:

```markdown
**Từ E7b, app cổng gọi THẲNG hai hàm whitelist của module HĐĐT trong
`Sales Invoice.on_submit`** (qua job nền `miyano_portal.hddt_tu_dong`):
`builder.create_from_delivery_note(delivery_note)` và
`actions.preview_draft(fei, client=None)`. Đổi chữ ký hai hàm đó — kể cả đổi
tên tham số `client` — là vỡ luồng tự động này. Tham số `client` đang được
dùng để tiêm FastClient giả trong test của cổng; xin giữ nó.

Cổng KHÔNG gọi `send_draft_to_customer`: việc gửi bản nháp cho khách vẫn do
kế toán bấm tay, đúng thiết kế.
```

- [ ] **Step 3: Commit**

```bash
git add docs
git commit -m "docs: E7b — hợp đồng API hoá đơn nháp + phụ thuộc mới báo team HĐĐT

Co-Authored-By: Claude Opus 5 (1M context) <noreply@anthropic.com>"
```

---

## Kiểm cuối cùng

- [ ] `bench --site erptest.local run-tests --app miyano_portal` → OK
- [ ] Đếm test: trước khi bắt đầu là **836**; kỳ vọng sau Task 6 khoảng **880–890** (Task 1 thêm ~7, Task 2 thêm ~18, Task 3 thêm ~8, Task 4 thêm ~10). Nếu tổng **giảm** so với 836 → có test bị mất, dừng lại tìm nguyên nhân trước khi báo xong.
- [ ] `bench --site erptest.local migrate` → không lỗi
- [ ] Thử tay trên Desk: submit một Sales Invoice có phiếu giao → sau vài giây, `Fast EInvoice Document` mới ở `02 - Đã xem nháp`, có `draft_pdf`, và có Comment trên Sales Invoice
- [ ] Thử tay trên cổng: đăng nhập khách → trang Hoá đơn & công nợ thấy badge "Hoá đơn nháp" + PDF hiện trong trang; chi tiết đơn hàng thấy khối tương ứng ở đợt giao
