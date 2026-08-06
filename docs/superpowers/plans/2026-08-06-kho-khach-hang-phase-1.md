# Kho Khách Hàng — Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Dựng sổ kho riêng của khách hàng trong `miyano_portal` — sáu doctype, engine ghi sổ theo lô, tồn theo lô, mở kho, và cách ly dữ liệu giữa các khách.

**Architecture:** Sổ kho hoàn toàn độc lập với hệ thống kho của ERPNext (không dùng `Warehouse`, `Bin`, `Stock Entry`, `Stock Ledger Entry`) và không thuộc Company nào, vì `enable_perpetual_inventory = 1` trên cả hai company của Miyano. `Customer Stock Ledger Entry` là sổ ghi tăng dần và là nguồn sự thật duy nhất; `Customer Stock Lot Balance` là cache dẫn xuất, tái dựng được. Phiếu nhập/xuất là doctype submittable, `on_submit` ghi sổ, `on_cancel` sinh phiếu đảo với số lượng ngược dấu.

**Tech Stack:** Frappe v15.113.4, ERPNext v15.83.0, Python 3.12, MariaDB. Test bằng `FrappeTestCase`.

## Global Constraints

- Spec nguồn: `docs/superpowers/specs/2026-08-06-kho-khach-hang-design.md`. Mọi quyết định trong đó là ràng buộc.
- App: `apps/miyano_portal`, branch `develop`. Module Frappe: `Miyano Portal`.
- Site test và dev: `erptest.local`. Bench: `/home/hoangvietyeuem/frappe-bench-yhct`.
- **Không** dùng `Warehouse`, `Bin`, `Stock Entry`, `Stock Ledger Entry` của ERPNext. **Không** tạo Company. **Không** sinh bút toán kế toán.
- **Không** tạo `Item` cho mã vật tư khách tự thêm.
- Mỗi Customer đúng một `Customer Warehouse` (unique).
- Mọi vật tư đều theo dõi lô + HSD. Vật tư không có lô thực thì `so_lo = "KHONG-LO"` và `han_su_dung` để trống.
- **Tên doctype bằng tiếng Anh**, fieldname tiếng Việt không dấu, label tiếng Việt. Lý do: Frappe sinh tên thư mục và module Python bằng `frappe.scrub(doctype_name)`, tên có dấu tạo thư mục và module Python chứa ký tự Unicode — dễ vỡ với git và chuẩn hoá NFC/NFD. Bảng ánh xạ:

  | Spec (tiếng Việt) | Doctype (thực thi) |
  |---|---|
  | Kho Khách Hàng | `Customer Warehouse` |
  | Vật Tư Kho Khách | `Customer Warehouse Item` |
  | Phiếu Nhập Kho | `Customer Stock Receipt` (+ `Customer Stock Receipt Item`) |
  | Phiếu Xuất Kho | `Customer Stock Issue` (+ `Customer Stock Issue Item`) |
  | Sổ Kho Khách | `Customer Stock Ledger Entry` |
  | Tồn Theo Lô | `Customer Stock Lot Balance` |

- Mọi thông báo lỗi ra **tiếng Việt**, không lộ tên doctype tiếng Anh, không lộ traceback.
- `frappe.get_doc` **không** tự chạy hook `has_permission` ở build này. Mọi chỗ lấy doc theo tên do client gửi **phải** gọi `doc.check_permission("read")` tường minh. Xem `miyano_portal/api/portal.py:351` và `:490`.
- Chạy test: `cd /home/hoangvietyeuem/frappe-bench-yhct && bench --site erptest.local run-tests --app miyano_portal --module miyano_portal.tests.<tên module>`
- Áp dụng migrate sau khi thêm/sửa doctype JSON: `cd /home/hoangvietyeuem/frappe-bench-yhct && bench --site erptest.local migrate`
- Commit sau mỗi task. Không push.

**Phạm vi:** Plan này **chỉ** phủ Phase 1 trong bảng §11 của spec. Import tồn đầu kỳ (P2), FEFO + in phiếu (P3), hook Delivery Note (P4), báo cáo N-X-T (P5), màn hình desk Miyano (P6) mỗi phase có plan riêng.

## File Structure

**Tạo mới**

| File | Trách nhiệm |
|---|---|
| `miyano_portal/miyano_portal/doctype/customer_warehouse/` | Doctype kho, 1–1 với Customer |
| `miyano_portal/miyano_portal/doctype/customer_warehouse_item/` | Danh mục vật tư trong kho |
| `miyano_portal/miyano_portal/doctype/customer_stock_ledger_entry/` | Sổ ghi tăng dần |
| `miyano_portal/miyano_portal/doctype/customer_stock_lot_balance/` | Cache tồn theo lô |
| `miyano_portal/miyano_portal/doctype/customer_stock_receipt/` | Phiếu nhập |
| `miyano_portal/miyano_portal/doctype/customer_stock_receipt_item/` | Dòng phiếu nhập |
| `miyano_portal/miyano_portal/doctype/customer_stock_issue/` | Phiếu xuất |
| `miyano_portal/miyano_portal/doctype/customer_stock_issue_item/` | Dòng phiếu xuất |
| `miyano_portal/kho/__init__.py` | package |
| `miyano_portal/kho/ledger.py` | Engine ghi sổ, cập nhật tồn theo lô, rebuild |
| `miyano_portal/kho/voucher.py` | Logic dùng chung của phiếu nhập và phiếu xuất (autoname, đảo phiếu) |
| `miyano_portal/kho/permissions.py` | Query condition + has_permission cho sáu doctype |
| `miyano_portal/api/kho.py` | Endpoint portal |
| `miyano_portal/tests/test_kho_ledger.py` | Test engine sổ kho |
| `miyano_portal/tests/test_kho_receipt.py` | Test phiếu nhập |
| `miyano_portal/tests/test_kho_issue.py` | Test phiếu xuất |
| `miyano_portal/tests/test_kho_isolation.py` | Test cách ly |
| `miyano_portal/tests/test_kho_api.py` | Test endpoint portal |
| `miyano_portal/setup/seed_kho_demo.py` | Dựng dữ liệu kho cho test và demo |

**Sửa**

| File | Thay đổi |
|---|---|
| `miyano_portal/hooks.py:131-143` | Thêm sáu doctype vào `permission_query_conditions` và `has_permission` |
| `miyano_portal/portal_context.py` | Thêm `get_portal_kho()` |

---

### Task 1: Doctype `Customer Warehouse` và mở kho

**Files:**
- Create: `miyano_portal/miyano_portal/doctype/customer_warehouse/__init__.py`
- Create: `miyano_portal/miyano_portal/doctype/customer_warehouse/customer_warehouse.json`
- Create: `miyano_portal/miyano_portal/doctype/customer_warehouse/customer_warehouse.py`
- Create: `miyano_portal/setup/seed_kho_demo.py`
- Test: `miyano_portal/tests/test_kho_ledger.py`

**Interfaces:**
- Consumes: `miyano_portal.portal_context.get_allowed_customers` (đã có).
- Produces:
  - Doctype `Customer Warehouse`, autoname `KKH-.#####`, fields: `customer` (Link Customer, reqd, unique), `ten_kho` (Data, reqd), `ma_kho` (Data, reqd, unique), `thu_kho` (Data), `dia_chi_kho` (Small Text), `ten_don_vi_in` (Data), `bo_phan_in` (Data), `mau_phieu_nhap` (Link Print Format), `mau_phieu_xuat` (Link Print Format), `ngay_bat_dau` (Date, reqd), `active` (Check, default 1).
  - `miyano_portal.setup.seed_kho_demo.seed_kho_demo() -> dict` trả về `{"kho_bm": str, "kho_pxn": str}` — tên hai `Customer Warehouse` cho `Bệnh viện Bạch Mai` và `PXN ABC`. Idempotent.

- [ ] **Step 1: Viết test thất bại**

Tạo `miyano_portal/tests/test_kho_ledger.py`:

```python
import frappe
from frappe.tests.utils import FrappeTestCase
from miyano_portal.setup.seed_kho_demo import seed_kho_demo


class TestKhoWarehouse(FrappeTestCase):
    def setUp(self):
        self.kho = seed_kho_demo()

    def test_seed_creates_one_warehouse_per_customer(self):
        self.assertTrue(frappe.db.exists("Customer Warehouse", self.kho["kho_bm"]))
        self.assertEqual(
            frappe.db.get_value("Customer Warehouse", self.kho["kho_bm"], "customer"),
            "Bệnh viện Bạch Mai",
        )

    def test_seed_is_idempotent(self):
        again = seed_kho_demo()
        self.assertEqual(again["kho_bm"], self.kho["kho_bm"])
        self.assertEqual(
            frappe.db.count("Customer Warehouse", {"customer": "Bệnh viện Bạch Mai"}), 1
        )

    def test_one_warehouse_per_customer_enforced(self):
        doc = frappe.get_doc({
            "doctype": "Customer Warehouse",
            "customer": "Bệnh viện Bạch Mai",
            "ten_kho": "Kho trùng",
            "ma_kho": "BM2",
            "ngay_bat_dau": "2026-01-01",
        })
        with self.assertRaises(frappe.ValidationError) as ctx:
            doc.insert(ignore_permissions=True)
        self.assertIn("đã có kho", str(ctx.exception))
```

- [ ] **Step 2: Chạy test cho thất bại**

Run: `cd /home/hoangvietyeuem/frappe-bench-yhct && bench --site erptest.local run-tests --app miyano_portal --module miyano_portal.tests.test_kho_ledger`
Expected: FAIL — `ModuleNotFoundError: No module named 'miyano_portal.setup.seed_kho_demo'`

- [ ] **Step 3: Tạo doctype JSON**

Tạo `miyano_portal/miyano_portal/doctype/customer_warehouse/__init__.py` (file rỗng).

Tạo `miyano_portal/miyano_portal/doctype/customer_warehouse/customer_warehouse.json`:

```json
{
 "actions": [],
 "allow_rename": 0,
 "autoname": "KKH-.#####",
 "creation": "2026-08-06 00:00:00.000000",
 "doctype": "DocType",
 "editable_grid": 1,
 "engine": "InnoDB",
 "field_order": [
  "customer", "ten_kho", "ma_kho", "active", "col_1", "thu_kho",
  "dia_chi_kho", "ngay_bat_dau", "sec_in", "ten_don_vi_in", "bo_phan_in",
  "col_2", "mau_phieu_nhap", "mau_phieu_xuat"
 ],
 "fields": [
  {"fieldname": "customer", "fieldtype": "Link", "label": "Khách hàng", "options": "Customer", "reqd": 1, "unique": 1, "in_list_view": 1},
  {"fieldname": "ten_kho", "fieldtype": "Data", "label": "Tên kho", "reqd": 1, "in_list_view": 1},
  {"fieldname": "ma_kho", "fieldtype": "Data", "label": "Mã kho", "reqd": 1, "unique": 1, "description": "Viết tắt dùng trong số phiếu, ví dụ BM"},
  {"fieldname": "active", "fieldtype": "Check", "label": "Đang hoạt động", "default": "1"},
  {"fieldname": "col_1", "fieldtype": "Column Break"},
  {"fieldname": "thu_kho", "fieldtype": "Data", "label": "Thủ kho"},
  {"fieldname": "dia_chi_kho", "fieldtype": "Small Text", "label": "Địa chỉ kho"},
  {"fieldname": "ngay_bat_dau", "fieldtype": "Date", "label": "Ngày bắt đầu quản lý", "reqd": 1},
  {"fieldname": "sec_in", "fieldtype": "Section Break", "label": "Thông tin in phiếu"},
  {"fieldname": "ten_don_vi_in", "fieldtype": "Data", "label": "Tên đơn vị in trên phiếu"},
  {"fieldname": "bo_phan_in", "fieldtype": "Data", "label": "Bộ phận"},
  {"fieldname": "col_2", "fieldtype": "Column Break"},
  {"fieldname": "mau_phieu_nhap", "fieldtype": "Link", "label": "Mẫu phiếu nhập", "options": "Print Format"},
  {"fieldname": "mau_phieu_xuat", "fieldtype": "Link", "label": "Mẫu phiếu xuất", "options": "Print Format"}
 ],
 "index_web_pages_for_search": 0,
 "links": [],
 "modified": "2026-08-06 00:00:00.000000",
 "modified_by": "Administrator",
 "module": "Miyano Portal",
 "name": "Customer Warehouse",
 "owner": "Administrator",
 "permissions": [
  {"role": "System Manager", "read": 1, "write": 1, "create": 1, "delete": 1, "report": 1, "export": 1},
  {"role": "Sales Manager", "read": 1, "write": 1, "create": 1, "report": 1},
  {"role": "Sales User", "read": 1, "report": 1},
  {"role": "Customer", "read": 1}
 ],
 "sort_field": "modified",
 "sort_order": "DESC",
 "states": [],
 "track_changes": 1
}
```

- [ ] **Step 4: Viết controller**

Tạo `miyano_portal/miyano_portal/doctype/customer_warehouse/customer_warehouse.py`:

```python
import frappe
from frappe.model.document import Document


class CustomerWarehouse(Document):
	def validate(self):
		self._one_per_customer()
		self._ma_kho_duy_nhat()
		if not self.ten_don_vi_in:
			self.ten_don_vi_in = frappe.db.get_value(
				"Customer", self.customer, "customer_name"
			)

	def _one_per_customer(self):
		"""Mỗi khách hàng chỉ được có đúng một kho trên cổng (spec §2, quyết định 5).

		Field `customer` đã đánh unique ở tầng database, nhưng lỗi
		DuplicateEntryError của MariaDB không đọc được với người dùng cuối, nên
		chặn sớm ở đây để trả về thông báo tiếng Việt.
		"""
		existing = frappe.db.get_value(
			"Customer Warehouse",
			{"customer": self.customer, "name": ["!=", self.name or ""]},
			"name",
		)
		if existing:
			frappe.throw(
				f"Khách hàng {self.customer} đã có kho {existing} trên cổng. "
				f"Mỗi khách hàng chỉ được có một kho.",
				frappe.ValidationError,
			)

	def _ma_kho_duy_nhat(self):
		"""Mã kho đi vào số phiếu (PN-BM-2026-00001) nên phải duy nhất toàn hệ thống.

		Field đã đánh unique ở database, nhưng khi chạm phải index đó Frappe in
		ra "Mã kho must be unique" — tiếng Anh, lẫn vào giao diện tiếng Việt.
		Chặn trước ở đây để thông báo đọc được.
		"""
		self.ma_kho = (self.ma_kho or "").strip()
		existing = frappe.db.get_value(
			"Customer Warehouse",
			{"ma_kho": self.ma_kho, "name": ["!=", self.name or ""]},
			["name", "customer"],
			as_dict=True,
		)
		if existing:
			frappe.throw(
				f"Mã kho {self.ma_kho} đã được dùng cho kho {existing.name} "
				f"({existing.customer}). Hãy chọn mã khác.",
				frappe.ValidationError,
			)
```

- [ ] **Step 5: Viết seed**

Tạo `miyano_portal/setup/seed_kho_demo.py`:

```python
"""Dữ liệu kho tối thiểu cho test và demo.

Idempotent: gọi bao nhiêu lần cũng ra cùng kết quả, giống seed_demo.py sẵn có.
Dựa vào các Customer do miyano_portal.setup.seed_demo tạo ra.
"""

import frappe
from miyano_portal.setup.seed_demo import seed_demo

KHO_DEMO = [
	{"customer": "Bệnh viện Bạch Mai", "ten_kho": "Kho Khoa Dược", "ma_kho": "BM"},
	{"customer": "PXN ABC", "ten_kho": "Kho vật tư PXN", "ma_kho": "PXN"},
]


def _ensure_kho(customer: str, ten_kho: str, ma_kho: str) -> str:
	existing = frappe.db.get_value("Customer Warehouse", {"customer": customer}, "name")
	if existing:
		return existing
	doc = frappe.get_doc({
		"doctype": "Customer Warehouse",
		"customer": customer,
		"ten_kho": ten_kho,
		"ma_kho": ma_kho,
		"thu_kho": "Nguyễn Thị Thủ Kho",
		"ngay_bat_dau": "2026-01-01",
	})
	doc.insert(ignore_permissions=True)
	return doc.name


def seed_kho_demo() -> dict:
	seed_demo()
	names = {}
	for row in KHO_DEMO:
		names[row["customer"]] = _ensure_kho(
			row["customer"], row["ten_kho"], row["ma_kho"]
		)
	# KHÔNG gọi frappe.db.commit() ở đây. seed_demo.py sẵn có cũng không gọi,
	# và tám test file hiện tại đều seed trong setUp: commit sẽ phá rollback
	# của FrappeTestCase và ghi rác vĩnh viễn vào site.
	return {
		"kho_bm": names["Bệnh viện Bạch Mai"],
		"kho_pxn": names["PXN ABC"],
	}
```

- [ ] **Step 6: Migrate và chạy test**

Run:
```bash
cd /home/hoangvietyeuem/frappe-bench-yhct
bench --site erptest.local migrate
bench --site erptest.local run-tests --app miyano_portal --module miyano_portal.tests.test_kho_ledger
```
Expected: PASS, 3 test.

- [ ] **Step 7: Commit**

```bash
cd /home/hoangvietyeuem/frappe-bench-yhct/apps/miyano_portal
git add miyano_portal/miyano_portal/doctype/customer_warehouse miyano_portal/setup/seed_kho_demo.py miyano_portal/tests/test_kho_ledger.py
git commit -m "feat(kho): doctype Customer Warehouse, mỗi khách một kho"
```

---

### Task 2: Doctype `Customer Warehouse Item`

**Files:**
- Create: `miyano_portal/miyano_portal/doctype/customer_warehouse_item/__init__.py`
- Create: `miyano_portal/miyano_portal/doctype/customer_warehouse_item/customer_warehouse_item.json`
- Create: `miyano_portal/miyano_portal/doctype/customer_warehouse_item/customer_warehouse_item.py`
- Modify: `miyano_portal/setup/seed_kho_demo.py`
- Test: `miyano_portal/tests/test_kho_ledger.py`

**Interfaces:**
- Consumes: `Customer Warehouse` (Task 1), `seed_kho_demo()`.
- Produces:
  - Doctype `Customer Warehouse Item`, autoname `VTK-.#####`, fields: `kho` (Link Customer Warehouse, reqd), `ma_vat_tu` (Data, reqd), `ten_vat_tu` (Data, reqd), `dvt` (Data, reqd), `item_code` (Link Item, **nullable**), `quy_cach` (Data), `nhom` (Data), `ghi_chu` (Small Text), `active` (Check, default 1).
  - `seed_kho_demo()` bổ sung khoá `"vt_bm"` — tên `Customer Warehouse Item` mã `MYN-GLOVE-M` trong kho Bạch Mai, có `item_code` trỏ về Item thật; và `"vt_rieng_bm"` — mã riêng `BM-GAC-01` với `item_code` để trống.

- [ ] **Step 1: Viết test thất bại**

Thêm vào `miyano_portal/tests/test_kho_ledger.py`:

```python
class TestKhoWarehouseItem(FrappeTestCase):
    def setUp(self):
        self.kho = seed_kho_demo()

    def test_miyano_item_links_to_real_item(self):
        vt = frappe.get_doc("Customer Warehouse Item", self.kho["vt_bm"])
        self.assertEqual(vt.item_code, "MYN-GLOVE-M")
        self.assertEqual(vt.kho, self.kho["kho_bm"])

    def test_customer_private_code_has_no_item(self):
        vt = frappe.get_doc("Customer Warehouse Item", self.kho["vt_rieng_bm"])
        self.assertFalse(vt.item_code)
        self.assertFalse(frappe.db.exists("Item", "BM-GAC-01"))

    def test_duplicate_code_in_same_warehouse_blocked(self):
        doc = frappe.get_doc({
            "doctype": "Customer Warehouse Item",
            "kho": self.kho["kho_bm"],
            "ma_vat_tu": "BM-GAC-01",
            "ten_vat_tu": "Gạc trùng mã",
            "dvt": "Cái",
        })
        with self.assertRaises(frappe.ValidationError) as ctx:
            doc.insert(ignore_permissions=True)
        self.assertIn("đã tồn tại", str(ctx.exception))

    def test_same_code_allowed_in_different_warehouse(self):
        doc = frappe.get_doc({
            "doctype": "Customer Warehouse Item",
            "kho": self.kho["kho_pxn"],
            "ma_vat_tu": "BM-GAC-01",
            "ten_vat_tu": "Gạc của PXN",
            "dvt": "Cái",
        })
        doc.insert(ignore_permissions=True)
        self.assertTrue(doc.name)
```

- [ ] **Step 2: Chạy test cho thất bại**

Run: `cd /home/hoangvietyeuem/frappe-bench-yhct && bench --site erptest.local run-tests --app miyano_portal --module miyano_portal.tests.test_kho_ledger`
Expected: FAIL — `KeyError: 'vt_bm'`

- [ ] **Step 3: Tạo doctype JSON**

Tạo `miyano_portal/miyano_portal/doctype/customer_warehouse_item/__init__.py` (rỗng).

Tạo `miyano_portal/miyano_portal/doctype/customer_warehouse_item/customer_warehouse_item.json`:

```json
{
 "actions": [],
 "allow_rename": 0,
 "autoname": "VTK-.#####",
 "creation": "2026-08-06 00:00:00.000000",
 "doctype": "DocType",
 "editable_grid": 1,
 "engine": "InnoDB",
 "field_order": [
  "kho", "ma_vat_tu", "ten_vat_tu", "dvt", "active",
  "col_1", "item_code", "quy_cach", "nhom", "ghi_chu"
 ],
 "fields": [
  {"fieldname": "kho", "fieldtype": "Link", "label": "Kho", "options": "Customer Warehouse", "reqd": 1, "search_index": 1},
  {"fieldname": "ma_vat_tu", "fieldtype": "Data", "label": "Mã vật tư", "reqd": 1, "in_list_view": 1, "search_index": 1},
  {"fieldname": "ten_vat_tu", "fieldtype": "Data", "label": "Tên vật tư", "reqd": 1, "in_list_view": 1},
  {"fieldname": "dvt", "fieldtype": "Data", "label": "ĐVT", "reqd": 1, "in_list_view": 1},
  {"fieldname": "active", "fieldtype": "Check", "label": "Đang dùng", "default": "1"},
  {"fieldname": "col_1", "fieldtype": "Column Break"},
  {"fieldname": "item_code", "fieldtype": "Link", "label": "Mã hàng Miyano", "options": "Item", "description": "Để trống nếu là mã khách tự thêm"},
  {"fieldname": "quy_cach", "fieldtype": "Data", "label": "Quy cách"},
  {"fieldname": "nhom", "fieldtype": "Data", "label": "Nhóm"},
  {"fieldname": "ghi_chu", "fieldtype": "Small Text", "label": "Ghi chú"}
 ],
 "index_web_pages_for_search": 0,
 "links": [],
 "modified": "2026-08-06 00:00:00.000000",
 "modified_by": "Administrator",
 "module": "Miyano Portal",
 "name": "Customer Warehouse Item",
 "owner": "Administrator",
 "permissions": [
  {"role": "System Manager", "read": 1, "write": 1, "create": 1, "delete": 1, "report": 1, "export": 1},
  {"role": "Sales Manager", "read": 1, "write": 1, "create": 1, "report": 1},
  {"role": "Sales User", "read": 1, "report": 1},
  {"role": "Customer", "read": 1}
 ],
 "sort_field": "modified",
 "sort_order": "DESC",
 "states": [],
 "title_field": "ten_vat_tu",
 "track_changes": 1
}
```

- [ ] **Step 4: Viết controller**

Tạo `miyano_portal/miyano_portal/doctype/customer_warehouse_item/customer_warehouse_item.py`:

```python
import frappe
from frappe.model.document import Document


class CustomerWarehouseItem(Document):
	def validate(self):
		self.ma_vat_tu = (self.ma_vat_tu or "").strip()
		self._unique_within_warehouse()

	def _unique_within_warehouse(self):
		"""Mã vật tư chỉ cần duy nhất TRONG một kho.

		Hai khách khác nhau hoàn toàn được phép dùng trùng mã, nên không thể
		đánh unique ở tầng field; phải kiểm tra theo cặp (kho, ma_vat_tu).
		"""
		existing = frappe.db.get_value(
			"Customer Warehouse Item",
			{
				"kho": self.kho,
				"ma_vat_tu": self.ma_vat_tu,
				"name": ["!=", self.name or ""],
			},
			"name",
		)
		if existing:
			frappe.throw(
				f"Mã vật tư {self.ma_vat_tu} đã tồn tại trong kho này ({existing}).",
				frappe.ValidationError,
			)
```

- [ ] **Step 5: Mở rộng seed**

Trong `miyano_portal/setup/seed_kho_demo.py`, thêm hằng số và hàm sau vào cuối file (trước `seed_kho_demo`):

```python
VAT_TU_DEMO = [
	{
		"key": "vt_bm", "kho_key": "kho_bm", "ma_vat_tu": "MYN-GLOVE-M",
		"ten_vat_tu": "Găng tay y tế size M", "dvt": "Hộp",
		"item_code": "MYN-GLOVE-M",
	},
	{
		"key": "vt_rieng_bm", "kho_key": "kho_bm", "ma_vat_tu": "BM-GAC-01",
		"ten_vat_tu": "Gạc y tế mua ngoài", "dvt": "Cái", "item_code": None,
	},
	{
		"key": "vt_pxn", "kho_key": "kho_pxn", "ma_vat_tu": "MYN-SYR-10",
		"ten_vat_tu": "Bơm tiêm 10ml", "dvt": "Cái", "item_code": "MYN-SYR-10",
	},
]


def _ensure_vat_tu(kho: str, row: dict) -> str:
	existing = frappe.db.get_value(
		"Customer Warehouse Item", {"kho": kho, "ma_vat_tu": row["ma_vat_tu"]}, "name"
	)
	if existing:
		return existing
	# item_code chỉ set khi Item đó thật sự tồn tại trên site, để seed không vỡ
	# khi chạy trên database chưa có catalog Miyano.
	item_code = row["item_code"]
	if item_code and not frappe.db.exists("Item", item_code):
		item_code = None
	doc = frappe.get_doc({
		"doctype": "Customer Warehouse Item",
		"kho": kho,
		"ma_vat_tu": row["ma_vat_tu"],
		"ten_vat_tu": row["ten_vat_tu"],
		"dvt": row["dvt"],
		"item_code": item_code,
	})
	doc.insert(ignore_permissions=True)
	return doc.name
```

Rồi sửa `seed_kho_demo` để trả thêm các khoá vật tư — thay phần `return` bằng:

```python
def seed_kho_demo() -> dict:
	seed_demo()
	names = {}
	for row in KHO_DEMO:
		names[row["customer"]] = _ensure_kho(
			row["customer"], row["ten_kho"], row["ma_kho"]
		)
	out = {
		"kho_bm": names["Bệnh viện Bạch Mai"],
		"kho_pxn": names["PXN ABC"],
	}
	for row in VAT_TU_DEMO:
		out[row["key"]] = _ensure_vat_tu(out[row["kho_key"]], row)
	return out
```

- [ ] **Step 6: Migrate và chạy test**

Run:
```bash
cd /home/hoangvietyeuem/frappe-bench-yhct
bench --site erptest.local migrate
bench --site erptest.local run-tests --app miyano_portal --module miyano_portal.tests.test_kho_ledger
```
Expected: PASS, 7 test.

- [ ] **Step 7: Commit**

```bash
cd /home/hoangvietyeuem/frappe-bench-yhct/apps/miyano_portal
git add miyano_portal/miyano_portal/doctype/customer_warehouse_item miyano_portal/setup/seed_kho_demo.py miyano_portal/tests/test_kho_ledger.py
git commit -m "feat(kho): doctype Customer Warehouse Item, mã riêng không tạo Item"
```

---

### Task 3: Sổ kho và tồn theo lô

Đây là task trọng tâm của Phase 1. Sổ là nguồn sự thật; tồn theo lô là cache tái dựng được.

**Files:**
- Create: `miyano_portal/miyano_portal/doctype/customer_stock_ledger_entry/{__init__.py,customer_stock_ledger_entry.json,customer_stock_ledger_entry.py}`
- Create: `miyano_portal/miyano_portal/doctype/customer_stock_lot_balance/{__init__.py,customer_stock_lot_balance.json,customer_stock_lot_balance.py}`
- Create: `miyano_portal/kho/__init__.py`
- Create: `miyano_portal/kho/ledger.py`
- Test: `miyano_portal/tests/test_kho_ledger.py`

**Interfaces:**
- Consumes: `Customer Warehouse` (Task 1), `Customer Warehouse Item` (Task 2).
- Produces — `miyano_portal.kho.ledger`:
  - `post_lines(voucher, lines: list[dict]) -> list[str]` — `voucher` là Document có `.kho`, `.ngay`, `.doctype`, `.name`. Mỗi phần tử `lines` là dict `{"vat_tu": str, "so_lo": str, "han_su_dung": str | None, "so_luong": float (đã mang dấu), "don_gia": float, "chung_tu_row": str}`. Insert `Customer Stock Ledger Entry` và cập nhật `Customer Stock Lot Balance`. Trả về danh sách tên entry đã tạo.
  - `get_lot_balance(kho: str, vat_tu: str, so_lo: str) -> dict | None` — trả `{"name","so_luong","don_gia","han_su_dung"}` hoặc `None`.
  - `get_lot_balances(kho: str, vat_tu: str) -> list[dict]` — các lô còn tồn > 0, **sắp xếp FEFO**: `han_su_dung` tăng dần, lô không có hạn xếp cuối.
  - `mark_reversed(chung_tu_type: str, chung_tu: str) -> None` — bật `da_dao = 1` trên mọi entry của chứng từ đó.
  - `rebuild_lot_balance(kho: str | None = None) -> int` — xoá và dựng lại toàn bộ `Customer Stock Lot Balance` từ sổ, trả về số bản ghi đã ghi.
  - `LOT_KHONG_CO = "KHONG-LO"` — hằng số số lô cho vật tư không quản lô.

- [ ] **Step 1: Viết test thất bại**

Thêm vào `miyano_portal/tests/test_kho_ledger.py` (thêm import ở đầu file):

```python
from miyano_portal.kho import ledger
```

```python
class _FakeVoucher:
    """Đủ thuộc tính để post_lines dùng, không cần doctype thật ở task này."""

    def __init__(self, kho, ngay="2026-02-01", doctype="Customer Stock Receipt",
                 name="TEST-PN-001"):
        self.kho = kho
        self.ngay = ngay
        self.doctype = doctype
        self.name = name


class TestKhoLedger(FrappeTestCase):
    def setUp(self):
        self.kho = seed_kho_demo()
        frappe.db.delete("Customer Stock Ledger Entry", {"kho": self.kho["kho_bm"]})
        frappe.db.delete("Customer Stock Lot Balance", {"kho": self.kho["kho_bm"]})

    def _nhap(self, so_luong, don_gia, so_lo="LO-A", han="2027-01-01", row="r1",
              name="TEST-PN-001"):
        v = _FakeVoucher(self.kho["kho_bm"], name=name)
        return ledger.post_lines(v, [{
            "vat_tu": self.kho["vt_bm"], "so_lo": so_lo, "han_su_dung": han,
            "so_luong": so_luong, "don_gia": don_gia, "chung_tu_row": row,
        }])

    def test_receipt_creates_lot_balance(self):
        self._nhap(100, 50000)
        bal = ledger.get_lot_balance(self.kho["kho_bm"], self.kho["vt_bm"], "LO-A")
        self.assertEqual(bal["so_luong"], 100)
        self.assertEqual(bal["don_gia"], 50000)

    def test_issue_reduces_lot_balance(self):
        self._nhap(100, 50000)
        v = _FakeVoucher(self.kho["kho_bm"], doctype="Customer Stock Issue",
                         name="TEST-PX-001")
        ledger.post_lines(v, [{
            "vat_tu": self.kho["vt_bm"], "so_lo": "LO-A", "han_su_dung": "2027-01-01",
            "so_luong": -30, "don_gia": 50000, "chung_tu_row": "r9",
        }])
        bal = ledger.get_lot_balance(self.kho["kho_bm"], self.kho["vt_bm"], "LO-A")
        self.assertEqual(bal["so_luong"], 70)
        # Xuất không đổi đơn giá của lô
        self.assertEqual(bal["don_gia"], 50000)

    def test_same_lot_twice_gives_weighted_average_price(self):
        self._nhap(100, 50000, row="r1", name="TEST-PN-001")
        self._nhap(100, 70000, row="r2", name="TEST-PN-002")
        bal = ledger.get_lot_balance(self.kho["kho_bm"], self.kho["vt_bm"], "LO-A")
        self.assertEqual(bal["so_luong"], 200)
        self.assertEqual(bal["don_gia"], 60000)

    def test_ledger_is_append_only(self):
        self._nhap(100, 50000)
        entries = frappe.get_all(
            "Customer Stock Ledger Entry",
            filters={"kho": self.kho["kho_bm"]},
            fields=["name", "so_luong", "gia_tri", "chung_tu"],
        )
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["gia_tri"], 100 * 50000)

    def test_duplicate_row_is_not_posted_twice(self):
        self._nhap(100, 50000, row="r1")
        self._nhap(100, 50000, row="r1")
        self.assertEqual(
            frappe.db.count(
                "Customer Stock Ledger Entry", {"kho": self.kho["kho_bm"]}
            ),
            1,
        )

    def test_mark_reversed_flags_entries(self):
        self._nhap(100, 50000)
        ledger.mark_reversed("Customer Stock Receipt", "TEST-PN-001")
        flags = frappe.get_all(
            "Customer Stock Ledger Entry",
            filters={"chung_tu": "TEST-PN-001"}, pluck="da_dao",
        )
        self.assertTrue(all(flags))

    def test_rebuild_lot_balance_matches_ledger(self):
        self._nhap(100, 50000)
        self._nhap(50, 50000, so_lo="LO-B", han="2026-12-01", row="r2",
                   name="TEST-PN-002")
        frappe.db.delete("Customer Stock Lot Balance", {"kho": self.kho["kho_bm"]})
        written = ledger.rebuild_lot_balance(self.kho["kho_bm"])
        self.assertEqual(written, 2)
        self.assertEqual(
            ledger.get_lot_balance(
                self.kho["kho_bm"], self.kho["vt_bm"], "LO-A")["so_luong"], 100
        )
        self.assertEqual(
            ledger.get_lot_balance(
                self.kho["kho_bm"], self.kho["vt_bm"], "LO-B")["so_luong"], 50
        )

    def test_get_lot_balances_is_fefo_ordered(self):
        self._nhap(10, 1000, so_lo="LO-XA", han="2028-01-01", row="r1",
                   name="TEST-PN-001")
        self._nhap(10, 1000, so_lo="LO-GAN", han="2026-09-01", row="r2",
                   name="TEST-PN-002")
        self._nhap(10, 1000, so_lo=ledger.LOT_KHONG_CO, han=None, row="r3",
                   name="TEST-PN-003")
        lots = ledger.get_lot_balances(self.kho["kho_bm"], self.kho["vt_bm"])
        self.assertEqual([l["so_lo"] for l in lots],
                         ["LO-GAN", "LO-XA", ledger.LOT_KHONG_CO])

    def test_zero_balance_lot_excluded_from_fefo(self):
        self._nhap(10, 1000, so_lo="LO-HET", han="2026-09-01")
        v = _FakeVoucher(self.kho["kho_bm"], doctype="Customer Stock Issue",
                         name="TEST-PX-001")
        ledger.post_lines(v, [{
            "vat_tu": self.kho["vt_bm"], "so_lo": "LO-HET",
            "han_su_dung": "2026-09-01", "so_luong": -10, "don_gia": 1000,
            "chung_tu_row": "r9",
        }])
        lots = ledger.get_lot_balances(self.kho["kho_bm"], self.kho["vt_bm"])
        self.assertEqual(lots, [])
```

- [ ] **Step 2: Chạy test cho thất bại**

Run: `cd /home/hoangvietyeuem/frappe-bench-yhct && bench --site erptest.local run-tests --app miyano_portal --module miyano_portal.tests.test_kho_ledger`
Expected: FAIL — `ModuleNotFoundError: No module named 'miyano_portal.kho'`

- [ ] **Step 3: Tạo doctype `Customer Stock Ledger Entry`**

Tạo `miyano_portal/miyano_portal/doctype/customer_stock_ledger_entry/__init__.py` (rỗng).

Tạo `.../customer_stock_ledger_entry.json`:

```json
{
 "actions": [],
 "allow_rename": 0,
 "autoname": "SKK-.#########",
 "creation": "2026-08-06 00:00:00.000000",
 "doctype": "DocType",
 "editable_grid": 0,
 "engine": "InnoDB",
 "field_order": [
  "kho", "ngay", "vat_tu", "so_lo", "han_su_dung",
  "col_1", "so_luong", "don_gia", "gia_tri",
  "sec_ct", "chung_tu_type", "chung_tu", "chung_tu_row", "da_dao"
 ],
 "fields": [
  {"fieldname": "kho", "fieldtype": "Link", "label": "Kho", "options": "Customer Warehouse", "reqd": 1, "search_index": 1, "read_only": 1},
  {"fieldname": "ngay", "fieldtype": "Date", "label": "Ngày", "reqd": 1, "search_index": 1, "read_only": 1, "in_list_view": 1},
  {"fieldname": "vat_tu", "fieldtype": "Link", "label": "Vật tư", "options": "Customer Warehouse Item", "reqd": 1, "search_index": 1, "read_only": 1, "in_list_view": 1},
  {"fieldname": "so_lo", "fieldtype": "Data", "label": "Số lô", "reqd": 1, "read_only": 1, "in_list_view": 1},
  {"fieldname": "han_su_dung", "fieldtype": "Date", "label": "Hạn sử dụng", "read_only": 1},
  {"fieldname": "col_1", "fieldtype": "Column Break"},
  {"fieldname": "so_luong", "fieldtype": "Float", "label": "Số lượng", "precision": "3", "read_only": 1, "in_list_view": 1, "description": "Dương là nhập, âm là xuất"},
  {"fieldname": "don_gia", "fieldtype": "Currency", "label": "Đơn giá", "read_only": 1},
  {"fieldname": "gia_tri", "fieldtype": "Currency", "label": "Giá trị", "read_only": 1},
  {"fieldname": "sec_ct", "fieldtype": "Section Break", "label": "Chứng từ"},
  {"fieldname": "chung_tu_type", "fieldtype": "Select", "label": "Loại chứng từ", "options": "Customer Stock Receipt\nCustomer Stock Issue", "reqd": 1, "read_only": 1},
  {"fieldname": "chung_tu", "fieldtype": "Data", "label": "Số chứng từ", "reqd": 1, "search_index": 1, "read_only": 1},
  {"fieldname": "chung_tu_row", "fieldtype": "Data", "label": "Dòng chứng từ", "reqd": 1, "search_index": 1, "read_only": 1},
  {"fieldname": "da_dao", "fieldtype": "Check", "label": "Đã bị đảo", "default": "0"}
 ],
 "index_web_pages_for_search": 0,
 "links": [],
 "modified": "2026-08-06 00:00:00.000000",
 "modified_by": "Administrator",
 "module": "Miyano Portal",
 "name": "Customer Stock Ledger Entry",
 "owner": "Administrator",
 "permissions": [
  {"role": "System Manager", "read": 1, "report": 1, "export": 1},
  {"role": "Sales Manager", "read": 1, "report": 1},
  {"role": "Sales User", "read": 1, "report": 1},
  {"role": "Customer", "read": 1}
 ],
 "sort_field": "creation",
 "sort_order": "ASC",
 "states": []
}
```

Tạo `.../customer_stock_ledger_entry.py`:

```python
import frappe
from frappe.model.document import Document


class CustomerStockLedgerEntry(Document):
	"""Sổ ghi tăng dần. Chỉ insert, không sửa, không xoá.

	Ngoại lệ duy nhất được phép sửa sau khi insert là cờ `da_dao` — xem
	ledger.mark_reversed(). Mọi thay đổi khác đều bị chặn ở đây để một lỗi
	lập trình về sau không âm thầm làm hỏng sổ.

	Chốt chặn nằm ở `before_save`, KHÔNG phải `on_update`: Document.save()
	gọi db_update() rồi mới tới run_post_save_methods(), và không có savepoint
	quanh một lần save. Đặt ở on_update thì UPDATE đã ghi xong trước khi lỗi
	được ném, nên bất kỳ ai bắt ValidationError cũng để lại dòng sổ hỏng đã
	nằm trong transaction. `on_trash` thì ngược lại, delete_doc chạy on_trash
	TRƯỚC khi xoá nên đặt ở đó là đúng.
	"""

	def before_save(self):
		if self.is_new():
			return
		before = self.get_doc_before_save()
		if not before:
			return
		changed = {
			f.fieldname
			for f in self.meta.fields
			if self.get(f.fieldname) != before.get(f.fieldname)
		}
		if changed - {"da_dao"}:
			frappe.throw(
				"Không được sửa dòng sổ kho đã ghi. Muốn điều chỉnh thì huỷ "
				"phiếu để hệ thống ghi phiếu đảo.",
				frappe.ValidationError,
			)

	def on_trash(self):
		frappe.throw(
			"Không được xoá dòng sổ kho. Muốn điều chỉnh thì huỷ phiếu để hệ "
			"thống ghi phiếu đảo.",
			frappe.ValidationError,
		)
```

- [ ] **Step 4: Tạo doctype `Customer Stock Lot Balance`**

Tạo `miyano_portal/miyano_portal/doctype/customer_stock_lot_balance/__init__.py` (rỗng).

Tạo `.../customer_stock_lot_balance.json`:

```json
{
 "actions": [],
 "allow_rename": 0,
 "autoname": "",
 "creation": "2026-08-06 00:00:00.000000",
 "doctype": "DocType",
 "editable_grid": 0,
 "engine": "InnoDB",
 "field_order": [
  "kho", "vat_tu", "so_lo", "han_su_dung",
  "col_1", "so_luong", "don_gia", "gia_tri"
 ],
 "fields": [
  {"fieldname": "kho", "fieldtype": "Link", "label": "Kho", "options": "Customer Warehouse", "reqd": 1, "search_index": 1, "read_only": 1},
  {"fieldname": "vat_tu", "fieldtype": "Link", "label": "Vật tư", "options": "Customer Warehouse Item", "reqd": 1, "search_index": 1, "read_only": 1, "in_list_view": 1},
  {"fieldname": "so_lo", "fieldtype": "Data", "label": "Số lô", "reqd": 1, "read_only": 1, "in_list_view": 1},
  {"fieldname": "han_su_dung", "fieldtype": "Date", "label": "Hạn sử dụng", "read_only": 1, "in_list_view": 1},
  {"fieldname": "col_1", "fieldtype": "Column Break"},
  {"fieldname": "so_luong", "fieldtype": "Float", "label": "Số lượng còn", "precision": "3", "read_only": 1, "in_list_view": 1},
  {"fieldname": "don_gia", "fieldtype": "Currency", "label": "Đơn giá", "read_only": 1},
  {"fieldname": "gia_tri", "fieldtype": "Currency", "label": "Giá trị", "read_only": 1}
 ],
 "index_web_pages_for_search": 0,
 "links": [],
 "modified": "2026-08-06 00:00:00.000000",
 "modified_by": "Administrator",
 "module": "Miyano Portal",
 "name": "Customer Stock Lot Balance",
 "owner": "Administrator",
 "permissions": [
  {"role": "System Manager", "read": 1, "report": 1, "export": 1},
  {"role": "Sales Manager", "read": 1, "report": 1},
  {"role": "Sales User", "read": 1, "report": 1},
  {"role": "Customer", "read": 1}
 ],
 "sort_field": "modified",
 "sort_order": "DESC",
 "states": []
}
```

Tạo `.../customer_stock_lot_balance.py`:

```python
import hashlib

from frappe.model.document import Document


class CustomerStockLotBalance(Document):
	def autoname(self):
		"""Tên xác định theo (kho, vật tư, lô) để không bao giờ có hai bản ghi
		tồn cho cùng một lô.

		Số lô do khách nhập tay nên có thể dài hoặc chứa ký tự lạ; băm lại để
		tên luôn nằm trong giới hạn 140 ký tự của Frappe.
		"""
		raw = f"{self.kho}::{self.vat_tu}::{self.so_lo}"
		self.name = "TON-" + hashlib.sha1(raw.encode("utf-8")).hexdigest()[:20]
```

- [ ] **Step 5: Viết engine sổ kho**

Tạo `miyano_portal/kho/__init__.py` (rỗng).

Tạo `miyano_portal/kho/ledger.py`:

```python
"""Engine ghi sổ kho khách hàng.

`Customer Stock Ledger Entry` là nguồn sự thật duy nhất: chỉ ghi thêm, không
sửa, không xoá. `Customer Stock Lot Balance` là cache dẫn xuất, tái dựng lại
được bất cứ lúc nào bằng rebuild_lot_balance().

Cố ý KHÔNG dùng Stock Ledger Entry / Bin của ERPNext: kho khách không thuộc
Company nào, và cả hai company của Miyano đều bật perpetual inventory nên mọi
bút toán kho ở đó đều chảy vào sổ kế toán của Miyano.
"""

import frappe

LOT_KHONG_CO = "KHONG-LO"

# Số lượng nhỏ hơn ngưỡng này coi như bằng 0, tránh rác do sai số dấu phẩy động
# tích luỹ qua nhiều lần cộng trừ.
EPS = 0.0005


def _lot_balance_name(kho: str, vat_tu: str, so_lo: str) -> str | None:
	return frappe.db.get_value(
		"Customer Stock Lot Balance",
		{"kho": kho, "vat_tu": vat_tu, "so_lo": so_lo},
		"name",
	)


def _apply_to_balance(kho, vat_tu, so_lo, han_su_dung, delta, don_gia):
	"""Cộng `delta` vào tồn của một lô và cập nhật đơn giá.

	Nhập (delta > 0) làm đơn giá lô thành bình quân gia quyền của các lần nhập.
	Xuất (delta < 0) không đổi đơn giá — giá vốn xuất chính là đơn giá đang có
	của lô, đó là toàn bộ lý do sổ này theo lô thay vì cần engine định giá.
	"""
	name = _lot_balance_name(kho, vat_tu, so_lo)
	if name:
		bal = frappe.get_doc("Customer Stock Lot Balance", name)
	else:
		bal = frappe.new_doc("Customer Stock Lot Balance")
		bal.kho = kho
		bal.vat_tu = vat_tu
		bal.so_lo = so_lo
		bal.so_luong = 0
		bal.don_gia = 0

	cu_qty = float(bal.so_luong or 0)
	moi_qty = cu_qty + float(delta)

	if delta > 0:
		tong = cu_qty + float(delta)
		if tong > EPS:
			bal.don_gia = (
				cu_qty * float(bal.don_gia or 0) + float(delta) * float(don_gia)
			) / tong
		else:
			bal.don_gia = float(don_gia)

	if moi_qty < -EPS:
		# Chặn tồn âm ngay tại ranh giới sổ, không chỉ ở tầng phiếu. Nếu để
		# lọt, lô mang số âm sẽ (a) biến mất khỏi FEFO vì bộ lọc so_luong > EPS,
		# và (b) làm hỏng vĩnh viễn đơn giá bình quân ở lần nhập kế tiếp:
		# (-50*50000 + 100*70000)/50 = 90000 thay vì 70000.
		frappe.throw(
			f"Lô {so_lo} chỉ còn {cu_qty:g}, không đủ để ghi giảm "
			f"{abs(float(delta)):g}.",
			frappe.ValidationError,
		)

	bal.so_luong = 0.0 if abs(moi_qty) < EPS else moi_qty
	# Hạn dùng ghi lần đầu; lần nhập sau của cùng lô không được ghi đè bằng
	# giá trị rỗng, nhưng được phép bổ sung nếu trước đó chưa có.
	if han_su_dung and not bal.han_su_dung:
		bal.han_su_dung = han_su_dung
	bal.gia_tri = float(bal.so_luong) * float(bal.don_gia or 0)
	bal.flags.ignore_permissions = True
	bal.save(ignore_permissions=True)


def post_lines(voucher, lines: list[dict]) -> list[str]:
	"""Ghi các dòng của một phiếu vào sổ và cập nhật tồn theo lô.

	`so_luong` trong mỗi dòng đã mang dấu: dương là nhập, âm là xuất.
	Bỏ qua dòng đã ghi rồi (khoá theo `chung_tu_row`) nên gọi lại an toàn.
	"""
	created = []
	for line in lines:
		row_id = line["chung_tu_row"]
		if frappe.db.exists(
			"Customer Stock Ledger Entry",
			{
				"chung_tu_type": voucher.doctype,
				"chung_tu": voucher.name,
				"chung_tu_row": row_id,
			},
		):
			continue

		so_luong = float(line["so_luong"])
		don_gia = float(line.get("don_gia") or 0)
		entry = frappe.new_doc("Customer Stock Ledger Entry")
		entry.kho = voucher.kho
		entry.ngay = voucher.ngay
		entry.vat_tu = line["vat_tu"]
		entry.so_lo = line["so_lo"]
		entry.han_su_dung = line.get("han_su_dung")
		entry.so_luong = so_luong
		entry.don_gia = don_gia
		entry.gia_tri = so_luong * don_gia
		entry.chung_tu_type = voucher.doctype
		entry.chung_tu = voucher.name
		entry.chung_tu_row = row_id
		entry.flags.ignore_permissions = True
		entry.insert(ignore_permissions=True)
		created.append(entry.name)

		_apply_to_balance(
			voucher.kho, line["vat_tu"], line["so_lo"],
			line.get("han_su_dung"), so_luong, don_gia,
		)
	return created


def get_lot_balance(kho: str, vat_tu: str, so_lo: str) -> dict | None:
	return frappe.db.get_value(
		"Customer Stock Lot Balance",
		{"kho": kho, "vat_tu": vat_tu, "so_lo": so_lo},
		["name", "so_luong", "don_gia", "han_su_dung"],
		as_dict=True,
	)


def get_lot_balances(kho: str, vat_tu: str) -> list[dict]:
	"""Các lô còn tồn của một vật tư, sắp theo FEFO.

	Hạn gần nhất xuất trước; lô không có hạn dùng xếp cuối vì không thể so sánh
	với lô có hạn — để chúng lên đầu sẽ khiến hàng sắp hết hạn nằm lại kho.
	"""
	rows = frappe.get_all(
		"Customer Stock Lot Balance",
		filters={"kho": kho, "vat_tu": vat_tu, "so_luong": [">", EPS]},
		fields=["name", "so_lo", "han_su_dung", "so_luong", "don_gia"],
	)
	return sorted(
		rows,
		key=lambda r: (r["han_su_dung"] is None, r["han_su_dung"] or "", r["so_lo"]),
	)


def mark_reversed(chung_tu_type: str, chung_tu: str) -> None:
	frappe.db.set_value(
		"Customer Stock Ledger Entry",
		{"chung_tu_type": chung_tu_type, "chung_tu": chung_tu},
		"da_dao",
		1,
		update_modified=False,
	)


def rebuild_lot_balance(kho: str | None = None) -> int:
	"""Dựng lại toàn bộ tồn theo lô từ sổ.

	Lưới an toàn khi nghi ngờ cache lệch sổ. Chạy được từ dòng lệnh:
	    bench --site <site> execute miyano_portal.kho.ledger.rebuild_lot_balance
	"""
	filters = {"kho": kho} if kho else {}
	frappe.db.delete("Customer Stock Lot Balance", filters)

	entries = frappe.get_all(
		"Customer Stock Ledger Entry",
		filters=filters,
		fields=["kho", "vat_tu", "so_lo", "han_su_dung", "so_luong", "don_gia"],
		# Phải có tiebreaker: _apply_to_balance không giao hoán với don_gia, nên
		# hai dòng trùng `creation` (import di trú giữ nguyên mốc thời gian gốc,
		# hoặc hai lần insert cùng micro-giây) replay theo thứ tự tuỳ database sẽ
		# ra đơn giá khác đường ghi tăng dần. Series SKK-.######### đơn điệu.
		order_by="creation asc, name asc",
	)
	for e in entries:
		_apply_to_balance(
			e["kho"], e["vat_tu"], e["so_lo"], e["han_su_dung"],
			float(e["so_luong"]), float(e["don_gia"] or 0),
		)
	return frappe.db.count("Customer Stock Lot Balance", filters)
```

- [ ] **Step 6: Migrate và chạy test**

Run:
```bash
cd /home/hoangvietyeuem/frappe-bench-yhct
bench --site erptest.local migrate
bench --site erptest.local run-tests --app miyano_portal --module miyano_portal.tests.test_kho_ledger
```
Expected: PASS, 16 test.

- [ ] **Step 7: Commit**

```bash
cd /home/hoangvietyeuem/frappe-bench-yhct/apps/miyano_portal
git add miyano_portal/miyano_portal/doctype/customer_stock_ledger_entry miyano_portal/miyano_portal/doctype/customer_stock_lot_balance miyano_portal/kho miyano_portal/tests/test_kho_ledger.py
git commit -m "feat(kho): sổ kho ghi tăng dần + tồn theo lô, giá bám vào lô"
```

---

### Task 4: Phiếu nhập kho

**Files:**
- Create: `miyano_portal/miyano_portal/doctype/customer_stock_receipt_item/{__init__.py,customer_stock_receipt_item.json}`
- Create: `miyano_portal/miyano_portal/doctype/customer_stock_receipt/{__init__.py,customer_stock_receipt.json,customer_stock_receipt.py}`
- Create: `miyano_portal/kho/voucher.py`
- Test: `miyano_portal/tests/test_kho_receipt.py`

**Interfaces:**
- Consumes: `ledger.post_lines`, `ledger.get_lot_balance`, `ledger.mark_reversed`, `ledger.LOT_KHONG_CO` (Task 3); `seed_kho_demo()` (Task 2).
- Produces:
  - Doctype `Customer Stock Receipt` (submittable). Fields: `kho` (Link, reqd), `ngay` (Date, reqd), `loai_nhap` (Select: `Tồn đầu kỳ` / `Từ đơn hàng Miyano` / `Nhập khác` / `Phiếu đảo`, reqd), `delivery_note` (Data, read-only), `sales_order` (Data, read-only), `nguoi_giao` (Data), `chung_tu_kem` (Data), `dien_giai` (Small Text), `phieu_goc` (Link Customer Stock Receipt, read-only), `tong_tien` (Currency, read-only), `items` (Table `Customer Stock Receipt Item`, reqd).
  - `Customer Stock Receipt Item` fields: `vat_tu` (Link Customer Warehouse Item, reqd), `ten_vat_tu` (Data, read-only), `dvt` (Data, read-only), `so_lo` (Data, reqd), `han_su_dung` (Date), `so_luong` (Float, reqd), `don_gia` (Currency, reqd), `thanh_tien` (Currency, read-only), `ghi_chu` (Data).
  - `miyano_portal.kho.voucher.next_voucher_name(prefix: str, doctype: str, kho: str, ngay: str) -> str` — sinh `{prefix}-{ma_kho}-{YYYY}-{#####}` đếm theo (kho, năm). `doctype` phải nằm trong danh sách trắng `VOUCHER_DOCTYPES`.
  - `miyano_portal.kho.voucher.validate_ngay(doc) -> None` — chặn ngày phiếu trước `ngay_bat_dau` của kho.
  - `miyano_portal.kho.voucher.validate_vat_tu_thuoc_kho(doc) -> None` — chặn dòng có vật tư không thuộc `doc.kho`.

- [ ] **Step 1: Viết test thất bại**

Tạo `miyano_portal/tests/test_kho_receipt.py`:

```python
import frappe
from frappe.tests.utils import FrappeTestCase
from miyano_portal.kho import ledger
from miyano_portal.setup.seed_kho_demo import seed_kho_demo


class TestPhieuNhap(FrappeTestCase):
    def setUp(self):
        self.kho = seed_kho_demo()
        frappe.db.delete("Customer Stock Ledger Entry", {"kho": self.kho["kho_bm"]})
        frappe.db.delete("Customer Stock Lot Balance", {"kho": self.kho["kho_bm"]})

    def _phieu(self, so_luong=100, don_gia=50000, so_lo="LO-A", ngay="2026-02-01",
               vat_tu=None):
        doc = frappe.get_doc({
            "doctype": "Customer Stock Receipt",
            "kho": self.kho["kho_bm"],
            "ngay": ngay,
            "loai_nhap": "Nhập khác",
            "nguoi_giao": "Trần Văn Giao",
            "items": [{
                "vat_tu": vat_tu or self.kho["vt_bm"],
                "so_lo": so_lo,
                "han_su_dung": "2027-01-01",
                "so_luong": so_luong,
                "don_gia": don_gia,
            }],
        })
        doc.insert(ignore_permissions=True)
        return doc

    def test_naming_uses_warehouse_code_and_year(self):
        doc = self._phieu()
        self.assertTrue(doc.name.startswith("PN-BM-2026-"), doc.name)

    def test_draft_does_not_touch_ledger(self):
        self._phieu()
        self.assertEqual(
            frappe.db.count("Customer Stock Ledger Entry", {"kho": self.kho["kho_bm"]}), 0
        )

    def test_submit_posts_ledger_and_balance(self):
        doc = self._phieu()
        doc.submit()
        bal = ledger.get_lot_balance(self.kho["kho_bm"], self.kho["vt_bm"], "LO-A")
        self.assertEqual(bal["so_luong"], 100)
        self.assertEqual(doc.tong_tien, 100 * 50000)

    def test_totals_computed_on_validate(self):
        doc = self._phieu(so_luong=3, don_gia=1500)
        self.assertEqual(doc.items[0].thanh_tien, 4500)
        self.assertEqual(doc.tong_tien, 4500)
        self.assertEqual(doc.items[0].ten_vat_tu, "Găng tay y tế size M")

    def test_zero_qty_blocked(self):
        with self.assertRaises(frappe.ValidationError) as ctx:
            self._phieu(so_luong=0)
        self.assertIn("lớn hơn 0", str(ctx.exception))

    def test_negative_price_blocked(self):
        with self.assertRaises(frappe.ValidationError) as ctx:
            self._phieu(don_gia=-1)
        self.assertIn("không được âm", str(ctx.exception))

    def test_date_before_warehouse_start_blocked(self):
        with self.assertRaises(frappe.ValidationError) as ctx:
            self._phieu(ngay="2025-12-31")
        self.assertIn("Ngày bắt đầu quản lý", str(ctx.exception))

    def test_item_from_other_warehouse_blocked(self):
        with self.assertRaises(frappe.ValidationError) as ctx:
            self._phieu(vat_tu=self.kho["vt_pxn"])
        self.assertIn("không thuộc kho", str(ctx.exception))

    def test_cancel_creates_reversal_and_keeps_ledger(self):
        doc = self._phieu()
        doc.submit()
        doc.cancel()

        dao = frappe.get_all(
            "Customer Stock Receipt",
            filters={"phieu_goc": doc.name, "loai_nhap": "Phiếu đảo"},
            fields=["name", "docstatus"],
        )
        self.assertEqual(len(dao), 1)
        self.assertEqual(dao[0]["docstatus"], 1)

        # Sổ giữ nguyên dòng gốc, cộng thêm dòng đảo -> tồn về 0
        self.assertEqual(
            frappe.db.count("Customer Stock Ledger Entry", {"kho": self.kho["kho_bm"]}), 2
        )
        bal = ledger.get_lot_balance(self.kho["kho_bm"], self.kho["vt_bm"], "LO-A")
        self.assertEqual(bal["so_luong"], 0)
        self.assertTrue(all(frappe.get_all(
            "Customer Stock Ledger Entry",
            filters={"chung_tu": doc.name}, pluck="da_dao",
        )))

    def test_reversal_voucher_cannot_be_cancelled(self):
        doc = self._phieu()
        doc.submit()
        doc.cancel()
        dao_name = frappe.db.get_value(
            "Customer Stock Receipt", {"phieu_goc": doc.name}, "name"
        )
        dao = frappe.get_doc("Customer Stock Receipt", dao_name)
        with self.assertRaises(frappe.ValidationError) as ctx:
            dao.cancel()
        self.assertIn("phiếu đảo", str(ctx.exception).lower())
```

- [ ] **Step 2: Chạy test cho thất bại**

Run: `cd /home/hoangvietyeuem/frappe-bench-yhct && bench --site erptest.local run-tests --app miyano_portal --module miyano_portal.tests.test_kho_receipt`
Expected: FAIL — `DoesNotExistError: DocType Customer Stock Receipt not found`

- [ ] **Step 3: Tạo child doctype**

Tạo `miyano_portal/miyano_portal/doctype/customer_stock_receipt_item/__init__.py` (rỗng).

Tạo `.../customer_stock_receipt_item.json`:

```json
{
 "actions": [],
 "creation": "2026-08-06 00:00:00.000000",
 "doctype": "DocType",
 "editable_grid": 1,
 "engine": "InnoDB",
 "field_order": [
  "vat_tu", "ten_vat_tu", "dvt", "so_lo", "han_su_dung",
  "so_luong", "don_gia", "thanh_tien", "ghi_chu"
 ],
 "fields": [
  {"fieldname": "vat_tu", "fieldtype": "Link", "label": "Vật tư", "options": "Customer Warehouse Item", "reqd": 1, "in_list_view": 1, "columns": 2},
  {"fieldname": "ten_vat_tu", "fieldtype": "Data", "label": "Tên vật tư", "read_only": 1, "in_list_view": 1, "columns": 2},
  {"fieldname": "dvt", "fieldtype": "Data", "label": "ĐVT", "read_only": 1, "in_list_view": 1, "columns": 1},
  {"fieldname": "so_lo", "fieldtype": "Data", "label": "Số lô", "reqd": 1, "in_list_view": 1, "columns": 1},
  {"fieldname": "han_su_dung", "fieldtype": "Date", "label": "Hạn dùng", "in_list_view": 1, "columns": 1},
  {"fieldname": "so_luong", "fieldtype": "Float", "label": "Số lượng", "precision": "3", "reqd": 1, "in_list_view": 1, "columns": 1},
  {"fieldname": "don_gia", "fieldtype": "Currency", "label": "Đơn giá", "reqd": 1, "in_list_view": 1, "columns": 1},
  {"fieldname": "thanh_tien", "fieldtype": "Currency", "label": "Thành tiền", "read_only": 1, "in_list_view": 1, "columns": 2},
  {"fieldname": "ghi_chu", "fieldtype": "Data", "label": "Ghi chú"}
 ],
 "index_web_pages_for_search": 0,
 "istable": 1,
 "links": [],
 "modified": "2026-08-06 00:00:00.000000",
 "modified_by": "Administrator",
 "module": "Miyano Portal",
 "name": "Customer Stock Receipt Item",
 "owner": "Administrator",
 "permissions": [],
 "sort_field": "modified",
 "sort_order": "DESC",
 "states": []
}
```

- [ ] **Step 4: Tạo doctype phiếu nhập**

Tạo `miyano_portal/miyano_portal/doctype/customer_stock_receipt/__init__.py` (rỗng).

Tạo `.../customer_stock_receipt.json`:

```json
{
 "actions": [],
 "allow_rename": 0,
 "autoname": "",
 "creation": "2026-08-06 00:00:00.000000",
 "doctype": "DocType",
 "editable_grid": 1,
 "engine": "InnoDB",
 "is_submittable": 1,
 "field_order": [
  "kho", "ngay", "loai_nhap",
  "col_1", "nguoi_giao", "chung_tu_kem",
  "sec_ref", "delivery_note", "sales_order", "phieu_goc",
  "sec_items", "items", "tong_tien", "dien_giai", "amended_from"
 ],
 "fields": [
  {"fieldname": "kho", "fieldtype": "Link", "label": "Kho", "options": "Customer Warehouse", "reqd": 1, "search_index": 1},
  {"fieldname": "ngay", "fieldtype": "Date", "label": "Ngày", "reqd": 1, "default": "Today", "in_list_view": 1},
  {"fieldname": "loai_nhap", "fieldtype": "Select", "label": "Loại nhập", "options": "Tồn đầu kỳ\nTừ đơn hàng Miyano\nNhập khác\nPhiếu đảo", "reqd": 1, "default": "Nhập khác", "in_list_view": 1},
  {"fieldname": "col_1", "fieldtype": "Column Break"},
  {"fieldname": "nguoi_giao", "fieldtype": "Data", "label": "Người giao hàng"},
  {"fieldname": "chung_tu_kem", "fieldtype": "Data", "label": "Chứng từ kèm theo"},
  {"fieldname": "sec_ref", "fieldtype": "Section Break", "label": "Tham chiếu", "collapsible": 1},
  {"fieldname": "delivery_note", "fieldtype": "Data", "label": "Phiếu giao hàng Miyano", "read_only": 1, "search_index": 1},
  {"fieldname": "sales_order", "fieldtype": "Data", "label": "Đơn hàng Miyano", "read_only": 1},
  {"fieldname": "phieu_goc", "fieldtype": "Link", "label": "Phiếu gốc", "options": "Customer Stock Receipt", "read_only": 1},
  {"fieldname": "sec_items", "fieldtype": "Section Break", "label": "Chi tiết"},
  {"fieldname": "items", "fieldtype": "Table", "label": "Dòng vật tư", "options": "Customer Stock Receipt Item", "reqd": 1},
  {"fieldname": "tong_tien", "fieldtype": "Currency", "label": "Tổng tiền", "read_only": 1, "in_list_view": 1},
  {"fieldname": "dien_giai", "fieldtype": "Small Text", "label": "Diễn giải"},
  {"fieldname": "amended_from", "fieldtype": "Link", "label": "Amended From", "options": "Customer Stock Receipt", "read_only": 1, "no_copy": 1, "print_hide": 1}
 ],
 "index_web_pages_for_search": 0,
 "links": [],
 "modified": "2026-08-06 00:00:00.000000",
 "modified_by": "Administrator",
 "module": "Miyano Portal",
 "name": "Customer Stock Receipt",
 "owner": "Administrator",
 "permissions": [
  {"role": "System Manager", "read": 1, "write": 1, "create": 1, "delete": 1, "submit": 1, "cancel": 1, "amend": 1, "report": 1, "export": 1, "print": 1},
  {"role": "Sales Manager", "read": 1, "write": 1, "create": 1, "submit": 1, "cancel": 1, "report": 1, "print": 1},
  {"role": "Sales User", "read": 1, "report": 1, "print": 1},
  {"role": "Customer", "read": 1, "print": 1}
 ],
 "sort_field": "modified",
 "sort_order": "DESC",
 "states": [],
 "track_changes": 1
}
```

- [ ] **Step 5: Viết helper dùng chung**

Tạo `miyano_portal/kho/voucher.py`:

```python
"""Logic dùng chung của phiếu nhập và phiếu xuất kho khách hàng."""

import frappe

from miyano_portal.kho.ledger import LOT_KHONG_CO

LOAI_DAO = "Phiếu đảo"

# Chỉ hai doctype này được phép truyền vào next_voucher_name. Danh sách trắng
# vì tên doctype bị nội suy thẳng vào SQL — không bao giờ nhận từ dữ liệu
# người dùng.
VOUCHER_DOCTYPES = ("Customer Stock Receipt", "Customer Stock Issue")


def next_voucher_name(prefix: str, doctype: str, kho: str, ngay: str) -> str:
	"""Sinh số phiếu dạng PN-BM-2026-00001, đếm riêng theo từng kho và từng năm.

	Không dùng naming_series của Frappe vì series ở đó là hằng số khai báo
	trong doctype, không chèn được mã kho lấy từ bản ghi.
	"""
	if doctype not in VOUCHER_DOCTYPES:
		frappe.throw(f"Loại chứng từ kho không hợp lệ: {doctype}")
	ma_kho = frappe.db.get_value("Customer Warehouse", kho, "ma_kho")
	nam = frappe.utils.getdate(ngay).year
	tien_to = f"{prefix}-{ma_kho}-{nam}-"
	cuoi = frappe.db.sql(
		f"""select name from `tab{doctype}` where name like %s
		    order by name desc limit 1""",
		tien_to + "%",
	)
	so = int(cuoi[0][0].rsplit("-", 1)[1]) + 1 if cuoi else 1
	return f"{tien_to}{so:05d}"


def validate_ngay(doc) -> None:
	bat_dau = frappe.db.get_value("Customer Warehouse", doc.kho, "ngay_bat_dau")
	if bat_dau and frappe.utils.getdate(doc.ngay) < frappe.utils.getdate(bat_dau):
		frappe.throw(
			f"Ngày phiếu ({frappe.utils.formatdate(doc.ngay)}) không được trước "
			f"Ngày bắt đầu quản lý của kho ({frappe.utils.formatdate(bat_dau)}).",
			frappe.ValidationError,
		)


def validate_vat_tu_thuoc_kho(doc) -> None:
	"""Chặn dòng phiếu trỏ tới vật tư của kho khác.

	Đây vừa là kiểm tra dữ liệu vừa là hàng rào cách ly: nếu không có nó, một
	người dùng có thể ghi vào sổ kho của mình bằng vật tư của khách khác.
	"""
	for row in doc.items:
		kho_cua_vt = frappe.db.get_value("Customer Warehouse Item", row.vat_tu, "kho")
		if kho_cua_vt != doc.kho:
			frappe.throw(
				f"Dòng {row.idx}: vật tư {row.vat_tu} không thuộc kho {doc.kho}.",
				frappe.ValidationError,
			)


def validate_so_luong_don_gia(doc) -> None:
	for row in doc.items:
		if float(row.so_luong or 0) <= 0:
			frappe.throw(
				f"Dòng {row.idx}: số lượng phải lớn hơn 0.", frappe.ValidationError
			)
		if float(row.don_gia or 0) < 0:
			frappe.throw(
				f"Dòng {row.idx}: đơn giá không được âm.", frappe.ValidationError
			)


def fill_item_details(doc) -> None:
	"""Điền tên/ĐVT và tính thành tiền, tổng tiền."""
	tong = 0.0
	for row in doc.items:
		vt = frappe.db.get_value(
			"Customer Warehouse Item", row.vat_tu, ["ten_vat_tu", "dvt"], as_dict=True
		)
		if vt:
			row.ten_vat_tu = vt.ten_vat_tu
			row.dvt = vt.dvt
		if not row.so_lo:
			row.so_lo = LOT_KHONG_CO
		row.thanh_tien = float(row.so_luong or 0) * float(row.don_gia or 0)
		tong += row.thanh_tien
	doc.tong_tien = tong


def block_cancel_of_reversal(doc, loai_field: str) -> None:
	if doc.get(loai_field) == LOAI_DAO:
		frappe.throw(
			"Không thể huỷ một phiếu đảo. Phiếu đảo được sinh tự động để bù trừ "
			"phiếu gốc.",
			frappe.ValidationError,
		)
```

**Lưu ý cho người thực thi:** `doctype` bị nội suy thẳng vào câu SQL nên phải đi qua danh sách trắng `VOUCHER_DOCTYPES`. Cả `prefix` lẫn `doctype` đều là hằng số viết trong code của từng controller, không bao giờ đến từ dữ liệu người dùng.

- [ ] **Step 6: Viết controller phiếu nhập**

Tạo `miyano_portal/miyano_portal/doctype/customer_stock_receipt/customer_stock_receipt.py`:

```python
import frappe
from frappe.model.document import Document

from miyano_portal.kho import ledger, voucher


class CustomerStockReceipt(Document):
	def autoname(self):
		self.name = voucher.next_voucher_name(
			"PN", "Customer Stock Receipt", self.kho, self.ngay
		)

	def validate(self):
		voucher.validate_ngay(self)
		voucher.validate_vat_tu_thuoc_kho(self)
		voucher.validate_so_luong_don_gia(self)
		voucher.fill_item_details(self)

	def _he_so_dau(self) -> float:
		"""Phiếu đảo mang số lượng DƯƠNG trên chứng từ cho người đọc dễ hiểu,
		nhưng ghi vào sổ với dấu ÂM để bù trừ phiếu gốc."""
		return -1.0 if self.loai_nhap == voucher.LOAI_DAO else 1.0

	def on_submit(self):
		he_so = self._he_so_dau()
		ledger.post_lines(self, [{
			"vat_tu": r.vat_tu,
			"so_lo": r.so_lo,
			"han_su_dung": r.han_su_dung,
			"so_luong": he_so * float(r.so_luong),
			"don_gia": float(r.don_gia or 0),
			"chung_tu_row": r.name,
		} for r in self.items])

	def on_cancel(self):
		"""Huỷ phiếu KHÔNG xoá dòng sổ nào.

		Thay vào đó sinh một phiếu đảo đã submit với số lượng ngược dấu, rồi
		đánh dấu các dòng sổ gốc là đã bị đảo. Sổ vẫn cộng dồn ra đúng tồn.
		"""
		voucher.block_cancel_of_reversal(self, "loai_nhap")
		self._chan_neu_dao_lam_am_ton()
		self._tao_phieu_dao()
		ledger.mark_reversed(self.doctype, self.name)

	def _chan_neu_dao_lam_am_ton(self):
		"""Không cho huỷ nếu hàng của lô đó đã bị xuất mất rồi.

		Đảo lại sẽ kéo tồn xuống âm, mà sổ này không cho phép tồn âm.
		"""
		for r in self.items:
			bal = ledger.get_lot_balance(self.kho, r.vat_tu, r.so_lo)
			con = float(bal["so_luong"]) if bal else 0.0
			if con < float(r.so_luong) - ledger.EPS:
				frappe.throw(
					f"Không thể huỷ phiếu: lô {r.so_lo} của {r.ten_vat_tu} chỉ còn "
					f"{con:g} {r.dvt or ''} trong khi phiếu này đã nhập "
					f"{float(r.so_luong):g}. Hàng đã được xuất đi, hãy huỷ phiếu "
					f"xuất tương ứng trước.",
					frappe.ValidationError,
				)

	def _tao_phieu_dao(self):
		dao = frappe.new_doc("Customer Stock Receipt")
		dao.kho = self.kho
		dao.ngay = frappe.utils.today()
		dao.loai_nhap = voucher.LOAI_DAO
		dao.phieu_goc = self.name
		dao.dien_giai = f"Đảo phiếu {self.name}"
		for r in self.items:
			dao.append("items", {
				"vat_tu": r.vat_tu,
				"so_lo": r.so_lo,
				"han_su_dung": r.han_su_dung,
				"so_luong": r.so_luong,
				"don_gia": r.don_gia,
			})
		dao.flags.ignore_permissions = True
		dao.insert(ignore_permissions=True)
		dao.submit()
		return dao
```

- [ ] **Step 7: Migrate và chạy test**

Run:
```bash
cd /home/hoangvietyeuem/frappe-bench-yhct
bench --site erptest.local migrate
bench --site erptest.local run-tests --app miyano_portal --module miyano_portal.tests.test_kho_receipt
```
Expected: PASS, 10 test.

- [ ] **Step 8: Commit**

```bash
cd /home/hoangvietyeuem/frappe-bench-yhct/apps/miyano_portal
git add miyano_portal/miyano_portal/doctype/customer_stock_receipt miyano_portal/miyano_portal/doctype/customer_stock_receipt_item miyano_portal/kho/voucher.py miyano_portal/tests/test_kho_receipt.py
git commit -m "feat(kho): phiếu nhập kho, huỷ phiếu sinh phiếu đảo"
```

---

### Task 5: Phiếu xuất kho

**Files:**
- Create: `miyano_portal/miyano_portal/doctype/customer_stock_issue_item/{__init__.py,customer_stock_issue_item.json}`
- Create: `miyano_portal/miyano_portal/doctype/customer_stock_issue/{__init__.py,customer_stock_issue.json,customer_stock_issue.py}`
- Test: `miyano_portal/tests/test_kho_issue.py`

**Interfaces:**
- Consumes: `ledger.*`, `voucher.*` (Tasks 3, 4).
- Produces:
  - Doctype `Customer Stock Issue` (submittable). Fields: `kho`, `ngay`, `loai_xuat` (Select: `Xuất sử dụng` / `Xuất huỷ - hết hạn` / `Xuất trả lại` / `Điều chỉnh kiểm kê` / `Phiếu đảo`), `noi_nhan` (Data — **text tự do, không có master khoa/phòng**), `nguoi_nhan` (Data), `dien_giai` (Small Text), `phieu_goc` (Link), `tong_tien` (Currency, read-only), `items` (Table `Customer Stock Issue Item`).
  - `Customer Stock Issue Item` fields: `vat_tu`, `ten_vat_tu` (ro), `dvt` (ro), `so_lo` (reqd), `han_su_dung` (Date, ro), `so_luong` (Float, reqd), `don_gia` (Currency, ro), `thanh_tien` (Currency, ro), `xac_nhan_het_han` (Check), `ghi_chu` (Data).

- [ ] **Step 1: Viết test thất bại**

Tạo `miyano_portal/tests/test_kho_issue.py`:

```python
import frappe
from frappe.tests.utils import FrappeTestCase
from miyano_portal.kho import ledger
from miyano_portal.setup.seed_kho_demo import seed_kho_demo


class TestPhieuXuat(FrappeTestCase):
    def setUp(self):
        self.kho = seed_kho_demo()
        frappe.db.delete("Customer Stock Ledger Entry", {"kho": self.kho["kho_bm"]})
        frappe.db.delete("Customer Stock Lot Balance", {"kho": self.kho["kho_bm"]})
        self._nhap("LO-A", 100, 50000, han="2027-01-01")

    def _nhap(self, so_lo, so_luong, don_gia, han):
        doc = frappe.get_doc({
            "doctype": "Customer Stock Receipt",
            "kho": self.kho["kho_bm"], "ngay": "2026-02-01",
            "loai_nhap": "Nhập khác",
            "items": [{
                "vat_tu": self.kho["vt_bm"], "so_lo": so_lo, "han_su_dung": han,
                "so_luong": so_luong, "don_gia": don_gia,
            }],
        })
        doc.insert(ignore_permissions=True)
        doc.submit()
        return doc

    def _xuat(self, so_luong=10, so_lo="LO-A", xac_nhan=0, lines=None):
        items = lines or [{
            "vat_tu": self.kho["vt_bm"], "so_lo": so_lo,
            "so_luong": so_luong, "xac_nhan_het_han": xac_nhan,
        }]
        doc = frappe.get_doc({
            "doctype": "Customer Stock Issue",
            "kho": self.kho["kho_bm"], "ngay": "2026-03-01",
            "loai_xuat": "Xuất sử dụng",
            "noi_nhan": "Khoa Hồi sức tích cực",
            "nguoi_nhan": "Điều dưỡng Lan",
            "items": items,
        })
        doc.insert(ignore_permissions=True)
        return doc

    def test_naming(self):
        self.assertTrue(self._xuat().name.startswith("PX-BM-2026-"))

    def test_price_taken_from_lot_not_user(self):
        doc = self._xuat(so_luong=10)
        self.assertEqual(doc.items[0].don_gia, 50000)
        self.assertEqual(doc.items[0].thanh_tien, 500000)
        self.assertEqual(doc.items[0].han_su_dung.isoformat(), "2027-01-01")

    def test_submit_reduces_balance(self):
        self._xuat(so_luong=30).submit()
        bal = ledger.get_lot_balance(self.kho["kho_bm"], self.kho["vt_bm"], "LO-A")
        self.assertEqual(bal["so_luong"], 70)

    def test_over_issue_blocked(self):
        doc = self._xuat(so_luong=150)
        with self.assertRaises(frappe.ValidationError) as ctx:
            doc.submit()
        msg = str(ctx.exception)
        self.assertIn("LO-A", msg)
        self.assertIn("chỉ còn 100", msg)

    def test_split_rows_cannot_bypass_balance(self):
        """Tách hai dòng cùng lô để mỗi dòng đều lọt kiểm tra riêng lẻ."""
        doc = self._xuat(lines=[
            {"vat_tu": self.kho["vt_bm"], "so_lo": "LO-A", "so_luong": 60},
            {"vat_tu": self.kho["vt_bm"], "so_lo": "LO-A", "so_luong": 60},
        ])
        with self.assertRaises(frappe.ValidationError) as ctx:
            doc.submit()
        self.assertIn("chỉ còn 100", str(ctx.exception))

    def test_unknown_lot_blocked(self):
        doc = self._xuat(so_lo="LO-KHONG-CO")
        with self.assertRaises(frappe.ValidationError) as ctx:
            doc.submit()
        self.assertIn("LO-KHONG-CO", str(ctx.exception))

    def test_expired_lot_requires_confirmation(self):
        self._nhap("LO-HET-HAN", 20, 10000, han="2026-01-01")
        doc = self._xuat(so_luong=5, so_lo="LO-HET-HAN", xac_nhan=0)
        with self.assertRaises(frappe.ValidationError) as ctx:
            doc.submit()
        self.assertIn("hết hạn", str(ctx.exception))

    def test_expired_lot_allowed_when_confirmed(self):
        self._nhap("LO-HET-HAN", 20, 10000, han="2026-01-01")
        self._xuat(so_luong=5, so_lo="LO-HET-HAN", xac_nhan=1).submit()
        bal = ledger.get_lot_balance(
            self.kho["kho_bm"], self.kho["vt_bm"], "LO-HET-HAN"
        )
        self.assertEqual(bal["so_luong"], 15)

    def test_cancel_returns_stock_via_reversal(self):
        doc = self._xuat(so_luong=30)
        doc.submit()
        doc.cancel()
        bal = ledger.get_lot_balance(self.kho["kho_bm"], self.kho["vt_bm"], "LO-A")
        self.assertEqual(bal["so_luong"], 100)
        self.assertEqual(
            frappe.db.count("Customer Stock Issue", {"phieu_goc": doc.name}), 1
        )
        # Không dòng sổ nào bị xoá: 1 nhập + 1 xuất + 1 đảo
        self.assertEqual(
            frappe.db.count("Customer Stock Ledger Entry", {"kho": self.kho["kho_bm"]}), 3
        )

    def test_noi_nhan_is_free_text(self):
        doc = self._xuat()
        self.assertEqual(doc.noi_nhan, "Khoa Hồi sức tích cực")
        self.assertFalse(frappe.db.exists("DocType", "Customer Department"))
```

- [ ] **Step 2: Chạy test cho thất bại**

Run: `cd /home/hoangvietyeuem/frappe-bench-yhct && bench --site erptest.local run-tests --app miyano_portal --module miyano_portal.tests.test_kho_issue`
Expected: FAIL — `DoesNotExistError: DocType Customer Stock Issue not found`

- [ ] **Step 3: Tạo child doctype**

Tạo `miyano_portal/miyano_portal/doctype/customer_stock_issue_item/__init__.py` (rỗng).

Tạo `.../customer_stock_issue_item.json`:

```json
{
 "actions": [],
 "creation": "2026-08-06 00:00:00.000000",
 "doctype": "DocType",
 "editable_grid": 1,
 "engine": "InnoDB",
 "field_order": [
  "vat_tu", "ten_vat_tu", "dvt", "so_lo", "han_su_dung",
  "so_luong", "don_gia", "thanh_tien", "xac_nhan_het_han", "ghi_chu"
 ],
 "fields": [
  {"fieldname": "vat_tu", "fieldtype": "Link", "label": "Vật tư", "options": "Customer Warehouse Item", "reqd": 1, "in_list_view": 1, "columns": 2},
  {"fieldname": "ten_vat_tu", "fieldtype": "Data", "label": "Tên vật tư", "read_only": 1, "in_list_view": 1, "columns": 2},
  {"fieldname": "dvt", "fieldtype": "Data", "label": "ĐVT", "read_only": 1, "in_list_view": 1, "columns": 1},
  {"fieldname": "so_lo", "fieldtype": "Data", "label": "Số lô", "reqd": 1, "in_list_view": 1, "columns": 1},
  {"fieldname": "han_su_dung", "fieldtype": "Date", "label": "Hạn dùng", "read_only": 1, "in_list_view": 1, "columns": 1},
  {"fieldname": "so_luong", "fieldtype": "Float", "label": "Số lượng", "precision": "3", "reqd": 1, "in_list_view": 1, "columns": 1},
  {"fieldname": "don_gia", "fieldtype": "Currency", "label": "Đơn giá", "read_only": 1, "in_list_view": 1, "columns": 1},
  {"fieldname": "thanh_tien", "fieldtype": "Currency", "label": "Thành tiền", "read_only": 1, "in_list_view": 1, "columns": 2},
  {"fieldname": "xac_nhan_het_han", "fieldtype": "Check", "label": "Xác nhận xuất lô hết hạn", "default": "0"},
  {"fieldname": "ghi_chu", "fieldtype": "Data", "label": "Ghi chú"}
 ],
 "index_web_pages_for_search": 0,
 "istable": 1,
 "links": [],
 "modified": "2026-08-06 00:00:00.000000",
 "modified_by": "Administrator",
 "module": "Miyano Portal",
 "name": "Customer Stock Issue Item",
 "owner": "Administrator",
 "permissions": [],
 "sort_field": "modified",
 "sort_order": "DESC",
 "states": []
}
```

- [ ] **Step 4: Tạo doctype phiếu xuất**

Tạo `miyano_portal/miyano_portal/doctype/customer_stock_issue/__init__.py` (rỗng).

Tạo `.../customer_stock_issue.json`:

```json
{
 "actions": [],
 "allow_rename": 0,
 "autoname": "",
 "creation": "2026-08-06 00:00:00.000000",
 "doctype": "DocType",
 "editable_grid": 1,
 "engine": "InnoDB",
 "is_submittable": 1,
 "field_order": [
  "kho", "ngay", "loai_xuat",
  "col_1", "noi_nhan", "nguoi_nhan",
  "sec_ref", "phieu_goc",
  "sec_items", "items", "tong_tien", "dien_giai", "amended_from"
 ],
 "fields": [
  {"fieldname": "kho", "fieldtype": "Link", "label": "Kho", "options": "Customer Warehouse", "reqd": 1, "search_index": 1},
  {"fieldname": "ngay", "fieldtype": "Date", "label": "Ngày", "reqd": 1, "default": "Today", "in_list_view": 1},
  {"fieldname": "loai_xuat", "fieldtype": "Select", "label": "Loại xuất", "options": "Xuất sử dụng\nXuất huỷ - hết hạn\nXuất trả lại\nĐiều chỉnh kiểm kê\nPhiếu đảo", "reqd": 1, "default": "Xuất sử dụng", "in_list_view": 1},
  {"fieldname": "col_1", "fieldtype": "Column Break"},
  {"fieldname": "noi_nhan", "fieldtype": "Data", "label": "Nơi nhận", "description": "Ghi tự do, ví dụ: Khoa Hồi sức tích cực"},
  {"fieldname": "nguoi_nhan", "fieldtype": "Data", "label": "Người nhận"},
  {"fieldname": "sec_ref", "fieldtype": "Section Break", "label": "Tham chiếu", "collapsible": 1},
  {"fieldname": "phieu_goc", "fieldtype": "Data", "label": "Phiếu gốc", "read_only": 1, "description": "Data chứ không phải Link: phiếu đảo trỏ ngược về phiếu gốc vừa bị huỷ, mà Link tới doctype submittable đang docstatus=2 sẽ ném CancelledLinkError, rồi chính phiếu đảo lại chặn phiếu gốc huỷ qua LinkExistsError. Dùng Data cắt vòng đó mà không phải tắt ignore_links."},
  {"fieldname": "sec_items", "fieldtype": "Section Break", "label": "Chi tiết"},
  {"fieldname": "items", "fieldtype": "Table", "label": "Dòng vật tư", "options": "Customer Stock Issue Item", "reqd": 1},
  {"fieldname": "tong_tien", "fieldtype": "Currency", "label": "Tổng tiền", "read_only": 1, "in_list_view": 1},
  {"fieldname": "dien_giai", "fieldtype": "Small Text", "label": "Lý do xuất"},
  {"fieldname": "amended_from", "fieldtype": "Link", "label": "Amended From", "options": "Customer Stock Issue", "read_only": 1, "no_copy": 1, "print_hide": 1}
 ],
 "index_web_pages_for_search": 0,
 "links": [],
 "modified": "2026-08-06 00:00:00.000000",
 "modified_by": "Administrator",
 "module": "Miyano Portal",
 "name": "Customer Stock Issue",
 "owner": "Administrator",
 "permissions": [
  {"role": "System Manager", "read": 1, "write": 1, "create": 1, "delete": 1, "submit": 1, "cancel": 1, "amend": 1, "report": 1, "export": 1, "print": 1},
  {"role": "Sales Manager", "read": 1, "write": 1, "create": 1, "submit": 1, "cancel": 1, "report": 1, "print": 1},
  {"role": "Sales User", "read": 1, "report": 1, "print": 1},
  {"role": "Customer", "read": 1, "print": 1}
 ],
 "sort_field": "modified",
 "sort_order": "DESC",
 "states": [],
 "track_changes": 1
}
```

- [ ] **Step 5: Viết controller phiếu xuất**

Tạo `miyano_portal/miyano_portal/doctype/customer_stock_issue/customer_stock_issue.py`:

```python
from collections import defaultdict

import frappe
from frappe.model.document import Document

from miyano_portal.kho import ledger, voucher


class CustomerStockIssue(Document):
	def autoname(self):
		self.name = voucher.next_voucher_name(
			"PX", "Customer Stock Issue", self.kho, self.ngay
		)

	def validate(self):
		voucher.validate_ngay(self)
		voucher.validate_vat_tu_thuoc_kho(self)
		self._chan_dao_thu_cong()
		self._validate_so_luong()
		self._lay_gia_va_han_tu_lo()

	def _chan_dao_thu_cong(self):
		"""Chỉ _tao_phieu_dao mới được đặt loai_xuat = "Phiếu đảo".

		Nếu để hở, người dùng chọn "Phiếu đảo" từ dropdown là tạo được một
		phiếu XUẤT mang hệ số +1: nó CỘNG tồn thay vì trừ, đẻ ra hàng ma, đồng
		thời before_submit bỏ qua toàn bộ kiểm tra tồn và lô hết hạn. Tệ hơn,
		block_cancel_of_reversal khiến phiếu đó vĩnh viễn không huỷ được.
		"""
		if self.loai_xuat != voucher.LOAI_DAO:
			return
		# Điều kiện DUY NHẤT là cờ in-memory do _tao_phieu_dao đặt. Tuyệt đối
		# không chấp nhận `or self.phieu_goc`: phieu_goc là Data, ai cũng ghi
		# được, nên điền một chuỗi bất kỳ là thoả mệnh đề or và guard thành vô
		# dụng. Cờ này không lưu xuống database nên không giả mạo qua form được.
		if not self.flags.dang_tao_dao:
			frappe.throw(
				"Không thể tạo phiếu đảo bằng tay. Phiếu đảo chỉ được hệ thống "
				"sinh tự động khi huỷ một phiếu xuất đã ghi sổ.",
				frappe.ValidationError,
			)

	def _validate_so_luong(self):
		for row in self.items:
			if float(row.so_luong or 0) <= 0:
				frappe.throw(
					f"Dòng {row.idx}: số lượng phải lớn hơn 0.",
					frappe.ValidationError,
				)

	def _lay_gia_va_han_tu_lo(self):
		"""Đơn giá và hạn dùng của dòng xuất LUÔN lấy từ lô, không nhận từ người dùng.

		Đây là điều làm cho báo cáo nhập-xuất-tồn có cột thành tiền mà không cần
		engine định giá: giá vốn xuất chính là đơn giá đang có của lô.
		"""
		tong = 0.0
		for row in self.items:
			vt = frappe.db.get_value(
				"Customer Warehouse Item", row.vat_tu,
				["ten_vat_tu", "dvt"], as_dict=True,
			)
			if vt:
				row.ten_vat_tu = vt.ten_vat_tu
				row.dvt = vt.dvt
			# Phiếu đảo giữ NGUYÊN đơn giá đã copy từ phiếu gốc, không lấy lại
			# giá hiện hành của lô. Nếu lấy lại: nhập 100@50k, xuất 30 (sổ ghi
			# -1.500.000), nhập tiếp 100@70k (bình quân lô thành 61.764,71),
			# rồi huỷ phiếu xuất -> đảo hoàn +1.852.941. Sổ dôi ra 352.941đ
			# sinh từ hư không, và đơn giá lô kẹt sai vĩnh viễn. Số lượng vẫn
			# khớp nên không ai thấy. Phiếu nhập (Task 4) copy giá từ dòng gốc,
			# phía xuất phải làm y hệt.
			if not self.flags.dang_tao_dao:
				bal = ledger.get_lot_balance(self.kho, row.vat_tu, row.so_lo)
				row.don_gia = float(bal["don_gia"]) if bal else 0.0
				row.han_su_dung = bal["han_su_dung"] if bal else None
			row.thanh_tien = float(row.so_luong or 0) * float(row.don_gia or 0)
			tong += row.thanh_tien
		self.tong_tien = tong

	def before_submit(self):
		if self.loai_xuat != voucher.LOAI_DAO:
			self._chan_xuat_qua_ton()
			self._chan_lo_het_han_chua_xac_nhan()

	def _chan_xuat_qua_ton(self):
		"""Cộng dồn theo (vật tư, lô) TRƯỚC khi so với tồn.

		Nếu kiểm tra từng dòng riêng lẻ, người dùng tách một lần xuất thành hai
		dòng cùng lô là lọt qua cả hai lần kiểm tra mà tổng vẫn vượt tồn.
		"""
		gop = defaultdict(float)
		for row in self.items:
			gop[(row.vat_tu, row.so_lo)] += float(row.so_luong or 0)

		for (vat_tu, so_lo), can in gop.items():
			bal = ledger.get_lot_balance(self.kho, vat_tu, so_lo)
			con = float(bal["so_luong"]) if bal else 0.0
			if can > con + ledger.EPS:
				ten = frappe.db.get_value(
					"Customer Warehouse Item", vat_tu, "ten_vat_tu"
				)
				dvt = frappe.db.get_value("Customer Warehouse Item", vat_tu, "dvt")
				frappe.throw(
					f"Lô {so_lo} của {ten} chỉ còn {con:g} {dvt or ''}, "
					f"không đủ để xuất {can:g}.",
					frappe.ValidationError,
				)

	def _chan_lo_het_han_chua_xac_nhan(self):
		hom_nay = frappe.utils.getdate(frappe.utils.today())
		for row in self.items:
			if not row.han_su_dung:
				continue
			if frappe.utils.getdate(row.han_su_dung) < hom_nay and not row.xac_nhan_het_han:
				frappe.throw(
					f"Dòng {row.idx}: lô {row.so_lo} của {row.ten_vat_tu} đã hết hạn "
					f"ngày {frappe.utils.formatdate(row.han_su_dung)}. Tích ô "
					f"\"Xác nhận xuất lô hết hạn\" nếu vẫn muốn xuất.",
					frappe.ValidationError,
				)

	def on_submit(self):
		he_so = 1.0 if self.loai_xuat == voucher.LOAI_DAO else -1.0
		ledger.post_lines(self, [{
			"vat_tu": r.vat_tu,
			"so_lo": r.so_lo,
			"han_su_dung": r.han_su_dung,
			"so_luong": he_so * float(r.so_luong),
			"don_gia": float(r.don_gia or 0),
			"chung_tu_row": r.name,
		} for r in self.items])

	def before_cancel(self):
		# Chốt chặn phải nằm ở before_cancel, KHÔNG phải on_cancel: on_cancel
		# chạy sau db_update() nên docstatus=2 đã ghi xuống database rồi. Ai bắt
		# ValidationError trong cùng transaction (bench script, background job,
		# test suite) sẽ để lại phiếu đã huỷ mà lẽ ra phải bị chặn.
		voucher.block_cancel_of_reversal(self, "loai_xuat")

	def on_cancel(self):
		# Đây là tác dụng phụ, không phải kiểm tra, nên đặt sau đổi trạng thái.
		self._tao_phieu_dao()
		ledger.mark_reversed(self.doctype, self.name)

	def _tao_phieu_dao(self):
		dao = frappe.new_doc("Customer Stock Issue")
		dao.flags.dang_tao_dao = True
		dao.kho = self.kho
		dao.ngay = frappe.utils.today()
		dao.loai_xuat = voucher.LOAI_DAO
		dao.phieu_goc = self.name
		dao.noi_nhan = self.noi_nhan
		dao.nguoi_nhan = self.nguoi_nhan
		dao.dien_giai = f"Đảo phiếu {self.name}"
		for r in self.items:
			# Copy nguyên đơn giá và hạn dùng của dòng gốc: phiếu đảo phải hoàn
			# lại ĐÚNG giá trị đã trừ đi, không phải giá lô tại thời điểm huỷ.
			dao.append("items", {
				"vat_tu": r.vat_tu, "so_lo": r.so_lo,
				"so_luong": r.so_luong, "don_gia": r.don_gia,
				"han_su_dung": r.han_su_dung, "xac_nhan_het_han": 1,
			})
		dao.flags.ignore_permissions = True
		dao.insert(ignore_permissions=True)
		dao.submit()
		return dao
```

- [ ] **Step 6: Migrate và chạy test**

Run:
```bash
cd /home/hoangvietyeuem/frappe-bench-yhct
bench --site erptest.local migrate
bench --site erptest.local run-tests --app miyano_portal --module miyano_portal.tests.test_kho_issue
```
Expected: PASS, 10 test.

- [ ] **Step 7: Commit**

```bash
cd /home/hoangvietyeuem/frappe-bench-yhct/apps/miyano_portal
git add miyano_portal/miyano_portal/doctype/customer_stock_issue miyano_portal/miyano_portal/doctype/customer_stock_issue_item miyano_portal/tests/test_kho_issue.py
git commit -m "feat(kho): phiếu xuất kho, chặn xuất quá tồn, cảnh báo lô hết hạn"
```

---

### Task 6: Cách ly dữ liệu giữa các khách

**Files:**
- Create: `miyano_portal/kho/permissions.py`
- Modify: `miyano_portal/portal_context.py` (thêm `get_portal_kho`)
- Modify: `miyano_portal/hooks.py:131-143`
- Test: `miyano_portal/tests/test_kho_isolation.py`

**Interfaces:**
- Consumes: `miyano_portal.portal_context.get_allowed_customers`, `miyano_portal.permissions._is_restricted_user` (đã có).
- Produces:
  - `miyano_portal.portal_context.get_portal_kho(user: str | None = None) -> str` — tên `Customer Warehouse` của khách đang đăng nhập, ném `frappe.PermissionError` với thông báo tiếng Việt nếu chưa được mở kho.
  - `miyano_portal.kho.permissions` với: `kho_query`, `vat_tu_query`, `receipt_query`, `issue_query`, `sle_query`, `lot_query`, `kho_has_permission`, `kho_child_has_permission`.

- [ ] **Step 1: Viết test thất bại**

Tạo `miyano_portal/tests/test_kho_isolation.py`:

```python
import frappe
from frappe.tests.utils import FrappeTestCase
from miyano_portal.kho import permissions as kho_perms
from miyano_portal.portal_context import get_portal_kho
from miyano_portal.setup.seed_kho_demo import seed_kho_demo

BM_USER = "bvbm@demo.miyano"
PXN_USER = "pxnabc@demo.miyano"


class TestKhoIsolation(FrappeTestCase):
    def setUp(self):
        self.kho = seed_kho_demo()

    def tearDown(self):
        frappe.set_user("Administrator")

    def test_get_portal_kho_resolves_own_warehouse(self):
        frappe.set_user(BM_USER)
        self.assertEqual(get_portal_kho(), self.kho["kho_bm"])

    def test_get_portal_kho_blocks_user_without_warehouse(self):
        u = "orphan@demo.miyano"
        if not frappe.db.exists("User", u):
            frappe.get_doc({
                "doctype": "User", "email": u, "first_name": "Orphan",
                "user_type": "Website User", "send_welcome_email": 0,
            }).insert(ignore_permissions=True)
        frappe.set_user(u)
        with self.assertRaises(frappe.PermissionError) as ctx:
            get_portal_kho()
        self.assertIn("chưa được mở kho", str(ctx.exception))

    def test_warehouse_query_scopes_to_own_customer(self):
        cond = kho_perms.kho_query(BM_USER)
        self.assertIn("Bệnh viện Bạch Mai", cond)
        self.assertNotIn("PXN ABC", cond)

    def test_child_queries_scope_to_own_warehouse(self):
        for fn, table in [
            (kho_perms.vat_tu_query, "Customer Warehouse Item"),
            (kho_perms.receipt_query, "Customer Stock Receipt"),
            (kho_perms.issue_query, "Customer Stock Issue"),
            (kho_perms.sle_query, "Customer Stock Ledger Entry"),
            (kho_perms.lot_query, "Customer Stock Lot Balance"),
        ]:
            cond = fn(BM_USER)
            self.assertIn(f"`tab{table}`.`kho`", cond)
            self.assertIn(self.kho["kho_bm"], cond)
            self.assertNotIn(self.kho["kho_pxn"], cond)

    def test_system_user_unrestricted(self):
        self.assertEqual(kho_perms.kho_query("Administrator"), "")
        self.assertEqual(kho_perms.vat_tu_query("Administrator"), "")

    def test_user_without_customer_sees_nothing(self):
        u = "orphan@demo.miyano"
        self.assertIn("1=0", kho_perms.kho_query(u))
        self.assertIn("1=0", kho_perms.vat_tu_query(u))

    def test_has_permission_blocks_other_customers_warehouse(self):
        kho_pxn = frappe.get_doc("Customer Warehouse", self.kho["kho_pxn"])
        self.assertFalse(kho_perms.kho_has_permission(kho_pxn, user=BM_USER))
        kho_bm = frappe.get_doc("Customer Warehouse", self.kho["kho_bm"])
        self.assertTrue(kho_perms.kho_has_permission(kho_bm, user=BM_USER))

    def test_has_permission_blocks_other_customers_item(self):
        vt_pxn = frappe.get_doc("Customer Warehouse Item", self.kho["vt_pxn"])
        self.assertFalse(kho_perms.kho_child_has_permission(vt_pxn, user=BM_USER))
        vt_bm = frappe.get_doc("Customer Warehouse Item", self.kho["vt_bm"])
        self.assertTrue(kho_perms.kho_child_has_permission(vt_bm, user=BM_USER))

    def test_check_permission_raises_for_other_customer(self):
        """Đường thoát thật sự: doc.check_permission() phải chặn."""
        frappe.set_user(BM_USER)
        doc = frappe.get_doc("Customer Warehouse Item", self.kho["vt_pxn"])
        with self.assertRaises(frappe.PermissionError):
            doc.check_permission("read")

    def test_hooks_registered_for_all_six_doctypes(self):
        from miyano_portal import hooks
        for dt in [
            "Customer Warehouse", "Customer Warehouse Item",
            "Customer Stock Receipt", "Customer Stock Issue",
            "Customer Stock Ledger Entry", "Customer Stock Lot Balance",
        ]:
            self.assertIn(dt, hooks.permission_query_conditions, dt)
            self.assertIn(dt, hooks.has_permission, dt)
```

- [ ] **Step 2: Chạy test cho thất bại**

Run: `cd /home/hoangvietyeuem/frappe-bench-yhct && bench --site erptest.local run-tests --app miyano_portal --module miyano_portal.tests.test_kho_isolation`
Expected: FAIL — `ImportError: cannot import name 'permissions' from 'miyano_portal.kho'`

- [ ] **Step 3: Thêm `get_portal_kho`**

Thêm vào cuối `miyano_portal/portal_context.py`:

```python
def get_portal_kho(user: str | None = None) -> str:
    """Tên Customer Warehouse của khách đang đăng nhập.

    Mỗi khách đúng một kho, nên hàm này trả về một chuỗi chứ không phải danh
    sách. Mọi endpoint kho đều phải đi qua đây thay vì nhận tên kho từ client.
    """
    customers = get_allowed_customers(user)
    if not customers:
        raise frappe.PermissionError("Tài khoản chưa gắn với khách hàng nào.")
    kho = frappe.db.get_value(
        "Customer Warehouse",
        {"customer": ["in", customers], "active": 1},
        "name",
    )
    if not kho:
        raise frappe.PermissionError(
            "Đơn vị của bạn chưa được mở kho trên cổng. Vui lòng liên hệ "
            "nhân viên kinh doanh Miyano."
        )
    return kho


def get_allowed_khos(user: str | None = None) -> list[str]:
    """Mọi kho mà user được phép thấy. Dùng cho các hook phân quyền."""
    customers = get_allowed_customers(user)
    if not customers:
        return []
    return frappe.get_all(
        "Customer Warehouse", filters={"customer": ["in", customers]}, pluck="name"
    )
```

- [ ] **Step 4: Viết module phân quyền kho**

Tạo `miyano_portal/kho/permissions.py`:

```python
"""Cách ly dữ liệu kho giữa các khách hàng.

Kho Khách Hàng lọc theo `customer`; năm doctype còn lại đều mang field `kho`
nên lọc theo danh sách kho mà user được phép thấy.

Chỉ Website User bị ràng buộc — nhân viên Miyano ngồi desk thấy toàn bộ, giống
cơ chế đã dùng cho Sales Order ở miyano_portal/permissions.py.
"""

import frappe

from miyano_portal.permissions import _is_restricted_user
from miyano_portal.portal_context import get_allowed_customers, get_allowed_khos


def _kho_condition(table: str, user: str | None) -> str:
	user = user or frappe.session.user
	if not _is_restricted_user(user):
		return ""
	khos = get_allowed_khos(user)
	if not khos:
		return "1=0"
	joined = ", ".join(frappe.db.escape(k) for k in khos)
	return f"`tab{table}`.`kho` in ({joined})"


def kho_query(user=None) -> str:
	user = user or frappe.session.user
	if not _is_restricted_user(user):
		return ""
	customers = get_allowed_customers(user)
	if not customers:
		return "1=0"
	joined = ", ".join(frappe.db.escape(c) for c in customers)
	return f"`tabCustomer Warehouse`.`customer` in ({joined})"


def vat_tu_query(user=None) -> str:
	return _kho_condition("Customer Warehouse Item", user)


def receipt_query(user=None) -> str:
	return _kho_condition("Customer Stock Receipt", user)


def issue_query(user=None) -> str:
	return _kho_condition("Customer Stock Issue", user)


def sle_query(user=None) -> str:
	return _kho_condition("Customer Stock Ledger Entry", user)


def lot_query(user=None) -> str:
	return _kho_condition("Customer Stock Lot Balance", user)


def kho_has_permission(doc, ptype=None, user=None) -> bool:
	user = user or frappe.session.user
	if not _is_restricted_user(user):
		return True
	return doc.get("customer") in get_allowed_customers(user)


def kho_child_has_permission(doc, ptype=None, user=None) -> bool:
	user = user or frappe.session.user
	if not _is_restricted_user(user):
		return True
	return doc.get("kho") in get_allowed_khos(user)


# --- Bảng con của chứng từ -------------------------------------------------
# Hai doctype istable dưới đây KHÔNG có field `kho` của riêng chúng, nên phải
# suy kho qua chứng từ cha. Nếu bỏ sót, chúng rò rỉ toàn bộ dòng phiếu kèm đơn
# giá của mọi khách: `frappe.client.get_list` được whitelist cho Website User,
# và check_parent_permission chỉ kiểm quyền ở mức DOCTYPE của cha (role Customer
# có read nên qua), rồi db_query lọc trên chính bảng con — bảng không có điều
# kiện lọc nào. Kể cả tài khoản không gắn khách hàng nào cũng lấy được sạch bảng.


def _child_condition(table: str, parent_table: str, user: str | None) -> str:
	user = user or frappe.session.user
	if not _is_restricted_user(user):
		return ""
	khos = get_allowed_khos(user)
	if not khos:
		return "1=0"
	joined = ", ".join(frappe.db.escape(k) for k in khos)
	return (
		f"`tab{table}`.`parent` in "
		f"(select name from `tab{parent_table}` where `kho` in ({joined}))"
	)


def receipt_item_query(user=None) -> str:
	return _child_condition(
		"Customer Stock Receipt Item", "Customer Stock Receipt", user
	)


def issue_item_query(user=None) -> str:
	return _child_condition(
		"Customer Stock Issue Item", "Customer Stock Issue", user
	)


def voucher_item_readable(doc, ptype=None, user=None) -> bool:
	"""Dòng con này có thuộc kho của người gọi không.

	CHỈ dùng để THU HẸP quyền đọc, tuyệt đối không dùng để mở rộng quyền:
	với ptype khác "read", hàm này phải để mặc định của Frappe quyết định.
	Nếu trả True cho mọi ptype thì role Customer — vốn chỉ có `read` trên
	chứng từ cha — sẽ xoá được dòng của phiếu ĐÃ SUBMIT qua
	`DELETE /api/resource/...` và sửa được đơn giá trên phiếu nháp, mà
	on_submit/on_cancel của cha không hề chạy nên sổ lệch âm thầm.

	Đăng ký hàm này vào hook `has_permission` là VÔ ÍCH với doctype istable:
	frappe/permissions.py rẽ sang has_child_permission() trước khi tới hook,
	và phép suy `parent_doc` ở đó trả None cho mọi dòng con nạp rời. Chốt chặn
	thật nằm ở method has_permission() override trên controller của hai
	doctype con, vì method đó chặn được doc.check_permission() ở mọi đường
	nạp, kể cả REST v1 /api/resource/... và v2 /api/v2/document/...
	"""
	user = user or frappe.session.user
	if not _is_restricted_user(user):
		return True
	parent_type, parent = doc.get("parenttype"), doc.get("parent")
	if not parent_type or not parent:
		return False
	kho = frappe.db.get_value(parent_type, parent, "kho")
	return bool(kho) and kho in get_allowed_khos(user)
```

Controller của hai doctype con (`customer_stock_receipt_item.py`, `customer_stock_issue_item.py`)
override method `has_permission`, uỷ quyền về helper trên và **chỉ thu hẹp `read`**:

```python
import frappe
from frappe.model.document import Document

from miyano_portal.kho.permissions import voucher_item_readable


class CustomerStockReceiptItem(Document):
	def has_permission(self, permtype="read", *, debug=False, user=None):
		# Chỉ thu hẹp quyền đọc. Mọi ptype khác trả về mặc định của Frappe,
		# nếu không sẽ thành leo thang quyền: role Customer chỉ có read trên
		# chứng từ cha nhưng lại xoá/sửa được dòng con.
		#
		# CHÚ Ý (sửa ở vòng review 3): chữ ký thật của
		# Document.has_permission() trong Frappe 15.113.4 là
		# (self, permtype="read", *, debug=False, user=None) — không có
		# tham số `verbose`. Đoạn code mẫu này từng viết sai thành
		# `verbose=False`; bản đã triển khai (customer_stock_receipt_item.py)
		# dùng đúng `debug`/`user`. Tài liệu này chỉ là plan lịch sử, không
		# phải nguồn sự thật — xem code thật để biết chữ ký chính xác.
		if permtype != "read":
			return super().has_permission(permtype, debug=debug, user=user)
		if not super().has_permission(permtype, debug=debug, user=user):
			return False
		return voucher_item_readable(self, permtype, user=user)
```

- [ ] **Step 5: Đăng ký hook**

Trong `miyano_portal/hooks.py`, thay khối `permission_query_conditions` và `has_permission` (dòng 131-143) bằng:

```python
permission_query_conditions = {
	"Sales Order": "miyano_portal.permissions.sales_query",
	"Delivery Note": "miyano_portal.permissions.delivery_query",
	"Sales Invoice": "miyano_portal.permissions.invoice_query",
	"Blanket Order": "miyano_portal.permissions.blanket_query",
	# Kho khách hàng — xem miyano_portal/kho/permissions.py
	"Customer Warehouse": "miyano_portal.kho.permissions.kho_query",
	"Customer Warehouse Item": "miyano_portal.kho.permissions.vat_tu_query",
	"Customer Stock Receipt": "miyano_portal.kho.permissions.receipt_query",
	"Customer Stock Issue": "miyano_portal.kho.permissions.issue_query",
	"Customer Stock Ledger Entry": "miyano_portal.kho.permissions.sle_query",
	"Customer Stock Lot Balance": "miyano_portal.kho.permissions.lot_query",
	# Bảng con: bắt buộc phải có, xem chú thích trong kho/permissions.py
	"Customer Stock Receipt Item": "miyano_portal.kho.permissions.receipt_item_query",
	"Customer Stock Issue Item": "miyano_portal.kho.permissions.issue_item_query",
}

has_permission = {
	"Sales Order": "miyano_portal.permissions.sales_has_permission",
	"Delivery Note": "miyano_portal.permissions.generic_has_permission",
	"Sales Invoice": "miyano_portal.permissions.generic_has_permission",
	"Blanket Order": "miyano_portal.permissions.generic_has_permission",
	"Customer Warehouse": "miyano_portal.kho.permissions.kho_has_permission",
	"Customer Warehouse Item": "miyano_portal.kho.permissions.kho_child_has_permission",
	"Customer Stock Receipt": "miyano_portal.kho.permissions.kho_child_has_permission",
	"Customer Stock Issue": "miyano_portal.kho.permissions.kho_child_has_permission",
	"Customer Stock Ledger Entry": "miyano_portal.kho.permissions.kho_child_has_permission",
	"Customer Stock Lot Balance": "miyano_portal.kho.permissions.kho_child_has_permission",
	# KHÔNG đăng ký hai doctype con ở đây: hook has_permission không bao giờ
	# chạy với doctype istable (frappe/permissions.py rẽ sang
	# has_child_permission() trước). Đăng ký vào đây là dựng một chốt chặn giả
	# — người đọc sau sẽ tưởng bảng con đã được bảo vệ. Chốt thật là method
	# has_permission() override trên controller của hai doctype con.
}
```

- [ ] **Step 6: Migrate và chạy test**

Run:
```bash
cd /home/hoangvietyeuem/frappe-bench-yhct
bench --site erptest.local migrate
bench --site erptest.local run-tests --app miyano_portal --module miyano_portal.tests.test_kho_isolation
```
Expected: PASS, 10 test.

- [ ] **Step 7: Chạy lại toàn bộ test kho để chắc không vỡ gì**

Run:
```bash
cd /home/hoangvietyeuem/frappe-bench-yhct
for m in test_kho_ledger test_kho_receipt test_kho_issue test_kho_isolation; do
  bench --site erptest.local run-tests --app miyano_portal --module miyano_portal.tests.$m || echo "FAILED: $m"
done
```
Expected: cả bốn PASS, không dòng `FAILED:` nào.

- [ ] **Step 8: Commit**

```bash
cd /home/hoangvietyeuem/frappe-bench-yhct/apps/miyano_portal
git add miyano_portal/kho/permissions.py miyano_portal/portal_context.py miyano_portal/hooks.py miyano_portal/tests/test_kho_isolation.py
git commit -m "feat(kho): cách ly dữ liệu kho giữa các khách hàng"
```

---

### Task 7: API đọc kho cho portal

**Files:**
- Create: `miyano_portal/api/kho.py`
- Test: `miyano_portal/tests/test_kho_api.py`

**Interfaces:**
- Consumes: `get_portal_kho` (Task 6), `ledger.get_lot_balances` (Task 3).
- Produces — `miyano_portal.api.kho`:
  - `kho_me() -> dict` — `{"kho", "ten_kho", "ma_kho", "thu_kho", "customer", "customer_name", "ngay_bat_dau"}`
  - `kho_ton(tim=None) -> list[dict]` — mỗi vật tư một dòng: `{"vat_tu", "ma_vat_tu", "ten_vat_tu", "dvt", "item_code", "so_luong", "gia_tri", "so_lo_count", "han_gan_nhat"}`, sắp theo `ten_vat_tu`.
  - `kho_lo(vat_tu) -> list[dict]` — các lô còn tồn của một vật tư, thứ tự FEFO.

- [ ] **Step 1: Viết test thất bại**

Tạo `miyano_portal/tests/test_kho_api.py`:

```python
import frappe
from frappe.tests.utils import FrappeTestCase
from miyano_portal.api import kho as kho_api
from miyano_portal.setup.seed_kho_demo import seed_kho_demo

BM_USER = "bvbm@demo.miyano"


class TestKhoApi(FrappeTestCase):
    def setUp(self):
        self.kho = seed_kho_demo()
        frappe.db.delete("Customer Stock Ledger Entry", {"kho": self.kho["kho_bm"]})
        frappe.db.delete("Customer Stock Lot Balance", {"kho": self.kho["kho_bm"]})
        doc = frappe.get_doc({
            "doctype": "Customer Stock Receipt",
            "kho": self.kho["kho_bm"], "ngay": "2026-02-01",
            "loai_nhap": "Nhập khác",
            "items": [
                {"vat_tu": self.kho["vt_bm"], "so_lo": "LO-A",
                 "han_su_dung": "2027-01-01", "so_luong": 100, "don_gia": 50000},
                {"vat_tu": self.kho["vt_bm"], "so_lo": "LO-B",
                 "han_su_dung": "2026-09-01", "so_luong": 40, "don_gia": 50000},
            ],
        })
        doc.insert(ignore_permissions=True)
        doc.submit()

    def tearDown(self):
        frappe.set_user("Administrator")

    def test_kho_me_returns_own_warehouse(self):
        frappe.set_user(BM_USER)
        out = kho_api.kho_me()
        self.assertEqual(out["kho"], self.kho["kho_bm"])
        self.assertEqual(out["customer"], "Bệnh viện Bạch Mai")
        self.assertEqual(out["ma_kho"], "BM")

    def test_kho_ton_aggregates_lots_per_item(self):
        frappe.set_user(BM_USER)
        rows = kho_api.kho_ton()
        row = next(r for r in rows if r["vat_tu"] == self.kho["vt_bm"])
        self.assertEqual(row["so_luong"], 140)
        self.assertEqual(row["gia_tri"], 140 * 50000)
        self.assertEqual(row["so_lo_count"], 2)
        self.assertEqual(str(row["han_gan_nhat"]), "2026-09-01")

    def test_kho_ton_never_leaks_other_customers(self):
        frappe.set_user(BM_USER)
        rows = kho_api.kho_ton()
        self.assertTrue(all(r["vat_tu"] != self.kho["vt_pxn"] for r in rows))

    def test_kho_lo_is_fefo_ordered(self):
        frappe.set_user(BM_USER)
        lots = kho_api.kho_lo(self.kho["vt_bm"])
        self.assertEqual([l["so_lo"] for l in lots], ["LO-B", "LO-A"])

    def test_kho_lo_rejects_other_customers_item(self):
        frappe.set_user(BM_USER)
        with self.assertRaises(frappe.PermissionError):
            kho_api.kho_lo(self.kho["vt_pxn"])

    def test_search_filters_by_name_and_code(self):
        frappe.set_user(BM_USER)
        self.assertTrue(kho_api.kho_ton(tim="Găng"))
        self.assertEqual(kho_api.kho_ton(tim="không-có-gì-cả"), [])
```

- [ ] **Step 2: Chạy test cho thất bại**

Run: `cd /home/hoangvietyeuem/frappe-bench-yhct && bench --site erptest.local run-tests --app miyano_portal --module miyano_portal.tests.test_kho_api`
Expected: FAIL — `ImportError: cannot import name 'kho' from 'miyano_portal.api'`

- [ ] **Step 3: Viết API**

Tạo `miyano_portal/api/kho.py`:

```python
"""Endpoint kho cho cổng khách hàng.

Nguyên tắc bất di bất dịch: KHÔNG endpoint nào nhận tên kho hay tên khách hàng
từ client. Kho luôn được suy ra từ phiên đăng nhập qua get_portal_kho(), và mọi
tham số do client gửi (ví dụ `vat_tu`) đều phải kiểm tra là thuộc kho đó.
"""

import frappe

from miyano_portal.kho import ledger
from miyano_portal.portal_context import get_portal_kho


def _vat_tu_cua_kho(vat_tu: str, kho: str) -> str:
	"""Xác nhận một vật tư do client gửi lên đúng là của kho người gọi.

	frappe.get_doc KHÔNG tự chạy hook has_permission ở build này (xem
	api/portal.py:351), nên không thể tin vào việc nạp doc là đủ an toàn.
	"""
	if frappe.db.get_value("Customer Warehouse Item", vat_tu, "kho") != kho:
		raise frappe.PermissionError("Vật tư không thuộc kho của đơn vị bạn.")
	return vat_tu


@frappe.whitelist()
def kho_me() -> dict:
	kho = get_portal_kho()
	row = frappe.db.get_value(
		"Customer Warehouse", kho,
		["name", "ten_kho", "ma_kho", "thu_kho", "customer", "ngay_bat_dau"],
		as_dict=True,
	)
	return {
		"kho": row.name,
		"ten_kho": row.ten_kho,
		"ma_kho": row.ma_kho,
		"thu_kho": row.thu_kho or "",
		"customer": row.customer,
		"customer_name": frappe.db.get_value(
			"Customer", row.customer, "customer_name"
		),
		"ngay_bat_dau": row.ngay_bat_dau,
	}


@frappe.whitelist()
def kho_ton(tim=None) -> list:
	"""Tồn hiện tại, gộp các lô về một dòng cho mỗi vật tư."""
	kho = get_portal_kho()
	lots = frappe.get_all(
		"Customer Stock Lot Balance",
		filters={"kho": kho, "so_luong": [">", ledger.EPS]},
		fields=["vat_tu", "so_lo", "han_su_dung", "so_luong", "gia_tri"],
	)

	gop = {}
	for lot in lots:
		g = gop.setdefault(lot["vat_tu"], {
			"vat_tu": lot["vat_tu"], "so_luong": 0.0, "gia_tri": 0.0,
			"so_lo_count": 0, "han_gan_nhat": None,
		})
		g["so_luong"] += float(lot["so_luong"])
		g["gia_tri"] += float(lot["gia_tri"] or 0)
		g["so_lo_count"] += 1
		han = lot["han_su_dung"]
		if han and (g["han_gan_nhat"] is None or han < g["han_gan_nhat"]):
			g["han_gan_nhat"] = han

	out = []
	for vat_tu, g in gop.items():
		vt = frappe.db.get_value(
			"Customer Warehouse Item", vat_tu,
			["ma_vat_tu", "ten_vat_tu", "dvt", "item_code"], as_dict=True,
		)
		if not vt:
			continue
		if tim:
			hay = f"{vt.ma_vat_tu} {vt.ten_vat_tu}".lower()
			if tim.lower() not in hay:
				continue
		out.append({**g, **{
			"ma_vat_tu": vt.ma_vat_tu, "ten_vat_tu": vt.ten_vat_tu,
			"dvt": vt.dvt, "item_code": vt.item_code or "",
		}})
	return sorted(out, key=lambda r: r["ten_vat_tu"])


@frappe.whitelist()
def kho_lo(vat_tu) -> list:
	"""Các lô còn tồn của một vật tư, thứ tự FEFO."""
	kho = get_portal_kho()
	_vat_tu_cua_kho(vat_tu, kho)
	return ledger.get_lot_balances(kho, vat_tu)
```

- [ ] **Step 4: Chạy test**

Run: `cd /home/hoangvietyeuem/frappe-bench-yhct && bench --site erptest.local run-tests --app miyano_portal --module miyano_portal.tests.test_kho_api`
Expected: PASS, 6 test.

- [ ] **Step 5: Chạy toàn bộ test của app để chắc không vỡ tính năng cũ**

Run: `cd /home/hoangvietyeuem/frappe-bench-yhct && bench --site erptest.local run-tests --app miyano_portal`
Expected: PASS toàn bộ, kể cả các test có sẵn (`test_isolation`, `test_order_place`, `test_e2e_flow`, ...).

- [ ] **Step 6: Commit**

```bash
cd /home/hoangvietyeuem/frappe-bench-yhct/apps/miyano_portal
git add miyano_portal/api/kho.py miyano_portal/tests/test_kho_api.py
git commit -m "feat(kho): API đọc tồn kho cho cổng khách hàng"
```

---

## Định nghĩa hoàn thành Phase 1

- [ ] Sáu doctype tồn tại và migrate sạch trên `erptest.local`
- [ ] `bench --site erptest.local run-tests --app miyano_portal` xanh toàn bộ
- [ ] Nhập rồi xuất cho ra tồn đúng cả số lượng lẫn thành tiền
- [ ] Huỷ phiếu không xoá dòng sổ nào, tồn trở về đúng
- [ ] Khách A không đọc được bất kỳ dữ liệu kho nào của khách B qua mọi đường
- [ ] `rebuild_lot_balance` dựng lại đúng tồn từ sổ

## Sang phase sau

P2 import tồn đầu kỳ · P3 FEFO trên giao diện + in phiếu · P4 hook Delivery Note ·
P5 báo cáo N-X-T · P6 màn hình desk cho Miyano. Mỗi phase một plan riêng, viết khi
phase trước đã xanh.
