"""Guard cấu trúc của `Portal De Xuat Mua` (spec §5.2).

Ba guard ở đây đều là chốt DỮ LIỆU, không phải chốt phân quyền — chốt phân
quyền theo phiên đăng nhập nằm ở endpoint (Task 5) và hook (Task 4). Doctype
không tự biết ai đang gọi nó, nên không giả vờ kiểm điều đó.
"""

import frappe
from frappe.tests.utils import FrappeTestCase

from miyano_portal.tests.fixtures_de_xuat import dung_fixture


class TestDeXuatGuard(FrappeTestCase):
	def setUp(self):
		# FrappeTestCase rollback MỘT LẦN cho cả class → fixture tự dọn phiếu
		# cũ bên trong `dung_fixture`.
		f = dung_fixture(self)
		self.kh_a, self.kh_b = f.kh_a, f.kh_b
		self.khoa_a, self.khoa_b = f.khoa_huyethoc, f.khoa_duoc
		self.item = f.item

	def _phieu(self, customer, khoa_phong, **kw):
		doc = frappe.get_doc({
			"doctype": "Portal De Xuat Mua",
			"customer": customer, "khoa_phong": khoa_phong,
			"loai_don": kw.pop("loai_don", "HĐNT"),
			"items": kw.pop("items", [
				{"item_code": self.item, "so_luong_de_xuat": 5},
			]),
			**kw,
		})
		return doc

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
