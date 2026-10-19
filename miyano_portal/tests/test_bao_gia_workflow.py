"""Workflow "Quotation - Client Portal" (spec 2026-10-12 §4.1)."""

import frappe
from frappe.model.workflow import apply_workflow, get_transitions

from miyano_portal import bao_gia
from miyano_portal.patches.v1_42 import bao_gia_quotation
from miyano_portal.setup import install_workflow
from miyano_portal.tests.nen_bao_gia import NenBaoGia


def _hinh_dang():
	"""Mọi bước chuyển của workflow đang cài, đủ năm cột mà bộ cài ghi."""
	wf = frappe.get_doc("Workflow", bao_gia.WORKFLOW)
	return [
		(t.state, t.action, t.next_state, t.allowed, t.condition or None,
		 int(t.allow_self_approval or 0))
		for t in wf.transitions
	]


def _hinh_dang_goc():
	return [(*t, 1) for t in install_workflow._bao_gia_transitions()]


class TestBaoGiaWorkflow(NenBaoGia):
	def test_cai_dat_chay_lai_duoc(self):
		install_workflow.install_quotation_workflow()
		install_workflow.install_quotation_workflow()
		wf = frappe.get_doc("Workflow", bao_gia.WORKFLOW)
		self.assertEqual(wf.document_type, "Quotation")
		self.assertEqual(wf.is_active, 1)
		self.assertEqual(len(wf.states), 8)
		self.assertEqual(len(wf.transitions), 12)

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
			bao_gia.TT_DA_BAO_HET: 0, bao_gia.TT_HUY_CON_LAI: 0,
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

	# ---- I4: mở lại báo giá hết hạn

	def _nguoi_dung_desk(self, email, vai):
		if not frappe.db.exists("User", email):
			frappe.get_doc({
				"doctype": "User", "email": email, "first_name": email.split("@")[0],
				"send_welcome_email": 0, "roles": [{"role": vai}],
			}).insert(ignore_permissions=True)
		return email

	def _het_han(self):
		bg = self._bao_gia_tho()
		frappe.db.set_value("Quotation", bg.name, "workflow_state", bao_gia.TT_HET_HAN)
		bg.reload()
		return bg

	def test_mo_lai_chi_tu_bao_gia_het_han(self):
		self.assertEqual(bao_gia.HD_MO_LAI, "Mở lại")
		self.assertTrue(frappe.db.exists("Workflow Action Master", bao_gia.HD_MO_LAI))
		mo_lai = [t for t in _hinh_dang() if t[1] == bao_gia.HD_MO_LAI]
		self.assertEqual(mo_lai, [
			(bao_gia.TT_HET_HAN, bao_gia.HD_MO_LAI, bao_gia.TT_CHO_MIYANO, "Sales Manager", None, 1),
		])
		# "Khách từ chối" và "Miyano từ chối" vẫn là trạng thái kết thúc.
		ra = {t[0] for t in _hinh_dang()}
		self.assertNotIn(bao_gia.TT_KHACH_TU_CHOI, ra)
		self.assertNotIn(bao_gia.TT_MIYANO_TU_CHOI, ra)

	def test_sales_user_khong_thay_buoc_mo_lai(self):
		bg = self._het_han()
		nv = self._nguoi_dung_desk("bgwf.nv@demo.miyano", "Sales User")
		ql = self._nguoi_dung_desk("bgwf.ql@demo.miyano", "Sales Manager")
		thay = {}
		for nguoi in (nv, ql):
			frappe.set_user(nguoi)
			try:
				thay[nguoi] = {t["action"] for t in get_transitions(bg)}
			finally:
				frappe.set_user("Administrator")
		self.assertNotIn(bao_gia.HD_MO_LAI, thay[nv])
		self.assertIn(bao_gia.HD_MO_LAI, thay[ql])
		# Và chính Sales Manager bấm được, không chỉ Administrator.
		frappe.set_user(ql)
		try:
			bg = apply_workflow(bg, bao_gia.HD_MO_LAI)
		finally:
			frappe.set_user("Administrator")
		self.assertEqual(bg.workflow_state, bao_gia.TT_CHO_MIYANO)

	def test_site_nang_cap_duoc_them_buoc_mo_lai(self):
		"""Workflow đã cài từ trước (8 bước): patch v1_42 thêm «Mở lại», patch
		v1_45 thêm ba bước theo đợt; chạy lại thì không thêm gì."""
		from miyano_portal.patches.v1_45 import bao_gia_theo_dot as v1_45

		self.addCleanup(frappe.clear_document_cache, "Workflow", bao_gia.WORKFLOW)
		theo_dot = {hd for _tu, hd, _toi, _vai, _dk in install_workflow._canh_theo_dot()}
		wf = frappe.get_doc("Workflow", bao_gia.WORKFLOW)
		wf.set("transitions", [
			t for t in wf.transitions if t.action != bao_gia.HD_MO_LAI and t.action not in theo_dot
		])
		wf.flags.ignore_permissions = True
		wf.save()
		self.assertEqual(len(_hinh_dang()), 8)

		for _ in range(2):
			bao_gia_quotation.cai_workflow()
			v1_45.cai_workflow()
			self.assertEqual(_hinh_dang(), _hinh_dang_goc())
		self.assertEqual(len(_hinh_dang()), 12)

	def test_site_moi_va_site_nang_cap_co_cung_workflow(self):
		self.addCleanup(frappe.clear_document_cache, "Workflow", bao_gia.WORKFLOW)
		nang_cap = _hinh_dang()
		frappe.delete_doc("Workflow", bao_gia.WORKFLOW, force=True, ignore_permissions=True)
		self.assertFalse(frappe.db.exists("Workflow", bao_gia.WORKFLOW))
		bao_gia_quotation.cai_workflow()
		self.assertEqual(_hinh_dang(), nang_cap)
		self.assertEqual(_hinh_dang(), _hinh_dang_goc())

	# ---- I3: nhân bản báo giá của cổng trên Desk

	def test_nhan_ban_bao_gia_cong_thanh_bao_gia_noi_bo(self):
		"""Desk «Duplicate» / «Amend» bỏ trường `no_copy` (`frappe.copy_doc(...,
		ignore_no_copy=False)`). Bản sao không có mã yêu cầu nên không được mang
		nguồn "Client Portal": khách thấy nút Đồng ý mà không ai đồng ý được."""
		phieu = frappe.get_doc({
			"doctype": "Portal De Xuat Mua", "customer": self.kh_a,
			"khoa_phong": self.khoa_huyethoc, "ly_do_yeu_cau": "Hết hàng trong kho khoa",
			"items": [{"item_code": self.item_boi_so, "so_luong_de_xuat": 10}],
		}).insert(ignore_permissions=True)
		bg = self._bao_gia_tho(
			khoa=self.khoa_huyethoc, custom_de_xuat=phieu.name,
			custom_ten_don_hang="Đợt thử nhân bản",
		)
		ban_sao = frappe.copy_doc(bg, ignore_no_copy=False)
		ban_sao.insert(ignore_permissions=True)
		ban_sao = frappe.get_doc("Quotation", ban_sao.name)
		self.assertEqual(ban_sao.custom_nguon_don, "Nội bộ")
		for truong in (
			"custom_de_xuat", "custom_khoa_phong", "custom_ten_don_hang", "custom_request_id",
		):
			self.assertFalse(ban_sao.get(truong), truong)
		# Và nó đi được hết vòng của một báo giá nội bộ.
		ban_sao = apply_workflow(ban_sao, bao_gia.HD_GUI_KHACH)
		self.assertIn(bao_gia.HD_GHI_NHAN, {t["action"] for t in get_transitions(ban_sao)})
