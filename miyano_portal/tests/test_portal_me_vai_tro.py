"""`portal_me` phải trả vai trò để frontend gating được menu.

Không có ba khoá này thì SPA không có đường nào biết người đăng nhập là
Quản lý hay Nhân viên khoa — `portal_me` hôm nay chỉ trả tên khách, mã số
thuế, công nợ, địa chỉ.
"""

import frappe
from frappe.tests.utils import FrappeTestCase

from miyano_portal.api import portal
from miyano_portal.tests.fixtures_de_xuat import dung_fixture


class TestPortalMeVaiTro(FrappeTestCase):
	def setUp(self):
		self.f = dung_fixture(self)
		# Dựng user quản lý + user nhân viên khoa, cùng khuôn
		# `test_de_xuat_endpoint.py::_dam_bao_thanh_vien` — không phát minh
		# cách dựng user mới.
		self.user_quan_ly = self._dam_bao_thanh_vien(
			"portalme.ql@demo.miyano", self.f.kh_a, "Quản lý", None
		)
		self.user_huyethoc = self._dam_bao_thanh_vien(
			"portalme.huyethoc@demo.miyano", self.f.kh_a, "Nhân viên khoa",
			self.f.khoa_huyethoc,
		)

	def tearDown(self):
		frappe.set_user("Administrator")

	def _dam_bao_thanh_vien(self, email, customer, vai_tro, khoa_phong):
		if not frappe.db.exists("User", email):
			u = frappe.get_doc({
				"doctype": "User", "email": email,
				"first_name": email.split("@")[0],
				"user_type": "Website User", "send_welcome_email": 0,
			})
			u.append("roles", {"role": "Customer"})
			u.insert(ignore_permissions=True)
		ten_tv = frappe.db.get_value("Portal Member", {"user": email}, "name")
		gia_tri = {
			"customer": customer, "vai_tro": vai_tro,
			"khoa_phong": khoa_phong, "active": 1,
		}
		if ten_tv:
			frappe.db.set_value("Portal Member", ten_tv, gia_tri)
		else:
			frappe.get_doc({
				"doctype": "Portal Member", "user": email, **gia_tri,
			}).insert(ignore_permissions=True)
		return email

	def test_quan_ly_thay_vai_tro_va_co_quyen_duyet(self):
		frappe.set_user(self.user_quan_ly)
		me = portal.portal_me()
		self.assertEqual(me["vai_tro"], "Quản lý")
		self.assertTrue(me["la_quan_ly"])
		self.assertIsNone(me["khoa_phong"])

	def test_nhan_vien_khoa_thay_dung_khoa_cua_minh(self):
		frappe.set_user(self.user_huyethoc)
		me = portal.portal_me()
		self.assertEqual(me["vai_tro"], "Nhân viên khoa")
		self.assertFalse(me["la_quan_ly"])
		self.assertEqual(me["khoa_phong"], self.f.khoa_huyethoc)

	def test_khoa_phong_KHONG_nhan_tu_client(self):
		"""Vế canh: `portal_me` không có tham số nào, mọi giá trị suy từ phiên."""
		import inspect
		sig = inspect.signature(portal.portal_me)
		self.assertEqual(len(sig.parameters), 0)

	def test_tra_dung_user_dang_dang_nhap(self):
		"""Task 3 (màn /de-xuat) — `de-xuat-actions.js` so `d.owner === me.user`
		để quyết định hiện nút "Gửi duyệt"/"Xoá" cho đúng chủ phiếu. Trước bản
		vá này `portal_me()` không có khoá `user`, nên vế so sánh đó luôn
		false — hai nút không bao giờ hiện, kể cả cho chủ phiếu."""
		frappe.set_user(self.user_huyethoc)
		me = portal.portal_me()
		self.assertEqual(me["user"], self.user_huyethoc)
		self.assertEqual(me["user"], frappe.session.user)
