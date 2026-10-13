"""Khách từ chối và sửa số lượng báo giá (spec 2026-10-12 §4.3)."""

import frappe
from frappe.model.workflow import apply_workflow

from miyano_portal import bang_gia_khach, bao_gia
from miyano_portal.tests.nen_bao_gia import NenBaoGia


class TestBaoGiaTuChoiSua(NenBaoGia):
	def setUp(self):
		super().setUp()
		self.ql = self._quan_ly("bgtc.ql@demo.miyano", self.kh_a)
		frappe.db.set_value("Customer", self.kh_a, "account_manager", "Administrator")

	def _cho_khach(self):
		kq = bao_gia.tao_bao_gia(
			self.kh_a,
			items=[
				{"item_code": self.item_ngoai, "qty": 10},
				{"item_code": self.item_boi_so, "qty": 20},
			],
			request_id=frappe.generate_hash(length=12), khoa_phong=self.khoa_huyethoc,
		)
		bg = frappe.get_doc("Quotation", kq["bao_gia"])
		for d in bg.items:
			if d.item_code == self.item_boi_so:
				d.rate = d.price_list_rate = 7000
		bg.save()
		return apply_workflow(bg, bao_gia.HD_GUI_KHACH)

	def _dong(self, bg, ma):
		return next(d for d in bg.items if d.item_code == ma)

	def _voi_khach(self, ham, *tham_so):
		frappe.set_user(self.ql)
		try:
			return ham(*tham_so)
		finally:
			frappe.set_user("Administrator")

	def test_tu_choi_khong_sinh_don_khong_ghi_gia(self):
		bg = self._cho_khach()
		kq = self._voi_khach(bao_gia.tu_choi, bg.name, "Giá cao hơn nhà cung cấp hiện tại")
		bg.reload()
		self.assertEqual(kq["trang_thai_moi"], bao_gia.TT_KHACH_TU_CHOI)
		self.assertEqual((bg.workflow_state, bg.docstatus), (bao_gia.TT_KHACH_TU_CHOI, 0))
		self.assertEqual(bg.custom_ly_do_tu_choi, "Giá cao hơn nhà cung cấp hiện tại")
		self.assertIsNone(bao_gia.don_cua_bao_gia(bg))
		self.assertIsNone(bang_gia_khach.gia_bang_gia(self.kh_a, self.item_boi_so))

	def test_tu_choi_khong_can_ly_do(self):
		bg = self._cho_khach()
		self._voi_khach(bao_gia.tu_choi, bg.name, None)
		self.assertEqual(
			frappe.db.get_value("Quotation", bg.name, "workflow_state"), bao_gia.TT_KHACH_TU_CHOI
		)

	def test_tu_choi_sai_trang_thai(self):
		bg = apply_workflow(self._cho_khach(), bao_gia.HD_THU_HOI)
		with self.assertRaises(frappe.ValidationError):
			self._voi_khach(bao_gia.tu_choi, bg.name, None)

	def test_sua_so_luong_ve_cho_miyano_giu_gia_xoa_han(self):
		bg = self._cho_khach()
		dong = self._dong(bg, self.item_boi_so)
		kq = self._voi_khach(bao_gia.sua_so_luong, bg.name, [{"name": dong.name, "qty": 40}])
		bg.reload()
		self.assertEqual(kq["trang_thai_moi"], bao_gia.TT_CHO_MIYANO)
		self.assertEqual(kq["ap_dung"], {self.item_boi_so: 40.0})
		self.assertEqual(self._dong(bg, self.item_boi_so).qty, 40)
		self.assertEqual(self._dong(bg, self.item_boi_so).rate, 7000)
		self.assertEqual(self._dong(bg, self.item_ngoai).qty, 10)
		self.assertFalse(bg.valid_till)
		self.assertFalse(bg.custom_ngay_gui_khach_duyet)

	def test_khong_them_dong(self):
		bg = self._cho_khach()
		with self.assertRaises(frappe.ValidationError):
			self._voi_khach(bao_gia.sua_so_luong, bg.name, [{"name": "khong-co-dong-nay", "qty": 5}])

	def test_khong_dat_ve_khong(self):
		bg = self._cho_khach()
		dong = self._dong(bg, self.item_ngoai)
		with self.assertRaises(frappe.ValidationError) as ctx:
			self._voi_khach(bao_gia.sua_so_luong, bg.name, [{"name": dong.name, "qty": 0}])
		self.assertIn("từ chối", str(ctx.exception))

	def test_sai_boi_so_bi_chan(self):
		bg = self._cho_khach()
		dong = self._dong(bg, self.item_boi_so)
		with self.assertRaises(frappe.ValidationError):
			self._voi_khach(bao_gia.sua_so_luong, bg.name, [{"name": dong.name, "qty": 25}])

	def test_khong_doi_gi_thi_bao_loi(self):
		bg = self._cho_khach()
		dong = self._dong(bg, self.item_ngoai)
		with self.assertRaises(frappe.ValidationError):
			self._voi_khach(bao_gia.sua_so_luong, bg.name, [{"name": dong.name, "qty": 10}])
		self.assertEqual(
			frappe.db.get_value("Quotation", bg.name, "workflow_state"), bao_gia.TT_CHO_KHACH
		)

	def test_nhan_vien_duoc_bao(self):
		bg = self._cho_khach()
		dong = self._dong(bg, self.item_boi_so)
		self._voi_khach(bao_gia.sua_so_luong, bg.name, [{"name": dong.name, "qty": 40}])
		log = frappe.get_all(
			"Notification Log",
			filters={"document_type": "Quotation", "document_name": bg.name,
			         "for_user": "Administrator"},
			fields=["subject", "email_content"],
		)
		self.assertEqual(len(log), 1)
		self.assertIn(self.item_boi_so, log[0].email_content)

	def test_gui_lai_sau_khi_sua_thi_dong_y_duoc(self):
		bg = self._cho_khach()
		dong = self._dong(bg, self.item_boi_so)
		self._voi_khach(bao_gia.sua_so_luong, bg.name, [{"name": dong.name, "qty": 40}])
		bg.reload()
		bg = apply_workflow(bg, bao_gia.HD_GUI_KHACH)
		kq = self._voi_khach(bao_gia.dong_y, bg.name)
		so = frappe.get_doc("Sales Order", kq["sales_order"])
		self.assertEqual(next(d.qty for d in so.items if d.item_code == self.item_boi_so), 40)

	def test_tu_choi_bao_gia_ngoai_cong_bi_tu_choi(self):
		bg = self._bao_gia_tho(nguon="Nội bộ")
		frappe.db.set_value("Quotation", bg.name, "workflow_state", bao_gia.TT_CHO_KHACH)
		with self.assertRaises(frappe.ValidationError) as ctx:
			self._voi_khach(bao_gia.tu_choi, bg.name, None)
		self.assertIn("không phải của cổng khách hàng", str(ctx.exception))

	def test_sua_so_luong_bao_gia_ngoai_cong_bi_tu_choi(self):
		bg = self._bao_gia_tho(nguon="Nội bộ")
		frappe.db.set_value("Quotation", bg.name, "workflow_state", bao_gia.TT_CHO_KHACH)
		with self.assertRaises(frappe.ValidationError) as ctx:
			self._voi_khach(
				bao_gia.sua_so_luong, bg.name, [{"name": bg.items[0].name, "qty": 20}]
			)
		self.assertIn("không phải của cổng khách hàng", str(ctx.exception))

