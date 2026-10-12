"""Task 12 (gộp luồng đặt hàng, 2026-08-21) — QĐ-G12: với một dòng HỢP
ĐỒNG, nguồn giá là CHÍNH HỢP ĐỒNG ĐÓ.

Triệu chứng thật, chủ đầu tư gặp trên trình duyệt 21/08: `MFG-BLR-2026-00020`
(Minh Đức) khai `rate` đủ cho cả ba mã, `tabItem Price` không có dòng nào,
và cổng chặn đơn bằng "MYN-SYR-10 chưa có giá trong hợp đồng". Cơ chế cũ
(`gia_hdnt.tu_hdnt`, hook `Blanket Order.on_submit`) ĐÚNG nhưng PHỦ KHÔNG
KÍN: nó chỉ chạy một lần lúc trình ký, nên mọi hợp đồng ký trước khi hook ra
đời và mọi hợp đồng nhập bằng import không bao giờ được đồng bộ.

Thứ tự tra (dừng ở giá trị DƯƠNG đầu tiên):
  1. `Blanket Order Item.rate` của ĐÚNG hợp đồng dòng đó đã suy ra
  2. `Item Price` trong `Customer.default_price_list`
  3. Không có → mới báo thiếu giá (giữ nguyên câu hiện tại)

BẪY FIXTURE của chính file này, đọc trước khi sửa: hook `on_submit` DỰNG
`Item Price` cho mọi dòng có `rate > 0`. Nếu để nguyên, tiền đề "hợp đồng có
giá mà bảng giá KHÔNG có dòng nào" — đúng tiền đề chủ đầu tư gặp — bị chính
fixture xoá mất, và ca chính sẽ xanh qua bước 2 chứ không phải bước 1.
`_xoa_gia()` chạy SAU mỗi lần submit để dựng lại đúng hiện trường, và ca
chính KHẲNG ĐỊNH tiền đề đó (`assertFalse(... exists("Item Price" ...))`)
chứ không tin nó.

Mọi bài đi ĐƯỜNG CÔNG KHAI (`dat_hang.tao_sales_order`,
`PortalDeXuatMua.gui_duyet`), không gọi thẳng hàm tra giá dùng chung: đó là
các nơi có thể lệch, và bài test chỉ có giá trị khi nó đi qua đúng chỗ người
dùng đi.

SPEC 2026-10-09 (giá theo Price List) đảo QĐ-G12 ở HAI nơi, mỗi bài bị đảo
mang chú thích riêng: danh mục `portal_catalog_gop` (phân tầng theo Price
List) và việc DỰNG ĐƠN (`dat_hang._xay_don`, §4.2) — đơn lấy giá từ
`Customer.default_price_list`, không đọc `rate` của hợp đồng, không gắn hợp
đồng lên dòng, và "chưa có giá" là dòng chờ báo giá chứ không còn lỗi
`thieu_gia`. Thứ tự tra ở trên giờ chỉ còn đúng cho đường gửi duyệt phiếu và
`portal_reorder`.
"""

import frappe
from frappe.tests.utils import FrappeTestCase

from miyano_portal import bang_gia_khach, dat_hang, gia_hdnt
from miyano_portal.api import portal as portal_api
from miyano_portal.miyano_portal.doctype.portal_de_xuat_mua.portal_de_xuat_mua import (
	TRANG_THAI_NHAP,
)
from miyano_portal.tests.fixtures_de_xuat import dung_fixture

COMPANY = "Miyano Việt Nam"
PRICE_LIST = "_TEST G12 PRICE"
PRICE_LIST_B = "_TEST G12 PRICE B"

# Giá THẬT của hiện trường chủ đầu tư (MFG-BLR-2026-00020 / MYN-SYR-10).
GIA_HOP_DONG = 88000
GIA_BANG_GIA = 55000


def _rid() -> str:
	return frappe.generate_hash(length=12)


def _don_du_lieu_cu():
	"""HUỶ rồi XOÁ Sales Order và Blanket Order của `_TEST DX%`.

	KHÔNG lọc `docstatus: 0`: bản ghi ĐÃ NỘP do method/class khác để lại vẫn
	"còn hiệu lực" ở method sau (`FrappeTestCase` rollback MỘT LẦN mỗi CLASS)
	và ăn mất `ordered_qty` của hợp đồng, khiến mọi bài giá/hạn mức PHỤ THUỘC
	THỨ TỰ CHẠY — đúng bẫy `test_dat_hang_gop.py::_don_phieu_cu` đã ghi.
	"""
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
	# Hạ phiếu về Nháp TRƯỚC `dung_fixture()`: `PortalDeXuatMua.on_trash`
	# từ chối xoá phiếu đã gửi duyệt ("Dùng Huỷ phiếu để giữ lại dấu vết"),
	# nên phiếu do `test_gui_duyet_...` để lại sẽ làm ĐỎ setUp của MỌI
	# method sau nó. Cùng khuôn `test_dat_hang_gop.py::_don_phieu_cu`.
	frappe.db.sql(
		"""UPDATE `tabPortal De Xuat Mua` SET trang_thai = %s
		   WHERE customer LIKE '\\_TEST DX%%'""",
		TRANG_THAI_NHAP,
	)


class TestGiaTuHopDong(FrappeTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		_don_du_lieu_cu()
		f = dung_fixture(self)
		self.kh_a, self.kh_b = f.kh_a, f.kh_b
		self.khoa_huyethoc = f.khoa_huyethoc

		self.item_chi_hd = self._item("_TEST G12 CHI HOP DONG")
		self.item_ca_hai = self._item("_TEST G12 CA HAI")
		self.item_rate_0 = self._item("_TEST G12 RATE 0")
		self.item_trong_rong = self._item("_TEST G12 TRONG RONG")
		self.item_chi_b = self._item("_TEST G12 CHI KHACH B")

		# MỖI khách một bảng giá RIÊNG (Ruling P32, vòng sửa 1): một bảng giá
		# là `default_price_list` của nhiều khách nghĩa là giá đàm phán của
		# bệnh viện này ghi đè lên bệnh viện kia. `dong_bo` giờ TỪ CHỐI ghi
		# vào bảng giá dùng chung, nên fixture cũ (hai khách một bảng giá)
		# sẽ làm mọi bài ở đây im lặng không có giá.
		self.price_list = self._price_list(PRICE_LIST)
		self.price_list_b = self._price_list(PRICE_LIST_B)
		frappe.db.set_value("Customer", self.kh_a, "default_price_list", self.price_list)
		frappe.db.set_value("Customer", self.kh_b, "default_price_list", self.price_list_b)

		# `qty` DƯƠNG cho mọi dòng, KHÔNG phải 0: theo BR-O15 hạn mức 0 =
		# KHÔNG GIỚI HẠN, và dòng không giới hạn CỐ Ý không được gắn
		# `Sales Order Item.blanket_order` (xem `_xay_don`) — dựng fixture
		# bằng `qty = 0` sẽ làm mọi khẳng định "dòng truy vết đúng hợp đồng"
		# ở dưới thành vô nghĩa.
		self.bo_a = self._bo(self.kh_a, [
			{"item_code": self.item_chi_hd, "qty": 100, "rate": GIA_HOP_DONG},
			{"item_code": self.item_ca_hai, "qty": 100, "rate": GIA_HOP_DONG},
			# `rate = 0` = CHƯA KHAI GIÁ (quy ước đã chốt ở `gia_hdnt.py`),
			# không phải "bán 0 đồng".
			{"item_code": self.item_rate_0, "qty": 100, "rate": 0},
			{"item_code": self.item_trong_rong, "qty": 100, "rate": 0},
		])
		self.bo_b = self._bo(self.kh_b, [
			{"item_code": self.item_chi_b, "qty": 100, "rate": 77000},
		])

		# Dựng lại ĐÚNG hiện trường: hợp đồng có giá, bảng giá TRỐNG. Hook
		# `on_submit` vừa tự dựng `Item Price` cho các dòng `rate > 0` —
		# để nguyên là để fixture che mất chính cái cổng đang kiểm.
		for ma in (self.item_chi_hd, self.item_ca_hai, self.item_rate_0,
		           self.item_trong_rong, self.item_chi_b):
			self._xoa_gia(ma)

		# Chỉ HAI mã này có dòng bảng giá, và đều KHÁC giá hợp đồng.
		self._tao_gia(self.item_ca_hai, GIA_BANG_GIA)
		self._tao_gia(self.item_rate_0, GIA_BANG_GIA)

	def tearDown(self):
		frappe.set_user("Administrator")

	# -- fixture ------------------------------------------------------------

	def _item(self, ten):
		if not frappe.db.exists("Item", ten):
			frappe.get_doc({
				"doctype": "Item", "item_code": ten, "item_name": ten,
				"item_group": frappe.db.get_value("Item Group", {}, "name"),
				"stock_uom": "Cái", "is_stock_item": 0,
			}).insert(ignore_permissions=True)
		return ten

	def _price_list(self, ten):
		if not frappe.db.exists("Price List", ten):
			frappe.get_doc({
				"doctype": "Price List", "price_list_name": ten,
				"currency": "VND", "selling": 1, "enabled": 1,
			}).insert(ignore_permissions=True)
		return ten

	def _tao_gia(self, item_code, rate):
		loc = {"item_code": item_code, "price_list": self.price_list, "selling": 1}
		if frappe.db.exists("Item Price", loc):
			frappe.db.set_value("Item Price", loc, "price_list_rate", rate)
		else:
			frappe.get_doc({"doctype": "Item Price", "price_list_rate": rate, **loc}).insert(
				ignore_permissions=True
			)

	def _xoa_gia(self, item_code):
		for r in frappe.get_all("Item Price", filters={"item_code": item_code}, pluck="name"):
			frappe.delete_doc("Item Price", r, force=True, ignore_permissions=True)

	def _bo(self, customer, items, to_date_offset=365):
		"""SUBMIT thật — Ruling P18: "còn hiệu lực" đòi `docstatus == 1`."""
		doc = frappe.get_doc({
			"doctype": "Blanket Order", "blanket_order_type": "Selling",
			"customer": customer, "company": COMPANY,
			"from_date": frappe.utils.today(),
			"to_date": frappe.utils.add_days(frappe.utils.today(), to_date_offset),
			"items": items,
		}).insert(ignore_permissions=True)
		doc.submit()
		return doc.name

	def _dat(self, items, customer=None):
		return dat_hang.tao_sales_order(
			customer or self.kh_a, items=items, request_id=_rid()
		)

	def _dong(self, so_name, item_code):
		so = frappe.get_doc("Sales Order", so_name)
		for d in so.items:
			if d.item_code == item_code:
				return d
		self.fail(f"Không thấy dòng {item_code} trên đơn {so_name}.")

	def _thanh_vien(self, email, customer, khoa_phong, vai_tro="Nhân viên khoa"):
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
			frappe.get_doc({"doctype": "Portal Member", "user": email, **gia_tri}).insert(
				ignore_permissions=True
			)
		return email

	# -- CA CHÍNH ------------------------------------------------------------

	# Đảo theo spec 2026-10-09 (giá theo Price List).
	def test_co_ca_hai_va_khac_nhau_thi_don_lay_gia_bang_gia(self):
		"""Hợp đồng khai 88.000, Price List của khách khai 55.000 → đơn mang
		giá PRICE LIST (§4.2), dấu "Bảng giá", không gắn hợp đồng. Trước spec
		2026-10-09 bài này khẳng định điều ngược lại (hợp đồng đè bảng giá)."""
		self.assertEqual(
			float(frappe.db.get_value(
				"Item Price",
				{"item_code": self.item_ca_hai, "price_list": self.price_list},
				"price_list_rate",
			)),
			float(GIA_BANG_GIA),
			"Bảng giá phải THẬT SỰ khai một giá KHÁC, nếu không bài này vô nghĩa.",
		)
		kq = self._dat([{"item_code": self.item_ca_hai, "qty": 1}])
		dong = self._dong(kq["sales_order"], self.item_ca_hai)
		self.assertEqual(float(dong.rate), float(GIA_BANG_GIA))
		self.assertEqual(dong.custom_nguon_gia, "Bảng giá")
		self.assertFalse(dong.blanket_order)

	# Đảo theo spec 2026-10-09 (giá theo Price List).
	def test_rate_0_tren_hop_dong_thi_don_van_lay_gia_bang_gia(self):
		"""Hợp đồng khai `rate = 0`, Price List có giá → đơn mang giá Price
		List. Con số không đổi so với trước spec 2026-10-09; cái đổi là dòng
		không còn gắn hợp đồng (§4.2)."""
		kq = self._dat([{"item_code": self.item_rate_0, "qty": 1}])
		dong = self._dong(kq["sales_order"], self.item_rate_0)
		self.assertEqual(float(dong.rate), float(GIA_BANG_GIA))
		self.assertFalse(dong.blanket_order)

	# -- CÁCH LY -------------------------------------------------------------

	# Đảo theo spec 2026-10-09 (giá theo Price List).
	def test_gia_cua_khach_b_khong_roi_vao_don_khach_a(self):
		"""Hai vế trong CÙNG một đơn:

		  * mã có giá trong Price List của chính khách A ra đúng giá đó (nếu
		    vế này chết, vế cách ly bên dưới xanh chỉ vì hàm tra giá luôn
		    trả 0);
		  * mã CHỈ có giá ở phía khách B — 77.000 trên hợp đồng B và 77.000
		    trong Price List của B — ra `rate = 0`, dấu "Báo giá": giá của B
		    không được rơi sang đơn của A.
		"""
		frappe.get_doc({
			"doctype": "Item Price", "item_code": self.item_chi_b,
			"price_list": self.price_list_b, "selling": 1, "price_list_rate": 77000,
		}).insert(ignore_permissions=True)
		kq = self._dat([
			{"item_code": self.item_ca_hai, "qty": 1},
			{"item_code": self.item_chi_b, "qty": 1},
		])
		cua_a = self._dong(kq["sales_order"], self.item_ca_hai)
		self.assertEqual(float(cua_a.rate), float(GIA_BANG_GIA))
		self.assertEqual(cua_a.custom_nguon_gia, "Bảng giá")

		cua_b = self._dong(kq["sales_order"], self.item_chi_b)
		self.assertEqual(float(cua_b.rate), 0.0)
		self.assertEqual(cua_b.custom_nguon_gia, "Báo giá")
		self.assertFalse(cua_b.blanket_order)

	# -- DANH MỤC (không còn dùng hàm này) VÀ ĐƯỜNG GỬI DUYỆT (vẫn dùng) -----

	# Đảo theo spec 2026-10-09 (giá theo Price List).
	def test_danh_muc_gop_KHONG_hien_gia_hop_dong_khi_bang_gia_trong(self):
		"""`portal_catalog_gop` phân tầng theo Price List của khách: mã CHỈ có
		giá trên hợp đồng (bảng giá trống) là "chờ báo giá", không mang giá
		hay khoá hợp đồng nào."""
		user_a = self._thanh_vien("g12.a@demo.miyano", self.kh_a, self.khoa_huyethoc)
		frappe.set_user(user_a)
		out = portal_api.portal_catalog_gop(tu_khoa=self.item_chi_hd)
		dong = [r for r in out["rows"] if r["item_code"] == self.item_chi_hd]
		self.assertEqual(len(dong), 1, f"Không thấy {self.item_chi_hd} trong {out['rows']}")
		self.assertEqual(dong[0]["tang"], "cho_bao_gia")
		self.assertIsNone(dong[0]["don_gia"])
		self.assertNotIn("blanket_order", dong[0])

	# Đảo theo spec 2026-10-09 (giá theo Price List).
	def test_gui_duyet_KHONG_dong_dau_gia_hop_dong_khi_bang_gia_trong(self):
		"""`_dong_dau_gia` đi qua ĐƯỜNG CÔNG KHAI `gui_duyet()`: mã CHỈ có giá
		trên hợp đồng (Price List của khách trống) là dòng "Chờ báo giá" —
		không mang hợp đồng khung, và không có "giá khoa đã thấy" nào để
		đóng dấu. Giá hợp đồng không còn được hỏi ở đây."""
		doc = frappe.get_doc({
			"doctype": "Portal De Xuat Mua",
			"customer": self.kh_a, "khoa_phong": self.khoa_huyethoc,
			"items": [{"item_code": self.item_chi_hd, "so_luong_de_xuat": 3}],
		}).insert(ignore_permissions=True)
		doc.ly_do_yeu_cau = "cần hàng"
		doc.gui_duyet()
		doc.reload()
		self.assertEqual(doc.items[0].nguon_gia, "Chờ báo giá")
		self.assertFalse(doc.items[0].blanket_order)
		self.assertFalse(doc.items[0].don_gia)

	def test_dat_lai_don_cu_cung_lay_gia_hop_dong(self):
		"""`portal_reorder` — phép tra `Item Price` THỨ SÁU, độc lập, phát
		hiện khi rà theo TÊN DOCTYPE thay vì theo tên hàm trợ giúp cũ.

		Nếu nó không đi qua `gia_dong_hop_dong()`, cùng một mã hàng cho hai
		câu trả lời khác nhau tuỳ khách bấm "Đặt hàng" hay "Đặt lại đơn cũ":
		đặt mới thì được, đặt lại thì `thieu_gia`. Vế dương ĐỦ MẠNH: dòng
		phải NẰM TRONG giỏ, mang ĐÚNG giá hợp đồng, và KHÔNG có mặt trong
		`bi_loai`."""
		kq = self._dat([{"item_code": self.item_chi_hd, "qty": 2}])
		# Quản lý: `pham_vi_don()` trả `{}` nên xem được đơn cấp bệnh viện
		# (`custom_khoa_phong` rỗng) mà `tao_sales_order` vừa dựng.
		user_ql = self._thanh_vien(
			# Khoa phòng phải BỎ TRỐNG: `PortalMember._chan_vai_tro_va_khoa_
			# phong` cấm gắn Quản lý vào một khoa ("Quản lý nhìn xuyên mọi
			# khoa"). Đúng vai cần ở đây — đơn `tao_sales_order` dựng là đơn
			# cấp bệnh viện, không thuộc khoa nào.
			"g12.ql@demo.miyano", self.kh_a, None, vai_tro="Quản lý"
		)
		frappe.set_user(user_ql)
		out = portal_api.portal_reorder(kq["sales_order"])
		self.assertNotIn(
			self.item_chi_hd, [d["item_code"] for d in out["bi_loai"]],
			"mặt hàng có giá trên hợp đồng không được coi là thiếu giá",
		)
		gio = [d for d in out["gio_hang"] if d["item_code"] == self.item_chi_hd]
		self.assertEqual(len(gio), 1, f"Không thấy {self.item_chi_hd} trong {out}")
		self.assertEqual(float(gio[0]["gia_hien_hanh"]), float(GIA_HOP_DONG))

	# -- MỘT LUẬT PHÂN ĐỊNH (Ruling P30, vòng sửa 1) -------------------------

	def test_hai_hop_dong_con_hieu_luc_thi_bang_gia_theo_DUNG_luat_cong(self):
		"""Ruling P30 — cổng và `Item Price` phải phân định hợp đồng thắng
		cuộc bằng CÙNG MỘT luật.

		Cổng: "hết hạn sớm nhất thắng" (`nguon_gia_theo_ma_cho_khach`).
		`dong_bo_khach` trước vòng sửa này duyệt `creation asc` rồi để mỗi
		lần ghi đè lên cùng một dòng `Item Price`, tức luật ẨN "ký sau cùng
		thắng" — NGƯỢC lại. Trước Task 12 hai bên đều đọc `Item Price` nên
		khớp theo cấu trúc; sau Task 12 chúng là hai luật khác nhau trên cùng
		một dữ liệu, và hậu quả là nhân viên Miyano mở đơn trong Desk, sửa số
		lượng một cái là `transaction.js` nạp `price_list_rate` đè `rate`:
		bệnh viện được báo một giá, bị xuất hoá đơn một giá khác.

		Hai vế đều DƯƠNG và phải nói CÙNG một con số."""
		ma = self._item("_TEST G12 HAI HOP DONG")
		bo_som = self._bo(
			self.kh_a, [{"item_code": ma, "qty": 100, "rate": 88000}], to_date_offset=30
		)
		bo_muon = self._bo(
			self.kh_a, [{"item_code": ma, "qty": 100, "rate": 95000}], to_date_offset=400
		)
		self.assertNotEqual(bo_som, bo_muon)

		# Vế 1 — CỔNG. Đảo theo spec 2026-10-09 (giá theo Price List): đơn
		# không còn tự phân định hợp đồng thắng cuộc — nó đọc Price List
		# (chính dòng `dong_bo_khach` ghi ở vế 2) và không gắn hợp đồng lên
		# dòng. Con số vẫn phải là 88.000 của hợp đồng hết hạn sớm nhất.
		kq = self._dat([{"item_code": ma, "qty": 1}])
		dong = self._dong(kq["sales_order"], ma)
		self.assertEqual(float(dong.rate), 88000.0)
		self.assertFalse(dong.blanket_order)

		# Vế 2 — BẢNG GIÁ phải nói y hệt. `dong_bo_khach` đã chạy hai lần qua
		# hook `on_submit` của hai hợp đồng trên.
		self.assertEqual(
			float(frappe.db.get_value(
				"Item Price",
				{"item_code": ma, "price_list": self.price_list, "selling": 1},
				"price_list_rate",
			)),
			88000.0,
			"bảng giá đang theo luật NGƯỢC với cổng (ký sau cùng thắng)",
		)

	# -- HỢP ĐỒNG PHẢI CÒN HIỆU LỰC (Ruling P31, vòng sửa 1) ----------------

	def test_dat_lai_don_cu_lay_gia_hop_dong_CON_SONG(self):
		"""Ruling P31 + I-1 — `portal_reorder` tin `Sales Order.custom_hdnt`
		của ĐƠN CŨ và không kiểm hợp đồng đó còn hiệu lực hay không.

		Kịch bản thật: hợp đồng cũ hết hạn 31/12, ngày 02/01 khách bấm "Đặt
		lại đơn cũ" → giỏ hiện giá của một hợp đồng ĐÃ CHẾT, rồi lúc xác
		nhận `_xay_don` lại tính theo hợp đồng kế nhiệm. Số hiện lúc xác nhận
		không phải số trên đơn. Đây là đường SỐNG, frontend đang gọi.

		Vế dương kép: giỏ đặt lại phải mang giá HỢP ĐỒNG KẾ NHIỆM, và mã hàng
		KHÔNG được rơi vào `bi_loai`."""
		ma = self._item("_TEST G12 KE NHIEM")
		bo_cu = self._bo(self.kh_a, [{"item_code": ma, "qty": 100, "rate": 88000}])
		kq = self._dat([{"item_code": ma, "qty": 2}])
		self.assertEqual(float(self._dong(kq["sales_order"], ma).rate), 88000.0)

		# Thời gian trôi qua: hợp đồng cũ hết hạn. Ghi thẳng DB — `to_date`
		# của một Blanket Order đã nộp không sửa qua `save()` được, và đây
		# mô phỏng đúng việc ngày tháng đi tới (cùng khuôn
		# `test_han_muc_don_tron.py`).
		frappe.db.set_value(
			"Blanket Order", bo_cu, "to_date", frappe.utils.add_days(frappe.utils.today(), -1)
		)
		bo_moi = self._bo(self.kh_a, [{"item_code": ma, "qty": 100, "rate": 95000}])

		user_ql = self._thanh_vien(
			"g12.ql@demo.miyano", self.kh_a, None, vai_tro="Quản lý"
		)
		frappe.set_user(user_ql)
		out = portal_api.portal_reorder(kq["sales_order"])
		self.assertNotIn(ma, [d["item_code"] for d in out["bi_loai"]])
		gio = [d for d in out["gio_hang"] if d["item_code"] == ma]
		self.assertEqual(len(gio), 1, f"Không thấy {ma} trong {out}")
		self.assertEqual(
			float(gio[0]["gia_hien_hanh"]), 95000.0,
			"giỏ đặt lại đang đọc giá của hợp đồng ĐÃ HẾT HIỆU LỰC",
		)
		self.assertTrue(bo_moi)

	def test_hop_dong_het_han_khong_dinh_gia_duoc_cho_hom_nay(self):
		"""Ruling P31 ở tầng hàm dùng chung — chốt nằm TRONG
		`gia_dong_hop_dong()`, không ở sáu nơi gọi (sáu nơi là sáu chỗ quên
		được). Hợp đồng hết hạn → bỏ qua bước 1, rơi xuống bảng giá.

		Vế dương đi kèm: cũng chính hợp đồng đó, khi CÒN hiệu lực, thì định
		giá được — nếu không, bài này xanh cả khi hàm luôn trả `None`."""
		ma = self._item("_TEST G12 HET HAN")
		bo = self._bo(self.kh_a, [{"item_code": ma, "qty": 100, "rate": 88000}])
		self._xoa_gia(ma)
		self.assertEqual(
			gia_hdnt.gia_dong_hop_dong(ma, bo, self.price_list), 88000.0,
			"vế dương: hợp đồng CÒN hiệu lực phải định giá được",
		)
		frappe.db.set_value(
			"Blanket Order", bo, "to_date", frappe.utils.add_days(frappe.utils.today(), -1)
		)
		self.assertIsNone(
			gia_hdnt.gia_dong_hop_dong(ma, bo, self.price_list),
			"hợp đồng ĐÃ HẾT HẠN không có quyền định giá cho hôm nay",
		)

	# -- BẢNG GIÁ DÙNG CHUNG (spec 2026-10-09 §5.3, thay Ruling P32) ----------

	# Đảo theo spec 2026-10-09 (giá theo Price List).
	def test_bang_gia_dung_chung_duoc_tach_roi_moi_ghi_gia(self):
		"""§5.3 thay Ruling P32. Hai bệnh viện trỏ chung một bảng giá: trước
		đây `dong_bo` TỪ CHỐI ghi kèm `ly_do`; giờ nó tách cho khách của hợp
		đồng một bảng RIÊNG rồi ghi vào đó.

		Điều P32 bảo vệ vẫn phải đúng, và vẫn được khẳng định: giá đàm phán
		của khách A không được hiện ra cho khách B."""
		ma = self._item("_TEST G12 BANG GIA CHUNG")
		# Vế DƯƠNG trước: bảng giá RIÊNG thì ghi tại chỗ, không tách.
		bo_a = self._bo(self.kh_a, [{"item_code": ma, "qty": 100, "rate": 88000}])
		kq = gia_hdnt.dong_bo(bo_a)
		self.assertIsNone(kq["ly_do"])
		self.assertEqual(
			frappe.db.get_value("Customer", self.kh_a, "default_price_list"), self.price_list
		)
		self.assertEqual(bang_gia_khach.gia_bang_gia(self.kh_a, ma), 88000.0)

		# Giờ khách B trỏ CHUNG bảng giá của khách A, và bảng chưa có giá mã này.
		self._xoa_gia(ma)
		frappe.db.set_value("Customer", self.kh_b, "default_price_list", self.price_list)
		kq = gia_hdnt.dong_bo(bo_a)
		self.assertIsNone(kq["ly_do"])
		self.assertEqual(kq["tao"], 1)
		bang_a = frappe.db.get_value("Customer", self.kh_a, "default_price_list")
		self.assertNotEqual(bang_a, self.price_list, "khách A phải được tách bảng riêng")
		self.assertEqual(
			frappe.db.get_value("Customer", self.kh_b, "default_price_list"), self.price_list
		)
		self.assertEqual(bang_gia_khach.gia_bang_gia(self.kh_a, ma), 88000.0)
		self.assertIsNone(
			bang_gia_khach.gia_bang_gia(self.kh_b, ma),
			"giá đàm phán của khách A không được hiện ra cho khách B",
		)
		self.assertEqual(
			frappe.db.count("Item Price", {"item_code": ma, "price_list": self.price_list}),
			0,
			"không được ghi giá đàm phán của khách này vào bảng giá khách kia đọc",
		)

	# Đảo theo spec 2026-10-09 (giá theo Price List).
	def test_khach_da_VO_HIEU_HOA_khong_lam_bang_gia_bi_tach(self):
		""""Dùng chung" đếm khách hàng ĐANG HOẠT ĐỘNG (sửa 25/08, giữ nguyên
		trong `dam_bao_bang_gia_rieng`). Một bệnh viện cũ đã vô hiệu hoá vẫn
		trỏ `default_price_list` về bảng này không đặt hàng được nữa, nên
		không có giá nào của họ để mà trộn: khách còn lại giữ nguyên bảng và
		giá được ghi TẠI CHỖ.

		Vế "cả hai còn hoạt động → bị chặn" của bài cũ không còn: ca đó giờ
		là tách bảng, đã khẳng định ở bài ngay trên."""
		ma = self._item("_TEST G12 BANG GIA CHUNG VO HIEU")
		bo_a = self._bo(self.kh_a, [{"item_code": ma, "qty": 100, "rate": 88000}])
		self._xoa_gia(ma)
		frappe.db.set_value("Customer", self.kh_b, "default_price_list", self.price_list)
		self.addCleanup(
			frappe.db.set_value, "Customer", self.kh_b, "disabled", 0
		)
		frappe.db.set_value("Customer", self.kh_b, "disabled", 1)

		kq = gia_hdnt.dong_bo(bo_a)
		self.assertIsNone(kq["ly_do"])
		self.assertEqual(
			frappe.db.get_value("Customer", self.kh_a, "default_price_list"),
			self.price_list,
			"khách đã vô hiệu hoá không được khiến bảng của khách còn lại bị tách",
		)
		self.assertEqual(
			float(frappe.db.get_value(
				"Item Price",
				{"item_code": ma, "price_list": self.price_list, "selling": 1},
				"price_list_rate",
			)),
			88000.0,
		)

	# -- ĐÓNG DẤU GIÁ PHẢI NÓI VỀ LẦN GỬI NÀY (advisor, vòng sửa 1) ----------

	def test_gui_duyet_lai_khong_giu_gia_cu_khi_khong_con_tra_duoc_gia(self):
		"""`don_gia` là "giá khoa đã thấy **tại thời điểm gửi duyệt**". Phiếu
		bị TỪ CHỐI rồi GỬI LẠI đi qua `gui_duyet()` lần thứ hai, nên con dấu
		phải nói về LẦN GỬI ẤY.

		Bản trước chỉ ghi khi tra được giá (`if rate: row.don_gia = rate`),
		nên con dấu **chỉ đi lên, không bao giờ hạ**: lần gửi đầu đóng
		100.000, giá biến mất, lần gửi lại vẫn khoe 100.000 — một con số
		không hợp đồng nào và không bảng giá nào còn đỡ, in ra cho bệnh viện
		như bằng chứng. Cùng họ lỗi với `portal_reorder` tin `custom_hdnt`
		của đơn cũ: giá trị ĐÓNG BĂNG được tin hơn phép tính LẠI.

		Để RỖNG là câu trả lời đúng cho "không tra được giá" — đó đúng là
		điều `_dong_dau_gia` làm với một dòng chưa bao giờ có giá."""
		ma = self._item("_TEST G12 DONG DAU LAI")
		self._bo(self.kh_a, [{"item_code": ma, "qty": 100, "rate": 0}])
		self._xoa_gia(ma)
		self._tao_gia(ma, 100000)

		doc = frappe.get_doc({
			"doctype": "Portal De Xuat Mua",
			"customer": self.kh_a, "khoa_phong": self.khoa_huyethoc,
			"items": [{"item_code": ma, "so_luong_de_xuat": 1}],
		}).insert(ignore_permissions=True)
		doc.ly_do_yeu_cau = "cần hàng"
		doc.gui_duyet()
		doc.reload()
		self.assertEqual(float(doc.items[0].don_gia), 100000.0, "vế dương: lần gửi đầu")

		doc.tu_choi("chưa cần gấp")
		doc.reload()
		# Giá biến mất giữa hai lần gửi (bảng giá bị gỡ, hợp đồng chưa khai
		# giá) — thao tác thật của sales, không phải trạng thái dựng tay.
		self._xoa_gia(ma)
		doc.ly_do_yeu_cau = "cần lại"
		doc.gui_duyet()
		doc.reload()
		self.assertFalse(
			doc.items[0].don_gia,
			"con dấu giá phải nói về LẦN GỬI NÀY — giữ giá cũ là khoe một con "
			"số không còn nguồn nào đỡ",
		)

	# -- PATCH BACKFILL ------------------------------------------------------

	def test_patch_dung_item_price_tu_hop_dong_va_chay_hai_lan_khong_nhan_doi(self):
		"""Patch KHÔNG thay QĐ-G12 — nó giữ `Item Price` khớp hợp đồng cho
		phía ERPNext. Chạy hai lần phải cho ĐÚNG một dòng.

		Import TẠI CHỖ (không ở đầu file) để một `ImportError` của patch chỉ
		làm ĐỎ bài này, không kéo cả module xuống — ca chính phải đỏ ở tầng
		KHẲNG ĐỊNH thì bằng chứng đỏ mới nói được điều gì."""
		from miyano_portal.patches.v1_26 import dong_bo_gia_hdnt_da_ky

		loc ={"item_code": self.item_chi_hd, "price_list": self.price_list, "selling": 1}
		self.assertEqual(frappe.db.count("Item Price", loc), 0, "tiền đề: bảng giá trống")

		dong_bo_gia_hdnt_da_ky.execute()
		self.assertEqual(frappe.db.count("Item Price", loc), 1)
		self.assertEqual(
			float(frappe.db.get_value("Item Price", loc, "price_list_rate")),
			float(GIA_HOP_DONG),
		)

		dong_bo_gia_hdnt_da_ky.execute()
		self.assertEqual(
			frappe.db.count("Item Price", loc), 1,
			"chạy lần hai không được nhân đôi dòng bảng giá",
		)
		self.assertEqual(
			float(frappe.db.get_value("Item Price", loc, "price_list_rate")),
			float(GIA_HOP_DONG),
		)
		# `rate = 0` là CHƯA KHAI GIÁ — patch KHÔNG được dựng một dòng giá 0
		# (nó sẽ che mất đúng việc sales cần làm; xem `gia_hdnt.py`).
		self.assertEqual(
			frappe.db.count("Item Price", {
				"item_code": self.item_trong_rong, "price_list": self.price_list,
			}),
			0,
		)
