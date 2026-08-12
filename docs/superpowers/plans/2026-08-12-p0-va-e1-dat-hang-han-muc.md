# P0 còn lại + Epic E1 (Đặt hàng & hạn mức) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Dựng hai hạ tầng P0 còn thiếu (`Miyano Portal Settings`, ghim over-delivery = 0) rồi bịt bốn lỗ thao tác của luồng đặt hàng theo PRD E1: đơn trùng khi mạng chập chờn, sai bội số quy cách, ngày giao vô lý, và hạn mức khai 0 bị hiểu nhầm thành "hết hạn mức".

**Architecture:** Không đổi kiến trúc ba tầng. `api/portal.py` giữ vai trò cổng duy nhất (phiên + quyền + kiểm tham số); nghiệp vụ thuần tách xuống `portal_context.py` (hạn mức) và một module mới `portal_dat_hang.py` (bội số, ngày giao làm việc) để `portal_order_place` không phình thêm; SPA Vue chỉ báo lỗi sớm, không bao giờ là chốt duy nhất.

**Tech Stack:** Frappe v15.113.4, ERPNext v15.83.0, Python 3.12, MariaDB, Vue 3 + Vite. Test bằng `FrappeTestCase`.

## Global Constraints

- Spec nguồn: [`docs/Miyano-Portal(Client)_V2/DevHandoff/10_PRD_E1_DatHang_HanMuc.md`](../../Miyano-Portal%28Client%29_V2/DevHandoff/10_PRD_E1_DatHang_HanMuc.md). Quy tắc gốc: [`BA-miyano_portal_v2.md`](../../Miyano-Portal%28Client%29_V2/BA-miyano_portal_v2.md) §4.1, §6.1. Giao diện: [`FormSpec-miyano_portal_v2.md`](../../Miyano-Portal%28Client%29_V2/FormSpec-miyano_portal_v2.md) F-03, F-04, F-05. Test: `DevHandoff/40_TestCases.md` nhóm **TC-E1**.
- **Track NG-xx (`BA-v2-ngoai-le-va-UX-miyano_portal.md`) đã bị loại khỏi phạm vi** theo quyết định 2026-08-12. KHÔNG ghi mục vào `CHANGELOG-khac-phuc-BA-v2.md` nữa; tiến độ theo dõi bằng checkbox trong chính file này.
- App: `apps/miyano_portal`. Nhánh mới: `feature/e1-dat-hang-han-muc`, tách từ `feature/ba-v2-dot-1-p0` (đã chứa Task 0 baseline xanh + NG-37d).
- Site test và dev: `erptest.local`. Bench: `/home/hoangvietyeuem/frappe-bench-yhct`.
- **Baseline test hiện tại: 379 phải giữ xanh.** (Tài liệu ghi 339 — đó là ảnh chụp cũ; 339 + 29 test guard + 11 test NG-37d = 379.)
- Đặt tên: DocType tiếng Anh, fieldname tiếng Việt **không dấu**, label tiếng Việt có dấu. Không camelCase cho fieldname.
- Tiền VND hiển thị `1.234.567 ₫` không thập phân; ngày `dd/mm/yyyy`.
- Mọi chốt chặn nghiệp vụ ở **server**. Client chỉ báo lỗi sớm.
- Thông điệp lỗi ra **đúng nguyên văn** ma trận FormSpec §5 (chép trong từng task bên dưới).
- Patch/setup **idempotent**: `bench migrate` chạy hai lần liên tiếp không lỗi, không sinh trùng.
- `frappe.get_doc` **không** chạy hook `has_permission` ở build này — chỗ nào lấy doc theo tên client gửi phải `doc.check_permission("read")` tường minh.
- `frappe.get_all` **luôn** bỏ qua phân quyền; `frappe.get_list` thì không.
- `FrappeTestCase` rollback một lần mỗi **class**. Không save document `DocType` trong test.
- Chạy test một module: `cd /home/hoangvietyeuem/frappe-bench-yhct && bench --site erptest.local run-tests --app miyano_portal --module miyano_portal.tests.<tên>`
- Migrate: `cd /home/hoangvietyeuem/frappe-bench-yhct && bench --site erptest.local migrate`
- Build SPA: `cd apps/miyano_portal/frontend && yarn build`
- Commit sau mỗi task. **Không push.**

## Điểm nối [Hiện có] — KHÔNG code lại

`portal_order_place` (`api/portal.py:191-283`) đã làm đúng: kiểm sở hữu HĐNT và địa chỉ
(BR-O1, dòng 196-204), **gộp dòng trùng mã trước khi kiểm hạn mức** (BR-O2, dòng 216-220),
gom mọi lỗi hạn mức báo một lần (BR-O3, dòng 222-231), kho xuất theo TỪNG mặt hàng
(BR-O4, `_resolve_item_warehouse` dòng 71-94), chặn khi thiếu giá (BR-O5, dòng 259-260),
trừ hạn mức qua `against_blanket_order` (BR-O6, dòng 279), tạo SO nháp + gắn
`contact_email` cho Notification (dòng 249-252). Epic này **mở rộng**, không viết lại.

## Nợ kỹ thuật đã biết, CỐ Ý không xử lý ở đây

Ba lỗi sau nằm đúng trên hai hàm epic này sửa, thuộc track NG-xx đã bị loại khỏi phạm vi.
Ghi ra để người sau không tưởng là epic này bỏ sót:

| Hiện trạng | Chỗ | Hệ quả |
|---|---|---|
| `portal_catalog` trả `vat_pct: 0` cứng (`api/portal.py:182`) | catalog | Cổng báo tổng tiền **thấp hơn** số phải trả |
| `Item Price` đọc không lọc `valid_from`/`valid_upto`, nhiều bản ghi lấy tuỳ ý (`api/portal.py:169-173, 254-258`) | catalog + order_place | Có thể lấy giá đã hết hiệu lực |
| Hạn mức không trừ phần đơn **nháp** đang giữ (`portal_context.remaining_qty`) | order_place | Hai người đặt song song cùng vượt hạn mức |

## File Structure

| File | Trách nhiệm | Task |
|---|---|---|
| `miyano_portal/miyano_portal/doctype/miyano_portal_settings/` | **Tạo.** Single doctype tham số vận hành cổng | 1 |
| `miyano_portal/patches/v1_3/__init__.py` | **Tạo.** | 1 |
| `miyano_portal/patches/v1_3/ghim_over_delivery_zero.py` | **Tạo.** Ghim `over_delivery_receipt_allowance = 0` | 2 |
| `miyano_portal/patches/v1_3/create_e1_custom_fields.py` | **Tạo.** `Sales Order.custom_request_id`, `Item.custom_boi_so_dat` | 4, 6 |
| `miyano_portal/patches.txt` | **Sửa.** Thêm 3 patch | 1, 2, 4 |
| `miyano_portal/portal_context.py` | **Sửa.** `han_muc_con()` phân biệt "không giới hạn" | 3 |
| `miyano_portal/portal_dat_hang.py` | **Tạo.** Bội số quy cách + ngày giao làm việc | 4, 5 |
| `miyano_portal/api/portal.py` | **Sửa.** `portal_catalog`, `portal_order_place`, + `portal_reorder` | 3–8 |
| `miyano_portal/tests/test_e1_han_muc_khong_gioi_han.py` | **Tạo.** | 3 |
| `miyano_portal/tests/test_e1_boi_so_ngay_giao.py` | **Tạo.** | 4, 5 |
| `miyano_portal/tests/test_e1_idempotency.py` | **Tạo.** | 6 |
| `miyano_portal/tests/test_e1_thieu_gia_va_reorder.py` | **Tạo.** | 7, 8 |
| `miyano_portal/tests/test_portal_settings.py` | **Tạo.** | 1, 2 |
| `frontend/src/views/Catalog.vue`, `Cart.vue`, `src/store.js`, `src/api.js` | **Sửa.** | 9 |

## Quyết định phải chốt trong lúc lập kế hoạch (không có trong spec)

**Bội số quy cách của mặt hàng Miyano lưu ở đâu?** PRD E1 §Dữ liệu & API viết *"bội số đặt
của item Miyano lấy từ Item"* nhưng `20_DataDict.md` §4 **không định nghĩa trường nào trên
`Item`** (chỉ có `custom_ban_le_portal` của E6). Đã kiểm CSDL: `tabItem` không có cột nào
tên `%boi_so%`, và `tabCustom Field` chưa có bản ghi nào cho `Item`. Kế hoạch này chốt:
tạo custom field **`Item.custom_boi_so_dat` (Int, default rỗng = không ràng buộc bội số)**,
đặt cùng khuôn tên `custom_*` với bốn custom field `Sales Order` đang có. Nếu BA muốn tên
khác thì đổi trước khi chạy Task 4 — sau đó là đổi schema đã cài.

---

## Task 1: P0 — doctype `Miyano Portal Settings`

**Files:**
- Create: `miyano_portal/miyano_portal/doctype/miyano_portal_settings/__init__.py`
- Create: `miyano_portal/miyano_portal/doctype/miyano_portal_settings/miyano_portal_settings.json`
- Create: `miyano_portal/miyano_portal/doctype/miyano_portal_settings/miyano_portal_settings.py`
- Create: `miyano_portal/patches/v1_3/__init__.py`
- Modify: `miyano_portal/patches.txt`
- Test: `miyano_portal/tests/test_portal_settings.py`

**Interfaces:**
- Produces: Single DocType `Miyano Portal Settings` với 8 trường của `20_DataDict.md` §1.3.
  Task sau đọc bằng `frappe.get_cached_doc("Miyano Portal Settings")` hoặc
  `frappe.db.get_single_value("Miyano Portal Settings", "<fieldname>")`.

**Vì sao làm trước:** `00_INDEX.md` xếp đây là việc chung P0 "trước mọi epic". E2 đọc
`nguong_duyet_2_tang` + `sla_xu_ly_don_gio`; E4 đọc `nguong_cham_luan_chuyen_ngay`; E5 đọc
`so_ngay_adu` + `so_ngay_du_lieu_toi_thieu`; E6 đọc `price_list_ban_le` +
`hieu_luc_bao_gia_ngay` + `sla_yeu_cau_gio`. Dựng một lần, dùng cho cả bốn epic sau.

- [ ] **Step 1: Viết test thất bại**

Tạo `miyano_portal/tests/test_portal_settings.py`:

```python
import frappe
from frappe.tests.utils import FrappeTestCase

TEN = "Miyano Portal Settings"


class TestMiyanoPortalSettings(FrappeTestCase):
    def test_doctype_ton_tai_va_la_single(self):
        self.assertTrue(frappe.db.exists("DocType", TEN))
        self.assertEqual(frappe.get_meta(TEN).issingle, 1)

    def test_du_tam_truong_dung_kieu(self):
        meta = frappe.get_meta(TEN)
        mong_doi = {
            "nguong_duyet_2_tang": "Currency",
            "sla_xu_ly_don_gio": "Int",
            "price_list_ban_le": "Link",
            "hieu_luc_bao_gia_ngay": "Int",
            "sla_yeu_cau_gio": "Int",
            "so_ngay_adu": "Int",
            "so_ngay_du_lieu_toi_thieu": "Int",
            "nguong_cham_luan_chuyen_ngay": "Int",
        }
        for fieldname, fieldtype in mong_doi.items():
            with self.subTest(fieldname=fieldname):
                f = meta.get_field(fieldname)
                self.assertIsNotNone(f, f"thiếu trường {fieldname}")
                self.assertEqual(f.fieldtype, fieldtype)

    def test_gia_tri_mac_dinh_dung_dataDict(self):
        """Mặc định lấy nguyên từ 20_DataDict §1.3. `nguong_duyet_2_tang` CỐ Ý
        để trống = một tầng duyệt (VĐ-8 chưa chốt số)."""
        meta = frappe.get_meta(TEN)
        self.assertIn(meta.get_field("nguong_duyet_2_tang").default, (None, ""))
        for fieldname, mac_dinh in (
            ("sla_xu_ly_don_gio", "8"),
            ("hieu_luc_bao_gia_ngay", "7"),
            ("sla_yeu_cau_gio", "48"),
            ("so_ngay_adu", "90"),
            ("so_ngay_du_lieu_toi_thieu", "30"),
            ("nguong_cham_luan_chuyen_ngay", "90"),
        ):
            with self.subTest(fieldname=fieldname):
                self.assertEqual(meta.get_field(fieldname).default, mac_dinh)

    def test_chi_system_manager_duoc_sua(self):
        """BA §8: Settings chỉ `System Manager` sửa; role `Customer` không có
        DocPerm nào."""
        roles = {p.role for p in frappe.get_meta(TEN).permissions}
        self.assertEqual(roles, {"System Manager"})
```

- [ ] **Step 2: Chạy để thấy FAIL**

Run: `cd /home/hoangvietyeuem/frappe-bench-yhct && bench --site erptest.local run-tests --app miyano_portal --module miyano_portal.tests.test_portal_settings`
Expected: FAIL — `DocType "Miyano Portal Settings" không tồn tại`.

- [ ] **Step 3: Tạo doctype**

`miyano_portal/miyano_portal/doctype/miyano_portal_settings/__init__.py` — file rỗng.

`miyano_portal/miyano_portal/doctype/miyano_portal_settings/miyano_portal_settings.json`:

```json
{
 "actions": [],
 "creation": "2026-08-12 00:00:00.000000",
 "doctype": "DocType",
 "engine": "InnoDB",
 "field_order": [
  "sec_duyet_don", "nguong_duyet_2_tang", "sla_xu_ly_don_gio",
  "sec_mua_le", "price_list_ban_le", "hieu_luc_bao_gia_ngay", "sla_yeu_cau_gio",
  "sec_du_tru", "so_ngay_adu", "so_ngay_du_lieu_toi_thieu", "nguong_cham_luan_chuyen_ngay"
 ],
 "fields": [
  {"fieldname": "sec_duyet_don", "fieldtype": "Section Break", "label": "Duyệt đơn"},
  {"fieldname": "nguong_duyet_2_tang", "fieldtype": "Currency", "label": "Ngưỡng duyệt 2 tầng", "precision": "0",
   "description": "Đơn từ ngưỡng này trở lên bắt buộc Sales Manager duyệt. Để TRỐNG = một tầng duyệt như hiện tại."},
  {"fieldname": "sla_xu_ly_don_gio", "fieldtype": "Int", "label": "SLA xử lý đơn (giờ làm việc)", "default": "8"},
  {"fieldname": "sec_mua_le", "fieldtype": "Section Break", "label": "Mua lẻ & yêu cầu hàng hoá"},
  {"fieldname": "price_list_ban_le", "fieldtype": "Link", "label": "Price List bán lẻ", "options": "Price List"},
  {"fieldname": "hieu_luc_bao_gia_ngay", "fieldtype": "Int", "label": "Hiệu lực báo giá (ngày)", "default": "7"},
  {"fieldname": "sla_yeu_cau_gio", "fieldtype": "Int", "label": "SLA yêu cầu hàng hoá (giờ làm việc)", "default": "48"},
  {"fieldname": "sec_du_tru", "fieldtype": "Section Break", "label": "Dự trù"},
  {"fieldname": "so_ngay_adu", "fieldtype": "Int", "label": "Kỳ tính ADU (ngày)", "default": "90"},
  {"fieldname": "so_ngay_du_lieu_toi_thieu", "fieldtype": "Int", "label": "Số ngày dữ liệu tối thiểu", "default": "30"},
  {"fieldname": "nguong_cham_luan_chuyen_ngay", "fieldtype": "Int", "label": "Ngưỡng chậm luân chuyển (ngày)", "default": "90"}
 ],
 "issingle": 1,
 "links": [],
 "modified": "2026-08-12 00:00:00.000000",
 "modified_by": "Administrator",
 "module": "Miyano Portal",
 "name": "Miyano Portal Settings",
 "owner": "Administrator",
 "permissions": [
  {"create": 1, "email": 1, "print": 1, "read": 1, "role": "System Manager", "share": 1, "write": 1}
 ],
 "sort_field": "modified",
 "sort_order": "DESC",
 "track_changes": 1
}
```

`miyano_portal/miyano_portal/doctype/miyano_portal_settings/miyano_portal_settings.py`:

```python
import frappe
from frappe import _
from frappe.model.document import Document


class MiyanoPortalSettings(Document):
    def validate(self):
        # Số ngày/giờ âm không có nghĩa nghiệp vụ nào và sẽ làm mọi phép so
        # sánh kỳ trượt ở E5 ra kết quả ngược. Chặn tại đây, một chỗ.
        for fieldname, nhan in (
            ("sla_xu_ly_don_gio", "SLA xử lý đơn"),
            ("hieu_luc_bao_gia_ngay", "Hiệu lực báo giá"),
            ("sla_yeu_cau_gio", "SLA yêu cầu hàng hoá"),
            ("so_ngay_adu", "Kỳ tính ADU"),
            ("so_ngay_du_lieu_toi_thieu", "Số ngày dữ liệu tối thiểu"),
            ("nguong_cham_luan_chuyen_ngay", "Ngưỡng chậm luân chuyển"),
        ):
            if (self.get(fieldname) or 0) < 1:
                frappe.throw(_("{0} phải lớn hơn 0.").format(nhan))
```

- [ ] **Step 4: Tạo thư mục patch v1_3**

`miyano_portal/patches/v1_3/__init__.py` — file rỗng.

> **KHÔNG** thêm dòng nào vào `patches.txt` ở task này. `patches.txt` chỉ được nhắc tên
> một module đã tồn tại — ghi trước tên `ghim_over_delivery_zero` (Task 2) thì `migrate`
> ở Step 5 sẽ chết vì `ModuleNotFoundError`. Mỗi task tự đăng ký patch của chính nó.

- [ ] **Step 5: Migrate rồi chạy test**

```bash
cd /home/hoangvietyeuem/frappe-bench-yhct
bench --site erptest.local migrate
bench --site erptest.local run-tests --app miyano_portal --module miyano_portal.tests.test_portal_settings
```
Expected: 4 test PASS.

- [ ] **Step 6: Kiểm idempotent**

Run: `bench --site erptest.local migrate` lần hai. Expected: không lỗi.

- [ ] **Step 7: Commit**

```bash
cd /home/hoangvietyeuem/frappe-bench-yhct/apps/miyano_portal
git add miyano_portal/miyano_portal/doctype/miyano_portal_settings miyano_portal/patches/v1_3 miyano_portal/patches.txt miyano_portal/tests/test_portal_settings.py
git commit -m "feat(portal): doctype Miyano Portal Settings (P0)"
```

---

## Task 2: P0 — ghim `over_delivery_receipt_allowance = 0` (QĐ-2, BR-O10)

**Files:**
- Create: `miyano_portal/patches/v1_3/ghim_over_delivery_zero.py`
- Modify: `miyano_portal/patches.txt` (đăng ký patch — Task 1 cố ý KHÔNG làm việc này)
- Test: `miyano_portal/tests/test_portal_settings.py` (thêm class)

**Interfaces:**
- Consumes: thư mục `patches/v1_3/` từ Task 1.
- Produces: không có API mới. E3 (US-E3.1) dựa vào cấu hình này để ERPNext tự chặn giao vượt.

**Đính chính so với PRD E3.** PRD viết *"Selling Settings over_delivery_receipt_allowance = 0"*.
Trường này thực tế nằm ở **`Stock Settings`**, không phải `Selling Settings` (đã kiểm
`tabSingles`). Ngoài ra `Item` cũng có trường cùng tên ghi đè theo từng mặt hàng.

**Hiện trạng đã kiểm trên `erptest.local`:** `Stock Settings.over_delivery_receipt_allowance`
= `0` và **không** `Item` nào ghi đè khác 0. Tức hành vi mong muốn đang đúng — nhưng chỉ vì
mặc định, chưa ai ghim. Patch này biến "tình cờ đúng" thành "đúng theo thiết kế", và test
biến nó thành thứ không ai lỡ tay đổi mà không biết.

- [ ] **Step 1: Viết test thất bại**

Thêm vào cuối `miyano_portal/tests/test_portal_settings.py`:

```python
class TestOverDeliveryAllowance(FrappeTestCase):
    """QĐ-2 / BR-O10: không cho giao vượt số đặt.

    Kiểm CẤU HÌNH chứ không kiểm hành vi submit Delivery Note — hành vi đó
    thuộc E3 (TC-E3-01) và cần dựng cả SO lẫn DN. Ở đây chỉ chốt rằng tham số
    mà ERPNext dùng để chặn đang ở đúng giá trị, và không mặt hàng nào mở
    ngoại lệ.
    """

    def test_stock_settings_allowance_bang_0(self):
        self.assertEqual(
            frappe.db.get_single_value("Stock Settings", "over_delivery_receipt_allowance") or 0,
            0,
        )

    def test_khong_item_nao_ghi_de_allowance(self):
        ngoai_le = frappe.get_all(
            "Item",
            filters={"over_delivery_receipt_allowance": [">", 0]},
            pluck="name",
            limit=5,
        )
        self.assertEqual(
            ngoai_le, [], f"Các mặt hàng sau mở ngoại lệ giao vượt: {ngoai_le}"
        )
```

- [ ] **Step 2: Chạy test**

Run: `cd /home/hoangvietyeuem/frappe-bench-yhct && bench --site erptest.local run-tests --app miyano_portal --module miyano_portal.tests.test_portal_settings`
Expected: **PASS sẵn** — vì giá trị mặc định đã đúng. Đây là ca hiếm không có bước RED thật;
test ở đây là **chốt hồi quy**, không phải chứng minh bug. Ghi lại điều đó, đừng giả vờ RED.

- [ ] **Step 3: Viết patch ghim giá trị**

`miyano_portal/patches/v1_3/ghim_over_delivery_zero.py`:

```python
import frappe


def execute():
    """Ghim over-delivery allowance = 0 (QĐ-2, BR-O10).

    Trường nằm ở `Stock Settings` (KHÔNG phải `Selling Settings` như PRD E3
    ghi), và `Item` có trường cùng tên ghi đè theo từng mặt hàng.

    Chỉ ghi khi giá trị đang khác 0 — patch chạy lại nhiều lần không sinh
    thay đổi thừa, không đụng `modified` của Single khi không cần.
    """
    hien_tai = frappe.db.get_single_value(
        "Stock Settings", "over_delivery_receipt_allowance"
    )
    if (hien_tai or 0) != 0:
        frappe.db.set_single_value("Stock Settings", "over_delivery_receipt_allowance", 0)

    # Ngoại lệ theo từng mặt hàng làm rỗng nghĩa của cấu hình chung. Không tự
    # ý xoá — chỉ ghi log để người vận hành quyết định, vì một ngoại lệ có thể
    # do nghiệp vụ thật (hàng cân, hàng đong) chứ không phải cấu hình nhầm.
    ngoai_le = frappe.get_all(
        "Item",
        filters={"over_delivery_receipt_allowance": [">", 0]},
        fields=["name", "over_delivery_receipt_allowance"],
    )
    if ngoai_le:
        frappe.log_error(
            title="QĐ-2: mặt hàng mở ngoại lệ giao vượt",
            message=frappe.as_json(ngoai_le),
        )
```

- [ ] **Step 4: Migrate hai lần rồi chạy test**

```bash
cd /home/hoangvietyeuem/frappe-bench-yhct
bench --site erptest.local migrate && bench --site erptest.local migrate
bench --site erptest.local run-tests --app miyano_portal --module miyano_portal.tests.test_portal_settings
```
Expected: migrate lần hai không lỗi (patch đã chạy thì Frappe bỏ qua); 6 test PASS.

- [ ] **Step 5: Commit**

```bash
git add miyano_portal/patches/v1_3/ghim_over_delivery_zero.py miyano_portal/tests/test_portal_settings.py
git commit -m "feat(portal): ghim over-delivery allowance = 0 (QĐ-2, BR-O10)"
```

---

## Task 3: E1 — hạn mức khai 0 = KHÔNG GIỚI HẠN (BR-O15, QĐ-8)

**Files:**
- Modify: `miyano_portal/portal_context.py:82-91` (`remaining_qty`)
- Modify: `miyano_portal/api/portal.py:153-187` (`portal_catalog`), `:222-231` và `:272-280` (`portal_order_place`)
- Test: `miyano_portal/tests/test_e1_han_muc_khong_gioi_han.py`

**Interfaces:**
- Produces: `miyano_portal.portal_context.han_muc_con(blanket_order, item_code) -> tuple[float | None, float]`
  → `(con_lai, da_dat)`. `con_lai is None` nghĩa là **không giới hạn** (dòng HĐNT khai `qty = 0`).
  `remaining_qty()` giữ nguyên chữ ký cũ cho tương thích, cài đặt lại trên `han_muc_con`.
- Consumes: không.

**Lỗi hiện tại, cụ thể.** `remaining_qty` trả `qty - ordered_qty`. Với dòng khai `qty = 0`
và đã đặt 30, nó trả `-30`; `portal_order_place:228` so `qty > rem` nên **mọi** số lượng
đều "vượt hạn mức (còn -30)". `portal_catalog:185` trả `max(total - used, 0.0)` = `0` nên
giao diện hiện "Hết hạn mức". Đúng ngược với QĐ-8.

Hai hệ quả bắt buộc kèm theo (BR-O15, nêu thẳng trong BA §6.1):
1. Dòng SO của mặt hàng không giới hạn **KHÔNG** được gắn `against_blanket_order` — cơ chế
   gốc ERPNext coi `qty = 0` là **cấm đặt** và sẽ chặn lúc submit. Vẫn gắn `custom_hdnt`
   ở đầu đơn để truy vết.
2. Cảnh báo "dùng ≥ 80% hạn mức" và `% hạn mức` ở Dashboard/Hồ sơ **bỏ qua** dòng này
   (không vào mẫu số) — sửa ở `portal_contracts:141-149`.

- [ ] **Step 1: Viết test thất bại**

Tạo `miyano_portal/tests/test_e1_han_muc_khong_gioi_han.py`:

```python
"""BR-O15 / QĐ-8 / NL-1.11 — hạn mức khai 0 nghĩa là KHÔNG GIỚI HẠN.

Bộ số theo `40_TestCases.md` nhóm TC-E1: VT0009 hạn mức 0 (KGH),
VT0002 hạn mức 200 đã đặt 195.
"""

import frappe
from frappe.tests.utils import FrappeTestCase

from miyano_portal.api.portal import portal_catalog, portal_contracts, portal_order_place
from miyano_portal.portal_context import han_muc_con
from miyano_portal.tests.helpers_e1 import (
    USER_KHACH,
    dung_hdnt_e1,
)


class TestHanMucKhongGioiHan(FrappeTestCase):
    def setUp(self):
        self.ctx = dung_hdnt_e1()
        self.addCleanup(frappe.set_user, "Administrator")

    # ---------- tầng nghiệp vụ ----------
    def test_han_muc_con_tra_none_khi_khai_0(self):
        con_lai, da_dat = han_muc_con(self.ctx["hdnt"], self.ctx["vt_kgh"])
        self.assertIsNone(con_lai, "hạn mức khai 0 phải là None = không giới hạn")
        self.assertEqual(da_dat, 0.0)

    def test_han_muc_con_van_tra_so_khi_khai_duong(self):
        con_lai, da_dat = han_muc_con(self.ctx["hdnt"], self.ctx["vt_gioi_han"])
        self.assertEqual(con_lai, 5.0)
        self.assertEqual(da_dat, 195.0)

    # ---------- TC-E1-06: danh mục ----------
    def test_catalog_danh_dau_khong_gioi_han(self):
        frappe.set_user(USER_KHACH)
        rows = {r["item_code"]: r for r in portal_catalog(self.ctx["hdnt"])}
        kgh = rows[self.ctx["vt_kgh"]]
        self.assertTrue(kgh["khong_gioi_han"])
        self.assertIsNone(kgh["remaining"])
        gh = rows[self.ctx["vt_gioi_han"]]
        self.assertFalse(gh["khong_gioi_han"])
        self.assertEqual(gh["remaining"], 5.0)

    # ---------- TC-E1-05: đặt 1.000 vẫn thành công ----------
    def test_dat_1000_don_vi_tren_dong_khong_gioi_han(self):
        frappe.set_user(USER_KHACH)
        kq = portal_order_place(
            contract=self.ctx["hdnt"],
            items=[{"item_code": self.ctx["vt_kgh"], "qty": 1000}],
            request_id=frappe.generate_hash(length=12),
        )
        so = frappe.get_doc("Sales Order", kq["sales_order"])
        dong = so.items[0]
        self.assertEqual(dong.qty, 1000)
        self.assertFalse(
            dong.against_blanket_order,
            "dòng không giới hạn KHÔNG được gắn against_blanket_order — "
            "ERPNext coi qty=0 trên Blanket Order là cấm đặt và sẽ chặn lúc submit",
        )
        self.assertEqual(so.custom_hdnt, self.ctx["hdnt"], "vẫn phải truy vết được HĐNT")

    # ---------- TC-E1-07: dòng có hạn mức vẫn bị chặn như cũ ----------
    def test_dong_co_han_muc_van_bi_chan_khi_vuot(self):
        frappe.set_user(USER_KHACH)
        with self.assertRaises(frappe.ValidationError) as ctx:
            portal_order_place(
                contract=self.ctx["hdnt"],
                items=[{"item_code": self.ctx["vt_gioi_han"], "qty": 10}],
                request_id=frappe.generate_hash(length=12),
            )
        self.assertIn("chỉ còn", str(ctx.exception))
        self.assertIn("5", str(ctx.exception))

    # ---------- TC-E1-08: % hạn mức bỏ qua dòng KGH ----------
    def test_phan_tram_han_muc_bo_qua_dong_khong_gioi_han(self):
        frappe.set_user(USER_KHACH)
        hd = {r["name"]: r for r in portal_contracts()}[self.ctx["hdnt"]]
        # Mẫu số chỉ gồm VT giới hạn (200), đã đặt 195 -> 97.5%.
        # Nếu VT0009 (qty 0) lọt vào mẫu số thì kết quả sẽ khác.
        self.assertEqual(hd["used_pct"], 97.5)
        self.assertEqual(hd["item_count"], 2, "vẫn đếm đủ số mặt hàng của hợp đồng")
```

Tạo `miyano_portal/tests/helpers_e1.py`:

```python
"""Fixture dùng chung cho các test E1.

Dựng riêng một khách + HĐNT của test, KHÔNG mượn dữ liệu thật trên site —
bài học Task 0: một test dựa vào trạng thái CSDL mà thao tác nghiệp vụ bình
thường có thể thay đổi thì sớm muộn cũng đỏ vì lý do không liên quan.
"""

import frappe

KHACH = "_Test Khách E1"
USER_KHACH = "khach-e1@test.miyano"
VT_KGH = "_TEST-E1-KGH"        # hạn mức khai 0 = không giới hạn
VT_GIOI_HAN = "_TEST-E1-GH"    # hạn mức 200, đã đặt 195
BANG_GIA = "_Test Bảng giá E1"


def _tao_item(item_code: str, boi_so: int | None = None) -> str:
    if not frappe.db.exists("Item", item_code):
        doc = frappe.get_doc({
            "doctype": "Item",
            "item_code": item_code,
            "item_name": item_code,
            "item_group": "All Item Groups",
            "stock_uom": "Nos",
            "is_stock_item": 0,
        })
        if boi_so:
            doc.custom_boi_so_dat = boi_so
        doc.insert(ignore_permissions=True)
    elif boi_so is not None:
        frappe.db.set_value("Item", item_code, "custom_boi_so_dat", boi_so)
    return item_code


def dung_hdnt_e1() -> dict:
    """Trả về {khach, hdnt, vt_kgh, vt_gioi_han, bang_gia}."""
    raise NotImplementedError(
        "Điền ở Step 3 của Task 3 — xem hướng dẫn ngay dưới đây trong plan."
    )
```

> `dung_hdnt_e1()` được viết đầy đủ ở **Step 3** bên dưới; để `NotImplementedError` ở
> Step 1 là cố ý, để bước chạy-thấy-đỏ có lý do rõ ràng thay vì `ImportError` mơ hồ.

- [ ] **Step 2: Chạy để thấy FAIL**

Run: `cd /home/hoangvietyeuem/frappe-bench-yhct && bench --site erptest.local run-tests --app miyano_portal --module miyano_portal.tests.test_e1_han_muc_khong_gioi_han`
Expected: FAIL — `ImportError: cannot import name 'han_muc_con'` và `NotImplementedError`.

- [ ] **Step 3: Viết fixture thật**

Thay thân `dung_hdnt_e1()` trong `miyano_portal/tests/helpers_e1.py`:

```python
def dung_hdnt_e1() -> dict:
    """Trả về {khach, hdnt, vt_kgh, vt_gioi_han, bang_gia}."""
    if not frappe.db.exists("Customer", KHACH):
        frappe.get_doc({
            "doctype": "Customer",
            "customer_name": KHACH,
            "customer_type": "Company",
            "customer_group": "All Customer Groups",
            "territory": "All Territories",
        }).insert(ignore_permissions=True)

    if not frappe.db.exists("Price List", BANG_GIA):
        frappe.get_doc({
            "doctype": "Price List",
            "price_list_name": BANG_GIA,
            "selling": 1,
            "currency": "VND",
            "enabled": 1,
        }).insert(ignore_permissions=True)
    frappe.db.set_value("Customer", KHACH, "default_price_list", BANG_GIA)

    _tao_item(VT_KGH)
    _tao_item(VT_GIOI_HAN)
    for item_code, gia in ((VT_KGH, 10000), (VT_GIOI_HAN, 20000)):
        if not frappe.db.exists(
            "Item Price", {"item_code": item_code, "price_list": BANG_GIA}
        ):
            frappe.get_doc({
                "doctype": "Item Price",
                "item_code": item_code,
                "price_list": BANG_GIA,
                "selling": 1,
                "price_list_rate": gia,
            }).insert(ignore_permissions=True)

    if not frappe.db.exists("User", USER_KHACH):
        frappe.get_doc({
            "doctype": "User",
            "email": USER_KHACH,
            "first_name": "Khách E1",
            "user_type": "Website User",
            "send_welcome_email": 0,
        }).insert(ignore_permissions=True)
    u = frappe.get_doc("User", USER_KHACH)
    if not u.get("roles"):
        u.add_roles("Customer")
    if not frappe.db.exists("Contact", {"user": USER_KHACH}):
        c = frappe.get_doc({
            "doctype": "Contact",
            "first_name": "Khách E1",
            "user": USER_KHACH,
        })
        c.append("links", {"link_doctype": "Customer", "link_name": KHACH})
        c.insert(ignore_permissions=True)

    hdnt = frappe.db.get_value("Blanket Order", {"customer": KHACH}, "name")
    if not hdnt:
        bo = frappe.get_doc({
            "doctype": "Blanket Order",
            "blanket_order_type": "Selling",
            "customer": KHACH,
            "company": frappe.defaults.get_user_default("Company")
            or frappe.get_all("Company", pluck="name")[0],
            "from_date": frappe.utils.add_days(frappe.utils.today(), -30),
            "to_date": frappe.utils.add_days(frappe.utils.today(), 300),
        })
        # qty = 0 -> KHÔNG GIỚI HẠN theo QĐ-8. ordered_qty đặt tay để mô phỏng
        # lịch sử đặt hàng mà không phải submit cả một Sales Order thật.
        bo.append("items", {"item_code": VT_KGH, "qty": 0, "rate": 10000})
        bo.append("items", {"item_code": VT_GIOI_HAN, "qty": 200, "rate": 20000})
        bo.insert(ignore_permissions=True)
        bo.submit()
        hdnt = bo.name
    frappe.db.set_value(
        "Blanket Order Item",
        {"parent": hdnt, "item_code": VT_GIOI_HAN},
        "ordered_qty",
        195,
    )
    frappe.db.set_value(
        "Blanket Order Item", {"parent": hdnt, "item_code": VT_KGH}, "ordered_qty", 0
    )
    return {
        "khach": KHACH,
        "hdnt": hdnt,
        "vt_kgh": VT_KGH,
        "vt_gioi_han": VT_GIOI_HAN,
        "bang_gia": BANG_GIA,
    }
```

- [ ] **Step 4: Viết `han_muc_con` trong `portal_context.py`**

Thay `remaining_qty` (dòng 82-91) bằng:

```python
def han_muc_con(blanket_order: str, item_code: str) -> tuple[float | None, float]:
    """Hạn mức còn lại của một mặt hàng trong HĐNT, và số đã đặt luỹ kế.

    Trả `(None, da_dat)` khi dòng hợp đồng khai `qty = 0` — theo QĐ-8/BR-O15
    đó là quy ước **KHÔNG GIỚI HẠN**, không phải "hết hạn mức". Phân biệt hai
    thứ này là toàn bộ lý do hàm trả tuple thay vì một số: bản cũ trả
    `qty - ordered_qty` nên dòng khai 0 đã đặt 30 ra `-30`, và mọi lời gọi
    `qty > rem` đều chặn — đúng ngược ý nghiệp vụ.

    Dòng không tồn tại trong hợp đồng trả `(0.0, 0.0)` = không đặt được, khác
    hẳn với không giới hạn.
    """
    row = frappe.get_all(
        "Blanket Order Item",
        filters={"parent": blanket_order, "item_code": item_code},
        fields=["qty", "ordered_qty"],
        limit=1,
    )
    if not row:
        return 0.0, 0.0
    tong = float(row[0].qty or 0)
    da_dat = float(row[0].ordered_qty or 0)
    if tong == 0:
        return None, da_dat
    return tong - da_dat, da_dat


def remaining_qty(blanket_order: str, item_code: str) -> float:
    """Giữ nguyên chữ ký cũ cho mã và test đã có.

    KHÔNG phân biệt được "không giới hạn" — chỗ nào cần phân biệt thì gọi
    thẳng `han_muc_con`. Giữ lại để không phải sửa `test_portal_context.py`
    trong cùng một thay đổi.
    """
    con_lai, _ = han_muc_con(blanket_order, item_code)
    return float("inf") if con_lai is None else con_lai
```

- [ ] **Step 5: Sửa `portal_catalog`**

Trong `api/portal.py`, thay khối tạo `out.append(...)` (dòng 174-186):

```python
        con_lai, da_dat = han_muc_con(contract, row["item_code"])
        out.append({
            "item_code": row["item_code"],
            "item_name": item.item_name if item else row["item_code"],
            "uom": item.stock_uom if item else "",
            "item_group": (item.item_group if item else "") or "",
            "rate": float(rate),
            "vat_pct": 0,
            "total": float(row["qty"] or 0),
            "used": da_dat,
            # `None` chứ không phải 0: giao diện phải phân biệt "không giới
            # hạn" với "hết hạn mức" (NL-1.2 vs NL-1.11) — hai trạng thái
            # trước đây trông y hệt nhau vì cùng ra 0.
            "remaining": None if con_lai is None else max(con_lai, 0.0),
            "khong_gioi_han": con_lai is None,
            "boi_so_dat": int(
                frappe.db.get_value("Item", row["item_code"], "custom_boi_so_dat") or 0
            ),
        })
```

Thêm import ở đầu file (dòng 2): `from miyano_portal.portal_context import get_portal_customer, han_muc_con, remaining_qty`

> `boi_so_dat` để sẵn ở đây cho Task 4 và Task 9 dùng; trường custom được tạo ở Task 4.
> Chạy Task 3 trước Task 4 thì `frappe.db.get_value` trả `None` → `0` → không ràng buộc.

- [ ] **Step 6: Sửa `portal_order_place`**

Thay vòng kiểm hạn mức (dòng 222-231):

```python
    errors = []
    khong_gioi_han = set()
    for item_code, qty in aggregated.items():
        if qty <= 0:
            errors.append(f"{item_code}: số lượng phải > 0")
            continue
        con_lai, _ = han_muc_con(contract, item_code)
        if con_lai is None:
            khong_gioi_han.add(item_code)
            continue
        if qty > con_lai:
            # Nguyên văn FormSpec §5 / NL-1.3.
            errors.append(
                f"Không đặt được: {item_code} chỉ còn {con_lai:g} theo hạn mức HĐNT."
            )
    if errors:
        frappe.throw("<br>".join(errors), frappe.ValidationError)
```

Thay khối `so.append("items", ...)` (dòng 272-280):

```python
        dong = {
            "item_code": item_code,
            "qty": qty,
            "rate": rate,
            "warehouse": item_warehouse,
            "delivery_date": delivery_date,
        }
        if item_code not in khong_gioi_han:
            dong["blanket_order"] = contract
            dong["against_blanket_order"] = 1
        # Dòng KHÔNG GIỚI HẠN cố ý bỏ hai khoá trên: `against_blanket_order`
        # làm ERPNext đối chiếu với `qty = 0` của Blanket Order Item và chặn
        # ngay lúc submit. Truy vết vẫn còn qua `so.custom_hdnt` ở đầu đơn.
        so.append("items", dong)
```

- [ ] **Step 7: Sửa `portal_contracts` để % bỏ qua dòng KGH**

Thay khối tính `used_pct` (dòng 141-149):

```python
    for r in rows:
        agg = frappe.db.sql(
            """select sum(qty) q, sum(ordered_qty) o
               from `tabBlanket Order Item` where parent=%s and qty > 0""",
            r["name"],
        )[0]
        # `qty > 0` là toàn bộ điểm mấu chốt: dòng khai 0 = không giới hạn nên
        # không có mẫu số, đưa vào sẽ kéo % xuống một cách vô nghĩa (BR-O15).
        total, ordered = float(agg[0] or 0), float(agg[1] or 0)
        r["used_pct"] = round(ordered / total * 100, 1) if total else 0
        # Số mặt hàng vẫn đếm ĐỦ cả dòng không giới hạn — khách vẫn đặt được
        # chúng, chỉ là không có trần.
        r["item_count"] = frappe.db.count("Blanket Order Item", {"parent": r["name"]})
```

- [ ] **Step 8: Chạy test**

Run: `cd /home/hoangvietyeuem/frappe-bench-yhct && bench --site erptest.local run-tests --app miyano_portal --module miyano_portal.tests.test_e1_han_muc_khong_gioi_han`
Expected: 6 test PASS. *(Ca `test_dat_1000_don_vi_tren_dong_khong_gioi_han` cần `request_id`
— tham số đó thêm ở Task 6; tới lúc chạy Task 3 hãy tạm bỏ đối số `request_id` khỏi hai lời
gọi trong test rồi thêm lại ở Task 6, HOẶC chạy Task 6 trước Task 3. Kế hoạch đề nghị làm
Task 6 trước — xem "Thứ tự đề nghị" ở cuối.)*

- [ ] **Step 9: Chạy toàn suite**

Run: `bench --site erptest.local run-tests --app miyano_portal`
Expected: 379 cũ + test mới, tất cả xanh.

- [ ] **Step 10: Commit**

```bash
git add miyano_portal/portal_context.py miyano_portal/api/portal.py miyano_portal/tests/helpers_e1.py miyano_portal/tests/test_e1_han_muc_khong_gioi_han.py
git commit -m "feat(portal): hạn mức khai 0 = không giới hạn (BR-O15, QĐ-8)"
```

---

## Task 4: E1 — bội số quy cách đóng gói (BR-O11)

**Files:**
- Create: `miyano_portal/patches/v1_3/create_e1_custom_fields.py`
- Create: `miyano_portal/portal_dat_hang.py`
- Modify: `miyano_portal/patches.txt`
- Modify: `miyano_portal/api/portal.py` (`portal_order_place`)
- Test: `miyano_portal/tests/test_e1_boi_so_ngay_giao.py`

**Interfaces:**
- Produces:
  - Custom field `Item.custom_boi_so_dat` (Int) — bội số đặt hàng; rỗng/0 = không ràng buộc.
  - Custom field `Sales Order.custom_request_id` (Data, **unique**) — Task 6 dùng.
  - `miyano_portal.portal_dat_hang.kiem_boi_so(item_code, qty) -> str | None` — trả thông
    điệp lỗi nguyên văn FormSpec §5 nếu sai bội số, `None` nếu hợp lệ.
- Consumes: `portal_context.han_muc_con` (Task 3).

**Cả hai custom field cài chung một patch** vì cùng là schema của epic này và cùng phải
idempotent; tách hai patch chỉ tạo thêm một file phải nhớ.

- [ ] **Step 1: Viết test thất bại**

Tạo `miyano_portal/tests/test_e1_boi_so_ngay_giao.py`:

```python
"""BR-O11 (bội số quy cách) và BR-O13 (ngày giao) — TC-E1-03, TC-E1-04."""

import frappe
from frappe.tests.utils import FrappeTestCase

from miyano_portal.api.portal import portal_order_place
from miyano_portal.portal_dat_hang import kiem_boi_so, ngay_giao_mac_dinh
from miyano_portal.tests.helpers_e1 import USER_KHACH, dung_hdnt_e1


class TestBoiSoQuyCach(FrappeTestCase):
    def setUp(self):
        self.ctx = dung_hdnt_e1()
        frappe.db.set_value("Item", self.ctx["vt_kgh"], "custom_boi_so_dat", 10)
        self.addCleanup(frappe.set_user, "Administrator")

    def test_kiem_boi_so_dung_thi_khong_bao_loi(self):
        self.assertIsNone(kiem_boi_so(self.ctx["vt_kgh"], 20))

    def test_kiem_boi_so_sai_bao_dung_nguyen_van_va_goi_y_len(self):
        loi = kiem_boi_so(self.ctx["vt_kgh"], 15)
        self.assertEqual(
            loi, "Số lượng phải là bội số của 10. Gần nhất: 20."
        )

    def test_item_khong_khai_boi_so_thi_khong_rang_buoc(self):
        self.assertIsNone(kiem_boi_so(self.ctx["vt_gioi_han"], 7))

    # TC-E1-03: gửi thẳng API, bỏ qua client
    def test_server_la_chot_cuoi_khi_client_gui_sai_boi_so(self):
        frappe.set_user(USER_KHACH)
        with self.assertRaises(frappe.ValidationError) as ctx:
            portal_order_place(
                contract=self.ctx["hdnt"],
                items=[{"item_code": self.ctx["vt_kgh"], "qty": 15}],
                request_id=frappe.generate_hash(length=12),
            )
        self.assertIn("bội số của 10", str(ctx.exception))
        self.assertIn("Gần nhất: 20", str(ctx.exception))


class TestNgayGiao(FrappeTestCase):
    def setUp(self):
        self.ctx = dung_hdnt_e1()
        self.addCleanup(frappe.set_user, "Administrator")

    def test_mac_dinh_cong_2_ngay_lam_viec_bo_qua_cuoi_tuan(self):
        # Thứ Năm 2026-07-30 -> +2 ngày làm việc = Thứ Hai 2026-08-03
        self.assertEqual(str(ngay_giao_mac_dinh("2026-07-30")), "2026-08-03")
        # Thứ Hai 2026-08-03 -> Thứ Tư 2026-08-05 (không vướng cuối tuần)
        self.assertEqual(str(ngay_giao_mac_dinh("2026-08-03")), "2026-08-05")
        # Thứ Sáu 2026-07-31 -> Thứ Ba 2026-08-04
        self.assertEqual(str(ngay_giao_mac_dinh("2026-07-31")), "2026-08-04")

    # TC-E1-04
    def test_ngay_giao_qua_khu_bi_chan_o_server(self):
        frappe.set_user(USER_KHACH)
        hom_qua = frappe.utils.add_days(frappe.utils.today(), -1)
        with self.assertRaises(frappe.ValidationError) as ctx:
            portal_order_place(
                contract=self.ctx["hdnt"],
                items=[{"item_code": self.ctx["vt_gioi_han"], "qty": 1}],
                delivery_date=hom_qua,
                request_id=frappe.generate_hash(length=12),
            )
        self.assertIn("Ngày giao sớm nhất là", str(ctx.exception))

    def test_ngay_giao_hop_le_thi_di_qua(self):
        frappe.set_user(USER_KHACH)
        tuong_lai = frappe.utils.add_days(frappe.utils.today(), 10)
        kq = portal_order_place(
            contract=self.ctx["hdnt"],
            items=[{"item_code": self.ctx["vt_gioi_han"], "qty": 1}],
            delivery_date=tuong_lai,
            request_id=frappe.generate_hash(length=12),
        )
        self.assertEqual(
            str(frappe.db.get_value("Sales Order", kq["sales_order"], "delivery_date")),
            tuong_lai,
        )
```

- [ ] **Step 2: Chạy để thấy FAIL**

Run: `cd /home/hoangvietyeuem/frappe-bench-yhct && bench --site erptest.local run-tests --app miyano_portal --module miyano_portal.tests.test_e1_boi_so_ngay_giao`
Expected: FAIL — `ModuleNotFoundError: miyano_portal.portal_dat_hang`.

- [ ] **Step 3: Tạo patch custom field**

`miyano_portal/patches/v1_3/create_e1_custom_fields.py`:

```python
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def execute():
    """Custom field của Epic E1.

    `create_custom_fields` idempotent sẵn: gọi lại chỉ cập nhật thuộc tính,
    không sinh bản ghi thứ hai.

    `custom_boi_so_dat` KHÔNG có trong `20_DataDict.md` §4 — PRD E1 chỉ viết
    "bội số đặt của item Miyano lấy từ Item" mà không nêu tên trường. Chốt
    tên ở đây theo đúng khuôn `custom_*` của bốn field Sales Order đang có.
    """
    create_custom_fields(
        {
            "Item": [
                {
                    "fieldname": "custom_boi_so_dat",
                    "label": "Bội số đặt",
                    "fieldtype": "Int",
                    "insert_after": "stock_uom",
                    "description": (
                        "Số lượng đặt trên cổng phải là bội số của số này. "
                        "Để trống hoặc 0 = không ràng buộc."
                    ),
                }
            ],
            "Sales Order": [
                {
                    "fieldname": "custom_request_id",
                    "label": "Mã yêu cầu (chống trùng đơn)",
                    "fieldtype": "Data",
                    "unique": 1,
                    "read_only": 1,
                    "no_copy": 1,
                    "insert_after": "custom_nguon_don",
                    "description": (
                        "Sinh bởi cổng khi mở màn xác nhận. Gửi lại cùng mã "
                        "trả về đúng đơn đã tạo thay vì tạo đơn thứ hai."
                    ),
                }
            ],
        },
        ignore_validate=True,
    )
```

`patches.txt` — thêm dòng dưới dòng của Task 2:

```
miyano_portal.patches.v1_3.create_e1_custom_fields
```

- [ ] **Step 4: Tạo `portal_dat_hang.py`**

```python
"""Quy tắc thao tác của luồng đặt hàng — bội số quy cách và ngày giao.

Tách khỏi `api/portal.py` vì hai lý do: `portal_order_place` đã dài và mỗi
quy tắc mới đều muốn chen vào giữa nó, còn hai hàm dưới đây là nghiệp vụ
thuần, kiểm được mà không cần phiên đăng nhập hay Sales Order nào.
"""

import math

import frappe
from frappe import _
from frappe.utils import add_days, getdate


def kiem_boi_so(item_code: str, qty) -> str | None:
    """BR-O11. Trả thông điệp lỗi nếu sai bội số, `None` nếu hợp lệ.

    Gợi ý luôn LÀM TRÒN LÊN: khách đang muốn ít nhất chừng đó hàng, đề nghị
    một số nhỏ hơn nhu cầu là đề nghị sai thứ họ cần.
    """
    boi_so = int(frappe.db.get_value("Item", item_code, "custom_boi_so_dat") or 0)
    if boi_so <= 0:
        return None
    qty = float(qty or 0)
    if qty % boi_so == 0:
        return None
    goi_y = int(math.ceil(qty / boi_so) * boi_so)
    # Nguyên văn ma trận FormSpec §5, dòng NL-1.6.
    return _("Số lượng phải là bội số của {0}. Gần nhất: {1}.").format(boi_so, goi_y)


def ngay_giao_mac_dinh(tu_ngay=None):
    """BR-O13 — mặc định +2 NGÀY LÀM VIỆC, bỏ qua Thứ Bảy và Chủ Nhật.

    Cố ý KHÔNG trừ ngày lễ: spec chỉ nói bỏ T7/CN, và một bảng ngày lễ chưa
    ai duy trì sẽ sai lệch âm thầm còn tệ hơn không có.
    """
    ngay = getdate(tu_ngay or frappe.utils.today())
    con_lai = 2
    while con_lai > 0:
        ngay = add_days(ngay, 1)
        if getdate(ngay).weekday() < 5:  # 0=T2 … 4=T6
            con_lai -= 1
    return getdate(ngay)


def kiem_ngay_giao(delivery_date) -> str | None:
    """BR-O13 / NL-1.7. Trả thông điệp lỗi nếu ngày giao ở quá khứ."""
    if getdate(delivery_date) < getdate(frappe.utils.today()):
        som_nhat = ngay_giao_mac_dinh()
        # Nguyên văn ma trận FormSpec §5, dòng NL-1.7.
        return _("Ngày giao sớm nhất là {0} (sau 2 ngày làm việc).").format(
            som_nhat.strftime("%d/%m/%Y")
        )
    return None
```

- [ ] **Step 5: Nối vào `portal_order_place`**

Thay dòng 211 (`delivery_date = delivery_date or ...`):

```python
    delivery_date = delivery_date or ngay_giao_mac_dinh()
    loi_ngay = kiem_ngay_giao(delivery_date)
    if loi_ngay:
        frappe.throw(loi_ngay, frappe.ValidationError)
```

Trong vòng gom lỗi (Task 3, Step 6), thêm ngay sau nhánh `qty <= 0`:

```python
        loi_boi_so = kiem_boi_so(item_code, qty)
        if loi_boi_so:
            errors.append(loi_boi_so)
            continue
```

Thêm import: `from miyano_portal.portal_dat_hang import kiem_boi_so, kiem_ngay_giao, ngay_giao_mac_dinh`

- [ ] **Step 6: Migrate rồi chạy test**

```bash
cd /home/hoangvietyeuem/frappe-bench-yhct
bench --site erptest.local migrate
bench --site erptest.local run-tests --app miyano_portal --module miyano_portal.tests.test_e1_boi_so_ngay_giao
```
Expected: 7 test PASS.

- [ ] **Step 7: Commit**

```bash
git add miyano_portal/portal_dat_hang.py miyano_portal/patches/v1_3/create_e1_custom_fields.py miyano_portal/patches.txt miyano_portal/api/portal.py miyano_portal/tests/test_e1_boi_so_ngay_giao.py
git commit -m "feat(portal): bội số quy cách và ngày giao làm việc (BR-O11, BR-O13)"
```

---

## Task 5: (gộp vào Task 4)

Ngày giao (BR-O13) đi chung file, chung test và chung một lời gọi với bội số nên tách
thành task riêng chỉ tạo thêm một vòng review mà không có deliverable độc lập. Giữ số
task cho khớp PRD: **US-E1.2 = Task 4**.

---

## Task 6: E1 — chống tạo đơn trùng (BR-O12, US-E1.1)

**Files:**
- Modify: `miyano_portal/api/portal.py` (`portal_order_place`)
- Test: `miyano_portal/tests/test_e1_idempotency.py`

**Interfaces:**
- Consumes: custom field `Sales Order.custom_request_id` (Task 4).
- Produces: `portal_order_place(..., request_id)` trả thêm khoá `da_ton_tai: bool`
  (`30_API_Spec.md` §1.1).

**Cơ chế.** `custom_request_id` khai `unique: 1` nên **CSDL** là trọng tài, không phải
một phép kiểm trước-khi-ghi. Đó là điểm mấu chốt của TC-E1-02 (hai request song song):
kiểm-rồi-ghi vẫn để lọt hai đơn khi hai tiến trình cùng đọc thấy "chưa có"; bắt
`DuplicateEntryError` rồi trả về đơn đã tồn tại thì không.

- [ ] **Step 1: Viết test thất bại**

Tạo `miyano_portal/tests/test_e1_idempotency.py`:

```python
"""BR-O12 / US-E1.1 / NL-1.8 — TC-E1-01, TC-E1-02."""

import frappe
from frappe.tests.utils import FrappeTestCase

from miyano_portal.api.portal import portal_order_place
from miyano_portal.tests.helpers_e1 import USER_KHACH, dung_hdnt_e1


class TestIdempotencyDatHang(FrappeTestCase):
    def setUp(self):
        self.ctx = dung_hdnt_e1()
        self.addCleanup(frappe.set_user, "Administrator")

    def _dat(self, request_id, qty=1):
        return portal_order_place(
            contract=self.ctx["hdnt"],
            items=[{"item_code": self.ctx["vt_gioi_han"], "qty": qty}],
            request_id=request_id,
        )

    # TC-E1-01
    def test_goi_hai_lan_cung_request_id_chi_tao_mot_don(self):
        rid = frappe.generate_hash(length=12)
        lan1 = self._dat(rid)
        self.assertFalse(lan1["da_ton_tai"])

        lan2 = self._dat(rid)
        self.assertTrue(lan2["da_ton_tai"])
        self.assertEqual(lan2["sales_order"], lan1["sales_order"])

        self.assertEqual(
            frappe.db.count("Sales Order", {"custom_request_id": rid}),
            1,
            "CSDL chỉ được có đúng một đơn cho mỗi mã yêu cầu",
        )

    def test_request_id_khac_nhau_tao_don_khac_nhau(self):
        a = self._dat(frappe.generate_hash(length=12))
        b = self._dat(frappe.generate_hash(length=12))
        self.assertNotEqual(a["sales_order"], b["sales_order"])

    def test_thieu_request_id_bi_tu_choi(self):
        """Bắt buộc, không tuỳ chọn — nếu để tuỳ chọn thì client cũ vẫn tạo
        được đơn trùng và quy tắc thành trang trí."""
        frappe.set_user(USER_KHACH)
        with self.assertRaises(frappe.ValidationError):
            portal_order_place(
                contract=self.ctx["hdnt"],
                items=[{"item_code": self.ctx["vt_gioi_han"], "qty": 1}],
            )

    # TC-E1-02
    def test_hai_request_song_song_chi_mot_don_duoc_tao(self):
        """Mô phỏng đua bằng cách chèn thẳng bản ghi thứ hai mang cùng
        `custom_request_id` — đúng thứ CSDL sẽ gặp khi hai tiến trình cùng
        ghi. Không dùng thread thật: `FrappeTestCase` chạy trong MỘT
        transaction nên hai thread sẽ không thấy nhau, test sẽ xanh giả.
        """
        rid = frappe.generate_hash(length=12)
        lan1 = self._dat(rid)
        with self.assertRaises(frappe.exceptions.DuplicateEntryError):
            frappe.db.sql(
                """insert into `tabSales Order`
                   (name, customer, custom_request_id, docstatus, creation, modified, owner, modified_by)
                   values (%s, %s, %s, 0, now(), now(), 'Administrator', 'Administrator')""",
                (f"{lan1['sales_order']}-DUP", self.ctx["khach"], rid),
            )
```

- [ ] **Step 2: Chạy để thấy FAIL**

Run: `bench --site erptest.local run-tests --app miyano_portal --module miyano_portal.tests.test_e1_idempotency`
Expected: FAIL — `portal_order_place() got an unexpected keyword argument 'request_id'`.

- [ ] **Step 3: Sửa chữ ký và thêm nhánh idempotent**

Đổi dòng 191 của `api/portal.py`:

```python
@frappe.whitelist()
def portal_order_place(
    contract, items, po=None, delivery_date=None, note=None, address=None, request_id=None
) -> dict:
```

Ngay sau `customer = get_portal_customer()` (dòng 192), thêm:

```python
    if not request_id:
        frappe.throw(
            "Thiếu mã yêu cầu đặt hàng. Tải lại trang rồi thử lại.",
            frappe.ValidationError,
        )
    # Trả lại đơn cũ TRƯỚC khi làm bất cứ việc gì khác — người dùng bấm lại
    # vì lần trước có vẻ hỏng, không phải vì muốn đặt thêm.
    da_co = frappe.db.get_value(
        "Sales Order", {"custom_request_id": request_id}, ["name", "customer"], as_dict=True
    )
    if da_co:
        if da_co.customer != customer:
            # Mã yêu cầu của khách khác: không xác nhận sự tồn tại của nó.
            raise frappe.PermissionError("Mã yêu cầu không hợp lệ.")
        return {"sales_order": da_co.name, "da_ton_tai": True,
                "total": float(frappe.db.get_value("Sales Order", da_co.name, "grand_total") or 0)}
```

Gán trường trước khi insert (cạnh `so.custom_hdnt = contract`, dòng 240):

```python
    so.custom_request_id = request_id
```

Bọc `so.insert` (dòng 282):

```python
    try:
        so.insert(ignore_permissions=True)
    except frappe.exceptions.DuplicateEntryError:
        # Đua: tiến trình khác vừa ghi xong cùng mã yêu cầu. CSDL là trọng
        # tài, không phải phép kiểm ở trên — đọc lại và trả về đơn của họ.
        ten = frappe.db.get_value("Sales Order", {"custom_request_id": request_id}, "name")
        return {"sales_order": ten, "da_ton_tai": True,
                "total": float(frappe.db.get_value("Sales Order", ten, "grand_total") or 0)}
    return {"sales_order": so.name, "da_ton_tai": False, "total": float(so.grand_total)}
```

- [ ] **Step 4: Chạy test**

Run: `bench --site erptest.local run-tests --app miyano_portal --module miyano_portal.tests.test_e1_idempotency`
Expected: 4 test PASS.

- [ ] **Step 5: Sửa test cũ đang gọi `portal_order_place` không có `request_id`**

Run: `grep -rn "portal_order_place" miyano_portal/tests/ | grep -v test_e1_`
Với mỗi lời gọi, thêm `request_id=frappe.generate_hash(length=12)`. Chạy lại toàn suite.

- [ ] **Step 6: Commit**

```bash
git add miyano_portal/api/portal.py miyano_portal/tests/
git commit -m "feat(portal): chống tạo đơn trùng theo request_id (BR-O12)"
```

---

## Task 7: E1 — thiếu giá thì báo sales (US-E1.4, NL-1.4)

**Files:**
- Modify: `miyano_portal/api/portal.py` (`portal_order_place`, `portal_catalog`)
- Create: `miyano_portal/portal_thong_bao.py`
- Test: `miyano_portal/tests/test_e1_thieu_gia_va_reorder.py`

**Interfaces:**
- Produces: `miyano_portal.portal_thong_bao.bao_thieu_gia(customer, item_code) -> bool`
  — trả `True` nếu vừa gửi, `False` nếu đã gửi trong ngày (chống spam, tối đa 1 lần/
  (khách, mặt hàng)/ngày theo `30_API_Spec.md` §4).

- [ ] **Step 1: Viết test thất bại**

Tạo `miyano_portal/tests/test_e1_thieu_gia_va_reorder.py`:

```python
"""US-E1.4 (thiếu giá → báo sales) và US-E1.5 (đặt lại đơn cũ) — TC-E1-09, TC-E1-10."""

import frappe
from frappe.tests.utils import FrappeTestCase

from miyano_portal.api.portal import portal_order_place, portal_reorder
from miyano_portal.portal_thong_bao import bao_thieu_gia
from miyano_portal.tests.helpers_e1 import USER_KHACH, dung_hdnt_e1


class TestThieuGia(FrappeTestCase):
    def setUp(self):
        self.ctx = dung_hdnt_e1()
        self.vt_khong_gia = "_TEST-E1-KHONG-GIA"
        if not frappe.db.exists("Item", self.vt_khong_gia):
            frappe.get_doc({
                "doctype": "Item", "item_code": self.vt_khong_gia,
                "item_name": self.vt_khong_gia, "item_group": "All Item Groups",
                "stock_uom": "Nos", "is_stock_item": 0,
            }).insert(ignore_permissions=True)
        bo = frappe.get_doc("Blanket Order", self.ctx["hdnt"])
        if not any(r.item_code == self.vt_khong_gia for r in bo.items):
            frappe.get_doc({
                "doctype": "Blanket Order Item", "parent": self.ctx["hdnt"],
                "parenttype": "Blanket Order", "parentfield": "items",
                "item_code": self.vt_khong_gia, "qty": 100, "rate": 0,
            }).insert(ignore_permissions=True)
        self.addCleanup(frappe.set_user, "Administrator")

    # TC-E1-09
    def test_dat_hang_thieu_gia_bi_chan_va_bao_sales(self):
        frappe.set_user(USER_KHACH)
        with self.assertRaises(frappe.ValidationError) as ctx:
            portal_order_place(
                contract=self.ctx["hdnt"],
                items=[{"item_code": self.vt_khong_gia, "qty": 1}],
                request_id=frappe.generate_hash(length=12),
            )
        self.assertIn(self.vt_khong_gia, str(ctx.exception))
        self.assertIn("chưa có giá", str(ctx.exception))

    def test_chi_bao_mot_lan_moi_ngay_cho_moi_cap_khach_mat_hang(self):
        frappe.set_user("Administrator")
        self.assertTrue(bao_thieu_gia(self.ctx["khach"], self.vt_khong_gia))
        self.assertFalse(
            bao_thieu_gia(self.ctx["khach"], self.vt_khong_gia),
            "lần thứ hai trong ngày không được gửi lại",
        )


class TestReorder(FrappeTestCase):
    def setUp(self):
        self.ctx = dung_hdnt_e1()
        self.addCleanup(frappe.set_user, "Administrator")

    # TC-E1-10
    def test_reorder_dien_lai_gio_va_liet_ke_dong_bi_loai(self):
        frappe.set_user(USER_KHACH)
        don = portal_order_place(
            contract=self.ctx["hdnt"],
            items=[
                {"item_code": self.ctx["vt_gioi_han"], "qty": 2},
                {"item_code": self.ctx["vt_kgh"], "qty": 10},
            ],
            request_id=frappe.generate_hash(length=12),
        )["sales_order"]

        # Vắt cạn hạn mức của mặt hàng có giới hạn: 200 tổng, đặt 200.
        frappe.db.set_value(
            "Blanket Order Item",
            {"parent": self.ctx["hdnt"], "item_code": self.ctx["vt_gioi_han"]},
            "ordered_qty", 200,
        )

        kq = portal_reorder(don)
        con_dat_duoc = {d["item_code"] for d in kq["gio_hang"]}
        bi_loai = {d["item_code"]: d["ly_do"] for d in kq["bi_loai"]}

        self.assertEqual(con_dat_duoc, {self.ctx["vt_kgh"]})
        self.assertEqual(bi_loai, {self.ctx["vt_gioi_han"]: "het_han_muc"})
        self.assertEqual(
            kq["gio_hang"][0]["gia_hien_hanh"], 10000.0,
            "giá phải là giá HIỆN HÀNH, không phải giá đã lưu trên đơn cũ",
        )

    def test_reorder_don_cua_khach_khac_bi_tu_choi(self):
        don_khac = frappe.get_all(
            "Sales Order",
            filters={"customer": ["!=", self.ctx["khach"]]},
            pluck="name", limit=1,
        )
        if not don_khac:
            self.skipTest("Site không có đơn của khách khác để thử cách ly.")
        frappe.set_user(USER_KHACH)
        with self.assertRaises(frappe.PermissionError):
            portal_reorder(don_khac[0])
```

- [ ] **Step 2: Chạy để thấy FAIL**

Expected: FAIL — `cannot import name 'portal_reorder'` / `portal_thong_bao`.

- [ ] **Step 3: Tạo `portal_thong_bao.py`**

```python
"""Thông báo từ cổng sang nhân viên Miyano.

Chống spam bằng `Notification Log` đã có sẵn của Frappe thay vì dựng bảng
riêng: một khách mở danh mục mười lần trong ngày không được biến thành mười
thông báo cho cùng một nhân viên.
"""

import frappe
from frappe.utils import today

LOAI = "Portal - Thiếu giá"


def _sales_phu_trach(customer: str) -> str | None:
    """Nhân viên kinh doanh của khách; rỗng thì không gửi cho ai cả."""
    return frappe.db.get_value("Customer", customer, "account_manager")


def bao_thieu_gia(customer: str, item_code: str) -> bool:
    """NL-1.4. Trả `True` nếu vừa gửi, `False` nếu hôm nay đã gửi rồi."""
    nguoi_nhan = _sales_phu_trach(customer)
    if not nguoi_nhan:
        return False

    chu_de = f"{LOAI}: {item_code} ({customer})"
    da_gui = frappe.db.exists(
        "Notification Log",
        {
            "subject": chu_de,
            "for_user": nguoi_nhan,
            "creation": [">=", f"{today()} 00:00:00"],
        },
    )
    if da_gui:
        return False

    frappe.get_doc({
        "doctype": "Notification Log",
        "subject": chu_de,
        "for_user": nguoi_nhan,
        "type": "Alert",
        "email_content": (
            f"Khách hàng <b>{customer}</b> không đặt được mặt hàng "
            f"<b>{item_code}</b> vì chưa có giá trong bảng giá của họ. "
            f"Bổ sung Item Price để khách đặt được."
        ),
    }).insert(ignore_permissions=True)
    return True
```

- [ ] **Step 4: Nối vào `portal_order_place` và `portal_catalog`**

Thay khối `if not rate:` (dòng 259-260):

```python
        if not rate:
            bao_thieu_gia(customer, item_code)
            # Nguyên văn ma trận FormSpec §5, dòng NL-1.4.
            frappe.throw(
                f"{item_code} chưa có giá trong hợp đồng. "
                f"Miyano đã nhận được thông báo để bổ sung.",
                frappe.ValidationError,
            )
```

Thêm import: `from miyano_portal.portal_thong_bao import bao_thieu_gia`

- [ ] **Step 5: Viết `portal_reorder`** (US-E1.5, UC-14, `30_API_Spec.md` §2.1)

Thêm vào cuối `api/portal.py`:

```python
@frappe.whitelist()
def portal_reorder(order: str) -> dict:
    """UC-14 — điền lại giỏ theo một đơn cũ, GIÁ HIỆN HÀNH.

    Dòng nào không còn đặt được thì vào `bi_loai` kèm mã lý do để giao diện
    dịch sang thông điệp FormSpec §5 — im lặng bỏ bớt dòng là cách chắc chắn
    khiến khách đặt thiếu hàng mà không biết.
    """
    customer = get_portal_customer()
    so = frappe.get_doc("Sales Order", order)
    # frappe.get_doc KHÔNG chạy hook has_permission ở build này.
    so.check_permission("read")
    if so.customer != customer:
        raise frappe.PermissionError("Đơn hàng không thuộc đơn vị của bạn.")

    contract = so.custom_hdnt
    price_list = frappe.db.get_value("Customer", customer, "default_price_list")
    gio_hang, bi_loai = [], []

    for dong in so.items:
        if not contract:
            bi_loai.append({"item_code": dong.item_code, "ly_do": "ngoai_hdnt"})
            continue
        con_lai, _ = han_muc_con(contract, dong.item_code)
        if con_lai == 0.0:
            bi_loai.append({"item_code": dong.item_code, "ly_do": "het_han_muc"})
            continue
        gia = frappe.db.get_value(
            "Item Price",
            {"item_code": dong.item_code, "price_list": price_list, "selling": 1},
            "price_list_rate",
        )
        if not gia:
            bi_loai.append({"item_code": dong.item_code, "ly_do": "thieu_gia"})
            continue
        qty = float(dong.qty)
        if con_lai is not None:
            qty = min(qty, con_lai)
        gio_hang.append({
            "item_code": dong.item_code,
            "qty": qty,
            "gia_hien_hanh": float(gia),
        })

    return {"gio_hang": gio_hang, "bi_loai": bi_loai}
```

- [ ] **Step 6: Chạy test rồi toàn suite**

```bash
bench --site erptest.local run-tests --app miyano_portal --module miyano_portal.tests.test_e1_thieu_gia_va_reorder
bench --site erptest.local run-tests --app miyano_portal
```

- [ ] **Step 7: Commit**

```bash
git add miyano_portal/portal_thong_bao.py miyano_portal/api/portal.py miyano_portal/tests/test_e1_thieu_gia_va_reorder.py
git commit -m "feat(portal): báo sales khi thiếu giá + đặt lại đơn cũ (US-E1.4, UC-14)"
```

---

## Task 8: E1 — giao diện (FormSpec F-03, F-04, F-05)

**Files:**
- Modify: `frontend/src/views/Catalog.vue` — badge "Không giới hạn", bước nhảy bội số
- Modify: `frontend/src/views/Cart.vue` — `request_id`, ngày giao mặc định, nút khoá khi gửi
- Modify: `frontend/src/store.js` — giữ `request_id` theo phiên mở modal
- Modify: `frontend/src/views/OrderDetail.vue` — nút "Đặt lại đơn này"

**Interfaces:**
- Consumes: `portal_catalog` trả thêm `khong_gioi_han`, `boi_so_dat`, `remaining: null`
  (Task 3); `portal_order_place(request_id=...)` trả `da_ton_tai` (Task 6); `portal_reorder`
  (Task 7).

- [ ] **Step 1: Catalog — phân biệt "Không giới hạn" với "Hết hạn mức"**

Trong `Catalog.vue`, cột hạn mức:

```vue
<template v-if="row.khong_gioi_han">
  <span class="badge badge-info">Không giới hạn</span>
  <div class="text-muted small">đã đặt {{ fmtSo(row.used) }} {{ row.uom }}</div>
</template>
<template v-else-if="row.remaining <= 0">
  <span class="badge badge-danger">Hết hạn mức</span>
</template>
<template v-else>
  <div>{{ fmtSo(row.remaining) }} / {{ fmtSo(row.total) }} {{ row.uom }}</div>
  <progress :value="row.used" :max="row.total"
            :class="{ 'bar-canh-bao': row.used / row.total >= 0.8 }" />
</template>
```

Ô số lượng: `:max` chỉ đặt khi **không** phải dòng không giới hạn; `:step` =
`row.boi_so_dat || 1`.

- [ ] **Step 2: Cart — `request_id` sinh khi mở modal xác nhận**

Trong `store.js`, thêm state `requestId` và action:

```js
moModalXacNhan() {
  // Sinh MỘT lần khi mở modal, KHÔNG sinh lại mỗi lần bấm — đó chính là cơ
  // chế chống tạo đơn trùng (BR-O12): bấm lại phải gửi CÙNG mã.
  if (!this.requestId) this.requestId = crypto.randomUUID()
},
dongModalXacNhan(daTaoDon) {
  if (daTaoDon) this.requestId = null
},
```

Trong `Cart.vue`, sửa lời gọi (dòng 46):

```js
const res = await api.call('portal_order_place', {
  contract: store.contract,
  items: store.items,
  po: store.po,
  delivery_date: store.deliveryDate,
  note: store.note,
  address: store.address,
  request_id: store.requestId,
})
if (res.da_ton_tai) {
  toast.info(`Đơn ${res.sales_order} đã được tạo trước đó.`)
}
```

Nút xác nhận: `:disabled="dangGui"`, đặt `dangGui = true` trước khi gọi và chỉ đặt lại
`false` trong `finally`.

- [ ] **Step 3: Cart — ngày giao mặc định +2 ngày làm việc**

```js
function ngayGiaoMacDinh() {
  const d = new Date()
  let conLai = 2
  while (conLai > 0) {
    d.setDate(d.getDate() + 1)
    const thu = d.getDay()          // 0=CN, 6=T7
    if (thu !== 0 && thu !== 6) conLai -= 1
  }
  return d.toISOString().slice(0, 10)
}
```

Đặt `min` của date picker = hôm nay. Server vẫn là chốt cuối (Task 4).

- [ ] **Step 4: OrderDetail — nút "Đặt lại đơn này"**

```js
async function datLai() {
  const res = await api.call('portal_reorder', { order: props.name })
  store.napGio(res.gio_hang)
  if (res.bi_loai.length) {
    toast.warning(
      'Không đưa vào giỏ được: ' +
      res.bi_loai.map(d => `${d.item_code} (${LY_DO[d.ly_do]})`).join(', ')
    )
  }
  router.push('/cart')
}
const LY_DO = {
  het_han_muc: 'hết hạn mức',
  ngoai_hdnt: 'ngoài hợp đồng',
  thieu_gia: 'chưa có giá',
}
```

- [ ] **Step 5: Build và kiểm bằng mắt**

```bash
cd /home/hoangvietyeuem/frappe-bench-yhct/apps/miyano_portal/frontend && yarn build
cd /home/hoangvietyeuem/frappe-bench-yhct && bench --site erptest.local clear-cache
```
Mở `http://192.168.61.129:8003/portal`, đăng nhập tài khoản demo, kiểm bốn thứ: badge
"Không giới hạn" trên mặt hàng khai 0; stepper nhảy đúng bội số; ngày giao mặc định là
ngày làm việc; bấm đúp nút xác nhận chỉ ra một đơn.

- [ ] **Step 6: Commit**

```bash
git add frontend/src
git commit -m "feat(portal): giao diện E1 — không giới hạn, bội số, ngày giao, chống bấm đúp"
```

---

## Thứ tự đề nghị

```
Task 1 (Settings)        ─── độc lập
Task 2 (over-delivery)   ─── cần thư mục patch của Task 1
Task 4 (custom fields + bội số + ngày giao)   ← tạo custom_request_id
   └─ Task 6 (idempotency)                     ← dùng custom_request_id
        └─ Task 3 (hạn mức 0)                  ← test gọi có request_id
             └─ Task 7 (thiếu giá + reorder)   ← reorder dùng han_muc_con
                  └─ Task 8 (giao diện)        ← dùng cả ba API trên
```

**Lưu ý ràng buộc thứ tự:** Task 3 đứng sau Task 6 trong sơ đồ trên (dù số nhỏ hơn) vì test
của nó gọi `portal_order_place(request_id=...)`. Nếu muốn giữ đúng thứ tự số, bỏ đối số
`request_id` khỏi test Task 3 rồi thêm lại ở Task 6 — tốn thêm một lần sửa test.

**Ranh giới triển khai.** Task 6 làm `request_id` thành **bắt buộc** trên
`portal_order_place`, còn Task 8 mới dạy giao diện gửi nó. Giữa hai commit đó **không khách
nào đặt hàng được**. Chỉ `migrate` + build + restart trên site thật khi cả Task 6 và Task 8
đã xong. Task 1, 2 lên site riêng được.

## Định nghĩa hoàn thành cho cả gói

- Toàn bộ AC của US-E1.1…E1.5 có test tự động và pass.
- Nhóm TC-E1 (TC-E1-01…10) của `40_TestCases.md` phủ hết; riêng TC-E1-02 mô phỏng đua bằng
  chèn thẳng CSDL, có ghi rõ lý do không dùng thread.
- 379 test cũ giữ xanh.
- `bench migrate` chạy hai lần liên tiếp: sạch.
- Thông điệp lỗi đúng **nguyên văn** ma trận FormSpec §5 (NL-1.2, 1.3, 1.4, 1.6, 1.7).
- Không thêm DocPerm nào cho role `Customer`; không endpoint nào nhận `customer` từ client.
