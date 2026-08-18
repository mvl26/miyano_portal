"""Khoa phòng thuộc về BỆNH VIỆN, không thuộc về kho (bước 2).

Lý do đổi: đặt hàng thì bệnh viện nào cũng làm, kho thì chỉ vài bệnh viện
có. Giữ khoá theo kho thì khách chưa mở kho (Hi-medic) không có khoa phòng
nào để mà phân quyền.
"""

import frappe
from frappe.tests.utils import FrappeTestCase

KHACH_BM = "Bệnh viện Bạch Mai"


class TestKhoaPhongThuocKhachHang(FrappeTestCase):
	def setUp(self):
		frappe.db.delete("Customer Department", {"ten_khoa_phong": ["like", "ZZTEST%"]})

	def _tao(self, ten, ma=None, customer=KHACH_BM):
		return frappe.get_doc({
			"doctype": "Customer Department", "customer": customer,
			"ten_khoa_phong": ten, "ma_khoa": ma,
		}).insert(ignore_permissions=True)

	def test_khai_duoc_khoa_phong_cho_khach_chua_co_kho(self):
		kp = self._tao("ZZTEST Khoa Huyết học")
		self.assertEqual(kp.customer, KHACH_BM)
		self.assertFalse(kp.kho, "không cần kho mới khai được khoa phòng")

	def test_ma_khoa_tu_viet_hoa(self):
		self.assertEqual(self._tao("ZZTEST Hoá sinh", ma="hs").ma_khoa, "HS")

	def test_ma_khoa_chi_nhan_chu_va_so(self):
		with self.assertRaises(frappe.ValidationError):
			self._tao("ZZTEST Xét nghiệm", ma="XN-01")

	def test_ma_khoa_khong_duoc_trung_trong_mot_benh_vien(self):
		self._tao("ZZTEST Khoa A", ma="KA")
		with self.assertRaises(frappe.ValidationError):
			self._tao("ZZTEST Khoa B", ma="ka")

	def test_ma_khoa_CHUNG_la_ma_danh_rieng(self):
		"""`CHUNG` dành cho đơn quản lý đặt "Toàn viện" (spec §5.5)."""
		with self.assertRaises(frappe.ValidationError):
			self._tao("ZZTEST Khoa chung", ma="CHUNG")
