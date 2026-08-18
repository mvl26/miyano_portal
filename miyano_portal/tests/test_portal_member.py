"""`Portal Member` — nguồn sự thật duy nhất cho danh tính cổng (bước 3)."""

import frappe
from frappe.tests.utils import FrappeTestCase

KHACH_BM = "Bệnh viện Bạch Mai"
KHACH_PXN = "PXN ABC"


class _NenThanhVien(FrappeTestCase):
	def setUp(self):
		frappe.db.delete("Portal Member", {"user": ["like", "zztest%"]})
		frappe.db.delete("Customer Department", {"ten_khoa_phong": ["like", "ZZTEST%"]})
		self.kp_bm = frappe.get_doc({
			"doctype": "Customer Department", "customer": KHACH_BM,
			"ten_khoa_phong": "ZZTEST Huyết học", "ma_khoa": "ZZHH",
		}).insert(ignore_permissions=True)
		self.kp_pxn = frappe.get_doc({
			"doctype": "Customer Department", "customer": KHACH_PXN,
			"ten_khoa_phong": "ZZTEST Xét nghiệm", "ma_khoa": "ZZXN",
		}).insert(ignore_permissions=True)

	def _user(self, email):
		if not frappe.db.exists("User", email):
			frappe.get_doc({
				"doctype": "User", "email": email, "first_name": "ZZ",
				"user_type": "Website User", "send_welcome_email": 0,
			}).insert(ignore_permissions=True)
		return email

	def _tv(self, email, vai_tro="Quản lý", customer=KHACH_BM, khoa_phong=None):
		return frappe.get_doc({
			"doctype": "Portal Member", "user": self._user(email),
			"customer": customer, "vai_tro": vai_tro, "khoa_phong": khoa_phong,
		}).insert(ignore_permissions=True)


class TestPortalMemberRangBuoc(_NenThanhVien):
	def test_moi_benh_vien_dung_mot_quan_ly_dang_hoat_dong(self):
		self._tv("zztest.ql1@demo.miyano")
		with self.assertRaises(frappe.ValidationError):
			self._tv("zztest.ql2@demo.miyano")

	def test_nhan_vien_khoa_bat_buoc_co_khoa_phong(self):
		with self.assertRaises(frappe.ValidationError):
			self._tv("zztest.nv@demo.miyano", vai_tro="Nhân viên khoa")

	def test_quan_ly_khong_duoc_gan_khoa_phong(self):
		with self.assertRaises(frappe.ValidationError):
			self._tv("zztest.ql3@demo.miyano", khoa_phong=self.kp_bm.name)

	def test_khoa_phong_phai_thuoc_dung_benh_vien(self):
		"""Lỗ phân quyền mở được bằng một thao tác nhập liệu."""
		self._tv("zztest.ql4@demo.miyano")
		with self.assertRaises(frappe.ValidationError):
			self._tv(
				"zztest.nv2@demo.miyano", vai_tro="Nhân viên khoa",
				customer=KHACH_BM, khoa_phong=self.kp_pxn.name,
			)

	def test_mot_user_chi_thuoc_mot_benh_vien(self):
		self._tv("zztest.ql5@demo.miyano")
		with self.assertRaises(Exception):
			self._tv("zztest.ql5@demo.miyano", customer=KHACH_PXN)

	def test_bat_buoc_khach_hang_co_ma_ngan_truoc_khi_cap_tai_khoan_khoa(self):
		"""Kiểm đúng lúc BẬT tính năng, không phải lúc nhân viên bấm gửi."""
		frappe.db.set_value("Customer", KHACH_BM, "custom_ma_ngan", None)
		self._tv("zztest.ql6@demo.miyano")
		with self.assertRaises(frappe.ValidationError):
			self._tv(
				"zztest.nv3@demo.miyano", vai_tro="Nhân viên khoa",
				khoa_phong=self.kp_bm.name,
			)
