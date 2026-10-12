"""Chốt của luồng báo giá (spec 2026-10-09 §5.1, §5.4)."""

import frappe
from frappe.model.workflow import apply_workflow
from frappe.tests.utils import FrappeTestCase

from miyano_portal import chot_bao_gia, dat_hang
from miyano_portal.tests import test_catalog_gop as goc


class TestChotBaoGia(FrappeTestCase):
	def setUp(self):
		goc.TestPortalCatalogGop.setUp(self)
		for ma in (self.item_ngoai, self.item_boi_so):
			for ten in frappe.get_all(
				"Item Price", filters={"item_code": ma, "selling": 1}, pluck="name"
			):
				frappe.delete_doc("Item Price", ten, force=True)
		self._tao_gia(self.item_ngoai, self.price_list, 54000)

	def tearDown(self):
		frappe.set_user("Administrator")

	def _don(self, ma):
		kq = dat_hang.tao_sales_order(
			self.kh_a, items=[{"item_code": ma, "qty": 10}],
			request_id=frappe.generate_hash(length=12),
		)
		return frappe.get_doc("Sales Order", kq["sales_order"])

	def _don_da_dien_gia(self):
		so = self._don(self.item_boi_so)
		so.items[0].rate = 7000
		so.save()
		return so

	def test_don_bao_gia_khong_gui_duyet_thang_duoc(self):
		so = self._don_da_dien_gia()
		with self.assertRaises(frappe.ValidationError) as ctx:
			apply_workflow(so, "Gửi duyệt")
		self.assertIn("Gửi khách duyệt", str(ctx.exception))

	def test_don_theo_bang_gia_gui_duyet_thang_duoc(self):
		so = apply_workflow(self._don(self.item_ngoai), "Gửi duyệt")
		self.assertEqual(so.workflow_state, "Chờ Miyano xác nhận")

	def test_con_dong_gia_0_thi_chua_gui_khach_duoc(self):
		so = self._don(self.item_boi_so)
		with self.assertRaises(frappe.ValidationError) as ctx:
			apply_workflow(so, "Gửi khách duyệt")
		self.assertIn(self.item_boi_so, str(ctx.exception))

	def test_du_gia_thi_gui_khach_duoc(self):
		so = apply_workflow(self._don_da_dien_gia(), "Gửi khách duyệt")
		self.assertEqual(so.workflow_state, "Chờ khách đồng ý")

	def test_gia_khac_gia_khach_dong_y_thi_khong_xac_nhan_duoc(self):
		so = apply_workflow(self._don_da_dien_gia(), "Gửi khách duyệt")
		so = apply_workflow(so, "Khách đồng ý")
		frappe.db.set_value("Sales Order Item", so.items[0].name,
		                    "custom_gia_khach_dong_y", 7000)
		so.reload()
		so.items[0].rate = 9000
		with self.assertRaises(frappe.ValidationError) as ctx:
			so.submit()
		self.assertIn("gửi khách duyệt lại", str(ctx.exception))

	def test_gia_khop_gia_khach_dong_y_thi_xac_nhan_duoc(self):
		so = apply_workflow(self._don_da_dien_gia(), "Gửi khách duyệt")
		so = apply_workflow(so, "Khách đồng ý")
		frappe.db.set_value("Sales Order Item", so.items[0].name,
		                    "custom_gia_khach_dong_y", 7000)
		so.reload()
		so = apply_workflow(so, "Xác nhận")
		self.assertEqual(so.docstatus, 1)

	def test_quay_ve_cho_xac_nhan_thi_xoa_gia_da_dong_y(self):
		so = apply_workflow(self._don_da_dien_gia(), "Gửi khách duyệt")
		frappe.db.set_value("Sales Order Item", so.items[0].name,
		                    "custom_gia_khach_dong_y", 7000)
		so.reload()
		so = apply_workflow(so, "Khách không đồng ý")
		self.assertEqual(so.workflow_state, "Chờ xác nhận")
		self.assertEqual(float(so.items[0].custom_gia_khach_dong_y or 0), 0.0)

	def test_don_desk_khong_bi_chot(self):
		"""Đơn không phải từ cổng: cả ba chốt không áp."""
		so = self._don(self.item_boi_so)
		so.custom_nguon_don = "Nội bộ"
		so.save()
		so = apply_workflow(so, "Gửi duyệt")
		self.assertEqual(so.workflow_state, "Chờ Miyano xác nhận")
		so2 = self._don(self.item_boi_so)
		so2.custom_nguon_don = "Nội bộ"
		so2.save()
		so2 = apply_workflow(so2, "Gửi khách duyệt")
		self.assertEqual(so2.workflow_state, "Chờ khách đồng ý")
		# Chốt 3 — dựng ĐÚNG ca nó sinh ra để chặn (dòng "Báo giá", giá trên
		# đơn lệch giá khách đã đồng ý) ngay trong bộ nhớ. Vế đối chứng đi
		# trước: cũng dòng ấy trên đơn TỪ CỔNG thì bị chặn — không có nó, lời
		# gọi cho đơn Desk xanh cả khi dữ liệu chưa hề chạm tới điều kiện.
		dong = so2.items[0]
		self.assertEqual(dong.custom_nguon_gia, "Báo giá")
		dong.custom_gia_khach_dong_y = 7000
		dong.rate = 9000
		so2.custom_nguon_don = "Client Portal"
		with self.assertRaises(frappe.ValidationError):
			chot_bao_gia.kiem_gia_khop_gia_da_dong_y(so2)
		so2.custom_nguon_don = "Nội bộ"
		self.assertIsNone(chot_bao_gia.kiem_gia_khop_gia_da_dong_y(so2))

	def test_don_cu_theo_hdnt_du_gia_khong_bi_chot(self):
		"""Đơn cổng tạo trước thay đổi: loại "Theo HĐNT", dòng chưa đóng dấu nguồn giá."""
		so = self._don(self.item_ngoai)
		frappe.db.set_value("Sales Order", so.name, "custom_loai_don", "Theo HĐNT")
		frappe.db.set_value("Sales Order Item", so.items[0].name, "custom_nguon_gia", None)
		so.reload()
		so = apply_workflow(so, "Gửi duyệt")
		self.assertEqual(so.workflow_state, "Chờ Miyano xác nhận")
		so = apply_workflow(so, "Xác nhận")
		self.assertEqual(so.docstatus, 1)


for _ten, _ham in vars(goc.TestPortalCatalogGop).items():
	if _ten.startswith("_") and not _ten.startswith("__") and callable(_ham):
		if _ten not in vars(TestChotBaoGia):
			setattr(TestChotBaoGia, _ten, _ham)
