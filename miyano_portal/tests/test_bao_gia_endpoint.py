"""Endpoint báo giá của cổng (spec 2026-10-12 §6, §8)."""

from unittest.mock import patch

import frappe
from frappe.model.workflow import apply_workflow

from miyano_portal import bao_gia
from miyano_portal.api import portal
from miyano_portal.portal_context import LOI_KHONG_THAY
from miyano_portal.tests.nen_bao_gia import NenBaoGia


class TestBaoGiaEndpoint(NenBaoGia):
	def setUp(self):
		super().setUp()
		self.ql_a = self._quan_ly("bgep.ql.a@demo.miyano", self.kh_a)
		self.ql_b = self._quan_ly("bgep.ql.b@demo.miyano", self.kh_b)
		for ten in frappe.get_all(
			"Portal De Xuat Mua", filters={"customer": ["like", "_TEST DX%"]}, pluck="name"
		):
			frappe.delete_doc("Portal De Xuat Mua", ten, force=True)

	def tearDown(self):
		super().tearDown()
		frappe.local.response.pop("filecontent", None)

	def _phieu(self, ma_hang, khach=None, khoa=None, trang_thai="Nháp"):
		doc = frappe.get_doc({
			"doctype": "Portal De Xuat Mua", "customer": khach or self.kh_a,
			"khoa_phong": khoa or self.khoa_huyethoc,
			"ly_do_yeu_cau": "Hết hàng trong kho khoa", "trang_thai": trang_thai,
			"items": [{"item_code": ma_hang, "so_luong_de_xuat": 20, "so_luong_duyet": 20}],
		})
		doc.insert(ignore_permissions=True)
		return doc

	def _phieu_co_bao_gia(self, gui_khach=True):
		"""Phiếu chờ báo giá đã duyệt, có Quotation đứng sau (việc của Task 12)."""
		phieu = self._phieu(self.item_boi_so, trang_thai="Đã duyệt")
		kq = bao_gia.tao_bao_gia(
			self.kh_a, items=[{"item_code": self.item_boi_so, "qty": 20}],
			request_id=frappe.generate_hash(length=12), khoa_phong=self.khoa_huyethoc,
		)
		frappe.db.set_value("Quotation", kq["bao_gia"], "custom_de_xuat", phieu.name)
		frappe.db.set_value("Portal De Xuat Mua", phieu.name, "bao_gia", kq["bao_gia"])
		bg = frappe.get_doc("Quotation", kq["bao_gia"])
		bg.items[0].rate = bg.items[0].price_list_rate = 7000
		bg.save()
		if gui_khach:
			bg = apply_workflow(bg, bao_gia.HD_GUI_KHACH)
		return phieu, bg

	def _goi(self, user, ham, *a, **kw):
		frappe.set_user(user)
		try:
			return ham(*a, **kw)
		finally:
			frappe.set_user("Administrator")

	# ---- hai tab

	def test_phieu_cho_bao_gia_roi_khoi_tab_don_hang(self):
		nhap_bg = self._phieu(self.item_boi_so)
		nhap_gia = self._phieu(self.item_ngoai)
		co_bg, _ = self._phieu_co_bao_gia()
		don = {r["de_xuat"] for r in self._goi(self.ql_a, portal.portal_yeu_cau_cua_toi)["rows"]}
		self.assertIn(nhap_gia.name, don)
		self.assertNotIn(nhap_bg.name, don)
		self.assertNotIn(co_bg.name, don)

	def test_tab_bao_gia_du_nam_nhom(self):
		nhap = self._phieu(self.item_boi_so)
		dang, bg_dang = self._phieu_co_bao_gia(gui_khach=False)
		cho, _ = self._phieu_co_bao_gia()
		dong_y, bg_dy = self._phieu_co_bao_gia()
		self._goi(self.ql_a, bao_gia.dong_y, bg_dy.name)
		dong, bg_dong = self._phieu_co_bao_gia()
		self._goi(self.ql_a, bao_gia.tu_choi, bg_dong.name, None)
		self._phieu(self.item_ngoai)  # phiếu có giá: không thuộc tab này

		rows = self._goi(self.ql_a, portal.portal_bao_gia_danh_sach)["rows"]
		theo_phieu = {r["de_xuat"]: r["nhom"] for r in rows}
		self.assertEqual(theo_phieu, {
			nhap.name: "nhap", dang.name: "dang_bao_gia", cho.name: "cho_dong_y",
			dong_y.name: "da_dong_y", dong.name: "da_dong",
		})
		loc = self._goi(self.ql_a, portal.portal_bao_gia_danh_sach, nhom="cho_dong_y")
		self.assertEqual((loc["tong"], loc["rows"][0]["de_xuat"]), (1, cho.name))
		self.assertEqual(self._goi(self.ql_a, portal.portal_bao_gia_dem), {"cho_dong_y": 1})

	def test_don_sinh_tu_bao_gia_hien_o_tab_don_hang(self):
		phieu, bg = self._phieu_co_bao_gia()
		kq = self._goi(self.ql_a, bao_gia.dong_y, bg.name)
		rows = self._goi(self.ql_a, portal.portal_yeu_cau_cua_toi)["rows"]
		dong = next(r for r in rows if r["de_xuat"] == phieu.name)
		self.assertEqual(dong["sales_order"], kq["sales_order"])

	def test_danh_sach_khong_lo_tong_tien_khi_miyano_dang_bao_gia(self):
		_, bg = self._phieu_co_bao_gia(gui_khach=False)
		row = self._goi(self.ql_a, portal.portal_bao_gia_danh_sach)["rows"][0]
		self.assertEqual(row["bao_gia"], bg.name)
		self.assertIsNone(row["grand_total"])

	def test_nhom_khong_hop_le(self):
		with self.assertRaises(frappe.ValidationError):
			self._goi(self.ql_a, portal.portal_bao_gia_danh_sach, nhom="tat_ca")

	# ---- cách ly

	def test_khach_khac_khong_thay_trong_danh_sach(self):
		self._phieu_co_bao_gia()
		self.assertEqual(self._goi(self.ql_b, portal.portal_bao_gia_danh_sach)["rows"], [])

	def test_khach_khac_khong_doc_khong_dong_y_khong_sua(self):
		_, bg = self._phieu_co_bao_gia()
		for ham, tham_so in (
			(portal.portal_bao_gia_chi_tiet, (bg.name,)),
			(portal.portal_bao_gia_dong_y, (bg.name,)),
			(portal.portal_bao_gia_tu_choi, (bg.name,)),
			(portal.portal_bao_gia_sua_so_luong, (bg.name, [{"name": bg.items[0].name, "qty": 40}])),
			(portal.portal_bao_gia_pdf, (None, bg.name)),
		):
			with self.assertRaises(frappe.PermissionError, msg=ham.__name__):
				self._goi(self.ql_b, ham, *tham_so)
		self.assertEqual(
			frappe.db.get_value("Quotation", bg.name, "workflow_state"), bao_gia.TT_CHO_KHACH
		)

	def test_khoa_khac_khong_thay(self):
		_, bg = self._phieu_co_bao_gia()
		khoa_khac = frappe.get_doc({
			"doctype": "Customer Department", "customer": self.kh_a,
			"ten_khoa_phong": "Khoa thử endpoint báo giá", "ma_khoa": "BGEP", "active": 1,
		}).insert(ignore_permissions=True).name
		nv = self._dam_bao_thanh_vien("bgep.nv@demo.miyano", self.kh_a, "Nhân viên khoa", khoa_khac)
		self.assertEqual(self._goi(nv, portal.portal_bao_gia_danh_sach)["rows"], [])
		for ham, tham_so in (
			(portal.portal_bao_gia_chi_tiet, (bg.name,)),
			(portal.portal_bao_gia_dong_y, (bg.name,)),
			(portal.portal_bao_gia_tu_choi, (bg.name,)),
			(portal.portal_bao_gia_sua_so_luong, (bg.name, [{"name": bg.items[0].name, "qty": 40}])),
			(portal.portal_bao_gia_pdf, (None, bg.name)),
		):
			with self.assertRaises(frappe.PermissionError, msg=ham.__name__):
				self._goi(nv, ham, *tham_so)
		self.assertEqual(
			frappe.db.get_value("Quotation", bg.name, "workflow_state"), bao_gia.TT_CHO_KHACH
		)

	def _loi_khong_thay(self, user, ham, *tham_so):
		"""Gọi và đòi ĐÚNG lời từ chối chung; trả các thông điệp phụ mà lời
		gọi để lại (`message_log` đi ra client qua `_server_messages`)."""
		frappe.clear_messages()
		with self.assertRaises(frappe.PermissionError) as cm:
			self._goi(user, ham, *tham_so)
		self.assertEqual(str(cm.exception), LOI_KHONG_THAY)
		return frappe.get_message_log()

	def test_ten_phai_la_chuoi_khong_nhan_bo_loc(self):
		"""`frappe.db.get_value`/`frappe.get_doc` nhận cả dict bộ lọc, và thân
		JSON của request đưa dict tới nguyên vẹn. Một bộ lọc kèm `grand_total`
		trên báo giá CỦA CHÍNH MÌNH biến "có/không tìm thấy" thành máy dò tổng
		tiền trong lúc Miyano còn đang báo giá. Khớp hay không khớp đều phải
		ra đúng một lời từ chối."""
		_, bg = self._phieu_co_bao_gia(gui_khach=False)
		khop = {"name": bg.name, "grand_total": [">", 1]}
		khong_khop = {"name": bg.name, "grand_total": [">", 10**12]}
		for ham, sau in (
			(portal.portal_bao_gia_chi_tiet, ()),
			(portal.portal_bao_gia_tu_choi, ()),
			(portal.portal_bao_gia_dong_y, ()),
			(portal.portal_bao_gia_sua_so_luong, ([{"name": bg.items[0].name, "qty": 40}],)),
		):
			for ten in (khop, khong_khop, [bg.name], None, ""):
				with self.subTest(ham=ham.__name__, ten=ten):
					self.assertEqual(self._loi_khong_thay(self.ql_a, ham, ten, *sau), [])
		for ten in (khop, khong_khop, [bg.name]):
			with self.subTest(ham="portal_bao_gia_pdf", ten=ten):
				self.assertEqual(
					self._loi_khong_thay(self.ql_a, portal.portal_bao_gia_pdf, None, ten), []
				)

	def test_bao_gia_khach_khac_va_ten_khong_ton_tai_tu_choi_nhu_nhau(self):
		_, bg = self._phieu_co_bao_gia()
		cua_khach_khac = self._loi_khong_thay(self.ql_b, portal.portal_bao_gia_chi_tiet, bg.name)
		khong_ton_tai = self._loi_khong_thay(
			self.ql_b, portal.portal_bao_gia_chi_tiet, "SAL-QTN-KHONG-CO-THAT"
		)
		self.assertEqual((cua_khach_khac, khong_ton_tai), ([], []))

	def test_phieu_tro_bao_gia_khong_noi_duoc_thi_khong_dua_ten_bao_gia(self):
		"""Phiếu trỏ sang báo giá không qua được phép nối (ở đây: báo giá nội
		bộ) không được mang tên báo giá ra: màn danh sách sẽ dẫn tới một trang
		chi tiết từ chối."""
		phieu = self._phieu(self.item_boi_so)
		noi_bo = self._bao_gia_tho(nguon="Nội bộ")
		frappe.db.set_value("Portal De Xuat Mua", phieu.name, "bao_gia", noi_bo.name)
		rows = self._goi(self.ql_a, portal.portal_bao_gia_danh_sach)["rows"]
		dong = next(r for r in rows if r["de_xuat"] == phieu.name)
		self.assertEqual((dong["bao_gia"], dong["nhom"]), ("", "nhap"))
		self.assertIsNone(dong["grand_total"])

	def test_phieu_luong_cu_co_don_khong_co_bao_gia_khong_vao_tab_bao_gia(self):
		phieu = self._phieu(self.item_boi_so, trang_thai="Đã duyệt")
		frappe.db.set_value("Portal De Xuat Mua", phieu.name, "sales_order", "SAL-ORD-LUONG-CU")
		rows = self._goi(self.ql_a, portal.portal_bao_gia_danh_sach)["rows"]
		self.assertNotIn(phieu.name, {r["de_xuat"] for r in rows})

	def test_danh_sach_kep_limit_va_start(self):
		phieu = self._phieu(self.item_boi_so)
		for kw in ({"start": -5}, {"limit": 10**9}, {"limit": -3}, {"limit": "abc", "start": "x"}):
			with self.subTest(**kw):
				kq = self._goi(self.ql_a, portal.portal_bao_gia_danh_sach, **kw)
				self.assertEqual([r["de_xuat"] for r in kq["rows"]], [phieu.name])
		self.assertEqual(portal._kep_trang_bao_gia(10**9, -5), (200, 0))
		self.assertEqual(portal._kep_trang_bao_gia(None, None), (20, 0))

	def test_pdf_thieu_ca_hai_ma(self):
		for tham_so in ((), (None, None), ("", "")):
			with self.assertRaises(frappe.ValidationError) as cm:
				self._goi(self.ql_a, portal.portal_bao_gia_pdf, *tham_so)
			self.assertEqual(str(cm.exception), "Thiếu mã chứng từ.")
			self.assertNotIsInstance(cm.exception, frappe.PermissionError)

	def test_bao_gia_noi_bo_cung_khach_khong_hien(self):
		noi_bo = self._bao_gia_tho(nguon="Nội bộ")
		with self.assertRaises(frappe.PermissionError):
			self._goi(self.ql_a, portal.portal_bao_gia_chi_tiet, noi_bo.name)

	# ---- chi tiết

	def test_chi_tiet_cho_khach_dong_y(self):
		phieu, bg = self._phieu_co_bao_gia()
		ct = self._goi(self.ql_a, portal.portal_bao_gia_chi_tiet, bg.name)
		self.assertEqual((ct["nhom"], ct["de_xuat"]), ("cho_dong_y", phieu.name))
		self.assertTrue(ct["hien_gia"])
		self.assertTrue(ct["duoc_dong_y"])
		self.assertTrue(ct["duoc_sua_so_luong"])
		self.assertEqual(ct["items"][0]["rate"], 7000)
		self.assertEqual(ct["tong_tien"], 140000)
		self.assertEqual(ct["han_hieu_luc"], str(bg.valid_till))

	def test_khong_thay_don_gia_khi_miyano_dang_bao_gia(self):
		_, bg = self._phieu_co_bao_gia(gui_khach=False)
		ct = self._goi(self.ql_a, portal.portal_bao_gia_chi_tiet, bg.name)
		self.assertFalse(ct["hien_gia"])
		self.assertIsNone(ct["items"][0]["rate"])
		self.assertIsNone(ct["items"][0]["amount"])
		self.assertIsNone(ct["tong_tien"])
		self.assertFalse(ct["duoc_dong_y"])

	def test_nhan_vien_khoa_dong_y_duoc_nhung_khong_sua_so_luong(self):
		_, bg = self._phieu_co_bao_gia()
		ct = self._goi(self.user_a, portal.portal_bao_gia_chi_tiet, bg.name)
		self.assertTrue(ct["duoc_dong_y"])
		self.assertFalse(ct["duoc_sua_so_luong"])
		with self.assertRaises(frappe.PermissionError):
			self._goi(self.user_a, portal.portal_bao_gia_sua_so_luong, bg.name,
			          [{"name": bg.items[0].name, "qty": 40}])

	# ---- hành động

	def test_dong_y_qua_endpoint(self):
		phieu, bg = self._phieu_co_bao_gia()
		kq = self._goi(self.ql_a, portal.portal_bao_gia_dong_y, bg.name)
		self.assertTrue(frappe.db.exists("Sales Order", kq["sales_order"]))
		ct = self._goi(self.ql_a, portal.portal_bao_gia_chi_tiet, bg.name)
		self.assertEqual((ct["nhom"], ct["sales_order"]), ("da_dong_y", kq["sales_order"]))

	def test_sua_so_luong_dong_bo_ve_phieu(self):
		phieu, bg = self._phieu_co_bao_gia()
		self._goi(self.ql_a, portal.portal_bao_gia_sua_so_luong, bg.name,
		          frappe.as_json([{"name": bg.items[0].name, "qty": 40}]))
		phieu.reload()
		self.assertEqual(phieu.items[0].so_luong_duyet, 40)

	def test_pdf(self):
		_, dang = self._phieu_co_bao_gia(gui_khach=False)
		with self.assertRaises(frappe.ValidationError):
			self._goi(self.ql_a, portal.portal_bao_gia_pdf, None, dang.name)
		_, bg = self._phieu_co_bao_gia()
		# Chặn ở `get_pdf` như `test_cach_ly_khoa_phong`: wkhtmltopdf của máy
		# chạy test không phải điều đang kiểm. HTML vẫn được dựng THẬT từ mẫu
		# in — endpoint dựng nó dưới `quyen_he_thong()`, sau khi
		# `_bao_gia_cua_toi` đã kiểm quyền của khách.
		giu = {}

		def pdf_gia(html, *a, **kw):
			giu["html"] = html
			return b"%PDF-fake"

		with patch("frappe.utils.pdf.get_pdf", side_effect=pdf_gia):
			self._goi(self.ql_a, portal.portal_bao_gia_pdf, None, bg.name)
		self.assertIn(bg.name, giu["html"])
		self.assertEqual(frappe.local.response.filecontent, b"%PDF-fake")
		self.assertEqual(frappe.local.response.type, "pdf")
		self.assertEqual(frappe.local.response.filename, f"BaoGia-{bg.name}.pdf")

	# ---- tổng quan và thông báo

	def test_kpi_dem_bao_gia_cho_dong_y(self):
		truoc = self._goi(self.ql_a, portal.portal_dashboard_kpi)["bao_gia_cho_dong_y"]
		self._phieu_co_bao_gia()
		self.assertEqual(
			self._goi(self.ql_a, portal.portal_dashboard_kpi)["bao_gia_cho_dong_y"], truoc + 1
		)

	def test_duong_dan_thong_bao(self):
		_, bg = self._phieu_co_bao_gia()
		self.assertEqual(
			portal._lien_ket_thong_bao("Quotation", bg.name, self.kh_a),
			f"/yeu-cau-bao-gia/{bg.name}",
		)
		self.assertIsNone(portal._lien_ket_thong_bao("Quotation", bg.name, self.kh_b))

	def test_thong_bao_bao_gia_loc_theo_khoa_o_tang_hook(self):
		"""`permissions.notification_khoa_query` là ranh giới thật của
		`Notification Log` (đọc được qua `frappe.client.*`): thêm "Quotation"
		vào hằng mà quên vế `exists` thì nhân viên ĐÚNG khoa mất luôn thông
		báo; quên cả hai thì nhân viên khoa khác đọc được tiêu đề."""
		from miyano_portal import permissions

		_, bg = self._phieu_co_bao_gia()
		khoa_khac = frappe.get_doc({
			"doctype": "Customer Department", "customer": self.kh_a,
			"ten_khoa_phong": "Khoa thử thông báo báo giá", "ma_khoa": "BGTB", "active": 1,
		}).insert(ignore_permissions=True).name
		nv = self._dam_bao_thanh_vien("bgep.tb@demo.miyano", self.kh_a, "Nhân viên khoa", khoa_khac)

		def dem(user):
			log = frappe.get_doc({
				"doctype": "Notification Log", "for_user": user, "type": "Alert",
				"subject": f"Báo giá {bg.name}", "document_type": "Quotation",
				"document_name": bg.name,
			}).insert(ignore_permissions=True)
			return frappe.db.sql(
				"select count(*) from `tabNotification Log` where name = %s and "
				+ permissions.notification_khoa_query(user).replace("%", "%%"),
				log.name,
			)[0][0]

		self.assertEqual(dem(self.user_a), 1)
		self.assertEqual(dem(nv), 0)
