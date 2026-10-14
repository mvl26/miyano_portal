"""Đơn "Theo báo giá" là đơn thường, chỉ thêm chốt 3 (spec 2026-10-12 §4.5):
xác nhận phải đúng giá khách đã đồng ý trên Quotation."""

import frappe
from frappe.model.workflow import apply_workflow
from frappe.utils import add_days, nowdate

from miyano_portal import bao_gia, chot_bao_gia
from miyano_portal.api import portal
from miyano_portal.portal_mua_le import di_vong_bao_gia
from miyano_portal.tests.nen_bao_gia import NenBaoGia


class TestDonTheoBaoGia(NenBaoGia):
	def setUp(self):
		super().setUp()
		self.ql = self._quan_ly("dtbg.ql@demo.miyano", self.kh_a)

	def _voi_khach(self, ham, *a, **kw):
		frappe.set_user(self.ql)
		try:
			return ham(*a, **kw)
		finally:
			frappe.set_user("Administrator")

	def _don_theo_bao_gia(self):
		phieu = frappe.get_doc({
			"doctype": "Portal De Xuat Mua", "customer": self.kh_a,
			"khoa_phong": self.khoa_huyethoc, "ly_do_yeu_cau": "Hết hàng trong kho khoa",
			"trang_thai": "Đã duyệt", "ngay_can": add_days(nowdate(), 10),
			"items": [{"item_code": self.item_boi_so, "so_luong_de_xuat": 20, "so_luong_duyet": 20}],
		}).insert(ignore_permissions=True)
		kq = bao_gia.tao_bao_gia(
			self.kh_a, items=[{"item_code": self.item_boi_so, "qty": 20}],
			request_id=frappe.generate_hash(length=12), khoa_phong=self.khoa_huyethoc,
		)
		bg = frappe.get_doc("Quotation", kq["bao_gia"])
		bg.custom_de_xuat = phieu.name
		bg.items[0].rate = bg.items[0].price_list_rate = 7000
		bg.save()
		frappe.db.set_value("Portal De Xuat Mua", phieu.name, "bao_gia", bg.name)
		bg = apply_workflow(bg, bao_gia.HD_GUI_KHACH)
		ten = self._voi_khach(bao_gia.dong_y, bg.name)["sales_order"]
		return frappe.get_doc("Sales Order", ten), phieu

	# ---- bảng §4.5

	def test_khong_di_vong_bao_gia(self):
		so, _ = self._don_theo_bao_gia()
		self.assertFalse(di_vong_bao_gia(so))
		self.assertTrue(chot_bao_gia.co_gia_khach_dong_y(so))

	def test_track_khong_co_khoi_chap_nhan(self):
		so, _ = self._don_theo_bao_gia()
		kq = self._voi_khach(portal.portal_order_track, so.name)
		self.assertNotIn("chap_nhan", kq)
		self.assertNotIn("duoc_sua_da_duyet", kq)
		self.assertEqual(kq["loai_don"], "Theo báo giá")

	def test_pdf_bao_gia_tren_don_khong_ap_dung(self):
		so, _ = self._don_theo_bao_gia()
		with self.assertRaises(frappe.ValidationError):
			self._voi_khach(portal.portal_bao_gia_pdf, so.name)

	# ---- chốt 3 mở rộng

	def test_xac_nhan_duoc_khi_gia_khop(self):
		so, _ = self._don_theo_bao_gia()
		so = apply_workflow(so, "Xác nhận")
		self.assertEqual((so.workflow_state, so.docstatus), ("Đã xác nhận", 1))

	def test_khong_xac_nhan_khi_gia_khac_gia_khach_dong_y(self):
		so, _ = self._don_theo_bao_gia()
		so.items[0].rate = 9000
		so.save()
		with self.assertRaises(frappe.ValidationError) as ctx:
			apply_workflow(so, "Xác nhận")
		self.assertIn("khác giá khách đã đồng ý", str(ctx.exception))
