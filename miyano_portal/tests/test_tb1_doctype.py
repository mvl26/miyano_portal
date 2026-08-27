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
		khach_khac = "ZZTB Benh Vien Khac"
		for khach in (KHACH, khach_khac):
			for dt in ("Customer Equipment", "Customer Department"):
				for r in frappe.get_all(dt, filters={"customer": khach}, pluck="name"):
					frappe.delete_doc(dt, r, force=True, ignore_permissions=True)
			if frappe.db.exists("Customer", khach):
				frappe.delete_doc("Customer", khach, force=True, ignore_permissions=True)

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
			self._may(ma_thiet_bi="   ")

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
			"ngay_bat_dau": frappe.utils.today(),
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
