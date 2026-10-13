"""`quyen_he_thong` — chạy một khối dưới quyền hệ thống (spec 2026-10-12 §4.1)."""

import frappe
from frappe.tests.utils import FrappeTestCase

from miyano_portal.nang_quyen import quyen_he_thong


class TestNangQuyen(FrappeTestCase):
	def tearDown(self):
		frappe.set_user("Administrator")

	def test_trong_khoi_la_administrator_ra_khoi_tra_lai(self):
		frappe.set_user("Guest")
		with quyen_he_thong() as nguoi_goi:
			self.assertEqual(nguoi_goi, "Guest")
			self.assertEqual(frappe.session.user, "Administrator")
			self.assertIn("System Manager", frappe.get_roles())
		self.assertEqual(frappe.session.user, "Guest")

	def test_nem_loi_van_tra_lai_phien(self):
		frappe.set_user("Guest")
		with self.assertRaises(ValueError):
			with quyen_he_thong():
				raise ValueError("hỏng giữa chừng")
		self.assertEqual(frappe.session.user, "Guest")

	def test_khong_dung_toi_sid_va_data(self):
		frappe.set_user("Guest")
		session = frappe.local.session
		session.sid, session.data = "sid-that", frappe._dict(csrf_token="abc")
		with quyen_he_thong():
			pass
		self.assertEqual(session.sid, "sid-that")
		self.assertEqual(session.data.csrf_token, "abc")
