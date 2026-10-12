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
