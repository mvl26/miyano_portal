# Quản lý vật tư theo thiết bị và khoa phòng — Kế hoạch thi công

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Thêm chiều **thiết bị (máy)** vào module kho khách hàng của `miyano_portal`, để báo cáo trên cổng trả lời được "vật tư này nhập về bao nhiêu, cấp phát cho máy nào, khoa nào".

**Architecture:** Một master mới `Customer Equipment` treo vào `Customer`; một bảng con "máy dùng được" trên `Customer Warehouse Item` (danh mục tương thích, **không** dùng để cộng số); một field `thiet_bi` trên **dòng** phiếu xuất — đây là nơi duy nhất có số lượng thật theo máy. Sổ kho **không đổi schema**; báo cáo join `Customer Stock Ledger Entry.chung_tu_row` → `Customer Stock Issue Item.thiet_bi`.

**Tech Stack:** Frappe v15 (Python 3.11), ERPNext, Vue 3.4 + vue-router 4.3 + Vite 6 (SPA ở `frontend/`), MariaDB `utf8mb4_unicode_ci`, `FrappeTestCase`.

**Spec:** `docs/superpowers/specs/2026-08-27-thiet-bi-vat-tu-khoa-phong-design.md`

## Global Constraints

Mọi task đều ngầm mang các ràng buộc sau. Đọc hết trước khi làm task đầu tiên.

1. **KHÔNG sửa schema `Customer Stock Ledger Entry` và `Customer Stock Lot Balance`.** BR-CP4. Báo cáo join qua `chung_tu_row` (là **docname dòng con** — đã xác minh ở `kho/ledger.py:181,308`).
2. **KHÔNG thêm DocPerm cho role `Customer`** trên bất kỳ doctype kho nào, kể cả doctype mới. Đây là lớp cách ly **chịu lực**. Gặp `PermissionError` thì sửa bằng `ignore_permissions=True` **sau khi** đã tự kiểm tenant tường minh — đúng khuôn `kho/khoa_phong.py:184`. Xem `kho/permissions.py` docstring đầu file.
3. **Mọi endpoint suy kho/khách/khoa từ phiên**, không nhận từ client: `get_portal_kho()`, `get_portal_customer()`, `portal_context.khoa_phong_cho_don()`. Định danh do client gửi phải qua guard kiểu `_vat_tu_cua_kho()` trước khi `get_doc` chạm vào. `frappe.get_doc` **không** tự chạy `has_permission` ở build này.
4. **Dropdown máy trên SPA chỉ gọi `kho_thiet_bi_list`**, tuyệt đối không dùng Link field chuẩn / `frappe.desk.search.search_link` (lỗ đã biết, chưa vá của site này).
5. **Tên field tiếng Việt không dấu, nhãn tiếng Việt có dấu.** Tên doctype tiếng Anh. Đúng lệ module kho.
6. **Hai lớp lọc khi đếm cấp phát**, không được gộp làm một: `da_dao = 0` ở tầng sổ **và** `loai_xuat = "Xuất sử dụng"` ở tầng phiếu.
7. **Gộp theo docname**, không gộp theo tên. `ten_vat_tu` / `ten_thiet_bi` không duy nhất.
8. **So sánh chuỗi dựa vào collation** `utf8mb4_unicode_ci` (đã sẵn không dấu, không phân biệt hoa thường) — không thêm cột chuẩn hoá.
9. **Không backfill.** Dữ liệu cũ không chứa tên máy ở đâu cả (đo 27/08: `nhom` chứa nhóm hàng, `noi_nhan` chứa tên khoa).
10. **Không cần patch dữ liệu.** Cả 5 doctype đụng tới đều do app này sở hữu, nên `bench --site <site> migrate` tự đồng bộ cột mới. *(Spec §10 viết "patch thêm field đi theo patches.txt như thường lệ" — không đúng cho doctype app-owned; sửa lại ở đây. Cảnh báo `Patch Log` trong spec chỉ áp dụng nếu về sau có ai thêm patch dữ liệu thật.)*
11. **Lệnh chạy test:**
    - một module: `bench --site erptest.local run-tests --app miyano_portal --module miyano_portal.tests.test_<ten>`
    - toàn bộ: `bench --site erptest.local run-tests --app miyano_portal`
    - Chạy từ `/home/hoangvietyeuem/frappe-bench-yhct`.
    - **Test chập chờn đã biết:** `ReadTimeout` ngẫu nhiên khi ba bench cùng chạy trên một máy hết RAM. Gặp thì chạy lại đúng module đó trước khi kết luận có hồi quy.
12. **Dữ liệu test tự tạo, tiền tố riêng.** Không mượn khách hàng thật trên site (`Himedic`, `Bệnh viện Bạch Mai`) — đã có tiền lệ vỡ test. Dùng tiền tố `ZZTB` cho bộ test này.
12b. **Hàm dọn của test PHẢI lọc theo khách hàng của chính nó.** `erptest.local` là site làm việc thật, mang dữ liệu demo của nhiều bệnh viện và của các bộ test khác. Một vòng `frappe.get_all(dt, pluck="name")` **không lọc** rồi `delete_doc` sẽ dọn sạch site, và chỉ lộ ra ở lần chạy test tiếp theo của người khác. Mọi `_don()` trong kế hoạch này đều lọc theo `customer`/`kho` của bộ test.
13. **Sau mỗi task: commit.** Nhánh làm việc: `feat/thiet-bi-vat-tu` (tách từ `docs/thiet-bi-vat-tu`).

---

## File Structure

**Tạo mới (backend)**

| File | Trách nhiệm |
|---|---|
| `miyano_portal/miyano_portal/doctype/customer_equipment/customer_equipment.json` | Schema master thiết bị |
| `miyano_portal/miyano_portal/doctype/customer_equipment/customer_equipment.py` | Validate: chuẩn hoá mã, chống trùng, chặn xoá khi đã dùng |
| `miyano_portal/miyano_portal/doctype/customer_warehouse_item_equipment/*.json` | Bảng con "máy dùng được" |
| `miyano_portal/kho/thiet_bi.py` | Logic danh mục máy: `list_rows`, `save`, `tao_nhanh`, `gan_vao_vat_tu` |

**Sửa (backend)**

| File | Sửa gì |
|---|---|
| `.../customer_warehouse_item/customer_warehouse_item.json` | Thêm section + field `may_su_dung` (Table) |
| `.../customer_stock_issue_item/customer_stock_issue_item.json` | Thêm `thiet_bi` |
| `.../customer_stock_issue/customer_stock_issue.json` | Thêm `thiet_bi_mac_dinh` |
| `.../customer_stock_issue/customer_stock_issue.py` | BR-TB-1/2/3/4/5 |
| `.../customer_warehouse/customer_warehouse.json` + `.py` | Cờ `bat_buoc_thiet_bi` + mốc + `_ghi_moc_bat_buoc_thiet_bi()` |
| `miyano_portal/kho/permissions.py` | `thiet_bi_query`, `vat_tu_may_item_query` |
| `miyano_portal/hooks.py` | Đăng ký hai hàm trên |
| `miyano_portal/api/kho.py` | 5 endpoint mới + guard `_thiet_bi_cua_khach` + sửa `kho_phieu_xuat_save` |
| `miyano_portal/kho/reports.py` | `bao_cao_thiet_bi_rows`, `tieu_thu_theo_may_rows`, mở rộng `bao_cao_cap_phat_rows` |
| `miyano_portal/kho/desk_reports.py` | `tieu_thu_theo_thiet_bi_rows` |
| `miyano_portal/kho/dong_phieu.py` | Cột "Mã máy" trong file mẫu + khi đọc |
| `miyano_portal/kho/vat_tu.py` | Nhận `may_su_dung` khi save |

**Frontend**

| File | Trách nhiệm |
|---|---|
| `frontend/src/views/ThietBiList.vue` | Màn danh mục máy |
| `frontend/src/components/ThietBiModal.vue` | Form đầy đủ |
| `frontend/src/components/ThietBiPicker.vue` | Dropdown máy + nút tạo nhanh (dùng chung 2 nơi) |
| `frontend/src/components/ThietBiQuickCreate.vue` | Form 6 ô |
| `frontend/src/views/PhieuXuatDetail.vue` | Cột Máy + ô Máy mặc định + cảnh báo BR-TB-2 |
| `frontend/src/components/VatTuModal.vue` | Ô "Máy sử dụng" |
| `frontend/src/views/BaoCaoThietBi.vue` | Báo cáo mới |
| `frontend/src/router.js`, `src/App.vue`, `src/api.js` | Route + nav + hàm gọi |

**Test** — mỗi file một chủ đề, không nhồi chung:
`tests/test_tb1_doctype.py` · `test_tb2_phieu_xuat.py` · `test_tb3_bat_buoc.py` · `test_tb4_cach_ly.py` · `test_tb5_endpoint.py` · `test_tb6_bao_cao.py`

---

## Task 1: Doctype `Customer Equipment`

**Files:**
- Create: `miyano_portal/miyano_portal/doctype/customer_equipment/customer_equipment.json`
- Create: `miyano_portal/miyano_portal/doctype/customer_equipment/customer_equipment.py`
- Create: `miyano_portal/miyano_portal/doctype/customer_equipment/__init__.py` (rỗng)
- Test: `miyano_portal/tests/test_tb1_doctype.py`

**Interfaces:**
- Consumes: `Customer`, `Customer Department` (đã có).
- Produces: doctype `Customer Equipment` với các field `customer`, `ma_thiet_bi`, `ten_thiet_bi`, `khoa_phong`, `hang_san_xuat`, `xuat_xu`, `model`, `so_serial`, `nam_san_xuat`, `ngay_lap_dat`, `active`, `ghi_chu`. Autoname `TBK-.#####`. Lớp `CustomerEquipment(Document)`.

- [ ] **Step 1: Viết test đỏ**

Tạo `miyano_portal/tests/test_tb1_doctype.py`:

```python
"""Master thiết bị — chuẩn hoá mã, chống trùng, ràng buộc khoa cùng bệnh viện.

Dùng khách hàng ZZTB RIÊNG của bộ test này, không mượn khách thật trên site
(tiền lệ vỡ test: xem docs/CHANGELOG-khac-phuc-BA-v2.md dòng 302).
"""

import frappe
from frappe.tests.utils import FrappeTestCase

KHACH = "ZZTB Benh Vien"


class TestThietBiDoctype(FrappeTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		self._don()
		self.addCleanup(self._don)
		frappe.get_doc({
			"doctype": "Customer", "customer_name": KHACH,
			"customer_type": "Company", "customer_group": "All Customer Groups",
			"territory": "All Territories",
		}).insert(ignore_permissions=True)
		self.kp = frappe.get_doc({
			"doctype": "Customer Department", "customer": KHACH,
			"ten_khoa_phong": "ZZTB Khoa Xet nghiem", "ma_khoa": "ZZTBXN",
		}).insert(ignore_permissions=True)

	def _don(self):
		for dt in ("Customer Equipment", "Customer Department"):
			for r in frappe.get_all(dt, filters={"customer": KHACH}, pluck="name"):
				frappe.delete_doc(dt, r, force=True, ignore_permissions=True)
		if frappe.db.exists("Customer", KHACH):
			frappe.delete_doc("Customer", KHACH, force=True, ignore_permissions=True)

	def _may(self, **kw):
		du_lieu = {
			"doctype": "Customer Equipment", "customer": KHACH,
			"ma_thiet_bi": "xn500-01", "ten_thiet_bi": "Máy XN-500",
		}
		du_lieu.update(kw)
		return frappe.get_doc(du_lieu).insert(ignore_permissions=True)

	def test_ma_duoc_viet_hoa_va_cat_khoang_trang(self):
		may = self._may(ma_thiet_bi="  xn500-01  ")
		self.assertEqual(may.ma_thiet_bi, "XN500-01")

	def test_thieu_ten_bi_chan(self):
		with self.assertRaises(frappe.ValidationError):
			self._may(ten_thiet_bi="   ")

	def test_thieu_ma_bi_chan(self):
		with self.assertRaises(frappe.ValidationError):
			self._may(ma_thiet_bi="")

	def test_ma_trung_trong_cung_benh_vien_bi_chan(self):
		self._may()
		with self.assertRaises(frappe.ValidationError):
			self._may(ten_thiet_bi="Máy khác")

	def test_ten_trung_khac_dau_khac_hoa_thuong_bi_chan(self):
		self._may(ten_thiet_bi="Máy Xét nghiệm")
		with self.assertRaises(frappe.ValidationError):
			self._may(ma_thiet_bi="XN500-02", ten_thiet_bi="may xet nghiem")

	def test_khoa_phong_khac_benh_vien_bi_chan(self):
		khach_khac = frappe.get_doc({
			"doctype": "Customer", "customer_name": "ZZTB Benh Vien Khac",
			"customer_type": "Company", "customer_group": "All Customer Groups",
			"territory": "All Territories",
		}).insert(ignore_permissions=True)
		self.addCleanup(
			frappe.delete_doc, "Customer", khach_khac.name, force=True, ignore_permissions=True
		)
		kp_khac = frappe.get_doc({
			"doctype": "Customer Department", "customer": khach_khac.name,
			"ten_khoa_phong": "ZZTB Khoa La",
		}).insert(ignore_permissions=True)
		self.addCleanup(
			frappe.delete_doc, "Customer Department", kp_khac.name,
			force=True, ignore_permissions=True,
		)
		with self.assertRaises(frappe.ValidationError):
			self._may(khoa_phong=kp_khac.name)

	def test_khoa_phong_de_trong_la_may_dung_chung(self):
		may = self._may()
		self.assertIsNone(may.khoa_phong)

	def test_mac_dinh_dang_hoat_dong(self):
		self.assertEqual(self._may().active, 1)
```

- [ ] **Step 2: Chạy test, xác nhận ĐỎ**

```bash
cd /home/hoangvietyeuem/frappe-bench-yhct
bench --site erptest.local run-tests --app miyano_portal --module miyano_portal.tests.test_tb1_doctype
```

Kỳ vọng: FAIL — `DoesNotExistError: DocType Customer Equipment not found`.

- [ ] **Step 3: Tạo JSON doctype**

`miyano_portal/miyano_portal/doctype/customer_equipment/customer_equipment.json`:

```json
{
 "actions": [],
 "allow_rename": 0,
 "autoname": "TBK-.#####",
 "creation": "2026-08-27 00:00:00.000000",
 "doctype": "DocType",
 "editable_grid": 1,
 "engine": "InnoDB",
 "field_order": [
  "customer", "ma_thiet_bi", "ten_thiet_bi", "khoa_phong", "active",
  "col_1", "hang_san_xuat", "xuat_xu", "model", "so_serial",
  "nam_san_xuat", "ngay_lap_dat",
  "sec_1", "ghi_chu"
 ],
 "fields": [
  {"fieldname": "customer", "fieldtype": "Link", "label": "Khách hàng", "options": "Customer", "reqd": 1, "search_index": 1},
  {"fieldname": "ma_thiet_bi", "fieldtype": "Data", "label": "Mã máy", "reqd": 1, "length": 40, "in_list_view": 1, "description": "Nhập phiếu hàng loạt bằng Excel khớp máy theo mã này — không để trống"},
  {"fieldname": "ten_thiet_bi", "fieldtype": "Data", "label": "Tên máy", "reqd": 1, "in_list_view": 1},
  {"fieldname": "khoa_phong", "fieldtype": "Link", "label": "Khoa phòng đặt máy", "options": "Customer Department", "search_index": 1, "description": "Để trống = máy dùng chung, không thuộc khoa nào"},
  {"fieldname": "active", "fieldtype": "Check", "label": "Đang hoạt động", "default": "1"},
  {"fieldname": "col_1", "fieldtype": "Column Break"},
  {"fieldname": "hang_san_xuat", "fieldtype": "Data", "label": "Hãng sản xuất"},
  {"fieldname": "xuat_xu", "fieldtype": "Data", "label": "Xuất xứ"},
  {"fieldname": "model", "fieldtype": "Data", "label": "Model"},
  {"fieldname": "so_serial", "fieldtype": "Data", "label": "Số serial"},
  {"fieldname": "nam_san_xuat", "fieldtype": "Int", "label": "Năm sản xuất"},
  {"fieldname": "ngay_lap_dat", "fieldtype": "Date", "label": "Ngày lắp đặt"},
  {"fieldname": "sec_1", "fieldtype": "Section Break"},
  {"fieldname": "ghi_chu", "fieldtype": "Small Text", "label": "Ghi chú"}
 ],
 "index_web_pages_for_search": 0,
 "links": [],
 "modified": "2026-08-27 00:00:00.000000",
 "modified_by": "Administrator",
 "module": "Miyano Portal",
 "name": "Customer Equipment",
 "owner": "Administrator",
 "permissions": [
  {"role": "System Manager", "read": 1, "write": 1, "create": 1, "delete": 1, "report": 1, "export": 1},
  {"role": "Sales Manager", "read": 1, "write": 1, "create": 1, "report": 1},
  {"role": "Sales User", "read": 1, "report": 1}
 ],
 "sort_field": "modified",
 "sort_order": "DESC",
 "states": [],
 "title_field": "ten_thiet_bi",
 "track_changes": 1
}
```

> Ba role trên là **nhân viên Miyano ngồi Desk**. **Không** có dòng nào cho role `Customer` — cố ý, xem Global Constraint 2.

- [ ] **Step 4: Viết controller**

`miyano_portal/miyano_portal/doctype/customer_equipment/customer_equipment.py`:

```python
import frappe
from frappe.model.document import Document


class CustomerEquipment(Document):
	"""Master thiết bị của khách hàng (máy xét nghiệm, máy thở...).

	Treo vào `Customer` chứ KHÔNG vào `Customer Warehouse`: khoa phòng đã
	chuyển chủ sở hữu sang bệnh viện từ 18/08, và máy đặt ở khoa chứ không
	đặt ở kho. Bệnh viện chưa mở kho trên cổng vẫn khai được máy.
	"""

	def validate(self):
		self._chuan_hoa()
		self._chan_trung_ma()
		self._chan_trung_ten()
		self._chan_khoa_khac_benh_vien()

	def _chuan_hoa(self):
		self.ma_thiet_bi = (self.ma_thiet_bi or "").strip().upper()
		self.ten_thiet_bi = (self.ten_thiet_bi or "").strip()
		if not self.ma_thiet_bi:
			frappe.throw("Thiếu Mã máy.", frappe.ValidationError)
		if not self.ten_thiet_bi:
			frappe.throw("Thiếu Tên máy.", frappe.ValidationError)
		self.khoa_phong = self.khoa_phong or None

	def _chan_trung_ma(self):
		if frappe.db.exists("Customer Equipment", {
			"customer": self.customer, "ma_thiet_bi": self.ma_thiet_bi,
			"name": ["!=", self.name or ""],
		}):
			frappe.throw(
				f'Đơn vị này đã có máy mang mã "{self.ma_thiet_bi}".',
				frappe.ValidationError,
			)

	def _chan_trung_ten(self):
		"""So sánh dựa THẲNG vào collation utf8mb4_unicode_ci của CSDL — đã
		sẵn không dấu và không phân biệt hoa thường (spec 18/08 đã đo bằng
		truy vấn thật). Không thêm cột chuẩn hoá cho một phép so duy nhất."""
		trung = frappe.db.sql(
			"""select name from `tabCustomer Equipment`
			   where customer=%s and ten_thiet_bi=%s and name!=%s limit 1""",
			(self.customer, self.ten_thiet_bi, self.name or ""),
		)
		if trung:
			frappe.throw(
				f'Đơn vị này đã có máy tên "{self.ten_thiet_bi}" '
				f"(mã {frappe.db.get_value('Customer Equipment', trung[0][0], 'ma_thiet_bi')}).",
				frappe.ValidationError,
			)

	def _chan_khoa_khac_benh_vien(self):
		if not self.khoa_phong:
			return
		if frappe.db.get_value("Customer Department", self.khoa_phong, "customer") != self.customer:
			frappe.throw(
				"Khoa phòng được chọn không thuộc đơn vị này.", frappe.ValidationError
			)

	def on_trash(self):
		"""BR-TB-9 — máy đã xuất hiện trên phiếu xuất thì không xoá được.

		Xoá sẽ làm mọi dòng phiếu cũ trỏ vào một Link chết, và báo cáo theo
		máy của các kỳ trước im lặng đổi số. Hướng người dùng sang bỏ tích
		`active` — máy biến khỏi dropdown mà số liệu cũ còn nguyên.
		"""
		if frappe.db.exists("Customer Stock Issue Item", {"thiet_bi": self.name}):
			frappe.throw(
				f'Máy "{self.ten_thiet_bi}" đã được dùng trên phiếu xuất nên '
				"không xoá được. Hãy bỏ tích \"Đang hoạt động\" để ngừng dùng — "
				"số liệu các kỳ trước sẽ được giữ nguyên.",
				frappe.ValidationError,
			)
```

Và `__init__.py` rỗng.

- [ ] **Step 5: Migrate rồi chạy test, xác nhận XANH**

```bash
cd /home/hoangvietyeuem/frappe-bench-yhct
bench --site erptest.local migrate
bench --site erptest.local run-tests --app miyano_portal --module miyano_portal.tests.test_tb1_doctype
```

Kỳ vọng: 8 test PASS. *(`on_trash` chưa có test ở task này vì `Customer Stock Issue Item.thiet_bi` chưa tồn tại — ca đó nằm ở Task 3.)*

- [ ] **Step 6: Commit**

```bash
cd /home/hoangvietyeuem/frappe-bench-yhct/apps/miyano_portal
git add miyano_portal/miyano_portal/doctype/customer_equipment miyano_portal/tests/test_tb1_doctype.py
git commit -m "feat(kho): doctype Customer Equipment — master thiết bị theo bệnh viện"
```

---

## Task 2: Bảng con "Máy sử dụng" trên vật tư

**Files:**
- Create: `miyano_portal/miyano_portal/doctype/customer_warehouse_item_equipment/customer_warehouse_item_equipment.json`
- Create: `.../customer_warehouse_item_equipment/__init__.py` (rỗng)
- Modify: `miyano_portal/miyano_portal/doctype/customer_warehouse_item/customer_warehouse_item.json`
- Modify: `miyano_portal/miyano_portal/doctype/customer_warehouse_item/customer_warehouse_item.py`
- Modify: `miyano_portal/kho/vat_tu.py`
- Test: `miyano_portal/tests/test_tb1_doctype.py` (thêm lớp)

**Interfaces:**
- Consumes: `Customer Equipment` (Task 1).
- Produces: field `Customer Warehouse Item.may_su_dung` (Table → `Customer Warehouse Item Equipment`, mỗi dòng có `thiet_bi`); `vat_tu.save()` nhận khoá `may_su_dung` là danh sách docname máy.

- [ ] **Step 1: Viết test đỏ**

Thêm vào cuối `miyano_portal/tests/test_tb1_doctype.py`:

```python
class TestVatTuMaySuDung(FrappeTestCase):
	"""Bảng "Máy sử dụng" là DANH MỤC TƯƠNG THÍCH, không phải số liệu."""

	def setUp(self):
		frappe.set_user("Administrator")
		self._don()
		self.addCleanup(self._don)
		frappe.get_doc({
			"doctype": "Customer", "customer_name": KHACH,
			"customer_type": "Company", "customer_group": "All Customer Groups",
			"territory": "All Territories",
		}).insert(ignore_permissions=True)
		self.kho = frappe.get_doc({
			"doctype": "Customer Warehouse", "customer": KHACH,
			"ten_kho": "ZZTB Kho", "ma_kho": "ZZTB",
		}).insert(ignore_permissions=True)
		self.may = frappe.get_doc({
			"doctype": "Customer Equipment", "customer": KHACH,
			"ma_thiet_bi": "XN500-01", "ten_thiet_bi": "Máy XN-500",
		}).insert(ignore_permissions=True)

	def _don(self):
		for dt in ("Customer Warehouse Item", "Customer Equipment", "Customer Warehouse"):
			flt = {"kho": ["like", "%"]} if dt != "Customer Equipment" else {"customer": KHACH}
			if dt == "Customer Warehouse":
				flt = {"customer": KHACH}
			elif dt == "Customer Warehouse Item":
				khos = frappe.get_all("Customer Warehouse", filters={"customer": KHACH}, pluck="name")
				flt = {"kho": ["in", khos or [""]]}
			for r in frappe.get_all(dt, filters=flt, pluck="name"):
				frappe.delete_doc(dt, r, force=True, ignore_permissions=True)
		if frappe.db.exists("Customer", KHACH):
			frappe.delete_doc("Customer", KHACH, force=True, ignore_permissions=True)

	def _vat_tu(self, **kw):
		du_lieu = {
			"doctype": "Customer Warehouse Item", "kho": self.kho.name,
			"ma_vat_tu": "ZZTB-HC1", "ten_vat_tu": "Hoá chất ZZTB", "dvt": "Hộp",
		}
		du_lieu.update(kw)
		return frappe.get_doc(du_lieu).insert(ignore_permissions=True)

	def test_gan_duoc_nhieu_may(self):
		may2 = frappe.get_doc({
			"doctype": "Customer Equipment", "customer": KHACH,
			"ma_thiet_bi": "XN500-02", "ten_thiet_bi": "Máy XN-500 số 2",
		}).insert(ignore_permissions=True)
		vt = self._vat_tu(may_su_dung=[
			{"thiet_bi": self.may.name}, {"thiet_bi": may2.name},
		])
		self.assertEqual(
			{r.thiet_bi for r in vt.may_su_dung}, {self.may.name, may2.name}
		)

	def test_bang_trong_la_vat_tu_dung_chung(self):
		self.assertEqual(self._vat_tu().may_su_dung, [])

	def test_may_cua_benh_vien_khac_bi_chan(self):
		khach2 = frappe.get_doc({
			"doctype": "Customer", "customer_name": "ZZTB Benh Vien Khac",
			"customer_type": "Company", "customer_group": "All Customer Groups",
			"territory": "All Territories",
		}).insert(ignore_permissions=True)
		self.addCleanup(
			frappe.delete_doc, "Customer", khach2.name, force=True, ignore_permissions=True
		)
		may_la = frappe.get_doc({
			"doctype": "Customer Equipment", "customer": khach2.name,
			"ma_thiet_bi": "LA-01", "ten_thiet_bi": "Máy lạ",
		}).insert(ignore_permissions=True)
		self.addCleanup(
			frappe.delete_doc, "Customer Equipment", may_la.name,
			force=True, ignore_permissions=True,
		)
		with self.assertRaises(frappe.ValidationError):
			self._vat_tu(may_su_dung=[{"thiet_bi": may_la.name}])

	def test_gan_trung_mot_may_hai_lan_bi_gop(self):
		vt = self._vat_tu(may_su_dung=[
			{"thiet_bi": self.may.name}, {"thiet_bi": self.may.name},
		])
		self.assertEqual(len(vt.may_su_dung), 1)
```

- [ ] **Step 2: Chạy test, xác nhận ĐỎ**

```bash
cd /home/hoangvietyeuem/frappe-bench-yhct
bench --site erptest.local run-tests --app miyano_portal --module miyano_portal.tests.test_tb1_doctype
```

Kỳ vọng: 4 test mới FAIL — `Customer Warehouse Item` chưa có field `may_su_dung`.

- [ ] **Step 3: Tạo bảng con**

`.../customer_warehouse_item_equipment/customer_warehouse_item_equipment.json`:

```json
{
 "actions": [],
 "creation": "2026-08-27 00:00:00.000000",
 "doctype": "DocType",
 "editable_grid": 1,
 "engine": "InnoDB",
 "field_order": ["thiet_bi"],
 "fields": [
  {"fieldname": "thiet_bi", "fieldtype": "Link", "label": "Máy", "options": "Customer Equipment", "reqd": 1, "in_list_view": 1}
 ],
 "index_web_pages_for_search": 0,
 "istable": 1,
 "links": [],
 "modified": "2026-08-27 00:00:00.000000",
 "modified_by": "Administrator",
 "module": "Miyano Portal",
 "name": "Customer Warehouse Item Equipment",
 "owner": "Administrator",
 "permissions": [],
 "sort_field": "modified",
 "sort_order": "DESC",
 "states": []
}
```

- [ ] **Step 4: Gắn vào vật tư**

Trong `customer_warehouse_item.json`, thêm hai tên vào cuối `field_order`:

```json
"sec_may", "may_su_dung"
```

và hai field vào mảng `fields`:

```json
{"fieldname": "sec_may", "fieldtype": "Section Break", "label": "Máy sử dụng"},
{"fieldname": "may_su_dung", "fieldtype": "Table", "label": "Máy sử dụng", "options": "Customer Warehouse Item Equipment", "description": "Danh mục máy chạy được vật tư này. Dùng để lọc dropdown lúc xuất và tra ngược — KHÔNG dùng để cộng số lượng. Để trống = vật tư dùng chung."}
```

- [ ] **Step 5: Validate trong controller vật tư**

Thêm vào `CustomerWarehouseItem.validate()` (gọi cuối cùng):

```python
	def _validate_may_su_dung(self):
		"""Máy gán vào vật tư phải cùng bệnh viện với kho của vật tư, và
		không lặp. Lặp không sai về số liệu (bảng này không tham gia phép
		cộng nào) nhưng làm dropdown hiện một máy hai lần."""
		if not self.get("may_su_dung"):
			return
		customer = frappe.db.get_value("Customer Warehouse", self.kho, "customer")
		da_gap, giu = set(), []
		for row in self.may_su_dung:
			if not row.thiet_bi or row.thiet_bi in da_gap:
				continue
			chu = frappe.db.get_value("Customer Equipment", row.thiet_bi, "customer")
			if chu != customer:
				frappe.throw(
					"Máy được chọn không thuộc đơn vị của kho này.",
					frappe.ValidationError,
				)
			da_gap.add(row.thiet_bi)
			giu.append(row)
		self.may_su_dung = giu
```

- [ ] **Step 6: Cho `vat_tu.save()` nhận `may_su_dung`**

Trong `miyano_portal/kho/vat_tu.py`, ngay trước khối `doc.insert(...)`/`doc.save(...)` của `save()`:

```python
	# `may_su_dung` là DANH MỤC TƯƠNG THÍCH, không phải số liệu — sửa được
	# bất cứ lúc nào kể cả khi vật tư đã có phát sinh sổ kho (khác
	# TRUONG_KHOA): đổi danh sách máy không quy đổi ngược con số nào.
	if "may_su_dung" in du_lieu:
		doc.set("may_su_dung", [
			{"thiet_bi": m} for m in (du_lieu.get("may_su_dung") or []) if m
		])
```

- [ ] **Step 7: Migrate rồi chạy test, xác nhận XANH**

```bash
cd /home/hoangvietyeuem/frappe-bench-yhct
bench --site erptest.local migrate
bench --site erptest.local run-tests --app miyano_portal --module miyano_portal.tests.test_tb1_doctype
```

Kỳ vọng: 12 test PASS.

- [ ] **Step 8: Commit**

```bash
cd /home/hoangvietyeuem/frappe-bench-yhct/apps/miyano_portal
git add miyano_portal/miyano_portal/doctype/customer_warehouse_item_equipment \
        miyano_portal/miyano_portal/doctype/customer_warehouse_item \
        miyano_portal/kho/vat_tu.py miyano_portal/tests/test_tb1_doctype.py
git commit -m "feat(kho): bảng Máy sử dụng trên vật tư — danh mục tương thích, không cộng số"
```

---

## Task 3: `thiet_bi` trên dòng phiếu xuất + BR-TB-1/2/4/5

**Files:**
- Modify: `.../customer_stock_issue_item/customer_stock_issue_item.json`
- Modify: `.../customer_stock_issue/customer_stock_issue.json`
- Modify: `.../customer_stock_issue/customer_stock_issue.py`
- Test: `miyano_portal/tests/test_tb2_phieu_xuat.py`

**Interfaces:**
- Consumes: `Customer Equipment` (Task 1), `Customer Warehouse Item.may_su_dung` (Task 2).
- Produces: `Customer Stock Issue Item.thiet_bi`; `Customer Stock Issue.thiet_bi_mac_dinh`; danh sách cảnh báo mềm trong `doc.flags.canh_bao_thiet_bi` (list[str]) để endpoint đọc lại và trả về SPA.

- [ ] **Step 1: Viết test đỏ**

Tạo `miyano_portal/tests/test_tb2_phieu_xuat.py`. Nền dùng lại khuôn dựng kho + vật tư + tồn đầu của `tests/test_e4_ncc.py`; nếu file đó có helper dùng chung thì import, nếu không thì viết `_nen()` trong file này:

```python
"""Máy trên DÒNG phiếu xuất — BR-TB-1/2/4/5.

`thiet_bi_mac_dinh` ở đầu phiếu là TIỆN ÍCH NHẬP LIỆU, không ghi sổ và
không báo cáo nào được đọc nó — test cuối file khẳng định điều đó.
"""

import frappe
from frappe.tests.utils import FrappeTestCase

KHACH = "ZZTB2 Benh Vien"


class TestMayTrenPhieuXuat(FrappeTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		self._don()
		self.addCleanup(self._don)
		frappe.get_doc({
			"doctype": "Customer", "customer_name": KHACH,
			"customer_type": "Company", "customer_group": "All Customer Groups",
			"territory": "All Territories",
		}).insert(ignore_permissions=True)
		self.kho = frappe.get_doc({
			"doctype": "Customer Warehouse", "customer": KHACH,
			"ten_kho": "ZZTB2 Kho", "ma_kho": "ZZTB2",
			"ngay_bat_dau": frappe.utils.add_days(frappe.utils.today(), -30),
		}).insert(ignore_permissions=True)
		self.kp_a = self._khoa("ZZTB2 Khoa A", "ZZTB2A")
		self.kp_b = self._khoa("ZZTB2 Khoa B", "ZZTB2B")
		self.may_a = self._may("XN500-01", "Máy XN-500", self.kp_a.name)
		self.may_b = self._may("XN500-02", "Máy XN-500 số 2", None)
		self.may_khoa_a = self.may_a
		self.may_la = self._may_benh_vien_khac()
		self.vat_tu = frappe.get_doc({
			"doctype": "Customer Warehouse Item", "kho": self.kho.name,
			"ma_vat_tu": "ZZTB2-HC1", "ten_vat_tu": "Hoá chất ZZTB2", "dvt": "Hộp",
		}).insert(ignore_permissions=True)
		self.lo = "LO-ZZTB2"
		nhap = frappe.get_doc({
			"doctype": "Customer Stock Receipt", "kho": self.kho.name,
			"ngay": frappe.utils.add_days(frappe.utils.today(), -7),
			"loai_nhap": "Nhập mua",
			"items": [{
				"vat_tu": self.vat_tu.name, "so_lo": self.lo, "so_luong": 100,
				"don_gia": 50000,
			}],
		}).insert(ignore_permissions=True)
		nhap.submit()

	def _khoa(self, ten, ma):
		return frappe.get_doc({
			"doctype": "Customer Department", "customer": KHACH,
			"ten_khoa_phong": ten, "ma_khoa": ma,
		}).insert(ignore_permissions=True)

	def _may(self, ma, ten, khoa_phong):
		return frappe.get_doc({
			"doctype": "Customer Equipment", "customer": KHACH,
			"ma_thiet_bi": ma, "ten_thiet_bi": ten, "khoa_phong": khoa_phong,
		}).insert(ignore_permissions=True)

	def _may_benh_vien_khac(self):
		"""Máy CÓ THẬT nhưng của bệnh viện khác — dùng cho ca BR-TB-1. Phải là
		máy thật chứ không phải docname bịa, nếu không ca test chỉ chứng minh
		được "docname không tồn tại thì lỗi", vốn là chuyện khác."""
		if not frappe.db.exists("Customer", "ZZTB2 Benh Vien Khac"):
			frappe.get_doc({
				"doctype": "Customer", "customer_name": "ZZTB2 Benh Vien Khac",
				"customer_type": "Company", "customer_group": "All Customer Groups",
				"territory": "All Territories",
			}).insert(ignore_permissions=True)
		return frappe.get_doc({
			"doctype": "Customer Equipment", "customer": "ZZTB2 Benh Vien Khac",
			"ma_thiet_bi": "LA-01", "ten_thiet_bi": "Máy lạ",
		}).insert(ignore_permissions=True)

	def _xuat(self, thiet_bi=None, khoa_phong=None, loai_xuat="Xuất sử dụng",
	          thiet_bi_mac_dinh=None, submit=True):
		"""Lập một phiếu xuất một dòng. `submit=False` để giữ phiếu ở nháp cho
		các ca cần tạo trước / bật cờ sau."""
		doc = frappe.get_doc({
			"doctype": "Customer Stock Issue", "kho": self.kho.name,
			"ngay": frappe.utils.today(), "loai_xuat": loai_xuat,
			"khoa_phong": khoa_phong or self.kp_a.name,
			"thiet_bi_mac_dinh": thiet_bi_mac_dinh,
			"items": [{
				"vat_tu": self.vat_tu.name, "so_lo": self.lo,
				"so_luong": 2, "thiet_bi": thiet_bi,
			}],
		}).insert(ignore_permissions=True)
		if submit:
			doc.submit()
		return doc

	def _don(self):
		"""Dọn CHỈ dữ liệu của hai khách hàng ZZTB2 của bộ test này.

		TUYỆT ĐỐI không `frappe.get_all(dt, pluck="name")` không lọc rồi xoá —
		erptest.local là site làm việc thật, có dữ liệu demo của nhiều bệnh
		viện và các bộ test khác. Một vòng xoá không lọc sẽ dọn sạch site và
		chỉ lộ ra ở lần chạy test tiếp theo của người khác.
		"""
		khach = [KHACH, "ZZTB2 Benh Vien Khac"]
		khos = frappe.get_all(
			"Customer Warehouse", filters={"customer": ["in", khach]}, pluck="name"
		) or [""]
		# Thứ tự xoá đi từ phụ thuộc ra gốc: chứng từ → sổ → danh mục → kho.
		theo_kho = (
			"Customer Stock Issue", "Customer Stock Receipt",
			"Customer Stock Ledger Entry", "Customer Stock Lot Balance",
			"Customer Warehouse Item",
		)
		for dt in theo_kho:
			for r in frappe.get_all(dt, filters={"kho": ["in", khos]}, pluck="name"):
				frappe.delete_doc(dt, r, force=True, ignore_permissions=True)
		for dt in ("Customer Equipment", "Customer Department", "Customer Warehouse"):
			for r in frappe.get_all(dt, filters={"customer": ["in", khach]}, pluck="name"):
				frappe.delete_doc(dt, r, force=True, ignore_permissions=True)
		for c in khach:
			if frappe.db.exists("Customer", c):
				frappe.delete_doc("Customer", c, force=True, ignore_permissions=True)

	def test_may_cua_benh_vien_khac_bi_chan(self):
		"""BR-TB-1."""
		with self.assertRaises(frappe.ValidationError):
			self._xuat(thiet_bi=self.may_la.name)

	def test_may_ngoai_danh_muc_cua_vat_tu_chi_canh_bao(self):
		"""BR-TB-2 — KHÔNG chặn. Danh mục có thể khai thiếu; chặn cứng làm
		tắc việc xuất hàng. Cảnh báo đi kèm để SPA hiện nút "Gắn vào vật tư"."""
		self.vat_tu.set("may_su_dung", [{"thiet_bi": self.may_a.name}])
		self.vat_tu.save(ignore_permissions=True)
		doc = self._xuat(thiet_bi=self.may_b.name)
		self.assertEqual(doc.items[0].thiet_bi, self.may_b.name)
		self.assertTrue(doc.flags.canh_bao_thiet_bi)

	def test_may_trong_danh_muc_khong_canh_bao(self):
		self.vat_tu.set("may_su_dung", [{"thiet_bi": self.may_a.name}])
		self.vat_tu.save(ignore_permissions=True)
		doc = self._xuat(thiet_bi=self.may_a.name)
		self.assertFalse(doc.flags.get("canh_bao_thiet_bi"))

	def test_bang_may_trong_thi_chon_may_nao_cung_duoc(self):
		doc = self._xuat(thiet_bi=self.may_b.name)
		self.assertFalse(doc.flags.get("canh_bao_thiet_bi"))

	def test_khoa_cua_may_khac_khoa_tren_phieu_chi_canh_bao(self):
		"""BR-TB-4 — máy mới chuyển khoa, hoặc khoa mượn máy, đều là thật."""
		doc = self._xuat(thiet_bi=self.may_khoa_a.name, khoa_phong=self.kp_b.name)
		self.assertEqual(doc.docstatus, 1)
		self.assertTrue(doc.flags.canh_bao_thiet_bi)

	def test_may_da_tat_bi_chan_tren_phieu_moi(self):
		"""BR-TB-5."""
		self.may_a.active = 0
		self.may_a.save(ignore_permissions=True)
		with self.assertRaises(frappe.ValidationError):
			self._xuat(thiet_bi=self.may_a.name)

	def test_may_da_tat_khong_lam_vo_phieu_cu(self):
		doc = self._xuat(thiet_bi=self.may_a.name)
		self.may_a.active = 0
		self.may_a.save(ignore_permissions=True)
		doc.reload()
		self.assertEqual(doc.items[0].thiet_bi, self.may_a.name)

	def test_khong_xoa_duoc_may_da_dung(self):
		"""BR-TB-9 — hoàn tất ca test bỏ dở ở Task 1."""
		self._xuat(thiet_bi=self.may_a.name)
		with self.assertRaises(frappe.ValidationError):
			frappe.delete_doc(
				"Customer Equipment", self.may_a.name, force=True, ignore_permissions=True
			)

	def test_thiet_bi_mac_dinh_khong_ghi_xuong_dong(self):
		"""Đầu phiếu chỉ là tiện ích nhập liệu của SPA. Server KHÔNG tự điền
		xuống dòng — nếu server cũng điền thì một phiếu đổi máy mặc định sau
		khi các dòng đã chọn tay sẽ ra hai con số khác nhau tuỳ báo cáo nào chạy."""
		doc = self._xuat(thiet_bi=None, thiet_bi_mac_dinh=self.may_a.name)
		self.assertIsNone(doc.items[0].thiet_bi)
```

- [ ] **Step 2: Chạy test, xác nhận ĐỎ**

```bash
cd /home/hoangvietyeuem/frappe-bench-yhct
bench --site erptest.local run-tests --app miyano_portal --module miyano_portal.tests.test_tb2_phieu_xuat
```

Kỳ vọng: FAIL — `Customer Stock Issue Item` chưa có `thiet_bi`.

- [ ] **Step 3: Thêm field vào hai JSON**

`customer_stock_issue_item.json` — thêm `"thiet_bi"` vào `field_order` ngay sau `"dvt"`, và:

```json
{"fieldname": "thiet_bi", "fieldtype": "Link", "label": "Máy sử dụng", "options": "Customer Equipment", "in_list_view": 1}
```

`customer_stock_issue.json` — thêm `"thiet_bi_mac_dinh"` vào `field_order` ngay sau `"khoa_phong"`, và:

```json
{"fieldname": "thiet_bi_mac_dinh", "fieldtype": "Link", "label": "Máy mặc định", "options": "Customer Equipment", "description": "Chỉ để điền nhanh xuống các dòng đang trống trên giao diện. KHÔNG ghi sổ, KHÔNG báo cáo nào đọc ô này."}
```

- [ ] **Step 4: Viết validate**

Thêm vào `CustomerStockIssue`, gọi từ `validate()`:

```python
	def _validate_thiet_bi(self):
		"""BR-TB-1/2/4/5. Chạy trên MỌI đường ghi (endpoint cổng lẫn Desk),
		cùng lý do đã ghi ở `_validate_khoa_phong_thuoc_kho`.

		Cảnh báo mềm gom vào `flags.canh_bao_thiet_bi` chứ không `msgprint`
		thẳng: endpoint cổng đọc lại flag này rồi trả về cho SPA để hiện
		đúng nút "Gắn máy này vào vật tư" — `msgprint` không đi qua được
		lớp fetch của cổng (SPA không phải Desk).
		"""
		self.flags.canh_bao_thiet_bi = []
		may_tren_phieu = {r.thiet_bi for r in self.items if r.thiet_bi}
		if self.thiet_bi_mac_dinh:
			may_tren_phieu.add(self.thiet_bi_mac_dinh)
		if not may_tren_phieu:
			return

		customer = frappe.db.get_value("Customer Warehouse", self.kho, "customer")
		thong_tin = {
			r["name"]: r for r in frappe.get_all(
				"Customer Equipment", filters={"name": ["in", list(may_tren_phieu)]},
				fields=["name", "customer", "active", "ten_thiet_bi", "khoa_phong"],
			)
		}

		for may in may_tren_phieu:
			info = thong_tin.get(may)
			# BR-TB-1 — kể cả máy không tồn tại cũng rơi vào đây: thông điệp
			# GIỐNG HỆT trường hợp máy của bệnh viện khác, để không lộ ra
			# rằng một docname có thật hay không.
			if not info or info["customer"] != customer:
				frappe.throw(
					"Máy được chọn không thuộc đơn vị bạn.", frappe.PermissionError
				)

		if self.is_new() or self.docstatus == 0:
			for may in may_tren_phieu:  # BR-TB-5
				if not thong_tin[may]["active"]:
					frappe.throw(
						f'Máy "{thong_tin[may]["ten_thiet_bi"]}" đã ngừng hoạt động, '
						"không chọn cho phiếu mới được.",
						frappe.ValidationError,
					)

		for row in self.items:  # BR-TB-2
			if not row.thiet_bi:
				continue
			danh_muc = {
				r[0] for r in frappe.db.sql(
					"""select thiet_bi from `tabCustomer Warehouse Item Equipment`
					   where parent=%s""", (row.vat_tu,)
				)
			}
			if danh_muc and row.thiet_bi not in danh_muc:
				self.flags.canh_bao_thiet_bi.append(
					f'Dòng {row.idx}: máy "{thong_tin[row.thiet_bi]["ten_thiet_bi"]}" '
					f"chưa có trong danh mục máy của vật tư {row.ten_vat_tu or row.vat_tu}."
				)

		if self.khoa_phong:  # BR-TB-4
			for may in may_tren_phieu:
				kp_may = thong_tin[may]["khoa_phong"]
				if kp_may and kp_may != self.khoa_phong:
					self.flags.canh_bao_thiet_bi.append(
						f'Máy "{thong_tin[may]["ten_thiet_bi"]}" đang đặt ở khoa khác '
						"với khoa nhận trên phiếu."
					)
```

- [ ] **Step 5: Chạy test, xác nhận XANH**

```bash
cd /home/hoangvietyeuem/frappe-bench-yhct
bench --site erptest.local migrate
bench --site erptest.local run-tests --app miyano_portal --module miyano_portal.tests.test_tb2_phieu_xuat
bench --site erptest.local run-tests --app miyano_portal --module miyano_portal.tests.test_tb1_doctype
```

Kỳ vọng: cả hai module PASS (test_tb1 nay có đủ 12, ca `on_trash` đã được phủ ở test_tb2).

- [ ] **Step 6: Commit**

```bash
cd /home/hoangvietyeuem/frappe-bench-yhct/apps/miyano_portal
git add miyano_portal/miyano_portal/doctype/customer_stock_issue \
        miyano_portal/miyano_portal/doctype/customer_stock_issue_item \
        miyano_portal/tests/test_tb2_phieu_xuat.py
git commit -m "feat(kho): máy trên dòng phiếu xuất — BR-TB-1/2/4/5"
```

---

## Task 4: Cờ `bat_buoc_thiet_bi` (BR-TB-3)

**Files:**
- Modify: `.../customer_warehouse/customer_warehouse.json`
- Modify: `.../customer_warehouse/customer_warehouse.py`
- Modify: `.../customer_stock_issue/customer_stock_issue.py`
- Test: `miyano_portal/tests/test_tb3_bat_buoc.py`

**Interfaces:**
- Produces: `Customer Warehouse.bat_buoc_thiet_bi` (Check), `.bat_buoc_thiet_bi_tu` (Datetime, read-only); `CustomerWarehouse._ghi_moc_bat_buoc_thiet_bi()`; `CustomerStockIssue._chan_thieu_thiet_bi()`.

**Đây là task dễ làm sai nhất.** Đọc `customer_stock_issue.py::_chan_thieu_khoa_phong()` (dòng ~128) và `customer_warehouse.py::_ghi_moc_bat_buoc_khoa_phong()` (dòng ~55) **trước khi viết một dòng nào** — hành vi phải giống hệt, kể cả phần tự lành.

- [ ] **Step 1: Viết test đỏ**

`miyano_portal/tests/test_tb3_bat_buoc.py`:

```python
"""BR-TB-3 — cờ bắt buộc chọn máy, sao y cơ chế mốc thời gian của khoa phòng.

Chốt chặn so THỜI ĐIỂM TẠO PHIẾU với MỐC BẬT CỜ, không so thời điểm ghi sổ:
phiếu nháp tạo trước khi bật cờ vẫn ghi sổ được (tránh khoá tồn đọng).
"""

import frappe
from frappe.tests.utils import FrappeTestCase


class TestBatBuocThietBi(FrappeTestCase):
	def test_co_tat_thi_khong_bat_buoc(self):
		doc = self._phieu_nhap_lieu(thiet_bi=None)
		doc.submit()
		self.assertEqual(doc.docstatus, 1)

	def test_bat_co_thi_phieu_tao_sau_bi_chan(self):
		self._bat_co()
		doc = self._phieu_nhap_lieu(thiet_bi=None)
		with self.assertRaises(frappe.ValidationError):
			doc.submit()

	def test_phieu_nhap_tao_truoc_khi_bat_co_van_ghi_so_duoc(self):
		doc = self._phieu_nhap_lieu(thiet_bi=None)   # tạo TRƯỚC
		self._bat_co()                                # bật SAU
		doc.submit()
		self.assertEqual(doc.docstatus, 1)

	def test_co_bat_ma_moc_rong_thi_tu_lanh(self):
		"""Cờ bật qua db.set_value (patch rollout hàng loạt) không đi qua
		validate() nên không có mốc. Fail-closed ở đây sẽ ĐÓNG BĂNG mọi
		phiếu nháp đang mở ở MỌI kho — đúng cái E8 sinh ra để tránh."""
		doc = self._phieu_nhap_lieu(thiet_bi=None)
		frappe.db.set_value("Customer Warehouse", self.kho.name, "bat_buoc_thiet_bi", 1)
		frappe.db.set_value("Customer Warehouse", self.kho.name, "bat_buoc_thiet_bi_tu", None)
		doc.submit()
		self.assertEqual(doc.docstatus, 1)
		self.assertIsNotNone(
			frappe.db.get_value("Customer Warehouse", self.kho.name, "bat_buoc_thiet_bi_tu")
		)

	def test_chi_ap_cho_xuat_su_dung(self):
		self._bat_co()
		doc = self._phieu_nhap_lieu(thiet_bi=None, loai_xuat="Xuất huỷ - hết hạn")
		doc.submit()
		self.assertEqual(doc.docstatus, 1)

	def test_phieu_dao_khong_bi_chan(self):
		"""on_cancel KHÔNG được phép ném lỗi — bật cờ giữa lúc xuất và lúc
		huỷ không được làm sập thao tác huỷ."""
		doc = self._phieu_nhap_lieu(thiet_bi=None)
		doc.submit()
		self._bat_co()
		doc.cancel()
		self.assertEqual(doc.docstatus, 2)
```

- [ ] **Step 2: Chạy test, xác nhận ĐỎ**

```bash
cd /home/hoangvietyeuem/frappe-bench-yhct
bench --site erptest.local run-tests --app miyano_portal --module miyano_portal.tests.test_tb3_bat_buoc
```

Kỳ vọng: FAIL — chưa có field `bat_buoc_thiet_bi`.

- [ ] **Step 3: Thêm hai field vào `customer_warehouse.json`**

Thêm `"bat_buoc_thiet_bi", "bat_buoc_thiet_bi_tu"` vào `field_order` ngay sau `bat_buoc_khoa_phong_tu`, và:

```json
{"fieldname": "bat_buoc_thiet_bi", "fieldtype": "Check", "label": "Bắt buộc chọn máy khi Xuất sử dụng", "default": "0", "description": "BR-TB-3 — chỉ áp cho phiếu \"Xuất sử dụng\" TẠO SAU thời điểm bật cờ này (xem Bắt buộc từ). Phiếu nháp tạo trước đó vẫn ghi sổ được không cần máy."},
{"fieldname": "bat_buoc_thiet_bi_tu", "fieldtype": "Datetime", "label": "Bắt buộc chọn máy từ", "read_only": 1, "description": "Hệ tự ghi thời điểm cờ bên trái chuyển từ tắt sang bật — không sửa tay được."}
```

- [ ] **Step 4: Ghi mốc trong `CustomerWarehouse`**

Thêm hàm, và gọi nó ngay sau `self._ghi_moc_bat_buoc_khoa_phong()` trong `validate()`:

```python
	def _ghi_moc_bat_buoc_thiet_bi(self):
		"""BR-TB-3 — sao y `_ghi_moc_bat_buoc_khoa_phong()`. NƠI DUY NHẤT
		ghi vào `bat_buoc_thiet_bi_tu`. Bắt cả hai ca: kho cũ bật cờ lần
		đầu, và kho mới tạo với cờ đã bật sẵn."""
		if not frappe.utils.cint(self.bat_buoc_thiet_bi):
			return
		truoc = 0 if self.is_new() else frappe.utils.cint(
			frappe.db.get_value("Customer Warehouse", self.name, "bat_buoc_thiet_bi")
		)
		if not truoc:
			self.bat_buoc_thiet_bi_tu = frappe.utils.now_datetime()
```

- [ ] **Step 5: Chốt chặn trong `CustomerStockIssue`**

```python
	def _chan_thieu_thiet_bi(self):
		"""BR-TB-3 — sao y `_chan_thieu_khoa_phong()` bên dưới, KỂ CẢ phần
		tự lành khi cờ bật mà mốc rỗng. Đọc docstring hàm đó trước khi sửa
		hàm này; hai hàm phải cùng hành vi."""
		bat, moc = frappe.db.get_value(
			"Customer Warehouse", self.kho,
			["bat_buoc_thiet_bi", "bat_buoc_thiet_bi_tu"],
		)
		if not frappe.utils.cint(bat):
			return
		if not moc:
			moc = frappe.utils.now_datetime()
			frappe.db.set_value("Customer Warehouse", self.kho, "bat_buoc_thiet_bi_tu", moc)
		tao_luc = frappe.utils.get_datetime(self.creation or frappe.utils.now_datetime())
		if tao_luc <= frappe.utils.get_datetime(moc):
			return
		thieu = [r.idx for r in self.items if not r.thiet_bi]
		if thieu:
			frappe.throw(
				"Kho đã bật \"Bắt buộc chọn máy\" cho phiếu Xuất sử dụng tạo "
				f"sau thời điểm đó. Còn thiếu máy ở dòng: {', '.join(map(str, thieu))}.",
				frappe.ValidationError,
			)
```

Gọi nó **đúng chỗ** `_chan_thieu_khoa_phong()` đang được gọi — tức trong nhánh `before_submit` đã lọc `loai_xuat == "Xuất sử dụng"` và đã loại `Phiếu đảo`.

- [ ] **Step 6: Chạy test, xác nhận XANH**

```bash
cd /home/hoangvietyeuem/frappe-bench-yhct
bench --site erptest.local migrate
bench --site erptest.local run-tests --app miyano_portal --module miyano_portal.tests.test_tb3_bat_buoc
```

Kỳ vọng: 6 PASS.

- [ ] **Step 7: Commit**

```bash
cd /home/hoangvietyeuem/frappe-bench-yhct/apps/miyano_portal
git add miyano_portal/miyano_portal/doctype/customer_warehouse \
        miyano_portal/miyano_portal/doctype/customer_stock_issue \
        miyano_portal/tests/test_tb3_bat_buoc.py
git commit -m "feat(kho): cờ bắt buộc chọn máy kèm mốc thời gian (BR-TB-3)"
```

---

## Task 5: Cách ly dữ liệu máy

**Files:**
- Modify: `miyano_portal/kho/permissions.py`
- Modify: `miyano_portal/hooks.py`
- Test: `miyano_portal/tests/test_tb4_cach_ly.py`

**Interfaces:**
- Produces: `kho.permissions.thiet_bi_query(user)`, `kho.permissions.vat_tu_may_item_query(doc, user, permission_type)`.

- [ ] **Step 1: Viết test đỏ**

`miyano_portal/tests/test_tb4_cach_ly.py` — dựng hai bệnh viện ZZTB-A / ZZTB-B, mỗi bên một `Portal Member` Quản lý và một Nhân viên khoa:

```python
def test_query_condition_loc_theo_khach(self):
	frappe.set_user(self.ql_a)
	dieu_kien = permissions.thiet_bi_query(self.ql_a)
	self.assertIn(frappe.db.escape(self.khach_a), dieu_kien)
	self.assertNotIn(frappe.db.escape(self.khach_b), dieu_kien)

def test_nhan_vien_khoa_chi_thay_may_khoa_minh_va_may_dung_chung(self):
	frappe.set_user(self.nv_a1)
	dieu_kien = permissions.thiet_bi_query(self.nv_a1)
	self.assertIn("is null", dieu_kien.lower())      # máy dùng chung
	self.assertIn(frappe.db.escape(self.kp_a1), dieu_kien)
	self.assertNotIn(frappe.db.escape(self.kp_a2), dieu_kien)

def test_nhan_vien_mien_khong_thay_gi(self):
	frappe.set_user("Guest")
	self.assertEqual(permissions.thiet_bi_query("Guest"), "1=0")

def test_nhan_vien_miyano_thay_tat_ca(self):
	frappe.set_user("Administrator")
	self.assertEqual(permissions.thiet_bi_query("Administrator"), "")

def test_khong_co_docperm_cho_role_customer(self):
	"""Lớp CHỊU LỰC. Test này tồn tại để một PR sau không âm thầm cấp lại."""
	import json, pathlib
	for ten in ("customer_equipment",):
		p = pathlib.Path(frappe.get_app_path("miyano_portal")) / "miyano_portal" / "doctype" / ten / f"{ten}.json"
		perms = json.loads(p.read_text())["permissions"]
		self.assertNotIn("Customer", [x.get("role") for x in perms])

def test_website_user_khong_get_list_duoc(self):
	frappe.set_user(self.ql_a)
	with self.assertRaises(frappe.PermissionError):
		frappe.get_list("Customer Equipment")
```

- [ ] **Step 2: Chạy test, xác nhận ĐỎ**

```bash
cd /home/hoangvietyeuem/frappe-bench-yhct
bench --site erptest.local run-tests --app miyano_portal --module miyano_portal.tests.test_tb4_cach_ly
```

Kỳ vọng: FAIL — `module 'miyano_portal.kho.permissions' has no attribute 'thiet_bi_query'`.

- [ ] **Step 3: Viết hai hàm**

Thêm vào cuối `miyano_portal/kho/permissions.py`:

```python
def thiet_bi_query(user=None) -> str:
	"""LỚP PHÒNG THỦ THỨ HAI cho `Customer Equipment` — đọc docstring đầu
	file trước.

	Khác năm doctype kho phía trên: máy treo vào `customer` chứ không vào
	`kho` (khoa phòng đã chuyển chủ sở hữu sang bệnh viện từ 18/08), nên
	dùng khuôn `kho_query()` chứ không dùng `_kho_condition()`.

	Vế thứ hai — lọc theo khoa — là thứ năm doctype kia không có: một Nhân
	viên khoa chỉ được thấy máy của khoa mình CỘNG máy dùng chung
	(`khoa_phong` rỗng). Máy dùng chung phải lọt vào vì đó chính là những
	máy không thuộc khoa nào; ẩn chúng đi thì vật tư dùng chung không xuất
	cho máy nào được.
	"""
	user = user or frappe.session.user
	if not _is_restricted_user(user):
		return ""
	customers = get_allowed_customers(user)
	if not customers:
		return "1=0"
	joined = ", ".join(frappe.db.escape(c) for c in customers)
	dieu_kien = f"`tabCustomer Equipment`.`customer` in ({joined})"

	from miyano_portal.portal_context import get_portal_member

	try:
		tv = get_portal_member(user)
	except Exception:
		return dieu_kien
	if tv and tv.vai_tro == "Nhân viên khoa" and tv.khoa_phong:
		kp = frappe.db.escape(tv.khoa_phong)
		dieu_kien += (
			f" and (`tabCustomer Equipment`.`khoa_phong` = {kp}"
			" or `tabCustomer Equipment`.`khoa_phong` is null"
			" or `tabCustomer Equipment`.`khoa_phong` = '')"
		)
	return dieu_kien


def vat_tu_may_item_query(doc, user=None, permission_type=None) -> bool:
	"""`Customer Warehouse Item Equipment` là `istable` nên KHÔNG đi qua
	permission_query_conditions — phải chặn bằng has_permission, cùng khuôn
	hai child doctype kho đã có."""
	user = user or frappe.session.user
	if not _is_restricted_user(user):
		return True
	kho = frappe.db.get_value("Customer Warehouse Item", doc.parent, "kho")
	return bool(kho) and kho in set(get_allowed_khos(user))
```

- [ ] **Step 4: Đăng ký trong `hooks.py`**

Trong `permission_query_conditions`, cạnh các dòng kho:

```python
	# Thiết bị — treo vào `customer` (KHÔNG vào `kho`), cùng hình dạng
	# `Customer Warehouse`. Không có DocPerm nào cho role Customer (xem
	# JSON): cổng thật là api/kho.py, entry này là lớp phòng thủ thứ hai.
	"Customer Equipment": "miyano_portal.kho.permissions.thiet_bi_query",
```

Trong `has_permission`:

```python
	"Customer Warehouse Item Equipment": "miyano_portal.kho.permissions.vat_tu_may_item_query",
```

- [ ] **Step 5: Chạy test, xác nhận XANH**

```bash
cd /home/hoangvietyeuem/frappe-bench-yhct
bench --site erptest.local migrate
bench --site erptest.local run-tests --app miyano_portal --module miyano_portal.tests.test_tb4_cach_ly
```

Kỳ vọng: 6 PASS.

- [ ] **Step 6: Commit**

```bash
cd /home/hoangvietyeuem/frappe-bench-yhct/apps/miyano_portal
git add miyano_portal/kho/permissions.py miyano_portal/hooks.py miyano_portal/tests/test_tb4_cach_ly.py
git commit -m "feat(kho): cách ly Customer Equipment theo bệnh viện và khoa"
```

---

## Task 6: Module `kho/thiet_bi.py`

**Files:**
- Create: `miyano_portal/kho/thiet_bi.py`
- Test: `miyano_portal/tests/test_tb5_endpoint.py` (phần logic)

**Interfaces:**
- Produces:
  - `ra_dict(name: str) -> dict` — một máy dạng phẳng cho SPA.
  - `list_rows(customer, user, tim_kiem=None, ca_inactive=0, khoa_phong=None, vat_tu=None, limit=None, start=0) -> list | dict`
  - `save(customer, user, du_lieu: dict) -> dict`
  - `tao_nhanh(customer, user, du_lieu: dict) -> dict`
  - `gan_vao_vat_tu(vat_tu: str, thiet_bi: str) -> dict` — idempotent.

- [ ] **Step 1: Viết test đỏ**

Tạo `miyano_portal/tests/test_tb5_endpoint.py`. Nền: một bệnh viện ZZTB5 có kho,
hai khoa A/B, ba `Portal Member` (`ql`, `nv_a`, `nv_b`), ba máy (`may_a` ở khoa A,
`may_b` ở khoa B, `may_chung` không khoa), một vật tư.

```python
"""Logic + endpoint danh mục thiết bị.

Ca quan trọng nhất KHÔNG phải "gửi bậy thì lỗi" mà là "gửi bậy thì bị ÉP về
đúng": một nhân viên khoa A gửi kèm khoa B vẫn tạo ra máy thuộc khoa A. Trả
lỗi cũng chấp nhận được về mặt an toàn, nhưng ép là hành vi đã chốt
(BR-TB-6) và giống `portal_context.khoa_phong_cho_don()` đang chạy.
"""

import frappe
from frappe.tests.utils import FrappeTestCase

from miyano_portal.api import kho as kho_api
from miyano_portal.kho import thiet_bi as thiet_bi_mod


class TestThietBiLogic(FrappeTestCase):
	def test_nhan_vien_khoa_chi_thay_may_khoa_minh_va_may_chung(self):
		frappe.set_user(self.nv_a)
		ten = {r["name"] for r in thiet_bi_mod.list_rows(self.khach, self.nv_a)}
		self.assertIn(self.may_a.name, ten)
		self.assertIn(self.may_chung.name, ten)
		self.assertNotIn(self.may_b.name, ten)

	def test_quan_ly_thay_tat_ca(self):
		frappe.set_user(self.ql)
		ten = {r["name"] for r in thiet_bi_mod.list_rows(self.khach, self.ql)}
		self.assertEqual(ten, {self.may_a.name, self.may_b.name, self.may_chung.name})

	def test_loc_tang_hai_theo_vat_tu(self):
		self.vat_tu.set("may_su_dung", [{"thiet_bi": self.may_a.name}])
		self.vat_tu.save(ignore_permissions=True)
		frappe.set_user(self.ql)
		ten = {
			r["name"] for r in thiet_bi_mod.list_rows(
				self.khach, self.ql, vat_tu=self.vat_tu.name
			)
		}
		self.assertEqual(ten, {self.may_a.name})

	def test_bang_may_trong_thi_khong_loc_tang_hai(self):
		frappe.set_user(self.ql)
		ten = {
			r["name"] for r in thiet_bi_mod.list_rows(
				self.khach, self.ql, vat_tu=self.vat_tu.name
			)
		}
		self.assertEqual(len(ten), 3)

	def test_nhan_vien_khoa_gui_khoa_khac_thi_bi_ep_ve_khoa_minh(self):
		"""BR-TB-6 — ÉP, không phải tin."""
		frappe.set_user(self.nv_a)
		ra = thiet_bi_mod.save(self.khach, self.nv_a, {
			"ma_thiet_bi": "ZZTB5-NEW", "ten_thiet_bi": "Máy mới",
			"khoa_phong": self.kp_b.name,
		})
		self.assertEqual(
			frappe.db.get_value("Customer Equipment", ra["name"], "khoa_phong"),
			self.kp_a.name,
		)

	def test_nhan_vien_khoa_khong_sua_duoc_may_khoa_khac(self):
		"""BR-TB-7."""
		frappe.set_user(self.nv_a)
		with self.assertRaises(frappe.PermissionError):
			thiet_bi_mod.save(self.khach, self.nv_a, {
				"name": self.may_b.name, "ten_thiet_bi": "Đổi trộm",
			})

	def test_nhan_vien_khoa_khong_sua_duoc_may_dung_chung(self):
		"""BR-TB-8b — thấy và chọn được, nhưng không sửa được."""
		frappe.set_user(self.nv_a)
		with self.assertRaises(frappe.PermissionError):
			thiet_bi_mod.save(self.khach, self.nv_a, {
				"name": self.may_chung.name, "ten_thiet_bi": "Đổi trộm",
			})

	def test_quan_ly_dieu_chuyen_duoc_may_sang_khoa_khac(self):
		"""BR-TB-8."""
		frappe.set_user(self.ql)
		thiet_bi_mod.save(self.khach, self.ql, {
			"name": self.may_a.name, "khoa_phong": self.kp_b.name,
		})
		self.assertEqual(
			frappe.db.get_value("Customer Equipment", self.may_a.name, "khoa_phong"),
			self.kp_b.name,
		)

	def test_tao_nhanh_van_validate_day_du(self):
		""""Nhanh" nói về SỐ Ô, không nói về độ chặt."""
		frappe.set_user(self.ql)
		with self.assertRaises(frappe.ValidationError):
			thiet_bi_mod.tao_nhanh(self.khach, self.ql, {
				"ten_thiet_bi": "Máy X", "ma_thiet_bi": self.may_a.ma_thiet_bi,
			})

	def test_tao_nhanh_dien_du_sau_o(self):
		frappe.set_user(self.ql)
		ra = thiet_bi_mod.tao_nhanh(self.khach, self.ql, {
			"ten_thiet_bi": "Máy Cobas", "ma_thiet_bi": "COBAS-01",
			"hang_san_xuat": "Roche", "xuat_xu": "Thuỵ Sĩ", "so_serial": "SN-9",
		})
		doc = frappe.get_doc("Customer Equipment", ra["name"])
		self.assertEqual(doc.hang_san_xuat, "Roche")
		self.assertEqual(doc.xuat_xu, "Thuỵ Sĩ")

	def test_gan_vao_vat_tu_goi_hai_lan_khong_sinh_dong_thu_hai(self):
		thiet_bi_mod.gan_vao_vat_tu(self.vat_tu.name, self.may_a.name)
		thiet_bi_mod.gan_vao_vat_tu(self.vat_tu.name, self.may_a.name)
		self.vat_tu.reload()
		self.assertEqual(len(self.vat_tu.may_su_dung), 1)
```

- [ ] **Step 2: Chạy test, xác nhận ĐỎ**

```bash
cd /home/hoangvietyeuem/frappe-bench-yhct
bench --site erptest.local run-tests --app miyano_portal --module miyano_portal.tests.test_tb5_endpoint
```

- [ ] **Step 3: Viết module**

Khung bắt buộc (chi tiết còn lại theo khuôn `kho/khoa_phong.py`):

```python
"""Danh mục thiết bị của khách hàng — logic thuần, không whitelist.

Đường ghi: các hàm ở đây được gọi từ api/kho.py SAU khi endpoint đã suy
`customer`/`user` từ phiên. Chúng ghi bằng ignore_permissions=True — đúng
khuôn kho/khoa_phong.py::save(). Xem Global Constraint 2 của kế hoạch: THÊM
DOCPERM KHÔNG BAO GIỜ LÀ CÁCH SỬA một PermissionError ở đây.
"""

import frappe

from miyano_portal.portal_context import get_portal_member

TRUONG_NHAN_TU_CLIENT = (
	"ma_thiet_bi", "ten_thiet_bi", "hang_san_xuat", "xuat_xu",
	"model", "so_serial", "nam_san_xuat", "ngay_lap_dat", "ghi_chu",
)

# Sáu ô của form tạo nhanh. "Nhanh" nói về SỐ Ô, không nói về độ chặt —
# tao_nhanh() đi qua đúng validate() của doctype như form đầy đủ.
TRUONG_TAO_NHANH = ("ten_thiet_bi", "ma_thiet_bi", "hang_san_xuat", "xuat_xu", "so_serial")


def _khoa_ep_theo_phien(user: str, khoa_client):
	"""Nhân viên khoa: BỎ QUA HOÀN TOÀN giá trị client gửi, luôn trả khoa
	của chính họ. Quản lý: nhận giá trị client (đã kiểm cùng bệnh viện ở
	controller). Cùng nguyên tắc `portal_context.khoa_phong_cho_don()`."""
	tv = get_portal_member(user)
	if tv.vai_tro == "Nhân viên khoa":
		return tv.khoa_phong
	return khoa_client or None


def _chan_sua_ngoai_pham_vi(user: str, name: str):
	"""BR-TB-7 + BR-TB-8b."""
	tv = get_portal_member(user)
	if tv.vai_tro != "Nhân viên khoa":
		return
	kp = frappe.db.get_value("Customer Equipment", name, "khoa_phong")
	if not kp:
		raise frappe.PermissionError(
			"Máy dùng chung không thuộc khoa nào — chỉ quản lý đơn vị sửa được."
		)
	if kp != tv.khoa_phong:
		raise frappe.PermissionError("Máy này thuộc khoa khác.")
```

- [ ] **Step 4: Chạy test, xác nhận XANH** — cùng lệnh Step 2.

- [ ] **Step 5: Commit**

```bash
git add miyano_portal/kho/thiet_bi.py miyano_portal/tests/test_tb5_endpoint.py
git commit -m "feat(kho): module danh mục thiết bị, ép khoa theo phiên"
```

---

## Task 7: Endpoint cổng

**Files:**
- Modify: `miyano_portal/api/kho.py`
- Test: `miyano_portal/tests/test_tb5_endpoint.py` (phần endpoint)

**Interfaces:**
- Produces: `kho_thiet_bi_list`, `kho_thiet_bi_save`, `kho_thiet_bi_tao_nhanh`, `kho_vat_tu_gan_thiet_bi`, guard `_thiet_bi_cua_khach(thiet_bi, customer)`.

- [ ] **Step 1: Viết test đỏ**

Thêm lớp vào `miyano_portal/tests/test_tb5_endpoint.py`:

```python
class TestThietBiEndpoint(FrappeTestCase):
	def test_endpoint_khong_nhan_customer_tu_client(self):
		"""Chữ ký hàm KHÔNG được có tham số customer/kho — nguyên tắc bất di
		bất dịch ở đầu api/kho.py. Test đọc chữ ký để một PR sau không thêm
		vào cho tiện."""
		import inspect
		for ten in ("kho_thiet_bi_list", "kho_thiet_bi_save",
		            "kho_thiet_bi_tao_nhanh", "kho_vat_tu_gan_thiet_bi"):
			tham_so = set(inspect.signature(getattr(kho_api, ten)).parameters)
			self.assertFalse(
				tham_so & {"customer", "kho", "user"},
				f"{ten} nhận định danh từ client",
			)

	def test_list_qua_endpoint_loc_dung_theo_phien(self):
		frappe.set_user(self.nv_a)
		ten = {r["name"] for r in kho_api.kho_thiet_bi_list()}
		self.assertNotIn(self.may_b.name, ten)

	def test_may_benh_vien_khac_gan_vao_vat_tu_bi_chan(self):
		frappe.set_user(self.ql)
		with self.assertRaises(frappe.PermissionError):
			kho_api.kho_vat_tu_gan_thiet_bi(self.vat_tu.name, self.may_benh_vien_khac.name)

	def test_vat_tu_benh_vien_khac_bi_chan(self):
		frappe.set_user(self.ql)
		with self.assertRaises(frappe.PermissionError):
			kho_api.kho_vat_tu_gan_thiet_bi(self.vat_tu_khac_kho.name, self.may_a.name)

	def test_loc_theo_vat_tu_cua_kho_khac_bi_chan(self):
		"""`vat_tu` là định danh do client gửi — phải qua guard TRƯỚC khi dùng
		làm bộ lọc, nếu không nó thành một kênh dò dữ liệu kho khác."""
		frappe.set_user(self.ql)
		with self.assertRaises(frappe.PermissionError):
			kho_api.kho_thiet_bi_list(vat_tu=self.vat_tu_khac_kho.name)

	def test_loi_khong_lo_ten_lop_ngoai_le(self):
		"""Decorator _thiet_bi_action phải dịch mọi lỗi lạ sang tiếng Việt."""
		frappe.set_user(self.ql)
		try:
			kho_api.kho_thiet_bi_save({"name": "KHONG-CO-THAT"})
		except Exception as e:
			self.assertNotIn("Traceback", str(e))
```

- [ ] **Step 2: Chạy test, xác nhận ĐỎ.**

- [ ] **Step 3: Viết guard + 4 endpoint**

```python
_thiet_bi_action = _action("thiết bị")


def _thiet_bi_cua_khach(thiet_bi: str, customer: str) -> str:
	"""Cùng khuôn _vat_tu_cua_kho(): xác nhận một máy do client gửi lên đúng
	là của bệnh viện người gọi TRƯỚC khi get_doc/save chạm vào nó."""
	if frappe.db.get_value("Customer Equipment", thiet_bi, "customer") != customer:
		raise frappe.PermissionError("Máy không thuộc đơn vị bạn.")
	return thiet_bi


@frappe.whitelist()
@_thiet_bi_action
def kho_thiet_bi_list(tim_kiem=None, ca_inactive=0, khoa_phong=None, vat_tu=None,
                      limit=None, start=0) -> list | dict:
	"""Danh mục máy — KIÊM HAI VAI: màn danh mục và dropdown trên phiếu xuất.

	`vat_tu` là bộ lọc TẦNG HAI (chỉ những máy trong bảng "Máy sử dụng" của
	vật tư đó). Đây là lý do SPA không được dùng Link field chuẩn: bộ lọc
	tầng hai phải do SERVER áp, client tự khai thì bỏ qua được.
	"""
	customer = get_portal_customer()
	if vat_tu:
		_vat_tu_cua_kho(vat_tu, get_portal_kho())
	return thiet_bi_mod.list_rows(
		customer, frappe.session.user, tim_kiem, ca_inactive, khoa_phong, vat_tu, limit, start
	)
```

Ba endpoint còn lại theo cùng khuôn: suy `customer` từ phiên → guard định danh client gửi → gọi `thiet_bi_mod`.

- [ ] **Step 4: Chạy test, xác nhận XANH.**

- [ ] **Step 5: Commit**

```bash
git add miyano_portal/api/kho.py miyano_portal/tests/test_tb5_endpoint.py
git commit -m "feat(kho): 4 endpoint cổng cho danh mục thiết bị"
```

---

## Task 8: `kho_phieu_xuat_save` nhận máy

**Files:**
- Modify: `miyano_portal/api/kho.py` (hàm `kho_phieu_xuat_save`, ~dòng 793)
- Test: `miyano_portal/tests/test_tb5_endpoint.py`

**Interfaces:**
- Produces: `_phieu_to_dict(doc)` trả thêm khoá `canh_bao_thiet_bi: list[str]`.

- [ ] **Step 1: Viết test đỏ**

```python
class TestPhieuXuatNhanMay(FrappeTestCase):
	def test_dong_ghi_dung_may(self):
		frappe.set_user(self.ql)
		ra = kho_api.kho_phieu_xuat_save({
			"ngay": frappe.utils.today(), "loai_xuat": "Xuất sử dụng",
			"khoa_phong": self.kp_a.name, "thiet_bi_mac_dinh": self.may_a.name,
			"items": [{"vat_tu": self.vat_tu.name, "so_lo": self.lo,
			           "so_luong": 2, "thiet_bi": self.may_a.name}],
		})
		doc = frappe.get_doc("Customer Stock Issue", ra["name"])
		self.assertEqual(doc.items[0].thiet_bi, self.may_a.name)

	def test_may_ngoai_danh_muc_van_luu_duoc_kem_canh_bao(self):
		self.vat_tu.set("may_su_dung", [{"thiet_bi": self.may_a.name}])
		self.vat_tu.save(ignore_permissions=True)
		frappe.set_user(self.ql)
		ra = kho_api.kho_phieu_xuat_save({
			"ngay": frappe.utils.today(), "loai_xuat": "Xuất sử dụng",
			"items": [{"vat_tu": self.vat_tu.name, "so_lo": self.lo,
			           "so_luong": 1, "thiet_bi": self.may_chung.name}],
		})
		self.assertTrue(ra["name"])
		self.assertTrue(ra["canh_bao_thiet_bi"])

	def test_khong_co_canh_bao_thi_khoa_van_ton_tai_va_rong(self):
		"""SPA đọc thẳng `ket_qua.canh_bao_thiet_bi` — thiếu khoá sẽ vỡ giao
		diện, nên khoá phải LUÔN có, kể cả khi không có cảnh báo nào."""
		frappe.set_user(self.ql)
		ra = kho_api.kho_phieu_xuat_save({
			"ngay": frappe.utils.today(), "loai_xuat": "Xuất sử dụng",
			"items": [{"vat_tu": self.vat_tu.name, "so_lo": self.lo, "so_luong": 1}],
		})
		self.assertEqual(ra["canh_bao_thiet_bi"], [])

	def test_may_benh_vien_khac_bi_chan_o_tang_controller(self):
		frappe.set_user(self.ql)
		with self.assertRaises(frappe.PermissionError):
			kho_api.kho_phieu_xuat_save({
				"ngay": frappe.utils.today(), "loai_xuat": "Xuất sử dụng",
				"items": [{"vat_tu": self.vat_tu.name, "so_lo": self.lo,
				           "so_luong": 1, "thiet_bi": self.may_benh_vien_khac.name}],
			})
```

- [ ] **Step 2: Chạy test, xác nhận ĐỎ.**

- [ ] **Step 3: Sửa endpoint**

Trong vòng `for row in items`, thêm đúng một khoá:

```python
			# `thiet_bi` KHÔNG kiểm sở hữu ở tầng endpoint — cùng đúng khuôn
			# `vat_tu` và `khoa_phong` ngay trên: chốt chặn nằm ở TẦNG
			# CONTROLLER (_validate_thiet_bi), chạy trên MỌI đường ghi kể cả
			# Desk, không lặp logic kiểm hai lần.
			"thiet_bi": row.get("thiet_bi") or None,
```

Và trước `doc.khoa_phong = ...`:

```python
	doc.thiet_bi_mac_dinh = payload.get("thiet_bi_mac_dinh") or None
```

Rồi trong `_phieu_to_dict`, đính kèm cảnh báo:

```python
	out["canh_bao_thiet_bi"] = list(doc.flags.get("canh_bao_thiet_bi") or [])
```

- [ ] **Step 4: Chạy test, xác nhận XANH.**

- [ ] **Step 5: Commit**

```bash
git add miyano_portal/api/kho.py miyano_portal/tests/test_tb5_endpoint.py
git commit -m "feat(kho): phiếu xuất qua cổng nhận máy trên từng dòng"
```

---

## Task 9: Báo cáo "Vật tư · Máy · Khoa phòng"

**Files:**
- Modify: `miyano_portal/kho/reports.py`
- Test: `miyano_portal/tests/test_tb6_bao_cao.py`

**Interfaces:**
- Produces: `bao_cao_thiet_bi_rows(kho, tu_ngay, den_ngay, thiet_bi=None, khoa_phong=None, vat_tu=None) -> dict` với hình dạng:

```python
{
  "tong_gia_tri": float,
  "dong": [
    {
      "vat_tu_id": str, "ma_vat_tu": str, "vat_tu": str, "dvt": str,
      "ton_dau": float, "nhap": float,
      "cap_phat": float,      # lọc HAI lớp
      "xuat_khac": float,     # huỷ/trả/điều chỉnh + phần đã bị đảo
      "ton_cuoi": float,
      "may_tuong_thich": [{"thiet_bi": str, "ten": str}],
      "theo_may": [
        {"thiet_bi": str | None, "ten_may": str, "khoa_phong": str | None,
         "ten_khoa": str, "sl": float, "gia_tri": float, "pct": float}
      ],
    }
  ],
}
```

**Bất biến phải đúng, và có test giữ:**
`ton_dau + nhap - cap_phat - xuat_khac == ton_cuoi`, và `sum(r["sl"] for r in theo_may) == cap_phat`.

- [ ] **Step 1: Viết test đỏ**

`miyano_portal/tests/test_tb6_bao_cao.py` — sáu ca, dựng nền một kho có: 1 vật tư gắn 3 máy, xuất cho 2 máy; 1 phiếu bị đảo; 1 phiếu `Xuất huỷ - hết hạn`; 1 phiếu cũ không máy; 2 vật tư khác ĐVT cùng tên.

```python
def test_tong_theo_may_bang_cot_cap_phat(self):
	bc = reports.bao_cao_thiet_bi_rows(self.kho, self.tu, self.den)
	dong = self._dong(bc, self.vat_tu.name)
	self.assertAlmostEqual(sum(r["sl"] for r in dong["theo_may"]), dong["cap_phat"])

def test_khong_cong_trung_khi_vat_tu_dung_nhieu_may(self):
	"""Máy thứ ba khai trong danh mục nhưng chưa xuất lần nào — KHÔNG được
	xuất hiện trong theo_may với số 0 giả."""
	bc = reports.bao_cao_thiet_bi_rows(self.kho, self.tu, self.den)
	dong = self._dong(bc, self.vat_tu.name)
	self.assertEqual(len(dong["theo_may"]), 2)
	self.assertEqual(len(dong["may_tuong_thich"]), 3)

def test_phieu_dao_khong_lot_ca_hai_lop(self):
	bc = reports.bao_cao_thiet_bi_rows(self.kho, self.tu, self.den)
	dong = self._dong(bc, self.vat_tu_dao.name)
	self.assertEqual(dong["cap_phat"], 0)

def test_phieu_cu_khong_may_vao_nhom_chua_gan(self):
	bc = reports.bao_cao_thiet_bi_rows(self.kho, self.tu, self.den)
	dong = self._dong(bc, self.vat_tu_cu.name)
	chua = [r for r in dong["theo_may"] if r["thiet_bi"] is None]
	self.assertEqual(len(chua), 1)
	self.assertEqual(chua[0]["ten_may"], "Chưa gắn máy")
	self.assertIs(dong["theo_may"][-1], chua[0])   # LUÔN ở cuối

def test_hai_vat_tu_cung_ten_khac_dvt_tach_hai_dong(self):
	bc = reports.bao_cao_thiet_bi_rows(self.kho, self.tu, self.den)
	trung = [d for d in bc["dong"] if d["vat_tu"] == "Nước cất"]
	self.assertEqual(len(trung), 2)
	self.assertEqual({d["dvt"] for d in trung}, {"Chai", "Lít"})

def test_hang_van_can_khi_ky_co_ca_xuat_huy_va_phieu_dao(self):
	"""CA 13 của spec — ca đã suýt bị bỏ sót và là lý do tách hai cột xuất."""
	bc = reports.bao_cao_thiet_bi_rows(self.kho, self.tu, self.den)
	for d in bc["dong"]:
		self.assertAlmostEqual(
			d["ton_dau"] + d["nhap"] - d["cap_phat"] - d["xuat_khac"], d["ton_cuoi"],
			places=4,
			msg=f"Hàng không cân ở vật tư {d['ma_vat_tu']}",
		)
```

- [ ] **Step 2: Chạy test, xác nhận ĐỎ.**

- [ ] **Step 3: Viết hàm báo cáo**

Trong `miyano_portal/kho/reports.py`, sau `bao_cao_cap_phat_rows`. Docstring phải nêu rõ vì sao hai cột xuất (chép lý lẽ §9.2 của spec). Bộ khung:

```python
def bao_cao_thiet_bi_rows(kho, tu_ngay, den_ngay, thiet_bi=None,
                          khoa_phong=None, vat_tu=None) -> dict:
	"""Báo cáo "Vật tư · Máy · Khoa phòng".

	HAI CỘT XUẤT, cố ý. Module này chạy hai quy ước đếm khác nhau: NXT/thẻ
	kho KHÔNG lọc `da_dao` khỏi bất kỳ tổng nào (câu hỏi kế toán lịch sử),
	còn `bao_cao_cap_phat_rows` lọc HAI lớp (câu hỏi "khoa nào đang thực sự
	giữ hàng"). Đặt một cột "Đã xuất" kiểu NXT cạnh phần tách theo máy kiểu
	cấp phát thì hai bên lệch nhau vì hai lý do độc lập: phiếu bị đảo, và
	các loại xuất huỷ/trả lại/điều chỉnh vốn KHÔNG mang máy theo thiết kế
	(BR-TB-3 chỉ áp cho "Xuất sử dụng"). Đo trên site 27/08: 4 phiếu xuất,
	chỉ 3 là "Xuất sử dụng" — lệch là ca THƯỜNG.

	Nên: `cap_phat` (lọc hai lớp, khớp đúng tổng `theo_may`) và `xuat_khac`
	(phần còn lại), giữ bất biến
	`ton_dau + nhap - cap_phat - xuat_khac == ton_cuoi`.
	"""
```

Dùng lại `_vat_tu_info()`, `nxt_data()` cho `ton_dau`/`nhap`/`ton_cuoi`; phần `theo_may` join sổ → `chung_tu_row` → `Customer Stock Issue Item.thiet_bi`.

- [ ] **Step 4: Chạy test, xác nhận XANH.**

- [ ] **Step 5: Chạy toàn bộ test kho để bắt hồi quy**

```bash
cd /home/hoangvietyeuem/frappe-bench-yhct
bench --site erptest.local run-tests --app miyano_portal
```

- [ ] **Step 6: Commit**

```bash
git add miyano_portal/kho/reports.py miyano_portal/tests/test_tb6_bao_cao.py
git commit -m "feat(kho): báo cáo Vật tư-Máy-Khoa, tách cấp phát và xuất khác"
```

---

## Task 10: Báo cáo theo máy, cấp phát ba cấp, Desk

**Files:**
- Modify: `miyano_portal/kho/reports.py` (`tieu_thu_theo_may_rows`, mở rộng `bao_cao_cap_phat_rows`)
- Modify: `miyano_portal/kho/desk_reports.py` (`tieu_thu_theo_thiet_bi_rows`)
- Modify: `miyano_portal/api/kho.py` (endpoint + `_BAO_CAO_LOAI`)
- Test: `miyano_portal/tests/test_tb6_bao_cao.py`

**Interfaces:**
- Produces: `tieu_thu_theo_may_rows(kho, tu_ngay, den_ngay) -> list[dict]`; `bao_cao_cap_phat_rows(...)` mỗi nhóm khoa có thêm khoá `theo_may`; `desk_reports.tieu_thu_theo_thiet_bi_rows(customer=None, tu_ngay=None, den_ngay=None) -> list[dict]`.

**Bắt buộc:** mở rộng `bao_cao_cap_phat_rows` **chỉ thêm khoá**, không đổi khoá cũ và không đổi chữ ký — ba màn SPA và một nút Excel đang gọi nó.

- [ ] **Step 1: Viết test đỏ**

```python
class TestBaoCaoTheoMay(FrappeTestCase):
	# Danh sách CỨNG, cố ý: ba màn SPA và một nút Excel đang đọc đúng các
	# khoá này. Thêm khoá thì sửa danh sách; ĐỔI hoặc XOÁ khoá là hồi quy.
	KHOA_NHOM_CU = {"khoa_phong", "ten_hien_thi", "gia_tri", "pct", "dong"}

	def test_cap_phat_giu_nguyen_khoa_cu(self):
		bc = reports.bao_cao_cap_phat_rows(self.kho, self.tu, self.den)
		for nhom in bc["nhom"]:
			self.assertTrue(self.KHOA_NHOM_CU <= set(nhom))

	def test_cap_phat_them_khoa_theo_may(self):
		bc = reports.bao_cao_cap_phat_rows(self.kho, self.tu, self.den)
		self.assertIn("theo_may", bc["nhom"][0])

	def test_theo_may_cong_bang_gia_tri_cua_khoa(self):
		bc = reports.bao_cao_cap_phat_rows(self.kho, self.tu, self.den)
		for nhom in bc["nhom"]:
			self.assertAlmostEqual(
				sum(m["gia_tri"] for m in nhom["theo_may"]), nhom["gia_tri"], places=2
			)

	def test_tieu_thu_theo_may_gop_theo_docname(self):
		"""Hai máy khác nhau CÙNG TÊN (bệnh viện mua hai máy giống hệt, khai
		trùng tên là chuyện thường) phải ra HAI dòng."""
		rows = reports.tieu_thu_theo_may_rows(self.kho, self.tu, self.den)
		cung_ten = [r for r in rows if r["ten_may"] == "Máy XN-500"]
		self.assertEqual(len(cung_ten), 2)

	def test_desk_loc_theo_customer(self):
		rows = desk_reports.tieu_thu_theo_thiet_bi_rows(customer=self.khach)
		self.assertTrue(rows)
		self.assertTrue(all(r["customer"] == self.khach for r in rows))

	def test_desk_khong_loc_thi_gom_nhieu_benh_vien(self):
		rows = desk_reports.tieu_thu_theo_thiet_bi_rows()
		self.assertGreaterEqual(len({r["customer"] for r in rows}), 1)
```

- [ ] **Step 2: Chạy test, xác nhận ĐỎ**

```bash
cd /home/hoangvietyeuem/frappe-bench-yhct
bench --site erptest.local run-tests --app miyano_portal --module miyano_portal.tests.test_tb6_bao_cao
```

- [ ] **Step 3: Viết ba hàm**

`tieu_thu_theo_may_rows` trả về mỗi dòng:

```python
{"thiet_bi": str | None, "ten_may": str, "ma_may": str, "khoa_phong": str | None,
 "ten_khoa": str, "so_vat_tu": int, "sl": float, "gia_tri": float,
 "vat_tu": [{"vat_tu_id": str, "ten": str, "dvt": str, "sl": float, "gia_tri": float}]}
```

`desk_reports.tieu_thu_theo_thiet_bi_rows` thêm `customer` và `ten_khach` vào mỗi
dòng, và dùng `_active_khos(customer)` + `_customer_names()` sẵn có ở đầu file đó.

Mở rộng `bao_cao_cap_phat_rows`: **chỉ thêm khoá `theo_may` vào mỗi nhóm khoa**,
không đổi khoá cũ, không đổi chữ ký.
- [ ] **Step 4: Thêm `"thiet_bi"` vào `_BAO_CAO_LOAI` và nhánh tương ứng trong `kho_bao_cao_excel`.**
- [ ] **Step 5: Chạy test, xác nhận XANH.**
- [ ] **Step 6: Commit** — `feat(kho): báo cáo theo máy, cấp phát ba cấp, báo cáo Desk`

---

## Task 11: Cột "Mã máy" trong Excel nhập phiếu hàng loạt

**Files:**
- Modify: `miyano_portal/kho/dong_phieu.py`
- Test: `miyano_portal/tests/test_tb5_endpoint.py`

**Interfaces:**
- Produces: file mẫu phiếu xuất có thêm cột **"Mã máy"**; hàm đọc trả về `thiet_bi` (docname) trên mỗi dòng, và **lỗi có cấu trúc** khi mã không tìm thấy.

- [ ] **Step 1: Viết test đỏ**

```python
class TestExcelCotMaMay(FrappeTestCase):
	def test_ma_dung_ra_docname(self):
		rows, loi = dong_phieu.doc_rows_xuat(self.kho, [
			{"Mã vật tư": "ZZTB-HC1", "Số lô": self.lo, "Số lượng": 2,
			 "Mã máy": "XN500-01"},
		])
		self.assertEqual(rows[0]["thiet_bi"], self.may_a.name)
		self.assertEqual(loi, [])

	def test_ma_sai_vao_danh_sach_loi_chu_khong_bi_bo_qua(self):
		"""Bỏ qua im lặng = ghi sổ thiếu máy mà người dùng tin là đã có."""
		rows, loi = dong_phieu.doc_rows_xuat(self.kho, [
			{"Mã vật tư": "ZZTB-HC1", "Số lô": self.lo, "Số lượng": 2,
			 "Mã máy": "KHONG-CO"},
		])
		self.assertTrue(loi)
		self.assertIn("KHONG-CO", loi[0]["thong_diep"])

	def test_o_trong_la_khong_gan_may_khong_phai_loi(self):
		rows, loi = dong_phieu.doc_rows_xuat(self.kho, [
			{"Mã vật tư": "ZZTB-HC1", "Số lô": self.lo, "Số lượng": 2, "Mã máy": ""},
		])
		self.assertIsNone(rows[0]["thiet_bi"])
		self.assertEqual(loi, [])

	def test_ma_may_cua_benh_vien_khac_bao_loi_giong_ma_khong_ton_tai(self):
		"""Không được lộ ra rằng mã đó CÓ THẬT ở bệnh viện khác."""
		_, loi_la = dong_phieu.doc_rows_xuat(self.kho, [
			{"Mã vật tư": "ZZTB-HC1", "Số lô": self.lo, "Số lượng": 1,
			 "Mã máy": self.may_benh_vien_khac.ma_thiet_bi},
		])
		_, loi_ma = dong_phieu.doc_rows_xuat(self.kho, [
			{"Mã vật tư": "ZZTB-HC1", "Số lô": self.lo, "Số lượng": 1,
			 "Mã máy": "HOAN-TOAN-BIA"},
		])
		self.assertEqual(loi_la[0]["ly_do"], loi_ma[0]["ly_do"])

	def test_file_mau_co_cot_ma_may(self):
		import openpyxl, io as _io
		wb = openpyxl.load_workbook(_io.BytesIO(dong_phieu.mau_xuat_bytes()))
		tieu_de = [c.value for c in wb.active[1]]
		self.assertIn("Mã máy", tieu_de)
```

- [ ] **Step 2: Chạy test, xác nhận ĐỎ**

```bash
cd /home/hoangvietyeuem/frappe-bench-yhct
bench --site erptest.local run-tests --app miyano_portal --module miyano_portal.tests.test_tb5_endpoint
```

- [ ] **Step 3: Thêm cột vào mẫu và vào bộ đọc**

Khớp `ma_thiet_bi` trong phạm vi `customer` suy từ `kho`, **một truy vấn cho cả
file** (không phải mỗi dòng một truy vấn — file nhập hàng loạt có thể vài trăm
dòng):

```python
	ma_to_name = {
		r["ma_thiet_bi"]: r["name"] for r in frappe.get_all(
			"Customer Equipment",
			filters={"customer": frappe.db.get_value("Customer Warehouse", kho, "customer")},
			fields=["name", "ma_thiet_bi"],
		)
	}
```
- [ ] **Step 4: Chạy test, xác nhận XANH.**
- [ ] **Step 5: Commit** — `feat(kho): cột Mã máy trong Excel nhập phiếu xuất hàng loạt`

---

## Task 12: Màn danh mục Thiết bị (SPA)

**Files:**
- Create: `frontend/src/views/ThietBiList.vue`, `frontend/src/components/ThietBiModal.vue`
- Modify: `frontend/src/router.js`, `frontend/src/App.vue`, `frontend/src/api.js`

**Interfaces:**
- Consumes: `kho_thiet_bi_list`, `kho_thiet_bi_save`.
- Produces: route `{ path: '/kho/thiet-bi', name: 'kho-thiet-bi' }`.

- [ ] **Step 1: Dựng `ThietBiList.vue`**

Phải có, không được thiếu cái nào:

| Thành phần | Chi tiết |
|---|---|
| Cột bảng | Mã máy · Tên máy · Khoa phòng · Hãng · Xuất xứ · Serial · Trạng thái · nút Sửa |
| Ô tìm | debounce 300ms, gọi `kho_thiet_bi_list({ tim_kiem })` |
| Bộ lọc | checkbox "Hiện cả máy đã tắt" → `ca_inactive: 1` |
| Phân trang | dùng `components/PhanTrang.vue` sẵn có; `limit: 20`, `start` theo trang |
| Nút Thêm | mở `ThietBiModal` ở chế độ tạo mới |
| Trạng thái rỗng | "Chưa khai máy nào. Bấm Thêm để khai máy đầu tiên." — **không** để bảng trắng |
| Máy đã tắt | hiện chữ " (đã tắt)" sau tên, cùng cách `PhieuXuat.vue:104` đang làm với khoa |

```js
const tai = async () => {
  const ra = await api.callKho('kho_thiet_bi_list', {
    tim_kiem: tuKhoa.value || undefined,
    ca_inactive: hienCaTat.value ? 1 : 0,
    limit: 20, start: (trang.value - 1) * 20,
  })
  rows.value = ra.rows || ra
  tong.value = ra.tong ?? (ra.rows ? ra.tong : ra.length)
}
```

- [ ] **Step 2: Dựng `ThietBiModal.vue`**

12 ô của master, chia hai cột: *trái* Mã máy · Tên máy · Khoa phòng · Đang hoạt
động; *phải* Hãng · Xuất xứ · Model · Số serial · Năm SX · Ngày lắp đặt; *dưới*
Ghi chú.

Hai điều bắt buộc:

1. **Nhân viên khoa**: ô Khoa phòng `disabled`, giá trị đặt sẵn là khoa của họ
   lấy từ `store.me.khoa_phong`. Server ép lại giá trị này (BR-TB-6) — giao diện
   chỉ đang phản ánh sự thật, **không** phải cơ chế bảo vệ.
2. **Máy dùng chung** (`khoa_phong` rỗng) mở ra bởi nhân viên khoa: mọi ô
   `disabled`, kèm dòng chữ *"Máy dùng chung — liên hệ quản lý đơn vị để sửa"*.
   Không hiện nút Lưu; để họ bấm rồi ăn `PermissionError` là thiết kế tồi.
- [ ] **Step 3: Thêm route + mục nav** cạnh "Danh mục khoa phòng".
- [ ] **Step 4: Build và mở màn**

```bash
cd /home/hoangvietyeuem/frappe-bench-yhct/apps/miyano_portal/frontend
npm run build
```

Kiểm bằng mắt trên `/portal/kho/thiet-bi`: tạo được máy, sửa được, bỏ tích Hoạt động thì máy rời khỏi danh sách mặc định.

- [ ] **Step 5: Commit** — `feat(portal): màn danh mục thiết bị`

---

## Task 13: Dropdown máy + tạo nhanh (SPA)

**Files:**
- Create: `frontend/src/components/ThietBiPicker.vue`, `frontend/src/components/ThietBiQuickCreate.vue`
- Modify: `frontend/src/views/PhieuXuatDetail.vue`, `frontend/src/components/VatTuModal.vue`

**Interfaces:**
- `ThietBiPicker` props: `modelValue` (docname | null), `vatTu` (string | null → bật lọc tầng hai), `disabled`. Emit: `update:modelValue`, `createNew({ search })`.

- [ ] **Step 1: Dựng `ThietBiPicker.vue`**

Nút tạo nhanh **ghim dòng đầu dropdown**, hiện cả khi đã có kết quả:

```vue
<button v-if="choPhepTao" type="button"
  @mousedown.prevent="$emit('createNew', { search: tuKhoa }); moRong = false"
  class="w-full text-left px-3 py-2 text-sm font-semibold text-sc-royal
         hover:bg-sc-bg border-b border-sc-border bg-sc-info-50">
  + Tạo nhanh máy{{ tuKhoa ? ` "${tuKhoa}"` : '' }}
</button>
```

> `@mousedown.prevent` là **bắt buộc**. `@click` thua sự kiện blur của input — nút sẽ không bao giờ chạy và trông như hỏng.

- [ ] **Step 2: Dựng `ThietBiQuickCreate.vue`** — đúng 6 ô, **điền sẵn** chữ vừa gõ vào *Tên máy*. Gọi `kho_thiet_bi_tao_nhanh`, trả máy mới về ô đang điền.
- [ ] **Step 3: Nối vào `PhieuXuatDetail.vue`** — cột **Máy** sau cột vật tư; ô **Máy mặc định** cạnh Khoa phòng; đổi máy mặc định chỉ điền xuống dòng **đang trống**; chỉ còn một máy hợp lệ thì **tự điền**.
- [ ] **Step 4: Hiện cảnh báo BR-TB-2** từ `canh_bao_thiet_bi` sau khi lưu, kèm nút **"Gắn máy này vào vật tư"** gọi `kho_vat_tu_gan_thiet_bi`.
- [ ] **Step 5: Nối vào `VatTuModal.vue`** — ô "Máy sử dụng" chọn nhiều, cùng nút tạo nhanh.
- [ ] **Step 6: Build và thử tay** — luồng đầy đủ: lập phiếu xuất → gõ tên máy chưa có → tạo nhanh → chọn → lưu → thấy cảnh báo → bấm gắn vào vật tư → lưu lại, cảnh báo biến mất.
- [ ] **Step 7: Commit** — `feat(portal): dropdown máy có tạo nhanh trên phiếu xuất và danh mục vật tư`

---

## Task 14: Màn báo cáo (SPA)

**Files:**
- Create: `frontend/src/views/BaoCaoThietBi.vue`
- Modify: `frontend/src/router.js`, `frontend/src/App.vue`, `frontend/src/kho-bao-cao-columns.js`

- [ ] **Step 1: Dựng màn**

| Thành phần | Chi tiết |
|---|---|
| Bộ lọc | Từ ngày · Đến ngày (mặc định tháng này) · Máy · Khoa phòng · ô tìm vật tư |
| Bảng ngoài | Mã VT · Tên vật tư · ĐVT · Tồn đầu · Đã nhập · **Đã cấp phát** · **Xuất khác** · Tồn cuối · Máy sử dụng |
| Mở rộng dòng | bảng con: Máy · Khoa phòng · SL xuất · Giá trị · % |
| "Chưa gắn máy" | **luôn ở cuối** bảng con, chữ xám nghiêng, không tô như một máy thật |
| Xuất Excel | `kho_bao_cao_excel({ loai: 'thiet_bi', ... })` |
| Trạng thái rỗng | "Kỳ này chưa có phát sinh." |

- [ ] **Step 2: Nhãn hai cột xuất phải tự giải thích**

Đặt nhãn **"Đã cấp phát"** và **"Xuất khác"**; cột thứ hai kèm tooltip:

> *"Xuất huỷ / hết hạn, xuất trả lại, điều chỉnh kiểm kê, và phần thuộc phiếu đã bị huỷ. Các loại này không gắn máy nên không nằm trong phần tách theo máy."*

Không có tooltip thì người xem sẽ tưởng chênh lệch là lỗi và báo bug — đây chính
là hiểu lầm mà việc tách hai cột sinh ra để dập tắt.

- [ ] **Step 2b: Kiểm bất biến ngay trên giao diện**

Thêm một dòng tổng cuối bảng và tự đối chiếu
`Tồn đầu + Đã nhập − Đã cấp phát − Xuất khác = Tồn cuối`. Lệch thì hiện cảnh báo
đỏ *"Số liệu không cân — báo kỹ thuật"* thay vì hiển thị im lặng.
- [ ] **Step 3: Build và kiểm bằng mắt với dữ liệu demo.**
- [ ] **Step 4: Commit** — `feat(portal): màn báo cáo vật tư theo máy và khoa`

---

## Task 15: Tài liệu, dữ liệu demo, chạy toàn bộ

**Files:**
- Modify: `docs/HDSD-tao-khach-hang-mo-kho-va-thao-tac-cong.md`
- Modify: `miyano_portal/setup/demo_kho_flow.py`
- Create: `docs/HDSD-quan-ly-vat-tu-theo-may.md`

- [ ] **Step 1: Thêm máy vào kịch bản demo** — 2 máy cho BV Minh Đức, 1 vật tư gắn 2 máy, 1 vật tư dùng chung, xuất cho cả hai máy. Giữ **idempotent**, **không** `frappe.db.commit()`.
- [ ] **Step 2: Viết HDSD** — khai máy, gắn máy vào vật tư, xuất có máy, đọc báo cáo. Nêu rõ: *"nhập không chọn máy"* và *vì sao* (nếu không, người dùng sẽ báo là thiếu tính năng).
- [ ] **Step 3: Chạy toàn bộ test**

```bash
cd /home/hoangvietyeuem/frappe-bench-yhct
bench --site erptest.local run-tests --app miyano_portal
```

Kỳ vọng: toàn bộ XANH. Gặp `ReadTimeout` lẻ tẻ thì chạy lại đúng module đó — đó là triệu chứng hết RAM khi ba bench cùng chạy, không phải hồi quy.

- [ ] **Step 4: Chạy demo end-to-end**

```bash
bench --site erptest.local execute miyano_portal.setup.demo_kho_flow.chay_tat_ca
```

- [ ] **Step 5: Commit** — `docs(kho): HDSD quản lý vật tư theo máy + dữ liệu demo`

---

## Bảng đối chiếu spec → task

| Mục spec | Task |
|---|---|
| §4.1 `Customer Equipment` | 1 |
| §4.2 bảng con máy trên vật tư | 2 |
| §4.3 `thiet_bi` dòng phiếu xuất | 3 |
| §4.4 `thiet_bi_mac_dinh` | 3 |
| §4.5 cờ bắt buộc + mốc | 4 |
| §4.6 không sửa sổ/lot balance/phiếu nhập | Ràng buộc chung 1 (test §9.1 giữ ở Task 9) |
| §5 BR-TB-1/2/4/5/9 | 3 |
| §5.1 BR-TB-3 | 4 |
| §5 BR-TB-6/7/8/8b | 6, 7 |
| §6 bốn lớp cách ly | 5 |
| §7.1 màn danh mục | 12 |
| §7.2 gắn máy vào vật tư | 2 (backend), 13 (giao diện) |
| §7.3 phiếu xuất | 3 (backend), 13 (giao diện) |
| §7.4 tạo nhanh | 6, 7 (backend), 13 (giao diện) |
| §7.5 Excel | 11 |
| §8 API | 7, 8 |
| §9.1 quy tắc tính | 9 |
| §9.2 báo cáo chính | 9 (backend), 14 (giao diện) |
| §9.3 theo máy · §9.4 cấp phát ba cấp · §9.5 Desk | 10 |
| §10 không backfill, cờ mặc định tắt | Ràng buộc chung 9, 10 |
| §11 ca 1–14 | 1, 3, 4, 5, 9 |
| §12 cố ý không làm | — (không có task, cố ý) |
