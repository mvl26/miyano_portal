"""Khớp dòng gõ tay trên Quotation và chốt gửi khách (spec 2026-10-12 §3.3, §4.2)."""

import frappe
from frappe.model.workflow import apply_workflow
from frappe.utils import add_days, getdate, nowdate

from miyano_portal import bao_gia
from miyano_portal.portal_mua_le import ITEM_GIU_CHO, ben_mua
from miyano_portal.tests.nen_bao_gia import NenBaoGia

DONG_GO_TAY = {"ten_hang": "Kim sinh thiết thử", "dvt": "Cái", "so_luong": 2}


class TestBaoGiaGuiKhach(NenBaoGia):
	def _bao_gia(self, items=None, dat_ngoai=None):
		kq = bao_gia.tao_bao_gia(
			self.kh_a,
			items=[{"item_code": self.item_boi_so, "qty": 20}] if items is None else items,
			dat_ngoai=dat_ngoai or [], request_id=frappe.generate_hash(length=12),
			khoa_phong=self.khoa_huyethoc,
		)
		return frappe.get_doc("Quotation", kq["bao_gia"])

	def _dien_gia(self, bg, gia=7000):
		for d in bg.items:
			if not d.rate:
				d.rate = gia
				d.price_list_rate = gia
		bg.save()
		return bg

	def test_ben_mua(self):
		bg = self._bao_gia()
		self.assertEqual(ben_mua(bg), self.kh_a)
		so = frappe.new_doc("Sales Order")
		so.customer = self.kh_b
		self.assertEqual(ben_mua(so), self.kh_b)

	def test_khop_ma_co_gia_bang_gia_nhan_gia_bang(self):
		"""Review Focus 3 — Quotation không có cột `customer`."""
		bg = self._bao_gia(items=[], dat_ngoai=[DONG_GO_TAY])
		bg.custom_dat_ngoai[0].item_khop = self.item_ngoai
		bg.save()
		bg.reload()
		self.assertEqual([d.item_code for d in bg.items], [self.item_ngoai])
		self.assertEqual(bg.items[0].qty, 2)
		self.assertEqual(bg.items[0].rate, 54000)
		self.assertEqual(bg.items[0].custom_nguon_gia, "Bảng giá")
		self.assertEqual(bg.custom_dat_ngoai[0].da_xu_ly, 1)

	def test_khop_ma_chua_co_gia_thi_cho_bao_gia(self):
		bg = self._bao_gia(items=[], dat_ngoai=[DONG_GO_TAY])
		bg.custom_dat_ngoai[0].item_khop = self.item_boi_so
		bg.save()
		bg.reload()
		self.assertEqual(bg.items[0].rate, 0)
		self.assertEqual(bg.items[0].custom_nguon_gia, "Báo giá")
		self.assertNotIn(ITEM_GIU_CHO, [d.item_code for d in bg.items])

	def test_chan_khi_con_dong_go_tay_chua_khop(self):
		bg = self._dien_gia(self._bao_gia(dat_ngoai=[DONG_GO_TAY]))
		with self.assertRaises(frappe.ValidationError) as ctx:
			apply_workflow(bg, bao_gia.HD_GUI_KHACH)
		self.assertIn("Kim sinh thiết thử", str(ctx.exception))

	def test_chan_khi_con_dong_giu_cho(self):
		bg = self._bao_gia(items=[], dat_ngoai=[DONG_GO_TAY])
		with self.assertRaises(frappe.ValidationError) as ctx:
			apply_workflow(bg, bao_gia.HD_GUI_KHACH)
		self.assertIn(ITEM_GIU_CHO, str(ctx.exception))

	def test_chan_khi_con_dong_gia_khong(self):
		bg = self._bao_gia()
		with self.assertRaises(frappe.ValidationError) as ctx:
			apply_workflow(bg, bao_gia.HD_GUI_KHACH)
		self.assertIn(self.item_boi_so, str(ctx.exception))
		self.assertEqual(
			frappe.db.get_value("Quotation", bg.name, "workflow_state"), bao_gia.TT_CHO_MIYANO
		)

	def test_qua_chot_thi_co_han_hieu_luc(self):
		frappe.db.set_single_value("Miyano Portal Settings", "hieu_luc_bao_gia_ngay", 5)
		bg = self._dien_gia(self._bao_gia())
		bg = apply_workflow(bg, bao_gia.HD_GUI_KHACH)
		self.assertEqual(bg.workflow_state, bao_gia.TT_CHO_KHACH)
		self.assertEqual(getdate(bg.valid_till), getdate(add_days(nowdate(), 5)))
		self.assertTrue(bg.custom_ngay_gui_khach_duyet)

	def test_thu_hoi_xoa_han(self):
		bg = self._dien_gia(self._bao_gia())
		bg = apply_workflow(bg, bao_gia.HD_GUI_KHACH)
		bg = apply_workflow(bg, bao_gia.HD_THU_HOI)
		self.assertFalse(bg.valid_till)
		self.assertFalse(bg.custom_ngay_gui_khach_duyet)
		self.assertEqual(bg.items[0].rate, 7000)

	def test_bao_gia_noi_bo_khong_bi_chot(self):
		bg = self._bao_gia_tho(nguon="Nội bộ")
		bg.items[0].rate = 0
		bg.items[0].price_list_rate = 0
		bg.save()
		bg = apply_workflow(bg, bao_gia.HD_GUI_KHACH)
		self.assertEqual(bg.workflow_state, bao_gia.TT_CHO_KHACH)
		self.assertFalse(bg.valid_till)
