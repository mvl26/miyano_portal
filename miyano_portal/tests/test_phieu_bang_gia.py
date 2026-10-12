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
