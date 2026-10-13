"""Khách đồng ý báo giá → sinh Sales Order (spec 2026-10-12 §4.4)."""

from unittest.mock import patch

import frappe
from frappe.model.workflow import apply_workflow
from frappe.utils import add_days, getdate, nowdate

from miyano_portal import bang_gia_khach, bao_gia
from miyano_portal.portal_dat_hang import ngay_giao_mac_dinh
from miyano_portal.tests.nen_bao_gia import NenBaoGia


class TestBaoGiaDongY(NenBaoGia):
	def setUp(self):
		super().setUp()
		self.ql = self._quan_ly("bgdy.ql@demo.miyano", self.kh_a)

	def _phieu(self, ngay_can=None, ma_de_xuat=None):
		doc = frappe.get_doc({
			"doctype": "Portal De Xuat Mua", "customer": self.kh_a,
			"khoa_phong": self.khoa_huyethoc, "ly_do_yeu_cau": "Hết hàng trong kho khoa",
			"ten_don_hang": "Đợt thử báo giá", "ghi_chu": "Giao giờ hành chính",
			"ngay_can": ngay_can or add_days(nowdate(), 10),
			"trang_thai": "Đã duyệt", "ma_de_xuat": ma_de_xuat,
			"items": [{"item_code": self.item_boi_so, "so_luong_de_xuat": 20, "so_luong_duyet": 20}],
		})
		doc.insert(ignore_permissions=True)
		return doc

	def _cho_khach(self, gia=7000, gia_dong_co_gia=None, ngay_can=None, ma_de_xuat=None):
		"""Một báo giá của cổng đã được Miyano điền giá và gửi khách."""
		phieu = self._phieu(ngay_can, ma_de_xuat)
		kq = bao_gia.tao_bao_gia(
			self.kh_a,
			items=[
				{"item_code": self.item_ngoai, "qty": 10},
				{"item_code": self.item_boi_so, "qty": 20},
			],
			request_id=frappe.generate_hash(length=12), khoa_phong=self.khoa_huyethoc,
		)
		bg = frappe.get_doc("Quotation", kq["bao_gia"])
		bg.custom_de_xuat = phieu.name
		bg.custom_ten_don_hang = phieu.ten_don_hang
		for d in bg.items:
			if d.item_code == self.item_boi_so:
				d.rate = d.price_list_rate = gia
			elif gia_dong_co_gia:
				d.rate = gia_dong_co_gia
		bg.save()
		frappe.db.set_value("Portal De Xuat Mua", phieu.name, "bao_gia", bg.name)
		return apply_workflow(bg, bao_gia.HD_GUI_KHACH), phieu

	def _dong_y(self, bg):
		frappe.set_user(self.ql)
		try:
			return bao_gia.dong_y(bg.name)
		finally:
			frappe.set_user("Administrator")

	def test_bao_gia_duoc_submit(self):
		bg, _ = self._cho_khach()
		kq = self._dong_y(bg)
		bg.reload()
		self.assertEqual((bg.workflow_state, bg.docstatus), (bao_gia.TT_DA_DONG_Y, 1))
		self.assertEqual(kq["trang_thai_moi"], bao_gia.TT_DA_DONG_Y)
		self.assertFalse(kq["da_ton_tai"])
		self.assertFalse(frappe.flags.bao_gia_dong_y_qua_cong)

	def test_sinh_dung_mot_don_theo_bao_gia(self):
		bg, phieu = self._cho_khach()
		kq = self._dong_y(bg)
		so = frappe.get_doc("Sales Order", kq["sales_order"])
		self.assertEqual(so.customer, self.kh_a)
		self.assertEqual(so.custom_loai_don, "Theo báo giá")
		self.assertEqual((so.workflow_state, so.docstatus), ("Chờ Miyano xác nhận", 0))
		self.assertEqual(so.custom_nguon_don, "Client Portal")
		self.assertEqual(so.custom_khoa_phong, self.khoa_huyethoc)
		self.assertEqual(so.custom_de_xuat, phieu.name)
		self.assertEqual(so.custom_ten_don_hang, "Đợt thử báo giá")
		self.assertEqual(so.custom_yeu_cau_khach, "Giao giờ hành chính")
		self.assertEqual(so.custom_request_id, bg.custom_request_id + ":don")
		self.assertEqual(len(so.items), 2)

	def test_dong_don_mang_gia_dau_nguon_va_gia_da_dong_y(self):
		bg, _ = self._cho_khach()
		so = frappe.get_doc("Sales Order", self._dong_y(bg)["sales_order"])
		theo_ma = {d.item_code: d for d in so.items}
		self.assertEqual(theo_ma[self.item_boi_so].rate, 7000)
		self.assertEqual(theo_ma[self.item_ngoai].rate, 54000)
		for d in so.items:
			self.assertEqual(d.custom_nguon_gia, "Báo giá")
			self.assertEqual(d.custom_gia_khach_dong_y, d.rate)
			self.assertTrue(d.warehouse)
			self.assertEqual(d.prevdoc_docname, bg.name)

	def test_gia_don_dung_gia_khach_dong_y_khi_khac_bang_gia(self):
		"""Review Focus 2 — Miyano gõ 60000 cho mặt hàng có giá bảng 54000."""
		bg, _ = self._cho_khach(gia_dong_co_gia=60000)
		so = frappe.get_doc("Sales Order", self._dong_y(bg)["sales_order"])
		dong = next(d for d in so.items if d.item_code == self.item_ngoai)
		self.assertEqual(dong.rate, 60000)
		self.assertEqual(dong.price_list_rate, 60000)
		self.assertEqual(dong.discount_amount or 0, 0)
		self.assertEqual(dong.custom_gia_khach_dong_y, 60000)

	def test_don_khong_mang_truong_rieng_cua_bao_gia(self):
		bg, _ = self._cho_khach()
		so = frappe.get_doc("Sales Order", self._dong_y(bg)["sales_order"])
		self.assertNotEqual(so.custom_request_id, bg.custom_request_id)
		self.assertFalse(so.get("custom_ngay_gui_khach_duyet"))
		self.assertFalse(so.get("custom_ly_do_tu_choi"))
		self.assertEqual(len(so.get("custom_dat_ngoai") or []), 0)

	def test_phieu_co_sales_order(self):
		bg, phieu = self._cho_khach()
		kq = self._dong_y(bg)
		self.assertEqual(
			frappe.db.get_value("Portal De Xuat Mua", phieu.name, ["sales_order", "bao_gia"]),
			(kq["sales_order"], bg.name),
		)

	def test_gia_duoc_ghi_vao_price_list(self):
		bg, _ = self._cho_khach(gia=7000)
		self._dong_y(bg)
		self.assertEqual(bang_gia_khach.gia_bang_gia(self.kh_a, self.item_boi_so), 7000)

	def test_goi_lai_khong_sinh_don_thu_hai(self):
		"""Review Focus 1."""
		bg, _ = self._cho_khach()
		kq1 = self._dong_y(bg)
		kq2 = self._dong_y(bg)
		self.assertEqual(kq1["sales_order"], kq2["sales_order"])
		self.assertTrue(kq2["da_ton_tai"])
		self.assertEqual(
			frappe.db.count("Sales Order", {"custom_request_id": bg.custom_request_id + ":don"}), 1
		)

	def test_qua_han_khong_dong_y_duoc(self):
		"""Review Focus 4 — job hết hạn chưa chạy."""
		bg, _ = self._cho_khach()
		frappe.db.set_value("Quotation", bg.name, {
			"valid_till": add_days(nowdate(), -1), "transaction_date": add_days(nowdate(), -9),
		})
		with self.assertRaises(frappe.ValidationError) as ctx:
			self._dong_y(bg)
		self.assertIn("hết hiệu lực", str(ctx.exception))
		self.assertEqual(frappe.db.get_value("Quotation", bg.name, "docstatus"), 0)

	def test_khong_o_cho_khach_thi_tu_choi(self):
		bg, _ = self._cho_khach()
		bg = apply_workflow(bg, bao_gia.HD_THU_HOI)
		with self.assertRaises(frappe.ValidationError):
			self._dong_y(bg)

	def test_loi_ghi_gia_khong_lam_hong_viec_dong_y(self):
		bg, _ = self._cho_khach()
		with patch.object(bang_gia_khach, "ghi_gia_da_dong_y", side_effect=RuntimeError("hỏng")):
			kq = self._dong_y(bg)
		self.assertTrue(frappe.db.exists("Sales Order", kq["sales_order"]))
		self.assertEqual(
			frappe.db.get_value("Quotation", bg.name, "workflow_state"), bao_gia.TT_DA_DONG_Y
		)
		self.assertTrue(frappe.db.exists(
			"Error Log", {"reference_doctype": "Sales Order", "reference_name": kq["sales_order"]}
		))

	def test_loi_sinh_don_thi_bao_gia_khong_o_trang_thai_da_dong_y(self):
		bg, phieu = self._cho_khach()
		with patch.object(bao_gia, "_sinh_don", side_effect=frappe.ValidationError("hỏng")):
			with self.assertRaises(frappe.ValidationError):
				self._dong_y(bg)
		self.assertFalse(frappe.flags.bao_gia_dong_y_qua_cong)
		self.assertEqual(
			frappe.db.get_value("Quotation", bg.name, ["workflow_state", "docstatus"]),
			(bao_gia.TT_CHO_KHACH, 0),
		)
		self.assertFalse(frappe.db.get_value("Portal De Xuat Mua", phieu.name, "sales_order"))

	def test_ngay_giao_lay_tu_phieu(self):
		ngay = add_days(nowdate(), 10)
		bg, _ = self._cho_khach(ngay_can=ngay)
		so = frappe.get_doc("Sales Order", self._dong_y(bg)["sales_order"])
		self.assertEqual(getdate(so.delivery_date), getdate(ngay))
		self.assertEqual(getdate(so.items[0].delivery_date), getdate(ngay))

	def test_ngay_can_da_qua_dung_ngay_mac_dinh(self):
		"""Review Focus 7."""
		bg, phieu = self._cho_khach()
		frappe.db.set_value("Portal De Xuat Mua", phieu.name, "ngay_can", add_days(nowdate(), -3))
		so = frappe.get_doc("Sales Order", self._dong_y(bg)["sales_order"])
		self.assertEqual(getdate(so.delivery_date), getdate(ngay_giao_mac_dinh()))

	def test_phien_tra_ve_nguoi_bam(self):
		bg, _ = self._cho_khach()
		frappe.set_user(self.ql)
		bao_gia.dong_y(bg.name)
		self.assertEqual(frappe.session.user, self.ql)

	def test_dong_y_khac_ngay_lap_bao_gia(self):
		"""Vòng sửa 1 — báo giá lập hôm kia: lịch thanh toán của nó (hạn = ngày
		lập) không được theo sang đơn, nếu không đơn lập hôm nay bị chặn vì hạn
		thanh toán đứng trước ngày chứng từ."""
		bg, _ = self._cho_khach()
		hom_kia = add_days(nowdate(), -2)
		frappe.db.set_value(
			"Quotation", bg.name, "transaction_date", hom_kia, update_modified=False
		)
		lich = frappe.get_all(
			"Payment Schedule", filters={"parent": bg.name, "parenttype": "Quotation"},
			pluck="name",
		)
		self.assertTrue(lich, "fixture: báo giá phải có lịch thanh toán")
		for ten in lich:
			frappe.db.set_value(
				"Payment Schedule", ten, "due_date", hom_kia, update_modified=False
			)
		so = frappe.get_doc("Sales Order", self._dong_y(bg)["sales_order"])
		self.assertTrue(so.payment_schedule)
		for d in so.payment_schedule:
			self.assertGreaterEqual(getdate(d.due_date), getdate(so.transaction_date))

	def test_bao_gia_khong_cua_cong_bi_tu_choi(self):
		"""Vòng sửa 1 — báo giá nhân viên tự lập trên Desk không đi đường này."""
		bg = self._bao_gia_tho(nguon="Nội bộ")
		with self.assertRaises(frappe.ValidationError) as ctx:
			self._dong_y(bg)
		self.assertIn("không phải của cổng khách hàng", str(ctx.exception))
		self.assertEqual(frappe.db.get_value("Quotation", bg.name, "docstatus"), 0)

	def test_bao_gia_cong_thieu_ma_yeu_cau_bi_tu_choi(self):
		bg = self._bao_gia_tho()
		frappe.db.set_value("Quotation", bg.name, "custom_request_id", None)
		with self.assertRaises(frappe.ValidationError) as ctx:
			self._dong_y(bg)
		self.assertIn("không phải của cổng khách hàng", str(ctx.exception))

	def test_don_mang_ma_de_xuat_cua_phieu(self):
		"""Vòng sửa 1 — mã đơn là mã khách đang cầm trên phiếu."""
		ma = "BGDY-" + frappe.generate_hash(length=8).upper()
		bg, _ = self._cho_khach(ma_de_xuat=ma)
		kq = self._dong_y(bg)
		self.assertEqual(kq["sales_order"], ma)
		self.assertEqual(frappe.db.get_value("Sales Order", ma, "custom_ma_tra_cuu"), ma)

	def test_lui_savepoint_ghi_gia_hong_thi_khong_bao_thanh_cong(self):
		"""Vòng sửa 1 — lùi savepoint hỏng nghĩa là máy chủ đã lùi CẢ giao dịch
		(deadlock...): đơn vừa sinh không còn, không được trả về như đã xong."""
		bg, _ = self._cho_khach()
		lui_that = frappe.db.rollback

		def lui(*args, save_point=None, **kw):
			if save_point == "bao_gia_ghi_gia":
				raise frappe.db.InternalError("SAVEPOINT bao_gia_ghi_gia does not exist")
			return lui_that(*args, save_point=save_point, **kw)

		with patch.object(bang_gia_khach, "ghi_gia_da_dong_y", side_effect=RuntimeError("hỏng")):
			with patch.object(frappe.db, "rollback", side_effect=lui):
				with self.assertRaises(frappe.db.InternalError):
					self._dong_y(bg)
