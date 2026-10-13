"""Hai đường tạo đơn rẽ sang Quotation (spec 2026-10-12 §5)."""

from unittest.mock import patch

import frappe

from miyano_portal import bao_gia, de_xuat_duyet
from miyano_portal.api import portal
from miyano_portal.portal_mua_le import ITEM_GIU_CHO
from miyano_portal.tests.nen_bao_gia import NenBaoGia
from miyano_portal.tests import test_tach_phieu as tp

# `khong_co_anh`: dòng gõ tay không ảnh bị `gui_duyet()` từ chối (BR-Y5).
DONG_GO_TAY = {
	"ten_hang": "Kim sinh thiết thử", "dvt": "Cái", "so_luong": 2, "khong_co_anh": 1,
}


class TestBaoGiaReNhanh(NenBaoGia):
	# Quản lý có Contact gắn với khách: ERPNext từ chối `contact_person` lạ.
	# Nhập MODULE chứ không nhập lớp: lớp test nhập thẳng vào đây sẽ bị bộ
	# chạy test coi là test của file này và chạy lại toàn bộ.
	_quan_ly_cua = tp.TestTachPhieu._quan_ly_cua

	def setUp(self):
		super().setUp()
		self.ql = self._quan_ly_cua("bgrn.ql@demo.miyano", self.kh_a)
		frappe.db.set_value("Customer", self.kh_a, "account_manager", "Administrator")
		# Đơn nháp của test trước phải đi TRƯỚC phiếu: xoá phiếu mới nhất làm
		# Frappe lùi bộ đếm tên, phiếu sau nhận lại đúng tên cũ, và đơn còn sống
		# mang `custom_request_id` = tên đó sẽ bị coi là đơn của phiếu mới (cùng
		# bẫy với `test_de_xuat_duyet._don_phieu_cu`).
		for ten in frappe.get_all(
			"Sales Order", filters={"customer": ["like", "_TEST DX%"], "docstatus": 0},
			pluck="name",
		):
			frappe.delete_doc("Sales Order", ten, force=True, ignore_permissions=True)
		for ten in frappe.get_all(
			"Portal De Xuat Mua", filters={"customer": ["like", "_TEST DX%"]}, pluck="name"
		):
			frappe.delete_doc("Portal De Xuat Mua", ten, force=True)

	def _phieu_cho_duyet(self, ma_hang, dat_ngoai=None):
		doc = frappe.get_doc({
			"doctype": "Portal De Xuat Mua", "customer": self.kh_a,
			"khoa_phong": self.khoa_huyethoc, "ly_do_yeu_cau": "Hết hàng trong kho khoa",
			"ten_don_hang": "Đợt thử rẽ nhánh",
			"items": [{"item_code": ma_hang, "so_luong_de_xuat": 20}] if ma_hang else [],
			"dat_ngoai": dat_ngoai or [],
		}).insert(ignore_permissions=True)
		frappe.db.set_value("Portal De Xuat Mua", doc.name, "owner", self.user_a)
		doc.reload()
		doc.gui_duyet()
		return doc

	def _duyet(self, doc):
		frappe.set_user(self.ql)
		try:
			return de_xuat_duyet.duyet_va_tao_don(doc.name, self.ql)
		finally:
			frappe.set_user("Administrator")

	def _dat(self, **gio):
		frappe.set_user(self.ql)
		try:
			return portal.portal_order_place(request_id=frappe.generate_hash(length=12), **gio)
		finally:
			frappe.set_user("Administrator")

	# ---- khoa gửi đề xuất, quản lý duyệt

	def test_phieu_cho_bao_gia_sinh_quotation_khong_sinh_don(self):
		doc = self._phieu_cho_duyet(self.item_boi_so)
		kq = self._duyet(doc)
		self.assertIsNone(kq["sales_order"])
		bg = frappe.get_doc("Quotation", kq["bao_gia"])
		self.assertEqual(bg.workflow_state, bao_gia.TT_CHO_MIYANO)
		self.assertEqual(bg.custom_de_xuat, doc.name)
		self.assertEqual(bg.custom_khoa_phong, self.khoa_huyethoc)
		self.assertEqual(bg.custom_ten_don_hang, "Đợt thử rẽ nhánh")
		doc.reload()
		self.assertEqual((doc.trang_thai, doc.bao_gia), ("Đã duyệt", bg.name))
		self.assertFalse(doc.sales_order)
		self.assertFalse(frappe.db.exists("Sales Order", {"custom_de_xuat": doc.name}))

	def test_phieu_co_gia_van_sinh_don(self):
		doc = self._phieu_cho_duyet(self.item_ngoai)
		kq = self._duyet(doc)
		self.assertIsNone(kq["bao_gia"])
		self.assertEqual(
			frappe.db.get_value("Sales Order", kq["sales_order"], "custom_loai_don"),
			"Theo bảng giá",
		)

	def test_moi_dong_vua_co_gia_thi_di_thang_don(self):
		doc = self._phieu_cho_duyet(self.item_boi_so)
		self._tao_gia(self.item_boi_so, self.price_list, 7000)
		kq = self._duyet(doc)
		self.assertIsNone(kq["bao_gia"])
		self.assertTrue(frappe.db.exists("Sales Order", kq["sales_order"]))

	def test_phieu_chi_co_dong_go_tay(self):
		doc = self._phieu_cho_duyet(None, dat_ngoai=[DONG_GO_TAY])
		bg = frappe.get_doc("Quotation", self._duyet(doc)["bao_gia"])
		self.assertEqual([d.item_code for d in bg.items], [ITEM_GIU_CHO])
		self.assertEqual(bg.custom_dat_ngoai[0].ten_hang, "Kim sinh thiết thử")

	def test_nhan_vien_phu_trach_duoc_bao(self):
		kq = self._duyet(self._phieu_cho_duyet(self.item_boi_so))
		self.assertTrue(frappe.db.exists("Notification Log", {
			"document_type": "Quotation", "document_name": kq["bao_gia"],
			"for_user": "Administrator",
		}))

	def test_duyet_lai_khong_sinh_bao_gia_thu_hai(self):
		doc = self._phieu_cho_duyet(self.item_boi_so)
		self._duyet(doc)
		with self.assertRaises(frappe.ValidationError):
			self._duyet(doc)
		self.assertEqual(frappe.db.count("Quotation", {"custom_de_xuat": doc.name}), 1)

	# ---- quản lý đặt trực tiếp

	def test_gio_tron_mot_don_mot_bao_gia(self):
		kq = self._dat(items=[
			{"item_code": self.item_ngoai, "qty": 10},
			{"item_code": self.item_boi_so, "qty": 20},
		], khoa_phong=self.khoa_huyethoc)
		self.assertEqual(len(kq["don"]), 2)
		don, bg = kq["don"]
		self.assertEqual(don["loai_don"], "Theo bảng giá")
		self.assertTrue(frappe.db.exists("Sales Order", don["sales_order"]))
		self.assertIsNone(bg["sales_order"])
		self.assertEqual(bg["loai_don"], "Yêu cầu báo giá")
		phieu = frappe.get_doc("Portal De Xuat Mua", bg["de_xuat"])
		self.assertEqual((phieu.bao_gia, phieu.trang_thai), (bg["bao_gia"], "Đã duyệt"))
		self.assertFalse(phieu.sales_order)
		self.assertEqual(
			frappe.db.get_value("Quotation", bg["bao_gia"], "custom_de_xuat"), phieu.name
		)

	def test_gio_chi_co_hang_chua_gia(self):
		kq = self._dat(items=[{"item_code": self.item_boi_so, "qty": 20}],
		               khoa_phong=self.khoa_huyethoc)
		self.assertEqual(len(kq["don"]), 1)
		self.assertIsNone(kq["sales_order"])
		self.assertTrue(frappe.db.exists("Quotation", kq["bao_gia"]))

	def test_bam_lai_khong_sinh_trung(self):
		rid = frappe.generate_hash(length=12)
		gio = {"items": [{"item_code": self.item_boi_so, "qty": 20}],
		       "khoa_phong": self.khoa_huyethoc, "request_id": rid}
		frappe.set_user(self.ql)
		kq1 = portal.portal_order_place(**gio)
		kq2 = portal.portal_order_place(**gio)
		frappe.set_user("Administrator")
		self.assertEqual(kq1["bao_gia"], kq2["bao_gia"])
		self.assertEqual(kq1["de_xuat"], kq2["de_xuat"])
		self.assertEqual(frappe.db.count("Quotation", {"custom_request_id": rid}), 1)

	def test_bam_lai_sau_khi_mat_gia_van_tra_don_cu(self):
		"""Lần bấm đầu đã sinh Sales Order; giá biến mất rồi bấm lại cùng mã
		yêu cầu thì trả đúng đơn đó, không sinh thêm một Quotation."""
		rid = frappe.generate_hash(length=12)
		gio = {"items": [{"item_code": self.item_ngoai, "qty": 10}],
		       "khoa_phong": self.khoa_huyethoc, "request_id": rid}
		frappe.set_user(self.ql)
		kq1 = portal.portal_order_place(**gio)
		frappe.set_user("Administrator")
		self.assertTrue(kq1["sales_order"])
		for ten in frappe.get_all(
			"Item Price", filters={"item_code": self.item_ngoai, "selling": 1}, pluck="name"
		):
			frappe.delete_doc("Item Price", ten, force=True)
		frappe.set_user(self.ql)
		kq2 = portal.portal_order_place(**gio)
		frappe.set_user("Administrator")
		self.assertEqual(kq2["sales_order"], kq1["sales_order"])
		self.assertIsNone(kq2["bao_gia"])
		self.assertEqual(kq2["de_xuat"], kq1["de_xuat"])
		self.assertEqual(frappe.db.count("Quotation", {"custom_request_id": rid}), 0)

	def test_khong_con_don_mua_le_moi(self):
		truoc = frappe.db.count("Sales Order", {"custom_loai_don": "Mua lẻ"})
		self._duyet(self._phieu_cho_duyet(self.item_boi_so))
		self._dat(items=[{"item_code": self.item_boi_so, "qty": 20}], dat_ngoai=[DONG_GO_TAY],
		          khoa_phong=self.khoa_huyethoc)
		self.assertEqual(frappe.db.count("Sales Order", {"custom_loai_don": "Mua lẻ"}), truoc)

	# ---- M4: mã mới chạy trên site chưa `bench migrate`

	def _khong_cham_quotation(self):
		"""Chạy khối lệnh với `bao_gia.san_sang()` = False và trả mọi câu SQL
		đã chạy: không câu nào được nhắc tới bảng Quotation (cột
		`custom_request_id` của nó chưa có)."""
		that = frappe.db.sql
		cau = []

		def gia(query, *a, **kw):
			cau.append(str(query))
			return that(query, *a, **kw)

		return cau, patch.object(bao_gia, "san_sang", return_value=False), patch.object(
			frappe.local.db, "sql", side_effect=gia
		)

	def test_san_sang_tren_site_da_migrate(self):
		self.assertIs(bao_gia.san_sang(), True)

	def test_chua_san_sang_gio_chua_gia_van_sinh_don_mua_le(self):
		so_bg = frappe.db.count("Quotation")
		cau, khong_san_sang, nghe_sql = self._khong_cham_quotation()
		with khong_san_sang, nghe_sql:
			kq = self._dat(items=[{"item_code": self.item_boi_so, "qty": 20}],
			               khoa_phong=self.khoa_huyethoc)
		self.assertIsNone(kq["bao_gia"])
		self.assertEqual(
			frappe.db.get_value("Sales Order", kq["sales_order"], "custom_loai_don"), "Mua lẻ"
		)
		self.assertEqual(frappe.db.count("Quotation"), so_bg)
		self.assertTrue(cau)
		self.assertEqual([c for c in cau if "tabQuotation" in c], [])

	def test_chua_san_sang_gio_co_gia_khong_cham_quotation(self):
		cau, khong_san_sang, nghe_sql = self._khong_cham_quotation()
		with khong_san_sang, nghe_sql:
			kq = self._dat(items=[{"item_code": self.item_ngoai, "qty": 10}],
			               khoa_phong=self.khoa_huyethoc)
		self.assertEqual(
			frappe.db.get_value("Sales Order", kq["sales_order"], "custom_loai_don"),
			"Theo bảng giá",
		)
		self.assertTrue(cau)
		self.assertEqual([c for c in cau if "tabQuotation" in c], [])

	def test_chua_san_sang_gio_tron_ra_hai_don(self):
		cau, khong_san_sang, nghe_sql = self._khong_cham_quotation()
		with khong_san_sang, nghe_sql:
			kq = self._dat(items=[
				{"item_code": self.item_ngoai, "qty": 10},
				{"item_code": self.item_boi_so, "qty": 20},
			], khoa_phong=self.khoa_huyethoc)
		self.assertEqual([d["loai_don"] for d in kq["don"]], ["Theo bảng giá", "Mua lẻ"])
		self.assertEqual([d["bao_gia"] for d in kq["don"]], [None, None])
		self.assertEqual([c for c in cau if "tabQuotation" in c], [])

	def test_chua_san_sang_duyet_phieu_van_sinh_don_mua_le(self):
		doc = self._phieu_cho_duyet(self.item_boi_so)
		cau, khong_san_sang, nghe_sql = self._khong_cham_quotation()
		with khong_san_sang, nghe_sql:
			kq = self._duyet(doc)
		self.assertIsNone(kq["bao_gia"])
		self.assertEqual(
			frappe.db.get_value("Sales Order", kq["sales_order"], "custom_loai_don"), "Mua lẻ"
		)
		doc.reload()
		self.assertEqual((doc.trang_thai, doc.sales_order), ("Đã duyệt", kq["sales_order"]))
		self.assertFalse(doc.bao_gia)
		self.assertEqual([c for c in cau if "tabQuotation" in c], [])
