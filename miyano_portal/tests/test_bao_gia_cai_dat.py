"""Mẫu in, thông báo và hàng việc của Quotation (spec 2026-10-12 §7, §9)."""

from pathlib import Path

import frappe
from frappe.model.workflow import apply_workflow

from miyano_portal import bao_gia
from miyano_portal.patches.v1_42 import bao_gia_quotation
from miyano_portal.setup import install_kho_workspace, install_notifications, install_print_formats
from miyano_portal.tests.nen_bao_gia import NenBaoGia

JS = Path(frappe.get_app_path("miyano_portal", "public", "js"))


class TestBaoGiaCaiDat(NenBaoGia):
	def test_mau_in_cho_quotation(self):
		pf = frappe.get_doc("Print Format", install_print_formats.NAME_YCBG)
		self.assertEqual(pf.doc_type, "Quotation")
		self.assertEqual(install_print_formats.NAME_YCBG, "Miyano - Yêu cầu báo giá")

	def test_mau_in_dung_duoc(self):
		bg = apply_workflow(self._bao_gia_tho(), bao_gia.HD_GUI_KHACH)
		html = frappe.get_print(
			"Quotation", bg.name, print_format=install_print_formats.NAME_YCBG
		)
		self.assertIn(self.item_ngoai, html)
		self.assertIn("54.000", html)
		self.assertIn(frappe.utils.formatdate(bg.valid_till, "dd/mm/yyyy"), html)

	def test_thong_bao_cho_quotation(self):
		tb = frappe.get_doc("Notification", install_notifications.TEN_TB_BAO_GIA)
		self.assertEqual((tb.document_type, tb.event, tb.value_changed),
		                 ("Quotation", "Value Change", "workflow_state"))
		self.assertEqual(tb.print_format, install_print_formats.NAME_YCBG)
		self.assertEqual(tb.attach_print, 1)
		bg = self._bao_gia_tho()
		ngu_canh = {"doc": bg, "frappe": frappe}
		self.assertFalse(frappe.safe_eval(tb.condition, None, ngu_canh))
		bg.workflow_state = bao_gia.TT_CHO_KHACH
		self.assertTrue(frappe.safe_eval(tb.condition, None, ngu_canh))
		bg.custom_nguon_don = "Nội bộ"
		self.assertFalse(frappe.safe_eval(tb.condition, None, ngu_canh))

	def test_loi_tat_hang_viec(self):
		ws = frappe.get_doc("Workspace", install_kho_workspace.TITLE)
		sc = [s for s in ws.shortcuts if s.label == "Yêu cầu báo giá"]
		self.assertEqual(len(sc), 1)
		self.assertEqual(sc[0].link_to, "Quotation")
		loc = frappe.parse_json(sc[0].stats_filter)
		self.assertEqual(loc, {
			"custom_nguon_don": "Client Portal", "workflow_state": bao_gia.TT_CHO_MIYANO,
		})

	def test_patch_chay_hai_lan(self):
		bao_gia_quotation.execute()
		bao_gia_quotation.execute()
		self.assertEqual(frappe.db.count("Workflow", {"document_type": "Quotation"}), 1)
		self.assertEqual(
			frappe.db.count("Print Format", {"name": install_print_formats.NAME_YCBG}), 1
		)
		self.assertEqual(
			frappe.db.count("Notification", {"name": install_notifications.TEN_TB_BAO_GIA}), 1
		)

	def test_khoi_hang_moi_dung_chung_hai_form(self):
		chung = (JS / "hang_moi_khach_khai.js").read_text()
		self.assertIn("miyano_portal.hien_thong_tin_hang_moi = function", chung)
		self.assertIn("Hàng chưa có mã — thông tin khách khai", chung)
		for ten in ("sales_order.js", "quotation.js"):
			nguon = (JS / ten).read_text()
			self.assertIn("miyano_portal.hien_thong_tin_hang_moi(frm)", nguon, ten)
			self.assertNotIn("function hien_thong_tin_hang_moi", nguon, ten)
		js = frappe.get_hooks("doctype_js")
		for dt in ("Sales Order", "Quotation"):
			self.assertIn("public/js/hang_moi_khach_khai.js", js[dt], dt)
			self.assertIn("public/js/dat_ngoai_anh.js", js[dt], dt)
