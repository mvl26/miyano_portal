"""Phiếu đề xuất cũ còn kẹt ở "Chờ duyệt sửa".

Khoa không còn xin sửa đơn đã duyệt (patch v1_44 bỏ vòng báo giá trên Sales
Order). Phiếu cũ đã gửi yêu cầu xin sửa trước bản đó vẫn đứng ở "Chờ duyệt
sửa"; lối ra duy nhất là quản lý từ chối (`de_xuat_tu_choi_sua`), đơn giữ
nguyên số đã duyệt.
"""

import frappe
from frappe.tests.utils import FrappeTestCase

from miyano_portal.api import de_xuat
from miyano_portal.miyano_portal.doctype.portal_de_xuat_mua.portal_de_xuat_mua import (
	SO_LUONG_XIN_SUA_TRONG,
	TRANG_THAI_CHO_DUYET_SUA,
	TRANG_THAI_NHAP,
)
from miyano_portal.tests import don_mua_le_cu
from miyano_portal.tests.fixtures_de_xuat import dung_fixture


def _don_phieu_cu():
	"""Dọn Sales Order test TRƯỚC khi dọn phiếu, và hạ trạng thái phiếu cũ về
	Nháp TRƯỚC KHI `dung_fixture()` force-delete. Cùng khuôn `test_de_xuat_
	duyet.py::_don_phieu_cu`."""
	for r in frappe.get_all(
		"Sales Order", filters={"customer": ["like", "_TEST DX%"], "docstatus": 0}
	):
		frappe.delete_doc("Sales Order", r.name, force=True, ignore_permissions=True)
	frappe.db.sql(
		"""UPDATE `tabPortal De Xuat Mua` SET trang_thai = %s
		   WHERE customer LIKE '\\_TEST DX%%'""",
		TRANG_THAI_NHAP,
	)


def _dam_bao_thanh_vien(email, customer, vai_tro, khoa_phong):
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
	"""Cùng lý do `test_de_xuat_duyet.py` — `tao_sales_order` cần Contact
	gắn đúng Customer để không ném "Contact Person does not belong to..."."""
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


class TestDeXuatTuChoiSua(FrappeTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		_don_phieu_cu()
		f = dung_fixture(self)
		self.kh_a = f.kh_a
		self.item = f.item
		self.khoa_huyethoc = f.khoa_huyethoc

		self.user_quan_ly = _dam_bao_thanh_vien(
			"dxsua.ql@demo.miyano", self.kh_a, "Quản lý", None
		)
		self.user_huyethoc = _dam_bao_thanh_vien(
			"dxsua.huyethoc@demo.miyano", self.kh_a, "Nhân viên khoa",
			self.khoa_huyethoc,
		)

		# Phiếu quản lý đã duyệt 10 hộp, có đơn đứng sau; rồi dựng thẳng trạng
		# thái phiếu cũ đã xin sửa thành 100 (không còn đường nào sinh ra nó).
		doc = frappe.get_doc({
			"doctype": "Portal De Xuat Mua",
			"customer": self.kh_a, "khoa_phong": self.khoa_huyethoc,
			"items": [{"item_code": self.item, "so_luong_de_xuat": 10}],
		})
		doc.insert(ignore_permissions=True)
		doc.ly_do_yeu_cau = "cần gấp"
		doc.gui_duyet()
		doc.reload()
		kq = don_mua_le_cu.duyet_thanh_don(doc.name, self.user_quan_ly)
		self.don = kq["sales_order"]
		self.phieu = kq["de_xuat"]
		frappe.db.set_value(
			"Portal De Xuat Mua", self.phieu, "trang_thai", TRANG_THAI_CHO_DUYET_SUA,
			update_modified=False,
		)
		dong = frappe.get_doc("Portal De Xuat Mua", self.phieu).items[0]
		frappe.db.set_value(
			dong.doctype, dong.name, "so_luong_xin_sua", 100, update_modified=False
		)

	def tearDown(self):
		frappe.set_user("Administrator")

	def test_quan_ly_tu_choi_sua_thi_don_giu_nguyen(self):
		frappe.set_user(self.user_quan_ly)
		de_xuat.de_xuat_tu_choi_sua(self.phieu, "Vượt dự toán quý")
		so = frappe.get_doc("Sales Order", self.don)
		self.assertEqual(so.items[0].qty, 10)
		doc = frappe.get_doc("Portal De Xuat Mua", self.phieu)
		self.assertEqual(doc.trang_thai, "Đã duyệt")
		self.assertEqual(doc.items[0].so_luong_duyet, 10)
		self.assertEqual(doc.items[0].ghi_chu_quan_ly, "Vượt dự toán quý")
		# Về SENTINEL "chưa có yêu cầu" (-1), không phải 0: 0 là một giá trị
		# xin sửa hợp lệ ("xin bỏ dòng này").
		self.assertEqual(doc.items[0].so_luong_xin_sua, SO_LUONG_XIN_SUA_TRONG)

	def test_nhan_vien_khong_tu_choi_sua_duoc(self):
		frappe.set_user(self.user_huyethoc)
		with self.assertRaises(frappe.PermissionError):
			de_xuat.de_xuat_tu_choi_sua(self.phieu, "không đủ ngân sách")
		self.assertEqual(
			frappe.db.get_value("Portal De Xuat Mua", self.phieu, "trang_thai"),
			TRANG_THAI_CHO_DUYET_SUA,
		)

	def test_tu_choi_sua_bat_buoc_ly_do(self):
		frappe.set_user(self.user_quan_ly)
		with self.assertRaises(frappe.ValidationError) as ctx:
			de_xuat.de_xuat_tu_choi_sua(self.phieu, "  ")
		self.assertIn("bắt buộc", str(ctx.exception))
		self.assertEqual(
			frappe.db.get_value("Portal De Xuat Mua", self.phieu, "trang_thai"),
			TRANG_THAI_CHO_DUYET_SUA,
		)

	def test_tu_choi_sua_tu_trang_thai_cho_duyet_thi_bi_chan(self):
		"""I3 — cạnh "→ Đã duyệt" cũng hợp lệ từ "Chờ duyệt": thiếu chốt
		trạng thái thì phiếu chưa có đơn bị đẩy sang "Đã duyệt" giả."""
		doc = frappe.get_doc({
			"doctype": "Portal De Xuat Mua",
			"customer": self.kh_a, "khoa_phong": self.khoa_huyethoc,
			"items": [{"item_code": self.item, "so_luong_de_xuat": 3}],
		})
		doc.insert(ignore_permissions=True)
		doc.ly_do_yeu_cau = "cần gấp"
		doc.gui_duyet()
		doc.reload()
		with self.assertRaises(frappe.ValidationError) as ctx:
			doc.tu_choi_sua("không hợp lệ")
		self.assertIn("không có yêu cầu xin sửa", str(ctx.exception))
		doc.reload()
		self.assertEqual(doc.trang_thai, "Chờ duyệt")
		self.assertFalse(doc.sales_order)
