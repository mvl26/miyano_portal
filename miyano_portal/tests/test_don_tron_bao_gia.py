"""Task 6 (QĐ-G3 / QĐ-G2b, 2026-08-19) — đơn TRỘN đi một vòng báo giá.

Task 4 đã đổi NGHĨA của `Sales Order.custom_loai_don` mà không đổi tên nó:
`dat_hang.py` giờ ghi `"Mua lẻ"` cho **mọi đơn còn ít nhất một dòng chưa
có giá**, kể cả đơn chín dòng hợp đồng + một dòng chờ báo giá. Giá trị đó
tự nói dối về chính mình — khách đọc "Mua lẻ" trên một đơn mà 90% giá trị
là hàng hợp đồng.

Task này KHÔNG xoá field (Ruling P8 — nó còn ~15 chỗ đọc ngoài tầm app,
gồm Notification tự động). Task này đổi thứ các CHỐT hỏi: mọi chốt của
vòng báo giá gọi CHUNG `portal_mua_le.di_vong_bao_gia(so)` thay vì tự so
chuỗi `custom_loai_don == "Mua lẻ"` ở sáu nơi.

**Vị ngữ đọc DẤU ĐÓNG, không suy lại từ DÒNG** — xem docstring của
`di_vong_bao_gia`. Bài `test_don_tron_da_dien_gia_van_o_trong_vong_bao_gia`
là bài khoá lại quyết định đó: nó ĐỎ ngay khi ai đó "sửa" vị ngữ thành suy
lại từ dòng, vì Miyano ĐIỀN GIÁ trong chính vòng báo giá.

Lớp RIÊNG (không gộp vào `test_dat_hang_gop.py`) vì lớp này dựng
`Blanket Order` SUBMIT thật và `FrappeTestCase` chỉ rollback MỘT LẦN mỗi
CLASS — cùng lý do lớp kia đã tách.
"""

import frappe
from frappe.tests.utils import FrappeTestCase

from miyano_portal import dat_hang
from miyano_portal.api import portal
from miyano_portal.miyano_portal.doctype.portal_de_xuat_mua.portal_de_xuat_mua import (
	TRANG_THAI_NHAP,
)
from miyano_portal.portal_mua_le import TRANG_THAI_CHO_KHACH, di_vong_bao_gia
from miyano_portal.tests.fixtures_de_xuat import dung_fixture

COMPANY = "Miyano Việt Nam"


def _rid() -> str:
	return frappe.generate_hash(length=12)


def _don_phieu_cu():
	"""Dọn Sales Order TRƯỚC, rồi Blanket Order, rồi hạ phiếu về Nháp —
	đúng thứ tự và đúng lý do `test_dat_hang_gop.py::_don_phieu_cu` đã ghi
	(huỷ trước khi xoá; hợp đồng SUBMIT của method trước vẫn "còn hiệu
	lực" ở method sau và ăn mất tie-break `name asc`)."""
	for r in frappe.get_all(
		"Sales Order", filters={"customer": ["like", "_TEST DX%"]},
		fields=["name", "docstatus"],
	):
		if r.docstatus == 1:
			frappe.get_doc("Sales Order", r.name).cancel()
		frappe.delete_doc("Sales Order", r.name, force=True, ignore_permissions=True)
	for r in frappe.get_all(
		"Blanket Order", filters={"customer": ["like", "_TEST DX%"]},
		fields=["name", "docstatus"],
	):
		if r.docstatus == 1:
			frappe.get_doc("Blanket Order", r.name).cancel()
		frappe.delete_doc("Blanket Order", r.name, force=True, ignore_permissions=True)
	frappe.db.sql(
		"""UPDATE `tabPortal De Xuat Mua` SET trang_thai = %s
		   WHERE customer LIKE '\\_TEST DX%%'""",
		TRANG_THAI_NHAP,
	)


def _dam_bao_quan_ly(email, customer):
	"""Tài khoản cổng vai trò "Quản lý" — `pham_vi_don()` rỗng nên
	`dam_bao_xem_duoc` không lọc theo khoa, và `dam_bao_duoc_sua_don_da_
	duyet` cho qua. Cùng khuôn `test_de_xuat_sua_sau_duyet.py`."""
	if not frappe.db.exists("User", email):
		u = frappe.get_doc({
			"doctype": "User", "email": email,
			"first_name": email.split("@")[0],
			"user_type": "Website User", "send_welcome_email": 0,
		})
		u.append("roles", {"role": "Customer"})
		u.insert(ignore_permissions=True)
	gia_tri = {"customer": customer, "vai_tro": "Quản lý",
		   "khoa_phong": None, "active": 1}
	ten_tv = frappe.db.get_value("Portal Member", {"user": email}, "name")
	if ten_tv:
		frappe.db.set_value("Portal Member", ten_tv, gia_tri)
	else:
		frappe.get_doc({
			"doctype": "Portal Member", "user": email, **gia_tri,
		}).insert(ignore_permissions=True)
	contact = frappe.db.get_value("Contact", {"user": email})
	if contact and not frappe.db.exists("Dynamic Link", {
		"parent": contact, "parenttype": "Contact",
		"link_doctype": "Customer", "link_name": customer,
	}):
		c = frappe.get_doc("Contact", contact)
		c.append("links", {"link_doctype": "Customer", "link_name": customer})
		c.save(ignore_permissions=True)
	return email


class TestDonTronVongBaoGia(FrappeTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		_don_phieu_cu()
		f = dung_fixture(self)
		self.kh_a = f.kh_a
		self.item_hd = f.item
		self.item_ngoai = self._tao_item("_TEST DX TRON NGOAI HD")

		self.price_list = self._tao_price_list()
		frappe.db.set_value("Customer", self.kh_a, "default_price_list", self.price_list)
		self._tao_gia(self.item_hd, self.price_list, 100)
		# CỐ Ý cho mặt hàng NGOÀI hợp đồng một giá trong CÙNG bảng giá:
		# dòng tầng 2 phải ra `rate = 0` vì nó KHÔNG thuộc hợp đồng nào,
		# không phải vì tình cờ không tra được giá (bẫy false-green đã ghi
		# ở `test_dat_hang_gop.py`).
		self._tao_gia(self.item_ngoai, self.price_list, 777)

		self.bo = self._bo(self.kh_a, [
			{"item_code": self.item_hd, "qty": 50, "rate": 100},
		])
		self.user_quan_ly = _dam_bao_quan_ly("dxtron.ql@demo.miyano", self.kh_a)

	def tearDown(self):
		frappe.set_user("Administrator")

	# -- fixture riêng của lớp này -----------------------------------

	def _tao_item(self, ten):
		if not frappe.db.exists("Item", ten):
			frappe.get_doc({
				"doctype": "Item", "item_code": ten, "item_name": ten,
				"item_group": frappe.db.get_value("Item Group", {}, "name"),
				"stock_uom": "Nos", "is_stock_item": 0,
			}).insert(ignore_permissions=True)
		return ten

	def _tao_price_list(self):
		ten = "_TEST DX TRON PRICE"
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

	def _bo(self, customer, items):
		"""SUBMIT thật — Ruling P18: "còn hiệu lực" đòi `docstatus == 1`.
		Hợp đồng CHƯA submit cho `rate = 0` và không gắn `blanket_order`,
		tức "đơn thuần hợp đồng" của bài tương thích ngược sẽ THẬT RA là
		một đơn tầng 2 đóng dấu "Mua lẻ" — bài xanh vì lý do sai."""
		doc = frappe.get_doc({
			"doctype": "Blanket Order", "blanket_order_type": "Selling",
			"customer": customer, "company": COMPANY,
			"from_date": frappe.utils.today(),
			"to_date": frappe.utils.add_days(frappe.utils.today(), 365),
			"items": items,
		}).insert(ignore_permissions=True)
		doc.submit()
		return doc.name

	def _don_tron(self):
		"""Đơn TRỘN: một dòng hợp đồng (có giá) + một dòng tầng 2 (chờ báo
		giá). Kiểm luôn TIỀN ĐỀ của fixture — không có hai khẳng định này
		thì mọi bài dưới đây có thể xanh trên một fixture hỏng."""
		kq = dat_hang.tao_sales_order(
			self.kh_a,
			items=[
				{"item_code": self.item_hd, "qty": 2},
				{"item_code": self.item_ngoai, "qty": 3},
			],
			request_id=_rid(),
		)
		so = frappe.get_doc("Sales Order", kq["sales_order"])
		theo_ma = {d.item_code: d for d in so.items}
		self.assertEqual(theo_ma[self.item_hd].blanket_order, self.bo)
		self.assertEqual(float(theo_ma[self.item_hd].rate), 100.0)
		self.assertEqual(float(theo_ma[self.item_ngoai].rate), 0.0)
		return so

	def _don_thuan_hop_dong(self):
		"""Đơn THUẦN hợp đồng — đường sáu tài khoản bệnh viện đang đi mỗi
		ngày. Kiểm tiền đề y hệt lý do trên."""
		kq = dat_hang.tao_sales_order(
			self.kh_a,
			items=[{"item_code": self.item_hd, "qty": 4}],
			request_id=_rid(),
		)
		so = frappe.get_doc("Sales Order", kq["sales_order"])
		self.assertEqual(len(so.items), 1)
		self.assertEqual(so.items[0].blanket_order, self.bo)
		self.assertEqual(float(so.items[0].rate), 100.0)
		return so

	def _ep_cho_khach_dong_y(self, ten, ngay_gui=None):
		"""Ép `workflow_state` thẳng bằng `db.set_value` — cùng khuôn
		`test_e6_mua_le.py`/`test_de_xuat_sua_sau_duyet.py` dùng để dựng
		fixture ở trạng thái này, không đi qua workflow thật của sales."""
		frappe.db.set_value("Sales Order", ten, {
			"workflow_state": TRANG_THAI_CHO_KHACH,
			"custom_ngay_gui_khach_duyet": ngay_gui or frappe.utils.today(),
		}, update_modified=False)

	# ---- vị ngữ dùng chung ------------------------------------------

	def test_don_tron_duoc_coi_la_di_vong_bao_gia(self):
		"""VẾ DƯƠNG của QĐ-G3 ở mức vị ngữ: đơn còn MỘT dòng chưa có giá
		thì CẢ ĐƠN đi vòng báo giá."""
		so = self._don_tron()
		self.assertTrue(di_vong_bao_gia(so))

	def test_don_thuan_hop_dong_khong_di_vong_bao_gia(self):
		"""CHỐT TƯƠNG THÍCH NGƯỢC — đơn thuần hợp đồng KHÔNG bị ép qua
		vòng báo giá (QĐ-G3, vế sau)."""
		so = self._don_thuan_hop_dong()
		self.assertFalse(di_vong_bao_gia(so))

	# ---- chốt 1: banner hiệu lực báo giá (`portal_order_track`) ------

	def test_banner_hieu_luc_hien_cho_don_tron(self):
		"""VẾ DƯƠNG — khách mở đơn TRỘN đang chờ mình đồng ý phải thấy
		"Báo giá hiệu lực đến ..." (F-07). Trước mô hình gộp, chốt này hỏi
		`custom_loai_don == "Mua lẻ"`; giờ hỏi `di_vong_bao_gia`."""
		so = self._don_tron()
		self._ep_cho_khach_dong_y(so.name)
		frappe.set_user(self.user_quan_ly)
		kq = portal.portal_order_track(so.name)
		self.assertIsNotNone(kq["chap_nhan"])
		self.assertTrue(kq["chap_nhan"]["can_dong_y"])
		self.assertIsNotNone(kq["chap_nhan"]["han_hieu_luc"])

	def test_banner_hieu_luc_khong_ap_cho_don_thuan_hop_dong(self):
		"""TƯƠNG THÍCH NGƯỢC — đơn HĐNT ở "Chờ khách đồng ý" là luồng E2
		gốc, KHÔNG có khái niệm hiệu lực N ngày (review I-2(c))."""
		so = self._don_thuan_hop_dong()
		self._ep_cho_khach_dong_y(so.name)
		frappe.set_user(self.user_quan_ly)
		kq = portal.portal_order_track(so.name)
		self.assertIsNotNone(kq["chap_nhan"])
		self.assertTrue(kq["chap_nhan"]["can_dong_y"])
		self.assertIsNone(kq["chap_nhan"]["han_hieu_luc"])

	# ---- chốt 2: hết hiệu lực khi khách bấm đồng ý -------------------

	def test_don_tron_qua_han_bi_chan_dong_y(self):
		"""BR-R5 áp cho đơn TRỘN: báo giá gửi 30 ngày trước đã hết hiệu
		lực, khách không bấm đồng ý trên đơn cũ được nữa."""
		so = self._don_tron()
		self._ep_cho_khach_dong_y(
			so.name, ngay_gui=frappe.utils.add_days(frappe.utils.today(), -30)
		)
		frappe.set_user(self.user_quan_ly)
		with self.assertRaises(frappe.ValidationError) as ctx:
			portal.portal_order_accept(so.name, "dong_y")
		self.assertIn("hết hiệu lực", str(ctx.exception))

	# ---- chốt 3: sửa số lượng trong vòng báo giá ---------------------

	def test_don_tron_sua_duoc_so_luong(self):
		"""VẾ DƯƠNG — đơn trộn ĐANG trong vòng báo giá thì khách sửa được
		số lượng rồi gửi lại (đơn về "Chờ xác nhận" để Miyano báo lại)."""
		so = self._don_tron()
		self._ep_cho_khach_dong_y(so.name)
		frappe.set_user(self.user_quan_ly)
		portal.portal_order_sua_so_luong(
			so.name, {"items": [{"item_code": self.item_ngoai, "qty": 9}]}
		)
		frappe.set_user("Administrator")
		lai = frappe.get_doc("Sales Order", so.name)
		theo_ma = {d.item_code: d for d in lai.items}
		self.assertEqual(float(theo_ma[self.item_ngoai].qty), 9.0)
		self.assertEqual(lai.workflow_state, "Chờ xác nhận")

	def test_don_thuan_hop_dong_khong_sua_duoc_so_luong(self):
		"""CHỐT TƯƠNG THÍCH NGƯỢC — số lượng đơn HĐNT đã chốt theo hợp
		đồng, cổng không sửa được."""
		so = self._don_thuan_hop_dong()
		self._ep_cho_khach_dong_y(so.name)
		frappe.set_user(self.user_quan_ly)
		with self.assertRaises(frappe.ValidationError) as ctx:
			portal.portal_order_sua_so_luong(
				so.name, {"items": [{"item_code": self.item_hd, "qty": 9}]}
			)
		self.assertIn("chờ báo giá", str(ctx.exception))

	# ---- chốt 4: PDF báo giá ----------------------------------------

	def test_pdf_bao_gia_khong_chan_don_tron_o_chot_loai_don(self):
		"""Đơn trộn phải ĐI QUA được chốt loại đơn của `portal_bao_gia_
		pdf`. Chứng minh bằng chốt KẾ TIẾP: để đơn ở "Chờ xác nhận" thì
		lỗi nhận được phải là lỗi "chưa gửi báo giá", tức chốt loại đơn
		đứng TRƯỚC nó đã cho qua. (Cố ý không dựng PDF thật ở đây — bài
		này canh CHỐT, không canh wkhtmltopdf.)"""
		so = self._don_tron()
		self.assertEqual(so.workflow_state, "Chờ xác nhận")
		frappe.set_user(self.user_quan_ly)
		with self.assertRaises(frappe.ValidationError) as ctx:
			portal.portal_bao_gia_pdf(order=so.name)
		self.assertIn("chưa được gửi", str(ctx.exception))

	def test_pdf_bao_gia_chan_don_thuan_hop_dong(self):
		"""TƯƠNG THÍCH NGƯỢC — đơn thuần hợp đồng ở "Chờ khách đồng ý"
		vẫn KHÔNG tải được chứng từ đề "Hiệu lực đến..." (review I-2)."""
		so = self._don_thuan_hop_dong()
		self._ep_cho_khach_dong_y(so.name)
		frappe.set_user(self.user_quan_ly)
		with self.assertRaises(frappe.ValidationError) as ctx:
			portal.portal_bao_gia_pdf(order=so.name)
		self.assertIn("chờ báo giá", str(ctx.exception))

	# ---- BÀI KHOÁ QUYẾT ĐỊNH: vị ngữ đọc DẤU, không suy lại từ dòng --

	def test_don_tron_da_dien_gia_van_o_trong_vong_bao_gia(self):
		"""Miyano ĐIỀN GIÁ ngay giữa vòng báo giá — đó là việc của vòng
		này. Nếu vị ngữ suy lại từ DÒNG thì đúng lúc đó nó lật sang
		`False` và đơn RƠI KHỎI vòng báo giá giữa chừng: banner hiệu lực
		tắt, PDF báo giá không tải được, khách không sửa được số lượng
		nữa. Vị ngữ vì vậy đọc DẤU ĐÓNG `custom_loai_don` — dấu ghi lại
		ĐƯỜNG đơn đã đi, không phải tình trạng giá lúc này.

		Bài này ĐỎ ngay khi ai đó đổi `di_vong_bao_gia` sang suy lại từ
		dòng."""
		so = self._don_tron()
		# Miyano báo giá: dòng tầng 2 có giá, không còn dòng nào rate 0.
		so.items[1].rate = 777
		so.save(ignore_permissions=True)
		so.reload()
		self.assertTrue(all(float(d.rate) > 0 for d in so.items))

		self.assertTrue(di_vong_bao_gia(so))

		# ... và các chốt vẫn nhận đơn này (đường công khai, không soi
		# vị ngữ một mình).
		self._ep_cho_khach_dong_y(so.name)
		frappe.set_user(self.user_quan_ly)
		kq = portal.portal_order_track(so.name)
		self.assertIsNotNone(kq["chap_nhan"]["han_hieu_luc"])
