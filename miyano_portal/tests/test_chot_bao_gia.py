"""Chốt giá trên Sales Order từ cổng (spec 2026-10-09 §5.1, §5.4; patch v1_44)."""

import frappe
from frappe.model.workflow import apply_workflow
from frappe.tests.utils import FrappeTestCase

from miyano_portal import chot_bao_gia, dat_hang
from miyano_portal.chot_bao_gia import TT_CHO_MIYANO, TT_CHO_XAC_NHAN
from miyano_portal.portal_mua_le import ITEM_GIU_CHO
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

	def _sap_gui_duyet(self, so, truoc=TT_CHO_XAC_NHAN):
		"""Đơn trong bộ nhớ đang đổi `truoc` → "Chờ Miyano xác nhận", như lúc
		`apply_workflow` gọi `save()`; gọi thẳng chốt 1, không qua hook khác."""
		so._doc_before_save = frappe.copy_doc(so)
		so._doc_before_save.workflow_state = truoc
		so.workflow_state = TT_CHO_MIYANO
		return so

	# ---- Chốt 1: vào "Chờ Miyano xác nhận" phải đủ đơn giá ------------------

	def test_con_dong_gia_0_thi_chua_gui_duyet_duoc(self):
		so = self._don(self.item_boi_so)
		self.assertEqual(so.custom_loai_don, "Mua lẻ")
		with self.assertRaises(frappe.ValidationError) as ctx:
			apply_workflow(so, "Gửi duyệt")
		self.assertIn("chưa có đơn giá", str(ctx.exception))
		self.assertIn(self.item_boi_so, str(ctx.exception))
		self.assertEqual(
			frappe.db.get_value("Sales Order", so.name, "workflow_state"), TT_CHO_XAC_NHAN
		)

	def test_nhan_vien_dien_gia_thi_gui_duyet_va_xac_nhan_duoc(self):
		so = apply_workflow(self._don_da_dien_gia(), "Gửi duyệt")
		self.assertEqual(so.workflow_state, TT_CHO_MIYANO)
		so = apply_workflow(so, "Xác nhận")
		self.assertEqual(so.docstatus, 1)

	def test_don_theo_bang_gia_gui_duyet_thang_duoc(self):
		so = apply_workflow(self._don(self.item_ngoai), "Gửi duyệt")
		self.assertEqual(so.workflow_state, TT_CHO_MIYANO)

	def test_dong_giu_cho_khong_bi_tinh_la_thieu_gia(self):
		so = self._sap_gui_duyet(self._don(self.item_ngoai))
		so.append("items", {"item_code": ITEM_GIU_CHO, "qty": 1, "rate": 0})
		self.assertIsNone(chot_bao_gia.kiem_chuyen_trang_thai(so))
		# Đối chứng: cùng đơn, dòng giá 0 là mặt hàng thật thì bị chặn.
		so.items[-1].item_code = self.item_boi_so
		with self.assertRaises(frappe.ValidationError):
			chot_bao_gia.kiem_chuyen_trang_thai(so)

	def test_chi_so_khi_trang_thai_doi(self):
		"""Lưu lại đơn đã ở "Chờ Miyano xác nhận" không bị chốt 1 hỏi lại."""
		so = self._don(self.item_boi_so)
		self._sap_gui_duyet(so)
		with self.assertRaises(frappe.ValidationError):
			chot_bao_gia.kiem_chuyen_trang_thai(so)
		self._sap_gui_duyet(so, truoc=TT_CHO_MIYANO)
		self.assertIsNone(chot_bao_gia.kiem_chuyen_trang_thai(so))

	# ---- Chốt 3: xác nhận phải đúng giá khách đã đồng ý ---------------------

	def _don_cho_xac_nhan_co_gia_da_dong_y(self, gia):
		so = apply_workflow(self._don_da_dien_gia(), "Gửi duyệt")
		frappe.db.set_value("Sales Order Item", so.items[0].name,
		                    "custom_gia_khach_dong_y", gia)
		so.reload()
		return so

	def test_gia_khac_gia_khach_dong_y_thi_khong_xac_nhan_duoc(self):
		so = self._don_cho_xac_nhan_co_gia_da_dong_y(7000)
		so.items[0].rate = 9000
		with self.assertRaises(frappe.ValidationError) as ctx:
			so.submit()
		self.assertIn(self.item_boi_so, str(ctx.exception))
		self.assertIn("sửa lại đúng giá đã đồng ý", str(ctx.exception))

	def test_gia_khop_gia_khach_dong_y_thi_xac_nhan_duoc(self):
		so = self._don_cho_xac_nhan_co_gia_da_dong_y(7000)
		so = apply_workflow(so, "Xác nhận")
		self.assertEqual(so.docstatus, 1)

	# ---- Phạm vi ------------------------------------------------------------

	def test_don_desk_khong_bi_chot(self):
		"""Đơn không phải từ cổng: cả hai chốt không áp."""
		so = self._don(self.item_boi_so)
		so.custom_nguon_don = "Nội bộ"
		so.save()
		so = apply_workflow(so, "Gửi duyệt")
		self.assertEqual(so.workflow_state, TT_CHO_MIYANO)
		# Chốt 3 — dựng ĐÚNG ca nó sinh ra để chặn (dòng "Báo giá", giá trên
		# đơn lệch giá khách đã đồng ý) ngay trong bộ nhớ. Vế đối chứng đi
		# trước: cũng dòng ấy trên đơn TỪ CỔNG thì bị chặn.
		dong = so.items[0]
		self.assertEqual(dong.custom_nguon_gia, "Báo giá")
		dong.custom_gia_khach_dong_y = 7000
		dong.rate = 9000
		so.custom_nguon_don = "Client Portal"
		with self.assertRaises(frappe.ValidationError):
			chot_bao_gia.kiem_gia_khop_gia_da_dong_y(so)
		so.custom_nguon_don = "Nội bộ"
		self.assertIsNone(chot_bao_gia.kiem_gia_khop_gia_da_dong_y(so))

	def test_don_cu_theo_hdnt_du_gia_khong_bi_chot(self):
		"""Đơn cổng tạo trước thay đổi: loại "Theo HĐNT", dòng chưa đóng dấu nguồn giá."""
		so = self._don(self.item_ngoai)
		frappe.db.set_value("Sales Order", so.name, "custom_loai_don", "Theo HĐNT")
		frappe.db.set_value("Sales Order Item", so.items[0].name, "custom_nguon_gia", None)
		so.reload()
		so = apply_workflow(so, "Gửi duyệt")
		self.assertEqual(so.workflow_state, TT_CHO_MIYANO)
		so = apply_workflow(so, "Xác nhận")
		self.assertEqual(so.docstatus, 1)


for _ten, _ham in vars(goc.TestPortalCatalogGop).items():
	if _ten.startswith("_") and not _ten.startswith("__") and callable(_ham):
		if _ten not in vars(TestChotBaoGia):
			setattr(TestChotBaoGia, _ten, _ham)
