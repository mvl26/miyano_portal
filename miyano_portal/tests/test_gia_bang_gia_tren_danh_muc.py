"""Danh mục đặt hàng phân tầng theo Price List của khách.

Spec `docs/superpowers/specs/2026-10-09-gia-theo-price-list-design.md` §3
(chủ đầu tư chốt 09/10/2026, Q3): mỗi dòng `portal_catalog_gop` thuộc đúng
một trong hai tầng — `"bang_gia"` (có giá dương, còn hiệu lực trong
`Customer.default_price_list`; `don_gia` là con số đó) hoặc `"cho_bao_gia"`
(`don_gia` là `None`). Hợp đồng khung KHÔNG còn quyết định tầng hay giá: bộ
fixture mượn của `test_catalog_gop` vẫn dựng hợp đồng đã nộp chính là để
chứng minh điều đó.
"""

import frappe
from frappe.tests.utils import FrappeTestCase

from miyano_portal.api import portal as portal_api
from miyano_portal.tests import test_catalog_gop as goc


class TestGiaBangGiaTrenDanhMuc(FrappeTestCase):
	def setUp(self):
		goc.TestPortalCatalogGop.setUp(self)
		# `FrappeTestCase` rollback MỘT lần cho cả class — giá của test trước
		# còn nguyên khi test sau chạy, nên mỗi test bắt đầu từ bảng trắng.
		self._xoa_gia(self.item_ngoai)

	def tearDown(self):
		frappe.set_user("Administrator")

	def _xoa_gia(self, item_code):
		for ten in frappe.get_all(
			"Item Price", filters={"item_code": item_code, "selling": 1}, pluck="name"
		):
			frappe.delete_doc("Item Price", ten, force=True, ignore_permissions=True)

	def _dong(self, item_code):
		frappe.set_user(self.user_a)
		try:
			out = portal_api.portal_catalog_gop(tu_khoa=item_code)
		finally:
			frappe.set_user("Administrator")
		return self._row(out["rows"], item_code)

	def test_hang_co_gia_la_tang_bang_gia(self):
		self._tao_gia(self.item_ngoai, self.price_list, 54000)
		row = self._dong(self.item_ngoai)
		self.assertEqual(row["tang"], "bang_gia")
		self.assertEqual(row["don_gia"], 54000.0)

	def test_hang_chua_co_gia_la_tang_cho_bao_gia(self):
		row = self._dong(self.item_ngoai)
		self.assertEqual(row["tang"], "cho_bao_gia")
		self.assertIsNone(row["don_gia"])

	def test_gia_0_la_cho_bao_gia(self):
		"""`<= 0` là CHƯA khai giá, không phải "bán 0 đồng"."""
		self._tao_gia(self.item_ngoai, self.price_list, 0)
		row = self._dong(self.item_ngoai)
		self.assertEqual(row["tang"], "cho_bao_gia")
		self.assertIsNone(row["don_gia"])

	# Đảo theo spec 2026-10-09 (giá theo Price List).
	def test_hang_thuoc_hop_dong_nhung_khong_co_gia_bang_gia_la_cho_bao_gia(self):
		"""Q3: hợp đồng không còn quyết định tầng. `setUp` đã đặt 111.000
		cho `item_hd` trong bảng giá — xoá nó thì hợp đồng một mình không
		cho ra giá nào."""
		self._xoa_gia(self.item_hd)
		row = self._dong(self.item_hd)
		self.assertEqual(row["tang"], "cho_bao_gia")
		self.assertIsNone(row["don_gia"])

	# Đảo theo spec 2026-10-09 (giá theo Price List).
	def test_hang_thuoc_hop_dong_lay_gia_BANG_GIA_khong_phai_gia_hop_dong(self):
		"""Hợp đồng khai 125.000, bảng giá 111.000 — cổng đọc bảng giá."""
		self._xoa_gia(self.item_hd)
		self._tao_gia(self.item_hd, self.price_list, 111000)
		row = self._dong(self.item_hd)
		self.assertEqual(row["tang"], "bang_gia")
		self.assertEqual(row["don_gia"], 111000.0)

	def test_dong_khong_con_khoa_hop_dong_va_han_muc(self):
		row = self._dong(self.item_ngoai)
		self.assertEqual(
			set(row), {"item_code", "item_name", "dvt", "boi_so", "nhom_vat_tu",
			           "ten_thuong_goi", "trang_thai_hang", "tang", "don_gia"},
		)

	def test_gia_bang_gia_cua_khach_khac_khong_lo_sang(self):
		"""Giá Miyano dành cho một bệnh viện là thông tin thương mại của
		riêng bệnh viện đó."""
		bang_khac = "_TEST DX GOP PRICE KHAC"
		if not frappe.db.exists("Price List", bang_khac):
			frappe.get_doc({
				"doctype": "Price List", "price_list_name": bang_khac,
				"currency": "VND", "selling": 1, "enabled": 1,
			}).insert(ignore_permissions=True)
		self._tao_gia(self.item_ngoai, bang_khac, 99000)
		self.assertIsNone(self._dong(self.item_ngoai)["don_gia"])


# Mượn các hàm dựng dữ liệu của bộ test danh mục gộp — MỘT bộ fixture cho
# cùng một endpoint, không chép lần hai rồi trôi lệch.
for _ten, _ham in vars(goc.TestPortalCatalogGop).items():
	if _ten.startswith("_") and not _ten.startswith("__") and callable(_ham):
		if _ten not in vars(TestGiaBangGiaTrenDanhMuc):
			setattr(TestGiaBangGiaTrenDanhMuc, _ten, _ham)
