"""Chốt của luồng báo giá (spec 2026-10-09 §5.1, §5.4)."""

import frappe
from frappe.model.workflow import apply_workflow
from frappe.tests.utils import FrappeTestCase

from miyano_portal import bang_gia_khach as bg
from miyano_portal import chot_bao_gia, dat_hang
from miyano_portal.api import portal
from miyano_portal.tests import test_catalog_gop as goc

WF = "Sales Order - Client Portal"


class TestChotBaoGia(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		# Cạnh mới của workflow nằm trong giao dịch của lớp test (rollback khi
		# hết lớp). Bản Workflow trong cache tài liệu thì KHÔNG theo giao dịch:
		# xoá nó SAU rollback (đăng ký trước `super()` vì cleanup chạy ngược).
		cls.addClassCleanup(frappe.clear_document_cache, "Workflow", WF)
		super().setUpClass()
		from miyano_portal.patches.v1_41 import gia_theo_price_list

		gia_theo_price_list.mo_rong_workflow()

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

	# ---- Final-fix I-1: lối ra của chốt 3 ---------------------------------
	# Chốt 3 bảo "gửi khách duyệt lại", nên từ "Chờ Miyano xác nhận" phải có
	# đường quay về "Chờ khách đồng ý" — trước đó chỉ có "Xác nhận" / "Từ chối".

	def _khach(self, so, action, **them):
		ql = self._dam_bao_thanh_vien("chot.ql@demo.miyano", self.kh_a, "Quản lý", None)
		frappe.set_user(ql)
		try:
			return portal.portal_order_accept(so.name, action, **them)
		finally:
			frappe.set_user("Administrator")

	def _dau(self, so):
		return float(frappe.db.get_value(
			"Sales Order Item", so.items[0].name, "custom_gia_khach_dong_y") or 0)

	def test_sua_gia_sau_khi_khach_dong_y_thi_gui_khach_duyet_lai_duoc(self):
		"""Đi hết vòng: báo giá A → khách đồng ý (bảng giá A, dấu A) → nhân viên
		sửa thành B → xác nhận bị chặn → «Gửi khách duyệt» → khách đồng ý →
		bảng giá B (vẫn MỘT dòng giá, R13), dấu B → xác nhận được."""
		so = apply_workflow(self._don_da_dien_gia(), "Gửi khách duyệt")
		self._khach(so, "dong_y")
		so.reload()
		self.assertEqual(so.workflow_state, "Chờ Miyano xác nhận")
		self.assertEqual(bg.gia_bang_gia(self.kh_a, self.item_boi_so), 7000.0)
		self.assertEqual(self._dau(so), 7000.0)

		so.items[0].rate = 9000
		so.save()
		with self.assertRaises(frappe.ValidationError) as ctx:
			apply_workflow(frappe.get_doc("Sales Order", so.name), "Xác nhận")
		self.assertIn("gửi khách duyệt lại", str(ctx.exception))

		# Hiệu lực báo giá đếm lại từ lần gửi này, không phải lần gửi đầu.
		frappe.db.set_value("Sales Order", so.name, "custom_ngay_gui_khach_duyet",
		                    frappe.utils.add_days(frappe.utils.today(), -5),
		                    update_modified=False)
		so = apply_workflow(frappe.get_doc("Sales Order", so.name), "Gửi khách duyệt")
		self.assertEqual(so.workflow_state, "Chờ khách đồng ý")
		self.assertEqual(str(so.custom_ngay_gui_khach_duyet), frappe.utils.today())
		self.assertEqual(self._dau(so), 0.0, "vòng mới đóng dấu lại lúc khách đồng ý")
		self.assertEqual(float(so.items[0].rate), 9000.0)
		# Khách chưa đồng ý giá mới thì bảng giá vẫn là giá đã đồng ý lần trước.
		self.assertEqual(bg.gia_bang_gia(self.kh_a, self.item_boi_so), 7000.0)

		# Phía khách: đơn lại hiện là báo giá đang chờ, với giá mới.
		ql = self._dam_bao_thanh_vien("chot.ql@demo.miyano", self.kh_a, "Quản lý", None)
		frappe.set_user(ql)
		try:
			kq = portal.portal_order_track(order=so.name)
		finally:
			frappe.set_user("Administrator")
		self.assertEqual(kq["workflow_state"], "Chờ khách đồng ý")
		self.assertEqual(float(kq["items"][0]["rate"]), 9000.0)

		self.assertEqual(self._khach(so, "dong_y")["trang_thai_moi"], "Chờ Miyano xác nhận")
		self.assertEqual(bg.gia_bang_gia(self.kh_a, self.item_boi_so), 9000.0)
		bang = frappe.db.get_value("Customer", self.kh_a, "default_price_list")
		self.assertEqual(frappe.db.count("Item Price", {
			"item_code": self.item_boi_so, "price_list": bang, "selling": 1,
		}), 1)
		self.assertEqual(self._dau(so), 9000.0)

		so = apply_workflow(frappe.get_doc("Sales Order", so.name), "Xác nhận")
		self.assertEqual(so.docstatus, 1)

	def test_khach_khong_dong_y_vong_hai_thi_ve_cho_xac_nhan(self):
		so = apply_workflow(self._don_da_dien_gia(), "Gửi khách duyệt")
		self._khach(so, "dong_y")
		so.reload()
		so.items[0].rate = 9000
		so.save()
		so = apply_workflow(so, "Gửi khách duyệt")
		kq = self._khach(so, "khong_dong_y", ly_do="Giá mới cao hơn giá đã thống nhất")
		self.assertEqual(kq["trang_thai_moi"], "Chờ xác nhận")
		self.assertEqual(self._dau(so), 0.0)
		self.assertEqual(bg.gia_bang_gia(self.kh_a, self.item_boi_so), 7000.0)

	def test_gui_khach_duyet_lai_van_qua_chot_2(self):
		"""Chốt 2 đứng trên MỌI bước vào "Chờ khách đồng ý", kể cả bước mới."""
		so = apply_workflow(self._don_da_dien_gia(), "Gửi khách duyệt")
		self._khach(so, "dong_y")
		so.reload()
		so.items[0].rate = 0
		so.save()
		with self.assertRaises(frappe.ValidationError) as ctx:
			apply_workflow(so, "Gửi khách duyệt")
		self.assertIn(self.item_boi_so, str(ctx.exception))
		self.assertIn("chưa có đơn giá", str(ctx.exception))

	def test_don_theo_bang_gia_dung_duoc_buoc_gui_khach_duyet_lai(self):
		"""Đơn "Theo bảng giá" ở "Chờ Miyano xác nhận" dùng được bước mới mà
		không lỗi; khách đồng ý không ghi gì vào Price List, không đóng dấu
		(hành vi sẵn có của đơn không đi vòng báo giá)."""
		so = apply_workflow(self._don(self.item_ngoai), "Gửi duyệt")
		self.assertEqual(so.custom_loai_don, "Theo bảng giá")

		def gia():
			return frappe.get_all(
				"Item Price", filters={"item_code": self.item_ngoai, "selling": 1},
				fields=["name", "price_list_rate", "modified"], order_by="name asc")

		truoc = gia()
		so = apply_workflow(so, "Gửi khách duyệt")
		self.assertEqual(so.workflow_state, "Chờ khách đồng ý")
		self.assertEqual(so.items[0].custom_nguon_gia, "Bảng giá")
		self._khach(so, "dong_y")
		so.reload()
		self.assertEqual(so.workflow_state, "Chờ Miyano xác nhận")
		self.assertEqual(gia(), truoc)
		self.assertEqual(self._dau(so), 0.0)
		so = apply_workflow(so, "Xác nhận")
		self.assertEqual(so.docstatus, 1)

	def test_chot_1_khong_dinh_buoc_khach_dong_y_cua_vong_hai(self):
		"""Chốt 1 chỉ bắt "Chờ xác nhận" → "Chờ Miyano xác nhận"; bước "Khách
		đồng ý" của vòng hai (từ "Chờ khách đồng ý") đi qua."""
		so = apply_workflow(self._don_da_dien_gia(), "Gửi khách duyệt")
		so = apply_workflow(so, "Khách đồng ý")
		so = apply_workflow(so, "Gửi khách duyệt")
		so = apply_workflow(so, "Khách đồng ý")
		self.assertEqual(so.workflow_state, "Chờ Miyano xác nhận")

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
