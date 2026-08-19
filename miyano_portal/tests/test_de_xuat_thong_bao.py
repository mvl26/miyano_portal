"""Thông báo chọn người nhận theo khoa phòng (Task 8, spec §5.8).

Bảng người nhận (spec §5.8):

  | Việc                                   | Ai nhận                         |
  |----------------------------------------|----------------------------------|
  | Khoa gửi đề xuất                       | CHỈ Quản lý                     |
  | Quản lý duyệt / từ chối                | Quản lý (luôn) + thành viên khác |
  |                                        | của khoa đứng tên phiếu          |
  | Miyano xác nhận, hẹn giao, giao hàng   | Quản lý + thành viên của khoa    |
  |                                        | đứng tên đơn                     |

"Xác nhận" (Notification khai báo "Portal - Đơn xác nhận",
`setup/install_notifications.py`) định tuyến qua `receiver_by_document_
field: contact_email` — CƠ CHẾ CỦA FRAPPE, `portal_thong_bao_khach.py`
không chen vào được (xem docstring đầu file đó) — NGOÀI PHẠM VI test này.
Chỉ "hẹn giao" (`bao_hen_giao_lai`) và "giao hàng" (`bao_da_nhap_hang`)
được sửa ở Task 8. `bao_kiem_hang_ket_qua` ("Kiểm hàng") mang cùng lỗ
broadcast-toàn-khách nhưng KHÔNG phải một trong ba việc bảng liệt kê —
CỐ Ý để nguyên, ghi vào report làm ứng viên vòng sau.

Bốn bẫy đã biết (brief Task 8 + `test_de_xuat_duyet.py`):
  1. `on_trash` chặn xoá phiếu đã gửi duyệt -> hạ trạng thái bằng SQL thô
     TRƯỚC `dung_fixture()`.
  2. Test tạo Sales Order phải xoá SO test TRƯỚC khi xoá phiếu (nếu không,
     `revert_series_if_last` cấp trùng tên phiếu, chốt chống-trùng-đơn trả
     nhầm đơn cũ).
  3. `tabError Log` là MyISAM, sống qua rollback -> không dùng để đếm.
  4. `User.insert()` commit bên trong -> tái dùng fixture/email cũ giữa các
     lớp, không tạo tuỳ tiện.
"""

from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from miyano_portal import de_xuat_duyet, portal_context
from miyano_portal.kho import delivery_hook
from miyano_portal.miyano_portal.doctype.portal_de_xuat_mua.portal_de_xuat_mua import (
	TRANG_THAI_NHAP,
)
from miyano_portal.portal_thong_bao_khach import (
	TIEN_TO_DE_XUAT_DA_DUYET,
	TIEN_TO_DE_XUAT_TU_CHOI,
	_portal_users_theo_khoa,
	bao_da_nhap_hang,
	bao_hen_giao_lai,
)
from miyano_portal.tests.fixtures_de_xuat import dung_fixture

COMPANY = "Miyano Việt Nam"
WAREHOUSE = "Stores - MYN"


def _don_phieu_cu():
	"""Bẫy #1/#2 — cùng khuôn `test_de_xuat_duyet.py::_don_phieu_cu`."""
	for r in frappe.get_all(
		"Sales Order", filters={"customer": ["like", "_TEST DX%"], "docstatus": 0}
	):
		frappe.delete_doc("Sales Order", r.name, force=True, ignore_permissions=True)
	frappe.db.sql(
		"""UPDATE `tabPortal De Xuat Mua` SET trang_thai = %s
		   WHERE customer LIKE '\\_TEST DX%%'""",
		TRANG_THAI_NHAP,
	)


def _dam_bao_khoa(customer, ten, ma):
	ten_bp = frappe.db.get_value(
		"Customer Department", {"customer": customer, "ma_khoa": ma}, "name"
	)
	if ten_bp:
		return ten_bp
	return frappe.get_doc({
		"doctype": "Customer Department", "customer": customer,
		"ten_khoa_phong": ten, "ma_khoa": ma, "active": 1,
	}).insert(ignore_permissions=True).name


def _dam_bao_thanh_vien(email, customer, vai_tro, khoa_phong):
	"""Cùng khuôn `test_de_xuat_duyet.py` — bẫy #4, tái dùng email cũ."""
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
	_gan_contact_vao_khach(email, customer)
	return email


def _gan_contact_vao_khach(email, customer):
	"""Cần cho các lớp đi qua `de_xuat_duyet.duyet_va_tao_don` (sinh Sales
	Order) — xem docstring gốc trong `test_de_xuat_duyet.py`."""
	contact_name = frappe.db.get_value("Contact", {"user": email})
	if not contact_name:
		return
	if frappe.db.exists("Dynamic Link", {
		"parent": contact_name, "parenttype": "Contact",
		"link_doctype": "Customer", "link_name": customer,
	}):
		return
	c = frappe.get_doc("Contact", contact_name)
	c.append("links", {"link_doctype": "Customer", "link_name": customer})
	c.save(ignore_permissions=True)


def _co_nhan(for_user, document_name, document_type=None):
	loc = {"for_user": for_user, "document_name": document_name}
	if document_type:
		loc["document_type"] = document_type
	return bool(frappe.db.exists("Notification Log", loc))


def _co_nhan_dung_buoc(for_user, document_name, tien_to):
	"""VẾ DƯƠNG canh ĐÚNG bước — review vòng 2 (Task 8): `gui_duyet()` tự
	gửi `bao_de_xuat_gui_duyet` cho Quản lý TRƯỚC khi test gọi
	`duyet()`/`tu_choi()` (đường dựng phiếu "Chờ duyệt" luôn đi qua
	`gui_duyet()`). `_co_nhan()` chỉ kiểm TỒN TẠI theo `for_user` +
	`document_name`, không phân biệt thông báo đến từ bước nào — với Quản
	lý (nhận ở CẢ BA bước) một `assertTrue(_co_nhan(...))` sau bước
	duyệt/từ chối vẫn xanh dù CHÍNH bước đó không gửi gì (bao_de_xuat_
	duyet/tu_choi nuốt lỗi, `except Exception: ... return 0`), chỉ vì
	thông báo gửi-duyệt còn sót lại. Hàm này khoá đúng `subject` bắt đầu
	bằng tiền tố của TỪNG bước — dùng cho MỌI khẳng định "Quản lý nhận"
	sau duyệt/từ chối, không dùng `_co_nhan()` trơn ở đó nữa."""
	return bool(frappe.db.exists("Notification Log", {
		"for_user": for_user, "document_name": document_name,
		"document_type": "Portal De Xuat Mua",
		"subject": ["like", f"{tien_to}:%"],
	}))


# ======================================================================
# _portal_users_theo_khoa — hàm chọn người nhận DÙNG CHUNG cho cả ba việc
# trong bảng §5.8 (khác nhau ở tham số `khoa_phong` truyền vào, không phải
# khác cơ chế).
# ======================================================================
class TestPortalUsersTheoKhoa(FrappeTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		_don_phieu_cu()
		f = dung_fixture(self)
		self.kh_a = f.kh_a
		self.khoa_huyethoc = f.khoa_huyethoc
		self.khoa_duoc = _dam_bao_khoa(self.kh_a, "Dược (test tb1)", "DXTB1DUOC")

		self.ql = _dam_bao_thanh_vien("dxtb1.ql@demo.miyano", self.kh_a, "Quản lý", None)
		self.huyethoc = _dam_bao_thanh_vien(
			"dxtb1.huyethoc@demo.miyano", self.kh_a, "Nhân viên khoa", self.khoa_huyethoc
		)
		self.duoc = _dam_bao_thanh_vien(
			"dxtb1.duoc@demo.miyano", self.kh_a, "Nhân viên khoa", self.khoa_duoc
		)

	def tearDown(self):
		frappe.set_user("Administrator")

	def test_khoa_phong_rong_chi_tra_quan_ly(self):
		"""`khoa_phong=None` -> CHỈ quản lý (đơn Toàn viện, hoặc sự kiện
		"gửi duyệt" chủ động không muốn báo lại cho khoa vừa gửi)."""
		ket_qua = _portal_users_theo_khoa(self.kh_a, None)
		self.assertIn(self.ql, ket_qua)             # VẾ DƯƠNG
		self.assertNotIn(self.huyethoc, ket_qua)     # VẾ ÂM
		self.assertNotIn(self.duoc, ket_qua)         # VẾ ÂM

	def test_khoa_phong_cu_the_tra_quan_ly_va_dung_khoa(self):
		ket_qua = _portal_users_theo_khoa(self.kh_a, self.khoa_huyethoc)
		self.assertIn(self.ql, ket_qua)              # quản lý luôn nhận
		self.assertIn(self.huyethoc, ket_qua)        # VẾ DƯƠNG — đúng khoa
		self.assertNotIn(self.duoc, ket_qua)         # VẾ ÂM — khoa khác

	def test_user_bi_khoa_khong_duoc_tinh(self):
		frappe.db.set_value("User", self.huyethoc, "enabled", 0)
		self.addCleanup(frappe.db.set_value, "User", self.huyethoc, "enabled", 1)
		ket_qua = _portal_users_theo_khoa(self.kh_a, self.khoa_huyethoc)
		self.assertNotIn(self.huyethoc, ket_qua)     # VẾ ÂM — đã khoá
		self.assertIn(self.ql, ket_qua)              # VẾ DƯƠNG — còn active

	def test_khach_khong_ai_tra_rong(self):
		self.assertEqual(_portal_users_theo_khoa("Khách không tồn tại XYZ8", None), [])


# ======================================================================
# Hàng 1 — Khoa gửi đề xuất -> CHỈ Quản lý.
# ======================================================================
class TestThongBaoGuiDuyet(FrappeTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		_don_phieu_cu()
		f = dung_fixture(self)
		self.kh_a = f.kh_a
		self.item = f.item
		self.khoa_huyethoc = f.khoa_huyethoc
		self.khoa_duoc = _dam_bao_khoa(self.kh_a, "Dược (test tb2)", "DXTB2DUOC")

		self.ql = _dam_bao_thanh_vien("dxtb2.ql@demo.miyano", self.kh_a, "Quản lý", None)
		self.huyethoc = _dam_bao_thanh_vien(
			"dxtb2.huyethoc@demo.miyano", self.kh_a, "Nhân viên khoa", self.khoa_huyethoc
		)
		self.duoc = _dam_bao_thanh_vien(
			"dxtb2.duoc@demo.miyano", self.kh_a, "Nhân viên khoa", self.khoa_duoc
		)

	def tearDown(self):
		frappe.set_user("Administrator")

	def _tao_va_gui(self):
		doc = frappe.get_doc({
			"doctype": "Portal De Xuat Mua",
			"customer": self.kh_a, "khoa_phong": self.khoa_huyethoc,
			"loai_don": "Mua lẻ",
			"items": [{"item_code": self.item, "so_luong_de_xuat": 3}],
		})
		doc.insert(ignore_permissions=True)
		frappe.db.set_value("Portal De Xuat Mua", doc.name, "owner", self.huyethoc)
		doc.reload()
		doc.ly_do_yeu_cau = "cần gấp"
		doc.gui_duyet()
		doc.reload()
		return doc

	def test_quan_ly_nhan_thong_bao_khi_khoa_gui_de_xuat(self):
		"""VẾ DƯƠNG bắt buộc — "Quản lý luôn nhận" (ràng buộc 3)."""
		doc = self._tao_va_gui()
		self.assertTrue(_co_nhan(self.ql, doc.name, "Portal De Xuat Mua"))

	def test_dong_nghiep_cung_khoa_khong_nhan_thong_bao_gui_duyet(self):
		"""VẾ ÂM — hàng 1 chỉ cấp Quản lý, không cấp lại cho chính khoa vừa
		gửi, kể cả đồng nghiệp cùng khoa với người lập."""
		doc = self._tao_va_gui()
		self.assertFalse(_co_nhan(self.huyethoc, doc.name, "Portal De Xuat Mua"))

	def test_nhan_vien_khoa_khac_khong_nhan_thong_bao_gui_duyet(self):
		"""VẾ ÂM."""
		doc = self._tao_va_gui()
		self.assertFalse(_co_nhan(self.duoc, doc.name, "Portal De Xuat Mua"))

	def test_noi_dung_thong_bao_mang_ma_de_xuat(self):
		doc = self._tao_va_gui()
		subject = frappe.db.get_value(
			"Notification Log",
			{"for_user": self.ql, "document_name": doc.name},
			"subject",
		)
		self.assertIn(doc.ma_de_xuat, subject)


# ======================================================================
# Hàng 2 (duyệt) — Quản lý (luôn) + thành viên khác của khoa đứng tên
# phiếu.
# ======================================================================
class TestThongBaoDuyet(FrappeTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		_don_phieu_cu()
		f = dung_fixture(self)
		self.kh_a = f.kh_a
		self.item = f.item
		self.khoa_huyethoc = f.khoa_huyethoc
		self.khoa_duoc = _dam_bao_khoa(self.kh_a, "Dược (test tb3)", "DXTB3DUOC")

		self.ql = _dam_bao_thanh_vien("dxtb3.ql@demo.miyano", self.kh_a, "Quản lý", None)
		self.huyethoc = _dam_bao_thanh_vien(
			"dxtb3.huyethoc@demo.miyano", self.kh_a, "Nhân viên khoa", self.khoa_huyethoc
		)
		# Đồng nghiệp THỨ HAI cùng khoa, KHÔNG phải người lập — chốt riêng
		# vế "+ thành viên khác của khoa đó", khác vế "người lập".
		self.huyethoc2 = _dam_bao_thanh_vien(
			"dxtb3.huyethoc2@demo.miyano", self.kh_a, "Nhân viên khoa", self.khoa_huyethoc
		)
		self.duoc = _dam_bao_thanh_vien(
			"dxtb3.duoc@demo.miyano", self.kh_a, "Nhân viên khoa", self.khoa_duoc
		)

		self.phieu = self._cho_duyet()

	def tearDown(self):
		frappe.set_user("Administrator")

	def _cho_duyet(self):
		doc = frappe.get_doc({
			"doctype": "Portal De Xuat Mua",
			"customer": self.kh_a, "khoa_phong": self.khoa_huyethoc,
			"loai_don": "Mua lẻ",
			"items": [{"item_code": self.item, "so_luong_de_xuat": 4}],
		})
		doc.insert(ignore_permissions=True)
		frappe.db.set_value("Portal De Xuat Mua", doc.name, "owner", self.huyethoc)
		doc.reload()
		doc.ly_do_yeu_cau = "cần gấp"
		doc.gui_duyet()
		doc.reload()
		doc.items[0].so_luong_duyet = doc.items[0].so_luong_de_xuat
		doc.save(ignore_permissions=True)
		doc.reload()
		return doc

	def test_quan_ly_nhan_thong_bao_khi_tu_duyet(self):
		"""VẾ DƯƠNG bắt buộc — quản lý luôn nhận, kể cả khi CHÍNH họ bấm
		duyệt.

		Review vòng 2 (Task 8) — dùng `_co_nhan_dung_buoc()` (khoá theo
		`TIEN_TO_DE_XUAT_DA_DUYET`), KHÔNG dùng `_co_nhan()` trơn: `setUp`
		đã gọi `gui_duyet()` để dựng phiếu "Chờ duyệt", và bước đó CŨNG gửi
		thông báo cho Quản lý (`bao_de_xuat_gui_duyet`) — `_co_nhan()`
		trơn sẽ xanh giả ngay cả khi CHÍNH `bao_de_xuat_duyet` hỏng/bị
		nuốt lỗi."""
		de_xuat_duyet.duyet_va_tao_don(self.phieu.name, self.ql)
		self.assertTrue(
			_co_nhan_dung_buoc(self.ql, self.phieu.name, TIEN_TO_DE_XUAT_DA_DUYET)
		)

	def test_nguoi_lap_de_xuat_nhan_thong_bao_duyet(self):
		"""VẾ DƯƠNG — người lập (owner) nhận."""
		de_xuat_duyet.duyet_va_tao_don(self.phieu.name, self.ql)
		self.assertTrue(_co_nhan(self.huyethoc, self.phieu.name, "Portal De Xuat Mua"))

	def test_dong_nghiep_khac_cung_khoa_nhan_thong_bao_duyet(self):
		"""VẾ DƯƠNG — thành viên KHÁC của khoa (không phải người lập) cũng
		phải biết phiếu vừa được duyệt."""
		de_xuat_duyet.duyet_va_tao_don(self.phieu.name, self.ql)
		self.assertTrue(_co_nhan(self.huyethoc2, self.phieu.name, "Portal De Xuat Mua"))

	def test_khoa_khac_khong_nhan_thong_bao_duyet(self):
		"""VẾ ÂM — chính lỗ đầu bài nêu."""
		de_xuat_duyet.duyet_va_tao_don(self.phieu.name, self.ql)
		self.assertFalse(_co_nhan(self.duoc, self.phieu.name, "Portal De Xuat Mua"))

	def test_phieu_toan_vien_khi_duyet_chi_quan_ly_nhan(self):
		"""I1 (review Task 8) — `doc.khoa_phong` RỖNG (phiếu "Toàn viện") →
		CHỈ Quản lý nhận, không thành viên khoa nào. Trước bản vá này, nhánh
		"chỉ Quản lý" của `_portal_users_theo_khoa` đúng nhưng KHÔNG có bằng
		chứng thực nghiệm ở dòng duyệt (dòng hẹn giao đã có
		`test_don_toan_vien_chi_quan_ly_nhan`) — một đổi `doc.khoa_phong`
		thành `doc.khoa_phong or "ALL"` sẽ không bị bắt."""
		doc = frappe.get_doc({
			"doctype": "Portal De Xuat Mua",
			"customer": self.kh_a, "khoa_phong": None,
			"loai_don": "Mua lẻ",
			"items": [{"item_code": self.item, "so_luong_de_xuat": 2}],
		})
		doc.insert(ignore_permissions=True)
		doc.ly_do_yeu_cau = "cần gấp"
		doc.gui_duyet()
		doc.reload()
		doc.items[0].so_luong_duyet = doc.items[0].so_luong_de_xuat
		doc.save(ignore_permissions=True)
		doc.reload()

		de_xuat_duyet.duyet_va_tao_don(doc.name, self.ql)
		# Review vòng 2 — cùng lý do `test_quan_ly_nhan_thong_bao_khi_tu_
		# duyet`: `gui_duyet()` ngay TRÊN cũng đã gửi cho Quản lý, khoá
		# theo tiền tố đúng bước để không xanh giả.
		self.assertTrue(_co_nhan_dung_buoc(
			self.ql, doc.name, TIEN_TO_DE_XUAT_DA_DUYET
		))                                                                          # VẾ DƯƠNG
		self.assertFalse(_co_nhan(self.huyethoc, doc.name, "Portal De Xuat Mua"))  # VẾ ÂM
		self.assertFalse(_co_nhan(self.huyethoc2, doc.name, "Portal De Xuat Mua"))
		self.assertFalse(_co_nhan(self.duoc, doc.name, "Portal De Xuat Mua"))


# ======================================================================
# Hàng 2 (từ chối) — cùng bảng người nhận với duyệt.
# ======================================================================
class TestThongBaoTuChoi(FrappeTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		_don_phieu_cu()
		f = dung_fixture(self)
		self.kh_a = f.kh_a
		self.item = f.item
		self.khoa_huyethoc = f.khoa_huyethoc
		self.khoa_duoc = _dam_bao_khoa(self.kh_a, "Dược (test tb4)", "DXTB4DUOC")

		self.ql = _dam_bao_thanh_vien("dxtb4.ql@demo.miyano", self.kh_a, "Quản lý", None)
		self.huyethoc = _dam_bao_thanh_vien(
			"dxtb4.huyethoc@demo.miyano", self.kh_a, "Nhân viên khoa", self.khoa_huyethoc
		)
		self.huyethoc2 = _dam_bao_thanh_vien(
			"dxtb4.huyethoc2@demo.miyano", self.kh_a, "Nhân viên khoa", self.khoa_huyethoc
		)
		self.duoc = _dam_bao_thanh_vien(
			"dxtb4.duoc@demo.miyano", self.kh_a, "Nhân viên khoa", self.khoa_duoc
		)

		self.phieu = self._cho_duyet()

	def tearDown(self):
		frappe.set_user("Administrator")

	def _cho_duyet(self):
		doc = frappe.get_doc({
			"doctype": "Portal De Xuat Mua",
			"customer": self.kh_a, "khoa_phong": self.khoa_huyethoc,
			"loai_don": "Mua lẻ",
			"items": [{"item_code": self.item, "so_luong_de_xuat": 2}],
		})
		doc.insert(ignore_permissions=True)
		frappe.db.set_value("Portal De Xuat Mua", doc.name, "owner", self.huyethoc)
		doc.reload()
		doc.ly_do_yeu_cau = "cần gấp"
		doc.gui_duyet()
		doc.reload()
		return doc

	def test_quan_ly_nhan_thong_bao_tu_choi(self):
		"""VẾ DƯƠNG.

		Review vòng 2 (Task 8) — cùng lý do `TestThongBaoDuyet.test_quan_
		ly_nhan_thong_bao_khi_tu_duyet`: `setUp` đã `gui_duyet()`, cũng
		gửi cho Quản lý. Khoá theo `TIEN_TO_DE_XUAT_TU_CHOI` để chỉ tính
		đúng thông báo của bước từ chối."""
		self.phieu.tu_choi("thiếu chứng từ")
		self.assertTrue(_co_nhan_dung_buoc(
			self.ql, self.phieu.name, TIEN_TO_DE_XUAT_TU_CHOI
		))

	def test_nguoi_lap_nhan_thong_bao_tu_choi(self):
		"""VẾ DƯƠNG."""
		self.phieu.tu_choi("thiếu chứng từ")
		self.assertTrue(_co_nhan(self.huyethoc, self.phieu.name, "Portal De Xuat Mua"))

	def test_dong_nghiep_cung_khoa_nhan_thong_bao_tu_choi(self):
		"""VẾ DƯƠNG."""
		self.phieu.tu_choi("thiếu chứng từ")
		self.assertTrue(_co_nhan(self.huyethoc2, self.phieu.name, "Portal De Xuat Mua"))

	def test_khoa_khac_khong_nhan_thong_bao_tu_choi(self):
		"""VẾ ÂM."""
		self.phieu.tu_choi("thiếu chứng từ")
		self.assertFalse(_co_nhan(self.duoc, self.phieu.name, "Portal De Xuat Mua"))

	def test_phieu_toan_vien_khi_tu_choi_chi_quan_ly_nhan(self):
		"""I1 (review Task 8) — cùng lý do với bản song sinh ở
		`TestThongBaoDuyet.test_phieu_toan_vien_khi_duyet_chi_quan_ly_nhan`,
		áp cho nhánh từ chối: `doc.khoa_phong` rỗng (phiếu "Toàn viện") →
		CHỈ Quản lý nhận."""
		doc = frappe.get_doc({
			"doctype": "Portal De Xuat Mua",
			"customer": self.kh_a, "khoa_phong": None,
			"loai_don": "Mua lẻ",
			"items": [{"item_code": self.item, "so_luong_de_xuat": 2}],
		})
		doc.insert(ignore_permissions=True)
		doc.ly_do_yeu_cau = "cần gấp"
		doc.gui_duyet()
		doc.reload()

		doc.tu_choi("thiếu chứng từ")
		# Review vòng 2 — cùng lý do bản song sinh ở TestThongBaoDuyet.
		self.assertTrue(_co_nhan_dung_buoc(
			self.ql, doc.name, TIEN_TO_DE_XUAT_TU_CHOI
		))                                                                          # VẾ DƯƠNG
		self.assertFalse(_co_nhan(self.huyethoc, doc.name, "Portal De Xuat Mua"))  # VẾ ÂM
		self.assertFalse(_co_nhan(self.huyethoc2, doc.name, "Portal De Xuat Mua"))
		self.assertFalse(_co_nhan(self.duoc, doc.name, "Portal De Xuat Mua"))

	def test_ly_do_tu_choi_co_trong_noi_dung(self):
		self.phieu.tu_choi("thiếu chứng từ pháp lý")
		noi_dung = frappe.db.get_value(
			"Notification Log",
			{"for_user": self.ql, "document_name": self.phieu.name},
			"email_content",
		)
		self.assertIn("thiếu chứng từ pháp lý", noi_dung)


# ======================================================================
# Hàng 3 (hẹn giao) — Quản lý + thành viên của khoa đứng tên ĐƠN.
# ======================================================================
class TestBaoHenGiaoLaiTheoKhoa(FrappeTestCase):
	"""Gọi THẲNG `bao_hen_giao_lai(so, ...)` với `so` là `frappe._dict` mô
	phỏng đủ field hàm này đọc (`customer`, `name`, `custom_khoa_phong`) —
	cùng khuôn `test_thong_bao_khach.py::TestKiemTraDinhTuyenThongBaoKhach.
	_so_gia`. Không dựng cả một Sales Order thật chỉ để có ba field."""

	def setUp(self):
		frappe.set_user("Administrator")
		_don_phieu_cu()
		f = dung_fixture(self)
		self.kh_a = f.kh_a
		self.khoa_huyethoc = f.khoa_huyethoc
		self.khoa_duoc = _dam_bao_khoa(self.kh_a, "Dược (test tb5)", "DXTB5DUOC")

		self.ql = _dam_bao_thanh_vien("dxtb5.ql@demo.miyano", self.kh_a, "Quản lý", None)
		self.huyethoc = _dam_bao_thanh_vien(
			"dxtb5.huyethoc@demo.miyano", self.kh_a, "Nhân viên khoa", self.khoa_huyethoc
		)
		self.duoc = _dam_bao_thanh_vien(
			"dxtb5.duoc@demo.miyano", self.kh_a, "Nhân viên khoa", self.khoa_duoc
		)

	def tearDown(self):
		frappe.set_user("Administrator")

	def _so_gia(self, ten, khoa_phong):
		return frappe._dict(
			doctype="Sales Order", name=ten,
			customer=self.kh_a, custom_khoa_phong=khoa_phong,
		)

	def _ngay(self):
		return frappe.utils.add_days(frappe.utils.today(), 3)

	def test_quan_ly_nhan_thong_bao_hen_giao(self):
		"""VẾ DƯƠNG."""
		so = self._so_gia("SAL-ORD-TB5-01", self.khoa_huyethoc)
		bao_hen_giao_lai(so, "Sẽ giao bù", self._ngay(), "hàng chưa về kho Miyano")
		self.assertTrue(_co_nhan(self.ql, so.name, "Sales Order"))

	def test_thanh_vien_dung_khoa_nhan_thong_bao_hen_giao(self):
		"""VẾ DƯƠNG."""
		so = self._so_gia("SAL-ORD-TB5-02", self.khoa_huyethoc)
		bao_hen_giao_lai(so, "Sẽ giao bù", self._ngay(), "hàng chưa về kho Miyano")
		self.assertTrue(_co_nhan(self.huyethoc, so.name, "Sales Order"))

	def test_khoa_khac_khong_nhan_thong_bao_hen_giao(self):
		"""VẾ ÂM — chính lỗ mà brief nêu (khoa Dược nhận thông báo của khoa
		Huyết học)."""
		so = self._so_gia("SAL-ORD-TB5-03", self.khoa_huyethoc)
		bao_hen_giao_lai(so, "Sẽ giao bù", self._ngay(), "hàng chưa về kho Miyano")
		self.assertFalse(_co_nhan(self.duoc, so.name, "Sales Order"))

	def test_don_toan_vien_chi_quan_ly_nhan(self):
		"""`khoa_phong` rỗng (đơn Toàn viện) -> CHỈ quản lý."""
		so = self._so_gia("SAL-ORD-TB5-04", None)
		bao_hen_giao_lai(so, "Sẽ giao bù", self._ngay(), "hàng chưa về kho Miyano")
		self.assertTrue(_co_nhan(self.ql, so.name, "Sales Order"))
		self.assertFalse(_co_nhan(self.huyethoc, so.name, "Sales Order"))

	# ---- M2 (review tổng) — thiếu cột thì rơi về "BÁO TẤT CẢ" ------------
	#
	# `kho/delivery_hook._khoa_phong_dau_tien` đã đi qua `portal_context.
	# _cot_khoa_phong_ton_tai()` và thiếu cột thì rơi về nhánh AN TOÀN "báo
	# TOÀN BỘ tài khoản của khách". Hàm này đọc `so.get("custom_khoa_phong")`
	# TRẦN, nên cùng một điều kiện (patch `v1_23` chưa chạy) lại rơi về nhánh
	# NGƯỢC LẠI — "chỉ Quản lý". Chốt của module: "gửi thừa còn hơn gửi
	# thiếu".

	def test_thieu_cot_khoa_phong_thi_bao_TAT_CA_khong_chi_quan_ly(self):
		so = self._so_gia("SAL-ORD-TB5-05", self.khoa_huyethoc)
		with patch.object(
			portal_context, "_cot_khoa_phong_ton_tai", return_value=False
		):
			bao_hen_giao_lai(so, "Sẽ giao bù", self._ngay(), "hàng chưa về kho")
		self.assertTrue(_co_nhan(self.ql, so.name, "Sales Order"))
		self.assertTrue(_co_nhan(self.huyethoc, so.name, "Sales Order"))
		# Chốt của M2 — khoa KHÁC cũng nhận: không xác định được khoa thì
		# KHÔNG được thu hẹp, đúng chiều fallback của `delivery_hook`.
		self.assertTrue(_co_nhan(self.duoc, so.name, "Sales Order"))

	def test_CO_cot_khoa_phong_thi_van_thu_hep_dung_khoa(self):
		"""VẾ DƯƠNG của test trên — lưới an toàn không được nới hành vi
		bình thường (khoa Dược vẫn KHÔNG nhận tin của khoa Huyết học)."""
		so = self._so_gia("SAL-ORD-TB5-06", self.khoa_huyethoc)
		bao_hen_giao_lai(so, "Sẽ giao bù", self._ngay(), "hàng chưa về kho")
		self.assertTrue(_co_nhan(self.huyethoc, so.name, "Sales Order"))
		self.assertFalse(_co_nhan(self.duoc, so.name, "Sales Order"))


# ======================================================================
# Hàng 3 (giao hàng) — Quản lý + thành viên của khoa đứng tên ĐƠN.
# ======================================================================
class TestBaoDaNhapHangTheoKhoa(FrappeTestCase):
	"""Tham số MỚI `khoa_phong` trên `bao_da_nhap_hang` (mặc định `None` —
	tương thích ngược: `test_thong_bao_khach.py::TestBaoDaNhapHang` không
	truyền tham số này và vẫn phải xanh, xem
	`test_khong_truyen_khoa_phong_giu_hanh_vi_cu_bao_moi_nguoi` dưới)."""

	def setUp(self):
		frappe.set_user("Administrator")
		_don_phieu_cu()
		f = dung_fixture(self)
		self.kh_a = f.kh_a
		self.khoa_huyethoc = f.khoa_huyethoc
		self.khoa_duoc = _dam_bao_khoa(self.kh_a, "Dược (test tb6)", "DXTB6DUOC")

		self.ql = _dam_bao_thanh_vien("dxtb6.ql@demo.miyano", self.kh_a, "Quản lý", None)
		self.huyethoc = _dam_bao_thanh_vien(
			"dxtb6.huyethoc@demo.miyano", self.kh_a, "Nhân viên khoa", self.khoa_huyethoc
		)
		self.duoc = _dam_bao_thanh_vien(
			"dxtb6.duoc@demo.miyano", self.kh_a, "Nhân viên khoa", self.khoa_duoc
		)
		self.addCleanup(
			frappe.db.delete, "Error Log",
			{"method": ["like", "Portal - Không tra được tài khoản cổng:%"]},
		)

	def tearDown(self):
		frappe.set_user("Administrator")

	def test_khoa_dung_thi_thanh_vien_khoa_va_quan_ly_nhan(self):
		dem = bao_da_nhap_hang(
			self.kh_a, "PHIEU-TB6-01", "DN-TB6-01", khoa_phong=self.khoa_huyethoc
		)
		self.assertEqual(dem, 2)  # quản lý + đúng khoa
		self.assertTrue(_co_nhan(self.ql, "PHIEU-TB6-01"))              # VẾ DƯƠNG
		self.assertTrue(_co_nhan(self.huyethoc, "PHIEU-TB6-01"))        # VẾ DƯƠNG

	def test_khoa_khac_khong_nhan_thong_bao_giao_hang(self):
		"""VẾ ÂM — chính lỗ đầu bài nêu."""
		bao_da_nhap_hang(
			self.kh_a, "PHIEU-TB6-02", "DN-TB6-02", khoa_phong=self.khoa_huyethoc
		)
		self.assertFalse(_co_nhan(self.duoc, "PHIEU-TB6-02"))

	def test_khong_truyen_khoa_phong_giu_hanh_vi_cu_bao_moi_nguoi(self):
		"""Tương thích ngược — KHÔNG truyền `khoa_phong` (mặc định `None`)
		vẫn báo TOÀN BỘ tài khoản của khách, đúng hành vi trước Task 8."""
		dem = bao_da_nhap_hang(self.kh_a, "PHIEU-TB6-03", "DN-TB6-03")
		self.assertEqual(dem, 3)  # ql + huyethoc + duoc, KHÔNG thu hẹp
		self.assertTrue(_co_nhan(self.duoc, "PHIEU-TB6-03"))


# ======================================================================
# `delivery_hook._khoa_phong_dau_tien` — suy khoa từ SO đầu tiên đứng sau
# DN (tái dùng `_sales_order_dau_tien` đã có cho `so_dot`, KHÔNG dựng cơ
# chế suy khoa thứ hai trong module thông báo — spec §11 mục 5).
# ======================================================================
class TestKhoaPhongDauTienDeliveryHook(FrappeTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		_don_phieu_cu()
		f = dung_fixture(self)
		self.kh_a = f.kh_a
		self.item = f.item
		self.khoa_huyethoc = f.khoa_huyethoc

	def tearDown(self):
		frappe.set_user("Administrator")

	def _so(self, khoa_phong):
		so = frappe.get_doc({
			"doctype": "Sales Order", "customer": self.kh_a, "company": COMPANY,
			"transaction_date": frappe.utils.today(),
			"delivery_date": frappe.utils.add_days(frappe.utils.today(), 3),
			"custom_khoa_phong": khoa_phong,
			"items": [{
				"item_code": self.item, "qty": 2, "rate": 10000,
				"warehouse": WAREHOUSE,
			}],
		})
		so.insert(ignore_permissions=True)
		so.submit()
		return so

	def test_suy_dung_khoa_tu_don_dung_sau_dn(self):
		"""VẾ DƯƠNG."""
		from erpnext.selling.doctype.sales_order.sales_order import make_delivery_note

		so = self._so(self.khoa_huyethoc)
		dn = make_delivery_note(so.name)
		self.assertEqual(delivery_hook._khoa_phong_dau_tien(dn), self.khoa_huyethoc)

	def test_dn_khong_qua_don_nao_thi_tra_none(self):
		"""VẾ ÂM — DN bán lẻ không qua Sales Order."""
		dn = frappe.get_doc({
			"doctype": "Delivery Note", "customer": self.kh_a, "company": COMPANY,
			"posting_date": frappe.utils.today(),
			"items": [{
				"item_code": self.item, "qty": 1, "rate": 10000,
				"warehouse": WAREHOUSE,
			}],
		})
		self.assertIsNone(delivery_hook._khoa_phong_dau_tien(dn))

	def test_khong_dot_cot_khi_thieu_cot_custom_khoa_phong(self):
		"""I2 (review Task 8) — `_khoa_phong_dau_tien` phải đi qua
		`portal_context._cot_khoa_phong_ton_tai()` TRƯỚC khi chạm cột
		`custom_khoa_phong`, cùng nguồn kiểm tra MỌI nơi khác trong app
		dùng (`permissions.py`, `api/portal.py`) — không dò cột thứ hai.
		Thiếu cột (site chưa chạy patch) → trả `None`, rơi về nhánh "gửi
		thừa còn hơn gửi thiếu" của `bao_da_nhap_hang`, KHÔNG ném lỗi CSDL
		thô. Cùng khuôn giả lập với `test_cach_ly_khoa_phong.py::
		TestC3ThieuCotKhoaFailClosed` — mock `frappe.db.has_column`, không
		đụng DDL thật."""
		from unittest.mock import patch as mock_patch

		from erpnext.selling.doctype.sales_order.sales_order import make_delivery_note

		so = self._so(self.khoa_huyethoc)
		dn = make_delivery_note(so.name)

		# Chốt cache cấp tiến trình — reset TRƯỚC/SAU để không ăn theo kết
		# quả (True, cột THẬT tồn tại trên site test) của lần gọi trước.
		portal_context._cot_khoa_ton_tai = None
		self.addCleanup(setattr, portal_context, "_cot_khoa_ton_tai", None)
		# `_cot_khoa_phong_ton_tai()` tự ghi Error Log khi thiếu cột —
		# `tabError Log` là MyISAM, sống qua rollback, phải tự dọn.
		self.addCleanup(
			frappe.db.delete, "Error Log",
			{"method": "Thiếu cột Sales Order.custom_khoa_phong"},
		)

		with mock_patch("frappe.db.has_column", return_value=False):
			self.assertIsNone(delivery_hook._khoa_phong_dau_tien(dn))
