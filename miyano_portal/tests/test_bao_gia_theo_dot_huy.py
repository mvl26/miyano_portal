"""Huỷ phần còn lại của phiếu gốc (spec 2026-10-15 §4.4, §6)."""

from unittest.mock import patch

import frappe
from frappe.model.workflow import apply_workflow

from miyano_portal import bao_gia, bao_gia_theo_dot as dot
from miyano_portal.tests.nen_bao_gia import NenBaoGiaTheoDot


class TestHuyConLai(NenBaoGiaTheoDot):
	def setUp(self):
		super().setUp()
		self.ql = self._quan_ly("dothuy.ql@demo.miyano", self.kh_a)
		self.goc = self._goc_ba_dong(contact_email="khach.dot@demo.miyano")
		self.d1 = dot.tach_dot(
			self.goc.name, [d.name for d in self.goc.items if d.item_code == self.item_ngoai]
		)["dot"]
		self.goc.reload()

	def _khach_huy(self, ly_do=None):
		frappe.set_user(self.ql)
		try:
			return dot.huy_con_lai_boi_khach(self.goc.name, ly_do)
		finally:
			frappe.set_user("Administrator")

	def test_miyano_phai_ghi_ly_do(self):
		with self.assertRaisesRegex(frappe.ValidationError, "lý do"):
			apply_workflow(self.goc, bao_gia.HD_HUY_CON_LAI)
		self.goc.reload()
		self.goc.custom_ly_do_huy_con_lai = "Khách chuyển sang mua thầu"
		self.goc.save()
		with patch("frappe.sendmail") as gui:
			goc = apply_workflow(self.goc, bao_gia.HD_HUY_CON_LAI)
		self.assertEqual(goc.workflow_state, bao_gia.TT_HUY_CON_LAI)
		self.assertEqual(goc.custom_nguoi_huy_con_lai, "Administrator")
		self.assertEqual(gui.call_args.kwargs["recipients"], ["khach.dot@demo.miyano"])
		self.assertIn("Khách chuyển sang mua thầu", gui.call_args.kwargs["message"])

	def test_khach_huy_khong_can_ly_do(self):
		frappe.db.set_value("Customer", self.kh_a, "account_manager", "Administrator")
		with patch("frappe.sendmail") as gui, patch("miyano_portal.bao_gia.bao_nhan_vien") as bao:
			kq = self._khach_huy()
		self.assertEqual(kq["trang_thai_moi"], bao_gia.TT_HUY_CON_LAI)
		self.goc.reload()
		self.assertEqual(self.goc.custom_nguoi_huy_con_lai, bao_gia.NGUOI_KHACH)
		self.assertEqual(gui.call_args.kwargs["recipients"], ["Administrator"])
		# Người nhận Notification Log tuỳ dữ liệu site: kiểm lời gọi, không kiểm bảng.
		self.assertIn("huỷ phần còn lại", bao.call_args.args[1])

	def test_khach_huy_ghi_ly_do_neu_co(self):
		with patch("frappe.sendmail"):
			self._khach_huy("Đã mua chỗ khác")
		self.assertEqual(
			frappe.db.get_value("Quotation", self.goc.name, "custom_ly_do_huy_con_lai"),
			"Đã mua chỗ khác",
		)

	def test_dot_dang_cho_van_con_hieu_luc_roi_tu_choi_khong_tra_ve(self):
		with patch("frappe.sendmail"):
			self._khach_huy()
		self.assertEqual(frappe.db.get_value("Quotation", self.d1, "workflow_state"), bao_gia.TT_CHO_KHACH)
		frappe.set_user(self.ql)
		try:
			bao_gia.tu_choi(self.d1)
		finally:
			frappe.set_user("Administrator")
		self.goc.reload()
		self.assertNotIn(self.item_ngoai, [d.item_code for d in self.goc.items])
		self.assertEqual(self.goc.workflow_state, bao_gia.TT_HUY_CON_LAI)
		self.assertFalse(frappe.db.get_value("Quotation", self.d1, "custom_da_tra_ve"))

	def test_khach_khong_huy_duoc_phieu_chua_tach(self):
		goc = self._goc_ba_dong()
		frappe.set_user(self.ql)
		try:
			with self.assertRaises(frappe.ValidationError):
				dot.huy_con_lai_boi_khach(goc.name)
		finally:
			frappe.set_user("Administrator")

	def test_khach_khong_huy_duoc_phieu_da_bao_het(self):
		self.goc.reload()
		dot.tach_dot(self.goc.name, [d.name for d in self.goc.items])
		with self.assertRaises(frappe.ValidationError):
			self._khach_huy()

	def test_khach_huy_khong_ly_do_xoa_ly_do_nhan_vien_go_do(self):
		"""Nhân viên gõ lý do, lưu, CHƯA chuyển trạng thái; khách huỷ không lý do
		thì lý do cũ không được đi theo việc huỷ của khách."""
		frappe.db.set_value("Customer", self.kh_a, "account_manager", "Administrator")
		self.goc.custom_ly_do_huy_con_lai = "Nhân viên gõ dở, chưa bấm huỷ"
		self.goc.save()
		with patch("frappe.sendmail") as gui, patch("miyano_portal.bao_gia.bao_nhan_vien") as bao:
			self._khach_huy()
		self.assertEqual(
			frappe.db.get_value("Quotation", self.goc.name, "custom_ly_do_huy_con_lai") or "", ""
		)
		self.assertNotIn("Lý do", gui.call_args.kwargs["message"])
		self.assertNotIn("Lý do", bao.call_args.args[2])

	def test_khach_huy_doc_lai_phieu_goc_co_khoa(self):
		"""`apply_workflow` nạp lại phiếu gốc trước khi lưu. Nó nhận lại CHÍNH đối
		tượng đã nạp `for_update=True` nên lần nạp lại đó cũng khoá (cả bảng con):
		dòng một đợt vừa trả về đồng thời không bị lần lưu này đánh rơi."""
		from frappe.model import workflow
		from frappe.model.document import Document

		goc_ap, goc_nap = workflow.apply_workflow, Document.load_from_db
		lan_nap_lai = []

		def ap(doc, action):
			dau = []

			def nap(d):
				if not dau:  # lần nạp ĐẦU TIÊN trong apply_workflow = nạp lại chứng từ
					dau.append((d is doc, bool(d.flags.for_update)))
				return goc_nap(d)

			with patch.object(Document, "load_from_db", nap):
				kq = goc_ap(doc, action)
			if doc.name == self.goc.name:
				lan_nap_lai.extend(dau)
			return kq

		with patch("frappe.sendmail"), patch.object(workflow, "apply_workflow", ap):
			self._khach_huy()
		self.assertEqual(lan_nap_lai, [(True, True)])
