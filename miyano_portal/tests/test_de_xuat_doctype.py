"""Guard cấu trúc của `Portal De Xuat Mua` (spec §5.2).

Ba guard ở đây đều là chốt DỮ LIỆU, không phải chốt phân quyền — chốt phân
quyền theo phiên đăng nhập nằm ở endpoint (Task 5) và hook (Task 4). Doctype
không tự biết ai đang gọi nó, nên không giả vờ kiểm điều đó.
"""

import frappe
from frappe.tests.utils import FrappeTestCase


class TestDeXuatGuard(FrappeTestCase):
	def setUp(self):
		# FrappeTestCase rollback MỘT LẦN cho cả class → tự dọn ở đây.
		for dt in ("Portal De Xuat Mua",):
			for r in frappe.get_all(dt, filters={"customer": ["like", "_TEST DX%"]}):
				frappe.delete_doc(dt, r.name, force=True)
		self.kh_a = self._customer("_TEST DX A", "DXA")
		self.kh_b = self._customer("_TEST DX B", "DXB")
		self.khoa_a = self._khoa(self.kh_a, "Huyết học", "HUYETHOC")
		self.khoa_b = self._khoa(self.kh_b, "Dược", "DUOC")

	def _customer(self, ten, ma_ngan):
		if not frappe.db.exists("Customer", ten):
			frappe.get_doc({
				"doctype": "Customer", "customer_name": ten,
				"customer_group": frappe.db.get_value("Customer Group", {}, "name"),
				"territory": frappe.db.get_value("Territory", {}, "name"),
			}).insert(ignore_permissions=True)
		frappe.db.set_value("Customer", ten, "custom_ma_ngan", ma_ngan)
		return ten

	def _khoa(self, customer, ten, ma):
		ten_bp = frappe.db.get_value(
			"Customer Department", {"customer": customer, "ma_khoa": ma}, "name"
		)
		if ten_bp:
			return ten_bp
		return frappe.get_doc({
			"doctype": "Customer Department", "customer": customer,
			"ten_khoa_phong": ten, "ma_khoa": ma, "active": 1,
		}).insert(ignore_permissions=True).name

	def _phieu(self, customer, khoa_phong, **kw):
		doc = frappe.get_doc({
			"doctype": "Portal De Xuat Mua",
			"customer": customer, "khoa_phong": khoa_phong,
			"loai_don": kw.pop("loai_don", "HĐNT"),
			"items": kw.pop("items", [
				{"item_code": self._item(), "so_luong_de_xuat": 5},
			]),
			**kw,
		})
		return doc

	def _item(self):
		ten = "_TEST DX ITEM"
		if not frappe.db.exists("Item", ten):
			frappe.get_doc({
				"doctype": "Item", "item_code": ten, "item_name": ten,
				"item_group": frappe.db.get_value("Item Group", {}, "name"),
				"stock_uom": "Nos", "is_stock_item": 0,
			}).insert(ignore_permissions=True)
		return ten

	def test_khoa_phong_phai_thuoc_dung_benh_vien(self):
		"""Khoa của bệnh viện B không gắn được lên phiếu của bệnh viện A."""
		doc = self._phieu(self.kh_a, self.khoa_b)
		with self.assertRaises(frappe.ValidationError) as ctx:
			doc.insert(ignore_permissions=True)
		# KHÔNG dùng assertRaises(ValidationError) trần: frappe.MandatoryError
		# là con của ValidationError nên một phiếu thiếu field bắt buộc cũng
		# làm test này XANH vì lý do hoàn toàn khác.
		self.assertIn("không thuộc", str(ctx.exception))

	def test_khoa_phong_dung_benh_vien_thi_luu_duoc(self):
		"""VẾ DƯƠNG — bắt buộc theo Global Constraints."""
		doc = self._phieu(self.kh_a, self.khoa_a)
		doc.insert(ignore_permissions=True)
		self.assertEqual(doc.trang_thai, "Nháp")
		self.assertFalse(doc.ma_de_xuat)
