"""Đơn "Theo báo giá" là đơn thường với mọi chốt của luồng cũ, trừ chốt 3
(spec 2026-10-12 §4.5). Và luồng "Mua lẻ" cũ vẫn chạy nốt (§9)."""

from pathlib import Path

import frappe
from frappe.model.workflow import apply_workflow
from frappe.utils import add_days, nowdate

from miyano_portal import bang_gia_khach, bao_gia, chot_bao_gia, dat_hang, portal_bao_gia
from miyano_portal.api import portal
from miyano_portal.portal_mua_le import di_vong_bao_gia
from miyano_portal.tests.nen_bao_gia import NenBaoGia

FRONTEND = Path(frappe.get_app_path("miyano_portal")).parent / "frontend" / "src"


class TestDonTheoBaoGia(NenBaoGia):
	@classmethod
	def setUpClass(cls):
		cls.addClassCleanup(frappe.clear_document_cache, "Workflow", "Sales Order - Client Portal")
		super().setUpClass()
		from miyano_portal.patches.v1_41 import gia_theo_price_list

		gia_theo_price_list.mo_rong_workflow()

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
		self.assertIsNone(kq["chap_nhan"])
		self.assertEqual(kq["loai_don"], "Theo báo giá")

	def test_pdf_bao_gia_tren_don_khong_ap_dung(self):
		so, _ = self._don_theo_bao_gia()
		with self.assertRaises(frappe.ValidationError):
			self._voi_khach(portal.portal_bao_gia_pdf, so.name)

	def test_sua_so_luong_tren_don_bi_tu_choi(self):
		so, _ = self._don_theo_bao_gia()
		with self.assertRaises(frappe.ValidationError):
			self._voi_khach(portal.portal_order_sua_so_luong, so.name,
			                {"items": [{"item_code": self.item_boi_so, "qty": 40}]})

	def test_job_het_han_cua_luong_cu_khong_quet(self):
		so, _ = self._don_theo_bao_gia()
		frappe.db.set_value("Sales Order", so.name, {
			"workflow_state": "Chờ khách đồng ý",
			"custom_ngay_gui_khach_duyet": add_days(nowdate(), -60),
		}, update_modified=False)
		portal_bao_gia.quet_bao_gia_het_han()
		self.assertEqual(
			frappe.db.get_value("Sales Order", so.name, "workflow_state"), "Chờ khách đồng ý"
		)

	def test_thong_bao_bao_gia_san_sang_tren_don_khong_gui(self):
		so, _ = self._don_theo_bao_gia()
		dieu_kien = frappe.db.get_value("Notification", "Portal - Báo giá sẵn sàng", "condition")
		so.workflow_state = "Chờ khách đồng ý"
		self.assertFalse(frappe.safe_eval(dieu_kien, None, {"doc": so, "frappe": frappe}))

	def test_xin_sua_qua_phieu_bi_tu_choi_nhu_don_thuong(self):
		_so, phieu = self._don_theo_bao_gia()
		phieu.reload()
		with self.assertRaises(frappe.ValidationError) as ctx:
			phieu._kiem_don_dung_duoc_xin_sua()
		self.assertIn("không có dòng nào chờ báo giá", str(ctx.exception))

	def test_giao_dien_van_so_dung_chuoi_mua_le(self):
		for ten in ("components/chi-tiet/KhoiBaoGia.vue", "don-actions.js"):
			nguon = (FRONTEND / ten).read_text()
			self.assertIn("'Mua lẻ'", nguon, ten)
			self.assertNotIn("Theo báo giá", nguon, ten)

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

	def test_gui_khach_duyet_lai_thi_dong_dau_gia_moi(self):
		so, _ = self._don_theo_bao_gia()
		so.items[0].rate = so.items[0].price_list_rate = 9000
		so.save()
		so = apply_workflow(so, "Gửi khách duyệt")
		self._voi_khach(portal.portal_order_accept, so.name, "dong_y")
		so.reload()
		self.assertEqual(so.workflow_state, "Chờ Miyano xác nhận")
		self.assertEqual(so.items[0].custom_gia_khach_dong_y, 9000)
		self.assertEqual(bang_gia_khach.gia_bang_gia(self.kh_a, self.item_boi_so), 9000)

	def test_khong_gui_duyet_gia_khach_da_tu_choi(self):
		"""I5 — nhân viên sửa giá, gửi khách duyệt lại, khách KHÔNG đồng ý: đơn
		về "Chờ xác nhận" với dấu giá đã đồng ý về 0. «Gửi duyệt» từ đó là đưa
		một đơn giá khách vừa từ chối tới chỗ «Xác nhận»."""
		so, _ = self._don_theo_bao_gia()
		so.items[0].rate = so.items[0].price_list_rate = 9000
		so.save()
		so = apply_workflow(so, "Gửi khách duyệt")
		self._voi_khach(
			portal.portal_order_accept, so.name, "khong_dong_y", "Giá mới cao hơn giá đã đồng ý"
		)
		so.reload()
		self.assertEqual(so.workflow_state, "Chờ xác nhận")
		self.assertEqual(so.items[0].custom_gia_khach_dong_y, 0)
		with self.assertRaises(frappe.ValidationError) as ctx:
			apply_workflow(so, "Gửi duyệt")
		self.assertIn("Gửi khách duyệt", str(ctx.exception))
		self.assertEqual(
			frappe.db.get_value("Sales Order", so.name, "workflow_state"), "Chờ xác nhận"
		)
		# Lối ra: gửi khách duyệt lại, khách đồng ý thì đơn đi tiếp được.
		so.reload()
		so = apply_workflow(so, "Gửi khách duyệt")
		self._voi_khach(portal.portal_order_accept, so.name, "dong_y")
		so.reload()
		self.assertEqual(so.workflow_state, "Chờ Miyano xác nhận")
		self.assertEqual(so.items[0].custom_gia_khach_dong_y, 9000)
		so = apply_workflow(so, "Xác nhận")
		self.assertEqual(so.docstatus, 1)

	# ---- luồng cũ

	def test_don_mua_le_cu_van_dong_y_duoc(self):
		"""Review Focus 8."""
		kq = dat_hang.tao_sales_order(
			self.kh_a, items=[{"item_code": self.item_boi_so, "qty": 20}],
			request_id=frappe.generate_hash(length=12),
		)
		so = frappe.get_doc("Sales Order", kq["sales_order"])
		self.assertEqual(so.custom_loai_don, "Mua lẻ")
		so.items[0].rate = 7000
		so.save()
		so = apply_workflow(so, "Gửi khách duyệt")
		self._voi_khach(portal.portal_order_accept, so.name, "dong_y")
		so.reload()
		self.assertEqual(so.workflow_state, "Chờ Miyano xác nhận")
		self.assertEqual(bang_gia_khach.gia_bang_gia(self.kh_a, self.item_boi_so), 7000)
