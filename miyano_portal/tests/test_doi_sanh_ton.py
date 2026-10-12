"""Đối sánh tồn kho trên Sales Order và Material Request cho phần thiếu.

Spec: docs/superpowers/specs/2026-10-12-doi-sanh-ton-kho-khi-tao-so-design.md

BA ĐIỀU ĐỊNH HÌNH BỘ TEST NÀY:

1. **Đây là tồn của MIYANO (`Bin`), không phải tồn của bệnh viện** (CR-04,
   `kho/can_cu_duyet.py`). Hai nguồn, hai người đọc.

2. **Không tra được thì trả `None`, KHÔNG trả 0.** "Tồn 0" nghĩa là hết hàng.

3. **Tài khoản cổng khách hàng ĐỌC ĐƯỢC đơn của chính họ**, nên chốt quyền
   phải là danh sách vai nội bộ — kiểm "đọc được Sales Order" là để lọt đúng
   người cần chặn.
"""

import frappe
from frappe.tests.utils import FrappeTestCase

from miyano_portal import doi_sanh_ton as dst


class TestSlConGiao(FrappeTestCase):
	def test_chua_giao_gi_thi_bang_stock_qty(self):
		self.assertEqual(dst.sl_con_giao(stock_qty=20, qty=2, delivered_qty=0), 20)

	def test_giao_mot_phan_chi_con_phan_chua_giao(self):
		"""2 Thùng = 20 Hộp, đã giao 0,5 Thùng -> còn 15 Hộp."""
		self.assertEqual(dst.sl_con_giao(stock_qty=20, qty=2, delivered_qty=0.5), 15)

	def test_giao_thua_khong_ra_so_am(self):
		self.assertEqual(dst.sl_con_giao(stock_qty=10, qty=10, delivered_qty=12), 0)

	def test_qty_bang_0_khong_chia(self):
		self.assertEqual(dst.sl_con_giao(stock_qty=0, qty=0, delivered_qty=0), 0)


class TestTonKhaDung(FrappeTestCase):
	def test_khong_co_lo_het_han_thi_chi_tru_phan_da_giu(self):
		self.assertEqual(dst.ton_kha_dung(100, 0, 30), 70)

	def test_tru_lo_het_han_roi_tru_phan_da_giu(self):
		"""Tồn 100, trong đó 40 đã hết hạn; đơn khác giữ 10."""
		self.assertEqual(dst.ton_kha_dung(100, 40, 10), 50)

	def test_moi_lo_deu_het_han_thi_ve_0(self):
		self.assertEqual(dst.ton_kha_dung(100, 100, 0), 0)

	def test_don_khac_giu_nhieu_hon_ton_thi_ve_0_khong_am(self):
		self.assertEqual(dst.ton_kha_dung(4, 0, 10), 0)


class TestChiaTon(FrappeTestCase):
	def test_hai_dong_cung_mat_hang_chia_nhau_mot_luong_ton(self):
		"""Tồn 10, hai dòng mỗi dòng 6: dòng sau chỉ thấy 4 còn lại.

		Không có bài này thì hai dòng cùng báo "đủ" trên cùng 10 cái.
		"""
		k = ("A", "Kho 1")
		kq = dst.chia_ton([(k, 6), (k, 6)], {k: 10})
		self.assertEqual(kq, [(10, 0), (4, 2)])

	def test_khac_kho_thi_khong_chia_nhau(self):
		k1, k2 = ("A", "Kho 1"), ("A", "Kho 2")
		kq = dst.chia_ton([(k1, 6), (k2, 6)], {k1: 10, k2: 1})
		self.assertEqual(kq, [(10, 0), (1, 5)])

	def test_khong_sua_dict_dau_vao(self):
		k = ("A", "Kho 1")
		nguon = {k: 10}
		dst.chia_ton([(k, 6)], nguon)
		self.assertEqual(nguon, {k: 10})


class TestDeXuat(FrappeTestCase):
	def test_du_hang(self):
		self.assertEqual(
			dst.de_xuat(0, 0), {"ma": dst.DX_DU, "mr_da_phu": 0, "can_mua": 0}
		)

	def test_thieu_chua_co_mr(self):
		self.assertEqual(
			dst.de_xuat(6, 0), {"ma": dst.DX_CAN_MUA, "mr_da_phu": 0, "can_mua": 6}
		)

	def test_mr_phu_mot_phan(self):
		self.assertEqual(
			dst.de_xuat(6, 4), {"ma": dst.DX_MOT_PHAN, "mr_da_phu": 4, "can_mua": 2}
		)

	def test_mr_phu_het(self):
		self.assertEqual(
			dst.de_xuat(6, 6), {"ma": dst.DX_DA_CO_MR, "mr_da_phu": 6, "can_mua": 0}
		)

	def test_mr_nhieu_hon_thieu_thi_chi_tinh_bang_phan_thieu(self):
		"""MR 10 nhưng nay chỉ còn thiếu 6: không hiện "đã có MR 10" cho 6 cái."""
		self.assertEqual(
			dst.de_xuat(6, 10), {"ma": dst.DX_DA_CO_MR, "mr_da_phu": 6, "can_mua": 0}
		)

	def test_du_hang_ma_van_con_mr_thi_van_la_du(self):
		self.assertEqual(dst.de_xuat(0, 5)["ma"], dst.DX_DU)


class TestLyDoKhongTra(FrappeTestCase):
	"""Bốn ca của spec §5.5 (ca đặt ngoài nằm ở `bang_cho_don`)."""

	TON = frappe._dict(is_stock_item=1, has_batch_no=0)

	def _dong(self, **kw):
		d = frappe._dict(item_code="A", warehouse="Kho 1", delivered_by_supplier=0)
		d.update(kw)
		return d

	def test_dong_binh_thuong_tra_duoc(self):
		self.assertIsNone(dst.ly_do_khong_tra(self._dong(), self.TON, False))

	def test_hang_khong_quan_ly_ton(self):
		khong_ton = frappe._dict(is_stock_item=0, has_batch_no=0)
		self.assertEqual(
			dst.ly_do_khong_tra(self._dong(), khong_ton, False), dst.LY_DO_KHONG_TON
		)

	def test_item_khong_con_ton_tai(self):
		self.assertEqual(
			dst.ly_do_khong_tra(self._dong(), None, False), dst.LY_DO_KHONG_TON
		)

	def test_bo_san_pham(self):
		"""Mã gộp của Product Bundle luôn là hàng KHÔNG quản lý tồn — lý do
		phải là "bộ sản phẩm", không bị ca "không quản lý tồn" che mất."""
		khong_ton = frappe._dict(is_stock_item=0, has_batch_no=0)
		self.assertEqual(
			dst.ly_do_khong_tra(self._dong(), khong_ton, True), dst.LY_DO_BO
		)

	def test_giao_thang(self):
		self.assertEqual(
			dst.ly_do_khong_tra(self._dong(delivered_by_supplier=1), self.TON, False),
			dst.LY_DO_GIAO_THANG,
		)

	def test_khong_co_kho(self):
		self.assertEqual(
			dst.ly_do_khong_tra(self._dong(warehouse=None), self.TON, False),
			dst.LY_DO_KHONG_KHO,
		)
