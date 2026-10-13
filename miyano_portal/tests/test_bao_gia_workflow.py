"""Workflow "Quotation - Client Portal" (spec 2026-10-12 §4.1)."""

import frappe
from frappe.model.workflow import apply_workflow, get_transitions

from miyano_portal import bao_gia
from miyano_portal.setup import install_workflow
from miyano_portal.tests.nen_bao_gia import NenBaoGia


class TestBaoGiaWorkflow(NenBaoGia):
	def test_cai_dat_chay_lai_duoc(self):
		install_workflow.install_quotation_workflow()
		install_workflow.install_quotation_workflow()
		wf = frappe.get_doc("Workflow", bao_gia.WORKFLOW)
		self.assertEqual(wf.document_type, "Quotation")
		self.assertEqual(wf.is_active, 1)
		self.assertEqual(len(wf.states), 6)
		self.assertEqual(len(wf.transitions), 8)

	def test_workflow_don_hang_van_hoat_dong(self):
		self.assertEqual(
			frappe.db.get_value("Workflow", "Sales Order - Client Portal", "is_active"), 1
		)

	def test_trang_thai_va_docstatus(self):
		wf = frappe.get_doc("Workflow", bao_gia.WORKFLOW)
		theo_ten = {s.state: int(s.doc_status) for s in wf.states}
		self.assertEqual(theo_ten, {
			bao_gia.TT_CHO_MIYANO: 0, bao_gia.TT_CHO_KHACH: 0, bao_gia.TT_DA_DONG_Y: 1,
			bao_gia.TT_KHACH_TU_CHOI: 0, bao_gia.TT_MIYANO_TU_CHOI: 0, bao_gia.TT_HET_HAN: 0,
		})
		self.assertEqual(wf.states[0].state, bao_gia.TT_CHO_MIYANO)

	def test_buoc_phia_khach_chi_cho_system_manager(self):
		wf = frappe.get_doc("Workflow", bao_gia.WORKFLOW)
		for t in wf.transitions:
			if t.action in (
				bao_gia.HD_KHACH_DONG_Y, bao_gia.HD_KHACH_TU_CHOI,
				bao_gia.HD_KHACH_SUA_SL, bao_gia.HD_HET_HAN,
			):
				self.assertEqual(t.allowed, "System Manager", t.action)

	def test_bao_gia_moi_o_cho_miyano_bao_gia(self):
		bg = self._bao_gia_tho()
		self.assertEqual(bg.workflow_state, bao_gia.TT_CHO_MIYANO)
		self.assertEqual(bg.docstatus, 0)

	def test_bao_gia_noi_bo_nhan_vien_ghi_nhan_dong_y(self):
		bg = self._bao_gia_tho(nguon="Nội bộ")
		bg = apply_workflow(bg, bao_gia.HD_GUI_KHACH)
		bg = apply_workflow(bg, bao_gia.HD_GHI_NHAN)
		self.assertEqual((bg.workflow_state, bg.docstatus), (bao_gia.TT_DA_DONG_Y, 1))

	def test_bao_gia_cong_khong_co_buoc_ghi_nhan(self):
		bg = self._bao_gia_tho()
		frappe.db.set_value("Quotation", bg.name, "workflow_state", bao_gia.TT_CHO_KHACH)
		bg.reload()
		hanh_dong = {t["action"] for t in get_transitions(bg)}
		self.assertNotIn(bao_gia.HD_GHI_NHAN, hanh_dong)

	def test_khong_dong_y_thay_khach_cong_tren_desk(self):
		"""Review Focus 6 — Administrator có vai System Manager nên workflow cho
		bấm "Khách đồng ý"; hook `before_submit` phải chặn."""
		bg = self._bao_gia_tho()
		frappe.db.set_value("Quotation", bg.name, "workflow_state", bao_gia.TT_CHO_KHACH)
		bg.reload()
		with self.assertRaises(frappe.ValidationError) as ctx:
			apply_workflow(bg, bao_gia.HD_KHACH_DONG_Y)
		self.assertIn("trên cổng", str(ctx.exception))
		self.assertEqual(frappe.db.get_value("Quotation", bg.name, "docstatus"), 0)

	def test_miyano_tu_choi_bat_buoc_ly_do(self):
		bg = self._bao_gia_tho()
		with self.assertRaises(frappe.ValidationError):
			apply_workflow(bg, bao_gia.HD_TU_CHOI)
		bg.reload()
		bg.custom_ly_do_tu_choi = "Miyano không phân phối mặt hàng này."
		bg.save()
		bg = apply_workflow(bg, bao_gia.HD_TU_CHOI)
		self.assertEqual(bg.workflow_state, bao_gia.TT_MIYANO_TU_CHOI)

	def test_thu_hoi_de_sua(self):
		bg = self._bao_gia_tho(nguon="Nội bộ")
		bg = apply_workflow(bg, bao_gia.HD_GUI_KHACH)
		bg = apply_workflow(bg, bao_gia.HD_THU_HOI)
		self.assertEqual(bg.workflow_state, bao_gia.TT_CHO_MIYANO)

	def test_gan_trang_thai_cho_bao_gia_co_san(self):
		bg = self._bao_gia_tho(nguon="Nội bộ")
		frappe.db.set_value("Quotation", bg.name, "workflow_state", None)
		self.assertGreaterEqual(install_workflow.gan_trang_thai_bao_gia_cu(), 1)
		self.assertEqual(
			frappe.db.get_value("Quotation", bg.name, "workflow_state"), bao_gia.TT_CHO_MIYANO
		)
		self.assertEqual(install_workflow.gan_trang_thai_bao_gia_cu(), 0)
