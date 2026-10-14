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

	def test_thong_bao_miyano_tu_choi(self):
		ten = install_notifications.TEN_TB_BAO_GIA_TU_CHOI
		self.assertEqual(ten, "Portal - Yêu cầu báo giá bị từ chối")
		tb = frappe.get_doc("Notification", ten)
		self.assertEqual((tb.document_type, tb.event, tb.value_changed),
		                 ("Quotation", "Value Change", "workflow_state"))
		self.assertEqual((tb.enabled, tb.send_system_notification), (1, 1))
		self.assertEqual((tb.attach_print or 0, tb.print_format), (0, None))
		san_sang = frappe.get_doc("Notification", install_notifications.TEN_TB_BAO_GIA)
		self.assertEqual(
			[r.receiver_by_document_field for r in tb.recipients],
			[r.receiver_by_document_field for r in san_sang.recipients],
		)
		self.assertIn("doc.custom_ly_do_tu_choi", tb.message)

		bg = self._bao_gia_tho()
		ngu_canh = {"doc": bg, "frappe": frappe}
		# Chờ Miyano báo giá: không gửi.
		self.assertFalse(frappe.safe_eval(tb.condition, None, ngu_canh))
		# Khách tự từ chối: không phải tin báo cho khách.
		bg.workflow_state = bao_gia.TT_KHACH_TU_CHOI
		self.assertFalse(frappe.safe_eval(tb.condition, None, ngu_canh))
		bg.workflow_state = bao_gia.TT_MIYANO_TU_CHOI
		self.assertTrue(frappe.safe_eval(tb.condition, None, ngu_canh))
		# Báo giá nhân viên tự lập: không gửi.
		bg.custom_nguon_don = "Nội bộ"
		self.assertFalse(frappe.safe_eval(tb.condition, None, ngu_canh))

	def test_thong_bao_miyano_tu_choi_neu_ly_do(self):
		tb = frappe.get_doc("Notification", install_notifications.TEN_TB_BAO_GIA_TU_CHOI)
		bg = self._bao_gia_tho()
		bg.custom_ly_do_tu_choi = "Miyano không phân phối mặt hàng này."
		noi_dung = frappe.render_template(tb.message, {"doc": bg})
		self.assertIn("Miyano không phân phối mặt hàng này.", noi_dung)
		self.assertIn(bg.name, frappe.render_template(tb.subject, {"doc": bg}))

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
		self.assertEqual(
			frappe.db.count(
				"Notification", {"name": install_notifications.TEN_TB_BAO_GIA_TU_CHOI}
			), 1,
		)
		self.assertEqual(
			len(frappe.get_doc("Workflow", bao_gia.WORKFLOW).transitions), 9
		)

	def test_khoi_hang_moi_dung_chung_hai_form(self):
		chung = (JS / "hang_moi_khach_khai.js").read_text()
		self.assertIn("miyano_portal.hien_thong_tin_hang_moi = function", chung)
		self.assertIn("Hàng chưa có mã — thông tin khách khai", chung)
		nguon = (JS / "quotation.js").read_text()
		self.assertIn("miyano_portal.hien_thong_tin_hang_moi(frm)", nguon)
		self.assertNotIn("function hien_thong_tin_hang_moi", nguon)
		# Sales Order không còn bảng dòng gõ tay (patch v1_44).
		self.assertNotIn("hien_thong_tin_hang_moi", (JS / "sales_order.js").read_text())
		js = frappe.get_hooks("doctype_js")
		self.assertIn("public/js/hang_moi_khach_khai.js", js["Quotation"])
		self.assertIn("public/js/dat_ngoai_anh.js", js["Quotation"])
		self.assertNotIn("public/js/hang_moi_khach_khai.js", js["Sales Order"])
