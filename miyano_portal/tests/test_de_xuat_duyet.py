"""Đường duyệt → Sales Order (Task 6, spec §5.6).

`de_xuat_duyet.duyet_va_tao_don()` là hàm module DUY NHẤT tạo Sales Order từ
một phiếu đề xuất — nó lo hạn mức + giá + tạo đơn rồi gọi `doc.duyet()`
(Task 3), nơi DUY NHẤT viết trạng thái "Đã duyệt" + khối truy vết. Ba
endpoint (`de_xuat_duyet_phieu`/`de_xuat_tu_choi`/`de_xuat_huy`) là chốt
quyền — chỉ quản lý mới gọi được, đúng khuôn cách ly khoa/khách hàng đã
dựng ở Task 4/5.

BA LỚP, không dồn vào một — mỗi lớp có DB riêng (`FrappeTestCase` rollback
MỘT LẦN mỗi CLASS, và `addClassCleanup` chạy NGAY sau khi lớp đó xong, tức
là cách ly ĐƯỢC giữa các lớp dù không cách ly được giữa các test method
trong CÙNG một lớp):

  * `TestDeXuatDuyet` — dùng chế độ "Mua lẻ" cho phần lớn test (không cần
    Item Price/Blanket Order): duyệt sinh đơn, truy vết, điều chỉnh trước
    duyệt, từ chối, huỷ.
  * `TestDeXuatDuyetHanMuc` — RIÊNG một lớp vì nó dựng một `Blanket Order`
    thật cho `_TEST DX A`. Nếu gộp chung lớp trên, mặt hàng `_TEST DX ITEM`
    sẽ lọt vào `items_thuoc_hdnt_hieu_luc(kh_a)` (BR-R7) và chặn NHẦM các
    test Mua lẻ khác trong CÙNG lớp (vì không rollback giữa các method).
  * `TestDeXuatMaTraCuuTrenDonHang` — Step 4b, `custom_ma_tra_cuu` phơi qua
    `portal_order_history`.
"""

import json

import frappe
from frappe.tests.utils import FrappeTestCase

from miyano_portal import de_xuat_duyet, portal_context
from miyano_portal.api import de_xuat
from miyano_portal.api import portal
from miyano_portal.miyano_portal.doctype.portal_de_xuat_mua.portal_de_xuat_mua import (
	TRANG_THAI_NHAP,
)
from miyano_portal.tests.fixtures_de_xuat import dung_fixture

COMPANY = "Miyano Việt Nam"
WAREHOUSE = "Stores - MYN"


def _don_phieu_cu():
	"""Hạ mọi phiếu `_TEST DX%` về Nháp — bẫy đã biết (`on_trash` chặn xoá
	phiếu đã gửi duyệt). Chạy TRƯỚC `dung_fixture()`, cùng pattern
	`test_de_xuat_endpoint.py`.

	Bẫy THỨ TƯ, riêng của Task 6 (khác ba bẫy brief đã liệt kê) — Task 6 là
	task ĐẦU TIÊN trong bộ test `_TEST DX%` thực sự tạo ra Sales Order thật
	qua `duyet_va_tao_don`. `dung_fixture()` FORCE DELETE phiếu cũ mỗi
	`setUp`; Frappe (`revert_series_if_last`) LÙI bộ đếm đặt tên khi bản ghi
	bị xoá là bản MỚI NHẤT của chuỗi "DXM-2026-", nên phiếu ở method SAU có
	thể được cấp LẠI đúng cái tên phiếu ở method TRƯỚC vừa xoá. Nếu Sales
	Order của method trước còn sống với `custom_request_id` = đúng tên đó,
	`tao_sales_order` (BR-O12, chống trùng đơn — CỐ Ý, không phải lỗi) sẽ
	coi phiếu MỚI là một cú bấm-lại của đơn CŨ và trả về NGUYÊN Sales Order
	cũ, khiến method sau đọc nhầm dữ liệu của method trước dù hai phiếu
	logic khác nhau hoàn toàn. Dọn Sales Order test TRƯỚC khi dọn phiếu, cắt
	đứt khả năng trùng tên đè lên một `custom_request_id` còn sống."""
	# `docstatus: 0` — mọi Sales Order lớp này tạo ra đều là NHÁP (cổng
	# không submit). Giới hạn tường minh để nếu sau này có test submit một
	# đơn, xoá nó sẽ ném lỗi RÕ RÀNG ngay tại đó thay vì làm `setUp` của MỌI
	# method sau vỡ với một lỗi không liên quan gì tới nguyên nhân thật.
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
	"""Frappe tự sinh MỘT `Contact` cho mọi User mới (`user.create_contact`),
	KHÔNG gắn Customer nào. `dat_hang.tao_sales_order` (qua
	`_xay_don_hdnt`/`_xay_don_ban_le`) đọc `frappe.session.user` để điền
	`Sales Order.contact_person` bằng đúng Contact đó — thiếu Dynamic Link
	tới khách hàng thì ERPNext (`validate_party_contact`) ném "Contact
	Person does not belong to {customer}" ngay lúc insert. Một Portal
	Member THẬT được Miyano tạo tay sẽ có bước gắn Contact-Customer khi
	onboard; test tự làm bước đó ở đây cho khớp, KHÔNG phải việc của
	`_dam_bao_thanh_vien` (fixture dùng chung, không phải path test này)."""
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


def _item2():
	"""Vật tư THỨ HAI, riêng của file này — không đụng `fixtures_de_xuat.py`
	(dùng chung nhiều task), chỉ cần tồn tại để có một dòng hàng khác mã."""
	ten = "_TEST DX DUYET ITEM 2"
	if not frappe.db.exists("Item", ten):
		frappe.get_doc({
			"doctype": "Item", "item_code": ten, "item_name": ten,
			"item_group": frappe.db.get_value("Item Group", {}, "name"),
			"stock_uom": "Nos", "is_stock_item": 0,
		}).insert(ignore_permissions=True)
	return ten


class TestDeXuatDuyet(FrappeTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		_don_phieu_cu()
		f = dung_fixture(self)
		self.kh_a = f.kh_a
		self.item = f.item
		self.item2 = _item2()
		self.khoa_huyethoc = f.khoa_huyethoc

		self.user_quan_ly = _dam_bao_thanh_vien(
			"dxduyet.ql@demo.miyano", self.kh_a, "Quản lý", None
		)
		self.user_huyethoc = _dam_bao_thanh_vien(
			"dxduyet.huyethoc@demo.miyano", self.kh_a, "Nhân viên khoa",
			self.khoa_huyethoc,
		)

		# Phiếu "Chờ duyệt" dùng chung cho phần lớn test — mỗi test method có
		# `setUp` riêng (chạy lại mỗi lần) nên không lo test này ăn phiếu của
		# test khác, dù DB không rollback giữa các method trong cùng lớp.
		self.phieu_huyethoc = self._cho_duyet()

	def tearDown(self):
		frappe.set_user("Administrator")

	# -- fixture riêng của lớp này --------------------------------------

	def _nhap(self, items=None):
		doc = frappe.get_doc({
			"doctype": "Portal De Xuat Mua",
			"customer": self.kh_a, "khoa_phong": self.khoa_huyethoc,
			"loai_don": "Mua lẻ",
			"items": items or [{"item_code": self.item, "so_luong_de_xuat": 5}],
		})
		doc.insert(ignore_permissions=True)
		return doc

	def _cho_duyet(self, items=None):
		"""Đưa phiếu tới "Chờ duyệt" VÀ điền `so_luong_duyet` = `so_luong_de_xuat`
		cho mọi dòng — không hàm nào trong app tự làm việc này (đã xác nhận:
		`gui_duyet()` không đụng `so_luong_duyet`), quản lý phải tự gõ hoặc
		qua `_ap_dieu_chinh`. Test dựng sẵn để không phải lặp lại ở mỗi ca."""
		doc = self._nhap(items)
		doc.ly_do_yeu_cau = "cần gấp"
		doc.gui_duyet()
		doc.reload()
		for row in doc.items:
			row.so_luong_duyet = row.so_luong_de_xuat
		doc.save(ignore_permissions=True)
		doc.reload()
		return doc

	def _cho_duyet_hai_dong(self):
		return self._cho_duyet(items=[
			{"item_code": self.item, "so_luong_de_xuat": 5},
			{"item_code": self.item2, "so_luong_de_xuat": 5},
		])

	# ---- Step 1: duyệt sinh Sales Order ------------------------------

	def test_duyet_sinh_sales_order_chi_tu_dong_co_so_luong_duyet(self):
		"""§5.3 — dòng hạ về 0 KHÔNG đi vào đơn, nhưng VẪN CÒN trên phiếu."""
		doc = self._cho_duyet_hai_dong()
		doc.items[1].so_luong_duyet = 0
		doc.save(ignore_permissions=True)
		kq = de_xuat_duyet.duyet_va_tao_don(doc.name, "Administrator")
		so = frappe.get_doc("Sales Order", kq["sales_order"])
		self.assertEqual(len(so.items), 1)
		doc.reload()
		self.assertEqual(len(doc.items), 2)          # phiếu gốc còn nguyên
		self.assertEqual(doc.items[1].so_luong_de_xuat, 5)

	def test_don_mang_dung_khoa_cua_phieu(self):
		"""Chốt của cả đề án: đơn sinh ra PHẢI mang khoa, nếu không thì
		chính nhân viên khoa đó không mở lại được đơn mình vừa đặt."""
		doc = self.phieu_huyethoc
		kq = de_xuat_duyet.duyet_va_tao_don(doc.name, "Administrator")
		self.assertEqual(
			frappe.db.get_value("Sales Order", kq["sales_order"], "custom_khoa_phong"),
			doc.khoa_phong,
		)

	def test_don_tro_nguoc_ve_phieu_goc(self):
		doc = self.phieu_huyethoc
		kq = de_xuat_duyet.duyet_va_tao_don(doc.name, "Administrator")
		self.assertEqual(
			frappe.db.get_value("Sales Order", kq["sales_order"], "custom_de_xuat"),
			doc.name,
		)
		self.assertEqual(
			frappe.db.get_value("Sales Order", kq["sales_order"], "custom_ma_tra_cuu"),
			doc.ma_de_xuat,
		)

	def test_mua_le_khong_dong_dau_gia_va_khong_canh_bao(self):
		"""§5.6 bẫy #2 chỉ áp dụng HĐNT — Mua lẻ không tra giá ở đâu cả
		(§4.5), nên `don_gia` phải RỖNG và không có gì để cảnh báo."""
		doc = self.phieu_huyethoc
		self.assertFalse(doc.items[0].don_gia)
		kq = de_xuat_duyet.duyet_va_tao_don(doc.name, "Administrator")
		self.assertEqual(kq["canh_bao_gia"], [])

	def test_bam_duyet_hai_lan_khong_tao_hai_don(self):
		"""§5.2 — `request_id` chuyển xuống tầng phiếu: bấm Duyệt hai lần trả
		về CÙNG một Sales Order, không tạo đơn trùng (BR-O12)."""
		doc = self.phieu_huyethoc
		a = de_xuat_duyet.duyet_va_tao_don(doc.name, "Administrator")
		doc.reload()
		doc.trang_thai = "Chờ duyệt"      # giả lập bấm lại khi UI chưa kịp cập nhật
		doc.db_update()
		b = de_xuat_duyet.duyet_va_tao_don(doc.name, "Administrator")
		self.assertEqual(a["sales_order"], b["sales_order"])

	def test_khong_con_dong_nao_thi_duyet_bi_chan(self):
		"""VẾ ÂM cần cho §5.3 — hạ hết mọi dòng về 0 thì không có gì để đặt."""
		doc = self.phieu_huyethoc
		doc.items[0].so_luong_duyet = 0
		doc.save(ignore_permissions=True)
		with self.assertRaises(frappe.ValidationError) as ctx:
			de_xuat_duyet.duyet_va_tao_don(doc.name, "Administrator")
		self.assertIn("số lượng duyệt lớn hơn 0", str(ctx.exception))

	# ---- Chốt quyền endpoint duyệt ------------------------------------

	def test_nhan_vien_khong_duyet_duoc(self):
		frappe.set_user(self.user_huyethoc)
		with self.assertRaises(frappe.PermissionError):
			de_xuat.de_xuat_duyet_phieu(self.phieu_huyethoc.name)

	def test_quan_ly_duyet_duoc(self):
		"""VẾ DƯƠNG."""
		frappe.set_user(self.user_quan_ly)
		kq = de_xuat.de_xuat_duyet_phieu(self.phieu_huyethoc.name)
		self.assertTrue(kq["sales_order"])

	def test_duyet_ghi_du_khoi_truy_vet(self):
		"""§5.2 — người duyệt, thời điểm, tư cách."""
		frappe.set_user(self.user_quan_ly)
		de_xuat.de_xuat_duyet_phieu(self.phieu_huyethoc.name)
		doc = frappe.get_doc("Portal De Xuat Mua", self.phieu_huyethoc.name)
		self.assertEqual(doc.nguoi_duyet, self.user_quan_ly)
		self.assertTrue(doc.thoi_diem_duyet)
		self.assertEqual(doc.duyet_voi_tu_cach, "Quản lý chính")

	# ---- `_ap_dieu_chinh` qua endpoint (QĐ-KP-3) ----------------------

	def test_quan_ly_dieu_chinh_so_luong_truoc_khi_duyet(self):
		"""VẾ DƯƠNG — quản lý hạ số lượng duyệt qua `dieu_chinh` TRƯỚC khi
		phiếu được duyệt, đơn sinh ra phải mang đúng số đã điều chỉnh."""
		doc = self.phieu_huyethoc
		frappe.set_user(self.user_quan_ly)
		dc = {"items": [{"item_code": self.item, "so_luong_duyet": 2}]}
		kq = de_xuat.de_xuat_duyet_phieu(doc.name, dieu_chinh=json.dumps(dc))
		so = frappe.get_doc("Sales Order", kq["sales_order"])
		self.assertEqual(len(so.items), 1)
		self.assertEqual(so.items[0].qty, 2)

	def test_quan_ly_them_mat_hang_qua_dieu_chinh(self):
		"""§5.3 — dòng "Quản lý thêm" bắt buộc `so_luong_de_xuat = 0`, và đi
		vào đơn với đúng `so_luong_duyet` quản lý gõ."""
		doc = self.phieu_huyethoc
		frappe.set_user(self.user_quan_ly)
		dc = {"items": [
			{"item_code": self.item, "so_luong_duyet": 5},
			{"item_code": self.item2, "so_luong_duyet": 3},
		]}
		kq = de_xuat.de_xuat_duyet_phieu(doc.name, dieu_chinh=json.dumps(dc))
		so = frappe.get_doc("Sales Order", kq["sales_order"])
		theo_ma = {r.item_code: r.qty for r in so.items}
		self.assertEqual(theo_ma.get(self.item2), 3)
		pdoc = frappe.get_doc("Portal De Xuat Mua", doc.name)
		dong_moi = next(r for r in pdoc.items if r.item_code == self.item2)
		self.assertEqual(dong_moi.nguon_dong, "Quản lý thêm")
		self.assertEqual(dong_moi.so_luong_de_xuat, 0)

	# ---- de_xuat_tu_choi -----------------------------------------------

	def test_nhan_vien_khong_tu_choi_duoc(self):
		frappe.set_user(self.user_huyethoc)
		with self.assertRaises(frappe.PermissionError):
			de_xuat.de_xuat_tu_choi(self.phieu_huyethoc.name, "thiếu chứng từ")

	def test_quan_ly_tu_choi_duoc(self):
		"""VẾ DƯƠNG."""
		frappe.set_user(self.user_quan_ly)
		de_xuat.de_xuat_tu_choi(self.phieu_huyethoc.name, "thiếu chứng từ")
		doc = frappe.get_doc("Portal De Xuat Mua", self.phieu_huyethoc.name)
		self.assertEqual(doc.trang_thai, "Từ chối")
		self.assertEqual(doc.ly_do_tu_choi, "thiếu chứng từ")

	# ---- de_xuat_huy -----------------------------------------------------

	def test_nhan_vien_khong_huy_duoc_phieu_da_gui(self):
		"""§5.4b — từ Chờ duyệt trở đi CHỈ quản lý huỷ được."""
		frappe.set_user(self.user_huyethoc)
		with self.assertRaises(frappe.PermissionError):
			de_xuat.de_xuat_huy(self.phieu_huyethoc.name)

	def test_quan_ly_huy_duoc_phieu_da_gui(self):
		"""VẾ DƯƠNG."""
		frappe.set_user(self.user_quan_ly)
		de_xuat.de_xuat_huy(self.phieu_huyethoc.name)
		doc = frappe.get_doc("Portal De Xuat Mua", self.phieu_huyethoc.name)
		self.assertEqual(doc.trang_thai, "Đã huỷ")


class TestDeXuatDuyetHanMuc(FrappeTestCase):
	"""§5.6 — hạn mức HĐNT là tài nguyên CHUNG giữa các khoa CÙNG một khách
	hàng. Trừ lúc DUYỆT; hết hạn mức thì thất bại kèm TÊN KHOA đã tiêu mất,
	không im lặng cắt số lượng.

	RIÊNG một lớp — xem docstring đầu file."""

	def setUp(self):
		frappe.set_user("Administrator")
		_don_phieu_cu()
		f = dung_fixture(self)
		self.kh_a = f.kh_a
		self.item = f.item
		self.khoa_huyethoc = f.khoa_huyethoc
		self.khoa_duoc = _dam_bao_khoa(
			self.kh_a, "Dược (nội bộ, test duyệt hạn mức)", "DXDUYETHM"
		)

		self.price_list = self._tao_price_list()
		frappe.db.set_value("Customer", self.kh_a, "default_price_list", self.price_list)
		self._tao_gia(self.item, self.price_list, 100)

		# Hạn mức 5, đã dùng 3 -> còn 2. `ordered_qty` chỉ được ERPNext tự
		# cập nhật lúc SUBMIT Sales Order (`update_blanket_order`,
		# `on_submit`/`on_cancel`); cổng chỉ tạo đơn NHÁP nên set thẳng qua
		# `frappe.db.set_value`, cùng pattern `test_e1_loi_co_cau_truc.py`.
		self.bo = frappe.get_doc({
			"doctype": "Blanket Order", "blanket_order_type": "Selling",
			"customer": self.kh_a, "company": COMPANY,
			"from_date": frappe.utils.today(),
			"to_date": frappe.utils.add_days(frappe.utils.today(), 365),
			"items": [{"item_code": self.item, "qty": 5, "ordered_qty": 3, "rate": 100}],
		}).insert(ignore_permissions=True).name

		# Đơn "đã tiêu" của khoa Dược trên CÙNG hợp đồng — `_kiem_han_muc`
		# chỉ hỏi `custom_hdnt` + `docstatus < 2`, không cần đơn này SUBMIT.
		frappe.get_doc({
			"doctype": "Sales Order", "customer": self.kh_a, "company": COMPANY,
			"transaction_date": frappe.utils.today(),
			"delivery_date": frappe.utils.add_days(frappe.utils.today(), 5),
			"selling_price_list": self.price_list,
			"custom_hdnt": self.bo, "custom_khoa_phong": self.khoa_duoc,
			"items": [{"item_code": self.item, "qty": 3, "rate": 100, "warehouse": WAREHOUSE}],
		}).insert(ignore_permissions=True)

	def tearDown(self):
		frappe.set_user("Administrator")

	# -- fixture riêng của lớp này --------------------------------------

	def _tao_price_list(self):
		ten = "_TEST DX DUYET HDNT PRICE"
		if not frappe.db.exists("Price List", ten):
			frappe.get_doc({
				"doctype": "Price List", "price_list_name": ten,
				"currency": "VND", "selling": 1, "enabled": 1,
			}).insert(ignore_permissions=True)
		return ten

	def _tao_gia(self, item_code, price_list, rate):
		loc = {"item_code": item_code, "price_list": price_list, "selling": 1}
		if frappe.db.exists("Item Price", loc):
			frappe.db.set_value("Item Price", loc, "price_list_rate", rate)
		else:
			frappe.get_doc({"doctype": "Item Price", "price_list_rate": rate, **loc}).insert(
				ignore_permissions=True
			)

	def _cho_duyet_vuot_han_muc(self):
		doc = frappe.get_doc({
			"doctype": "Portal De Xuat Mua",
			"customer": self.kh_a, "khoa_phong": self.khoa_huyethoc,
			"loai_don": "HĐNT", "hdnt": self.bo,
			"items": [{"item_code": self.item, "so_luong_de_xuat": 10}],
		})
		doc.insert(ignore_permissions=True)
		doc.ly_do_yeu_cau = "cần gấp, vượt hạn mức"
		doc.gui_duyet()
		doc.reload()
		doc.items[0].so_luong_duyet = 10   # hạn mức còn lại chỉ 2 (5 - 3)
		doc.save(ignore_permissions=True)
		doc.reload()
		return doc

	def _cho_duyet_hdnt_thuong(self, so_luong=2):
		"""HĐNT trong hạn mức (còn lại 2, xem `setUp`) — dùng cho các test
		giá, không muốn vướng bẫy hạn mức của lớp này."""
		doc = frappe.get_doc({
			"doctype": "Portal De Xuat Mua",
			"customer": self.kh_a, "khoa_phong": self.khoa_huyethoc,
			"loai_don": "HĐNT", "hdnt": self.bo,
			"items": [{"item_code": self.item, "so_luong_de_xuat": so_luong}],
		})
		doc.insert(ignore_permissions=True)
		doc.ly_do_yeu_cau = "cần giá"
		doc.gui_duyet()
		doc.reload()
		doc.items[0].so_luong_duyet = so_luong
		doc.save(ignore_permissions=True)
		doc.reload()
		return doc

	def test_het_han_muc_thi_duyet_that_bai_kem_ten_khoa(self):
		"""§5.6 — không im lặng cắt số lượng xuống."""
		doc = self._cho_duyet_vuot_han_muc()
		with self.assertRaises(frappe.ValidationError) as ctx:
			de_xuat_duyet.duyet_va_tao_don(doc.name, "Administrator")
		self.assertIn("Dược", str(ctx.exception))    # tên khoa đã tiêu mất
		# Vế ÂM cũng phải giữ đúng luật §5.6: KHÔNG âm thầm cắt xuống — phiếu
		# và trạng thái không được đổi khi duyệt thất bại.
		doc.reload()
		self.assertEqual(doc.trang_thai, "Chờ duyệt")
		self.assertEqual(doc.items[0].so_luong_duyet, 10)

	def test_con_du_han_muc_thi_duyet_thanh_cong(self):
		"""VẾ DƯƠNG — bắt buộc theo ràng buộc: thiếu nó, một hàm luôn ném lỗi
		vẫn qua được test trên."""
		doc = self._cho_duyet_vuot_han_muc()
		doc.items[0].so_luong_duyet = 2    # đúng bằng phần còn lại
		doc.save(ignore_permissions=True)
		kq = de_xuat_duyet.duyet_va_tao_don(doc.name, "Administrator")
		so = frappe.get_doc("Sales Order", kq["sales_order"])
		self.assertEqual(so.items[0].qty, 2)
		self.assertEqual(so.items[0].blanket_order, self.bo)

	# ---- §5.6 bẫy #2 — đóng dấu + cảnh báo giá (vòng sửa sau report) --

	def test_gui_duyet_dong_dau_don_gia_bang_gia_hien_hanh(self):
		"""VẾ DƯƠNG — `don_gia` phải CÓ giá trị ngay sau khi gửi duyệt, đúng
		bằng giá hiện hành lúc đó (100, xem `setUp`)."""
		doc = self._cho_duyet_hdnt_thuong()
		self.assertEqual(doc.items[0].don_gia, 100)

	def test_gia_doi_giua_gui_va_duyet_thi_co_canh_bao(self):
		doc = self._cho_duyet_hdnt_thuong()
		self.assertEqual(doc.items[0].don_gia, 100)
		self._tao_gia(self.item, self.price_list, 150)    # giá đổi SAU khi gửi
		kq = de_xuat_duyet.duyet_va_tao_don(doc.name, "Administrator")
		self.assertEqual(len(kq["canh_bao_gia"]), 1)
		cb = kq["canh_bao_gia"][0]
		self.assertEqual(cb["item_code"], self.item)
		self.assertEqual(cb["gia_cu"], 100)
		self.assertEqual(cb["gia_moi"], 150)

	def test_gia_khong_doi_thi_khong_canh_bao(self):
		"""VẾ DƯƠNG — không báo động giả khi giá không hề đổi."""
		doc = self._cho_duyet_hdnt_thuong()
		kq = de_xuat_duyet.duyet_va_tao_don(doc.name, "Administrator")
		self.assertEqual(kq["canh_bao_gia"], [])

	def test_co_canh_bao_gia_van_duyet_duoc(self):
		"""Chốt bắt buộc — cảnh báo giá CHỈ mang thông tin, không được chặn
		việc duyệt; Sales Order vẫn phải sinh ra."""
		doc = self._cho_duyet_hdnt_thuong()
		self._tao_gia(self.item, self.price_list, 150)
		kq = de_xuat_duyet.duyet_va_tao_don(doc.name, "Administrator")
		self.assertTrue(kq["canh_bao_gia"])
		self.assertTrue(kq["sales_order"])
		so = frappe.get_doc("Sales Order", kq["sales_order"])
		self.assertEqual(so.items[0].qty, 2)
		# Giá tính lại tại thời điểm duyệt (vế 1 của bẫy #2) — đơn phải mang
		# giá MỚI (150), không phải giá khoa đã thấy lúc gửi (100).
		self.assertEqual(so.items[0].rate, 150)


class TestDeXuatMaTraCuuTrenDonHang(FrappeTestCase):
	"""Step 4b (QĐ-A4) — `portal_order_history` phải trả cả `name`
	(SAL-ORD-*, mã hệ thống) LẪN `ma_tra_cuu` (mã của khách), và không vỡ
	trên đơn CŨ chưa từng đi qua một phiếu đề xuất."""

	def setUp(self):
		frappe.set_user("Administrator")
		_don_phieu_cu()
		f = dung_fixture(self)
		self.kh_a = f.kh_a
		self.item = f.item
		self.khoa_huyethoc = f.khoa_huyethoc

		self.user_quan_ly = _dam_bao_thanh_vien(
			"dxduyetma.ql@demo.miyano", self.kh_a, "Quản lý", None
		)

		doc = frappe.get_doc({
			"doctype": "Portal De Xuat Mua",
			"customer": self.kh_a, "khoa_phong": self.khoa_huyethoc,
			"loai_don": "Mua lẻ",
			"items": [{"item_code": self.item, "so_luong_de_xuat": 2}],
		})
		doc.insert(ignore_permissions=True)
		doc.ly_do_yeu_cau = "cần gấp"
		doc.gui_duyet()
		doc.reload()
		doc.items[0].so_luong_duyet = 2
		doc.save(ignore_permissions=True)
		doc.reload()
		kq = de_xuat_duyet.duyet_va_tao_don(doc.name, "Administrator")
		self.don_da_duyet = kq["sales_order"]

		# 102 đơn cũ không có phiếu đề xuất đứng sau — đặt trực tiếp, KHÔNG
		# qua đường đề xuất, đúng tình huống tương thích ngược.
		self.don_cu_khong_co_de_xuat = frappe.get_doc({
			"doctype": "Sales Order", "customer": self.kh_a, "company": COMPANY,
			"transaction_date": frappe.utils.today(),
			"delivery_date": frappe.utils.add_days(frappe.utils.today(), 5),
			"selling_price_list": "Standard Selling",
			"items": [{"item_code": self.item, "qty": 1, "rate": 0, "warehouse": WAREHOUSE}],
		}).insert(ignore_permissions=True).name

	def tearDown(self):
		frappe.set_user("Administrator")

	def test_api_don_hang_tra_ca_hai_ma(self):
		frappe.set_user(self.user_quan_ly)
		rows = portal.portal_order_history()["rows"]
		r = next(x for x in rows if x["name"] == self.don_da_duyet)
		self.assertTrue(r["name"].startswith("SAL-ORD-"))   # mã hệ thống
		self.assertIn("-HUYETHOC-", r["ma_tra_cuu"])         # mã của khách

	def test_don_cu_khong_co_ma_tra_cuu_thi_khong_vo(self):
		"""Chốt tương thích ngược — phải xanh cả trước lẫn sau."""
		frappe.set_user(self.user_quan_ly)
		rows = portal.portal_order_history()["rows"]
		r = next(x for x in rows if x["name"] == self.don_cu_khong_co_de_xuat)
		self.assertFalse(r.get("ma_tra_cuu"))


class TestQuanLyDatTrucTiepTuDuyet(FrappeTestCase):
	"""Task 7, §5.5 — quản lý đặt hàng trực tiếp qua giỏ hàng vẫn sinh một
	`Portal De Xuat Mua` TỰ ĐÁNH "Đã duyệt" (`nguoi_duyet` = chính họ) đứng
	sau mỗi Sales Order: KHÔNG có hai loại đơn với hai lịch sử khác nhau
	trên hệ thống.

	QĐ điều phối viên (19/08/2026, vòng sửa sau report đầu của Task 7 — xem
	`task-7-report.md`, chữ dùng SỬA LẠI ở review M3): `portal_order_place`
	KHÔNG route qua `de_xuat_duyet.duyet_va_tao_don`. Nó vẫn gọi THẲNG
	`dat_hang.tao_sales_order` như trước Task 7 — giữ NGUYÊN cách hàm đó
	báo lỗi vượt hạn mức: ghi `frappe.local.response["loi"]` (danh sách CÓ
	CẤU TRÚC theo từng dòng hàng) RỒI MỚI `frappe.throw(..., ValidationError)`
	— nhiều test (`test_e1_loi_co_cau_truc.py` và các test E1 khác) đọc
	thẳng khoá đó. `_kiem_han_muc` (bên trong `duyet_va_tao_don`) cũng NÉM
	`ValidationError` (không phải "mềm hơn"), nhưng chỉ một câu văn xuôi
	PHẲNG, không ghi gì vào `frappe.local.response` — route qua đó sẽ MẤT
	dữ liệu có cấu trúc cho MỌI người gọi, không riêng nhân viên khoa; sáu
	tài khoản đang chạy thật đều là quản lý và đi đúng đường này mỗi ngày.
	Chỉ SAU KHI Sales Order tạo xong mới ghi một phiếu "Đã duyệt" đứng sau.

	Cũng theo QĐ đó: thiếu `Customer.custom_ma_ngan` KHÔNG được chặn đơn
	trực tiếp của quản lý (khác nhân viên GỬI DUYỆT, nơi guard cấp tài
	khoản đã bắt buộc mã ngắn từ trước) — phiếu vẫn tạo, `ma_de_xuat` để
	rỗng.
	"""

	def setUp(self):
		frappe.set_user("Administrator")
		_don_phieu_cu()
		f = dung_fixture(self)
		self.kh_a = f.kh_a
		self.item = f.item
		self.khoa_huyethoc = f.khoa_huyethoc

		# Khoa THỨ HAI trong CÙNG bệnh viện kh_a — để quản lý có gì đó khác
		# `khoa_huyethoc` mà CHỌN qua giỏ hàng (§5.5).
		self.khoa_duoc_a = _dam_bao_khoa(self.kh_a, "Dược (test task7)", "DXT7DUOC")
		# Khoa của MỘT bệnh viện KHÁC (kh_b, có sẵn trong fixture dùng
		# chung) — để kiểm quản lý kh_a không đặt hộ được khoa của kh_b.
		self.khoa_benh_vien_b = f.khoa_duoc
		# Review I1 — khoa CÙNG bệnh viện kh_a nhưng SẼ TẮT (`active=0` đặt
		# ngay trong từng test cần nó, không đặt sẵn ở đây để không ảnh
		# hưởng các test khác dùng chung `setUp`). Khác `khoa_benh_vien_b`
		# ở CHỖ SAI: cái đó sai vì khác BỆNH VIỆN, cái này sai vì đã TẮT —
		# hai điều kiện độc lập của `khoa_phong_cho_don()`, phải có test
		# riêng cho từng cái, không được để một test đại diện cho cả hai.
		self.khoa_da_tat_a = _dam_bao_khoa(
			self.kh_a, "Đã tắt (test task7)", "DXT7TAT"
		)

		self.user_quan_ly = _dam_bao_thanh_vien(
			"dxt7.ql@demo.miyano", self.kh_a, "Quản lý", None
		)
		self.user_huyethoc = _dam_bao_thanh_vien(
			"dxt7.huyethoc@demo.miyano", self.kh_a, "Nhân viên khoa",
			self.khoa_huyethoc,
		)

	def tearDown(self):
		frappe.set_user("Administrator")

	def _dat(self, khoa_phong=None, request_id=None):
		return portal.portal_order_place(
			mode="ban_le",
			items=json.dumps([{"item_code": self.item, "qty": 1}]),
			request_id=request_id or frappe.generate_hash(length=20),
			khoa_phong=khoa_phong,
		)

	# ---- khoa_phong_cho_don() trực tiếp --------------------------------
	#
	# Test 1 gốc của brief ("nhân viên khoa gửi khoa khác vẫn bị ép về khoa
	# mình") gọi qua `portal_order_place`. Nhưng §5.5 câu cuối chốt CHẶN HẲN
	# nhân viên khoa ở chính endpoint đó (xem
	# `test_nhan_vien_khoa_goi_thang_portal_order_place_bi_tu_choi_ro_rang`
	# dưới) — nên vế "client gửi khoa khác vẫn bị ép về khoa mình" chỉ còn
	# đo được ở tầng `khoa_phong_cho_don()` trực tiếp, không qua endpoint.
	# Điều phối viên đã chốt cách sửa này trong brief.

	def test_nhan_vien_khoa_gui_khoa_khac_van_bi_ep_ve_khoa_minh(self):
		"""C1 vẫn đứng: client không tự chọn khoa được — với NHÂN VIÊN."""
		frappe.set_user(self.user_huyethoc)
		self.assertEqual(
			portal_context.khoa_phong_cho_don(self.khoa_duoc_a),
			self.khoa_huyethoc,
		)

	def test_quan_ly_duoc_chon_khoa_qua_khoa_phong_cho_don(self):
		"""§5.5 — VẾ DƯƠNG của test trên: quản lý ĐƯỢC chọn."""
		frappe.set_user(self.user_quan_ly)
		self.assertEqual(
			portal_context.khoa_phong_cho_don(self.khoa_duoc_a),
			self.khoa_duoc_a,
		)

	def test_quan_ly_khong_chon_duoc_khoa_benh_vien_khac_qua_khoa_phong_cho_don(self):
		frappe.set_user(self.user_quan_ly)
		with self.assertRaises(frappe.PermissionError) as ctx:
			portal_context.khoa_phong_cho_don(self.khoa_benh_vien_b)
		self.assertIn("không thuộc", str(ctx.exception))

	def test_quan_ly_khong_chon_duoc_khoa_da_tat_cung_benh_vien_qua_khoa_phong_cho_don(self):
		"""Review I1 — điều kiện THỨ HAI của `khoa_phong_cho_don()`, ĐỘC
		LẬP với "khác bệnh viện" ở test trên: khoa CÙNG bệnh viện `kh_a`
		nhưng đã `active=0`. Trước review này, KHÔNG có test nào trong toàn
		suite chạm được vế `active` của hàm — xoá `or not kp.active` khỏi
		`khoa_phong_cho_don()` vẫn xanh hết nếu không có test này."""
		frappe.db.set_value("Customer Department", self.khoa_da_tat_a, "active", 0)
		frappe.set_user(self.user_quan_ly)
		with self.assertRaises(frappe.PermissionError) as ctx:
			portal_context.khoa_phong_cho_don(self.khoa_da_tat_a)
		self.assertIn("hoạt động", str(ctx.exception))

	def test_quan_ly_chon_toan_vien_qua_khoa_phong_cho_don(self):
		"""VẾ DƯƠNG — `None` (Toàn viện) là hợp lệ, không phải lỗi."""
		frappe.set_user(self.user_quan_ly)
		self.assertIsNone(portal_context.khoa_phong_cho_don(None))

	# ---- portal_order_place — quản lý ----------------------------------

	def test_quan_ly_dat_ho_mot_khoa(self):
		"""§5.5 — quản lý chọn khoa qua giỏ hàng, đơn mang đúng khoa đó."""
		frappe.set_user(self.user_quan_ly)
		kq = self._dat(khoa_phong=self.khoa_duoc_a)
		self.assertEqual(
			frappe.db.get_value("Sales Order", kq["sales_order"], "custom_khoa_phong"),
			self.khoa_duoc_a,
		)

	def test_quan_ly_khong_dat_duoc_cho_khoa_benh_vien_khac(self):
		frappe.set_user(self.user_quan_ly)
		with self.assertRaises(frappe.PermissionError) as ctx:
			self._dat(khoa_phong=self.khoa_benh_vien_b)
		self.assertIn("không thuộc", str(ctx.exception))

	def test_quan_ly_dat_toan_vien_thi_ma_la_CHUNG(self):
		frappe.set_user(self.user_quan_ly)
		kq = self._dat(khoa_phong=None)
		phieu = frappe.get_doc("Portal De Xuat Mua", kq["de_xuat"])
		self.assertIn("-CHUNG-", phieu.ma_de_xuat)
		self.assertEqual(phieu.trang_thai, "Đã duyệt")

	def test_moi_don_deu_co_dung_mot_phieu_dung_sau(self):
		"""§5.5 — không có hai loại đơn với hai lịch sử khác nhau."""
		frappe.set_user(self.user_quan_ly)
		kq = self._dat()
		self.assertTrue(
			frappe.db.get_value("Sales Order", kq["sales_order"], "custom_de_xuat")
		)
		self.assertEqual(
			frappe.db.get_value("Sales Order", kq["sales_order"], "custom_de_xuat"),
			kq["de_xuat"],
		)

	def test_phieu_tu_duyet_ghi_dung_nguoi_duyet_la_chinh_quan_ly(self):
		"""§5.2 — khối truy vết: `nguoi_duyet` = chính người đặt, tự duyệt."""
		frappe.set_user(self.user_quan_ly)
		kq = self._dat()
		phieu = frappe.get_doc("Portal De Xuat Mua", kq["de_xuat"])
		self.assertEqual(phieu.nguoi_duyet, self.user_quan_ly)
		self.assertEqual(phieu.duyet_voi_tu_cach, "Quản lý chính")
		self.assertTrue(phieu.tu_duyet)

	def test_bam_lai_cung_request_id_khong_tao_phieu_thu_hai(self):
		"""BR-O12 — bấm lại (chống trùng đơn) không được tạo phiếu thứ hai."""
		frappe.set_user(self.user_quan_ly)
		rid = frappe.generate_hash(length=20)
		a = self._dat(request_id=rid)
		b = self._dat(request_id=rid)
		self.assertEqual(a["sales_order"], b["sales_order"])
		self.assertEqual(a["de_xuat"], b["de_xuat"])
		self.assertEqual(
			frappe.db.count("Portal De Xuat Mua", {"sales_order": a["sales_order"]}),
			1,
		)

	def test_thieu_ma_ngan_khong_chan_don_quan_ly(self):
		"""QĐ điều phối viên 19/08 — thiếu `custom_ma_ngan` KHÔNG được chặn
		đơn trực tiếp của quản lý (khác nhân viên GỬI DUYỆT, nơi guard cấp
		tài khoản đã bắt buộc mã ngắn từ trước). Phiếu vẫn tạo, `ma_de_xuat`
		để rỗng — mã tra cứu là tiện ích đối chiếu, không phải điều kiện
		đúng đắn của một đơn hàng, không bao giờ được chặn một bệnh viện
		mua hàng."""
		frappe.db.set_value("Customer", self.kh_a, "custom_ma_ngan", "")
		frappe.set_user(self.user_quan_ly)
		kq = self._dat()
		self.assertTrue(kq["sales_order"])
		phieu = frappe.get_doc("Portal De Xuat Mua", kq["de_xuat"])
		self.assertFalse(phieu.ma_de_xuat)
		self.assertEqual(phieu.trang_thai, "Đã duyệt")

	# ---- portal_order_place — nhân viên khoa bị chặn hẳn (§5.5) --------

	def test_nhan_vien_khoa_goi_thang_portal_order_place_bi_tu_choi_ro_rang(self):
		"""§5.5 câu cuối — không phải lỗi 500 khó hiểu."""
		frappe.set_user(self.user_huyethoc)
		with self.assertRaises(frappe.ValidationError) as ctx:
			self._dat()
		self.assertIn("gửi duyệt", str(ctx.exception))
