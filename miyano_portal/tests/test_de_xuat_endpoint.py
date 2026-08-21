"""Endpoint cổng cho `Portal De Xuat Mua` (Task 5, spec §5).

Vì role `Customer` có ZERO DocPerm trên doctype này (đã kiểm `tabDocPerm`
19/08 — xem docstring `api/de_xuat.py` và `test_de_xuat_cach_ly.py`),
`frappe.get_list`/`doc.check_permission()` ném `PermissionError` cho MỌI
Website User trước khi hook `has_permission`/`permission_query_conditions`
(Task 4) kịp chạy. Đường sống của cổng là TẦNG ENDPOINT ở `api/de_xuat.py`
— test ở đây vì thế gọi THẲNG các hàm whitelist đó (không qua
`frappe.get_list`), đủ cả vế âm lẫn vế dương cho cả trục KHÁCH HÀNG lẫn trục
KHOA PHÒNG, cộng thêm vế khoa còn thiếu của `permissions.de_xuat_item_query`
(mang sang từ Task 4, review phát hiện).
"""

import frappe
from frappe.tests.utils import FrappeTestCase

from miyano_portal import permissions
from miyano_portal.api import de_xuat
from miyano_portal.miyano_portal.doctype.portal_de_xuat_mua.portal_de_xuat_mua import (
	TRANG_THAI_NHAP,
)
from miyano_portal.tests.fixtures_de_xuat import dung_fixture


class TestDeXuatEndpoint(FrappeTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		# Bẫy đã biết (Task 3/4): `on_trash` chặn xoá phiếu đã gửi duyệt.
		# Hạ mọi phiếu cũ của bộ fixture về Nháp TRƯỚC khi gọi `dung_fixture`
		# (nó dùng `delete_doc(force=True)`, chỉ thành công khi phiếu Nháp).
		frappe.db.sql(
			"""UPDATE `tabPortal De Xuat Mua` SET trang_thai = %s
			   WHERE customer LIKE '\\_TEST DX%%'""",
			TRANG_THAI_NHAP,
		)
		f = dung_fixture(self)
		self.kh_a, self.kh_b = f.kh_a, f.kh_b
		self.item = f.item
		self.khoa_huyethoc = f.khoa_huyethoc  # dưới kh_a

		# Khoa thứ hai CÙNG kh_a — cô lập đúng trục khoa, không lẫn trục
		# khách hàng (cùng lý do `test_de_xuat_cach_ly.py` đã ghi).
		self.khoa_duoc = self._dam_bao_khoa(
			self.kh_a, "Dược (nội bộ, test endpoint)", "DXENDDUOC"
		)

		self.user_quan_ly = self._dam_bao_thanh_vien(
			"dxendpoint.ql@demo.miyano", self.kh_a, "Quản lý", None
		)
		self.user_huyethoc = self._dam_bao_thanh_vien(
			"dxendpoint.huyethoc@demo.miyano", self.kh_a, "Nhân viên khoa",
			self.khoa_huyethoc,
		)
		# Đồng nghiệp THỨ HAI cùng khoa Huyết học — chốt "cùng khoa nhưng
		# không phải chủ phiếu".
		self.user_huyethoc2 = self._dam_bao_thanh_vien(
			"dxendpoint.huyethoc2@demo.miyano", self.kh_a, "Nhân viên khoa",
			self.khoa_huyethoc,
		)
		self.user_duoc = self._dam_bao_thanh_vien(
			"dxendpoint.duoc@demo.miyano", self.kh_a, "Nhân viên khoa",
			self.khoa_duoc,
		)
		# Nhân viên của MỘT BỆNH VIỆN KHÁC (kh_b) — chốt trục khách hàng.
		self.user_benh_vien_b = self._dam_bao_thanh_vien(
			"dxendpoint.benhvienb@demo.miyano", self.kh_b, "Nhân viên khoa",
			f.khoa_duoc,
		)

		self.phieu_huyethoc = self._tao_phieu(
			self.kh_a, self.khoa_huyethoc, owner=self.user_huyethoc
		)
		self.phieu_duoc = self._tao_phieu(
			self.kh_a, self.khoa_duoc, owner=self.user_duoc
		)
		self.phieu_benh_vien_b = self._tao_phieu(
			self.kh_b, f.khoa_duoc, owner=self.user_benh_vien_b
		)

		# Task 10 — mặt hàng RIÊNG của file này có khai bội số. CỐ Ý không
		# gắn `custom_boi_so_dat` lên `_TEST DX ITEM` (fixture DÙNG CHUNG cho
		# nhiều file test): đặt bội số lên nó sẽ làm mọi bài đang đặt 1 đơn
		# vị của mã đó vướng `kiem_boi_so()` ở một file khác hẳn.
		self.item_boi_so = self._dam_bao_item_boi_so("_TEST DX ITEM LOC 10", 10)
		self.phieu_boi_so = self._tao_phieu(
			self.kh_a, self.khoa_huyethoc, owner=self.user_huyethoc,
			item_code=self.item_boi_so,
		)

		# Tên riêng khớp Step 1 của brief (đọc dễ hơn `self.phieu_huyethoc`
		# khi nói về "phiếu của tôi"/"phiếu của người khác").
		self.phieu_nhap_cua_toi = self.phieu_huyethoc
		self.phieu_nhap_cua_nguoi_khac = self.phieu_huyethoc

	def tearDown(self):
		frappe.set_user("Administrator")

	# -- fixture riêng của file này ------------------------------------------

	def _dam_bao_khoa(self, customer, ten, ma):
		ten_bp = frappe.db.get_value(
			"Customer Department", {"customer": customer, "ma_khoa": ma}, "name"
		)
		if ten_bp:
			return ten_bp
		return frappe.get_doc({
			"doctype": "Customer Department", "customer": customer,
			"ten_khoa_phong": ten, "ma_khoa": ma, "active": 1,
		}).insert(ignore_permissions=True).name

	def _dam_bao_thanh_vien(self, email, customer, vai_tro, khoa_phong):
		if not frappe.db.exists("User", email):
			u = frappe.get_doc({
				"doctype": "User", "email": email,
				"first_name": email.split("@")[0],
				"user_type": "Website User", "send_welcome_email": 0,
			})
			u.append("roles", {"role": "Customer"})
			u.insert(ignore_permissions=True)
		ten_tv = frappe.db.get_value("Portal Member", {"user": email}, "name")
		gia_tri = {
			"customer": customer, "vai_tro": vai_tro,
			"khoa_phong": khoa_phong, "active": 1,
		}
		if ten_tv:
			frappe.db.set_value("Portal Member", ten_tv, gia_tri)
		else:
			frappe.get_doc({
				"doctype": "Portal Member", "user": email, **gia_tri,
			}).insert(ignore_permissions=True)
		return email

	def _dam_bao_item_boi_so(self, ten, boi_so):
		if not frappe.db.exists("Item", ten):
			frappe.get_doc({
				"doctype": "Item", "item_code": ten, "item_name": ten,
				"item_group": frappe.db.get_value("Item Group", {}, "name"),
				"stock_uom": "Nos", "is_stock_item": 0,
			}).insert(ignore_permissions=True)
		frappe.db.set_value("Item", ten, "custom_boi_so_dat", boi_so)
		return ten

	def _tao_phieu(self, customer, khoa_phong, owner, so_luong=1, item_code=None):
		doc = frappe.get_doc({
			"doctype": "Portal De Xuat Mua",
			"customer": customer, "khoa_phong": khoa_phong,
			"items": [{
				"item_code": item_code or self.item, "so_luong_de_xuat": so_luong,
			}],
		})
		doc.insert(ignore_permissions=True)
		frappe.db.set_value("Portal De Xuat Mua", doc.name, "owner", owner)
		return doc.name

	# -- de_xuat_tao_nhap -----------------------------------------------------

	def test_nhan_vien_tao_phieu_thi_khoa_lay_tu_PHIEN(self):
		"""Không nhận khoa từ client — nhân viên khoa Huyết học không lập
		được phiếu mang tên khoa Dược kể cả khi sửa payload."""
		frappe.set_user(self.user_huyethoc)
		ten = de_xuat.de_xuat_tao_nhap(khoa_phong=self.khoa_duoc)["name"]
		doc = frappe.get_doc("Portal De Xuat Mua", ten)
		self.assertEqual(doc.khoa_phong, self.khoa_huyethoc)
		# Cùng luật với khoa: customer cũng suy từ phiên, không nhận từ
		# client — đóng dấu đúng khách hàng của người gọi.
		self.assertEqual(doc.customer, self.kh_a)
		self.assertEqual(doc.trang_thai, TRANG_THAI_NHAP)

	def test_khach_khong_tao_phieu_mang_ten_khach_khac_du_sua_payload(self):
		"""Cùng luật C1 ở trục KHÁCH HÀNG — client không tự đóng dấu
		`customer` được, dù `de_xuat_tao_nhap` không có tham số đó trong chữ
		ký (rơi vào `**_bo_qua` nếu cố gửi)."""
		frappe.set_user(self.user_huyethoc)
		ten = de_xuat.de_xuat_tao_nhap(customer=self.kh_b)["name"]
		doc = frappe.get_doc("Portal De Xuat Mua", ten)
		self.assertEqual(doc.customer, self.kh_a)

	def test_quan_ly_tao_phieu_toan_vien_khong_gan_khoa(self):
		"""VẾ DƯƠNG — quản lý (`khoa_phong` rỗng trên `Portal Member`) tạo
		phiếu cấp bệnh viện (§5.5), không phải một điều kiện lỗi."""
		frappe.set_user(self.user_quan_ly)
		ten = de_xuat.de_xuat_tao_nhap()["name"]
		doc = frappe.get_doc("Portal De Xuat Mua", ten)
		self.assertFalse(doc.khoa_phong)
		self.assertEqual(doc.customer, self.kh_a)

	# -- de_xuat_luu_nhap -------------------------------------------------------

	def test_chinh_chu_luu_duoc_phieu_nhap_cua_minh(self):
		"""VẾ DƯƠNG."""
		frappe.set_user(self.user_huyethoc)
		de_xuat.de_xuat_luu_nhap(self.phieu_huyethoc, ghi_chu="cap nhat")
		doc = frappe.get_doc("Portal De Xuat Mua", self.phieu_huyethoc)
		self.assertEqual(doc.ghi_chu, "cap nhat")

	def test_nguoi_khac_khong_luu_duoc_phieu_nhap_cua_nguoi_khac(self):
		frappe.set_user(self.user_huyethoc2)
		with self.assertRaises(frappe.PermissionError):
			de_xuat.de_xuat_luu_nhap(self.phieu_huyethoc, ghi_chu="hack")

	def test_khoa_khac_khong_luu_duoc_phieu_khoa_khac(self):
		"""Chốt trục KHOA — chặn ở vòng kiểm phạm vi khoa, TRƯỚC vòng kiểm
		chủ sở hữu."""
		frappe.set_user(self.user_duoc)
		with self.assertRaises(frappe.PermissionError) as ctx:
			de_xuat.de_xuat_luu_nhap(self.phieu_huyethoc, ghi_chu="hack")
		self.assertIn("khoa", str(ctx.exception))

	def test_quan_ly_luu_duoc_phieu_cua_nhan_vien(self):
		"""VẾ DƯƠNG — quản lý sửa được phiếu Nháp của nhân viên trong bệnh
		viện mình."""
		frappe.set_user(self.user_quan_ly)
		de_xuat.de_xuat_luu_nhap(self.phieu_huyethoc, ghi_chu="quan ly sua")
		doc = frappe.get_doc("Portal De Xuat Mua", self.phieu_huyethoc)
		self.assertEqual(doc.ghi_chu, "quan ly sua")

	def test_khong_luu_duoc_phieu_da_gui_duyet(self):
		frappe.set_user(self.user_huyethoc)
		de_xuat.de_xuat_luu_nhap(self.phieu_huyethoc, ly_do_yeu_cau="can gap")
		de_xuat.de_xuat_gui_duyet(self.phieu_huyethoc)
		with self.assertRaises(frappe.ValidationError) as ctx:
			de_xuat.de_xuat_luu_nhap(self.phieu_huyethoc, ghi_chu="sua tiep")
		self.assertIn("Nháp", str(ctx.exception))

	# -- de_xuat_xoa_nhap -------------------------------------------------------

	def test_nhan_vien_khong_xoa_duoc_phieu_nhap_cua_nguoi_khac(self):
		frappe.set_user(self.user_huyethoc2)
		with self.assertRaises(frappe.PermissionError):
			de_xuat.de_xuat_xoa_nhap(self.phieu_nhap_cua_nguoi_khac)

	def test_chinh_chu_xoa_duoc_phieu_nhap_cua_minh(self):
		"""VẾ DƯƠNG."""
		frappe.set_user(self.user_huyethoc)
		de_xuat.de_xuat_xoa_nhap(self.phieu_nhap_cua_toi)
		self.assertFalse(
			frappe.db.exists("Portal De Xuat Mua", self.phieu_nhap_cua_toi)
		)

	def test_quan_ly_xoa_duoc_phieu_nhap_cua_nhan_vien(self):
		"""VẾ DƯƠNG của §5.4b — "owner HOẶC quản lý"."""
		frappe.set_user(self.user_quan_ly)
		de_xuat.de_xuat_xoa_nhap(self.phieu_huyethoc)
		self.assertFalse(
			frappe.db.exists("Portal De Xuat Mua", self.phieu_huyethoc)
		)

	def test_khoa_khac_khong_xoa_duoc_phieu_khoa_khac(self):
		frappe.set_user(self.user_duoc)
		with self.assertRaises(frappe.PermissionError) as ctx:
			de_xuat.de_xuat_xoa_nhap(self.phieu_huyethoc)
		self.assertIn("khoa", str(ctx.exception))

	def test_chinh_chu_khong_xoa_duoc_phieu_da_gui_duyet(self):
		"""`on_trash` là chốt cuối — endpoint không tự nới nó."""
		frappe.set_user(self.user_huyethoc)
		de_xuat.de_xuat_luu_nhap(self.phieu_huyethoc, ly_do_yeu_cau="can gap")
		de_xuat.de_xuat_gui_duyet(self.phieu_huyethoc)
		with self.assertRaises(frappe.ValidationError) as ctx:
			de_xuat.de_xuat_xoa_nhap(self.phieu_huyethoc)
		self.assertIn("không xoá được", str(ctx.exception))

	# -- de_xuat_gui_duyet --------------------------------------------------

	def test_chinh_chu_gui_duyet_thanh_cong(self):
		"""VẾ DƯƠNG."""
		frappe.set_user(self.user_huyethoc)
		de_xuat.de_xuat_luu_nhap(self.phieu_huyethoc, ly_do_yeu_cau="can gap")
		ket_qua = de_xuat.de_xuat_gui_duyet(self.phieu_huyethoc)
		self.assertTrue(ket_qua["ma_de_xuat"])
		doc = frappe.get_doc("Portal De Xuat Mua", self.phieu_huyethoc)
		self.assertEqual(doc.trang_thai, "Chờ duyệt")

	def test_nguoi_khac_khong_gui_duyet_duoc_phieu_nguoi_khac(self):
		frappe.set_user(self.user_huyethoc2)
		with self.assertRaises(frappe.PermissionError):
			de_xuat.de_xuat_gui_duyet(self.phieu_huyethoc)

	def test_khoa_khac_khong_gui_duyet_duoc_phieu_khoa_khac(self):
		frappe.set_user(self.user_duoc)
		with self.assertRaises(frappe.PermissionError) as ctx:
			de_xuat.de_xuat_gui_duyet(self.phieu_huyethoc)
		self.assertIn("khoa", str(ctx.exception))

	def test_quan_ly_khong_tu_gui_duyet_ho_phieu_cua_nhan_vien(self):
		"""Chốt phân quyền riêng của `de_xuat_gui_duyet` — CHỈ owner, khác
		`de_xuat_xoa_nhap`/`de_xuat_luu_nhap` (owner HOẶC quản lý). Quản lý
		vẫn là người DUYỆT phiếu (`doc.duyet()`, Task 6/9) chứ không tự GỬI
		hộ phiếu người khác — `_phieu_cua_toi()` một mình sẽ cho quản lý đi
		qua (vì nó cũng chấp nhận quản lý), nên endpoint phải tự thêm một
		chốt owner-only riêng."""
		frappe.set_user(self.user_huyethoc)
		de_xuat.de_xuat_luu_nhap(self.phieu_huyethoc, ly_do_yeu_cau="can gap")
		frappe.set_user(self.user_quan_ly)
		with self.assertRaises(frappe.PermissionError) as ctx:
			de_xuat.de_xuat_gui_duyet(self.phieu_huyethoc)
		self.assertIn("chủ", str(ctx.exception).lower())

	# -- de_xuat_danh_sach ----------------------------------------------------

	def test_danh_sach_chi_tra_phieu_trong_pham_vi(self):
		frappe.set_user(self.user_huyethoc)
		ten = [r["name"] for r in de_xuat.de_xuat_danh_sach()]
		self.assertIn(self.phieu_huyethoc, ten)      # vế dương
		self.assertNotIn(self.phieu_duoc, ten)       # vế âm

	def test_danh_sach_khong_thay_phieu_benh_vien_khac(self):
		"""Trục KHÁCH HÀNG — quản lý kh_a không thấy phiếu của kh_b dù cùng
		gọi `de_xuat_danh_sach` không giới hạn khoa."""
		frappe.set_user(self.user_quan_ly)
		ten = [r["name"] for r in de_xuat.de_xuat_danh_sach()]
		self.assertNotIn(self.phieu_benh_vien_b, ten)

	def test_quan_ly_thay_ca_hai_khoa(self):
		"""VẾ DƯƠNG của quản lý — nhìn xuyên mọi khoa TRONG bệnh viện mình."""
		frappe.set_user(self.user_quan_ly)
		ten = [r["name"] for r in de_xuat.de_xuat_danh_sach()]
		self.assertIn(self.phieu_huyethoc, ten)
		self.assertIn(self.phieu_duoc, ten)

	def test_danh_sach_loc_theo_trang_thai(self):
		frappe.set_user(self.user_quan_ly)
		ten = [
			r["name"] for r in de_xuat.de_xuat_danh_sach(trang_thai=TRANG_THAI_NHAP)
		]
		self.assertIn(self.phieu_huyethoc, ten)

	# -- de_xuat_chi_tiet -------------------------------------------------------

	def test_chinh_chu_xem_duoc_chi_tiet_phieu_cua_minh(self):
		"""VẾ DƯƠNG."""
		frappe.set_user(self.user_huyethoc)
		ket_qua = de_xuat.de_xuat_chi_tiet(self.phieu_huyethoc)
		self.assertEqual(ket_qua["name"], self.phieu_huyethoc)

	def test_dong_nghiep_cung_khoa_xem_duoc_chi_tiet_phieu_nguoi_khac(self):
		"""VẾ DƯƠNG khác — `cho_quan_ly=True` nghĩa là BỎ kiểm chủ sở hữu
		(không phải "chỉ quản lý"): một đồng nghiệp CÙNG khoa xem được chi
		tiết phiếu không phải do mình tạo."""
		frappe.set_user(self.user_huyethoc2)
		ket_qua = de_xuat.de_xuat_chi_tiet(self.phieu_huyethoc)
		self.assertEqual(ket_qua["name"], self.phieu_huyethoc)

	def test_khoa_khac_khong_xem_duoc_chi_tiet(self):
		frappe.set_user(self.user_duoc)
		with self.assertRaises(frappe.PermissionError) as ctx:
			de_xuat.de_xuat_chi_tiet(self.phieu_huyethoc)
		self.assertIn("khoa", str(ctx.exception))

	def test_benh_vien_khac_khong_xem_duoc_chi_tiet(self):
		"""Trục KHÁCH HÀNG — thông báo không tiết lộ sự tồn tại của phiếu
		thuộc bệnh viện khác."""
		frappe.set_user(self.user_benh_vien_b)
		with self.assertRaises(frappe.PermissionError) as ctx:
			de_xuat.de_xuat_chi_tiet(self.phieu_huyethoc)
		self.assertIn("không thuộc", str(ctx.exception))

	# ---- M1 (review tổng) — sentinel -1 KHÔNG được lọt ra ngoài ---------
	#
	# `so_luong_xin_sua` mặc định `-1` là quy ước NỘI BỘ ("chưa có yêu cầu
	# xin sửa"). `de_xuat_chi_tiet` trả `doc.as_dict()` thô nên đẩy thẳng
	# `-1` ra API, và field còn `in_list_view: 1` không `hidden` nên nhân sự
	# Miyano mở phiếu trên Desk thấy "SL xin sửa: -1" ở MỌI dòng.

	def test_chi_tiet_khong_lo_sentinel_am_ra_ngoai(self):
		frappe.set_user(self.user_huyethoc)
		ket_qua = de_xuat.de_xuat_chi_tiet(self.phieu_huyethoc)
		for row in ket_qua["items"]:
			self.assertIsNone(row.get("so_luong_xin_sua"))

	def test_chi_tiet_VAN_tra_so_xin_sua_that(self):
		"""VẾ DƯƠNG — dọn sentinel không được nuốt luôn yêu cầu THẬT
		(kể cả `0`, nghĩa "xin bỏ dòng này")."""
		frappe.db.sql(
			"""UPDATE `tabPortal De Xuat Mua Item` SET so_luong_xin_sua = 0
			   WHERE parent = %s""",
			self.phieu_huyethoc,
		)
		frappe.set_user(self.user_huyethoc)
		ket_qua = de_xuat.de_xuat_chi_tiet(self.phieu_huyethoc)
		for row in ket_qua["items"]:
			self.assertEqual(row.get("so_luong_xin_sua"), 0)

	# ---- Task 10 — `boi_so` phải đi CÙNG dòng phiếu, không chỉ đi cùng
	# kết quả tìm kiếm.
	#
	# Màn Đặt hàng chặn bội số ngay tại ô số lượng (`portal_catalog_gop` trả
	# `boi_so` cho dòng vừa tìm). Nhưng một phiếu Nháp MỞ LẠI để sửa tiếp
	# không đi qua ô tìm kiếm nữa — nó nạp dòng từ đây. Thiếu `boi_so` ở
	# đường này, đúng cái lỗi "7 hộp của lốc 10" lại nổ vào mặt QUẢN LÝ lúc
	# duyệt, cho một con số quản lý không hề chọn.

	def test_chi_tiet_tra_boi_so_cua_tung_dong(self):
		"""VẾ DƯƠNG — mặt hàng khai `custom_boi_so_dat = 10` phải ra `10`."""
		frappe.set_user(self.user_huyethoc)
		ket_qua = de_xuat.de_xuat_chi_tiet(self.phieu_boi_so)
		dong = [r for r in ket_qua["items"] if r["item_code"] == self.item_boi_so]
		self.assertEqual(len(dong), 1)
		self.assertEqual(dong[0]["boi_so"], 10)

	def test_chi_tiet_tra_boi_so_none_khi_khong_khai(self):
		"""`None`, KHÔNG phải `0` hay `1` — cùng quy ước `portal_catalog_gop`
		("không ràng buộc bội số"). `0` sẽ đọc thành "bội số bằng 0" và `1`
		là một ràng buộc THẬT mà mặt hàng này không có."""
		frappe.set_user(self.user_huyethoc)
		ket_qua = de_xuat.de_xuat_chi_tiet(self.phieu_huyethoc)
		for row in ket_qua["items"]:
			self.assertIsNone(row["boi_so"])

	def test_field_so_luong_xin_sua_an_tren_desk(self):
		"""Chốt cấu hình — đọc THẲNG file JSON của doctype (nguồn sự thật),
		không qua `frappe.get_meta` (đọc DB, chỉ đúng sau `bench migrate`)."""
		import json as _json
		import os

		import miyano_portal

		duong_dan = os.path.join(
			os.path.dirname(miyano_portal.__file__),
			"miyano_portal", "doctype", "portal_de_xuat_mua_item",
			"portal_de_xuat_mua_item.json",
		)
		with open(duong_dan, encoding="utf-8") as f:
			meta = _json.load(f)
		field = next(
			d for d in meta["fields"] if d["fieldname"] == "so_luong_xin_sua"
		)
		self.assertEqual(field.get("hidden"), 1)
		self.assertFalse(field.get("in_list_view"))


class TestDeXuatItemQueryVeKhoa(FrappeTestCase):
	"""`permissions.de_xuat_item_query` — vế khoa còn thiếu (mang sang từ
	Task 4, review phát hiện). Bảng con `Portal De Xuat Mua Item` trước bản
	vá chỉ lọc theo `customer` — một nhân viên khoa Huyết học gọi thẳng hook
	này (kênh `frappe.client.*`/reportview) vẫn thấy dòng hàng của khoa Dược
	cùng bệnh viện. Test THẲNG hàm hook (cùng khuôn `test_de_xuat_cach_ly.py`
	— kênh `frappe.get_list` chết trên doctype cha, và bảng con cũng không
	thoát nổi NG-37/NG-37b, xem `test_kho_isolation.py`), không qua endpoint.
	"""

	def setUp(self):
		frappe.set_user("Administrator")
		frappe.db.sql(
			"""UPDATE `tabPortal De Xuat Mua` SET trang_thai = %s
			   WHERE customer LIKE '\\_TEST DX%%'""",
			TRANG_THAI_NHAP,
		)
		f = dung_fixture(self)
		self.kh_a = f.kh_a
		self.item = f.item
		self.khoa_huyethoc = f.khoa_huyethoc
		self.khoa_duoc = self._dam_bao_khoa(
			self.kh_a, "Dược (nội bộ, test item query)", "DXIQDUOC"
		)

		self.user_huyethoc = self._dam_bao_thanh_vien(
			"dxitemquery.huyethoc@demo.miyano", self.kh_a, "Nhân viên khoa",
			self.khoa_huyethoc,
		)

		self.phieu_huyethoc = self._tao_phieu(self.khoa_huyethoc)
		self.phieu_duoc = self._tao_phieu(self.khoa_duoc)
		self.dong_huyethoc = frappe.get_all(
			"Portal De Xuat Mua Item", filters={"parent": self.phieu_huyethoc},
			pluck="name",
		)
		self.dong_duoc = frappe.get_all(
			"Portal De Xuat Mua Item", filters={"parent": self.phieu_duoc},
			pluck="name",
		)

	def tearDown(self):
		frappe.set_user("Administrator")

	def _dam_bao_khoa(self, customer, ten, ma):
		ten_bp = frappe.db.get_value(
			"Customer Department", {"customer": customer, "ma_khoa": ma}, "name"
		)
		if ten_bp:
			return ten_bp
		return frappe.get_doc({
			"doctype": "Customer Department", "customer": customer,
			"ten_khoa_phong": ten, "ma_khoa": ma, "active": 1,
		}).insert(ignore_permissions=True).name

	def _dam_bao_thanh_vien(self, email, customer, vai_tro, khoa_phong):
		if not frappe.db.exists("User", email):
			u = frappe.get_doc({
				"doctype": "User", "email": email,
				"first_name": email.split("@")[0],
				"user_type": "Website User", "send_welcome_email": 0,
			})
			u.append("roles", {"role": "Customer"})
			u.insert(ignore_permissions=True)
		ten_tv = frappe.db.get_value("Portal Member", {"user": email}, "name")
		gia_tri = {
			"customer": customer, "vai_tro": vai_tro,
			"khoa_phong": khoa_phong, "active": 1,
		}
		if ten_tv:
			frappe.db.set_value("Portal Member", ten_tv, gia_tri)
		else:
			frappe.get_doc({
				"doctype": "Portal Member", "user": email, **gia_tri,
			}).insert(ignore_permissions=True)
		return email

	def _tao_phieu(self, khoa_phong):
		doc = frappe.get_doc({
			"doctype": "Portal De Xuat Mua",
			"customer": self.kh_a, "khoa_phong": khoa_phong,
			"items": [{"item_code": self.item, "so_luong_de_xuat": 1}],
		})
		doc.insert(ignore_permissions=True)
		return doc.name

	def _dong_qua_dieu_kien(self, user):
		dk = permissions.de_xuat_item_query(user)
		sql = "select name from `tabPortal De Xuat Mua Item`"
		if dk:
			sql += f" where {dk}"
		return [r.name for r in frappe.db.sql(sql, as_dict=True)]

	def test_khong_chua_dong_hang_khoa_khac(self):
		ten = self._dong_qua_dieu_kien(self.user_huyethoc)
		for d in self.dong_duoc:
			self.assertNotIn(d, ten)

	def test_van_chua_dong_hang_khoa_minh(self):
		"""VẾ DƯƠNG — thiếu test này thì `1=0` cũng qua bài."""
		ten = self._dong_qua_dieu_kien(self.user_huyethoc)
		for d in self.dong_huyethoc:
			self.assertIn(d, ten)

	# ---- I4 (review tổng) — nửa vá ở TẦNG INSTANCE của bảng con ----------
	#
	# `permissions.de_xuat_item_query` (tầng hook, hai test ngay trên) ĐÃ có
	# vế khoa, nhưng `PortalDeXuatMuaItem.has_permission` (tầng instance,
	# CÙNG doctype) vẫn chỉ lọc `customer` — hai tầng cùng một doctype trả
	# lời khác nhau cho cùng một câu hỏi.
	#
	# `super().has_permission()` của Frappe uỷ quyền dòng con cho doctype CHA
	# (`frappe/permissions.py::has_child_permission`), mà `Portal De Xuat Mua`
	# có ZERO DocPerm cho role `Customer` — nên nó trả `False` cho MỌI Website
	# User và bộ lọc riêng của app không bao giờ chạy tới (đúng như docstring
	# `portal_de_xuat_mua_item.py` tự khai: "LỚP PHÒNG THỦ THỨ HAI, chỉ sống
	# lại nếu ai đó cấp DocPerm cho doctype cha"). Test dưới đây mô phỏng ĐÚNG
	# cái "nếu" đó bằng cách vá `Document.has_permission` trả `True` — không
	# cấp DocPerm thật (sẽ rò sang mọi test khác trong cùng site).

	def _co_quyen_doc_dong(self, ten_dong, user):
		from unittest.mock import patch

		from frappe.model.document import Document

		row = frappe.get_doc("Portal De Xuat Mua Item", ten_dong)
		row.flags.ignore_permissions = False
		with patch.object(Document, "has_permission", return_value=True):
			return row.has_permission("read", user=user)

	def test_instance_has_permission_chan_dong_hang_khoa_khac(self):
		for d in self.dong_duoc:
			self.assertFalse(self._co_quyen_doc_dong(d, self.user_huyethoc))

	def test_instance_has_permission_cho_qua_dong_hang_khoa_minh(self):
		"""VẾ DƯƠNG — thiếu test này thì một `return False` vô điều kiện
		cũng qua được vế âm một mình."""
		for d in self.dong_huyethoc:
			self.assertTrue(self._co_quyen_doc_dong(d, self.user_huyethoc))
