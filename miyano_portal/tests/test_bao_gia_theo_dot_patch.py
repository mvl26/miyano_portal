"""Patch v1_45 — báo giá theo đợt (spec 2026-10-15 §3)."""

import frappe

from miyano_portal import bao_gia
from miyano_portal.patches.v1_45 import bao_gia_theo_dot as patch
from miyano_portal.setup import install_workflow
from miyano_portal.tests.nen_bao_gia import NenBaoGiaTheoDot


def _dem_workflow():
	frappe.clear_document_cache("Workflow", bao_gia.WORKFLOW)
	wf = frappe.get_doc("Workflow", bao_gia.WORKFLOW)
	return (len(wf.states), len(wf.transitions))


class TestPatchBaoGiaTheoDot(NenBaoGiaTheoDot):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		# Chạy lại patch NGAY ĐÂY, trước mọi `setUp`, KHÔNG trong thân test:
		# `reload_doc(force=True)`/`create_custom_fields` đi qua
		# `frappe.db.updatedb()` — hàm này COMMIT. Gọi sau `setUp` là commit
		# luôn dữ liệu `_TEST DX` của nó vào DB dev (Item Price, Price List,
		# Blanket Order…), và các module chạy sau (test_bang_gia_khach,
		# test_catalog_gop) đỏ vì dữ liệu sót đó.
		cls._wf_truoc = _dem_workflow()
		patch.execute()
		cls._wf_sau = _dem_workflow()

	def test_truong_moi_tren_quotation(self):
		meta = frappe.get_meta("Quotation")
		for f in ("custom_phieu_goc", "custom_so_dot", "custom_da_tra_ve",
		          "custom_ly_do_huy_con_lai", "custom_nguoi_huy_con_lai"):
			self.assertTrue(meta.has_field(f), f)
			self.assertTrue(meta.get_field(f).no_copy, f)
		# Trên phiếu gốc `custom_so_dot` là bộ đếm nội bộ, không phải «Đợt».
		self.assertEqual(meta.get_field("custom_so_dot").depends_on, "eval:doc.custom_phieu_goc")

	def test_bang_don_hang_tren_phieu(self):
		self.assertEqual(
			frappe.get_meta("Portal De Xuat Mua").get_field("don_hang").options,
			"Portal De Xuat Mua Don Hang",
		)

	def test_workflow_co_trang_thai_va_buoc_moi(self):
		wf = frappe.get_doc("Workflow", bao_gia.WORKFLOW)
		self.assertTrue({bao_gia.TT_DA_BAO_HET, bao_gia.TT_HUY_CON_LAI} <= {s.state for s in wf.states})
		canh = {(t.state, t.action, t.next_state, t.allowed) for t in wf.transitions}
		for tu, hd, toi, vai, _dk in install_workflow._canh_theo_dot():
			self.assertIn((tu, hd, toi, vai), canh)

	def test_chay_lai_khong_nhan_doi(self):
		# Lần chạy lại nằm ở `setUpClass` — xem lý do ở đó.
		self.assertEqual(self._wf_sau, self._wf_truoc)
		self.assertEqual(self._wf_sau, (8, 12))

	def test_site_cu_duoc_bo_sung(self):
		wf = frappe.get_doc("Workflow", bao_gia.WORKFLOW)
		moi = {bao_gia.TT_DA_BAO_HET, bao_gia.TT_HUY_CON_LAI}
		wf.set("states", [s for s in wf.states if s.state not in moi])
		wf.set("transitions", [
			t for t in wf.transitions if t.state not in moi and t.next_state not in moi
		])
		wf.flags.ignore_permissions = True
		wf.save()
		self.assertTrue(install_workflow.mo_rong_workflow_theo_dot())
		wf.reload()
		self.assertEqual((len(wf.states), len(wf.transitions)), (8, 12))

	def test_tieu_de_thong_bao_co_so_dot(self):
		from miyano_portal.setup.install_notifications import TEN_TB_BAO_GIA

		tieu_de = frappe.db.get_value("Notification", TEN_TB_BAO_GIA, "subject")
		bg = frappe._dict(name="SAL-QTN-X", custom_so_dot=2)
		self.assertEqual(frappe.render_template(tieu_de, {"doc": bg}), "Báo giá SAL-QTN-X (đợt 2) đã sẵn sàng")
		bg.custom_so_dot = 0
		self.assertEqual(frappe.render_template(tieu_de, {"doc": bg}), "Báo giá SAL-QTN-X đã sẵn sàng")

	def test_chep_sales_order_vao_don_hang_mot_lan(self):
		phieu = frappe.get_doc({
			"doctype": "Portal De Xuat Mua", "customer": self.kh_a,
			"khoa_phong": self.khoa_huyethoc, "ly_do_yeu_cau": "Hết hàng trong kho khoa",
			"trang_thai": "Đã duyệt",
			"items": [{"item_code": self.item_ngoai, "so_luong_de_xuat": 1, "so_luong_duyet": 1}],
		}).insert(ignore_permissions=True)
		frappe.db.set_value("Portal De Xuat Mua", phieu.name, "sales_order", "SO-DOT-PATCH-1")
		patch.chep_don_hang()
		patch.chep_don_hang()
		dong = frappe.get_all(
			"Portal De Xuat Mua Don Hang", filters={"parent": phieu.name},
			fields=["sales_order", "so_dot", "parenttype", "parentfield"],
		)
		self.assertEqual(len(dong), 1)
		self.assertEqual(dong[0].sales_order, "SO-DOT-PATCH-1")
		self.assertEqual((dong[0].parenttype, dong[0].parentfield), ("Portal De Xuat Mua", "don_hang"))
