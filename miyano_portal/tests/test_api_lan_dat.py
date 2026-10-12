"""API của hai phiếu cùng lần đặt (spec 2026-10-09 §7)."""

import frappe
from frappe.tests.utils import FrappeTestCase

from miyano_portal.api import de_xuat, portal
from miyano_portal.tests import test_tach_phieu as goc

DT = "Portal De Xuat Mua"


class TestApiLanDat(FrappeTestCase):
	_phieu_nhap = goc.TestTachPhieu._phieu_nhap

	def setUp(self):
		# FrappeTestCase chỉ rollback khi HẾT LỚP. `setUp` dọn dữ liệu cũ nên
		# làm lùi bộ đếm đặt tên (`revert_series_if_last`) trong khi đơn của
		# bài trước vẫn còn → bài sau trùng `request_id` ("đã được tạo trước
		# đó"). Mỗi bài tự rollback về savepoint để không bài nào thấy bài kia.
		frappe.db.savepoint("lan_dat_bai")
		goc.TestTachPhieu.setUp(self)

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.rollback(save_point="lan_dat_bai")

	def _hai_phieu(self):
		kq = de_xuat.de_xuat_gui_duyet(
			self._phieu_nhap([self.co_gia, self.chua_gia])
		)
		return kq["name"], kq["phieu_cung_lan_dat"]

	def _khoa_khac_cung_khach(self):
		"""Khoa thứ hai CÙNG `kh_a` (`khoa_duoc` của fixture thuộc `kh_b`)."""
		ten = frappe.db.get_value(
			"Customer Department", {"customer": self.kh_a, "ma_khoa": "LANDATKHAC"}
		)
		if ten:
			return ten
		return frappe.get_doc({
			"doctype": "Customer Department", "customer": self.kh_a,
			"ten_khoa_phong": "Khoa khác (test lần đặt)", "ma_khoa": "LANDATKHAC",
			"active": 1,
		}).insert(ignore_permissions=True).name

	def test_chi_tiet_tra_phieu_cung_lan_dat(self):
		a, b = self._hai_phieu()
		frappe.set_user(self.quan_ly)
		kq = de_xuat.de_xuat_chi_tiet(ten=a)
		self.assertTrue(kq["ma_lan_dat"])
		self.assertEqual(
			set(kq["phieu_cung_lan_dat"]), {"name", "ma_de_xuat", "trang_thai"}
		)
		self.assertEqual(kq["phieu_cung_lan_dat"]["name"], b)
		self.assertEqual(kq["phieu_cung_lan_dat"]["trang_thai"], "Chờ duyệt")

	def test_chi_tiet_phieu_don_le_tra_None(self):
		frappe.set_user(self.user_a)
		ten = de_xuat.de_xuat_gui_duyet(self._phieu_nhap([self.co_gia]))["name"]
		frappe.set_user(self.quan_ly)
		kq = de_xuat.de_xuat_chi_tiet(ten=ten)
		self.assertIsNone(kq["phieu_cung_lan_dat"])
		self.assertEqual(kq["ma_lan_dat"], "")

	def test_chi_tiet_khong_lo_phieu_kia_khi_khong_mo_duoc_no(self):
		a, b = self._hai_phieu()
		# Dữ liệu bất thường: phiếu kia nằm ở khoa khác. Người gọi mở được A
		# nhưng không mở được B, nên không được thấy mã/trạng thái của B.
		frappe.set_user("Administrator")
		frappe.db.set_value(DT, b, "khoa_phong", self._khoa_khac_cung_khach())
		frappe.set_user(self.user_a)
		kq = de_xuat.de_xuat_chi_tiet(ten=a)
		self.assertIsNone(kq["phieu_cung_lan_dat"])

	def test_nguoi_khoa_khac_va_khach_khac_khong_thay_phieu_kia(self):
		a, _b = self._hai_phieu()
		khoa_khac = self._dam_bao_thanh_vien(
			"tach.khoakhac@demo.miyano", self.kh_a, "Nhân viên khoa",
			self._khoa_khac_cung_khach(),
		)
		for nguoi in (khoa_khac, self.user_b):
			frappe.set_user(nguoi)
			with self.assertRaises(frappe.PermissionError):
				de_xuat.de_xuat_chi_tiet(ten=a)

	def test_chi_tiet_tra_canh_bao_gia_khi_gia_doi(self):
		a, _b = self._hai_phieu()
		self._tao_gia(self.co_gia, self.price_list, 60000)
		frappe.set_user(self.quan_ly)
		kq = de_xuat.de_xuat_chi_tiet(ten=a)
		self.assertEqual(kq["canh_bao_gia"], [{
			"item_code": self.co_gia, "gia_cu": 54000.0, "gia_moi": 60000.0,
			"ly_do": "gia_doi",
		}])

	def test_chi_tiet_canh_bao_mat_gia_khong_nem_loi(self):
		a, _b = self._hai_phieu()
		frappe.set_user("Administrator")
		for ten in frappe.get_all(
			"Item Price", filters={"item_code": self.co_gia, "selling": 1}, pluck="name"
		):
			frappe.delete_doc("Item Price", ten, force=True)
		frappe.set_user(self.quan_ly)
		kq = de_xuat.de_xuat_chi_tiet(ten=a)
		self.assertEqual(len(kq["canh_bao_gia"]), 1)
		self.assertEqual(kq["canh_bao_gia"][0]["ly_do"], "mat_gia")
		self.assertIn(self.co_gia, kq["canh_bao_gia"][0]["thong_diep"])
		self.assertNotIn("<", kq["canh_bao_gia"][0]["thong_diep"])

	def test_chi_tiet_phieu_khong_cho_duyet_khong_canh_bao(self):
		a, _b = self._hai_phieu()
		frappe.set_user(self.quan_ly)
		de_xuat.de_xuat_duyet_phieu(a)
		self.assertEqual(de_xuat.de_xuat_chi_tiet(ten=a)["canh_bao_gia"], [])

	def test_duyet_ca_hai(self):
		a, b = self._hai_phieu()
		frappe.set_user(self.quan_ly)
		kq = de_xuat.de_xuat_duyet_phieu(a, duyet_ca_hai=1)
		self.assertTrue(kq["sales_order"])
		self.assertTrue(kq["phieu_cung_lan_dat"]["sales_order"])
		frappe.set_user("Administrator")
		for ten in (a, b):
			self.assertEqual(frappe.db.get_value(DT, ten, "trang_thai"), "Đã duyệt")

	def _khong_dong_gi_cho_phieu_dau(self, a, b, so_don_truoc):
		"""KHÔNG rollback ở test: phiếu đầu phải còn nguyên vì production
		chưa hề ghi gì cho nó."""
		frappe.set_user("Administrator")
		self.assertEqual(frappe.db.get_value(DT, a, "trang_thai"), "Chờ duyệt")
		self.assertFalse(frappe.db.get_value(DT, a, "sales_order"))
		self.assertEqual(
			frappe.db.count("Sales Order", {"customer": self.kh_a}), so_don_truoc
		)
		self.assertEqual(frappe.db.get_value(DT, b, "trang_thai"), "Chờ duyệt")

	def test_duyet_ca_hai_phieu_kia_mat_gia_thi_chua_ghi_gi_cho_phieu_dau(self):
		a, b = self._hai_phieu()
		# Phiếu kia (chờ báo giá) bị đóng dấu "Bảng giá" cho một mã không có giá
		# → `_kiem_gia_doi` chặn việc duyệt nó.
		frappe.set_user("Administrator")
		ten_dong = frappe.get_doc(DT, b).items[0].name
		frappe.db.set_value(
			"Portal De Xuat Mua Item", ten_dong, {"nguon_gia": "Bảng giá", "don_gia": 1000}
		)
		so_don = frappe.db.count("Sales Order", {"customer": self.kh_a})
		frappe.set_user(self.quan_ly)
		with self.assertRaises(frappe.ValidationError):
			de_xuat.de_xuat_duyet_phieu(a, duyet_ca_hai=1)
		self._khong_dong_gi_cho_phieu_dau(a, b, so_don)

	def test_duyet_ca_hai_khong_quyen_phieu_kia_thi_chua_ghi_gi_cho_phieu_dau(self):
		a, b = self._hai_phieu()
		# Quản lý không gắn khoa (luật Portal Member) nên "không quyền" được
		# dựng bằng phiếu kia thuộc khách khác: `_phieu_cua_toi` chặn đúng như
		# khi duyệt thẳng phiếu đó.
		frappe.set_user("Administrator")
		frappe.db.set_value(DT, b, "customer", self.kh_b)
		so_don = frappe.db.count("Sales Order", {"customer": self.kh_a})
		frappe.set_user(self.quan_ly)
		with self.assertRaises(frappe.PermissionError):
			de_xuat.de_xuat_duyet_phieu(b)  # cùng lỗi khi duyệt thẳng phiếu kia
		with self.assertRaises(frappe.PermissionError):
			de_xuat.de_xuat_duyet_phieu(a, duyet_ca_hai=1)
		self._khong_dong_gi_cho_phieu_dau(a, b, so_don)

	def test_loi_sau_khi_duyet_phieu_dau_duoc_nem_ra_khoi_endpoint(self):
		"""Chứng minh LAN TRUYỀN lỗi (không nuốt) — việc rollback là của
		Frappe khi ngoại lệ thoát khỏi request, không được test ở đây."""
		from unittest import mock

		from miyano_portal import de_xuat_duyet

		a, _b = self._hai_phieu()
		goc_ham = de_xuat_duyet.duyet_va_tao_don
		so_lan = []

		def ham(*args, **kwargs):
			so_lan.append(args[0])
			if len(so_lan) == 2:
				raise frappe.ValidationError("lỗi lần duyệt thứ hai")
			return goc_ham(*args, **kwargs)

		frappe.set_user(self.quan_ly)
		with mock.patch.object(de_xuat_duyet, "duyet_va_tao_don", ham):
			with self.assertRaises(frappe.ValidationError):
				de_xuat.de_xuat_duyet_phieu(a, duyet_ca_hai=1)
		self.assertEqual(len(so_lan), 2)

	def test_duyet_ca_hai_dieu_chinh_chi_ap_cho_phieu_dau(self):
		a, b = self._hai_phieu()
		frappe.set_user("Administrator")
		doc_b = frappe.get_doc(DT, b)
		sl_b = float(doc_b.items[0].so_luong_duyet or 0)
		self.assertTrue(sl_b)
		frappe.set_user(self.quan_ly)
		kq = de_xuat.de_xuat_duyet_phieu(
			a, duyet_ca_hai=1,
			dieu_chinh={"items": [{"item_code": self.co_gia, "so_luong_duyet": 4}]},
		)
		frappe.set_user("Administrator")
		dong_a = frappe.get_all(
			"Sales Order Item", filters={"parent": kq["sales_order"]},
			fields=["item_code", "qty"],
		)
		self.assertEqual({d.item_code: float(d.qty) for d in dong_a}, {self.co_gia: 4.0})
		dong_b = frappe.get_all(
			"Sales Order Item", filters={"parent": kq["phieu_cung_lan_dat"]["sales_order"]},
			fields=["item_code", "qty"],
		)
		self.assertEqual({d.item_code: float(d.qty) for d in dong_b}, {self.chua_gia: sl_b})
		self.assertEqual(
			float(frappe.get_doc(DT, b).items[0].so_luong_duyet), sl_b
		)

	def test_duyet_mot_phieu_khong_dung_phieu_kia(self):
		a, b = self._hai_phieu()
		frappe.set_user(self.quan_ly)
		kq = de_xuat.de_xuat_duyet_phieu(a)
		self.assertIsNone(kq["phieu_cung_lan_dat"])
		frappe.set_user("Administrator")
		self.assertEqual(frappe.db.get_value(DT, b, "trang_thai"), "Chờ duyệt")

	def test_danh_sach_phieu_mang_ma_lan_dat(self):
		a, b = self._hai_phieu()
		frappe.set_user(self.user_a)
		le = de_xuat.de_xuat_gui_duyet(self._phieu_nhap([self.co_gia]))["name"]
		frappe.set_user(self.quan_ly)
		theo_ten = {r["name"]: r for r in de_xuat.de_xuat_danh_sach()}
		self.assertTrue(theo_ten[a]["ma_lan_dat"])
		self.assertEqual(theo_ten[a]["ma_lan_dat"], theo_ten[b]["ma_lan_dat"])
		self.assertFalse(theo_ten[le]["ma_lan_dat"])

	def test_danh_sach_yeu_cau_mang_ma_lan_dat(self):
		a, b = self._hai_phieu()
		frappe.set_user(self.user_a)
		le = de_xuat.de_xuat_gui_duyet(self._phieu_nhap([self.co_gia]))["name"]
		frappe.set_user(self.quan_ly)
		rows = portal.portal_yeu_cau_cua_toi(limit=100)["rows"]
		theo_phieu = {r["de_xuat"]: r for r in rows}
		self.assertTrue(theo_phieu[a]["ma_lan_dat"])
		self.assertEqual(theo_phieu[a]["ma_lan_dat"], theo_phieu[b]["ma_lan_dat"])
		self.assertEqual(theo_phieu[le]["ma_lan_dat"], "")
		self.assertTrue(all("ma_lan_dat" in r for r in rows))


for _ten, _ham in vars(goc.TestTachPhieu).items():
	if _ten.startswith("_") and not _ten.startswith("__") and callable(_ham):
		if _ten not in vars(TestApiLanDat):
			setattr(TestApiLanDat, _ten, _ham)
