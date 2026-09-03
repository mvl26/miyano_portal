"""Màn chi tiết GỘP (03/09/2026) — hai nửa của MỘT yêu cầu trên một màn.

Trước bản này, chi tiết một yêu cầu nằm ở HAI màn: `DeXuatDetail.vue`
(`/yeu-cau/phieu/:ten`) và `OrderDetail.vue` (`/yeu-cau/don/:name`). Khoa
xin 100, quản lý duyệt 40, Miyano giao 25 — ba con số của MỘT việc, ở hai
trang, nối với nhau bằng một cái link.

Hai bổ sung backend ở đây là thứ làm màn gộp CHẠY ĐƯỢC:
  * `portal_order_track` trả `de_xuat` — vào bằng đường ĐƠN thì phải tìm
    ngược ra phiếu, mà `Sales Order.name` KHÔNG suy ra `Portal De Xuat
    Mua.name` (hai naming khác nhau);
  * `de_xuat_chi_tiet` trả giá/đã giao THEO DÒNG — bảng mặt hàng gộp làm
    một, và phép nối phiếu↔đơn phải làm ở SERVER: `frontend/` không có hạ
    tầng test nào (package.json chỉ có `build`), nên một hàm nối viết bằng
    JS là một hàm không ai canh.
"""

import frappe
from frappe.tests.utils import FrappeTestCase

from miyano_portal.api import de_xuat, portal
from miyano_portal.miyano_portal.doctype.portal_de_xuat_mua.portal_de_xuat_mua import (
	TRANG_THAI_NHAP,
)
from miyano_portal.tests.fixtures_de_xuat import dung_fixture

COMPANY = "Miyano Việt Nam"


def _don_phieu_cu():
	"""Dọn Sales Order test TRƯỚC khi dọn phiếu, và hạ phiếu cũ về Nháp
	TRƯỚC KHI `dung_fixture()` force-delete (`on_trash` chặn xoá phiếu đã
	gửi duyệt). Cùng khuôn `test_yeu_cau_list.py::_don_phieu_cu`."""
	for r in frappe.get_all(
		"Sales Order", filters={"customer": ["like", "_TEST DX%"]},
		fields=["name", "docstatus"],
	):
		if r.docstatus == 1:
			frappe.get_doc("Sales Order", r.name).cancel()
		frappe.delete_doc("Sales Order", r.name, force=True, ignore_permissions=True)
	frappe.db.sql(
		"""UPDATE `tabPortal De Xuat Mua` SET trang_thai = %s
		   WHERE customer LIKE '\\_TEST DX%%'""",
		TRANG_THAI_NHAP,
	)


class TestChiTietGopBackend(FrappeTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		_don_phieu_cu()
		f = dung_fixture(self)
		self.kh_a = f.kh_a
		self.khoa_a = f.khoa_huyethoc
		self.item = f.item
		self.quan_ly = self._thanh_vien("dxgop.ql@demo.miyano", "Quản lý", None)
		self.nhan_vien = self._thanh_vien(
			"dxgop.nv@demo.miyano", "Nhân viên khoa", self.khoa_a
		)

	def tearDown(self):
		frappe.set_user("Administrator")

	def _thanh_vien(self, email, vai_tro, khoa_phong):
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
			"customer": self.kh_a, "vai_tro": vai_tro,
			"khoa_phong": khoa_phong, "active": 1,
		}
		if ten_tv:
			frappe.db.set_value("Portal Member", ten_tv, gia_tri)
		else:
			frappe.get_doc({
				"doctype": "Portal Member", "user": email, **gia_tri,
			}).insert(ignore_permissions=True)
		contact = frappe.db.get_value("Contact", {"user": email})
		if contact and not frappe.db.exists("Dynamic Link", {
			"parent": contact, "parenttype": "Contact",
			"link_doctype": "Customer", "link_name": self.kh_a,
		}):
			c = frappe.get_doc("Contact", contact)
			c.append("links", {"link_doctype": "Customer", "link_name": self.kh_a})
			c.save(ignore_permissions=True)
		return email

	def _phieu_da_duyet(self, so_luong=10):
		"""Phiếu đi qua ĐƯỜNG DUYỆT THẬT (`de_xuat_duyet.duyet_va_tao_don`),
		KHÔNG gán tay `phieu.sales_order` — gán tay là ghim một trạng thái
		rồi đo lại chính nó, đúng kiểu fixture-che-cổng dự án đã dính bảy
		lần (xem docstring `test_yeu_cau_list.py`)."""
		doc = frappe.get_doc({
			"doctype": "Portal De Xuat Mua",
			"customer": self.kh_a, "khoa_phong": self.khoa_a,
			"ly_do_yeu_cau": "Hết găng tay cỡ M",
			"items": [{"item_code": self.item, "so_luong_de_xuat": so_luong}],
		}).insert(ignore_permissions=True)
		frappe.db.set_value("Portal De Xuat Mua", doc.name, "owner", self.nhan_vien)
		doc.reload()
		doc.gui_duyet()
		from miyano_portal import de_xuat_duyet
		de_xuat_duyet.duyet_va_tao_don(doc.name, self.quan_ly)
		doc.reload()
		return doc

	def test_order_track_tra_ten_phieu_dung_sau_don(self):
		"""Vào màn bằng đường ĐƠN thì phải tìm ngược ra phiếu — `Sales
		Order.name` không suy ra được `Portal De Xuat Mua.name`."""
		phieu = self._phieu_da_duyet()
		frappe.set_user(self.quan_ly)
		kq = portal.portal_order_track(order=phieu.sales_order)
		self.assertEqual(kq["de_xuat"], phieu.name)

	def test_order_track_tra_phan_tram_da_giao(self):
		"""Giai đoạn "Đã giao" đòi `per_delivered >= 100` (Ruling P42) —
		`milestones[delivering].done` KHÔNG thay được: cờ đó là `> 0`, giao
		một thùng cũng bật. Màn gộp dùng giai đoạn này để quyết định thu gọn
		khối "Yêu cầu & duyệt", nên suy sai là thu gọn quá sớm."""
		phieu = self._phieu_da_duyet()
		frappe.db.set_value(
			"Sales Order", phieu.sales_order, "per_delivered", 40,
			update_modified=False,
		)
		frappe.set_user(self.quan_ly)
		kq = portal.portal_order_track(order=phieu.sales_order)
		self.assertEqual(float(kq["per_delivered"]), 40.0)

	def test_order_track_don_khong_co_phieu_tra_chuoi_rong(self):
		"""~102 đơn cũ có TRƯỚC luồng duyệt không có phiếu nào đứng sau.
		Trả `""` (không phải thiếu khoá): màn gộp đọc khoá này để quyết
		định có nạp nửa phiếu hay không, và một khoá vắng mặt buộc client
		phải đoán."""
		so = frappe.get_doc({
			"doctype": "Sales Order", "customer": self.kh_a, "company": COMPANY,
			"transaction_date": frappe.utils.today(),
			"delivery_date": frappe.utils.add_days(frappe.utils.today(), 3),
			"items": [{
				"item_code": self.item, "qty": 1, "rate": 1000,
				"delivery_date": frappe.utils.add_days(frappe.utils.today(), 3),
			}],
		}).insert(ignore_permissions=True)
		frappe.set_user(self.quan_ly)
		kq = portal.portal_order_track(order=so.name)
		self.assertEqual(kq["de_xuat"], "")
