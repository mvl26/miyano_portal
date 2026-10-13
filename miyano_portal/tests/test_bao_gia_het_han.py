"""Hết hạn, quá hạn xử lý và nhật ký của báo giá (spec 2026-10-12 §4.6, §7)."""

from unittest.mock import patch

import frappe
from frappe.model import workflow as wf_goc
from frappe.model.workflow import apply_workflow
from frappe.utils import add_days, add_to_date, getdate, now_datetime, nowdate

from miyano_portal import bao_gia, nhat_ky, portal_bao_gia, portal_sla
from miyano_portal.tests.nen_bao_gia import NenBaoGia


class TestBaoGiaHetHan(NenBaoGia):
	def _cho_khach(self, **them):
		bg = self._bao_gia_tho(khoa=self.khoa_huyethoc, **them)
		return apply_workflow(bg, bao_gia.HD_GUI_KHACH)

	def _lui_han(self, bg, so_ngay):
		frappe.db.set_value("Quotation", bg.name, {
			"valid_till": add_days(nowdate(), -so_ngay),
			"transaction_date": add_days(nowdate(), -so_ngay - 7),
		}, update_modified=False)

	def test_bao_gia_qua_han_bi_dong(self):
		bg = self._cho_khach()
		self._lui_han(bg, 1)
		self.assertEqual(bao_gia.quet_het_han(), 1)
		self.assertEqual(
			frappe.db.get_value("Quotation", bg.name, ["workflow_state", "docstatus"]),
			(bao_gia.TT_HET_HAN, 0),
		)

	def test_bao_gia_con_han_khong_bi_dung(self):
		bg = self._cho_khach()
		self.assertEqual(bao_gia.quet_het_han(), 0)
		self.assertEqual(
			frappe.db.get_value("Quotation", bg.name, "workflow_state"), bao_gia.TT_CHO_KHACH
		)

	def test_bao_gia_noi_bo_khong_bi_job_dong(self):
		bg = apply_workflow(self._bao_gia_tho(nguon="Nội bộ"), bao_gia.HD_GUI_KHACH)
		self._lui_han(bg, 30)
		self.assertEqual(bao_gia.quet_het_han(), 0)
		self.assertEqual(
			frappe.db.get_value("Quotation", bg.name, "workflow_state"), bao_gia.TT_CHO_KHACH
		)

	def test_het_han_dung_ngay_cuoi_van_con_hieu_luc(self):
		bg = self._cho_khach()
		self._lui_han(bg, 0)
		self.assertEqual(bao_gia.quet_het_han(), 0)

	def test_job_hang_ngay_quet_ca_quotation(self):
		bg = self._cho_khach()
		self._lui_han(bg, 2)
		self.assertGreaterEqual(portal_bao_gia.quet_bao_gia_het_han(), 1)
		self.assertEqual(
			frappe.db.get_value("Quotation", bg.name, "workflow_state"), bao_gia.TT_HET_HAN
		)

	def test_het_han_ghi_nhat_ky(self):
		phieu = frappe.get_doc({
			"doctype": "Portal De Xuat Mua", "customer": self.kh_a,
			"khoa_phong": self.khoa_huyethoc, "ly_do_yeu_cau": "Hết hàng trong kho khoa",
			"items": [{"item_code": self.item_boi_so, "so_luong_de_xuat": 10}],
		}).insert(ignore_permissions=True)
		bg = self._cho_khach(custom_de_xuat=phieu.name)
		self._lui_han(bg, 1)
		bao_gia.quet_het_han()
		su_kien = frappe.get_all(
			nhat_ky.DOCTYPE, filters={"de_xuat": phieu.name}, pluck="su_kien"
		)
		self.assertIn(nhat_ky.SK_MIYANO_BAO_GIA, su_kien)
		self.assertIn(nhat_ky.SK_BAO_GIA_HET_HAN, su_kien)

	def test_sla_nhac_bao_gia_treo(self):
		bg = self._bao_gia_tho(khoa=self.khoa_huyethoc)
		frappe.db.set_value(
			"Quotation", bg.name, "modified", add_to_date(now_datetime(), days=-14),
			update_modified=False,
		)
		portal_sla.quet_don_treo()
		self.assertTrue(frappe.db.exists(
			"Notification Log", {"subject": f"{portal_sla.TIEU_DE_BAO_GIA}: {bg.name}"}
		))

	def test_sla_khong_nhac_bao_gia_noi_bo_va_bao_gia_dang_o_phia_khach(self):
		noi_bo = self._bao_gia_tho(nguon="Nội bộ")
		o_khach = self._cho_khach()
		for bg in (noi_bo, o_khach):
			frappe.db.set_value(
				"Quotation", bg.name, "modified", add_to_date(now_datetime(), days=-14),
				update_modified=False,
			)
		portal_sla.quet_don_treo()
		for bg in (noi_bo, o_khach):
			self.assertFalse(frappe.db.exists(
				"Notification Log", {"subject": f"{portal_sla.TIEU_DE_BAO_GIA}: {bg.name}"}
			))

	# ---- M1: một báo giá hỏng không làm dừng cả đợt quét

	def test_mot_bao_gia_loi_khong_dung_ca_dot_quet(self):
		hong, lanh = self._cho_khach(), self._cho_khach()
		for bg in (hong, lanh):
			self._lui_han(bg, 1)
		that = wf_goc.apply_workflow

		def gia(doc, hanh_dong):
			if doc.name == hong.name:
				raise frappe.ValidationError("báo giá này lưu hỏng")
			return that(doc, hanh_dong)

		with patch.object(wf_goc, "apply_workflow", side_effect=gia):
			self.assertEqual(bao_gia.quet_het_han(), 1)
		self.assertEqual(
			frappe.db.get_value("Quotation", lanh.name, "workflow_state"), bao_gia.TT_HET_HAN
		)
		self.assertEqual(
			frappe.db.get_value("Quotation", hong.name, "workflow_state"), bao_gia.TT_CHO_KHACH
		)
		self.assertTrue(frappe.db.exists(
			"Error Log", {"reference_doctype": "Quotation", "reference_name": hong.name}
		))
		self.assertFalse(frappe.db.exists(
			"Error Log", {"reference_doctype": "Quotation", "reference_name": lanh.name}
		))
		# Đợt quét sau (hết lỗi) đóng nốt báo giá còn lại.
		self.assertEqual(bao_gia.quet_het_han(), 1)

	# ---- I4: mở lại báo giá hết hạn

	def _het_han_tu_yeu_cau(self):
		kq = bao_gia.tao_bao_gia(
			self.kh_a, items=[{"item_code": self.item_boi_so, "qty": 20}],
			request_id=frappe.generate_hash(length=12), khoa_phong=self.khoa_huyethoc,
		)
		bg = frappe.get_doc("Quotation", kq["bao_gia"])
		bg.items[0].rate = bg.items[0].price_list_rate = 7000
		bg.save()
		bg = apply_workflow(bg, bao_gia.HD_GUI_KHACH)
		self._lui_han(bg, 3)
		self.assertEqual(bao_gia.quet_het_han(), 1)
		bg.reload()
		self.assertEqual(bg.workflow_state, bao_gia.TT_HET_HAN)
		return bg

	def test_mo_lai_xoa_han_cu_giu_don_gia(self):
		bg = self._het_han_tu_yeu_cau()
		self.assertTrue(bg.valid_till)
		self.assertTrue(bg.custom_ngay_gui_khach_duyet)
		bg = apply_workflow(bg, bao_gia.HD_MO_LAI)
		bg.reload()
		self.assertEqual((bg.workflow_state, bg.docstatus), (bao_gia.TT_CHO_MIYANO, 0))
		self.assertFalse(bg.valid_till)
		self.assertFalse(bg.custom_ngay_gui_khach_duyet)
		self.assertEqual(bg.items[0].rate, 7000)

	def test_tron_vong_het_han_mo_lai_gui_lai_khach_dong_y(self):
		ql = self._quan_ly("bghh.ql@demo.miyano", self.kh_a)
		bg = self._het_han_tu_yeu_cau()
		bg = apply_workflow(bg, bao_gia.HD_MO_LAI)
		bg = apply_workflow(bg, bao_gia.HD_GUI_KHACH)
		self.assertEqual(bg.workflow_state, bao_gia.TT_CHO_KHACH)
		self.assertGreaterEqual(getdate(bg.valid_till), getdate(nowdate()))
		self.assertTrue(bg.custom_ngay_gui_khach_duyet)
		frappe.set_user(ql)
		try:
			kq = bao_gia.dong_y(bg.name)
		finally:
			frappe.set_user("Administrator")
		self.assertEqual(kq["trang_thai_moi"], bao_gia.TT_DA_DONG_Y)
		so = frappe.get_doc("Sales Order", kq["sales_order"])
		self.assertEqual((so.custom_loai_don, so.items[0].rate), ("Theo báo giá", 7000))

	def test_bao_gia_noi_bo_mo_lai_khong_bi_dung_han(self):
		"""Hook chỉ dọn hạn cho báo giá của cổng."""
		bg = apply_workflow(self._bao_gia_tho(nguon="Nội bộ"), bao_gia.HD_GUI_KHACH)
		han = bg.valid_till
		frappe.db.set_value("Quotation", bg.name, "workflow_state", bao_gia.TT_HET_HAN)
		bg.reload()
		bg = apply_workflow(bg, bao_gia.HD_MO_LAI)
		self.assertEqual(bg.workflow_state, bao_gia.TT_CHO_MIYANO)
		self.assertEqual(getdate(bg.valid_till), getdate(han))
