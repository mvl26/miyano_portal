"""Phiếu đề xuất theo Price List (spec 2026-10-09 §3.2, §4.3)."""

import frappe
from frappe.tests.utils import FrappeTestCase

from miyano_portal import de_xuat_duyet
from miyano_portal.tests import test_chi_tiet_gop as goc
from miyano_portal.tests.fixtures_de_xuat import dung_fixture

BANG = "_TEST DX PBG"


class TestPhieuBangGia(FrappeTestCase):
	_thanh_vien = goc.TestChiTietGopBackend._thanh_vien

	def setUp(self):
		frappe.set_user("Administrator")
		goc._don_phieu_cu()
		f = dung_fixture(self)
		self.kh_a, self.khoa_a, self.item = f.kh_a, f.khoa_huyethoc, f.item
		if not frappe.db.exists("Price List", BANG):
			frappe.get_doc({"doctype": "Price List", "price_list_name": BANG,
			                "currency": "VND", "selling": 1, "enabled": 1}).insert()
		frappe.db.set_value("Customer", self.kh_a, "default_price_list", BANG)
		self._dat_gia(None)
		self.quan_ly = self._thanh_vien("pbg.ql@demo.miyano", "Quản lý", None)
		self.nhan_vien = self._thanh_vien("pbg.nv@demo.miyano", "Nhân viên khoa", self.khoa_a)

	def tearDown(self):
		frappe.set_user("Administrator")

	def _dat_gia(self, rate):
		for ten in frappe.get_all(
			"Item Price", filters={"item_code": self.item, "selling": 1}, pluck="name"
		):
			frappe.delete_doc("Item Price", ten, force=True)
		if rate is not None:
			frappe.get_doc({"doctype": "Item Price", "item_code": self.item,
			                "price_list": BANG, "selling": 1,
			                "price_list_rate": rate}).insert()

	def _phieu(self, gui=True):
		doc = frappe.get_doc({
			"doctype": "Portal De Xuat Mua", "customer": self.kh_a,
			"khoa_phong": self.khoa_a, "ly_do_yeu_cau": "Hết hàng trong kho khoa",
			"items": [{"item_code": self.item, "so_luong_de_xuat": 5}],
		}).insert(ignore_permissions=True)
		frappe.db.set_value("Portal De Xuat Mua", doc.name, "owner", self.nhan_vien)
		doc.reload()
		if gui:
			doc.gui_duyet()
			doc.reload()
		return doc

	def test_dong_co_gia_la_nguon_bang_gia(self):
		self._dat_gia(54000)
		row = self._phieu(gui=False).items[0]
		self.assertEqual(row.nguon_gia, "Bảng giá")
		self.assertFalse(row.blanket_order)

	def test_dong_chua_co_gia_la_cho_bao_gia(self):
		self.assertEqual(self._phieu(gui=False).items[0].nguon_gia, "Chờ báo giá")

	def test_gui_duyet_dong_dau_don_gia_bang_gia(self):
		self._dat_gia(54000)
		self.assertEqual(float(self._phieu().items[0].don_gia), 54000.0)

	def test_duyet_canh_bao_khi_gia_doi_va_don_mang_gia_moi(self):
		self._dat_gia(54000)
		doc = self._phieu()
		self._dat_gia(60000)
		kq = de_xuat_duyet.duyet_va_tao_don(doc.name, self.quan_ly)
		self.assertEqual(kq["canh_bao_gia"], [{
			"item_code": self.item, "gia_cu": 54000.0, "gia_moi": 60000.0,
			"ly_do": "gia_doi",
		}])
		self.assertEqual(
			float(frappe.db.get_value(
				"Sales Order Item", {"parent": kq["sales_order"]}, "rate")),
			60000.0,
		)

	def test_duyet_bi_chan_khi_dong_bang_gia_mat_gia(self):
		self._dat_gia(54000)
		doc = self._phieu()
		self._dat_gia(None)
		with self.assertRaises(frappe.ValidationError) as ctx:
			de_xuat_duyet.duyet_va_tao_don(doc.name, self.quan_ly)
		self.assertIn(self.item, str(ctx.exception))
		self.assertEqual(
			frappe.db.get_value("Portal De Xuat Mua", doc.name, "trang_thai"),
			"Chờ duyệt",
		)

	def test_phieu_cho_bao_gia_vua_co_gia_thi_don_di_thang(self):
		doc = self._phieu()
		self._dat_gia(54000)
		kq = de_xuat_duyet.duyet_va_tao_don(doc.name, self.quan_ly)
		self.assertEqual(
			frappe.db.get_value("Sales Order", kq["sales_order"], "custom_loai_don"),
			"Theo bảng giá",
		)

	# ---- Ruling R5 — lối thoát của lời chặn "mất giá" phải chạy được ----
	# Mỗi lần GỬI DUYỆT (kể cả gửi lại sau "Từ chối"/"Thu hồi"), dòng đã đóng
	# dấu "Bảng giá" mà mặt hàng không còn giá thì chuyển sang "Chờ báo giá"
	# với `don_gia = 0`, DÙ dòng đã đóng băng. Mọi dòng đóng băng khác giữ
	# nguyên.

	def _doc_moi(self, ten):
		"""Nạp `Document` MỚI như endpoint thật làm ở mỗi request."""
		return frappe.get_doc("Portal De Xuat Mua", ten)

	def _khang_dinh_thanh_don_bao_gia(self, ten):
		doc = self._doc_moi(ten)
		self.assertEqual(doc.trang_thai, "Chờ duyệt")
		self.assertEqual(doc.items[0].nguon_gia, "Chờ báo giá")
		self.assertEqual(float(doc.items[0].don_gia or 0), 0.0)
		kq = de_xuat_duyet.duyet_va_tao_don(ten, self.quan_ly)
		self.assertEqual(kq["canh_bao_gia"], [])
		self.assertEqual(
			frappe.db.get_value("Sales Order", kq["sales_order"], "custom_loai_don"),
			"Mua lẻ",
		)
		dong = frappe.db.get_value(
			"Sales Order Item", {"parent": kq["sales_order"]},
			["rate", "custom_nguon_gia"], as_dict=True,
		)
		self.assertEqual(float(dong.rate), 0.0)
		self.assertEqual(dong.custom_nguon_gia, "Báo giá")

	def test_mat_gia_bi_chan_roi_tu_choi_gui_lai_thi_thanh_cho_bao_gia(self):
		self._dat_gia(54000)
		ten = self._phieu().name
		self._dat_gia(None)
		with self.assertRaises(frappe.ValidationError):
			de_xuat_duyet.duyet_va_tao_don(ten, self.quan_ly)
		self._doc_moi(ten).tu_choi("Mặt hàng không còn giá trong bảng giá")
		self._doc_moi(ten).gui_duyet()
		self._khang_dinh_thanh_don_bao_gia(ten)

	def test_mat_gia_roi_thu_hoi_gui_lai_thi_thanh_cho_bao_gia(self):
		self._dat_gia(54000)
		ten = self._phieu().name
		self._dat_gia(None)
		self._doc_moi(ten).thu_hoi()
		# Thu hồi một mình KHÔNG viết lại bằng chứng đã đóng băng — chỉ lần
		# GỬI DUYỆT mới làm.
		self.assertEqual(self._doc_moi(ten).items[0].nguon_gia, "Bảng giá")
		self._doc_moi(ten).gui_duyet()
		self._khang_dinh_thanh_don_bao_gia(ten)

	def test_luu_phieu_khong_viet_lai_dong_bang_gia_da_mat_gia(self):
		"""R5 nằm ở chỗ đóng dấu giá lúc gửi, KHÔNG ở `validate()`: một lần
		lưu bất kỳ không được viết lại bằng chứng đã đóng băng."""
		self._dat_gia(54000)
		ten = self._phieu().name
		self._dat_gia(None)
		self._doc_moi(ten).save(ignore_permissions=True)
		row = self._doc_moi(ten).items[0]
		self.assertEqual(row.nguon_gia, "Bảng giá")
		self.assertEqual(float(row.don_gia), 54000.0)

	def test_gia_chi_doi_thi_gui_lai_van_la_bang_gia_va_dong_dau_gia_moi(self):
		self._dat_gia(54000)
		ten = self._phieu().name
		self._dat_gia(60000)
		self._doc_moi(ten).tu_choi("Chưa cần gấp")
		self._doc_moi(ten).gui_duyet()
		row = self._doc_moi(ten).items[0]
		self.assertEqual(row.nguon_gia, "Bảng giá")
		self.assertEqual(float(row.don_gia), 60000.0)
		# Con dấu đã là giá hiện hành nên không còn gì để cảnh báo.
		kq = de_xuat_duyet.duyet_va_tao_don(ten, self.quan_ly)
		self.assertEqual(kq["canh_bao_gia"], [])

	def test_dong_cho_bao_gia_da_dong_bang_vua_co_gia_thi_gui_lai_van_giu_nguyen(self):
		ten = self._phieu().name
		self._dat_gia(54000)
		self._doc_moi(ten).tu_choi("Chưa cần gấp")
		self._doc_moi(ten).gui_duyet()
		row = self._doc_moi(ten).items[0]
		self.assertEqual(row.nguon_gia, "Chờ báo giá")
		self.assertEqual(float(row.don_gia or 0), 0.0)

	def test_dong_cu_hop_dong_khong_bi_dung_toi_khi_gui_lai(self):
		"""Dòng lập TRƯỚC spec 2026-10-09 (đóng băng "Hợp đồng" + hợp đồng
		khung + con dấu 300), mặt hàng không có giá Price List: gửi lại
		không đổi gì trên nó."""
		ten = self._phieu().name
		bo = frappe.get_doc({
			"doctype": "Blanket Order", "blanket_order_type": "Selling",
			"customer": self.kh_a, "company": "Miyano Việt Nam",
			"from_date": frappe.utils.today(),
			"to_date": frappe.utils.add_days(frappe.utils.today(), 365),
			# `rate: 0` — hợp đồng có khai giá sẽ tự chép giá sang Price List
			# lúc submit (`gia_hdnt.tu_hdnt`).
			"items": [{"item_code": self.item, "qty": 5, "rate": 0}],
		}).insert(ignore_permissions=True)
		bo.submit()
		frappe.db.set_value(
			"Portal De Xuat Mua Item", self._doc_moi(ten).items[0].name,
			{"nguon_gia": "Hợp đồng", "blanket_order": bo.name, "don_gia": 300},
		)
		self._doc_moi(ten).tu_choi("Chưa cần gấp")
		self._doc_moi(ten).gui_duyet()
		row = self._doc_moi(ten).items[0]
		self.assertEqual(row.nguon_gia, "Hợp đồng")
		self.assertEqual(row.blanket_order, bo.name)
		self.assertEqual(float(row.don_gia), 300.0)
