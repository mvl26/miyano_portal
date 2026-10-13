"""Tên hiển thị của mặt hàng trên cổng — MỘT nguồn cho mọi bảng.

Chủ đầu tư 13/10/2026: mọi bảng mặt hàng của cổng (Chọn hàng, Giỏ hàng, Chi
tiết đơn/phiếu, Kiểm hàng, Báo giá) hiện cùng ba cột Mã → Tên mặt hàng → Tên
thường gọi. `ten_hang.thong_tin_ten_hang` là hàm duy nhất trả hai tên đó;
`portal_ten_hang` là cửa của SPA. Tên thường gọi là của TỪNG khách — tên bệnh
viện A đặt không được lộ sang bệnh viện B.

Mượn bộ fixture của `test_catalog_gop` (hai khách, hai Portal Member thật).
"""

from types import SimpleNamespace

import frappe
from frappe.tests.utils import FrappeTestCase

from miyano_portal import ten_hang
from miyano_portal.api import hang_hoa as hang_hoa_api
from miyano_portal.api import portal as portal_api
from miyano_portal.tests import test_catalog_gop as goc


class TestTenHang(FrappeTestCase):
	def setUp(self):
		goc.TestPortalCatalogGop.setUp(self)
		frappe.db.delete("Item Ten Thuong Goi", {"parent": ["like", "_TEST DX%"]})

	def tearDown(self):
		frappe.set_user("Administrator")

	def _dat_ten_goi(self, item_code, ten, customer):
		item = frappe.get_doc("Item", item_code)
		item.append("custom_ten_thuong_goi", {"ten_thuong_goi": ten, "customer": customer})
		item.save(ignore_permissions=True)

	def test_tra_ten_xuat_hoa_don_va_ten_thuong_goi_cua_khach(self):
		self._dat_ten_goi(self.item_ngoai, "Ống đỏ", self.kh_a)
		self._dat_ten_goi(self.item_ngoai, "Ống EDTA", self.kh_a)
		out = ten_hang.thong_tin_ten_hang(self.kh_a, [self.item_ngoai])
		self.assertEqual(out[self.item_ngoai]["item_name"],
			frappe.db.get_value("Item", self.item_ngoai, "item_name"))
		# Đúng thứ tự Miyano nhập trên Item.
		self.assertEqual(out[self.item_ngoai]["ten_thuong_goi"], ["Ống đỏ", "Ống EDTA"])

	def test_ten_thuong_goi_cua_khach_khac_khong_lo(self):
		self._dat_ten_goi(self.item_ngoai, "Bí danh của B", self.kh_b)
		out = ten_hang.thong_tin_ten_hang(self.kh_a, [self.item_ngoai])
		self.assertEqual(out[self.item_ngoai]["ten_thuong_goi"], [])

	def test_ma_khong_co_ten_thuong_goi_van_co_mat_voi_danh_sach_rong(self):
		out = ten_hang.thong_tin_ten_hang(self.kh_a, [self.item_ngoai, self.item_co_dau])
		self.assertEqual(set(out), {self.item_ngoai, self.item_co_dau})
		self.assertEqual(out[self.item_co_dau]["ten_thuong_goi"], [])

	def test_ma_la_va_ma_rong_bi_bo_qua(self):
		out = ten_hang.thong_tin_ten_hang(self.kh_a, ["_KHONG CO MA NAY", "", None, self.item_ngoai])
		self.assertEqual(set(out), {self.item_ngoai})
		self.assertEqual(ten_hang.thong_tin_ten_hang(self.kh_a, []), {})

	def test_endpoint_suy_khach_tu_phien_dang_nhap(self):
		self._dat_ten_goi(self.item_ngoai, "Tên của A", self.kh_a)
		self._dat_ten_goi(self.item_ngoai, "Tên của B", self.kh_b)
		frappe.set_user(self.user_a)
		# SPA gửi danh sách mã dạng chuỗi JSON.
		out = hang_hoa_api.portal_ten_hang(item_codes=frappe.as_json([self.item_ngoai]))
		self.assertEqual(out[self.item_ngoai]["ten_thuong_goi"], ["Tên của A"])

	def test_endpoint_tu_choi_qua_nhieu_ma(self):
		frappe.set_user(self.user_a)
		with self.assertRaises(frappe.ValidationError):
			hang_hoa_api.portal_ten_hang(item_codes=[f"M{i}" for i in range(ten_hang.SO_MA_TOI_DA + 1)])

	def test_danh_muc_va_ham_chung_noi_cung_mot_ten(self):
		"""Màn Chọn hàng và các bảng khác không được ra hai kết quả."""
		self._dat_ten_goi(self.item_ngoai, "Một tên", self.kh_a)
		frappe.set_user(self.user_a)
		row = self._row(portal_api.portal_catalog_gop(tu_khoa=self.item_ngoai)["rows"], self.item_ngoai)
		chung = hang_hoa_api.portal_ten_hang(item_codes=[self.item_ngoai])[self.item_ngoai]
		self.assertEqual(row["ten_thuong_goi"], chung["ten_thuong_goi"])
		self.assertEqual(row["item_name"], chung["item_name"])

	def test_thu_xac_nhan_don_ghi_ma_roi_ten(self):
		"""Thư gửi khách theo cùng thứ tự Mã → Tên với cổng, Desk và mẫu in."""
		from miyano_portal.setup.install_notifications import DEFS

		mau = next(d["message"] for d in DEFS if d["name"] == "Portal - Đơn xác nhận")
		# Không dùng `frappe._dict`: `doc.items` sẽ ra `dict.items`.
		doc = SimpleNamespace(name="SO-X", delivery_date="2026-10-16", items=[
			SimpleNamespace(item_code="MA-01", item_name="Tên rất dài " * 20, delivery_date="2026-10-16"),
		])
		thu = frappe.render_template(mau, {"doc": doc})
		self.assertIn("- MA-01 — " + "Tên rất dài " * 20, thu)


# Mượn các hàm dựng dữ liệu (`_tao_item`, `_row`, …) của lớp gốc, không mượn
# test — cùng cách `test_gia_bang_gia_tren_danh_muc.py`.
for _ten, _ham in vars(goc.TestPortalCatalogGop).items():
	if _ten.startswith("_") and not _ten.startswith("__") and callable(_ham) and not hasattr(TestTenHang, _ten):
		setattr(TestTenHang, _ten, _ham)
