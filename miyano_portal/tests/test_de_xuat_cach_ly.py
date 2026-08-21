"""Cách ly `Portal De Xuat Mua` theo khoa phòng — Ở TẦNG HOOK (Task 4).

**Lệch so với kịch bản gốc trong brief — đã kiểm thực nghiệm, không phải
đoán.** Brief đề nghị gọi `frappe.get_list("Portal De Xuat Mua")` dưới một
Website User để quan sát hành vi lọc. Thực nghiệm cho thấy điều đó KHÔNG khả
thi trên doctype này: `Custom DocPerm`/`DocPerm` không có dòng nào cấp
`read` cho role `Customer` (đã kiểm trực tiếp qua `frappe.get_all` trên hai
bảng đó), nên `frappe.get_list`/`doc.check_permission()` ném `PermissionError`
NGAY ở vòng kiểm role — TRƯỚC KHI `permission_query_conditions`/
`has_permission` (hai hàm `de_xuat_query_condition`/`de_xuat_co_quyen`) kịp
chạy. Đây KHÔNG phải một lỗ hổng của Task 4 — nó khớp CHÍNH XÁC với chốt canh
đã có sẵn trong app: `test_kho_isolation.py::TestKhoIsolationParentDoctypes.
test_get_list_denied_for_portal_user_for_every_parent_doctype` đã liệt kê
"Portal De Xuat Mua" vào nhóm 11 doctype "kho cha" mà `frappe.get_list` ném
`PermissionError` cho MỌI Website User, MỌI bộ lọc — kể cả dữ liệu của chính
mình. Hai hàm hook ở đây vì thế là LỚP PHÒNG THỦ THỨ HAI, CHẾT CÓ ĐIỀU KIỆN
trên kênh `frappe.get_list`/`frappe.client.*` — đúng khuôn `hooks.py` đã ghi
cho tám doctype kho khác (khối comment quanh `has_permission = {...}`). Cửa
THẬT của portal cho doctype này là endpoint app (Task 5, chưa tồn tại lúc
file này được viết).

Test ở đây vì thế gọi THẲNG `permissions.de_xuat_query_condition`/
`permissions.de_xuat_co_quyen` — cùng khuôn `test_cach_ly_khoa_phong.py::
TestC3ThieuCotKhoaFailClosed.test_dieu_kien_sql_tra_1_bang_0_khi_thieu_cot`
(gọi `permissions.sales_query()` trực tiếp) và `test_kho_isolation.py`
(gọi `kho_perms.kho_query(BM_USER)` trực tiếp) — vẫn CỐ Ý không qua endpoint
của app (đúng ràng buộc đề bài), chỉ khác là không giả vờ một kênh
`frappe.get_list` "sống" trong khi nó không sống trên doctype này.
`test_frappe_get_list_nem_permission_error_cho_website_user` ở cuối file ghim
lại đúng sự thật thực nghiệm này làm chốt canh kiến trúc, không phải xoá bỏ.
"""

import frappe
from frappe.tests.utils import FrappeTestCase

from miyano_portal import permissions
from miyano_portal.miyano_portal.doctype.portal_de_xuat_mua.portal_de_xuat_mua import (
	TRANG_THAI_NHAP,
)
from miyano_portal.tests.fixtures_de_xuat import dung_fixture


class TestDeXuatCachLy(FrappeTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		# Hạ trạng thái phiếu cũ về Nháp trước khi dọn fixture — né `on_trash`
		# chặn xoá phiếu đã gửi duyệt (bẫy Task 3 đã ghi, xem
		# `TestDeXuatVongDoi.setUp` trong `test_de_xuat_doctype.py`).
		frappe.db.sql(
			"""UPDATE `tabPortal De Xuat Mua` SET trang_thai = %s
			   WHERE customer LIKE '\\_TEST DX%%'""",
			TRANG_THAI_NHAP,
		)
		f = dung_fixture(self)
		self.kh_a, self.kh_b = f.kh_a, f.kh_b
		self.item = f.item
		self.khoa_huyethoc = f.khoa_huyethoc  # dưới kh_a

		# Khoa thứ hai CÙNG kh_a — cô lập đúng trục khoa. `fixtures_de_xuat.
		# khoa_duoc` nằm dưới kh_b (khách khác) — dùng thẳng nó sẽ lẫn trục
		# khách hàng (Task 1) vào bài kiểm trục khoa của Task 4.
		self.khoa_duoc = self._dam_bao_khoa(self.kh_a, "Dược (nội bộ, test cách ly)", "DXDUOCNB")

		self.user_quan_ly = self._dam_bao_thanh_vien(
			"dxcachly.ql@demo.miyano", self.kh_a, "Quản lý", None
		)
		self.user_huyethoc = self._dam_bao_thanh_vien(
			"dxcachly.huyethoc@demo.miyano", self.kh_a, "Nhân viên khoa", self.khoa_huyethoc
		)
		self.user_duoc = self._dam_bao_thanh_vien(
			"dxcachly.duoc@demo.miyano", self.kh_a, "Nhân viên khoa", self.khoa_duoc
		)

		self.phieu_huyethoc = self._tao_phieu(self.kh_a, self.khoa_huyethoc)
		self.phieu_duoc = self._tao_phieu(self.kh_a, self.khoa_duoc)
		# Phiếu của bệnh viện khác — chốt canh trục khách hàng (Task 1); khoa
		# dùng đúng `f.khoa_duoc` (thuộc kh_b), KHÔNG phải `self.khoa_duoc`
		# (thuộc kh_a).
		self.phieu_benh_vien_b = self._tao_phieu(self.kh_b, f.khoa_duoc)

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
			# Role `Customer` — đúng role cổng cấp tài khoản thật
			# (`portal_provision`) gán; `_is_restricted_user` chỉ đọc
			# `user_type`, nhưng gán role này cho khớp một tài khoản thật.
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

	def _tao_phieu(self, customer, khoa_phong):
		doc = frappe.get_doc({
			"doctype": "Portal De Xuat Mua",
			"customer": customer, "khoa_phong": khoa_phong,
			"items": [{"item_code": self.item, "so_luong_de_xuat": 1}],
		})
		doc.insert(ignore_permissions=True)
		return doc.name

	def _ten_qua_dieu_kien(self, user):
		"""Áp `permissions.de_xuat_query_condition(user)` làm mệnh đề WHERE
		THẬT lên bảng, đúng ngữ nghĩa `permission_query_conditions` (một
		chuỗi SQL bổ sung — framework AND nó vào truy vấn gốc). Đi qua CHÍNH
		SQL do hàm sinh ra, không phải so khớp chuỗi — vẫn là một phép kiểm
		tầng hook thật, chỉ không đi qua `frappe.get_list` (kênh đó chết trên
		doctype này, xem docstring đầu file)."""
		dk = permissions.de_xuat_query_condition(user)
		sql = "select name from `tabPortal De Xuat Mua`"
		if dk:
			sql += f" where {dk}"
		return [r.name for r in frappe.db.sql(sql, as_dict=True)]

	# -- trục khoa (Task 4) ---------------------------------------------------

	def test_dieu_kien_khong_chua_phieu_khoa_khac(self):
		ten = self._ten_qua_dieu_kien(self.user_huyethoc)
		self.assertNotIn(self.phieu_duoc, ten)

	def test_dieu_kien_VAN_CHUA_phieu_khoa_minh(self):
		"""VẾ DƯƠNG — thiếu test này thì điều kiện `1=0` cũng qua bài.

		Đây chính xác là lỗ hổng đã làm bộ test bước trước xanh trong khi
		tính năng chết hẳn: nhân viên đặt đơn xong thì chính họ không mở lại
		được."""
		ten = self._ten_qua_dieu_kien(self.user_huyethoc)
		self.assertIn(self.phieu_huyethoc, ten)

	def test_quan_ly_thay_ca_hai_khoa(self):
		ten = self._ten_qua_dieu_kien(self.user_quan_ly)
		self.assertIn(self.phieu_huyethoc, ten)
		self.assertIn(self.phieu_duoc, ten)

	def test_khong_thay_phieu_benh_vien_khac(self):
		"""Trục KHÁCH HÀNG vẫn phải nguyên (chốt canh Task 1) — hook mới
		thêm vế khoa không được nới trục khách hàng đã có."""
		ten = self._ten_qua_dieu_kien(self.user_quan_ly)
		self.assertNotIn(self.phieu_benh_vien_b, ten)

	def test_has_permission_chan_phieu_khoa_khac(self):
		doc = frappe.get_doc("Portal De Xuat Mua", self.phieu_duoc)
		self.assertFalse(permissions.de_xuat_co_quyen(doc, user=self.user_huyethoc))

	def test_has_permission_cho_qua_phieu_khoa_minh(self):
		"""VẾ DƯƠNG của `has_permission` — cùng lý do với test điều kiện SQL
		ngay trên: một `has_permission` trả `False` vô điều kiện cũng qua
		được vế âm một mình."""
		doc = frappe.get_doc("Portal De Xuat Mua", self.phieu_huyethoc)
		self.assertTrue(permissions.de_xuat_co_quyen(doc, user=self.user_huyethoc))

	def test_has_permission_quan_ly_qua_ca_hai_khoa(self):
		doc_huyethoc = frappe.get_doc("Portal De Xuat Mua", self.phieu_huyethoc)
		doc_duoc = frappe.get_doc("Portal De Xuat Mua", self.phieu_duoc)
		self.assertTrue(permissions.de_xuat_co_quyen(doc_huyethoc, user=self.user_quan_ly))
		self.assertTrue(permissions.de_xuat_co_quyen(doc_duoc, user=self.user_quan_ly))

	def test_has_permission_chan_benh_vien_khac(self):
		"""Trục khách hàng của `has_permission` vẫn phải nguyên."""
		doc = frappe.get_doc("Portal De Xuat Mua", self.phieu_benh_vien_b)
		self.assertFalse(permissions.de_xuat_co_quyen(doc, user=self.user_quan_ly))

	# -- chốt canh kiến trúc ---------------------------------------------------

	def test_frappe_get_list_nem_permission_error_cho_website_user(self):
		"""Ghim lại sự thật thực nghiệm đã dẫn tới cách viết test ở trên: role
		`Customer` không có DocPerm `read` nào trên doctype này, nên
		`frappe.get_list` ném `PermissionError` NGAY, trước khi
		`permission_query_conditions`/`has_permission` kịp chạy — khớp
		`test_kho_isolation.py::TestKhoIsolationParentDoctypes.
		test_get_list_denied_for_portal_user_for_every_parent_doctype`. Nếu
		test này một ngày nào đó ĐỎ (tức có ai cấp lại DocPerm cho `Customer`
		trên doctype này), toàn bộ các test gọi thẳng hook ở trên PHẢI được
		viết lại thành test qua `frappe.get_list`, đúng tinh thần gốc của
		brief Task 4."""
		frappe.set_user(self.user_huyethoc)
		with self.assertRaises(frappe.PermissionError):
			frappe.get_list("Portal De Xuat Mua")
