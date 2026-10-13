"""Patch v1_42 — trường của Quotation và lựa chọn "Theo báo giá" (spec 2026-10-12 §3, §9)."""

import frappe
from frappe.tests.utils import FrappeTestCase

from miyano_portal.patches.v1_42 import bao_gia_quotation


class TestPatchBaoGiaQuotation(FrappeTestCase):
	def test_truong_tren_quotation(self):
		bao_gia_quotation.them_truong()
		meta = frappe.get_meta("Quotation")
		for ten in (
			"custom_nguon_don", "custom_de_xuat", "custom_khoa_phong",
			"custom_ten_don_hang", "custom_request_id",
			"custom_ngay_gui_khach_duyet", "custom_ly_do_tu_choi", "custom_dat_ngoai",
		):
			self.assertTrue(meta.has_field(ten), ten)
		self.assertEqual(meta.get_field("custom_dat_ngoai").options, "Sales Order Dat Ngoai Item")
		self.assertEqual(meta.get_field("custom_ngay_gui_khach_duyet").fieldtype, "Datetime")
		self.assertTrue(meta.get_field("custom_request_id").unique)

	def test_truong_khong_chep_sang_ban_sao_va_don(self):
		bao_gia_quotation.them_truong()
		meta = frappe.get_meta("Quotation")
		for ten in (
			"custom_request_id", "custom_ngay_gui_khach_duyet",
			"custom_ly_do_tu_choi", "custom_dat_ngoai",
			# Bản sao / bản amend trên Desk không có mã yêu cầu: nó phải là báo
			# giá "Nội bộ", không mang phiếu, khoa và tên của yêu cầu gốc.
			"custom_nguon_don", "custom_de_xuat", "custom_khoa_phong", "custom_ten_don_hang",
		):
			self.assertEqual(meta.get_field(ten).no_copy, 1, ten)

	def test_truong_da_co_duoc_cap_nhat_no_copy(self):
		"""Site đã chạy patch bản trước: `create_custom_fields` phải SỬA Custom
		Field đang có, không chỉ tạo field mới."""
		ten = frappe.db.get_value(
			"Custom Field", {"dt": "Quotation", "fieldname": "custom_nguon_don"}, "name"
		)
		frappe.db.set_value("Custom Field", ten, "no_copy", 0)
		frappe.clear_cache(doctype="Quotation")
		bao_gia_quotation.them_truong()
		self.assertEqual(frappe.db.get_value("Custom Field", ten, "no_copy"), 1)
		self.assertEqual(frappe.get_meta("Quotation").get_field("custom_nguon_don").no_copy, 1)

	def test_dau_nguon_gia_tren_dong_bao_gia(self):
		bao_gia_quotation.them_truong()
		truong = frappe.get_meta("Quotation Item").get_field("custom_nguon_gia")
		self.assertEqual(truong.options, "\nBảng giá\nBáo giá")
		self.assertEqual(truong.no_copy, 1)

	def test_phieu_co_truong_bao_gia(self):
		bao_gia_quotation.them_truong()
		truong = frappe.get_meta("Portal De Xuat Mua").get_field("bao_gia")
		self.assertEqual((truong.fieldtype, truong.options), ("Link", "Quotation"))
		self.assertEqual(truong.no_copy, 1)

	def test_lua_chon_theo_bao_gia(self):
		bao_gia_quotation.them_truong()
		lua_chon = frappe.get_meta("Sales Order").get_field("custom_loai_don").options.split("\n")
		self.assertIn("Theo báo giá", lua_chon)
		self.assertIn("Mua lẻ", lua_chon)

	def test_chay_hai_lan_cung_ket_qua(self):
		bao_gia_quotation.them_truong()
		bao_gia_quotation.them_truong()
		lua_chon = frappe.get_meta("Sales Order").get_field("custom_loai_don").options.split("\n")
		self.assertEqual(lua_chon.count("Theo báo giá"), 1)
		self.assertEqual(
			frappe.db.count("Custom Field", {"dt": "Quotation", "fieldname": "custom_request_id"}), 1
		)
