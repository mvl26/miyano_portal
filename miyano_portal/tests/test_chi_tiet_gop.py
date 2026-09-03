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

	def test_chi_tiet_tra_gia_va_da_giao_theo_dong(self):
		"""Bảng mặt hàng của màn gộp là MỘT bảng: SL xin / SL duyệt (của
		phiếu) đứng cạnh Đơn giá / Đã giao (của đơn). Phép nối làm ở ĐÂY,
		không ở JS — `frontend/` không có test nào, và đây cũng là truy vấn
		`Sales Order Item` mà hàm này ĐÃ chạy sẵn cho `so_luong_tren_don`
		(Ruling P51), nên không tốn thêm một vòng hỏi CSDL nào."""
		# `delivered_qty` PHẢI khác 0: `frappe._dict` trả `None` cho khoá
		# vắng mặt (không ném lỗi), nên nếu ai lỡ xoá "delivered_qty" khỏi
		# `fields=[...]` của truy vấn, `float(tren_don.delivered_qty or 0)`
		# vẫn ra 0.0 y hệt kỳ vọng cũ — test xanh giả. Chọn 3 (khác 1500 và
		# 15000) để nếu code map nhầm cột thì khẳng định cũng đỏ.
		phieu = self._phieu_da_duyet(so_luong=10)
		frappe.db.set_value(
			"Sales Order Item",
			{"parent": phieu.sales_order, "item_code": self.item},
			{"rate": 1500, "amount": 15000, "delivered_qty": 3},
			update_modified=False,
		)
		frappe.set_user(self.quan_ly)
		kq = de_xuat.de_xuat_chi_tiet(ten=phieu.name)
		dong = next(d for d in kq["items"] if d["item_code"] == self.item)
		self.assertEqual(float(dong["don_gia_tren_don"]), 1500.0)
		self.assertEqual(float(dong["thanh_tien_tren_don"]), 15000.0)
		self.assertEqual(float(dong["da_giao_tren_don"]), 3.0)

	def test_chi_tiet_phieu_chua_co_don_tra_None_khong_phai_0(self):
		"""`0` và "chưa có đơn" là HAI ca khác nhau, đừng gộp — cùng lý do
		`so_luong_tren_don` đã trả `None` (Ruling P51). Một bảng in `0 ₫`
		cho phiếu Chờ duyệt là nói với khoa rằng hàng của họ giá 0."""
		doc = frappe.get_doc({
			"doctype": "Portal De Xuat Mua",
			"customer": self.kh_a, "khoa_phong": self.khoa_a,
			"ly_do_yeu_cau": "x",
			"items": [{"item_code": self.item, "so_luong_de_xuat": 5}],
		}).insert(ignore_permissions=True)
		frappe.db.set_value("Portal De Xuat Mua", doc.name, "owner", self.nhan_vien)
		doc.reload()
		doc.gui_duyet()
		frappe.set_user(self.quan_ly)
		kq = de_xuat.de_xuat_chi_tiet(ten=doc.name)
		dong = kq["items"][0]
		self.assertIsNone(dong["don_gia_tren_don"])
		self.assertIsNone(dong["thanh_tien_tren_don"])
		self.assertIsNone(dong["da_giao_tren_don"])

	# --- Review Task 7a (Critical 1) — `giai_doan` phải là ĐÚNG kết quả của
	# `_sql_giai_doan()`, không phải một bản suy lại ở client. Hai bài dưới
	# đây khớp trực tiếp hai chỗ lệch reviewer đã đối chiếu tay và bắt được
	# trong `ChiTietYeuCau.vue` bản đầu — cả hai đều phải ĐỎ nếu backend
	# thôi không trả `giai_doan`, hoặc trả sai theo đúng lỗi cũ.

	def test_order_track_tra_giai_doan_tu_choi_khi_miyano_tu_choi(self):
		"""Bài canh đúng ca đang hỏng: `status_vi` của một đơn Miyano từ chối
		là "Miyano đã từ chối" (`_so_status_vi_full`), một chuỗi KHÁC hằng
		trạng thái PHIẾU 'Từ chối' — bản suy client cũ so `d.status_vi ===
		'Từ chối'`, không bao giờ khớp, và đơn rơi hết nhánh ra 'da_duyet'.
		`portal_order_track` phải tự trả đúng khoá `giai_doan`, không để
		client đoán lại phép so đó."""
		phieu = self._phieu_da_duyet()
		frappe.db.set_value(
			"Sales Order", phieu.sales_order, "workflow_state", "Từ chối",
			update_modified=False,
		)
		frappe.set_user(self.quan_ly)
		kq = portal.portal_order_track(order=phieu.sales_order)
		self.assertEqual(kq["giai_doan"], "tu_choi")

	def test_chi_tiet_giai_doan_phieu_thang_truoc_du_da_co_don(self):
		"""Thứ tự nhánh của `_sql_giai_doan()` là CÓ CHỦ Ý: trạng thái PHIẾU
		thắng trước trạng thái ĐƠN. Một phiếu đang 'Chờ duyệt' dù `sales_
		order` đã có giá trị (ca xin sửa/khớp lại) thì thứ nó đang CHỜ vẫn là
		quản lý, không phải Miyano — phải ra 'cho_duyet', không phải
		'da_duyet' hay giai đoạn nào suy từ đơn."""
		phieu = self._phieu_da_duyet()
		frappe.db.set_value(
			"Portal De Xuat Mua", phieu.name, "trang_thai", "Chờ duyệt",
			update_modified=False,
		)
		frappe.set_user(self.quan_ly)
		kq = de_xuat.de_xuat_chi_tiet(ten=phieu.name)
		self.assertEqual(kq["giai_doan"], "cho_duyet")
