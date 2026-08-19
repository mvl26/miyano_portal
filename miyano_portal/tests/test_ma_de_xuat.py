"""Sinh mã đề xuất (spec §6.1, §6.2)."""

import frappe
from frappe.tests.utils import FrappeTestCase

from miyano_portal import ma_de_xuat


from miyano_portal.tests.fixtures_de_xuat import dung_fixture


class TestMaDeXuat(FrappeTestCase):
	def setUp(self):
		# Bộ đếm sống trong `tabSeries`. `getseries` chạy SQL thường trong
		# CHÍNH transaction hiện tại (đã đọc `frappe/model/naming.py`: SELECT
		# ... FOR UPDATE rồi UPDATE, không commit riêng) — nên rollback CÓ
		# dọn nó. Nhưng `FrappeTestCase` rollback MỘT LẦN cho cả CLASS, nên
		# các test TRONG CÙNG class vẫn cộng dồn số của nhau: không dọn thì
		# `test_tran_sang_ba_chu_so` xanh/đỏ tuỳ thứ tự chạy.
		frappe.db.delete("Series", {"name": ["like", "DXA-%"]})
		frappe.db.delete("Series", {"name": ["like", "DXB-%"]})
		# Fixture dùng chung với test_de_xuat_doctype.py — tách ra module
		# riêng để hai bộ test không trôi lệch định nghĩa khách/khoa/vật tư.
		f = dung_fixture(self)
		self.khoa, self.khoa2 = f.khoa_huyethoc, f.khoa_duoc

	def test_cau_truc_ma(self):
		ma = ma_de_xuat.sinh_ma("_TEST DX A", self.khoa, ngay="2026-08-19")
		self.assertEqual(ma, "DXA-HUYETHOC-260819-01")

	def test_dem_rieng_cho_tung_khoa(self):
		"""Khoa khác nhau có dãy số RIÊNG, không dùng chung bộ đếm."""
		a1 = ma_de_xuat.sinh_ma("_TEST DX A", self.khoa, ngay="2026-08-19")
		b1 = ma_de_xuat.sinh_ma("_TEST DX A", self.khoa2, ngay="2026-08-19")
		a2 = ma_de_xuat.sinh_ma("_TEST DX A", self.khoa, ngay="2026-08-19")
		self.assertTrue(a1.endswith("-01"))
		self.assertTrue(b1.endswith("-01"))   # khoa khác → lại bắt đầu từ 01
		self.assertTrue(a2.endswith("-02"))

	def test_dem_rieng_cho_tung_ngay(self):
		h = ma_de_xuat.sinh_ma("_TEST DX A", self.khoa, ngay="2026-08-19")
		mai = ma_de_xuat.sinh_ma("_TEST DX A", self.khoa, ngay="2026-08-20")
		self.assertTrue(h.endswith("-01"))
		self.assertTrue(mai.endswith("-01"))

	def test_tran_sang_ba_chu_so_khong_quay_vong(self):
		"""§6.1: vượt 99 thì tràn sang 3 chữ số, KHÔNG quay vòng về 01."""
		for _ in range(99):
			ma_de_xuat.sinh_ma("_TEST DX A", self.khoa, ngay="2026-08-19")
		thu_100 = ma_de_xuat.sinh_ma("_TEST DX A", self.khoa, ngay="2026-08-19")
		self.assertTrue(thu_100.endswith("-100"), thu_100)

	def test_khong_co_khoa_thi_dung_ma_CHUNG(self):
		"""§5.5 — đơn 'Toàn viện' của quản lý."""
		ma = ma_de_xuat.sinh_ma("_TEST DX A", None, ngay="2026-08-19")
		self.assertEqual(ma, "DXA-CHUNG-260819-01")

	def test_thieu_ma_ngan_thi_bao_loi_tu_xu_ly_duoc(self):
		"""QĐ-A3 — không tự đoán mã bệnh viện."""
		frappe.db.set_value("Customer", "_TEST DX B", "custom_ma_ngan", None)
		with self.assertRaises(frappe.ValidationError) as ctx:
			ma_de_xuat.sinh_ma("_TEST DX B", None, ngay="2026-08-19")
		self.assertIn("Mã ngắn", str(ctx.exception))
