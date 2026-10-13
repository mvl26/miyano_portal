"""Dựng Quotation từ giỏ hàng (spec 2026-10-12 §3, §5)."""

import frappe

from miyano_portal import bao_gia
from miyano_portal.portal_mua_le import ITEM_GIU_CHO
from miyano_portal.tests.nen_bao_gia import NenBaoGia

DONG_GO_TAY = {"ten_hang": "Kim sinh thiết thử", "dvt": "Cái", "so_luong": 2, "hang_san_xuat": "ACME"}


class TestTaoBaoGia(NenBaoGia):
	def _rid(self):
		return frappe.generate_hash(length=12)

	def _tao(self, **them):
		tham_so = {
			"items": [
				{"item_code": self.item_ngoai, "qty": 10},
				{"item_code": self.item_boi_so, "qty": 20},
			],
			"request_id": self._rid(), "khoa_phong": self.khoa_huyethoc,
		}
		tham_so.update(them)
		kq = bao_gia.tao_bao_gia(self.kh_a, **tham_so)
		return kq, frappe.get_doc("Quotation", kq["bao_gia"])

	def test_can_bao_gia(self):
		co_gia = [{"item_code": self.item_ngoai, "qty": 10}]
		chua_gia = [{"item_code": self.item_boi_so, "qty": 10}]
		self.assertFalse(bao_gia.can_bao_gia(self.kh_a, co_gia, []))
		self.assertTrue(bao_gia.can_bao_gia(self.kh_a, co_gia + chua_gia, []))
		self.assertTrue(bao_gia.can_bao_gia(self.kh_a, co_gia, [DONG_GO_TAY]))

	def test_dau_chung_tu(self):
		kq, bg = self._tao()
		self.assertFalse(kq["da_ton_tai"])
		self.assertEqual((bg.quotation_to, bg.party_name), ("Customer", self.kh_a))
		self.assertEqual(bg.order_type, "Sales")
		self.assertEqual(bg.custom_nguon_don, "Client Portal")
		self.assertEqual(bg.custom_khoa_phong, self.khoa_huyethoc)
		self.assertEqual((bg.workflow_state, bg.docstatus), (bao_gia.TT_CHO_MIYANO, 0))
		self.assertEqual(bg.selling_price_list, self.price_list)
		self.assertEqual(bg.ignore_pricing_rule, 1)
		self.assertFalse(bg.valid_till)

	def test_dong_co_gia_nhan_gia_dong_chua_gia_bang_khong(self):
		_kq, bg = self._tao()
		theo_ma = {d.item_code: d for d in bg.items}
		self.assertEqual(theo_ma[self.item_ngoai].rate, 54000)
		self.assertEqual(theo_ma[self.item_ngoai].custom_nguon_gia, "Bảng giá")
		self.assertEqual(theo_ma[self.item_boi_so].rate, 0)
		self.assertEqual(theo_ma[self.item_boi_so].custom_nguon_gia, "Báo giá")
		self.assertEqual(theo_ma[self.item_boi_so].qty, 20)

	def test_khong_sinh_sales_order(self):
		rid = self._rid()
		self._tao(request_id=rid)
		self.assertFalse(frappe.db.exists("Sales Order", {"custom_request_id": rid}))

	def test_dong_go_tay_vao_bang_rieng(self):
		_kq, bg = self._tao(dat_ngoai=[DONG_GO_TAY])
		self.assertEqual(len(bg.custom_dat_ngoai), 1)
		dong = bg.custom_dat_ngoai[0]
		self.assertEqual((dong.ten_hang, dong.so_luong, dong.hang_san_xuat),
		                 ("Kim sinh thiết thử", 2, "ACME"))
		self.assertEqual(dong.da_xu_ly, 0)
		self.assertNotIn(ITEM_GIU_CHO, [d.item_code for d in bg.items])

	def test_chi_co_dong_go_tay_thi_co_dong_giu_cho(self):
		_kq, bg = self._tao(items=[], dat_ngoai=[DONG_GO_TAY])
		self.assertEqual([d.item_code for d in bg.items], [ITEM_GIU_CHO])
		self.assertEqual(bg.items[0].rate, 0)

	def test_gui_trung_khong_sinh_bao_gia_thu_hai(self):
		rid = self._rid()
		kq1, _ = self._tao(request_id=rid)
		kq2, _ = self._tao(request_id=rid)
		self.assertEqual(kq1["bao_gia"], kq2["bao_gia"])
		self.assertTrue(kq2["da_ton_tai"])
		self.assertEqual(frappe.db.count("Quotation", {"custom_request_id": rid}), 1)

	def test_ma_yeu_cau_cua_khach_khac(self):
		rid = self._rid()
		self._tao(request_id=rid)
		with self.assertRaises(frappe.PermissionError):
			bao_gia.tao_bao_gia(
				self.kh_b, items=[{"item_code": self.item_boi_so, "qty": 10}], request_id=rid
			)

	def test_sai_boi_so_bi_chan_nhu_dat_hang(self):
		with self.assertRaises(frappe.ValidationError):
			self._tao(items=[{"item_code": self.item_boi_so, "qty": 7}])

	def test_khoa_cua_khach_khac_bi_tu_choi(self):
		with self.assertRaises(frappe.PermissionError):
			self._tao(khoa_phong=self.khoa_duoc)

	def test_thieu_ma_yeu_cau(self):
		with self.assertRaises(frappe.ValidationError):
			self._tao(request_id=None)
