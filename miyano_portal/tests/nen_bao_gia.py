"""Dữ liệu nền cho mọi test của Quotation (kế hoạch 2026-10-13).

Mượn `setUp` của `TestPortalCatalogGop` (khách A/B, khoa, mặt hàng, Price List)
như `test_chot_bao_gia`, rồi đưa hai mặt hàng về đúng một trạng thái giá:
`item_ngoai` CÓ giá 54000, `item_boi_so` CHƯA có giá.
"""

import frappe
from frappe.tests.utils import FrappeTestCase

from miyano_portal import bao_gia
from miyano_portal.tests import test_catalog_gop as goc


class NenBaoGia(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		# Bản Workflow trong cache tài liệu không theo giao dịch: xoá SAU rollback.
		cls.addClassCleanup(frappe.clear_document_cache, "Workflow", bao_gia.WORKFLOW)
		super().setUpClass()
		from miyano_portal.patches.v1_42 import bao_gia_quotation

		bao_gia_quotation.execute()

	def setUp(self):
		goc.TestPortalCatalogGop.setUp(self)
		for ma in (self.item_ngoai, self.item_boi_so):
			for ten in frappe.get_all(
				"Item Price", filters={"item_code": ma, "selling": 1}, pluck="name"
			):
				frappe.delete_doc("Item Price", ten, force=True)
		self._tao_gia(self.item_ngoai, self.price_list, 54000)
		for ten in frappe.get_all(
			"Quotation", filters={"party_name": ["like", "_TEST DX%"], "docstatus": 0},
			pluck="name",
		):
			frappe.delete_doc("Quotation", ten, force=True)

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.flags.bao_gia_dong_y_qua_cong = None

	# Mượn nguyên các hàm dựng dữ liệu của lớp gốc.
	_tao_item = goc.TestPortalCatalogGop._tao_item
	_tao_bin = goc.TestPortalCatalogGop._tao_bin
	_tao_price_list = goc.TestPortalCatalogGop._tao_price_list
	_tao_gia = goc.TestPortalCatalogGop._tao_gia
	_dam_bao_thanh_vien = goc.TestPortalCatalogGop._dam_bao_thanh_vien

	def _quan_ly(self, email, khach):
		return self._dam_bao_thanh_vien(email, khach, "Quản lý", None)

	def _bao_gia_tho(self, nguon="Client Portal", khach=None, khoa=None, **them):
		"""Một Quotation chèn thẳng, không qua `bao_gia.tao_bao_gia` (Task 5)."""
		bg = frappe.get_doc({
			"doctype": "Quotation", "quotation_to": "Customer",
			"party_name": khach or self.kh_a, "company": goc.COMPANY,
			"selling_price_list": self.price_list, "ignore_pricing_rule": 1,
			"custom_nguon_don": nguon, "custom_khoa_phong": khoa,
			"custom_request_id": frappe.generate_hash(length=12),
			"items": [{
				"item_code": self.item_ngoai, "qty": 10,
				"rate": 54000, "price_list_rate": 54000,
			}],
			**them,
		})
		bg.insert(ignore_permissions=True)
		# Trả bản NẠP LẠI: `insert(ignore_permissions=True)` để lại
		# `flags.ignore_permissions` trên đối tượng, và `frappe.has_permission`
		# / `frappe.has_website_permission` cho qua ngay khi thấy cờ đó — mọi
		# test về quyền trên đối tượng vừa chèn sẽ xanh giả.
		return frappe.get_doc("Quotation", bg.name)


class NenBaoGiaTheoDot(NenBaoGia):
	"""Nền cho test báo giá theo đợt (kế hoạch 2026-10-16)."""

	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		from miyano_portal.patches.v1_45 import bao_gia_theo_dot

		bao_gia_theo_dot.execute()

	def setUp(self):
		# Đợt trỏ về phiếu gốc bằng Link: xoá đợt TRƯỚC khi lớp cha xoá phiếu gốc.
		for ten in frappe.get_all(
			"Quotation",
			filters={"party_name": ["like", "_TEST DX%"], "custom_phieu_goc": ["is", "set"]},
			pluck="name",
		):
			frappe.db.set_value("Quotation", ten, "docstatus", 0, update_modified=False)
			# `ignore_on_trash`: hook `chan_xoa_dot` chặn xoá đợt nháp còn mặt hàng.
			frappe.delete_doc("Quotation", ten, force=True, ignore_on_trash=True)
		super().setUp()

	def _goc_ba_dong(self, **them):
		"""Yêu cầu báo giá của cổng, ba mặt hàng đều đã có giá, ở «Chờ Miyano báo giá»."""
		gia = {self.item_ngoai: 54000, self.item_boi_so: 7000, self.item_co_dau: 12000}
		return self._bao_gia_tho(
			items=[
				{"item_code": ma, "qty": 10, "rate": g, "price_list_rate": g}
				for ma, g in gia.items()
			],
			**them,
		)

	def _nhan_vien(self, email="dot.nv@demo.miyano"):
		"""Nhân viên chỉ có vai Sales User."""
		if not frappe.db.exists("User", email):
			frappe.get_doc({
				"doctype": "User", "email": email, "first_name": "NV đợt",
				"send_welcome_email": 0, "roles": [{"role": "Sales User"}],
			}).insert(ignore_permissions=True)
		return email
