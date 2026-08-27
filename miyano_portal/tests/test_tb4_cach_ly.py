"""Task 5 — cách ly dữ liệu `Customer Equipment` giữa các bệnh viện, và giữa
các khoa trong cùng một bệnh viện.

Bốn lớp cách ly (đọc docstring đầu `kho/permissions.py` trước khi sửa gì ở
đây):

1. `permission_query_conditions` (`thiet_bi_query`) — lọc theo `customer`
   của phiên; Nhân viên khoa lọc thêm theo `khoa_phong` CỘNG máy dùng chung
   (`khoa_phong` rỗng).
2. `has_permission` cho `Customer Equipment` (`thiet_bi_has_permission`, cha
   — BẮT BUỘC có mặt trong hooks.py, guard `test_kho_isolation.py` đòi mọi
   doctype kho không istable phải đăng ký) VÀ cho bảng con `Customer
   Warehouse Item Equipment` — bảng `istable` không đi qua
   `permission_query_conditions`, đóng bằng cách kế thừa
   `miyano_portal.kho.voucher_item.VoucherItemBase` (KHÔNG viết một hàm
   `has_permission` riêng — FINDING N4: dùng chung với Customer Stock
   Receipt/Issue Item, xem docstring controller).
3. KHÔNG có DocPerm nào cho role `Customer` trên `Customer Equipment` — lớp
   CHỊU LỰC, kiểm bằng cách đọc thẳng JSON doctype (không phải xin quyền).
4. API suy tenant từ phiên — thuộc Task 6-7, không kiểm ở đây.

Hai bệnh viện ZZTB4-A / ZZTB4-B, mỗi bên một Quản lý; bệnh viện A có thêm hai
khoa (A1/A2) và một Nhân viên khoa cho mỗi khoa, để kiểm cả cách ly liên viện
lẫn cách ly nội viện theo khoa.

DEVIATION so với brief gốc (xem task-5-report.md mục "Sai khác so với brief"
để biết đầy đủ): brief đề nghị một hàm `vat_tu_may_item_query` riêng cho bảng
con, đăng ký trong hooks.py. Cả hai điều đó SAI — đăng ký hooks.py cho
istable là "chết cấu trúc" (không bao giờ được gọi, xem comment dài trong
hooks.py), và viết riêng một hàm trùng logic `voucher_item_readable()` đã có
(cha của bảng con này CÓ field `kho`) là đúng loại trùng lặp FINDING N4 sinh
ra để chống. Test file này vì thế test `voucher_item_readable`/
`VoucherItemBase`, không phải một hàm `vat_tu_may_item_query` không tồn tại.
"""

import frappe
from frappe.tests.utils import FrappeTestCase

from miyano_portal.kho import permissions
from miyano_portal.kho.voucher_item import VoucherItemBase

KHACH_A = "ZZTB4 Benh Vien A"
KHACH_B = "ZZTB4 Benh Vien B"


class TestCachLyThietBi(FrappeTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		self._don()
		self.addCleanup(self._don)

		frappe.get_doc({
			"doctype": "Customer", "customer_name": KHACH_A,
			"customer_type": "Company", "customer_group": "All Customer Groups",
			"territory": "All Territories",
			"custom_ma_ngan": "ZZT4A", "custom_cho_phep_mua_le": 1,
		}).insert(ignore_permissions=True)
		frappe.get_doc({
			"doctype": "Customer", "customer_name": KHACH_B,
			"customer_type": "Company", "customer_group": "All Customer Groups",
			"territory": "All Territories",
			"custom_ma_ngan": "ZZT4B", "custom_cho_phep_mua_le": 1,
		}).insert(ignore_permissions=True)

		self.kho_a = frappe.get_doc({
			"doctype": "Customer Warehouse", "customer": KHACH_A,
			"ten_kho": "ZZTB4 Kho A", "ma_kho": "ZZTB4A",
			"ngay_bat_dau": frappe.utils.add_days(frappe.utils.today(), -30),
		}).insert(ignore_permissions=True)
		self.kho_b = frappe.get_doc({
			"doctype": "Customer Warehouse", "customer": KHACH_B,
			"ten_kho": "ZZTB4 Kho B", "ma_kho": "ZZTB4B",
			"ngay_bat_dau": frappe.utils.add_days(frappe.utils.today(), -30),
		}).insert(ignore_permissions=True)

		self.kp_a1 = frappe.get_doc({
			"doctype": "Customer Department", "customer": KHACH_A,
			"ten_khoa_phong": "ZZTB4 Khoa A1", "ma_khoa": "ZZT4A1",
		}).insert(ignore_permissions=True)
		self.kp_a2 = frappe.get_doc({
			"doctype": "Customer Department", "customer": KHACH_A,
			"ten_khoa_phong": "ZZTB4 Khoa A2", "ma_khoa": "ZZT4A2",
		}).insert(ignore_permissions=True)

		self.ql_a = self._tv("zztb4.a.ql@demo.miyano", KHACH_A, "Quản lý", None)
		self.nv_a1 = self._tv("zztb4.a.nv1@demo.miyano", KHACH_A, "Nhân viên khoa", self.kp_a1.name)
		self.nv_a2 = self._tv("zztb4.a.nv2@demo.miyano", KHACH_A, "Nhân viên khoa", self.kp_a2.name)
		self.ql_b = self._tv("zztb4.b.ql@demo.miyano", KHACH_B, "Quản lý", None)

		self.may_a1 = frappe.get_doc({
			"doctype": "Customer Equipment", "customer": KHACH_A,
			"ma_thiet_bi": "ZZTB4-A1-01", "ten_thiet_bi": "Máy khoa A1",
			"khoa_phong": self.kp_a1.name,
		}).insert(ignore_permissions=True)
		self.may_a2 = frappe.get_doc({
			"doctype": "Customer Equipment", "customer": KHACH_A,
			"ma_thiet_bi": "ZZTB4-A2-01", "ten_thiet_bi": "Máy khoa A2",
			"khoa_phong": self.kp_a2.name,
		}).insert(ignore_permissions=True)
		self.may_a_dung_chung = frappe.get_doc({
			"doctype": "Customer Equipment", "customer": KHACH_A,
			"ma_thiet_bi": "ZZTB4-A-DC", "ten_thiet_bi": "Máy dùng chung A",
		}).insert(ignore_permissions=True)
		self.may_b = frappe.get_doc({
			"doctype": "Customer Equipment", "customer": KHACH_B,
			"ma_thiet_bi": "ZZTB4-B-01", "ten_thiet_bi": "Máy bệnh viện B",
		}).insert(ignore_permissions=True)

		self.vat_tu_a = frappe.get_doc({
			"doctype": "Customer Warehouse Item", "kho": self.kho_a.name,
			"ma_vat_tu": "ZZTB4-VT-A", "ten_vat_tu": "Vật tư kho A", "dvt": "Hộp",
			"may_su_dung": [{"thiet_bi": self.may_a1.name}],
		}).insert(ignore_permissions=True)
		self.vat_tu_b = frappe.get_doc({
			"doctype": "Customer Warehouse Item", "kho": self.kho_b.name,
			"ma_vat_tu": "ZZTB4-VT-B", "ten_vat_tu": "Vật tư kho B", "dvt": "Hộp",
			"may_su_dung": [{"thiet_bi": self.may_b.name}],
		}).insert(ignore_permissions=True)

	def _tv(self, email, khach, vai_tro, khoa_phong):
		"""Dựng User + Contact + Portal Member — sao y `_tv()` của
		`test_cach_ly_khoa_phong.py` (đã kiểm chứng đúng, không viết lại logic
		Contact "mồ côi")."""
		if not frappe.db.exists("User", email):
			u = frappe.get_doc({
				"doctype": "User", "email": email, "first_name": "ZZ",
				"user_type": "Website User", "send_welcome_email": 0,
			})
			u.append("roles", {"role": "Customer"})
			u.insert(ignore_permissions=True)
			ten_contact = f"{khach}-{email}"
			if not frappe.db.exists("Contact", ten_contact):
				ct = frappe.get_doc({"doctype": "Contact", "first_name": khach, "user": email})
				ct.name = ten_contact
				ct.append("email_ids", {"email_id": email, "is_primary": 1})
				ct.append("links", {"link_doctype": "Customer", "link_name": khach})
				ct.insert(ignore_permissions=True)
		return frappe.get_doc({
			"doctype": "Portal Member", "user": email, "customer": khach,
			"vai_tro": vai_tro, "khoa_phong": khoa_phong,
		}).insert(ignore_permissions=True)

	def _don(self):
		"""Dọn CHỈ dữ liệu của hai khách hàng ZZTB4 của bộ test này. TUYỆT ĐỐI
		không xoá không lọc — erptest.local mang dữ liệu demo của nhiều bệnh
		viện và nhiều bộ test khác (xem `_don()` của `test_tb3_bat_buoc.py`,
		khuôn mẫu đúng)."""
		khach = [KHACH_A, KHACH_B]
		khos = frappe.get_all(
			"Customer Warehouse", filters={"customer": ["in", khach]}, pluck="name"
		) or [""]
		vat_tu = frappe.get_all(
			"Customer Warehouse Item", filters={"kho": ["in", khos]}, pluck="name"
		) or [""]
		frappe.db.delete("Customer Warehouse Item Equipment", {"parent": ["in", vat_tu]})
		frappe.db.delete("Customer Warehouse Item", {"kho": ["in", khos]})
		frappe.db.delete("Customer Equipment", {"customer": ["in", khach]})
		emails = [
			"zztb4.a.ql@demo.miyano", "zztb4.a.nv1@demo.miyano",
			"zztb4.a.nv2@demo.miyano", "zztb4.b.ql@demo.miyano",
			# Không có Contact/vai trò kèm — chỉ Portal Member, xem
			# test_nhan_vien_khoa_active_ma_khoa_phong_rong_fail_closed
			# (tự dọn trong `finally` của chính nó, liệt kê lại ở đây làm
			# lưới an toàn nếu test bị ngắt giữa chừng).
			"zztb4.a.nv.chuagankhoa@demo.miyano",
		]
		frappe.db.delete("Portal Member", {"user": ["in", emails]})
		for khach_ten in khach:
			for email in emails:
				ct = f"{khach_ten}-{email}"
				if frappe.db.exists("Contact", ct):
					frappe.delete_doc("Contact", ct, force=True, ignore_permissions=True)
		frappe.db.delete("Customer Department", {"customer": ["in", khach]})
		frappe.db.delete("Customer Warehouse", {"customer": ["in", khach]})
		frappe.db.delete("Customer", {"name": ["in", khach]})

	# -- Lớp 1: permission_query_conditions ---------------------------------

	def test_query_condition_loc_theo_khach(self):
		frappe.set_user(self.ql_a.user)
		dieu_kien = permissions.thiet_bi_query(self.ql_a.user)
		self.assertIn(frappe.db.escape(KHACH_A), dieu_kien)
		self.assertNotIn(frappe.db.escape(KHACH_B), dieu_kien)

	def test_nhan_vien_khoa_chi_thay_may_khoa_minh_va_may_dung_chung(self):
		frappe.set_user(self.nv_a1.user)
		dieu_kien = permissions.thiet_bi_query(self.nv_a1.user)
		self.assertIn("is null", dieu_kien.lower())
		self.assertIn(frappe.db.escape(self.kp_a1.name), dieu_kien)
		self.assertNotIn(frappe.db.escape(self.kp_a2.name), dieu_kien)

	def test_nhan_vien_mien_khong_thay_gi(self):
		frappe.set_user("Guest")
		self.assertEqual(permissions.thiet_bi_query("Guest"), "1=0")

	def test_nhan_vien_miyano_thay_tat_ca(self):
		frappe.set_user("Administrator")
		self.assertEqual(permissions.thiet_bi_query("Administrator"), "")

	def test_quan_ly_khong_bi_loc_theo_khoa(self):
		"""Đối chứng cho ca Nhân viên khoa: Quản lý nhìn xuyên mọi khoa của
		đúng bệnh viện mình, điều kiện SQL không được có vế `khoa_phong`."""
		frappe.set_user(self.ql_a.user)
		dieu_kien = permissions.thiet_bi_query(self.ql_a.user)
		self.assertNotIn("khoa_phong", dieu_kien.lower())

	def test_dieu_kien_sql_that_su_loc_dung_khi_ap_truc_tiep(self):
		"""Chốt bằng số liệu thật, không chỉ soi chuỗi SQL: áp điều kiện của
		`thiet_bi_query` trực tiếp vào `frappe.db.sql` (đường vòng qua tầng
		phân quyền, giống hệt cách framework tự AND điều kiện này vào mọi
		`frappe.get_list`/reportview) và kiểm đúng tập máy trả về."""
		frappe.set_user(self.nv_a1.user)
		dieu_kien = permissions.thiet_bi_query(self.nv_a1.user)
		ten = frappe.db.sql_list(
			f"select name from `tabCustomer Equipment` where {dieu_kien} "
			"and customer = %s",
			KHACH_A,
		)
		self.assertIn(self.may_a1.name, ten)
		self.assertIn(self.may_a_dung_chung.name, ten)
		self.assertNotIn(self.may_a2.name, ten)

	# -- Lớp 3: KHÔNG có DocPerm cho role Customer — lớp chịu lực ------------

	def test_khong_co_docperm_cho_role_customer(self):
		"""Lớp CHỊU LỰC. Test này tồn tại để một PR sau không âm thầm cấp lại
		DocPerm cho role `Customer` trên `Customer Equipment`."""
		import json
		import pathlib

		p = (
			pathlib.Path(frappe.get_app_path("miyano_portal"))
			/ "miyano_portal" / "doctype" / "customer_equipment" / "customer_equipment.json"
		)
		perms = json.loads(p.read_text())["permissions"]
		self.assertNotIn("Customer", [x.get("role") for x in perms])

	def test_khong_co_docperm_cho_role_customer_tren_bang_con(self):
		"""Cùng lớp chịu lực cho bảng con — `Customer Warehouse Item
		Equipment` là `istable`, JSON gốc phải giữ `permissions: []`."""
		import json
		import pathlib

		p = (
			pathlib.Path(frappe.get_app_path("miyano_portal"))
			/ "miyano_portal" / "doctype" / "customer_warehouse_item_equipment"
			/ "customer_warehouse_item_equipment.json"
		)
		perms = json.loads(p.read_text())["permissions"]
		self.assertEqual(perms, [])

	def test_website_user_khong_get_list_duoc(self):
		frappe.set_user(self.ql_a.user)
		with self.assertRaises(frappe.PermissionError):
			frappe.get_list("Customer Equipment")

	# -- Lớp 2: has_permission cho Customer Equipment (cha) ------------------

	def test_parent_has_permission_cho_phep_khach_cua_chinh_minh(self):
		self.assertTrue(
			permissions.thiet_bi_has_permission(self.may_a1, user=self.ql_a.user)
		)

	def test_parent_has_permission_chan_benh_vien_khac(self):
		self.assertFalse(
			permissions.thiet_bi_has_permission(self.may_b, user=self.ql_a.user)
		)

	def test_parent_has_permission_nhan_vien_khoa_chan_khoa_khac(self):
		self.assertFalse(
			permissions.thiet_bi_has_permission(self.may_a2, user=self.nv_a1.user)
		)

	def test_parent_has_permission_nhan_vien_khoa_qua_duoc_may_dung_chung(self):
		self.assertTrue(
			permissions.thiet_bi_has_permission(
				self.may_a_dung_chung, user=self.nv_a1.user
			)
		)

	def test_parent_has_permission_nhan_vien_mien_khong_thay_gi(self):
		self.assertFalse(permissions.thiet_bi_has_permission(self.may_a1, user="Guest"))

	def test_parent_has_permission_nhan_vien_miyano_luon_qua(self):
		self.assertTrue(
			permissions.thiet_bi_has_permission(self.may_b, user="Administrator")
		)

	# -- Lớp 2: has_permission cho bảng con istable (dùng chung VoucherItemBase) --

	def test_child_reuses_voucher_item_base_khong_ham_rieng(self):
		"""FINDING N4 — kiểm cả ba mắt xích, cùng khuôn
		`test_child_item_controllers_use_shared_has_permission` của
		`test_kho_isolation.py`: controller kế thừa `VoucherItemBase` và
		dùng ĐÚNG bản `has_permission` của lớp cơ sở (không tự ghi đè)."""
		from miyano_portal.miyano_portal.doctype.customer_warehouse_item_equipment.customer_warehouse_item_equipment import (
			CustomerWarehouseItemEquipment,
		)

		self.assertTrue(issubclass(CustomerWarehouseItemEquipment, VoucherItemBase))
		self.assertIs(
			CustomerWarehouseItemEquipment.has_permission,
			VoucherItemBase.has_permission,
		)

	def test_child_voucher_item_readable_cho_phep_kho_cua_chinh_minh(self):
		row = frappe._dict({"parenttype": "Customer Warehouse Item", "parent": self.vat_tu_a.name})
		self.assertTrue(permissions.voucher_item_readable(row, user=self.ql_a.user))

	def test_child_voucher_item_readable_chan_kho_benh_vien_khac(self):
		row = frappe._dict({"parenttype": "Customer Warehouse Item", "parent": self.vat_tu_b.name})
		self.assertFalse(permissions.voucher_item_readable(row, user=self.ql_a.user))

	def test_child_voucher_item_readable_nhan_vien_mien_khong_thay_gi(self):
		row = frappe._dict({"parenttype": "Customer Warehouse Item", "parent": self.vat_tu_a.name})
		self.assertFalse(permissions.voucher_item_readable(row, user="Guest"))

	def test_child_voucher_item_readable_nhan_vien_miyano_luon_qua(self):
		row = frappe._dict({"parenttype": "Customer Warehouse Item", "parent": self.vat_tu_b.name})
		self.assertTrue(permissions.voucher_item_readable(row, user="Administrator"))

	def test_controller_override_chan_qua_instance_khac_benh_vien(self):
		"""Chốt bằng doc THẬT đi qua `doc.has_permission()` — đường mà
		`VoucherItemBase.has_permission()` (thừa kế qua controller) thực sự
		can thiệp được, khác `frappe.has_permission()` module-level (không
		bao giờ chạm override này cho istable — xem docstring
		`VoucherItemBase`). Cần role Customer có DocPerm thật trên `Customer
		Warehouse Item` để bài kiểm này có ý nghĩa (nếu không, super().
		has_permission() đã trả False từ vòng kiểm role, override không kịp
		chạy tới nhánh voucher_item_readable) — dựng grant TẠM cho đúng một
		test này rồi dọn lại ngay trong cùng test, không đụng JSON trên đĩa
		(lớp CHỊU LỰC — test_khong_co_docperm_cho_role_customer* — vẫn phải
		thấy JSON sạch).

		Tự chữa lành ở ĐẦU test (không chỉ ở `finally`): `finally` không
		sống sót qua SIGKILL (OOM kill nhiều bench chung máy — xem memory
		`test_rest_guard chập chờn`), nên một lần chạy bị giết giữa chừng có
		thể để lại grant TẠM này sống trên erptest.local. Lọc theo ĐÚNG HAI
		khoá (parent + role) — không match-all — nên không đụng gì khác."""
		frappe.db.delete(
			"Custom DocPerm", {"parent": "Customer Warehouse Item", "role": "Customer"}
		)
		frappe.clear_cache(doctype="Customer Warehouse Item")
		frappe.get_doc({
			"doctype": "Custom DocPerm", "parent": "Customer Warehouse Item",
			"parenttype": "DocType", "parentfield": "permissions",
			"role": "Customer", "read": 1,
		}).insert(ignore_permissions=True)
		frappe.clear_cache(doctype="Customer Warehouse Item")
		try:
			row_a = frappe.get_doc(
				"Customer Warehouse Item Equipment",
				{"parent": self.vat_tu_a.name, "parentfield": "may_su_dung"},
			)
			row_b = frappe.get_doc(
				"Customer Warehouse Item Equipment",
				{"parent": self.vat_tu_b.name, "parentfield": "may_su_dung"},
			)
			frappe.set_user(self.ql_a.user)
			self.assertTrue(row_a.has_permission("read"))
			self.assertFalse(row_b.has_permission("read"))
		finally:
			frappe.set_user("Administrator")
			frappe.db.delete(
				"Custom DocPerm",
				{"parent": "Customer Warehouse Item", "role": "Customer"},
			)
			frappe.clear_cache(doctype="Customer Warehouse Item")

	def test_nhan_vien_khoa_active_ma_khoa_phong_rong_fail_closed(self):
		"""VÒNG SỬA (trước commit) — bản đầu của `thiet_bi_query` tự đọc
		`vai_tro`/`khoa_phong` và coi `khoa_phong` rỗng như "không giới hạn
		theo khoa", NGƯỢC với `pham_vi_don()` (VÒNG SỬA 3, F5 ở
		`portal_context.py`) — nơi đúng trạng thái này (Nhân viên khoa
		`active=1`, `khoa_phong` rỗng, đi vòng qua `validate()` bằng
		`db.set_value`) bị fail-closed bằng `PermissionError`. Sao y fixture
		của `TestI2FailClosedThongBaoChoNhanVienChuaGanKhoa`
		(`test_cach_ly_khoa_phong.py`): `active=0` để qua được validate lúc
		insert, bật lại bằng `db.set_value`."""
		email = "zztb4.a.nv.chuagankhoa@demo.miyano"
		if not frappe.db.exists("User", email):
			u = frappe.get_doc({
				"doctype": "User", "email": email, "first_name": "ZZ",
				"user_type": "Website User", "send_welcome_email": 0,
			})
			u.append("roles", {"role": "Customer"})
			u.insert(ignore_permissions=True)
		tv = frappe.get_doc({
			"doctype": "Portal Member", "user": email, "customer": KHACH_A,
			"vai_tro": "Nhân viên khoa", "khoa_phong": None, "active": 0,
		}).insert(ignore_permissions=True)
		frappe.db.set_value("Portal Member", tv.name, "active", 1)
		try:
			frappe.set_user(email)
			self.assertEqual(permissions.thiet_bi_query(email), "1=0")
		finally:
			frappe.set_user("Administrator")
			frappe.db.delete("Portal Member", {"user": email})

	# -- Đăng ký trong hooks.py ------------------------------------------------

	def test_hooks_dang_ky_dung_ham(self):
		from miyano_portal import hooks

		self.assertEqual(
			hooks.permission_query_conditions.get("Customer Equipment"),
			"miyano_portal.kho.permissions.thiet_bi_query",
		)
		self.assertEqual(
			hooks.has_permission.get("Customer Equipment"),
			"miyano_portal.kho.permissions.thiet_bi_has_permission",
		)

	def test_hooks_khong_dang_ky_has_permission_cho_bang_con(self):
		"""`Customer Warehouse Item Equipment` là istable=1 — một entry
		`has_permission` cho CHÍNH nó trong hooks.py không bao giờ được gọi
		(xem comment trong hooks.py); cơ chế thật nằm ở việc controller kế
		thừa `VoucherItemBase`. Test này tồn tại để một PR sau không âm thầm
		thêm lại một entry decoy."""
		from miyano_portal import hooks

		self.assertNotIn("Customer Warehouse Item Equipment", hooks.has_permission)
