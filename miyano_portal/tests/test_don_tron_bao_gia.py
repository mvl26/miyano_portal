"""Task 6 (QĐ-G3 / QĐ-G2b, 2026-08-19) — đơn TRỘN đi một vòng báo giá.

Task 4 đã đổi NGHĨA của `Sales Order.custom_loai_don` mà không đổi tên nó:
`dat_hang.py` giờ ghi `"Mua lẻ"` cho **mọi đơn còn ít nhất một dòng chưa
có giá**, kể cả đơn chín dòng hợp đồng + một dòng chờ báo giá. Giá trị đó
tự nói dối về chính mình — khách đọc "Mua lẻ" trên một đơn mà 90% giá trị
là hàng hợp đồng.

Task này KHÔNG xoá field (Ruling P8 — nó còn ~15 chỗ đọc ngoài tầm app,
gồm Notification tự động). Task này đổi thứ các CHỐT hỏi: mọi chốt của
vòng báo giá gọi CHUNG `portal_mua_le.di_vong_bao_gia(so)` thay vì tự so
chuỗi `custom_loai_don == "Mua lẻ"` ở sáu nơi. Từ patch v1_44 vòng báo giá
trên đơn đã bỏ (đơn mới đi Quotation); vị ngữ còn lại cho đơn "Mua lẻ" cũ
(chốt 3 của `chot_bao_gia`).

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
from miyano_portal.portal_mua_le import di_vong_bao_gia
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
	`dam_bao_xem_duoc` không lọc theo khoa."""
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
		# Đảo theo spec 2026-10-09 (giá theo Price List). Tầng của một dòng
		# giờ là "có giá trong Price List của khách hay chưa", không phải
		# "thuộc hợp đồng hay không" — nên dòng chờ báo giá của đơn trộn là
		# mã KHÔNG có dòng giá nào (trước đây fixture cố ý gài 777 cho nó).
		for ten in frappe.get_all(
			"Item Price", filters={"item_code": self.item_ngoai, "selling": 1}, pluck="name"
		):
			frappe.delete_doc("Item Price", ten, force=True)

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
		"""SUBMIT thật — hợp đồng còn hiệu lực là vế ĐỐI CHỨNG: từ spec
		2026-10-09 nó không còn quyết định giá hay tầng của dòng nào."""
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
		"""Đơn TRỘN: một dòng có giá trong Price List + một dòng chờ báo
		giá. Kiểm luôn TIỀN ĐỀ của fixture — không có các khẳng định này
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
		# Đảo theo spec 2026-10-09 (giá theo Price List).
		self.assertEqual(theo_ma[self.item_hd].custom_nguon_gia, "Bảng giá")
		self.assertFalse(theo_ma[self.item_hd].blanket_order)
		self.assertEqual(float(theo_ma[self.item_hd].rate), 100.0)
		self.assertEqual(theo_ma[self.item_ngoai].custom_nguon_gia, "Báo giá")
		self.assertEqual(float(theo_ma[self.item_ngoai].rate), 0.0)
		return so

	def _don_thuan_hop_dong(self):
		"""Đơn mọi dòng ĐÃ CÓ GIÁ ("Theo bảng giá"; trước spec 2026-10-09
		là đơn thuần hợp đồng "Theo HĐNT") — đường sáu tài khoản bệnh viện
		đang đi mỗi ngày. Kiểm tiền đề y hệt lý do trên."""
		kq = dat_hang.tao_sales_order(
			self.kh_a,
			items=[{"item_code": self.item_hd, "qty": 4}],
			request_id=_rid(),
		)
		so = frappe.get_doc("Sales Order", kq["sales_order"])
		self.assertEqual(len(so.items), 1)
		# Đảo theo spec 2026-10-09 (giá theo Price List).
		self.assertEqual(so.items[0].custom_nguon_gia, "Bảng giá")
		self.assertFalse(so.items[0].blanket_order)
		self.assertEqual(float(so.items[0].rate), 100.0)
		return so

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

	# ---- BÀI KHOÁ QUYẾT ĐỊNH: vị ngữ đọc DẤU, không suy lại từ dòng --

	def test_don_tron_da_dien_gia_van_o_trong_vong_bao_gia(self):
		"""Miyano ĐIỀN GIÁ ngay giữa vòng báo giá — đó là việc của vòng
		này. Nếu vị ngữ suy lại từ DÒNG thì đúng lúc đó nó lật sang
		`False` và đơn RƠI KHỎI vòng báo giá giữa chừng (chốt 3 thôi canh
		giá khách đã đồng ý). Vị ngữ vì vậy đọc DẤU ĐÓNG `custom_loai_don` — dấu ghi lại
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

	# ---- Ruling P49 — nhãn "Có hàng chờ báo giá" phải TẮT khi đơn đã chốt

	def test_track_tra_docstatus_de_khach_khong_thay_nhan_cho_bao_gia_tren_don_da_chot(self):
		"""Ruling P49 — trên một đơn đã xác nhận (và có thể đã giao xong),
		"Có hàng chờ báo giá" không phải một phân loại sai, nó là một lời
		nói SAI VỀ HIỆN TẠI: vòng báo giá diễn ra lúc đơn còn nháp.

		`custom_loai_don` là DẤU ghi lại đường đơn đã đi nên nó KHÔNG (và
		không được) tự tắt — cái phải tắt là NHÃN. `portal_order_track` vì
		vậy trả `docstatus` để màn chi tiết cắt nhãn ở `docstatus == 1`.
		Không dùng `status_vi`: nó là chuỗi tiếng Việt cho người đọc, dựng
		một chốt trên một chuỗi hiển thị là mời nó lệch ở lần đổi chữ sau.

		BẪY khi đọc bài này: phong bì `portal_order_track` dùng khoá
		`loai_don`, còn `di_vong_bao_gia()` đọc `custom_loai_don` — gọi vị
		ngữ lên phong bì sẽ trả `False` IM LẶNG, không lỗi. Vì vậy ở đây so
		thẳng khoá của phong bì; muốn hỏi vị ngữ thì phải hỏi trên `doc`.
		"""
		so = self._don_tron()
		frappe.set_user(self.user_quan_ly)
		kq = portal.portal_order_track(so.name)
		self.assertEqual(kq["docstatus"], 0)
		self.assertEqual(kq["loai_don"], "Mua lẻ", "đơn nháp vẫn mang dấu — nhãn còn đúng")

		frappe.set_user("Administrator")
		lai = frappe.get_doc("Sales Order", so.name)
		lai.submit()
		frappe.set_user(self.user_quan_ly)
		kq = portal.portal_order_track(so.name)
		self.assertEqual(
			kq["docstatus"], 1,
			"đơn đã chốt — màn chi tiết cắt nhãn 'Có hàng chờ báo giá' ở đây",
		)
		self.assertEqual(
			kq["loai_don"], "Mua lẻ",
			"DẤU vẫn nguyên: chốt vòng báo giá không được đổi theo docstatus, "
			"chỉ NHÃN mới tắt",
		)

		# Vế thứ BA (review vòng 1, B2/B3) — đơn ĐÃ HUỶ mang `docstatus == 2`.
		# Màn chi tiết cắt nhãn ở `docstatus === 0` chứ KHÔNG ở `!== 1`: với
		# `!== 1` thì nhãn "Có hàng chờ báo giá" hiện LẠI trên một đơn đã huỷ
		# — đúng lớp lỗi P49 vừa dẹp, một câu sai về hiện tại. Bài này chứng
		# minh phong bì phân biệt được cả BA trạng thái mà biểu thức Vue dựa
		# vào, không chỉ hai.
		frappe.set_user("Administrator")
		lai = frappe.get_doc("Sales Order", so.name)
		lai.cancel()
		frappe.set_user(self.user_quan_ly)
		kq = portal.portal_order_track(so.name)
		self.assertEqual(kq["docstatus"], 2)
