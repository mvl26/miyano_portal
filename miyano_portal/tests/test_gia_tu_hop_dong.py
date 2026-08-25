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

Mọi bài đi ĐƯỜNG CÔNG KHAI (`dat_hang.tao_sales_order`, `portal_catalog_gop`,
`PortalDeXuatMua.gui_duyet`), không gọi thẳng hàm tra giá dùng chung: ba nơi
đó là ba nơi có thể lệch, và bài test chỉ có giá trị khi nó đi qua đúng chỗ
người dùng đi.
"""

import frappe
from frappe.tests.utils import FrappeTestCase

from miyano_portal import dat_hang, gia_hdnt
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

	def test_hop_dong_co_gia_bang_gia_trong_van_dat_duoc_hang(self):
		"""CA CHÍNH — chính xác ca chủ đầu tư gặp 21/08.

		Hợp đồng khai `rate = 88.000`, `tabItem Price` KHÔNG có dòng nào cho
		mã đó → đơn phải ĐI, và dòng phải mang ĐÚNG giá hợp đồng."""
		self.assertFalse(
			frappe.db.exists("Item Price", {
				"item_code": self.item_chi_hd, "price_list": self.price_list,
			}),
			"Tiền đề của ca này là bảng giá TRỐNG — fixture đang che mất cổng cần kiểm.",
		)
		kq = self._dat([{"item_code": self.item_chi_hd, "qty": 2}])
		self.assertTrue(kq["sales_order"])
		dong = self._dong(kq["sales_order"], self.item_chi_hd)
		self.assertEqual(float(dong.rate), float(GIA_HOP_DONG))
		self.assertEqual(dong.blanket_order, self.bo_a)

	def test_co_ca_hai_va_khac_nhau_thi_lay_gia_hop_dong(self):
		"""Hợp đồng ĐÈ bảng giá — nguyên tắc đã tuyên bố ở `gia_hdnt.py`
		("Hợp đồng đã ký là nguồn sự thật"), giờ mã mới khớp lời."""
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
		self.assertEqual(float(dong.rate), float(GIA_HOP_DONG))

	def test_rate_0_tren_hop_dong_thi_roi_ve_bang_gia(self):
		"""`rate = 0` là CHƯA KHAI GIÁ, không phải "bán 0 đồng" — bước 1
		chỉ dừng ở giá trị DƯƠNG, nên dòng này đi tiếp xuống bảng giá."""
		kq = self._dat([{"item_code": self.item_rate_0, "qty": 1}])
		dong = self._dong(kq["sales_order"], self.item_rate_0)
		self.assertEqual(float(dong.rate), float(GIA_BANG_GIA))
		self.assertEqual(dong.blanket_order, self.bo_a)

	def test_khong_co_ca_hai_thi_van_bao_thieu_gia_nguyen_van(self):
		with self.assertRaises(frappe.ValidationError) as ctx:
			self._dat([{"item_code": self.item_trong_rong, "qty": 1}])
		self.assertIn(
			f"{self.item_trong_rong} chưa có giá trong hợp đồng.", str(ctx.exception)
		)
		self.assertIn("Miyano đã nhận được thông báo để bổ sung.", str(ctx.exception))
		self.assertEqual(
			[d["ly_do"] for d in frappe.local.response["loi"]], ["thieu_gia"]
		)

	# -- CÁCH LY -------------------------------------------------------------

	def test_rate_hop_dong_khach_b_khong_roi_vao_don_khach_a(self):
		"""Hai vế trong CÙNG một đơn, cả hai đều DƯƠNG:

		  * mã của chính khách A ra đúng giá hợp đồng A (nếu vế này chết,
		    vế cách ly bên dưới xanh chỉ vì hàm tra giá luôn trả 0);
		  * mã CHỈ có trong hợp đồng khách B ra `rate = 0` (tầng "chờ báo
		    giá") và KHÔNG gắn hợp đồng nào — 77.000 của B không được rơi
		    sang đơn của A.
		"""
		kq = self._dat([
			{"item_code": self.item_chi_hd, "qty": 1},
			{"item_code": self.item_chi_b, "qty": 1},
		])
		cua_a = self._dong(kq["sales_order"], self.item_chi_hd)
		self.assertEqual(float(cua_a.rate), float(GIA_HOP_DONG))
		self.assertEqual(cua_a.blanket_order, self.bo_a)

		cua_b = self._dong(kq["sales_order"], self.item_chi_b)
		self.assertEqual(float(cua_b.rate), 0.0)
		self.assertFalse(cua_b.blanket_order)

	# -- HAI NƠI CÒN LẠI DÙNG CHUNG MỘT HÀM ---------------------------------

	def test_danh_muc_gop_hien_gia_hop_dong_khi_bang_gia_trong(self):
		"""`portal_catalog_gop` — màn Lập phiếu phải hiện ĐÚNG con số mà đơn
		sẽ mang. Trước Task 12 nó hiện `null` cho đúng mã hàng đặt được."""
		user_a = self._thanh_vien("g12.a@demo.miyano", self.kh_a, self.khoa_huyethoc)
		frappe.set_user(user_a)
		out = portal_api.portal_catalog_gop(tu_khoa=self.item_chi_hd)
		dong = [r for r in out["rows"] if r["item_code"] == self.item_chi_hd]
		self.assertEqual(len(dong), 1, f"Không thấy {self.item_chi_hd} trong {out['rows']}")
		self.assertEqual(dong[0]["tang"], "hop_dong")
		self.assertEqual(dong[0]["don_gia"], float(GIA_HOP_DONG))
		self.assertEqual(dong[0]["blanket_order"], self.bo_a)

	def test_gui_duyet_dong_dau_gia_hop_dong_khi_bang_gia_trong(self):
		"""`_dong_dau_gia` — "giá khoa đã thấy" phải là giá hợp đồng, đi qua
		ĐƯỜNG CÔNG KHAI `gui_duyet()`."""
		doc = frappe.get_doc({
			"doctype": "Portal De Xuat Mua",
			"customer": self.kh_a, "khoa_phong": self.khoa_huyethoc,
			"items": [{"item_code": self.item_chi_hd, "so_luong_de_xuat": 3}],
		}).insert(ignore_permissions=True)
		doc.ly_do_yeu_cau = "cần hàng"
		doc.gui_duyet()
		doc.reload()
		self.assertEqual(doc.items[0].nguon_gia, "Hợp đồng")
		self.assertEqual(float(doc.items[0].don_gia), float(GIA_HOP_DONG))

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

		# Vế 1 — CỔNG: hết hạn sớm nhất thắng.
		kq = self._dat([{"item_code": ma, "qty": 1}])
		dong = self._dong(kq["sales_order"], ma)
		self.assertEqual(float(dong.rate), 88000.0)
		self.assertEqual(dong.blanket_order, bo_som)

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

	# -- BẢNG GIÁ DÙNG CHUNG (Ruling P32, vòng sửa 1) ------------------------

	def test_khong_ghi_gia_vao_bang_gia_nhieu_khach_dung_chung(self):
		"""Ruling P32 — `dong_bo` lấy bảng giá đích từ
		`Customer.default_price_list`, KHÔNG từ hợp đồng. Khi hai bệnh viện
		trỏ chung một bảng giá, hợp đồng của bên này ghi giá cho bên kia:
		một mã `rate = 0` (chưa khai giá) của khách B sẽ rơi xuống bước 2 và
		đọc trúng giá ĐÃ ĐÀM PHÁN của khách A, thay vì bị chặn đúng bằng
		"chưa có giá trong hợp đồng".

		Thà không ghi và báo ồn ào, còn hơn ghi rồi không ai biết."""
		ma = self._item("_TEST G12 BANG GIA CHUNG")
		# Vế DƯƠNG trước: bảng giá RIÊNG thì ghi được.
		bo_a = self._bo(self.kh_a, [{"item_code": ma, "qty": 100, "rate": 88000}])
		kq = gia_hdnt.dong_bo(bo_a)
		self.assertIsNone(kq["ly_do"])
		self.assertEqual(
			float(frappe.db.get_value(
				"Item Price",
				{"item_code": ma, "price_list": self.price_list, "selling": 1},
				"price_list_rate",
			)),
			88000.0,
		)

		# Giờ khách B trỏ CHUNG bảng giá của khách A — phải từ chối ghi.
		self._xoa_gia(ma)
		frappe.db.set_value("Customer", self.kh_b, "default_price_list", self.price_list)
		kq = gia_hdnt.dong_bo(bo_a)
		self.assertEqual(kq["tao"], 0)
		self.assertEqual(kq["cap_nhat"], 0)
		self.assertTrue(kq["ly_do"], "phải nêu rõ vì sao không đồng bộ được")
		self.assertIn(self.price_list, kq["ly_do"])
		self.assertIn(self.kh_b, kq["ly_do"], "phải nêu TÊN các khách dùng chung")
		self.assertEqual(
			frappe.db.count("Item Price", {
				"item_code": ma, "price_list": self.price_list,
			}),
			0,
			"không được ghi giá đàm phán của khách này vào bảng giá khách kia",
		)

	def test_khach_da_VO_HIEU_HOA_khong_con_chan_dong_bo(self):
		"""Sửa 25/08 — chốt P32 đếm khách hàng ĐANG HOẠT ĐỘNG.

		Thiếu bộ lọc `disabled`, một bệnh viện cũ đã bị vô hiệu hoá nhưng
		vẫn trỏ `default_price_list` về bảng giá này khiến phép đếm mãi mãi
		> 1, và bệnh viện CÒN LẠI bị chặn đồng bộ giá VĨNH VIỄN bằng một câu
		bảo họ "tách bảng giá riêng cho từng khách" — trong khi họ đã là
		khách duy nhất còn hoạt động dùng nó. Không có đường nào gỡ ra ngoài
		việc sửa tay dữ liệu.

		Khách đã vô hiệu hoá không đặt hàng được nữa nên không có giá nào
		của họ để mà trộn: đúng nguy cơ P32 dựng lên để chặn, và nó không
		còn."""
		ma = self._item("_TEST G12 BANG GIA CHUNG VO HIEU")
		bo_a = self._bo(self.kh_a, [{"item_code": ma, "qty": 100, "rate": 88000}])
		frappe.db.set_value("Customer", self.kh_b, "default_price_list", self.price_list)
		self.addCleanup(
			frappe.db.set_value, "Customer", self.kh_b, "disabled", 0
		)

		# Vế ÂM trước — cả hai còn hoạt động thì vẫn phải chặn (nếu vế này
		# chết, vế dưới xanh chỉ vì chốt P32 đã hỏng hoàn toàn).
		self._xoa_gia(ma)
		kq = gia_hdnt.dong_bo(bo_a)
		self.assertTrue(kq["ly_do"])
		self.assertEqual(kq["tao"], 0)

		# Vô hiệu hoá khách B — khách A giờ là khách DUY NHẤT còn hoạt động
		# dùng bảng giá này, đồng bộ phải chạy lại được.
		frappe.db.set_value("Customer", self.kh_b, "disabled", 1)
		kq = gia_hdnt.dong_bo(bo_a)
		self.assertIsNone(
			kq["ly_do"],
			"khách đã vô hiệu hoá không được chặn đồng bộ của khách còn lại",
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
