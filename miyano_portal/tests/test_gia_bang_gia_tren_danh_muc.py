"""Màn Đặt hàng hiện giá từ Price List của khách (chủ đầu tư 09/10/2026).

Bước đầu của mục 7 "Hiển thị hàng hoá và đơn giá theo Price List của Khách
hàng": một mặt hàng KHÔNG thuộc hợp đồng khung nào nhưng CÓ giá trong
`Customer.default_price_list` thì danh mục trả kèm đơn giá đó.

Bản này CHỈ HIỆN GIÁ. `tang` vẫn là `"cho_bao_gia"` vì đường dựng đơn
(`dat_hang._xay_don`) chưa đổi: dòng ngoài hợp đồng vẫn vào đơn với giá 0 và
chờ Miyano báo giá. Đổi `tang` trước khi đường dựng đơn đổi là để màn hình
hứa "đặt ngay theo giá này" trong khi server vẫn đưa đơn đi vòng báo giá.
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

	def test_hang_ngoai_hop_dong_co_gia_bang_gia_thi_hien_gia(self):
		self._tao_gia(self.item_ngoai, self.price_list, 54000)
		row = self._dong(self.item_ngoai)
		self.assertEqual(row["don_gia"], 54000.0)
		self.assertEqual(row["nguon_don_gia"], "bang_gia")

	def test_hien_gia_KHONG_doi_tang_va_khong_mang_han_muc(self):
		"""Đường dựng đơn chưa đổi — dòng này vẫn đi vòng báo giá, nên `tang`
		và các khoá hạn mức phải y như một dòng chờ báo giá."""
		self._tao_gia(self.item_ngoai, self.price_list, 54000)
		row = self._dong(self.item_ngoai)
		self.assertEqual(row["tang"], "cho_bao_gia")
		self.assertIsNone(row["blanket_order"])
		self.assertIsNone(row["remaining"])
		self.assertFalse(row["khong_gioi_han"])

	def test_hang_chua_co_gia_van_la_None(self):
		row = self._dong(self.item_ngoai)
		self.assertIsNone(row["don_gia"])
		self.assertIsNone(row["nguon_don_gia"])

	def test_gia_0_la_CHUA_khai_gia_khong_phai_ban_0_dong(self):
		self._tao_gia(self.item_ngoai, self.price_list, 0)
		row = self._dong(self.item_ngoai)
		self.assertIsNone(row["don_gia"])
		self.assertIsNone(row["nguon_don_gia"])

	def test_gia_trong_bang_gia_cua_khach_KHAC_khong_lo_sang(self):
		"""Giá Miyano dành cho một bệnh viện là thông tin thương mại của
		riêng bệnh viện đó."""
		bang_khac = "_TEST DX GOP PRICE KHAC"
		if not frappe.db.exists("Price List", bang_khac):
			frappe.get_doc({
				"doctype": "Price List", "price_list_name": bang_khac,
				"currency": "VND", "selling": 1, "enabled": 1,
			}).insert(ignore_permissions=True)
		self._tao_gia(self.item_ngoai, bang_khac, 99000)
		row = self._dong(self.item_ngoai)
		self.assertIsNone(row["don_gia"])

	def test_hang_hop_dong_ghi_nguon_la_hop_dong(self):
		row = self._dong(self.item_hd)
		self.assertEqual(row["tang"], "hop_dong")
		self.assertEqual(row["nguon_don_gia"], "hop_dong")


# Mượn các hàm dựng dữ liệu của bộ test danh mục gộp — MỘT bộ fixture cho
# cùng một endpoint, không chép lần hai rồi trôi lệch.
for _ten, _ham in vars(goc.TestPortalCatalogGop).items():
	if _ten.startswith("_") and not _ten.startswith("__") and callable(_ham):
		if _ten not in vars(TestGiaBangGiaTrenDanhMuc):
			setattr(TestGiaBangGiaTrenDanhMuc, _ten, _ham)
