"""`resolve_ban_le_company(currency=...)` chỉ chọn company cùng tiền bảng giá.

Lỗi thật (DXM-2026-00059, 14/10/2026): mặt hàng chỉ khai Item Default ở
`_Test Company` (INR) kéo yêu cầu báo giá bảng giá VND sang company đó, và
ERPNext dừng ở "Exchange Rate is mandatory ... VND to INR" khi duyệt.
"""

import frappe
from frappe.tests.utils import FrappeTestCase

from miyano_portal.portal_mua_le import resolve_ban_le_company

ITEM = "_TEST RESOLVE TIEN TE"


def _company_va_kho(khac_tien: str):
	"""Một company có `default_currency` khác `khac_tien` và một kho lá của nó."""
	for c in frappe.get_all(
		"Company", filters={"default_currency": ["!=", khac_tien]}, pluck="name", order_by="name"
	):
		kho = frappe.db.get_value("Warehouse", {"company": c, "is_group": 0, "disabled": 0})
		if kho:
			return c, frappe.db.get_value("Company", c, "default_currency"), kho
	return None, None, None


class TestResolveCompanyTienTe(FrappeTestCase):
	def setUp(self):
		self.mac_dinh = frappe.defaults.get_global_default("company")
		self.tien = frappe.db.get_value("Company", self.mac_dinh, "default_currency")
		self.cty_khac, self.tien_khac, kho = _company_va_kho(self.tien)
		if not self.cty_khac:
			self.skipTest("Site chỉ có company một loại tiền")
		if frappe.db.exists("Item", ITEM):
			frappe.delete_doc("Item", ITEM, force=True, ignore_permissions=True)
		doc = frappe.get_doc({
			"doctype": "Item", "item_code": ITEM, "item_name": ITEM,
			"item_group": frappe.db.get_value("Item Group", {"is_group": 0}),
			"stock_uom": frappe.db.get_value("UOM", {}) or "Nos", "is_stock_item": 1,
		})
		doc.append("item_defaults", {"company": self.cty_khac, "default_warehouse": kho})
		doc.insert(ignore_permissions=True)

	def tearDown(self):
		frappe.db.rollback()

	def test_khong_truyen_tien_giu_hanh_vi_cu(self):
		self.assertEqual(resolve_ban_le_company([ITEM]), self.cty_khac)

	def test_bang_gia_khac_tien_thi_khong_chon_company_cua_item_default(self):
		ket_qua = resolve_ban_le_company([ITEM], currency=self.tien)
		self.assertEqual(ket_qua, self.mac_dinh)
		self.assertEqual(
			frappe.db.get_value("Company", ket_qua, "default_currency"), self.tien
		)

	def test_bang_gia_cung_tien_voi_item_default_thi_van_chon_company_do(self):
		self.assertEqual(
			resolve_ban_le_company([ITEM], currency=self.tien_khac), self.cty_khac
		)
