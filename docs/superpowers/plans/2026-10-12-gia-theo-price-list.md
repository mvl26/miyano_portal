# Giá theo Price List của khách hàng — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Cổng định giá mọi mặt hàng từ Price List của khách (không còn từ hợp đồng nguyên tắc), tách giỏ trộn thành hai phiếu, và ghi giá đã báo vào Price List khi khách đồng ý.

**Architecture:** Một module mới `bang_gia_khach.py` là nguồn giá duy nhất (đọc, ghi, bảo đảm bảng giá riêng). `dat_hang._xay_don` đóng dấu nguồn giá lên từng dòng đơn và bỏ mọi thứ thuộc hợp đồng. Một module mới `tach_phieu.py` tách phiếu trộn ở bước gửi. Luồng báo giá thêm ba chốt bằng hook `Sales Order` và ghi giá ở `portal_order_accept`.

**Tech Stack:** Frappe 15.113 / ERPNext 15.83 (Python 3.12), Vue 3.4 + Vite 6, MariaDB. Test: `FrappeTestCase` chạy qua `bench run-tests`.

**Spec:** `docs/superpowers/specs/2026-10-09-gia-theo-price-list-design.md` — đọc trước khi làm bất kỳ task nào.

## Global Constraints

- Nhánh làm việc: `feat/thoi-gian-giao-hang-va-gia-bang-gia`. Không commit ba file `miyano_portal/tests/test_e7_hddt.py`, `test_e7_hddt_nhap.py`, `test_e7b_tu_dong.py` (chủ dự án đang sửa dở).
- Chạy test: `cd /home/hoangvietyeuem/frappe-bench-yhct && bench --site erptest.local run-tests --app miyano_portal --module miyano_portal.tests.<ten_file>`.
- `erptest.local` cũng là site chủ dự án đang mở qua `192.168.61.129`. Không xoá dữ liệu ngoài dữ liệu test (`_TEST DX%`).
- Build giao diện: `cd frontend && yarn -s build`; bundle `miyano_portal/public/frontend/` được commit cùng thay đổi nguồn.
- Thụt lề theo file đang sửa: `api/portal.py`, `dat_hang.py`, `gia_hdnt.py`, `portal_mua_le.py` dùng 4 dấu cách; `hooks.py`, `de_xuat_duyet.py`, `api/de_xuat.py`, doctype `portal_de_xuat_mua`, và mọi file MỚI dùng tab.
- Tên trường, hằng số, thông báo: tiếng Việt, fieldname không dấu. Commit message không dấu, tiền tố `feat(portal):` / `test(portal):` / `docs:`; kết thúc bằng `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- Giá `<= 0` là CHƯA khai giá, không phải "bán 0 đồng".
- Giá trị chuỗi cố định: nguồn giá dòng đơn `"Bảng giá"` / `"Báo giá"`; nguồn giá dòng phiếu `"Bảng giá"` / `"Chờ báo giá"` (cũ: `"Hợp đồng"`); loại đơn `"Theo bảng giá"` / `"Mua lẻ"` (cũ: `"Theo HĐNT"`); `tang` của danh mục `"bang_gia"` / `"cho_bao_gia"`.
- Bộ test đầy đủ có 95 lỗi sẵn có ở `test_kho_isolation`, `test_e7_hddt`, `test_e7_hddt_nhap`, `test_tb6_bao_cao`, `test_notifications`. Chúng không thuộc kế hoạch này; mọi lỗi ở file khác là của mình.

## Review Focus

1. **Khách chưa có `default_price_list` đặt hàng.** Mong đợi: đơn vẫn tạo được, mọi dòng là chờ báo giá, khách được gán bảng riêng. Test ở Task 1 và Task 4.
2. **Gửi lại cùng `request_id` cho một giỏ trộn (bấm đúp, mạng chập chờn).** Mong đợi: trả về đúng hai đơn đã tạo, không sinh đơn thứ ba. Test ở Task 6.
3. **Dòng đơn dùng đơn vị khác đơn vị gốc khi ghi giá.** Mong đợi: giá ghi vào Price List đã quy đổi về đơn vị gốc. Test ở Task 8.
4. **Đơn báo giá đang ở "Chờ khách đồng ý" lúc chạy patch.** Mong đợi: khách đồng ý sau patch thì giá vẫn được ghi. Test ở Task 9.
5. **Hai dòng giá hợp lệ cùng lúc cho một mặt hàng (hai `valid_from`).** Mong đợi: lấy dòng `valid_from` mới nhất, tất định. Test ở Task 1.

---

## File Structure

| File | Trách nhiệm |
|---|---|
| Create `miyano_portal/bang_gia_khach.py` | Đọc giá, bảo đảm bảng giá riêng, ghi giá khách đã đồng ý. Hằng số nguồn giá. |
| Create `miyano_portal/tach_phieu.py` | Chia dòng theo có giá / chờ báo giá; tách phiếu khoa lúc gửi duyệt. |
| Create `miyano_portal/chot_bao_gia.py` | Ba hook `Sales Order` của luồng báo giá (§5.1, §5.4). |
| Create `miyano_portal/patches/v1_41/gia_theo_price_list.py` | Trường mới, bảng giá riêng, chép giá hợp đồng, đóng dấu đơn đang dở. |
| Modify `miyano_portal/dat_hang.py` | `_xay_don` theo luật mới. |
| Modify `miyano_portal/miyano_portal/doctype/portal_de_xuat_mua/portal_de_xuat_mua.py` (+ hai file `.json`) | Suy nguồn giá, đóng dấu giá, trường `ma_lan_dat`, `phieu_cung_lan_dat`. |
| Modify `miyano_portal/de_xuat_duyet.py` | Bỏ hạn mức; cảnh báo đổi giá; chặn khi mất giá. |
| Modify `miyano_portal/api/portal.py` | Danh mục, đặt hàng của quản lý, đặt lại, đồng ý báo giá, sửa số lượng; xoá ba endpoint. |
| Modify `miyano_portal/api/de_xuat.py` | Gửi duyệt có tách; duyệt cả hai; trả `canh_bao_gia`. |
| Modify `miyano_portal/portal_mua_le.py`, `miyano_portal/gia_hdnt.py`, `miyano_portal/hooks.py`, `miyano_portal/migration/import_erpnext.py` | Theo từng task. |
| Modify `frontend/src/views/LapPhieu.vue`, `ChiTietYeuCau.vue`, `Dashboard.vue`, `Profile.vue`, `components/chi-tiet/BangMatHang.vue` | Giao diện §7. |

---

### Task 1: `bang_gia_khach` — đọc giá và bảng giá riêng

**Files:**
- Create: `miyano_portal/bang_gia_khach.py`
- Test: `miyano_portal/tests/test_bang_gia_khach.py`

**Interfaces:**
- Produces:
  - `NGUON_BANG_GIA = "Bảng giá"`, `NGUON_BAO_GIA = "Báo giá"`, `LOAI_DON_BANG_GIA = "Theo bảng giá"`
  - `gia_bang_gia(customer: str, item_code: str) -> float | None`
  - `gia_bang_gia_nhieu(customer: str, item_codes: list[str]) -> dict[str, float]` (chỉ chứa mã CÓ giá)
  - `dam_bao_bang_gia_rieng(customer: str) -> str` (tên Price List)

- [ ] **Step 1: Viết test đỏ**

```python
"""Nguồn giá duy nhất của cổng: Price List của khách (spec 2026-10-09 §3, §5.3)."""

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import add_days, today

from miyano_portal import bang_gia_khach as bg
from miyano_portal.tests.fixtures_de_xuat import dung_fixture

BANG_A = "_TEST DX BGK A"


def _bang(ten):
	if not frappe.db.exists("Price List", ten):
		frappe.get_doc({
			"doctype": "Price List", "price_list_name": ten,
			"currency": "VND", "selling": 1, "enabled": 1,
		}).insert(ignore_permissions=True)
	return ten


def _gia(item, bang, rate, **them):
	return frappe.get_doc({
		"doctype": "Item Price", "item_code": item, "price_list": bang,
		"selling": 1, "price_list_rate": rate, **them,
	}).insert(ignore_permissions=True)


class TestBangGiaKhach(FrappeTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		f = dung_fixture(self)
		self.kh_a, self.kh_b, self.item = f.kh_a, f.kh_b, f.item
		for ten in frappe.get_all(
			"Item Price", filters={"item_code": self.item, "selling": 1}, pluck="name"
		):
			frappe.delete_doc("Item Price", ten, force=True)
		for kh in (self.kh_a, self.kh_b):
			frappe.db.set_value("Customer", kh, "default_price_list", None)
		for ten in frappe.get_all(
			"Price List", filters={"name": ["like", "Bảng giá _TEST DX%"]}, pluck="name"
		):
			frappe.delete_doc("Price List", ten, force=True)
		frappe.db.set_value("Customer", self.kh_a, "default_price_list", _bang(BANG_A))

	def test_co_gia_thi_tra_gia(self):
		_gia(self.item, BANG_A, 54000)
		self.assertEqual(bg.gia_bang_gia(self.kh_a, self.item), 54000.0)

	def test_khong_co_dong_gia_tra_None(self):
		self.assertIsNone(bg.gia_bang_gia(self.kh_a, self.item))

	def test_gia_0_la_chua_khai_gia(self):
		_gia(self.item, BANG_A, 0)
		self.assertIsNone(bg.gia_bang_gia(self.kh_a, self.item))

	def test_khach_chua_co_bang_gia_tra_None(self):
		self.assertIsNone(bg.gia_bang_gia(self.kh_b, self.item))

	def test_gia_cua_bang_khach_khac_khong_lo_sang(self):
		_gia(self.item, _bang("_TEST DX BGK KHAC"), 99000)
		self.assertIsNone(bg.gia_bang_gia(self.kh_a, self.item))

	def test_bo_qua_dong_gia_het_hieu_luc_va_chua_toi_ngay(self):
		_gia(self.item, BANG_A, 11000, valid_from=add_days(today(), -30),
		     valid_upto=add_days(today(), -1))
		_gia(self.item, BANG_A, 22000, valid_from=add_days(today(), 5))
		self.assertIsNone(bg.gia_bang_gia(self.kh_a, self.item))

	def test_hai_dong_hop_le_lay_valid_from_moi_nhat(self):
		_gia(self.item, BANG_A, 11000, valid_from=add_days(today(), -30))
		_gia(self.item, BANG_A, 22000, valid_from=add_days(today(), -2))
		self.assertEqual(bg.gia_bang_gia(self.kh_a, self.item), 22000.0)

	def test_bo_qua_dong_gia_theo_don_vi_khac_don_vi_goc(self):
		if not frappe.db.exists("UOM", "_TEST DX THUNG"):
			frappe.get_doc({"doctype": "UOM", "uom_name": "_TEST DX THUNG"}).insert()
		_gia(self.item, BANG_A, 900000, uom="_TEST DX THUNG")
		self.assertIsNone(bg.gia_bang_gia(self.kh_a, self.item))

	def test_tra_theo_lo_chi_chua_ma_co_gia(self):
		_gia(self.item, BANG_A, 54000)
		kq = bg.gia_bang_gia_nhieu(self.kh_a, [self.item, "KHONG-TON-TAI"])
		self.assertEqual(kq, {self.item: 54000.0})

	def test_bang_rieng_san_co_thi_giu_nguyen(self):
		self.assertEqual(bg.dam_bao_bang_gia_rieng(self.kh_a), BANG_A)

	def test_khach_chua_co_bang_thi_tao_va_gan(self):
		ten = bg.dam_bao_bang_gia_rieng(self.kh_b)
		self.assertEqual(ten, f"Bảng giá {self.kh_b}")
		self.assertEqual(
			frappe.db.get_value("Customer", self.kh_b, "default_price_list"), ten
		)
		self.assertEqual(
			frappe.db.get_value("Price List", ten, ["selling", "currency", "enabled"]),
			(1, "VND", 1),
		)

	def test_bang_dung_chung_thi_tach_va_chep_gia(self):
		_gia(self.item, BANG_A, 54000)
		frappe.db.set_value("Customer", self.kh_b, "default_price_list", BANG_A)
		ten = bg.dam_bao_bang_gia_rieng(self.kh_b)
		self.assertNotEqual(ten, BANG_A)
		self.assertEqual(bg.gia_bang_gia(self.kh_b, self.item), 54000.0)
		# Khách kia giữ nguyên bảng cũ — chỉ người được gọi mới bị tách.
		self.assertEqual(
			frappe.db.get_value("Customer", self.kh_a, "default_price_list"), BANG_A
		)

	def test_goi_hai_lan_khong_tao_bang_thu_hai(self):
		a = bg.dam_bao_bang_gia_rieng(self.kh_b)
		self.assertEqual(bg.dam_bao_bang_gia_rieng(self.kh_b), a)
```

- [ ] **Step 2: Chạy, thấy đỏ**

Run: `bench --site erptest.local run-tests --app miyano_portal --module miyano_portal.tests.test_bang_gia_khach`
Expected: lỗi import `cannot import name 'bang_gia_khach'`.

- [ ] **Step 3: Cài đặt**

```python
"""Giá của cổng khách hàng: MỘT nguồn — Price List của khách.

Spec `docs/superpowers/specs/2026-10-09-gia-theo-price-list-design.md` §3, §5.
Chủ đầu tư chốt 09/10/2026: cổng không còn định giá theo hợp đồng nguyên tắc.
Mọi nơi cần giá của một mặt hàng cho một khách đều hỏi module này — danh mục,
phiếu đề xuất, dựng đơn, khớp mã hàng gõ tay, đặt lại đơn cũ.
"""

import frappe
from frappe.utils import flt, getdate, today

NGUON_BANG_GIA = "Bảng giá"
NGUON_BAO_GIA = "Báo giá"
LOAI_DON_BANG_GIA = "Theo bảng giá"


def gia_bang_gia_nhieu(customer: str, item_codes: list[str]) -> dict[str, float]:
	"""`{item_code: giá}` cho những mã CÓ giá. Mã vắng mặt = chưa có giá.

	Một truy vấn cho cả lô. Chỉ nhận dòng theo đơn vị gốc (cổng luôn đặt theo
	`stock_uom`), còn hiệu lực hôm nay, giá dương. Nhiều dòng hợp lệ thì dòng
	`valid_from` mới nhất thắng; trùng thì `name` lớn hơn thắng — tất định.
	"""
	item_codes = [m for m in dict.fromkeys(item_codes or []) if m]
	if not item_codes:
		return {}
	bang = frappe.db.get_value("Customer", customer, "default_price_list")
	if not bang:
		return {}
	hom_nay = getdate(today())
	dong = frappe.db.sql(
		"""select ip.item_code, ip.price_list_rate
		   from `tabItem Price` ip
		   inner join `tabItem` it on it.name = ip.item_code
		   where ip.price_list = %(bang)s and ip.selling = 1
		     and ip.item_code in %(ma)s
		     and ip.price_list_rate > 0
		     and (ifnull(ip.uom, '') = '' or ip.uom = it.stock_uom)
		     and (ip.valid_from is null or ip.valid_from <= %(nay)s)
		     and (ip.valid_upto is null or ip.valid_upto >= %(nay)s)
		   order by ifnull(ip.valid_from, '1900-01-01') asc, ip.name asc""",
		{"bang": bang, "ma": tuple(item_codes), "nay": hom_nay},
		as_dict=True,
	)
	# Sắp tăng dần rồi ghi đè: dòng sau cùng (mới nhất) thắng.
	return {d.item_code: flt(d.price_list_rate) for d in dong}


def gia_bang_gia(customer: str, item_code: str) -> float | None:
	return gia_bang_gia_nhieu(customer, [item_code]).get(item_code)


def _khach_dung_bang(bang: str) -> list[str]:
	return frappe.get_all(
		"Customer", filters={"default_price_list": bang, "disabled": 0},
		pluck="name", order_by="name asc",
	)


def _ten_bang_moi(customer: str) -> str:
	ten = f"Bảng giá {customer}"
	if not frappe.db.exists("Price List", ten):
		return ten
	ma = frappe.db.get_value("Customer", customer, "custom_ma_ngan") or customer
	ten = f"Bảng giá {customer} ({ma})"
	i = 2
	while frappe.db.exists("Price List", ten):
		ten = f"Bảng giá {customer} ({ma}-{i})"
		i += 1
	return ten


def dam_bao_bang_gia_rieng(customer: str) -> str:
	"""Bảo đảm khách có Price List của RIÊNG mình; trả tên bảng.

	Chưa có → tạo "Bảng giá <tên khách>". Đang dùng chung với khách khác →
	tạo bảng riêng và chép mọi dòng giá bán của bảng chung sang. Ghi giá đàm
	phán của một bệnh viện vào bảng dùng chung là để bệnh viện khác thấy nó.
	"""
	bang = frappe.db.get_value("Customer", customer, "default_price_list")
	if bang and len(_khach_dung_bang(bang)) <= 1:
		return bang

	moi = frappe.get_doc({
		"doctype": "Price List", "price_list_name": _ten_bang_moi(customer),
		"currency": (frappe.db.get_value("Price List", bang, "currency") if bang else None)
		or "VND",
		"selling": 1, "enabled": 1,
	}).insert(ignore_permissions=True)

	if bang:
		for d in frappe.get_all(
			"Item Price", filters={"price_list": bang, "selling": 1},
			fields=["item_code", "uom", "price_list_rate", "currency",
			        "valid_from", "valid_upto"],
		):
			frappe.get_doc({
				"doctype": "Item Price", "price_list": moi.name,
				"selling": 1, "buying": 0, **d,
			}).insert(ignore_permissions=True)

	frappe.db.set_value("Customer", customer, "default_price_list", moi.name)
	return moi.name
```

- [ ] **Step 4: Chạy, thấy xanh**

Run: cùng lệnh Step 2. Expected: `Ran 13 tests … OK`.

- [ ] **Step 5: Commit**

```bash
git add miyano_portal/bang_gia_khach.py miyano_portal/tests/test_bang_gia_khach.py
git commit -m "feat(portal): bang_gia_khach - nguon gia duy nhat tu Price List cua khach"
```

---

### Task 2: Trường mới và patch `v1_41` (phần cấu trúc)

**Files:**
- Create: `miyano_portal/patches/v1_41/__init__.py` (rỗng), `miyano_portal/patches/v1_41/gia_theo_price_list.py`
- Modify: `miyano_portal/patches.txt` (thêm một dòng cuối)
- Modify: `miyano_portal/miyano_portal/doctype/portal_de_xuat_mua/portal_de_xuat_mua.json`, `miyano_portal/miyano_portal/doctype/portal_de_xuat_mua_item/portal_de_xuat_mua_item.json`
- Test: `miyano_portal/tests/test_patch_gia_theo_price_list.py`

**Interfaces:**
- Produces: `Sales Order Item.custom_nguon_gia` (Select `\nBảng giá\nBáo giá`), `Sales Order Item.custom_gia_khach_dong_y` (Currency), `Portal De Xuat Mua.ma_lan_dat` (Data), `Portal De Xuat Mua.phieu_cung_lan_dat` (Link), lựa chọn `Bảng giá` cho `Portal De Xuat Mua Item.nguon_gia`, lựa chọn `Theo bảng giá` cho `Sales Order.custom_loai_don`. Hàm `them_truong()` trong patch (Task 9 thêm phần dữ liệu vào `execute()`).

- [ ] **Step 1: Viết test đỏ**

```python
import frappe
from frappe.tests.utils import FrappeTestCase


class TestTruongGiaTheoPriceList(FrappeTestCase):
	def test_truong_moi_co_mat(self):
		soi = frappe.get_meta("Sales Order Item")
		self.assertEqual(
			soi.get_field("custom_nguon_gia").options.split("\n"),
			["", "Bảng giá", "Báo giá"],
		)
		self.assertEqual(soi.get_field("custom_gia_khach_dong_y").fieldtype, "Currency")
		dx = frappe.get_meta("Portal De Xuat Mua")
		self.assertEqual(dx.get_field("ma_lan_dat").fieldtype, "Data")
		self.assertEqual(dx.get_field("phieu_cung_lan_dat").options, "Portal De Xuat Mua")

	def test_lua_chon_moi_giu_ca_gia_tri_cu(self):
		nguon = frappe.get_meta("Portal De Xuat Mua Item").get_field("nguon_gia")
		self.assertEqual(
			nguon.options.split("\n"), ["Hợp đồng", "Bảng giá", "Chờ báo giá"]
		)
		loai = frappe.get_meta("Sales Order").get_field("custom_loai_don")
		self.assertIn("Theo bảng giá", loai.options.split("\n"))
		self.assertIn("Theo HĐNT", loai.options.split("\n"))
		self.assertIn("Mua lẻ", loai.options.split("\n"))
```

- [ ] **Step 2: Chạy, thấy đỏ** — Expected: `AttributeError: 'NoneType' object has no attribute 'options'`.

- [ ] **Step 3: Cài đặt**

Trong `portal_de_xuat_mua_item.json`, đổi `"options": "Hợp đồng\nChờ báo giá"` thành `"options": "Hợp đồng\nBảng giá\nChờ báo giá"`.

Trong `portal_de_xuat_mua.json`, thêm `"ma_lan_dat", "phieu_cung_lan_dat"` vào `field_order` ngay sau `"ma_de_xuat"`, và thêm vào `fields`:

```json
{"fieldname": "ma_lan_dat", "fieldtype": "Data", "label": "Mã lần đặt", "read_only": 1, "no_copy": 1,
 "description": "Hai phiếu tách ra từ cùng một lần đặt (một phiếu hàng có giá, một phiếu hàng chờ báo giá) mang chung mã này. Rỗng với phiếu không bị tách."},
{"fieldname": "phieu_cung_lan_dat", "fieldtype": "Link", "options": "Portal De Xuat Mua", "label": "Phiếu cùng lần đặt", "read_only": 1, "no_copy": 1}
```

`miyano_portal/patches/v1_41/gia_theo_price_list.py`:

```python
"""Giá theo Price List của khách (spec 2026-10-09 §6).

Phần CẤU TRÚC ở `them_truong()`. Phần DỮ LIỆU (bảng giá riêng, chép giá hợp
đồng, đóng dấu đơn đang dở) ở `chuyen_du_lieu()`.
"""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def them_truong():
	frappe.reload_doc("miyano_portal", "doctype", "portal_de_xuat_mua_item")
	frappe.reload_doc("miyano_portal", "doctype", "portal_de_xuat_mua")
	create_custom_fields({
		"Sales Order Item": [
			{
				"fieldname": "custom_nguon_gia", "label": "Nguồn giá",
				"fieldtype": "Select", "options": "\nBảng giá\nBáo giá",
				"insert_after": "rate", "read_only": 1, "no_copy": 1,
				"in_list_view": 1, "columns": 1,
				"description": "Bảng giá: đơn giá lấy từ Price List của khách. Báo giá: Miyano điền, ghi vào Price List khi khách đồng ý.",
			},
			{
				"fieldname": "custom_gia_khach_dong_y", "label": "Giá khách đã đồng ý",
				"fieldtype": "Currency", "insert_after": "custom_nguon_gia",
				"read_only": 1, "no_copy": 1,
			},
		],
	}, ignore_validate=True)

	ten = frappe.db.get_value(
		"Custom Field", {"dt": "Sales Order", "fieldname": "custom_loai_don"}, "name"
	)
	if ten:
		lua_chon = (frappe.db.get_value("Custom Field", ten, "options") or "").split("\n")
		if "Theo bảng giá" not in lua_chon:
			lua_chon.append("Theo bảng giá")
			frappe.db.set_value("Custom Field", ten, "options", "\n".join(lua_chon))
			frappe.clear_cache(doctype="Sales Order")


def chuyen_du_lieu():
	pass


def execute():
	them_truong()
	chuyen_du_lieu()
```

Thêm vào cuối `miyano_portal/patches.txt`: `miyano_portal.patches.v1_41.gia_theo_price_list`

- [ ] **Step 4: Áp patch và chạy test**

Run: `bench --site erptest.local execute miyano_portal.patches.v1_41.gia_theo_price_list.execute` rồi chạy `test_patch_gia_theo_price_list`. Expected: `Ran 2 tests … OK`.

- [ ] **Step 5: Commit**

```bash
git add miyano_portal/patches/v1_41 miyano_portal/patches.txt miyano_portal/miyano_portal/doctype/portal_de_xuat_mua miyano_portal/miyano_portal/doctype/portal_de_xuat_mua_item miyano_portal/tests/test_patch_gia_theo_price_list.py
git commit -m "feat(portal): truong dau nguon gia tren dong don va ma lan dat tren phieu"
```

---

### Task 3: Danh mục trả hai tầng theo Price List

**Files:**
- Modify: `miyano_portal/api/portal.py` — `portal_catalog_gop` (khoảng dòng 339–620); xoá `portal_contracts`, `portal_catalog`, `portal_catalog_ban_le`
- Test: viết lại `miyano_portal/tests/test_catalog_gop.py`, `miyano_portal/tests/test_gia_bang_gia_tren_danh_muc.py`; xoá các test của ba endpoint trong `test_portal_read.py` và lớp `TestCatalogBanLe` trong `test_e6_mua_le.py`

**Interfaces:**
- Consumes: `bang_gia_khach.gia_bang_gia_nhieu`
- Produces: mỗi dòng của `portal_catalog_gop` có đúng các khoá `item_code, item_name, dvt, boi_so, nhom_vat_tu, ten_thuong_goi, trang_thai_hang, tang, don_gia`. `tang ∈ {"bang_gia", "cho_bao_gia"}`; `don_gia` là `float` khi `bang_gia`, `None` khi `cho_bao_gia`. Tham số `contract` bị bỏ.

- [ ] **Step 1: Sửa test thành đỏ**

Thay toàn bộ thân lớp trong `test_gia_bang_gia_tren_danh_muc.py` (giữ `setUp`, `_xoa_gia`, `_dong`, và vòng `setattr` cuối file):

```python
	def test_hang_co_gia_la_tang_bang_gia(self):
		self._tao_gia(self.item_ngoai, self.price_list, 54000)
		row = self._dong(self.item_ngoai)
		self.assertEqual(row["tang"], "bang_gia")
		self.assertEqual(row["don_gia"], 54000.0)

	def test_hang_chua_co_gia_la_tang_cho_bao_gia(self):
		row = self._dong(self.item_ngoai)
		self.assertEqual(row["tang"], "cho_bao_gia")
		self.assertIsNone(row["don_gia"])

	def test_gia_0_la_cho_bao_gia(self):
		self._tao_gia(self.item_ngoai, self.price_list, 0)
		self.assertEqual(self._dong(self.item_ngoai)["tang"], "cho_bao_gia")

	def test_hang_thuoc_hop_dong_nhung_khong_co_gia_bang_gia_la_cho_bao_gia(self):
		"""Q3: hợp đồng không còn quyết định tầng. `setUp` đã đặt 111.000
		cho `item_hd` trong bảng giá — xoá nó thì hợp đồng một mình không
		cho ra giá nào."""
		self._xoa_gia(self.item_hd)
		row = self._dong(self.item_hd)
		self.assertEqual(row["tang"], "cho_bao_gia")
		self.assertIsNone(row["don_gia"])

	def test_hang_thuoc_hop_dong_lay_gia_BANG_GIA_khong_phai_gia_hop_dong(self):
		"""Hợp đồng khai 125.000, bảng giá 111.000 — cổng đọc bảng giá."""
		self._xoa_gia(self.item_hd)
		self._tao_gia(self.item_hd, self.price_list, 111000)
		self.assertEqual(self._dong(self.item_hd)["don_gia"], 111000.0)

	def test_dong_khong_con_khoa_hop_dong_va_han_muc(self):
		row = self._dong(self.item_ngoai)
		self.assertEqual(
			set(row), {"item_code", "item_name", "dvt", "boi_so", "nhom_vat_tu",
			           "ten_thuong_goi", "trang_thai_hang", "tang", "don_gia"},
		)

	def test_gia_bang_gia_cua_khach_khac_khong_lo_sang(self):
		bang_khac = "_TEST DX GOP PRICE KHAC"
		if not frappe.db.exists("Price List", bang_khac):
			frappe.get_doc({
				"doctype": "Price List", "price_list_name": bang_khac,
				"currency": "VND", "selling": 1, "enabled": 1,
			}).insert(ignore_permissions=True)
		self._tao_gia(self.item_ngoai, bang_khac, 99000)
		self.assertIsNone(self._dong(self.item_ngoai)["don_gia"])
```

Trong `test_catalog_gop.py`: xoá mọi test khẳng định `tang == "hop_dong"`, `blanket_order`, `total/used/remaining/khong_gioi_han`, thứ tự "hàng hợp đồng đứng trước" (QĐ-G10), và tham số `contract`. Giữ nguyên các test tìm kiếm, phân trang, bội số, tình trạng hàng, nhóm vật tư, nhà cung cấp, máy sử dụng, tên thường gọi, cách ly khoa. Thêm một test thay cho thứ tự cũ:

```python
	def test_thu_tu_thuan_theo_ten_khong_uu_tien_hang_hop_dong(self):
		frappe.set_user(self.user_a)
		out = portal_api.portal_catalog_gop(tu_khoa="GOPTEST", limit=200)
		ten = [r["item_name"] for r in out["rows"]]
		self.assertEqual(ten, sorted(ten, key=str.casefold))
```

- [ ] **Step 2: Chạy, thấy đỏ** — hai file trên. Expected: `'cho_bao_gia' != 'bang_gia'`, `KeyError`/khác tập khoá.

- [ ] **Step 3: Cài đặt**

Trong `portal_catalog_gop`:
1. Bỏ tham số `contract` khỏi chữ ký và xoá khối `if contract:` (kiểm sở hữu + lọc theo `Blanket Order Item`).
2. Xoá `thang_cuoc = nguon_gia_theo_ma_cho_khach(customer)`, `price_list = …`, `ma_hop_dong = sorted(thang_cuoc)`.
3. Thay toàn bộ khối `if ma_hop_dong: … else: …` (chia hai nửa) bằng:

```python
    tong = _dem(filters)
    rows = _trang(filters, start, limit)
```

4. Thay vòng dựng `out` bằng:

```python
    # Spec 2026-10-09 §3 — MỘT truy vấn giá cho cả trang; mã vắng mặt trong
    # dict = chưa có giá. Hợp đồng không còn được hỏi ở đây (Q3).
    gia_theo_ma = bang_gia_khach.gia_bang_gia_nhieu(
        customer, [r.item_code for r in rows]
    )
    out = []
    for r in rows:
        gia = gia_theo_ma.get(r.item_code)
        out.append({
            "item_code": r.item_code, "item_name": r.item_name, "dvt": r.stock_uom,
            # `0`/chưa khai đều là "không ràng buộc bội số" → `None`.
            "boi_so": int(r.custom_boi_so_dat or 0) or None,
            "nhom_vat_tu": r.get("custom_nhom_vat_tu") or None,
            "ten_thuong_goi": ten_goi_theo_ma.get(r.item_code, []),
            "trang_thai_hang": trang_thai_hang(r.item_code),
            "tang": "bang_gia" if gia is not None else "cho_bao_gia",
            "don_gia": gia,
        })
```

5. Thêm `from miyano_portal import bang_gia_khach` vào khối import đầu file.
6. Xoá ba hàm `portal_contracts`, `portal_catalog`, `portal_catalog_ban_le` cùng các hàm trợ giúp chỉ chúng dùng (kiểm bằng `grep -n "<ten_ham>(" miyano_portal -r --include=*.py | grep -v tests` trước khi xoá từng hàm trợ giúp). Viết lại docstring của `portal_catalog_gop` cho khớp hành vi mới, dẫn về spec.

- [ ] **Step 4: Chạy, thấy xanh** — `test_gia_bang_gia_tren_danh_muc`, `test_catalog_gop`, `test_portal_read`, `test_e6_mua_le`. Các test của ba endpoint đã xoá phải được gỡ khỏi `test_portal_read.py` (`test_contracts_and_catalog`, `test_contracts_expose_item_count`, `test_catalog_exposes_quota_and_group_fields`, `test_catalog_rejects_foreign_contract`) và `test_e6_mua_le.py` (lớp `TestCatalogBanLe`).

- [ ] **Step 5: Commit** — `feat(portal): danh muc dat hang phan tang theo Price List, bo tang hop dong`

---

### Task 4: `_xay_don` theo Price List

**Files:**
- Modify: `miyano_portal/dat_hang.py` — `_xay_don` (dòng 201–635), `_selling_price_list_mac_dinh` (xoá)
- Test: Create `miyano_portal/tests/test_xay_don_bang_gia.py`; viết lại `test_dat_hang_gop.py`, `test_e1_loi_co_cau_truc.py`, `test_e1_han_muc_khong_gioi_han.py`, `test_gia_tu_hop_dong.py`, `test_order_place.py` (hai test hạn mức), phần liên quan của `test_e1_thieu_gia_va_reorder.py` và `test_e1_dong_bo_gia_hdnt.py`

**Interfaces:**
- Consumes: `bang_gia_khach.gia_bang_gia_nhieu`, `dam_bao_bang_gia_rieng`, `NGUON_BANG_GIA`, `NGUON_BAO_GIA`, `LOAI_DON_BANG_GIA`
- Produces: `tao_sales_order(...)` giữ nguyên chữ ký và kiểu trả về. Đơn sinh ra: `selling_price_list` = bảng riêng của khách; mỗi dòng có `custom_nguon_gia`; không dòng nào có `blanket_order`; `custom_hdnt` rỗng; `custom_loai_don ∈ {"Theo bảng giá", "Mua lẻ"}`.

- [ ] **Step 1: Viết test đỏ** (`test_xay_don_bang_gia.py`)

```python
"""Dựng đơn theo Price List (spec 2026-10-09 §4.2)."""

import frappe
from frappe.tests.utils import FrappeTestCase

from miyano_portal import bang_gia_khach as bg
from miyano_portal import dat_hang
from miyano_portal.portal_mua_le import LOAI_DON_BAO_GIA
from miyano_portal.tests import test_catalog_gop as goc


class TestXayDonBangGia(FrappeTestCase):
	def setUp(self):
		goc.TestPortalCatalogGop.setUp(self)
		for ma in (self.item_ngoai, self.item_boi_so):
			for ten in frappe.get_all(
				"Item Price", filters={"item_code": ma, "selling": 1}, pluck="name"
			):
				frappe.delete_doc("Item Price", ten, force=True)
		self._tao_gia(self.item_ngoai, self.price_list, 54000)

	def tearDown(self):
		frappe.set_user("Administrator")

	def _dat(self, items, **them):
		kq = dat_hang.tao_sales_order(
			self.kh_a, items=items,
			request_id=frappe.generate_hash(length=12), **them,
		)
		return frappe.get_doc("Sales Order", kq["sales_order"])

	def test_dong_co_gia_lay_gia_bang_gia_va_dong_dau(self):
		so = self._dat([{"item_code": self.item_ngoai, "qty": 3}])
		d = so.items[0]
		self.assertEqual(float(d.rate), 54000.0)
		self.assertEqual(d.custom_nguon_gia, bg.NGUON_BANG_GIA)
		self.assertEqual(so.custom_loai_don, bg.LOAI_DON_BANG_GIA)

	def test_dong_chua_co_gia_la_bao_gia_gia_0(self):
		so = self._dat([{"item_code": self.item_boi_so, "qty": 10}])
		d = so.items[0]
		self.assertEqual(float(d.rate), 0.0)
		self.assertEqual(d.custom_nguon_gia, bg.NGUON_BAO_GIA)
		self.assertEqual(so.custom_loai_don, LOAI_DON_BAO_GIA)

	def test_don_luon_mang_bang_gia_cua_khach(self):
		so = self._dat([{"item_code": self.item_boi_so, "qty": 10}])
		self.assertEqual(so.selling_price_list, self.price_list)

	def test_khach_chua_co_bang_gia_van_dat_duoc_va_duoc_gan_bang_rieng(self):
		frappe.db.set_value("Customer", self.kh_a, "default_price_list", None)
		so = self._dat([{"item_code": self.item_ngoai, "qty": 1}])
		self.assertEqual(so.selling_price_list, f"Bảng giá {self.kh_a}")
		self.assertEqual(so.items[0].custom_nguon_gia, bg.NGUON_BAO_GIA)

	def test_dong_thuoc_hop_dong_khong_con_gan_lien_ket_hop_dong(self):
		so = self._dat([{"item_code": self.item_han_muc, "qty": 1}])
		self.assertFalse(so.items[0].get("blanket_order"))
		self.assertFalse(so.items[0].get("against_blanket_order"))
		self.assertFalse(so.get("custom_hdnt"))

	def test_dat_vuot_so_luong_hop_dong_khong_con_bi_chan(self):
		"""`item_het_hm` đã hết hạn mức trên hợp đồng A (fixture)."""
		so = self._dat([{"item_code": self.item_het_hm, "qty": 999}])
		self.assertEqual(float(so.items[0].qty), 999.0)

	def test_hop_dong_khai_gia_nhung_bang_gia_trong_thi_la_bao_gia(self):
		for ten in frappe.get_all(
			"Item Price", filters={"item_code": self.item_hd, "selling": 1}, pluck="name"
		):
			frappe.delete_doc("Item Price", ten, force=True)
		so = self._dat([{"item_code": self.item_hd, "qty": 1}])
		self.assertEqual(so.items[0].custom_nguon_gia, bg.NGUON_BAO_GIA)
		self.assertEqual(float(so.items[0].rate), 0.0)

	def test_hang_go_tay_lam_don_thanh_mua_le(self):
		so = self._dat(
			[{"item_code": self.item_ngoai, "qty": 1}],
			dat_ngoai=[{"ten_hang": "Kim luồn X", "dvt": "Cái", "so_luong": 5,
			            "khong_co_anh": 1}],
		)
		self.assertEqual(so.custom_loai_don, LOAI_DON_BAO_GIA)


for _ten, _ham in vars(goc.TestPortalCatalogGop).items():
	if _ten.startswith("_") and not _ten.startswith("__") and callable(_ham):
		if _ten not in vars(TestXayDonBangGia):
			setattr(TestXayDonBangGia, _ten, _ham)
```

- [ ] **Step 2: Chạy, thấy đỏ** — Expected: `AttributeError … custom_nguon_gia` rỗng / `'Theo HĐNT' != 'Theo bảng giá'` / lỗi hạn mức.

- [ ] **Step 3: Cài đặt** trong `_xay_don`

1. Đầu hàm, thay hai dòng `thang_cuoc = …`, `price_list = …` bằng:

```python
    # Spec 2026-10-09 §4.2 — giá và tầng của từng dòng đến từ Price List của
    # khách. Bảo đảm bảng riêng TRƯỚC khi tra: đơn phải mang đúng bảng đó
    # (mục 7.3), kể cả khi mọi dòng còn chờ báo giá.
    price_list = bang_gia_khach.dam_bao_bang_gia_rieng(customer)
    gia_theo_ma = bang_gia_khach.gia_bang_gia_nhieu(customer, list(aggregated))
```

2. Trong vòng dòng hàng, thay từ `bo_dong = thang_cuoc.get(item_code)` tới hết nhánh `hop_le.append({... "gan_hop_dong": bo_dong})` bằng:

```python
        gia = gia_theo_ma.get(item_code)
        hop_le.append({
            "item_code": item_code, "qty": qty,
            "rate": gia or 0,
            "nguon_gia": (
                bang_gia_khach.NGUON_BANG_GIA if gia
                else bang_gia_khach.NGUON_BAO_GIA
            ),
        })
```

3. Dòng giữ chỗ: `hop_le.append({"item_code": ITEM_GIU_CHO, "qty": 1, "rate": 0, "nguon_gia": None})`.
4. Thay khối chọn công ty bằng `company = resolve_ban_le_company(list(aggregated.keys()))` (giữ nguyên `frappe.throw` khi rỗng). Xoá `bo_tren_don`.
5. Thay ba dòng gán:

```python
    con_dong_chua_co_gia = bool(dong_dat_ngoai) or any(
        d["nguon_gia"] != bang_gia_khach.NGUON_BANG_GIA for d in hop_le
    )
    ...
    so.selling_price_list = price_list
    so.custom_hdnt = None
    so.custom_loai_don = (
        LOAI_DON_BAO_GIA if con_dong_chua_co_gia
        else bang_gia_khach.LOAI_DON_BANG_GIA
    )
```

6. Trong vòng `for d in hop_le:` dựng dòng:

```python
        dong = {
            "item_code": d["item_code"], "qty": d["qty"], "rate": d["rate"],
            "warehouse": item_warehouse, "delivery_date": delivery_date,
            "custom_nguon_gia": d["nguon_gia"],
            # Đặt CẢ HAI: `price_list_rate` là thứ ERPNext coi là nguồn khi
            # tính lại dòng. Dòng chờ báo giá để 0 tường minh, nếu không
            # `set_missing_item_details` tự điền hộ.
            "price_list_rate": d["rate"],
        }
        so.append("items", dong)
```

7. Xoá import không còn dùng: `nguon_gia_theo_ma_cho_khach`, `han_muc_con`, `ten_khoa_da_tieu`, `bao_thieu_gia`, `gia_hdnt`; thêm `from miyano_portal import bang_gia_khach`. Xoá `_selling_price_list_mac_dinh`. Viết lại docstring `_xay_don` theo bảng hai loại dòng của spec §3.2.

Dòng giữ chỗ có `nguon_gia = None` làm `con_dong_chua_co_gia` đúng (đơn toàn hàng gõ tay là `"Mua lẻ"`).

- [ ] **Step 4: Sửa các test cũ theo luật mới, chạy xanh**

| File | Việc |
|---|---|
| `test_e1_loi_co_cau_truc.py` | Xoá các test `vuot_han_muc` / `het_han_muc` / `thieu_gia`; giữ `ngay_giao_khong_hop_le`, `mat_hang_ngung_kinh_doanh`, `dat_ngoai_*`. |
| `test_e1_han_muc_khong_gioi_han.py` | Xoá file (mọi test nói về hạn mức và `against_blanket_order`). |
| `test_gia_tu_hop_dong.py` | Xoá các test "giá hợp đồng thắng Item Price" và `thieu_gia`; giữ test "bảng giá dùng chung" nhưng đổi kỳ vọng ở Task 9. |
| `test_dat_hang_gop.py` | Đổi kỳ vọng `"Theo HĐNT"` → `"Theo bảng giá"`; test giỏ trộn chuyển sang Task 6; xoá test lỗi vượt hạn mức. |
| `test_order_place.py` | Xoá `test_over_quota_rejected`, `test_duplicate_lines_aggregated_over_quota_rejected`. |
| `test_e1_thieu_gia_va_reorder.py` | Xoá các test `thieu_gia` của đường đặt hàng (phần reorder xử lý ở Task 10). |
| `test_e1_dong_bo_gia_hdnt.py` | `test_chua_khai_gia_o_dau_ca_thi_van_bao_thieu_gia` → đổi tên `…_thi_la_dong_cho_bao_gia`, khẳng định đơn tạo được với `rate == 0`. |

Mỗi test bị đảo kỳ vọng mang một dòng chú thích: `# Đảo theo spec 2026-10-09 (giá theo Price List), Q3.`

Run: tất cả file trên + `test_xay_don_bang_gia`. Expected: xanh.

- [ ] **Step 5: Commit** — `feat(portal): dung don theo Price List, bo han muc va lien ket hop dong`

---

### Task 5: Phiếu đề xuất — nguồn giá, đóng dấu giá, duyệt

**Files:**
- Modify: `miyano_portal/miyano_portal/doctype/portal_de_xuat_mua/portal_de_xuat_mua.py` — `_suy_nguon_gia` (1081–1173), `_dong_dau_gia` (385–467), `_nguon_gia_theo_ma` (xoá), hằng số
- Modify: `miyano_portal/de_xuat_duyet.py` — `_kiem_gia_doi`, `_kiem_han_muc` (xoá), `duyet_va_tao_don`
- Test: Create `miyano_portal/tests/test_phieu_bang_gia.py`; viết lại `test_nguon_gia_dong.py`, `test_han_muc_don_tron.py` (xoá file), phần 262 và 576–647 của `test_de_xuat_duyet.py`

**Interfaces:**
- Consumes: Task 1
- Produces: `NGUON_GIA_BANG_GIA = "Bảng giá"` trong module doctype; dòng phiếu có giá mang `nguon_gia == "Bảng giá"`, `blanket_order` rỗng; `duyet_va_tao_don` trả `canh_bao_gia: list[{"item_code", "gia_cu", "gia_moi", "ly_do": "gia_doi"}]`.

- [ ] **Step 1: Viết test đỏ** (`test_phieu_bang_gia.py`)

```python
"""Phiếu đề xuất theo Price List (spec 2026-10-09 §3.2, §4.3)."""

import frappe
from frappe.tests.utils import FrappeTestCase

from miyano_portal import de_xuat_duyet
from miyano_portal.tests import test_chi_tiet_gop as goc
from miyano_portal.tests.fixtures_de_xuat import dung_fixture

BANG = "_TEST DX PBG"


class TestPhieuBangGia(FrappeTestCase):
	_thanh_vien = goc.TestChiTietGopBackend._thanh_vien

	def setUp(self):
		frappe.set_user("Administrator")
		goc._don_phieu_cu()
		f = dung_fixture(self)
		self.kh_a, self.khoa_a, self.item = f.kh_a, f.khoa_huyethoc, f.item
		if not frappe.db.exists("Price List", BANG):
			frappe.get_doc({"doctype": "Price List", "price_list_name": BANG,
			                "currency": "VND", "selling": 1, "enabled": 1}).insert()
		frappe.db.set_value("Customer", self.kh_a, "default_price_list", BANG)
		self._dat_gia(None)
		self.quan_ly = self._thanh_vien("pbg.ql@demo.miyano", "Quản lý", None)
		self.nhan_vien = self._thanh_vien("pbg.nv@demo.miyano", "Nhân viên khoa", self.khoa_a)

	def tearDown(self):
		frappe.set_user("Administrator")

	def _dat_gia(self, rate):
		for ten in frappe.get_all(
			"Item Price", filters={"item_code": self.item, "selling": 1}, pluck="name"
		):
			frappe.delete_doc("Item Price", ten, force=True)
		if rate is not None:
			frappe.get_doc({"doctype": "Item Price", "item_code": self.item,
			                "price_list": BANG, "selling": 1,
			                "price_list_rate": rate}).insert()

	def _phieu(self, gui=True):
		doc = frappe.get_doc({
			"doctype": "Portal De Xuat Mua", "customer": self.kh_a,
			"khoa_phong": self.khoa_a, "ly_do_yeu_cau": "Hết hàng trong kho khoa",
			"items": [{"item_code": self.item, "so_luong_de_xuat": 5}],
		}).insert(ignore_permissions=True)
		frappe.db.set_value("Portal De Xuat Mua", doc.name, "owner", self.nhan_vien)
		doc.reload()
		if gui:
			doc.gui_duyet()
			doc.reload()
		return doc

	def test_dong_co_gia_la_nguon_bang_gia(self):
		self._dat_gia(54000)
		row = self._phieu(gui=False).items[0]
		self.assertEqual(row.nguon_gia, "Bảng giá")
		self.assertFalse(row.blanket_order)

	def test_dong_chua_co_gia_la_cho_bao_gia(self):
		self.assertEqual(self._phieu(gui=False).items[0].nguon_gia, "Chờ báo giá")

	def test_gui_duyet_dong_dau_don_gia_bang_gia(self):
		self._dat_gia(54000)
		self.assertEqual(float(self._phieu().items[0].don_gia), 54000.0)

	def test_duyet_canh_bao_khi_gia_doi_va_don_mang_gia_moi(self):
		self._dat_gia(54000)
		doc = self._phieu()
		self._dat_gia(60000)
		kq = de_xuat_duyet.duyet_va_tao_don(doc.name, self.quan_ly)
		self.assertEqual(kq["canh_bao_gia"], [{
			"item_code": self.item, "gia_cu": 54000.0, "gia_moi": 60000.0,
			"ly_do": "gia_doi",
		}])
		self.assertEqual(
			float(frappe.db.get_value(
				"Sales Order Item", {"parent": kq["sales_order"]}, "rate")),
			60000.0,
		)

	def test_duyet_bi_chan_khi_dong_bang_gia_mat_gia(self):
		self._dat_gia(54000)
		doc = self._phieu()
		self._dat_gia(None)
		with self.assertRaises(frappe.ValidationError) as ctx:
			de_xuat_duyet.duyet_va_tao_don(doc.name, self.quan_ly)
		self.assertIn(self.item, str(ctx.exception))
		self.assertEqual(
			frappe.db.get_value("Portal De Xuat Mua", doc.name, "trang_thai"),
			"Chờ duyệt",
		)

	def test_phieu_cho_bao_gia_vua_co_gia_thi_don_di_thang(self):
		doc = self._phieu()
		self._dat_gia(54000)
		kq = de_xuat_duyet.duyet_va_tao_don(doc.name, self.quan_ly)
		self.assertEqual(
			frappe.db.get_value("Sales Order", kq["sales_order"], "custom_loai_don"),
			"Theo bảng giá",
		)
```

- [ ] **Step 2: Chạy, thấy đỏ.**

- [ ] **Step 3: Cài đặt**

`portal_de_xuat_mua.py`:
- Thêm `NGUON_GIA_BANG_GIA = "Bảng giá"` cạnh `NGUON_GIA_HOP_DONG` (giữ hằng cũ cho dữ liệu cũ).
- Trong `_suy_nguon_gia`, thay `thang_cuoc = self._nguon_gia_theo_ma()` và thân vòng lặp bằng:

```python
		from miyano_portal import bang_gia_khach
		co_gia = bang_gia_khach.gia_bang_gia_nhieu(
			self.customer, [r.item_code for r in self.items]
		)
		for row in self.items:
			if dong_bang and row.name in da_khoa:
				continue
			row.blanket_order = None
			row.nguon_gia = (
				NGUON_GIA_BANG_GIA if row.item_code in co_gia
				else NGUON_GIA_CHO_BAO_GIA
			)
```

- Trong `_dong_dau_gia`, thay thân bằng:

```python
		from miyano_portal import bang_gia_khach
		self._suy_nguon_gia()
		gia = bang_gia_khach.gia_bang_gia_nhieu(
			self.customer, [r.item_code for r in self.items]
		)
		for row in self.items:
			if row.nguon_gia != NGUON_GIA_BANG_GIA:
				continue
			row.don_gia = gia.get(row.item_code) or 0
```

- Xoá `_nguon_gia_theo_ma`. Giữ `nguon_gia_theo_ma_cho_khach` ở module (vẫn được `gia_hdnt.dong_bo_khach` dùng — kiểm bằng grep; nếu không còn ai gọi thì xoá).

`de_xuat_duyet.py`:
- Xoá `_kiem_han_muc` và lời gọi `_kiem_han_muc(doc, dong)`; xoá import `han_muc_con`, `ten_khoa_da_tieu`, `nguon_gia_theo_ma_cho_khach`, `gia_hdnt`.
- Thay `_kiem_gia_doi` bằng:

```python
def _kiem_gia_doi(doc) -> list[dict]:
	"""Spec 2026-10-09 §4.3. So giá đã đóng dấu lúc gửi duyệt với giá Price
	List hiện hành. Dòng "Bảng giá" MẤT giá → chặn duyệt (không tự chuyển
	sang vòng báo giá: phiếu đã được tách theo loại lúc gửi). Giá ĐỔI → cảnh
	báo, đơn mang giá mới."""
	from miyano_portal import bang_gia_khach
	from miyano_portal.miyano_portal.doctype.portal_de_xuat_mua.portal_de_xuat_mua import (
		NGUON_GIA_BANG_GIA,
	)

	gia = bang_gia_khach.gia_bang_gia_nhieu(
		doc.customer, [r.item_code for r in doc.items]
	)
	mat_gia, canh_bao = [], []
	for row in doc.items:
		if row.nguon_gia != NGUON_GIA_BANG_GIA or not float(row.so_luong_duyet or 0):
			continue
		gia_moi = gia.get(row.item_code)
		if gia_moi is None:
			mat_gia.append(row.item_code)
			continue
		gia_cu = float(row.don_gia or 0)
		if gia_cu and gia_cu != float(gia_moi):
			canh_bao.append({
				"item_code": row.item_code, "gia_cu": gia_cu,
				"gia_moi": float(gia_moi), "ly_do": "gia_doi",
			})
	if mat_gia:
		frappe.throw(
			"Không duyệt được: " + ", ".join(mat_gia) + " không còn giá trong "
			"bảng giá. Từ chối phiếu để khoa gửi lại — các mặt hàng này sẽ "
			"chuyển sang chờ báo giá.",
			frappe.ValidationError,
		)
	return canh_bao
```

- Trong `duyet_va_tao_don`, bỏ `contract=doc.hdnt` khỏi lời gọi `tao_sales_order`.

- [ ] **Step 4: Sửa test cũ, chạy xanh**

`test_nguon_gia_dong.py`: thay mọi fixture "đưa mã vào hợp đồng để có nguồn Hợp đồng" bằng "đặt `Item Price` để có nguồn Bảng giá"; kỳ vọng `"Hợp đồng"` → `"Bảng giá"`, `blanket_order` luôn rỗng; xoá các test luật thắng cuộc giữa hai hợp đồng (Ruling P14) và kiểm hạn mức; giữ các test đóng băng dòng (`dong_bang`). Xoá `test_han_muc_don_tron.py`. Trong `test_de_xuat_duyet.py` xoá các test hạn mức lúc duyệt và `hop_dong_doi`.

- [ ] **Step 5: Commit** — `feat(portal): phieu de xuat suy nguon gia tu Price List, bo han muc luc duyet`

---

### Task 6: Tách giỏ trộn

**Files:**
- Create: `miyano_portal/tach_phieu.py`
- Modify: `miyano_portal/api/de_xuat.py` — `de_xuat_gui_duyet` (140–155)
- Modify: `miyano_portal/api/portal.py` — `portal_order_place` (674–749)
- Test: Create `miyano_portal/tests/test_tach_phieu.py`

**Interfaces:**
- Consumes: Task 1, 4, 5
- Produces:
  - `tach_phieu.chia_dong(customer, items: list[dict]) -> tuple[list[dict], list[dict]]` — `(co_gia, cho_bao_gia)`, mỗi phần tử giữ nguyên dict đầu vào (khoá `item_code`).
  - `tach_phieu.gui_duyet_co_tach(doc) -> list[Document]` — một hoặc hai phiếu đã ở "Chờ duyệt"; phiếu đầu là phiếu gốc.
  - `de_xuat_gui_duyet` trả `{"name", "ma_de_xuat", "phieu_cung_lan_dat": str | None}`.
  - `portal_order_place` trả thêm `"don": [{"sales_order", "de_xuat", "loai_don"}]` (1 hoặc 2 phần tử); `sales_order`/`de_xuat` cấp cao nhất là của phần tử đầu.

- [ ] **Step 1: Viết test đỏ**

```python
"""Tách giỏ trộn thành hai phiếu (spec 2026-10-09 §4.1)."""

import json

import frappe
from frappe.tests.utils import FrappeTestCase

from miyano_portal import tach_phieu
from miyano_portal.api import de_xuat, portal
from miyano_portal.tests import test_catalog_gop as goc


class TestTachPhieu(FrappeTestCase):
	def setUp(self):
		goc.TestPortalCatalogGop.setUp(self)
		for ma in (self.item_ngoai, self.item_boi_so):
			for ten in frappe.get_all(
				"Item Price", filters={"item_code": ma, "selling": 1}, pluck="name"
			):
				frappe.delete_doc("Item Price", ten, force=True)
		self._tao_gia(self.item_ngoai, self.price_list, 54000)   # có giá
		self.co_gia, self.chua_gia = self.item_ngoai, self.item_boi_so
		self.quan_ly = self._dam_bao_thanh_vien(
			"tach.ql@demo.miyano", self.kh_a, "Quản lý", None
		)

	def tearDown(self):
		frappe.set_user("Administrator")

	def _phieu_nhap(self, ma_hang, dat_ngoai=None):
		frappe.set_user(self.user_a)
		ten = de_xuat.de_xuat_tao_nhap()["name"]
		de_xuat.de_xuat_luu_nhap(
			ten,
			items=[{"item_code": m, "so_luong_de_xuat": 10} for m in ma_hang],
			dat_ngoai=dat_ngoai or [], ly_do_yeu_cau="Hết hàng trong kho khoa",
			ghi_chu="giao buổi sáng",
		)
		return ten

	def test_chia_dong(self):
		a, b = tach_phieu.chia_dong(
			self.kh_a, [{"item_code": self.co_gia}, {"item_code": self.chua_gia}]
		)
		self.assertEqual([d["item_code"] for d in a], [self.co_gia])
		self.assertEqual([d["item_code"] for d in b], [self.chua_gia])

	def test_phieu_chi_co_gia_khong_tach(self):
		kq = de_xuat.de_xuat_gui_duyet(self._phieu_nhap([self.co_gia]))
		self.assertIsNone(kq["phieu_cung_lan_dat"])
		self.assertFalse(frappe.db.get_value("Portal De Xuat Mua", kq["name"], "ma_lan_dat"))

	def test_phieu_chi_cho_bao_gia_khong_tach(self):
		kq = de_xuat.de_xuat_gui_duyet(self._phieu_nhap([self.chua_gia]))
		self.assertIsNone(kq["phieu_cung_lan_dat"])

	def test_phieu_tron_tach_thanh_hai(self):
		ten = self._phieu_nhap([self.co_gia, self.chua_gia])
		kq = de_xuat.de_xuat_gui_duyet(ten)
		frappe.set_user("Administrator")
		a = frappe.get_doc("Portal De Xuat Mua", kq["name"])
		b = frappe.get_doc("Portal De Xuat Mua", kq["phieu_cung_lan_dat"])
		self.assertEqual(a.name, ten)
		self.assertEqual([r.item_code for r in a.items], [self.co_gia])
		self.assertEqual([r.item_code for r in b.items], [self.chua_gia])
		self.assertEqual(a.trang_thai, "Chờ duyệt")
		self.assertEqual(b.trang_thai, "Chờ duyệt")
		self.assertTrue(a.ma_lan_dat)
		self.assertEqual(a.ma_lan_dat, b.ma_lan_dat)
		self.assertEqual(a.phieu_cung_lan_dat, b.name)
		self.assertEqual(b.phieu_cung_lan_dat, a.name)
		self.assertNotEqual(a.ma_de_xuat, b.ma_de_xuat)
		for f in ("khoa_phong", "ly_do_yeu_cau", "ghi_chu", "owner"):
			self.assertEqual(a.get(f), b.get(f), f)

	def test_hang_go_tay_di_theo_phieu_cho_bao_gia(self):
		ten = self._phieu_nhap(
			[self.co_gia],
			dat_ngoai=[{"ten_hang": "Kim luồn X", "dvt": "Cái", "so_luong": 5,
			            "khong_co_anh": 1}],
		)
		kq = de_xuat.de_xuat_gui_duyet(ten)
		frappe.set_user("Administrator")
		a = frappe.get_doc("Portal De Xuat Mua", kq["name"])
		b = frappe.get_doc("Portal De Xuat Mua", kq["phieu_cung_lan_dat"])
		self.assertEqual(len(a.dat_ngoai), 0)
		self.assertEqual(len(b.dat_ngoai), 1)
		self.assertEqual(len(b.items), 0)

	def test_loi_khi_gui_phieu_thu_hai_khong_de_lai_gi(self):
		ten = self._phieu_nhap(
			[self.co_gia],
			# Thiếu ảnh và không tích "không chụp được" → `gui_duyet` ném lỗi.
			dat_ngoai=[{"ten_hang": "Kim luồn X", "dvt": "Cái", "so_luong": 5}],
		)
		truoc = frappe.db.count("Portal De Xuat Mua", {"customer": self.kh_a})
		# Savepoint, KHÔNG `frappe.db.rollback()` trần: rollback trần cuốn
		# luôn fixture của cả class (FrappeTestCase chạy trong một giao dịch).
		# Trong request thật, Frappe rollback toàn bộ khi endpoint ném lỗi.
		frappe.db.savepoint("truoc_gui")
		with self.assertRaises(frappe.ValidationError):
			de_xuat.de_xuat_gui_duyet(ten)
		frappe.db.rollback(save_point="truoc_gui")
		frappe.set_user("Administrator")
		self.assertEqual(
			frappe.db.count("Portal De Xuat Mua", {"customer": self.kh_a}), truoc
		)
		self.assertEqual(
			frappe.db.get_value("Portal De Xuat Mua", ten, "trang_thai"), "Nháp"
		)

	def test_quan_ly_dat_gio_tron_ra_hai_don(self):
		frappe.set_user(self.quan_ly)
		rid = frappe.generate_hash(length=12)
		kq = portal.portal_order_place(
			items=json.dumps([{"item_code": self.co_gia, "qty": 2},
			                  {"item_code": self.chua_gia, "qty": 10}]),
			request_id=rid,
		)
		self.assertEqual([d["loai_don"] for d in kq["don"]], ["Theo bảng giá", "Mua lẻ"])
		self.assertEqual(kq["sales_order"], kq["don"][0]["sales_order"])
		frappe.set_user("Administrator")
		a, b = (frappe.get_doc("Portal De Xuat Mua", d["de_xuat"]) for d in kq["don"])
		self.assertEqual(a.ma_lan_dat, b.ma_lan_dat)
		self.assertEqual(a.phieu_cung_lan_dat, b.name)

	def test_quan_ly_gui_lai_cung_request_id_khong_sinh_don_thu_ba(self):
		frappe.set_user(self.quan_ly)
		rid = frappe.generate_hash(length=12)
		tham_so = dict(
			items=json.dumps([{"item_code": self.co_gia, "qty": 2},
			                  {"item_code": self.chua_gia, "qty": 10}]),
			request_id=rid,
		)
		lan1 = portal.portal_order_place(**tham_so)
		lan2 = portal.portal_order_place(**tham_so)
		self.assertEqual(
			[d["sales_order"] for d in lan1["don"]],
			[d["sales_order"] for d in lan2["don"]],
		)

	def test_quan_ly_dat_gio_mot_loai_giu_nguyen_request_id(self):
		frappe.set_user(self.quan_ly)
		rid = frappe.generate_hash(length=12)
		kq = portal.portal_order_place(
			items=json.dumps([{"item_code": self.co_gia, "qty": 2}]), request_id=rid,
		)
		self.assertEqual(len(kq["don"]), 1)
		self.assertEqual(
			frappe.db.get_value("Sales Order", kq["sales_order"], "custom_request_id"), rid
		)


for _ten, _ham in vars(goc.TestPortalCatalogGop).items():
	if _ten.startswith("_") and not _ten.startswith("__") and callable(_ham):
		if _ten not in vars(TestTachPhieu):
			setattr(TestTachPhieu, _ten, _ham)
```

- [ ] **Step 2: Chạy, thấy đỏ.**

- [ ] **Step 3: Cài đặt `tach_phieu.py`**

```python
"""Tách một lần đặt trộn thành hai phiếu (spec 2026-10-09 §4.1, quyết định Q6).

Hàng có giá trong Price List đi thẳng tới Miyano xác nhận; hàng chờ báo giá
đi vòng báo giá. Hai nhóm đi hai tốc độ khác nhau, nên mỗi nhóm là MỘT phiếu
và MỘT đơn — quan hệ một phiếu ↔ một đơn của cả hệ thống giữ nguyên.
"""

import frappe

from miyano_portal import bang_gia_khach

HAU_TO_GIA = ":gia"
HAU_TO_BAO_GIA = ":baogia"

# Thông tin đầu phiếu chép sang phiếu thứ hai.
_TRUONG_CHUNG = (
	"customer", "khoa_phong", "ngay_can", "dia_chi_giao", "ghi_chu",
	"ly_do_yeu_cau", "ten_don_hang", "hdnt",
)


def chia_dong(customer: str, items: list[dict]) -> tuple[list[dict], list[dict]]:
	co_gia_theo_ma = bang_gia_khach.gia_bang_gia_nhieu(
		customer, [d.get("item_code") for d in items]
	)
	co_gia = [d for d in items if d.get("item_code") in co_gia_theo_ma]
	cho_bao_gia = [d for d in items if d.get("item_code") not in co_gia_theo_ma]
	return co_gia, cho_bao_gia


def lien_ket(ten_a: str, ten_b: str, ma_lan_dat: str) -> None:
	frappe.db.set_value("Portal De Xuat Mua", ten_a, {
		"ma_lan_dat": ma_lan_dat, "phieu_cung_lan_dat": ten_b,
	}, update_modified=False)
	frappe.db.set_value("Portal De Xuat Mua", ten_b, {
		"ma_lan_dat": ma_lan_dat, "phieu_cung_lan_dat": ten_a,
	}, update_modified=False)


def gui_duyet_co_tach(doc) -> list:
	"""Gửi duyệt phiếu `doc`; nếu nó trộn hai loại hàng thì tách trước.

	Phiếu GỐC giữ hàng có giá. Phiếu MỚI nhận hàng chờ báo giá và mọi dòng gõ
	tay. Cả hai chạy trong giao dịch của request: lỗi ở bất kỳ bước nào thì
	Frappe rollback toàn bộ, không để lại phiếu mồ côi.
	"""
	co_gia, cho_bao_gia = chia_dong(doc.customer, [r.as_dict() for r in doc.items])
	co_nhom_bao_gia = bool(cho_bao_gia) or bool(doc.get("dat_ngoai"))
	if not (co_gia and co_nhom_bao_gia):
		doc.gui_duyet()
		return [doc]

	sach = ("name", "parent", "parenttype", "parentfield", "idx", "creation",
	        "modified", "modified_by", "owner", "docstatus")

	def _dong_moi(d):
		return {k: v for k, v in dict(d).items() if k not in sach}

	moi = frappe.get_doc({
		"doctype": "Portal De Xuat Mua", "trang_thai": "Nháp",
		**{f: doc.get(f) for f in _TRUONG_CHUNG},
		"items": [_dong_moi(d) for d in cho_bao_gia],
		"dat_ngoai": [_dong_moi(d.as_dict()) for d in (doc.get("dat_ngoai") or [])],
	}).insert(ignore_permissions=True)
	# Phiếu mới phải thuộc về người đã lập phiếu gốc: quyền gửi/thu hồi và
	# cột "người tạo" trên danh sách đều đọc `owner`.
	frappe.db.set_value("Portal De Xuat Mua", moi.name, "owner", doc.owner,
	                    update_modified=False)
	moi.reload()

	ma_co_gia = {d["item_code"] for d in co_gia}
	doc.set("items", [r for r in doc.items if r.item_code in ma_co_gia])
	doc.set("dat_ngoai", [])
	doc.save(ignore_permissions=True)

	doc.gui_duyet()
	moi.gui_duyet()
	lien_ket(doc.name, moi.name, doc.ma_de_xuat)
	doc.reload()
	moi.reload()
	return [doc, moi]
```

`api/de_xuat.py`, `de_xuat_gui_duyet` — thay hai dòng cuối:

```python
	from miyano_portal import tach_phieu

	ds = tach_phieu.gui_duyet_co_tach(doc)
	return {
		"name": ds[0].name, "ma_de_xuat": ds[0].ma_de_xuat,
		"phieu_cung_lan_dat": ds[1].name if len(ds) > 1 else None,
	}
```

`api/portal.py`, `portal_order_place` — thay từ `kq = dat_hang.tao_sales_order(` tới `return kq`:

```python
    from miyano_portal import tach_phieu

    ds_items = frappe.parse_json(items) if isinstance(items, str) else (items or [])
    ds_ngoai = (
        frappe.parse_json(dat_ngoai) if isinstance(dat_ngoai, str) else (dat_ngoai or [])
    )
    co_gia, cho_bao_gia = tach_phieu.chia_dong(customer, ds_items)
    # Spec 2026-10-09 §4.1 — giỏ trộn ra HAI đơn. Giỏ một loại giữ nguyên
    # `request_id` của client (tương thích với mọi đơn đã tạo trước đây).
    if co_gia and (cho_bao_gia or ds_ngoai):
        lo = [
            (co_gia, [], f"{request_id}{tach_phieu.HAU_TO_GIA}"),
            (cho_bao_gia, ds_ngoai, f"{request_id}{tach_phieu.HAU_TO_BAO_GIA}"),
        ]
    else:
        lo = [(ds_items, ds_ngoai, request_id)]

    don = []
    for lo_items, lo_ngoai, rid in lo:
        kq = dat_hang.tao_sales_order(
            customer, mode=mode, items=lo_items, dat_ngoai=lo_ngoai,
            po=po, delivery_date=delivery_date, note=note, address=address,
            request_id=rid, khoa_phong=khoa,
        )
        kq["de_xuat"] = _dam_bao_phieu_tu_duyet(
            customer=customer, khoa_phong=khoa, mode=mode, contract=None,
            dat_ngoai=lo_ngoai, delivery_date=delivery_date, address=address,
            note=note, request_id=rid, ten_don_hang=ten_don_hang,
            sales_order=kq["sales_order"], da_ton_tai=bool(kq.get("da_ton_tai")),
        )
        kq["loai_don"] = frappe.db.get_value(
            "Sales Order", kq["sales_order"], "custom_loai_don"
        )
        don.append(kq)

    if len(don) == 2 and don[0]["de_xuat"] and don[1]["de_xuat"]:
        ma = frappe.db.get_value("Portal De Xuat Mua", don[0]["de_xuat"], "ma_de_xuat")
        tach_phieu.lien_ket(don[0]["de_xuat"], don[1]["de_xuat"], ma or don[0]["de_xuat"])

    return {
        **don[0],
        "don": [
            {"sales_order": d["sales_order"], "de_xuat": d["de_xuat"],
             "loai_don": d["loai_don"]}
            for d in don
        ],
    }
```

Giữ nguyên phần kiểm `request_id` bắt buộc và kiểm vai trò ở đầu hàm. Tham số `contract` ở lại trong chữ ký (client cũ còn gửi) nhưng không còn được dùng; ghi điều đó vào docstring.

- [ ] **Step 4: Chạy xanh** — `test_tach_phieu`, `test_dat_hang_gop`, `test_order_place`, `test_de_xuat_endpoint`.

- [ ] **Step 5: Commit** — `feat(portal): tach gio tron thanh hai phieu, mot phieu mot don`

---

### Task 7: Ba chốt trên luồng báo giá

**Files:**
- Create: `miyano_portal/chot_bao_gia.py`
- Modify: `miyano_portal/hooks.py` — khối `"Sales Order"` trong `doc_events` (thêm vào danh sách `validate` và `before_submit`)
- Test: Create `miyano_portal/tests/test_chot_bao_gia.py`

**Interfaces:**
- Consumes: `portal_mua_le.di_vong_bao_gia`, `TRANG_THAI_CHO_KHACH`, `ITEM_GIU_CHO`; `bang_gia_khach.NGUON_BAO_GIA`
- Produces: `chot_bao_gia.kiem_chuyen_trang_thai(doc, method=None)` (validate), `chot_bao_gia.kiem_gia_khop_gia_da_dong_y(doc, method=None)` (before_submit)

- [ ] **Step 1: Viết test đỏ**

```python
"""Chốt của luồng báo giá (spec 2026-10-09 §5.1, §5.4)."""

import frappe
from frappe.model.workflow import apply_workflow
from frappe.tests.utils import FrappeTestCase

from miyano_portal import dat_hang
from miyano_portal.tests import test_catalog_gop as goc


class TestChotBaoGia(FrappeTestCase):
	def setUp(self):
		goc.TestPortalCatalogGop.setUp(self)
		for ma in (self.item_ngoai, self.item_boi_so):
			for ten in frappe.get_all(
				"Item Price", filters={"item_code": ma, "selling": 1}, pluck="name"
			):
				frappe.delete_doc("Item Price", ten, force=True)
		self._tao_gia(self.item_ngoai, self.price_list, 54000)

	def tearDown(self):
		frappe.set_user("Administrator")

	def _don(self, ma):
		kq = dat_hang.tao_sales_order(
			self.kh_a, items=[{"item_code": ma, "qty": 10}],
			request_id=frappe.generate_hash(length=12),
		)
		return frappe.get_doc("Sales Order", kq["sales_order"])

	def test_don_bao_gia_khong_gui_duyet_thang_duoc(self):
		so = self._don(self.item_boi_so)
		so.items[0].rate = 7000
		so.save()
		with self.assertRaises(frappe.ValidationError) as ctx:
			apply_workflow(so, "Gửi duyệt")
		self.assertIn("Gửi khách duyệt", str(ctx.exception))

	def test_don_theo_bang_gia_gui_duyet_thang_duoc(self):
		so = apply_workflow(self._don(self.item_ngoai), "Gửi duyệt")
		self.assertEqual(so.workflow_state, "Chờ Miyano xác nhận")

	def test_con_dong_gia_0_thi_chua_gui_khach_duoc(self):
		so = self._don(self.item_boi_so)
		with self.assertRaises(frappe.ValidationError) as ctx:
			apply_workflow(so, "Gửi khách duyệt")
		self.assertIn(self.item_boi_so, str(ctx.exception))

	def test_du_gia_thi_gui_khach_duoc(self):
		so = self._don(self.item_boi_so)
		so.items[0].rate = 7000
		so.save()
		so = apply_workflow(so, "Gửi khách duyệt")
		self.assertEqual(so.workflow_state, "Chờ khách đồng ý")

	def test_gia_khac_gia_khach_dong_y_thi_khong_xac_nhan_duoc(self):
		so = self._don(self.item_boi_so)
		so.items[0].rate = 7000
		so.save()
		so = apply_workflow(so, "Gửi khách duyệt")
		so = apply_workflow(so, "Khách đồng ý")
		frappe.db.set_value("Sales Order Item", so.items[0].name,
		                    "custom_gia_khach_dong_y", 7000)
		so.reload()
		so.items[0].rate = 9000
		with self.assertRaises(frappe.ValidationError) as ctx:
			so.submit()
		self.assertIn("gửi khách duyệt lại", str(ctx.exception))

	def test_quay_ve_cho_xac_nhan_thi_xoa_gia_da_dong_y(self):
		so = self._don(self.item_boi_so)
		so.items[0].rate = 7000
		so.save()
		so = apply_workflow(so, "Gửi khách duyệt")
		frappe.db.set_value("Sales Order Item", so.items[0].name,
		                    "custom_gia_khach_dong_y", 7000)
		so.reload()
		so = apply_workflow(so, "Khách không đồng ý")
		self.assertEqual(so.workflow_state, "Chờ xác nhận")
		self.assertEqual(float(so.items[0].custom_gia_khach_dong_y or 0), 0.0)


for _ten, _ham in vars(goc.TestPortalCatalogGop).items():
	if _ten.startswith("_") and not _ten.startswith("__") and callable(_ham):
		if _ten not in vars(TestChotBaoGia):
			setattr(TestChotBaoGia, _ten, _ham)
```

Trước khi viết, xác nhận tên hành động workflow bằng:
`grep -n '"action"' miyano_portal/setup/install_workflow.py miyano_portal/patches/v1_4/mo_rong_workflow_e2.py`. Nếu "Khách không đồng ý" đòi lý do ở hook `kiem_ly_do_tu_choi` hoặc hook tương tự, đặt trường lý do tương ứng trước khi gọi `apply_workflow` trong test cuối.

- [ ] **Step 2: Chạy, thấy đỏ.**

- [ ] **Step 3: Cài đặt `chot_bao_gia.py`**

```python
"""Chốt của luồng báo giá (spec 2026-10-09 §5.1, §5.4).

Giá báo chỉ vào Price List khi KHÁCH đồng ý (quyết định Q4). Ba chốt dưới đây
giữ cho điều đó không có đường vòng: đơn báo giá không đi tắt qua khách,
không gửi khách khi còn thiếu giá, và giá không đổi sau khi khách đã đồng ý.
"""

import frappe
from frappe.utils import flt

from miyano_portal.bang_gia_khach import NGUON_BAO_GIA
from miyano_portal.portal_mua_le import ITEM_GIU_CHO, TRANG_THAI_CHO_KHACH, di_vong_bao_gia

TT_CHO_XAC_NHAN = "Chờ xác nhận"
TT_CHO_MIYANO = "Chờ Miyano xác nhận"


def _trang_thai_truoc(doc) -> str | None:
	truoc = doc.get_doc_before_save()
	return truoc.get("workflow_state") if truoc else None


def kiem_chuyen_trang_thai(doc, method=None) -> None:
	if doc.is_new() or doc.get("custom_nguon_don") != "Client Portal":
		return
	truoc, nay = _trang_thai_truoc(doc), doc.get("workflow_state")
	if truoc == nay:
		return

	if nay == TT_CHO_MIYANO and truoc == TT_CHO_XAC_NHAN and di_vong_bao_gia(doc):
		frappe.throw(
			"Đơn có hàng chờ báo giá — dùng «Gửi khách duyệt» để khách đồng ý "
			"giá trước khi Miyano xác nhận.",
			frappe.ValidationError,
		)

	if nay == TRANG_THAI_CHO_KHACH:
		thieu = [
			d.item_code for d in doc.items
			if d.item_code != ITEM_GIU_CHO and flt(d.rate) <= 0
		]
		if thieu:
			frappe.throw(
				"Chưa gửi khách được — còn mặt hàng chưa có đơn giá: "
				+ ", ".join(thieu) + ".",
				frappe.ValidationError,
			)

	if nay == TT_CHO_XAC_NHAN:
		# Vòng đồng ý sau sẽ đóng dấu lại (xem `ghi_gia_da_dong_y`).
		for d in doc.items:
			d.custom_gia_khach_dong_y = 0


def kiem_gia_khop_gia_da_dong_y(doc, method=None) -> None:
	if doc.get("custom_nguon_don") != "Client Portal" or not di_vong_bao_gia(doc):
		return
	lech = [
		d.item_code for d in doc.items
		if d.get("custom_nguon_gia") == NGUON_BAO_GIA
		and flt(d.get("custom_gia_khach_dong_y")) > 0
		and flt(d.rate) != flt(d.custom_gia_khach_dong_y)
	]
	if lech:
		frappe.throw(
			"Đơn giá của " + ", ".join(lech) + " khác giá khách đã đồng ý — "
			"gửi khách duyệt lại trước khi xác nhận.",
			frappe.ValidationError,
		)
```

`hooks.py`: trong khối `"Sales Order"` của `doc_events`, thêm `"miyano_portal.chot_bao_gia.kiem_chuyen_trang_thai"` vào cuối danh sách `validate` và `"miyano_portal.chot_bao_gia.kiem_gia_khop_gia_da_dong_y"` vào cuối danh sách `before_submit`.

- [ ] **Step 4: Chạy xanh** — `test_chot_bao_gia`, `test_e2_workflow_va_accept`, `test_don_tron_bao_gia`, `test_e6_mua_le`. Test cũ nào gửi một đơn `"Mua lẻ"` qua "Gửi duyệt", hoặc gửi khách khi còn giá 0, phải được sửa để điền giá rồi đi "Gửi khách duyệt"; ghi chú `# Đảo theo spec 2026-10-09 §5.1.`

- [ ] **Step 5: Commit** — `feat(portal): ba chot tren luong bao gia`

---

### Task 8: Ghi giá vào Price List khi khách đồng ý

**Files:**
- Modify: `miyano_portal/bang_gia_khach.py` — thêm `ghi_gia_da_dong_y`
- Modify: `miyano_portal/api/portal.py` — `portal_order_accept`, nhánh `if action == "dong_y":` (khoảng dòng 3185)
- Test: Create `miyano_portal/tests/test_ghi_gia_da_dong_y.py`

**Interfaces:**
- Consumes: Task 1, 4, 7
- Produces: `bang_gia_khach.ghi_gia_da_dong_y(so) -> list[dict]` — mỗi phần tử `{"item_code", "gia_cu": float | None, "gia_moi": float}`. Ném lỗi khi ghi hỏng; người gọi bọc.

- [ ] **Step 1: Viết test đỏ**

```python
"""Ghi giá khách đã đồng ý vào Price List (spec 2026-10-09 §5.2)."""

from unittest.mock import patch

import frappe
from frappe.model.workflow import apply_workflow
from frappe.tests.utils import FrappeTestCase

from miyano_portal import bang_gia_khach as bg
from miyano_portal import dat_hang
from miyano_portal.api import portal
from miyano_portal.tests import test_catalog_gop as goc


class TestGhiGiaDaDongY(FrappeTestCase):
	def setUp(self):
		goc.TestPortalCatalogGop.setUp(self)
		for ma in (self.item_ngoai, self.item_boi_so):
			for ten in frappe.get_all(
				"Item Price", filters={"item_code": ma, "selling": 1}, pluck="name"
			):
				frappe.delete_doc("Item Price", ten, force=True)
		self.quan_ly = self._dam_bao_thanh_vien(
			"ghigia.ql@demo.miyano", self.kh_a, "Quản lý", None
		)

	def tearDown(self):
		frappe.set_user("Administrator")

	def _don_cho_khach(self, ma, rate):
		kq = dat_hang.tao_sales_order(
			self.kh_a, items=[{"item_code": ma, "qty": 10}],
			request_id=frappe.generate_hash(length=12),
		)
		so = frappe.get_doc("Sales Order", kq["sales_order"])
		so.items[0].rate = rate
		so.save()
		return apply_workflow(so, "Gửi khách duyệt")

	def _khach(self, so, action, **them):
		frappe.set_user(self.quan_ly)
		try:
			return portal.portal_order_accept(so.name, action, **them)
		finally:
			frappe.set_user("Administrator")

	def test_dong_y_tao_dong_gia_moi(self):
		so = self._don_cho_khach(self.item_boi_so, 7000)
		self._khach(so, "dong_y")
		self.assertEqual(bg.gia_bang_gia(self.kh_a, self.item_boi_so), 7000.0)

	def test_dong_y_cap_nhat_dong_gia_cu_khong_tao_dong_thu_hai(self):
		so = self._don_cho_khach(self.item_boi_so, 7000)
		# Giá xuất hiện SAU khi đơn đã tạo ở tầng chờ báo giá.
		self._tao_gia(self.item_boi_so, self.price_list, 5000)
		self._khach(so, "dong_y")
		self.assertEqual(bg.gia_bang_gia(self.kh_a, self.item_boi_so), 7000.0)
		self.assertEqual(frappe.db.count("Item Price", {
			"item_code": self.item_boi_so, "price_list": self.price_list, "selling": 1,
		}), 1)

	def test_dong_y_dong_dau_gia_khach_dong_y_tren_dong_don(self):
		so = self._don_cho_khach(self.item_boi_so, 7000)
		self._khach(so, "dong_y")
		self.assertEqual(float(frappe.db.get_value(
			"Sales Order Item", so.items[0].name, "custom_gia_khach_dong_y")), 7000.0)

	def test_khong_dong_y_khong_ghi_gi(self):
		so = self._don_cho_khach(self.item_boi_so, 7000)
		self._khach(so, "khong_dong_y", ly_do="Giá cao hơn nhà cung cấp hiện tại")
		self.assertIsNone(bg.gia_bang_gia(self.kh_a, self.item_boi_so))

	def test_quy_doi_ve_don_vi_goc(self):
		so = self._don_cho_khach(self.item_boi_so, 7000)
		frappe.db.set_value("Sales Order Item", so.items[0].name,
		                    {"conversion_factor": 10, "rate": 70000})
		self._khach(so, "dong_y")
		self.assertEqual(bg.gia_bang_gia(self.kh_a, self.item_boi_so), 7000.0)

	def test_khong_ghi_dong_bang_gia(self):
		self._tao_gia(self.item_ngoai, self.price_list, 54000)
		kq = dat_hang.tao_sales_order(
			self.kh_a,
			items=[{"item_code": self.item_ngoai, "qty": 1}],
			dat_ngoai=[{"ten_hang": "Kim X", "dvt": "Cái", "so_luong": 1,
			            "khong_co_anh": 1}],
			request_id=frappe.generate_hash(length=12),
		)
		so = frappe.get_doc("Sales Order", kq["sales_order"])
		self.assertEqual(
			[d for d in bg.ghi_gia_da_dong_y(so) if d["item_code"] == self.item_ngoai], []
		)

	def test_de_lai_dau_vet_tren_don(self):
		so = self._don_cho_khach(self.item_boi_so, 7000)
		self._khach(so, "dong_y")
		noi_dung = " ".join(frappe.get_all(
			"Comment", filters={"reference_doctype": "Sales Order",
			                    "reference_name": so.name}, pluck="content"))
		self.assertIn(self.item_boi_so, noi_dung)
		self.assertIn("7.000", noi_dung.replace(",", "."))

	def test_loi_ghi_gia_khong_lam_hong_viec_dong_y(self):
		so = self._don_cho_khach(self.item_boi_so, 7000)
		with patch.object(bg, "ghi_gia_da_dong_y", side_effect=RuntimeError("hong")):
			kq = self._khach(so, "dong_y")
		self.assertEqual(kq["trang_thai_moi"], "Chờ Miyano xác nhận")
		self.assertTrue(frappe.db.exists("Error Log", {
			"reference_doctype": "Sales Order", "reference_name": so.name,
		}))
		frappe.db.delete("Error Log", {"reference_name": so.name})


for _ten, _ham in vars(goc.TestPortalCatalogGop).items():
	if _ten.startswith("_") and not _ten.startswith("__") and callable(_ham):
		if _ten not in vars(TestGhiGiaDaDongY):
			setattr(TestGhiGiaDaDongY, _ten, _ham)
```

- [ ] **Step 2: Chạy, thấy đỏ.**

- [ ] **Step 3: Cài đặt**

Thêm vào `bang_gia_khach.py`:

```python
def ghi_gia_da_dong_y(so) -> list[dict]:
	"""Ghi đơn giá các dòng "Báo giá" của `so` vào Price List của khách.

	Gọi SAU khi khách đã đồng ý. Chỉ dòng mang dấu "Báo giá" và có giá dương;
	dòng "Bảng giá" đã là giá của bảng rồi. Giá ghi theo đơn vị gốc.
	"""
	from miyano_portal.portal_mua_le import ITEM_GIU_CHO

	bang = dam_bao_bang_gia_rieng(so.customer)
	tien_te = frappe.db.get_value("Price List", bang, "currency") or "VND"
	theo_ma: dict[str, float] = {}
	trung = set()
	for d in so.items:
		if d.item_code == ITEM_GIU_CHO or d.get("custom_nguon_gia") != NGUON_BAO_GIA:
			continue
		if flt(d.rate) <= 0:
			continue
		gia = flt(d.rate) / (flt(d.conversion_factor) or 1)
		if d.item_code in theo_ma and theo_ma[d.item_code] != gia:
			trung.add(d.item_code)
		theo_ma[d.item_code] = gia          # dòng sau cùng thắng
		frappe.db.set_value("Sales Order Item", d.name, "custom_gia_khach_dong_y",
		                    flt(d.rate), update_modified=False)

	ket_qua = []
	for item_code, gia in theo_ma.items():
		dvt = frappe.db.get_value("Item", item_code, "stock_uom")
		ten = frappe.db.sql(
			"""select name, price_list_rate from `tabItem Price`
			   where item_code = %s and price_list = %s and selling = 1
			     and (ifnull(uom, '') = '' or uom = %s)
			   order by ifnull(valid_from, '1900-01-01') desc, name desc limit 1""",
			(item_code, bang, dvt), as_dict=True,
		)
		if ten:
			gia_cu = flt(ten[0].price_list_rate)
			frappe.db.set_value("Item Price", ten[0].name, {
				"price_list_rate": gia, "valid_from": today(), "valid_upto": None,
			})
		else:
			gia_cu = None
			frappe.get_doc({
				"doctype": "Item Price", "item_code": item_code, "price_list": bang,
				"selling": 1, "buying": 0, "uom": dvt, "currency": tien_te,
				"price_list_rate": gia, "valid_from": today(),
			}).insert(ignore_permissions=True)
		ket_qua.append({"item_code": item_code, "gia_cu": gia_cu, "gia_moi": gia})

	if ket_qua:
		dong = [
			f"{d['item_code']}: "
			f"{frappe.utils.fmt_money(d['gia_cu'], currency=tien_te) if d['gia_cu'] else 'chưa có'}"
			f" → {frappe.utils.fmt_money(d['gia_moi'], currency=tien_te)}"
			for d in ket_qua
		]
		ghi_chu = f"[Portal] Ghi giá khách đã đồng ý vào {bang} — " + "; ".join(dong)
		if trung:
			ghi_chu += (
				". Lưu ý: " + ", ".join(sorted(trung))
				+ " có nhiều dòng khác giá trên đơn, đã lấy dòng sau cùng."
			)
		so.add_comment("Comment", ghi_chu)
	return ket_qua
```

`api/portal.py`, trong `portal_order_accept`, ngay sau `cap_nhat_yeu_cau_goc(so, "Đã chuyển thành đơn")`:

```python
        # Spec 2026-10-09 §5.2 — giá khách vừa đồng ý thành giá thường trực
        # trong Price List của họ. Bọc lỗi CỐ Ý: việc đồng ý đã thành công,
        # một trục trặc ở bảng giá không được biến nó thành lỗi cho khách.
        if di_vong_bao_gia(so):
            try:
                so.reload()
                bang_gia_khach.ghi_gia_da_dong_y(so)
            except Exception:
                frappe.log_error(
                    title=f"Không ghi được giá đã đồng ý của đơn {so.name} vào Price List",
                    message=frappe.get_traceback(with_context=True),
                    reference_doctype="Sales Order", reference_name=so.name,
                )
```

Lời gọi phải đi qua tên module (`bang_gia_khach.ghi_gia_da_dong_y`) để test `patch.object` bắt được. Comment của `ghi_gia_da_dong_y` do người dùng cổng tạo; nếu `add_comment` ném `PermissionError` dưới role `Customer`, chạy nó bằng `frappe.get_doc({...Comment...}).insert(ignore_permissions=True)` thay vì `so.add_comment`.

- [ ] **Step 4: Chạy xanh** — `test_ghi_gia_da_dong_y`, `test_chot_bao_gia`, `test_e2_workflow_va_accept`.

- [ ] **Step 5: Commit** — `feat(portal): ghi gia khach da dong y vao Price List`

---

### Task 9: Chuyển đổi dữ liệu và đồng bộ từ hợp đồng

**Files:**
- Modify: `miyano_portal/patches/v1_41/gia_theo_price_list.py` — `chuyen_du_lieu`
- Modify: `miyano_portal/gia_hdnt.py` — `dong_bo` (212–254); xoá `gia_dong_hop_dong`
- Modify: `miyano_portal/migration/import_erpnext.py` — khoảng dòng 322–345
- Test: thêm vào `miyano_portal/tests/test_patch_gia_theo_price_list.py`; sửa `test_e1_dong_bo_gia_hdnt.py`, `test_gia_tu_hop_dong.py`, `test_migration.py`

**Interfaces:**
- Consumes: Task 1, 2
- Produces: `chuyen_du_lieu()` chạy lại nhiều lần cho cùng kết quả.

- [ ] **Step 1: Viết test đỏ** (thêm lớp vào `test_patch_gia_theo_price_list.py`)

```python
from miyano_portal import bang_gia_khach as bg
from miyano_portal import dat_hang
from miyano_portal.patches.v1_41 import gia_theo_price_list as patch_moi
from miyano_portal.tests import test_catalog_gop as goc


class TestChuyenDuLieu(FrappeTestCase):
	def setUp(self):
		goc.TestPortalCatalogGop.setUp(self)

	def tearDown(self):
		frappe.set_user("Administrator")

	def test_khach_dung_chung_bang_duoc_tach(self):
		frappe.db.set_value("Customer", self.kh_b, "default_price_list", self.price_list)
		patch_moi.chuyen_du_lieu()
		a = frappe.db.get_value("Customer", self.kh_a, "default_price_list")
		b = frappe.db.get_value("Customer", self.kh_b, "default_price_list")
		self.assertNotEqual(a, b)

	def test_gia_hop_dong_duoc_chep_sang_bang_gia(self):
		"""Hợp đồng A khai 125.000 cho `item_hd`; xoá dòng giá để mô phỏng
		khách chỉ có giá nhờ hợp đồng (ca của Minh Đức)."""
		for ten in frappe.get_all(
			"Item Price", filters={"item_code": self.item_hd, "selling": 1}, pluck="name"
		):
			frappe.delete_doc("Item Price", ten, force=True)
		patch_moi.chuyen_du_lieu()
		self.assertEqual(bg.gia_bang_gia(self.kh_a, self.item_hd), 125000.0)

	def test_chay_hai_lan_khong_doi_ket_qua(self):
		patch_moi.chuyen_du_lieu()
		truoc = frappe.db.count("Item Price", {"selling": 1})
		bang = frappe.db.get_value("Customer", self.kh_a, "default_price_list")
		patch_moi.chuyen_du_lieu()
		self.assertEqual(frappe.db.count("Item Price", {"selling": 1}), truoc)
		self.assertEqual(
			frappe.db.get_value("Customer", self.kh_a, "default_price_list"), bang
		)

	def test_don_bao_gia_dang_do_duoc_dong_dau(self):
		kq = dat_hang.tao_sales_order(
			self.kh_a, items=[{"item_code": self.item_boi_so, "qty": 10}],
			request_id=frappe.generate_hash(length=12),
		)
		dong = frappe.db.get_value("Sales Order Item", {"parent": kq["sales_order"]}, "name")
		frappe.db.set_value("Sales Order Item", dong, "custom_nguon_gia", None)
		patch_moi.chuyen_du_lieu()
		self.assertEqual(
			frappe.db.get_value("Sales Order Item", dong, "custom_nguon_gia"), "Báo giá"
		)


for _ten, _ham in vars(goc.TestPortalCatalogGop).items():
	if _ten.startswith("_") and not _ten.startswith("__") and callable(_ham):
		if _ten not in vars(TestChuyenDuLieu):
			setattr(TestChuyenDuLieu, _ten, _ham)
```

- [ ] **Step 2: Chạy, thấy đỏ.**

- [ ] **Step 3: Cài đặt**

`chuyen_du_lieu` trong patch:

```python
def chuyen_du_lieu():
	from miyano_portal import bang_gia_khach, gia_hdnt

	khach = frappe.get_all("Customer", filters={"disabled": 0}, pluck="name")
	# 1. Bảng giá riêng cho MỌI khách — phải xong trước bước 2, vì `dong_bo`
	#    ghi vào `default_price_list` hiện hành.
	for kh in khach:
		bang_gia_khach.dam_bao_bang_gia_rieng(kh)

	# 2. Chép giá từ hợp đồng còn hiệu lực. Nhiều khách chỉ có giá nhờ hợp
	#    đồng; bỏ bước này thì hàng của họ rơi về "chờ báo giá".
	co_hop_dong = frappe.get_all(
		"Blanket Order",
		filters={"blanket_order_type": "Selling", "docstatus": 1},
		pluck="customer", distinct=True,
	)
	for kh in co_hop_dong:
		if kh:
			gia_hdnt.dong_bo_khach(kh)

	# 3. Đơn báo giá đang dở: đóng dấu "Báo giá" để khi khách đồng ý thì giá
	#    vẫn được ghi (dòng cũ có dấu rỗng, `ghi_gia_da_dong_y` bỏ qua chúng).
	frappe.db.sql(
		"""update `tabSales Order Item` soi
		   inner join `tabSales Order` so on so.name = soi.parent
		   set soi.custom_nguon_gia = 'Báo giá'
		   where so.docstatus = 0
		     and so.custom_nguon_don = 'Client Portal'
		     and so.custom_loai_don = 'Mua lẻ'
		     and so.workflow_state in ('Chờ xác nhận', 'Chờ khách đồng ý')
		     and ifnull(soi.custom_nguon_gia, '') = ''
		     and ifnull(soi.blanket_order, '') = ''
		     and soi.item_code != 'HANG-DAT-NGOAI'"""
	)
```

`gia_hdnt.dong_bo`: thay toàn bộ khối từ `bang_gia = frappe.db.get_value("Customer", …)` tới hết nhánh `if not bang_gia: … return ket_qua` bằng:

```python
    # Spec 2026-10-09 §5.3 (thay Ruling P32) — không còn TỪ CHỐI khi khách
    # chưa có bảng hoặc đang dùng chung bảng: tách/tạo bảng riêng rồi ghi.
    from miyano_portal import bang_gia_khach
    bang_gia = bang_gia_khach.dam_bao_bang_gia_rieng(doc.customer)
```

Xoá `gia_dong_hop_dong` và `con_hieu_luc` nếu grep không còn người gọi ngoài test (`grep -rn "gia_dong_hop_dong\|con_hieu_luc(" miyano_portal --include=*.py | grep -v tests`). Cập nhật docstring đầu file: thêm khối "09/10/2026" nói cổng không còn đọc giá hợp đồng; `dong_bo` là thứ duy nhất còn lại của module.

`migration/import_erpnext.py`: bỏ việc gán `Customer.default_price_list = "HĐNT-<số hợp đồng>"`. Thay bằng: sau khi nhập hợp đồng của một khách, gọi `bang_gia_khach.dam_bao_bang_gia_rieng(customer)` rồi ghi các dòng giá hợp đồng vào bảng đó theo cùng khoá upsert `{item_code, price_list, selling: 1}`; bỏ qua dòng `unit_price <= 0` (hiện đang tạo dòng giá 0).

- [ ] **Step 4: Sửa test cũ, chạy xanh**

`test_e1_dong_bo_gia_hdnt.py` và `test_gia_tu_hop_dong.py`: các test "khách chưa có bảng giá → không ghi, có `ly_do`" và "bảng dùng chung → không ghi" đảo thành "bảng riêng được tạo/tách và giá được ghi". `test_migration.py`: kỳ vọng `default_price_list` là `Bảng giá <tên khách>`.

Chạy patch thật trên site và kiểm ca Minh Đức:

```bash
bench --site erptest.local execute miyano_portal.patches.v1_41.gia_theo_price_list.execute
bench --site erptest.local execute miyano_portal.bang_gia_khach.gia_bang_gia_nhieu --kwargs "{'customer': 'Bệnh viện Đa khoa Minh Đức (DEMO)', 'item_codes': ['MYN-SYR-10', 'MYN-GLOVE-M', 'MYN-ALT']}"
```

Expected: `{'MYN-SYR-10': 88000.0, 'MYN-GLOVE-M': 95000.0, 'MYN-ALT': 1250000.0}`.

- [ ] **Step 5: Commit** — `feat(portal): patch v1_41 chuyen du lieu sang gia theo Price List`

---

### Task 10: Các đường phụ — khớp mã hàng gõ tay, đặt lại, sửa số lượng

**Files:**
- Modify: `miyano_portal/portal_mua_le.py` — `_gop_hoac_them_dong_hang` (715–826) và nơi gọi nó trong `chuyen_dong_dat_ngoai_thanh_hang`
- Modify: `miyano_portal/api/portal.py` — `portal_reorder` (3002–3080), `portal_order_sua_so_luong` (khối đặt `i.rate = 0`, khoảng dòng 3410–3422)
- Test: sửa `test_khop_ma_dat_ngoai.py`, `test_e1_thieu_gia_va_reorder.py`, phần sửa số lượng của `test_e6_mua_le.py`

**Interfaces:**
- Consumes: Task 1
- Produces: `portal_reorder` trả `{"gio_hang": [{"item_code", "item_name", "uom", "qty", "tang", "gia_hien_hanh": float | None}], "bi_loai": [{"item_code", "ly_do": "mat_hang_ngung_kinh_doanh"}]}`.

- [ ] **Step 1: Sửa test thành đỏ**

`test_khop_ma_dat_ngoai.py`: đảo `test_hang_ngoai_hop_dong_khong_nhat_gia_cu_trong_bang_gia` thành:

```python
	def test_ma_khop_co_gia_bang_gia_thi_dong_nhan_gia_do(self):
		# Đảo theo spec 2026-10-09 §4.4: mã khớp đã có giá trong Price List
		# của khách thì dòng tự nhận giá, không bắt nhân viên điền tay.
		self._tao_gia(self.item_khop, self.price_list, 54000)
		so = self._khop(self.item_khop)
		dong = next(d for d in so.items if d.item_code == self.item_khop)
		self.assertEqual(float(dong.rate), 54000.0)
		self.assertEqual(dong.custom_nguon_gia, "Bảng giá")

	def test_ma_khop_chua_co_gia_la_dong_bao_gia(self):
		so = self._khop(self.item_khop)
		dong = next(d for d in so.items if d.item_code == self.item_khop)
		self.assertEqual(float(dong.rate), 0.0)
		self.assertEqual(dong.custom_nguon_gia, "Báo giá")
```

(dùng tên fixture/helper sẵn có của file; nếu file không có `_khop` thì dùng đúng chuỗi thao tác mà test gốc đang làm để khớp mã.) Xoá các test khẳng định `blanket_order` được gắn khi khớp mã.

`test_e1_thieu_gia_va_reorder.py`, thay các test loại trừ bằng:

```python
	def test_reorder_dua_ca_hang_chua_co_gia_vao_gio(self):
		kq = portal.portal_reorder(self.don_cu)
		theo_ma = {d["item_code"]: d for d in kq["gio_hang"]}
		self.assertEqual(theo_ma[self.item_co_gia]["tang"], "bang_gia")
		self.assertEqual(theo_ma[self.item_chua_gia]["tang"], "cho_bao_gia")
		self.assertIsNone(theo_ma[self.item_chua_gia]["gia_hien_hanh"])
		self.assertEqual(kq["bi_loai"], [])

	def test_reorder_loai_hang_ngung_kinh_doanh(self):
		frappe.db.set_value("Item", self.item_co_gia, "disabled", 1)
		kq = portal.portal_reorder(self.don_cu)
		self.assertEqual(
			kq["bi_loai"],
			[{"item_code": self.item_co_gia, "ly_do": "mat_hang_ngung_kinh_doanh"}],
		)
```

Thêm vào lớp sửa số lượng của `test_e6_mua_le.py`:

```python
	def test_sua_so_luong_dong_bang_gia_giu_gia_bang_gia(self):
		# Spec 2026-10-09 §4.4: dòng "Bảng giá" đọc lại giá Price List,
		# không về 0 như dòng "Báo giá".
		dong = next(d for d in self.so.items if d.custom_nguon_gia == "Bảng giá")
		portal.portal_order_sua_so_luong(
			self.so.name, json.dumps({"items": [{"item_code": dong.item_code, "qty": 7}]})
		)
		self.so.reload()
		moi = next(d for d in self.so.items if d.item_code == dong.item_code)
		self.assertEqual(float(moi.qty), 7.0)
		self.assertGreater(float(moi.rate), 0)
```

(dựng `self.so` có một dòng "Bảng giá" bằng cách để một dòng "Báo giá" nhận giá Price List sau khi tạo đơn, đúng ca §4.3; đặt `custom_nguon_gia` của dòng đó thành "Bảng giá" như `_gop_hoac_them_dong_hang` sẽ làm.)

- [ ] **Step 2: Chạy, thấy đỏ.**

- [ ] **Step 3: Cài đặt**

`_gop_hoac_them_dong_hang`: đổi chữ ký thành `(doc, item_code: str, qty: float)`; thay phần tra hợp đồng bằng:

```python
    from miyano_portal import bang_gia_khach

    gia = bang_gia_khach.gia_bang_gia(doc.customer, item_code)
    rate = flt(gia)
    nguon = bang_gia_khach.NGUON_BANG_GIA if gia else bang_gia_khach.NGUON_BAO_GIA
```

Trong nhánh gộp vào dòng sẵn có: `if rate and not flt(hang.rate): hang.rate = rate; hang.price_list_rate = rate; hang.custom_nguon_gia = nguon`; nếu dòng sẵn có chưa có dấu thì `hang.custom_nguon_gia = hang.get("custom_nguon_gia") or nguon`. Trong nhánh tạo mới: `moi = {..., "rate": rate, "price_list_rate": rate, "custom_nguon_gia": nguon}`. Xoá mọi thứ thuộc `blanket_order`/`han_muc_con`. Sửa nơi gọi trong `chuyen_dong_dat_ngoai_thanh_hang` (bỏ `thang_cuoc`, `price_list`). Sau khi chuyển dòng, nếu mọi dòng hàng đều là "Bảng giá" và không còn dòng gõ tay chưa xử lý thì KHÔNG đổi `custom_loai_don` — đơn đã vào vòng báo giá thì đi hết vòng đó (QĐ-G2b: các chốt đọc dấu, không suy lại).

`portal_reorder`: thay thân vòng lặp bằng:

```python
    gia_theo_ma = bang_gia_khach.gia_bang_gia_nhieu(
        customer, [d.item_code for d in so.items]
    )
    gio_hang, bi_loai = [], []
    for dong in so.items:
        if dong.item_code == ITEM_GIU_CHO:
            continue
        if frappe.db.get_value("Item", dong.item_code, "disabled"):
            bi_loai.append({
                "item_code": dong.item_code, "ly_do": "mat_hang_ngung_kinh_doanh",
            })
            continue
        gia = gia_theo_ma.get(dong.item_code)
        gio_hang.append({
            "item_code": dong.item_code,
            "item_name": dong.item_name
            or frappe.db.get_value("Item", dong.item_code, "item_name"),
            "uom": dong.uom or "",
            "qty": float(dong.qty),
            "tang": "bang_gia" if gia is not None else "cho_bao_gia",
            "gia_hien_hanh": gia,
        })
    return {"gio_hang": gio_hang, "bi_loai": bi_loai}
```

`portal_order_sua_so_luong`, thay `i.rate = 0; i.price_list_rate = 0` bằng:

```python
            if i.get("custom_nguon_gia") == bang_gia_khach.NGUON_BANG_GIA:
                gia = bang_gia_khach.gia_bang_gia(so.customer, i.item_code) or 0
                i.rate = gia
                i.price_list_rate = gia
                if not gia:
                    i.custom_nguon_gia = bang_gia_khach.NGUON_BAO_GIA
            else:
                i.rate = 0
                i.price_list_rate = 0
```

và sửa chuỗi `thay_doi.append(...)` ngay trên để chỉ nói "chờ báo giá lại" cho nhánh `else`.

- [ ] **Step 4: Chạy xanh** — ba file trên + `test_don_tron_bao_gia`.

- [ ] **Step 5: Commit** — `feat(portal): khop ma, dat lai va sua so luong theo Price List`

---

### Task 11: API cho màn chi tiết và màn duyệt

**Files:**
- Modify: `miyano_portal/api/de_xuat.py` — `de_xuat_chi_tiet` (213–358), `de_xuat_duyet_phieu` (397–406), `de_xuat_danh_sach` (185–209)
- Modify: `miyano_portal/api/portal.py` — hàm danh sách yêu cầu gộp (tìm bằng `grep -n "def portal_yeu_cau" miyano_portal/api/portal.py`)
- Test: Create `miyano_portal/tests/test_api_lan_dat.py`

**Interfaces:**
- Consumes: Task 5, 6
- Produces:
  - `de_xuat_chi_tiet` trả thêm `ma_lan_dat: str`, `phieu_cung_lan_dat: {"name", "ma_de_xuat", "trang_thai"} | None`, `canh_bao_gia: list` (chỉ khi phiếu đang "Chờ duyệt", ngược lại `[]`).
  - `de_xuat_duyet_phieu(ten, dieu_chinh=None, duyet_ca_hai=0)` trả `{"sales_order", "de_xuat", "canh_bao_gia", "phieu_cung_lan_dat": {"sales_order", "de_xuat"} | None}`.
  - Danh sách yêu cầu: mỗi dòng có `ma_lan_dat`.

- [ ] **Step 1: Viết test đỏ**

```python
"""API của hai phiếu cùng lần đặt (spec 2026-10-09 §7)."""

import frappe
from frappe.tests.utils import FrappeTestCase

from miyano_portal.api import de_xuat
from miyano_portal.tests import test_tach_phieu as goc


class TestApiLanDat(FrappeTestCase):
	setUp = goc.TestTachPhieu.setUp
	tearDown = goc.TestTachPhieu.tearDown
	_phieu_nhap = goc.TestTachPhieu._phieu_nhap

	def _hai_phieu(self):
		kq = de_xuat.de_xuat_gui_duyet(
			self._phieu_nhap([self.co_gia, self.chua_gia])
		)
		return kq["name"], kq["phieu_cung_lan_dat"]

	def test_chi_tiet_tra_phieu_cung_lan_dat(self):
		a, b = self._hai_phieu()
		frappe.set_user(self.quan_ly)
		kq = de_xuat.de_xuat_chi_tiet(ten=a)
		self.assertTrue(kq["ma_lan_dat"])
		self.assertEqual(kq["phieu_cung_lan_dat"]["name"], b)
		self.assertEqual(kq["phieu_cung_lan_dat"]["trang_thai"], "Chờ duyệt")

	def test_chi_tiet_phieu_don_le_tra_None(self):
		frappe.set_user(self.user_a)
		ten = de_xuat.de_xuat_gui_duyet(self._phieu_nhap([self.co_gia]))["name"]
		frappe.set_user(self.quan_ly)
		kq = de_xuat.de_xuat_chi_tiet(ten=ten)
		self.assertIsNone(kq["phieu_cung_lan_dat"])
		self.assertEqual(kq["ma_lan_dat"], "")

	def test_chi_tiet_tra_canh_bao_gia_khi_gia_doi(self):
		a, _b = self._hai_phieu()
		self._tao_gia(self.co_gia, self.price_list, 60000)
		frappe.set_user(self.quan_ly)
		kq = de_xuat.de_xuat_chi_tiet(ten=a)
		self.assertEqual(kq["canh_bao_gia"], [{
			"item_code": self.co_gia, "gia_cu": 54000.0, "gia_moi": 60000.0,
			"ly_do": "gia_doi",
		}])

	def test_duyet_ca_hai(self):
		a, b = self._hai_phieu()
		frappe.set_user(self.quan_ly)
		kq = de_xuat.de_xuat_duyet_phieu(a, duyet_ca_hai=1)
		self.assertTrue(kq["sales_order"])
		self.assertTrue(kq["phieu_cung_lan_dat"]["sales_order"])
		frappe.set_user("Administrator")
		for ten in (a, b):
			self.assertEqual(
				frappe.db.get_value("Portal De Xuat Mua", ten, "trang_thai"), "Đã duyệt"
			)

	def test_duyet_mot_phieu_khong_dung_phieu_kia(self):
		a, b = self._hai_phieu()
		frappe.set_user(self.quan_ly)
		kq = de_xuat.de_xuat_duyet_phieu(a)
		self.assertIsNone(kq["phieu_cung_lan_dat"])
		frappe.set_user("Administrator")
		self.assertEqual(
			frappe.db.get_value("Portal De Xuat Mua", b, "trang_thai"), "Chờ duyệt"
		)


for _ten, _ham in vars(goc.TestTachPhieu).items():
	if _ten.startswith("_") and not _ten.startswith("__") and callable(_ham):
		if _ten not in vars(TestApiLanDat):
			setattr(TestApiLanDat, _ten, _ham)
```

- [ ] **Step 2: Chạy, thấy đỏ.**

- [ ] **Step 3: Cài đặt**

`de_xuat_chi_tiet`, trước `return kq`:

```python
	# Spec 2026-10-09 §7 — hai phiếu tách từ cùng một lần đặt.
	kq["ma_lan_dat"] = doc.get("ma_lan_dat") or ""
	kq["phieu_cung_lan_dat"] = None
	if doc.get("phieu_cung_lan_dat"):
		kq["phieu_cung_lan_dat"] = frappe.db.get_value(
			DOCTYPE, doc.phieu_cung_lan_dat,
			["name", "ma_de_xuat", "trang_thai"], as_dict=True,
		)
	# Cảnh báo đổi giá chỉ có nghĩa TRƯỚC khi duyệt. Bọc lỗi: `_kiem_gia_doi`
	# NÉM khi một dòng mất giá, mà màn chi tiết phải mở được để quản lý thấy
	# và từ chối phiếu.
	kq["canh_bao_gia"] = []
	if doc.trang_thai == "Chờ duyệt":
		from miyano_portal import de_xuat_duyet
		try:
			kq["canh_bao_gia"] = de_xuat_duyet._kiem_gia_doi(doc)
		except frappe.ValidationError as e:
			kq["canh_bao_gia"] = [{"ly_do": "mat_gia", "thong_diep": str(e)}]
```

`de_xuat_duyet_phieu`:

```python
@frappe.whitelist()
def de_xuat_duyet_phieu(ten, dieu_chinh=None, duyet_ca_hai=0) -> dict:
	doc = _phieu_cua_toi(ten, cho_quan_ly=True)
	... (giữ nguyên phần kiểm quyền và `_ap_dieu_chinh` hiện có) ...
	kq = de_xuat_duyet.duyet_va_tao_don(doc.name, frappe.session.user)
	kq["phieu_cung_lan_dat"] = None
	kia = doc.get("phieu_cung_lan_dat")
	if frappe.utils.cint(duyet_ca_hai) and kia and frappe.db.get_value(
		DOCTYPE, kia, "trang_thai"
	) == "Chờ duyệt":
		_phieu_cua_toi(kia, cho_quan_ly=True)
		kq_kia = de_xuat_duyet.duyet_va_tao_don(kia, frappe.session.user)
		kq["phieu_cung_lan_dat"] = {
			"sales_order": kq_kia["sales_order"], "de_xuat": kq_kia["de_xuat"],
		}
	return kq
```

Đọc thân hàm hiện có trước và chỉ CHÈN phần `duyet_ca_hai`; không đổi cách hàm đang kiểm quyền hay áp `dieu_chinh`. Hai lần duyệt nằm trong một giao dịch: phiếu kia lỗi thì phiếu này cũng rollback.

Thêm `"ma_lan_dat"` vào `fields` của `de_xuat_danh_sach` và vào câu SELECT của danh sách yêu cầu gộp.

- [ ] **Step 4: Chạy xanh** — `test_api_lan_dat`, `test_chi_tiet_gop`, `test_yeu_cau_list`, `test_de_xuat_endpoint`.

- [ ] **Step 5: Commit** — `feat(portal): API phieu cung lan dat, canh bao doi gia, duyet ca hai`

---

### Task 12: Giao diện

**Files:**
- Modify: `frontend/src/views/LapPhieu.vue`, `frontend/src/views/ChiTietYeuCau.vue`, `frontend/src/views/YeuCauList.vue`, `frontend/src/views/Dashboard.vue`, `frontend/src/views/Profile.vue`, `frontend/src/components/chi-tiet/BangMatHang.vue`, `frontend/src/de-xuat-actions.js`
- Test: `miyano_portal/tests/test_giao_dien_bang_gia.py` (kiểm nguồn Vue bằng chuỗi, cùng cách `test_chi_tiet_gop.TestManGopTrenRouter` đang làm — `frontend/` không có hạ tầng test component)

**Interfaces:**
- Consumes: Task 3, 6, 10, 11

- [ ] **Step 1: Viết test đỏ**

```python
"""Giao diện theo Price List (spec 2026-10-09 §7). Kiểm bằng nguồn Vue vì
`frontend/` không có hạ tầng test component."""

from pathlib import Path

from frappe.tests.utils import FrappeTestCase

SRC = Path(__file__).resolve().parents[2] / "frontend" / "src"


def _doc(rel):
	return (SRC / rel).read_text(encoding="utf-8")


class TestGiaoDienBangGia(FrappeTestCase):
	def test_man_dat_hang_khong_con_hop_dong_va_han_muc(self):
		s = _doc("views/LapPhieu.vue")
		for cu in ("nhanHanMuc", "canhBaoHanMuc", "Giá HĐ", "blanket_order",
		           "khong_gioi_han", "nguon_don_gia", "'hop_dong'"):
			self.assertNotIn(cu, s, cu)
		self.assertIn("'bang_gia'", s)

	def test_man_dat_hang_bao_truoc_khi_tach(self):
		s = _doc("views/LapPhieu.vue")
		self.assertIn("sẽ tách thành 2 phiếu", s)

	def test_trang_chu_va_ho_so_khong_con_hop_dong(self):
		for f in ("views/Dashboard.vue", "views/Profile.vue"):
			s = _doc(f)
			self.assertNotIn("portal_contracts", s, f)
			self.assertNotIn("Hạn mức", s, f)

	def test_chi_tiet_co_duong_sang_phieu_cung_lan_dat_va_canh_bao_gia(self):
		s = _doc("views/ChiTietYeuCau.vue")
		self.assertIn("phieu_cung_lan_dat", s)
		self.assertIn("canh_bao_gia", s)
		self.assertIn("Duyệt cả hai", s)

	def test_dat_lai_khong_con_ly_do_theo_hop_dong(self):
		s = _doc("views/ChiTietYeuCau.vue")
		for cu in ("ngoai_hdnt", "het_han_muc", "ngoài hợp đồng", "hết hạn mức"):
			self.assertNotIn(cu, s, cu)
```

- [ ] **Step 2: Chạy, thấy đỏ.**

- [ ] **Step 3: Cài đặt**

**`LapPhieu.vue`**
- Xoá `nhanHanMuc`, `canhBaoHanMuc`, `coGiaBangGia`, cột "Hạn mức" ở bảng tìm kiếm và giỏ (cả bản mobile), cột tên hợp đồng trong giỏ; trong `dongTuKetQua` bỏ `nguon_don_gia`, `blanket_order`, `total`, `used`, `remaining`, `khong_gioi_han`.
- Thay ba hàm nhãn:

```js
// Spec 2026-10-09 §3.2 — hai tầng, đọc từ `tang` do server trả.
function coGia(row) {
  return row.tang === 'bang_gia' && row.don_gia !== null && row.don_gia !== undefined
}
function nhanTang(row) {
  return coGia(row) ? `Bảng giá ${fmtVND(row.don_gia)}` : 'Chờ báo giá'
}
function classTang(row) {
  return coGia(row) ? 'b-green' : 'b-orange'
}
function giaTrongGio(row) {
  return coGia(row) ? fmtVND(row.don_gia) : '—'
}
function thanhTien(row) {
  return coGia(row) ? fmtVND(row.don_gia * (Number(row.so_luong) || 0)) : '—'
}
```

(dùng đúng tên trường số lượng mà giỏ đang dùng — đọc `soHienTai(row)` ở dòng ~226.)
- Thêm các computed và khối thông báo:

```js
const dongCoGia = computed(() => items.value.filter(coGia))
const dongChoBaoGia = computed(() => items.value.filter((r) => !coGia(r)))
const seTach = computed(
  () => dongCoGia.value.length > 0 &&
    (dongChoBaoGia.value.length > 0 || datNgoai.value.length > 0)
)
const tongTamTinh = computed(() =>
  dongCoGia.value.reduce((t, r) => t + r.don_gia * (Number(soHienTai(r)) || 0), 0)
)
```

```html
<p v-if="seTach" class="tag" style="border-left: 3px solid var(--orange); padding-left: 8px">
  Lần đặt này sẽ tách thành 2 phiếu: {{ dongCoGia.length }} mặt hàng đặt ngay theo
  bảng giá, {{ dongChoBaoGia.length + datNgoai.length }} mặt hàng chờ Miyano báo giá.
</p>
<p v-if="dongCoGia.length" class="right"><b>Tạm tính (hàng có giá): {{ fmtVND(tongTamTinh) }}</b></p>
```

Đặt khối này thay cho ghi chú "cả đơn sẽ chờ Miyano báo giá" (dòng ~1428) và xoá `coHangChoBaoGia` nếu không còn nơi dùng.
- Giỏ thêm cột "Thành tiền" (`thanhTien(r)`).
- Nạp lại phiếu nháp (dòng ~513): `tang: it.nguon_gia === 'Bảng giá' ? 'bang_gia' : 'cho_bao_gia'`.
- `guiDuyet()`: sau khi gọi `de_xuat_gui_duyet`, nếu `res.phieu_cung_lan_dat` thì `showToast('Đã tách thành 2 phiếu và gửi duyệt.', 'success'); router.push({ name: 'yeu-cau' })`, ngược lại giữ điều hướng cũ.
- `datHang()`: nếu `res.don.length === 2` thì toast "Đã tạo 2 đơn: 1 đơn đặt ngay, 1 đơn chờ báo giá." và `router.push({ name: 'yeu-cau' })`, ngược lại giữ điều hướng cũ. Bỏ `contract` khỏi tham số gửi đi nếu còn.

**`ChiTietYeuCau.vue`**
- Dưới tiêu đề phiếu:

```html
<p v-if="phieu?.phieu_cung_lan_dat" class="tag">
  Cùng lần đặt {{ phieu.ma_lan_dat }}:
  <router-link :to="{ name: 'de-xuat-detail', params: { ten: phieu.phieu_cung_lan_dat.name } }">
    {{ phieu.phieu_cung_lan_dat.ma_de_xuat || phieu.phieu_cung_lan_dat.name }}
  </router-link>
  ({{ phieu.phieu_cung_lan_dat.trang_thai }})
</p>
```

- Trong khối duyệt của quản lý, trước các nút:

```html
<div v-if="phieu?.canh_bao_gia?.length" style="border: 1px solid var(--orange); border-radius: 8px; padding: 10px; margin-bottom: 10px">
  <b>Giá đã thay đổi so với lúc khoa gửi</b>
  <p v-for="c in phieu.canh_bao_gia" :key="c.item_code || c.ly_do" class="tag" style="margin: 2px 0">
    <template v-if="c.ly_do === 'mat_gia'">{{ c.thong_diep }}</template>
    <template v-else>{{ c.item_code }}: {{ fmtVND(c.gia_cu) }} → {{ fmtVND(c.gia_moi) }}</template>
  </p>
</div>
```

- Gỡ dòng hiện `don.hdnt` ở đầu trang (dòng ~683).
- Đặt lại (`:540-544`, `:571-578`): bảng lý do loại chỉ còn `mat_hang_ngung_kinh_doanh: 'đã ngừng kinh doanh'`; giỏ nhận `tang` và `gia_hien_hanh` từ `portal_reorder`.

**`de-xuat-actions.js`**: thêm hành động cho quản lý, hiện khi `phieu.trang_thai === 'Chờ duyệt' && phieu.phieu_cung_lan_dat?.trang_thai === 'Chờ duyệt'`, nhãn `'Duyệt cả hai'`, gọi `de_xuat_duyet_phieu` với `{ ten, dieu_chinh, duyet_ca_hai: 1 }`. Đọc cách các hành động khác trong file được khai (khoá, nhãn, điều kiện, hàm chạy) và làm đúng khuôn đó; `test_de_xuat_action_registry.py` kiểm khuôn này, cập nhật danh sách hành động kỳ vọng ở đó.

**`BangMatHang.vue`**: thêm cột "Đơn giá" cho phiếu chưa có đơn:

```js
const coCotGiaPhieu = computed(
  () => coPhieu.value && !coDon.value && dong.value.some((r) => Number(r.don_gia) > 0)
)
```

`<th v-if="coCotGiaPhieu" class="right">Đơn giá</th>` và ô tương ứng `{{ Number(row.don_gia) > 0 ? fmtVND(row.don_gia) : 'Chờ báo giá' }}`; cộng `coCotGiaPhieu` vào `soCotTong`.

**`YeuCauList.vue`**: hiện `ma_lan_dat` dạng nhãn nhỏ `Lần đặt {{ r.ma_lan_dat }}` cạnh mã phiếu khi có.

**`Dashboard.vue`**: xoá thẻ "Hợp đồng khung" (dòng 108–128) và lời gọi `portal_contracts`. **`Profile.vue`**: xoá bảng hợp đồng (dòng 65–81) và lời gọi tương ứng.

- [ ] **Step 4: Build và chạy xanh**

```bash
cd frontend && yarn -s build && yarn -s test && cd ..
```

Chạy `test_giao_dien_bang_gia`, `test_chi_tiet_gop`, `test_de_xuat_action_registry`, `test_cr04_giao_dien`, `test_e3_giao_dien`. Sửa các kiểm chuỗi cũ nào đang đòi "Hạn mức"/"Giá HĐ" có mặt.

- [ ] **Step 5: Xem trên cổng**

Khởi động lại tiến trình web để nạp Python mới (`bench restart` cần sudo; nếu không có, gửi SIGTERM cho tiến trình gunicorn chủ của bench này — supervisor tự bật lại). Đăng nhập tài khoản Bệnh viện Đa khoa Minh Đức và kiểm:
1. Màn Đặt hàng, tìm `MYN-`: 13 mặt hàng hiện "Bảng giá …", còn lại "Chờ báo giá"; không còn cột Hạn mức.
2. Cho `MYN-ALC-70-500` (có giá) và một mặt hàng chờ báo giá vào giỏ: thấy thông báo tách và tổng tạm tính.
3. Gửi: danh sách yêu cầu có hai phiếu cùng mã lần đặt; mở một phiếu thấy đường dẫn sang phiếu kia.

- [ ] **Step 6: Commit** (kèm bundle) — `feat(portal): giao dien dat hang va chi tiet theo Price List`

---

### Task 13: Dọn dẹp, tài liệu, chạy toàn bộ

**Files:**
- Modify: `miyano_portal/portal_context.py` (xoá `han_muc_con`, `ten_khoa_da_tieu`, `remaining_qty` nếu không còn người gọi), `miyano_portal/portal_thong_bao.py` (xoá `bao_thieu_gia` nếu không còn người gọi), `miyano_portal/kho/dutru.py:407,442` (bỏ cờ `dat_duoc_hdnt`), `miyano_portal/portal_mua_le.py` (xoá `items_thuoc_hdnt_hieu_luc` nếu không còn người gọi)
- Modify: `docs/BA-miyano_portal.md`, `docs/Miyano-Portal(Client)_V2/BA-miyano_portal_v2.md`, `docs/BAN-DO-CHUC-NANG.md`
- Test: `test_portal_context.py`, `test_e5_du_tru.py:387-428`

- [ ] **Step 1: Tìm mã chết**

```bash
for f in han_muc_con ten_khoa_da_tieu remaining_qty bao_thieu_gia items_thuoc_hdnt_hieu_luc nguon_gia_theo_ma_cho_khach gia_dong_hop_dong con_hieu_luc _selling_price_list_mac_dinh; do echo "== $f"; grep -rn "\b$f\b" miyano_portal --include=*.py | grep -v "/tests/" | grep -v "def $f"; done
```

Hàm nào không còn dòng nào ngoài định nghĩa của chính nó thì xoá cùng test của nó. `nguon_gia_theo_ma_cho_khach` ở lại nếu `gia_hdnt.dong_bo_khach` còn dùng.

- [ ] **Step 2: Bỏ cờ `dat_duoc_hdnt`** ở `kho/dutru.py` và các khẳng định về nó trong `test_e5_du_tru.py`.

- [ ] **Step 3: Tài liệu**

Trong hai file BA, tại mỗi quy tắc sau thêm một dòng ngay dưới: `> **Đã thay bởi quyết định 09/10/2026** — xem docs/superpowers/specs/2026-10-09-gia-theo-price-list-design.md.` Danh sách: QĐ-8, BR-O2, BR-O3, BR-O15, NL-1.1–NL-1.4, NL-1.11, BR-R3, VĐ-7 (bản V2); MT2, BR-O1, BR-O2, BR-O3, BR-O5, BR-O6, UC-03 (bản gốc). Trong `docs/superpowers/plans/2026-08-19-gop-luong-dat-hang.md` làm tương tự cho QĐ-G1, QĐ-G3, QĐ-G8, QĐ-G9, QĐ-G10, QĐ-G12, QĐ-G14. Trong `docs/BAN-DO-CHUC-NANG.md` sửa các dòng 44, 195, 197–198 cho khớp hai tầng mới và việc tách phiếu.

- [ ] **Step 4: Chạy toàn bộ**

```bash
cd /home/hoangvietyeuem/frappe-bench-yhct && bench --site erptest.local run-tests --app miyano_portal 2>&1 | tee /tmp/full.log | grep -E "^Ran |^OK|^FAILED"
grep "^ERROR: \|^FAIL: " /tmp/full.log | sed -E 's/.*\(miyano_portal\.tests\.([a-z0-9_]+)\..*/\1/' | sort | uniq -c
```

Expected: lỗi chỉ còn ở năm file nêu trong Global Constraints, với số lượng không tăng. Mọi lỗi ở file khác phải được sửa trước khi commit.

- [ ] **Step 5: Commit** — `chore(portal): go ma han muc va hop dong khong con dung; cap nhat tai lieu`
