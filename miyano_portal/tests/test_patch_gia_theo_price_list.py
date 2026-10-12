from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from miyano_portal import bang_gia_khach as bg
from miyano_portal import dat_hang
from miyano_portal.patches.v1_41 import gia_theo_price_list as patch_moi
from miyano_portal.tests import test_catalog_gop as goc


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


class TestChuyenDuLieu(FrappeTestCase):
	"""Phần DỮ LIỆU của patch (spec 2026-10-09 §6). `chuyen_du_lieu()` quét MỌI
	khách của site; các bài dưới chỉ khẳng định về khách `_TEST DX%` của fixture."""

	def setUp(self):
		goc.TestPortalCatalogGop.setUp(self)

	def tearDown(self):
		frappe.set_user("Administrator")

	def test_khach_dung_chung_bang_duoc_tach(self):
		frappe.db.set_value("Customer", self.kh_b, "default_price_list", self.price_list)
		patch_moi.chuyen_du_lieu()
		a = frappe.db.get_value("Customer", self.kh_a, "default_price_list")
		b = frappe.db.get_value("Customer", self.kh_b, "default_price_list")
		self.assertTrue(a)
		self.assertTrue(b)
		self.assertNotEqual(a, b)

	def test_khach_chua_co_bang_duoc_tao_bang(self):
		frappe.db.set_value("Customer", self.kh_b, "default_price_list", None)
		patch_moi.chuyen_du_lieu()
		b = frappe.db.get_value("Customer", self.kh_b, "default_price_list")
		self.assertTrue(b)
		self.assertEqual(
			frappe.get_all("Customer", filters={"default_price_list": b}, pluck="name"),
			[self.kh_b],
		)

	def test_gia_hop_dong_duoc_chep_sang_bang_gia(self):
		"""Hợp đồng A khai 125.000 cho `item_hd`; xoá dòng giá để mô phỏng
		khách chỉ có giá nhờ hợp đồng (ca của Minh Đức)."""
		for ten in frappe.get_all(
			"Item Price", filters={"item_code": self.item_hd, "selling": 1}, pluck="name"
		):
			frappe.delete_doc("Item Price", ten, force=True)
		self.assertIsNone(bg.gia_bang_gia(self.kh_a, self.item_hd))
		patch_moi.chuyen_du_lieu()
		self.assertEqual(bg.gia_bang_gia(self.kh_a, self.item_hd), 125000.0)

	def test_chay_hai_lan_khong_doi_ket_qua(self):
		patch_moi.chuyen_du_lieu()
		truoc = frappe.db.count("Item Price", {"selling": 1})
		so_bang = frappe.db.count("Price List")
		bang = frappe.db.get_value("Customer", self.kh_a, "default_price_list")
		patch_moi.chuyen_du_lieu()
		self.assertEqual(frappe.db.count("Item Price", {"selling": 1}), truoc)
		self.assertEqual(frappe.db.count("Price List"), so_bang)
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

	def test_mot_khach_loi_khong_chan_khach_khac(self):
		"""Site thật có dữ liệu hỏng: khách B ném lỗi ở bước bảng giá riêng thì
		khách A vẫn phải được tách bảng và chép giá hợp đồng; lỗi nằm trong
		Error Log kèm tên khách B, và B không bị bỏ lại nửa chừng."""
		frappe.db.set_value("Customer", self.kh_b, "default_price_list", None)
		for ten in frappe.get_all(
			"Item Price", filters={"item_code": self.item_hd, "selling": 1}, pluck="name"
		):
			frappe.delete_doc("Item Price", ten, force=True)
		that = bg.dam_bao_bang_gia_rieng

		def _hong_voi_b(customer):
			if customer == self.kh_b:
				raise RuntimeError("bang gia hong")
			return that(customer)

		with patch.object(bg, "dam_bao_bang_gia_rieng", side_effect=_hong_voi_b):
			patch_moi.chuyen_du_lieu()   # không được ném lỗi

		self.assertEqual(bg.gia_bang_gia(self.kh_a, self.item_hd), 125000.0)
		self.assertFalse(frappe.db.get_value("Customer", self.kh_b, "default_price_list"))
		log = frappe.get_all(
			"Error Log", filters={"method": ["like", f"%{self.kh_b}%"]}, pluck="name"
		)
		self.assertTrue(log, "lỗi của khách B phải nằm trong Error Log kèm tên khách")
		frappe.db.delete("Error Log", {"name": ["in", log]})


for _ten, _ham in vars(goc.TestPortalCatalogGop).items():
	if _ten.startswith("_") and not _ten.startswith("__") and callable(_ham):
		if _ten not in vars(TestChuyenDuLieu):
			setattr(TestChuyenDuLieu, _ten, _ham)
