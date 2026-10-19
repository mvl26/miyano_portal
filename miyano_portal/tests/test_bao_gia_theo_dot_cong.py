"""API cổng cho báo giá theo đợt (spec 2026-10-15 §5)."""

from unittest.mock import patch

import frappe

from miyano_portal import bao_gia, bao_gia_theo_dot as dot
from miyano_portal.api import portal
from miyano_portal.portal_context import LOI_KHONG_THAY
from miyano_portal.tests.nen_bao_gia import NenBaoGiaTheoDot


class TestCongTheoDot(NenBaoGiaTheoDot):
	def setUp(self):
		super().setUp()
		self.ql_a = self._quan_ly("dotcong.ql.a@demo.miyano", self.kh_a)
		self.ql_b = self._quan_ly("dotcong.ql.b@demo.miyano", self.kh_b)
		for ten in frappe.get_all(
			"Portal De Xuat Mua", filters={"customer": ["like", "_TEST DX%"]}, pluck="name"
		):
			frappe.delete_doc("Portal De Xuat Mua", ten, force=True)
		self.phieu = frappe.get_doc({
			"doctype": "Portal De Xuat Mua", "customer": self.kh_a,
			"khoa_phong": self.khoa_huyethoc, "ly_do_yeu_cau": "Hết hàng trong kho khoa",
			"trang_thai": "Đã duyệt",
			"items": [{"item_code": self.item_ngoai, "so_luong_de_xuat": 10, "so_luong_duyet": 10}],
		}).insert(ignore_permissions=True)
		self.goc = self._goc_ba_dong(custom_de_xuat=self.phieu.name, khoa=self.khoa_huyethoc)
		frappe.db.set_value("Portal De Xuat Mua", self.phieu.name, "bao_gia", self.goc.name)

	def _goi(self, user, ham, *a, **kw):
		frappe.set_user(user)
		try:
			return ham(*a, **kw)
		finally:
			frappe.set_user("Administrator")

	def _tach(self, *ma):
		self.goc.reload()
		return dot.tach_dot(self.goc.name, [d.name for d in self.goc.items if d.item_code in ma])["dot"]

	def _dong_cua_phieu(self):
		rows = self._goi(self.ql_a, portal.portal_bao_gia_danh_sach)["rows"]
		return [r for r in rows if r["de_xuat"] == self.phieu.name]

	def test_danh_sach_chi_hien_phieu_goc_nhom_cho_dong_y(self):
		self._tach(self.item_ngoai)
		self._tach(self.item_boi_so)
		dong = self._dong_cua_phieu()
		self.assertEqual(len(dong), 1)
		self.assertEqual(dong[0]["bao_gia"], self.goc.name)
		self.assertEqual(dong[0]["nhom"], "cho_dong_y")
		self.assertEqual(self._goi(self.ql_a, portal.portal_bao_gia_dem)["cho_dong_y"], 2)

	def test_nhom_dang_bao_gia_khi_khong_dot_nao_cho_khach(self):
		d1 = self._tach(self.item_ngoai)
		self._goi(self.ql_a, bao_gia.dong_y, d1)
		self.assertEqual(self._dong_cua_phieu()[0]["nhom"], "dang_bao_gia")

	def test_nhom_da_dong_khi_bao_het_va_khong_dot_nao_cho(self):
		d1 = self._tach(self.item_ngoai, self.item_boi_so, self.item_co_dau)
		self._goi(self.ql_a, bao_gia.dong_y, d1)
		self.assertEqual(self._dong_cua_phieu()[0]["nhom"], "da_dong")

	def test_dot_dang_bao_lai_thi_dang_bao_gia_du_phieu_da_bao_het(self):
		d1 = self._tach(self.item_ngoai, self.item_boi_so, self.item_co_dau)
		self.assertEqual(
			frappe.db.get_value("Quotation", self.goc.name, "workflow_state"), bao_gia.TT_DA_BAO_HET
		)
		ten_dong = frappe.get_doc("Quotation", d1).items[0].name
		self._goi(self.ql_a, portal.portal_bao_gia_sua_so_luong, d1, [{"name": ten_dong, "qty": 20}])
		self.assertEqual(self._dong_cua_phieu()[0]["nhom"], "dang_bao_gia")
		kq = self._goi(self.ql_a, portal.portal_bao_gia_chi_tiet, self.goc.name)
		self.assertEqual(kq["nhom"], "dang_bao_gia")

	def test_chi_tiet_co_dot_va_con_lai(self):
		d1 = self._tach(self.item_ngoai)
		kq = self._goi(self.ql_a, portal.portal_bao_gia_chi_tiet, self.goc.name)
		self.assertEqual(kq["bao_gia"], self.goc.name)
		self.assertEqual(kq["nhom"], "cho_dong_y")
		self.assertEqual([d["bao_gia"] for d in kq["dot"]], [d1])
		dot1 = kq["dot"][0]
		self.assertEqual(dot1["so_dot"], 1)
		self.assertTrue(dot1["hien_gia"])
		self.assertTrue(dot1["duoc_dong_y"])
		self.assertFalse(dot1["da_tra_ve"])
		self.assertEqual(dot1["items"][0]["rate"], 54000)
		self.assertEqual(
			sorted(d["item_code"] for d in kq["con_lai"]), sorted([self.item_boi_so, self.item_co_dau])
		)
		self.assertNotIn("rate", kq["con_lai"][0])
		self.assertTrue(kq["duoc_huy_con_lai"])

	def test_chi_tiet_phieu_chua_tach_nhu_cu(self):
		kq = self._goi(self.ql_a, portal.portal_bao_gia_chi_tiet, self.goc.name)
		self.assertEqual((kq["dot"], kq["con_lai"], kq["duoc_huy_con_lai"]), ([], [], False))
		self.assertEqual(kq["nhom"], "dang_bao_gia")

	def test_chi_tiet_theo_ten_dot_tra_phieu_goc(self):
		d1 = self._tach(self.item_ngoai)
		kq = self._goi(self.ql_a, portal.portal_bao_gia_chi_tiet, d1)
		self.assertEqual(kq["bao_gia"], self.goc.name)
		self.assertEqual([d["bao_gia"] for d in kq["dot"]], [d1])

	def test_sua_so_luong_tren_dot_roi_gui_lai(self):
		from frappe.model.workflow import apply_workflow

		d1 = self._tach(self.item_ngoai)
		ten_dong = frappe.get_doc("Quotation", d1).items[0].name
		kq = self._goi(
			self.ql_a, portal.portal_bao_gia_sua_so_luong, d1, [{"name": ten_dong, "qty": 20}]
		)
		self.assertEqual(kq["trang_thai_moi"], bao_gia.TT_CHO_MIYANO)
		# Đợt (không phải phiếu gốc) gửi lại được: chốt D7 chỉ áp cho phiếu gốc.
		d = apply_workflow(frappe.get_doc("Quotation", d1), bao_gia.HD_GUI_KHACH)
		self.assertEqual(d.workflow_state, bao_gia.TT_CHO_KHACH)
		self.assertEqual(d.items[0].qty, 20)

	def test_dong_y_tu_choi_theo_ten_dot(self):
		d1 = self._tach(self.item_ngoai)
		d2 = self._tach(self.item_boi_so)
		self.assertTrue(self._goi(self.ql_a, portal.portal_bao_gia_dong_y, d1)["sales_order"])
		self.assertEqual(
			self._goi(self.ql_a, portal.portal_bao_gia_tu_choi, d2)["trang_thai_moi"],
			bao_gia.TT_KHACH_TU_CHOI,
		)

	def test_khach_khac_khong_thay_dot(self):
		d1 = self._tach(self.item_ngoai)
		for ham, tham in (
			(portal.portal_bao_gia_chi_tiet, (d1,)),
			(portal.portal_bao_gia_dong_y, (d1,)),
			(portal.portal_bao_gia_huy_con_lai, (self.goc.name,)),
		):
			with self.assertRaisesRegex(frappe.PermissionError, LOI_KHONG_THAY):
				self._goi(self.ql_b, ham, *tham)

	def test_huy_con_lai_qua_cong(self):
		self._tach(self.item_ngoai)
		with patch("frappe.sendmail"):
			kq = self._goi(self.ql_a, portal.portal_bao_gia_huy_con_lai, self.goc.name, "Đủ hàng rồi")
		self.assertEqual(kq["trang_thai_moi"], bao_gia.TT_HUY_CON_LAI)
		ct = self._goi(self.ql_a, portal.portal_bao_gia_chi_tiet, self.goc.name)
		self.assertFalse(ct["duoc_huy_con_lai"])
		self.assertEqual(ct["con_lai"], [])

	def test_huy_con_lai_ly_do_khong_phai_chuoi(self):
		self._tach(self.item_ngoai)
		with self.assertRaises(frappe.ValidationError):
			self._goi(self.ql_a, portal.portal_bao_gia_huy_con_lai, self.goc.name, {"x": 1})

	def test_don_dot_hai_hien_o_tab_don_hang(self):
		d1 = self._tach(self.item_ngoai)
		so1 = self._goi(self.ql_a, bao_gia.dong_y, d1)["sales_order"]
		d2 = self._tach(self.item_boi_so)
		so2 = self._goi(self.ql_a, bao_gia.dong_y, d2)["sales_order"]
		rows = self._goi(self.ql_a, portal.portal_yeu_cau_cua_toi, limit=200)["rows"]
		don = {r["sales_order"] for r in rows}
		self.assertTrue({so1, so2} <= don)

	def test_danh_sach_khong_vo_khi_chua_co_cot(self):
		self._tach(self.item_ngoai)
		with patch.object(dot, "san_sang", return_value=False):
			rows = self._goi(self.ql_a, portal.portal_bao_gia_danh_sach)["rows"]
			self._goi(self.ql_a, portal.portal_bao_gia_dem)
			kq = self._goi(self.ql_a, portal.portal_bao_gia_chi_tiet, self.goc.name)
		self.assertTrue(rows)
		self.assertEqual(kq["dot"], [])

	def _khoa_khac_cua_a(self):
		ten = frappe.db.get_value(
			"Customer Department", {"customer": self.kh_a, "ma_khoa": "DOTCONG"}, "name"
		)
		return ten or frappe.get_doc({
			"doctype": "Customer Department", "customer": self.kh_a,
			"ten_khoa_phong": "Khoa thử báo giá theo đợt", "ma_khoa": "DOTCONG", "active": 1,
		}).insert(ignore_permissions=True).name

	def test_huy_con_lai_khong_con_hien_dong_go_tay(self):
		"""Sau «Huỷ phần còn lại» không còn gì "Miyano đang tìm mã"."""
		frappe.delete_doc("Quotation", self.goc.name, force=True)
		self.goc = self._goc_ba_dong(
			custom_de_xuat=self.phieu.name, khoa=self.khoa_huyethoc,
			custom_dat_ngoai=[{"ten_hang": "Kim lạ chưa có mã", "dvt": "Cái", "so_luong": 2}],
		)
		frappe.db.set_value("Portal De Xuat Mua", self.phieu.name, "bao_gia", self.goc.name)
		self._tach(self.item_ngoai)
		ct = self._goi(self.ql_a, portal.portal_bao_gia_chi_tiet, self.goc.name)
		self.assertEqual([d["ten_hang"] for d in ct["dat_ngoai"]], ["Kim lạ chưa có mã"])
		self.assertFalse(ct["da_huy_con_lai"])
		self.assertEqual(ct["ly_do_huy_con_lai"], "")
		with patch("frappe.sendmail"):
			self._goi(self.ql_a, portal.portal_bao_gia_huy_con_lai, self.goc.name, "Đủ hàng rồi")
		ct = self._goi(self.ql_a, portal.portal_bao_gia_chi_tiet, self.goc.name)
		self.assertEqual(ct["dat_ngoai"], [])
		self.assertTrue(ct["da_huy_con_lai"])
		self.assertEqual(ct["ly_do_huy_con_lai"], "Đủ hàng rồi")

	def test_ly_do_huy_chua_ap_dung_khong_ra_cong(self):
		"""Lý do nhân viên gõ dở (chưa chuyển trạng thái) không đi ra cổng."""
		self._tach(self.item_ngoai)
		frappe.db.set_value("Quotation", self.goc.name, "custom_ly_do_huy_con_lai", "Nội bộ gõ dở")
		ct = self._goi(self.ql_a, portal.portal_bao_gia_chi_tiet, self.goc.name)
		self.assertEqual(ct["ly_do_huy_con_lai"], "")

	def test_khoa_khac_khong_thay_dot(self):
		d1 = self._tach(self.item_ngoai)
		nv_khac = self._dam_bao_thanh_vien(
			"dotcong.khac@demo.miyano", self.kh_a, "Nhân viên khoa", self._khoa_khac_cua_a()
		)
		nv_cung = self._dam_bao_thanh_vien(
			"dotcong.cung@demo.miyano", self.kh_a, "Nhân viên khoa", self.khoa_huyethoc
		)
		# Đối chứng: cùng khoa thì thấy — lỗi dưới đây là do trục khoa.
		self.assertEqual(self._goi(nv_cung, portal.portal_bao_gia_chi_tiet, d1)["bao_gia"], self.goc.name)
		with self.assertRaisesRegex(frappe.PermissionError, LOI_KHONG_THAY):
			self._goi(nv_khac, portal.portal_bao_gia_chi_tiet, d1)

	def test_dot_lech_khoa_khong_tra_ve(self):
		d1 = self._tach(self.item_ngoai)
		d2 = self._tach(self.item_boi_so)
		frappe.db.set_value("Quotation", d2, "custom_khoa_phong", self._khoa_khac_cua_a())
		kq = self._goi(self.ql_a, portal.portal_bao_gia_chi_tiet, self.goc.name)
		self.assertEqual([d["bao_gia"] for d in kq["dot"]], [d1])
