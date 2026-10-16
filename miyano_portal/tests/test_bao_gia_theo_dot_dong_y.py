"""Khách đồng ý một đợt (spec 2026-10-15 §4.2)."""

import frappe
from frappe.utils import add_days, nowdate

from miyano_portal import bao_gia, bao_gia_theo_dot as dot
from miyano_portal.tests.nen_bao_gia import NenBaoGiaTheoDot


class TestDongYDot(NenBaoGiaTheoDot):
	def setUp(self):
		super().setUp()
		self.ql = self._quan_ly("dotdy.ql@demo.miyano", self.kh_a)
		self.phieu = frappe.get_doc({
			"doctype": "Portal De Xuat Mua", "customer": self.kh_a,
			"khoa_phong": self.khoa_huyethoc, "ly_do_yeu_cau": "Hết hàng trong kho khoa",
			"ngay_can": add_days(nowdate(), 10), "trang_thai": "Đã duyệt",
			"items": [{"item_code": self.item_ngoai, "so_luong_de_xuat": 10, "so_luong_duyet": 10}],
		}).insert(ignore_permissions=True)
		self.goc = self._goc_ba_dong(custom_de_xuat=self.phieu.name)
		frappe.db.set_value("Portal De Xuat Mua", self.phieu.name, "bao_gia", self.goc.name)

	def _dong_y(self, ten):
		frappe.set_user(self.ql)
		try:
			return bao_gia.dong_y(ten)
		finally:
			frappe.set_user("Administrator")

	def _tach(self, ma):
		self.goc.reload()
		return dot.tach_dot(self.goc.name, [d.name for d in self.goc.items if d.item_code == ma])["dot"]

	def test_dong_y_dot_sinh_don_dung_ma_yeu_cau(self):
		d1 = self._tach(self.item_ngoai)
		kq = self._dong_y(d1)
		so = frappe.get_doc("Sales Order", kq["sales_order"])
		self.assertEqual(so.custom_request_id, self.goc.custom_request_id + ":dot1:don")
		self.assertEqual([d.item_code for d in so.items], [self.item_ngoai])
		self.assertEqual(bao_gia.bao_gia_cua_don(so), d1)

	def test_hai_dot_hai_don_bang_don_hang(self):
		d1 = self._tach(self.item_ngoai)
		so1 = self._dong_y(d1)["sales_order"]
		d2 = self._tach(self.item_boi_so)
		so2 = self._dong_y(d2)["sales_order"]
		self.assertNotEqual(so1, so2)
		# `sales_order` của phiếu giữ ĐƠN ĐẦU TIÊN.
		self.assertEqual(frappe.db.get_value("Portal De Xuat Mua", self.phieu.name, "sales_order"), so1)
		dong = frappe.get_all(
			"Portal De Xuat Mua Don Hang", filters={"parent": self.phieu.name},
			fields=["sales_order", "bao_gia", "so_dot"], order_by="idx asc",
		)
		self.assertEqual(
			[(r.sales_order, r.bao_gia, r.so_dot) for r in dong],
			[(so1, d1, 1), (so2, d2, 2)],
		)

	def test_bao_gia_khong_tach_dot_van_nhu_cu(self):
		goc = self._goc_ba_dong(custom_de_xuat=self.phieu.name)
		from frappe.model.workflow import apply_workflow

		apply_workflow(goc, bao_gia.HD_GUI_KHACH)
		so = self._dong_y(goc.name)["sales_order"]
		self.assertEqual(frappe.db.get_value("Portal De Xuat Mua", self.phieu.name, "sales_order"), so)
		self.assertEqual(
			frappe.get_all("Portal De Xuat Mua Don Hang", filters={"parent": self.phieu.name},
			               pluck="so_dot"),
			[0],
		)

	def test_dot_hai_doi_modified_phieu_chan_luu_ban_cu(self):
		"""Bản phiếu mở trên Desk TRƯỚC khi đợt 2 sinh đơn mà lưu lại thì phải vấp
		TimestampMismatch, không lặng lẽ xoá dòng `don_hang` vừa chèn."""
		self._dong_y(self._tach(self.item_ngoai))
		cu = frappe.get_doc("Portal De Xuat Mua", self.phieu.name)
		self._dong_y(self._tach(self.item_boi_so))
		self.assertNotEqual(
			str(frappe.db.get_value("Portal De Xuat Mua", self.phieu.name, "modified")),
			str(cu.modified),
		)
		with self.assertRaises(frappe.TimestampMismatchError):
			cu.save()
		self.assertEqual(
			len(frappe.get_all("Portal De Xuat Mua Don Hang", filters={"parent": self.phieu.name})), 2
		)
