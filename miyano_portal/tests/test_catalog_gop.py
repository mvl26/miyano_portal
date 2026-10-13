"""`portal_catalog_gop` — endpoint tìm kiếm danh mục cho màn Lập phiếu
(`LapPhieu.vue`).

Spec `docs/superpowers/specs/2026-10-09-gia-theo-price-list-design.md` §3:
mỗi dòng mang đúng các khoá `item_code, item_name, dvt, boi_so, nhom_vat_tu,
ten_thuong_goi, trang_thai_hang, tang, don_gia`; `tang` là `"bang_gia"` hoặc
`"cho_bao_gia"`, suy từ Price List của khách — hợp đồng khung KHÔNG còn được
hỏi. Phần phân tầng/giá kiểm ở `test_gia_bang_gia_tren_danh_muc.py` (mượn
`setUp` và các hàm dựng dữ liệu của lớp này); file này kiểm tìm kiếm, phân
trang, thứ tự, bội số, tình trạng hàng, các bộ lọc và cách ly.

Gọi THẲNG `portal_api.portal_catalog_gop(...)` sau khi `frappe.set_user()`
sang một Portal Member thật (không mock `get_portal_customer`) — cùng khuôn
`test_de_xuat_endpoint.py`/`test_e6_mua_le.py`: `role Customer` có ZERO
DocPerm trên các doctype cổng, nên đường sống DUY NHẤT của một request thật
là tầng endpoint tự suy khách từ phiên đăng nhập, và test phải đi ĐÚNG
đường đó để không false-green qua một context giả.

Fixture VẪN dựng hai hợp đồng khung đã nộp (của khách A và khách B) dù
endpoint không đọc chúng: chúng là vế đối chứng — có hợp đồng còn hiệu lực
mà tầng, giá và thứ tự vẫn không đổi. `FrappeTestCase` rollback MỘT LẦN mỗi
CLASS, còn `setUp` tạo hợp đồng cho TỪNG method, nên phải dọn hợp đồng
`_TEST DX%` của method trước ở đầu mỗi method.
"""

import unicodedata

import frappe
from frappe.tests.utils import FrappeTestCase

from miyano_portal.api import portal as portal_api
from miyano_portal.tests.fixtures_de_xuat import dung_fixture

COMPANY = "Miyano Việt Nam"


def _khoa_sap_nhu_db(ten):
	"""Khoá sắp xấp xỉ collation `utf8mb4_unicode_ci`: bỏ dấu, không phân biệt
	hoa/thường."""
	khong_dau = "".join(
		c for c in unicodedata.normalize("NFD", ten) if unicodedata.category(c) != "Mn"
	)
	return khong_dau.casefold()


def _don_bo_cu():
	"""Dọn Blanket Order `_TEST DX%` trước khi mỗi test method tự dựng hợp
	đồng riêng — xem docstring module. Bản ghi đã nộp không xoá thẳng được,
	phải HUỶ trước."""
	for r in frappe.get_all(
		"Blanket Order", filters={"customer": ["like", "_TEST DX%"]}, fields=["name", "docstatus"]
	):
		if r.docstatus == 1:
			frappe.get_doc("Blanket Order", r.name).cancel()
		frappe.delete_doc("Blanket Order", r.name, force=True, ignore_permissions=True)


class TestPortalCatalogGop(FrappeTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		_don_bo_cu()
		f = dung_fixture(self)
		self.kh_a, self.kh_b = f.kh_a, f.kh_b
		self.khoa_huyethoc, self.khoa_duoc = f.khoa_huyethoc, f.khoa_duoc
		self.item_hd = f.item  # "_TEST DX ITEM" — đưa vào hợp đồng A bên dưới

		self.item_ngoai = self._tao_item("_TEST DX GOP NGOAI HD", "Ngoài hợp đồng GOPTEST")
		self.item_boi_so = self._tao_item("_TEST DX GOP BOI SO", "Có bội số GOPTEST")
		frappe.db.set_value("Item", self.item_boi_so, "custom_boi_so_dat", 10)
		# Tên có dấu, TỰ ĐẶT (không trùng dữ liệu demo) — search bằng chuỗi
		# KHÔNG dấu bên dưới để kiểm collation `utf8mb4_unicode_ci`, chắc
		# chắn khớp đúng một dòng dù DB có bao nhiêu item khác.
		self.item_co_dau = self._tao_item("_TEST DX GOP KEP", "Kẹp phẫu thuật GOPTEST999")
		# Chỉ thuộc hợp đồng của KHÁCH B — dùng cho vế cách ly.
		self.item_chi_b = self._tao_item("_TEST DX GOP CHI B", "Chỉ thuộc hợp đồng B GOPTEST")
		self.item_b_cuoi = self._tao_item("_TEST DX GOP ZZZ B", "ZZZ GOPTEST chi B")

		# Hai mặt hàng thuộc hợp đồng của khách A, tên bắt đầu bằng "GOPTEST" để
		# bài thứ tự là một khẳng định THẬT: theo `item_name asc` thuần, ba mã
		# ngoài hợp đồng ("Chỉ thuộc…", "Có bội số…", "Con hang…") đứng TRƯỚC hai
		# mã này; một phép sắp "hàng hợp đồng trước" sẽ đẩy chúng lên đầu.
		self.item_han_muc = self._tao_item("_TEST DX GOP HAN MUC", "GOPTEST han muc con")
		self.item_het_hm = self._tao_item("_TEST DX GOP HET HM", "GOPTEST het han muc")
		# Mặt hàng CÓ tồn Miyano thật (`tabBin`) — vế dương cho cột "Tình
		# trạng hàng"; `self.item_ngoai` không có Bin nào nên là vế "Liên hệ".
		self.item_ton_kho = self._tao_item(
			"_TEST DX GOP CON HANG", "Con hang GOPTEST", is_stock_item=1
		)
		self._tao_bin(self.item_ton_kho, 7)

		self.price_list = self._tao_price_list()
		frappe.db.set_value("Customer", self.kh_a, "default_price_list", self.price_list)
		# SUBMIT thật: hợp đồng đối chứng phải CÒN HIỆU LỰC (`docstatus == 1`)
		# thì "hợp đồng không quyết định gì" mới là một khẳng định có nghĩa.
		self.bo_a = frappe.get_doc({
			"doctype": "Blanket Order", "blanket_order_type": "Selling",
			"customer": self.kh_a, "company": COMPANY,
			"from_date": frappe.utils.today(),
			"to_date": frappe.utils.add_days(frappe.utils.today(), 365),
			"items": [
				{"item_code": self.item_hd, "qty": 0, "ordered_qty": 0, "rate": 125000},
				{"item_code": self.item_han_muc, "qty": 100, "ordered_qty": 0, "rate": 9000},
				{"item_code": self.item_het_hm, "qty": 50, "ordered_qty": 0, "rate": 8000},
			],
		}).insert(ignore_permissions=True)
		self.bo_a.submit()
		self.bo_a = self.bo_a.name

		self.bo_b = frappe.get_doc({
			"doctype": "Blanket Order", "blanket_order_type": "Selling",
			"customer": self.kh_b, "company": COMPANY,
			"from_date": frappe.utils.today(),
			"to_date": frappe.utils.add_days(frappe.utils.today(), 365),
			"items": [
				{"item_code": self.item_chi_b, "qty": 0, "ordered_qty": 0, "rate": 50000},
				{"item_code": self.item_b_cuoi, "qty": 0, "ordered_qty": 0, "rate": 51000},
			],
		}).insert(ignore_permissions=True)
		self.bo_b.submit()
		self.bo_b = self.bo_b.name

		# Bảng giá khai giá KHÁC hợp đồng (125.000) để phân biệt được nguồn.
		# Phải đặt SAU MỌI `submit()` hợp đồng ở trên: hook `Blanket Order.
		# on_submit` (`gia_hdnt.tu_hdnt` → `dong_bo_khach`) GHI ĐÈ chính dòng
		# Item Price đó về giá hợp đồng.
		self._tao_gia(self.item_hd, self.price_list, 111000)

		self.user_a = self._dam_bao_thanh_vien(
			"dxgop.a@demo.miyano", self.kh_a, "Nhân viên khoa", self.khoa_huyethoc
		)
		self.user_b = self._dam_bao_thanh_vien(
			"dxgop.b@demo.miyano", self.kh_b, "Nhân viên khoa", self.khoa_duoc
		)

	def tearDown(self):
		frappe.set_user("Administrator")

	# -- fixture riêng của file này ------------------------------------------

	def _tao_item(self, ten, ten_hien_thi, is_stock_item=0):
		if not frappe.db.exists("Item", ten):
			frappe.get_doc({
				"doctype": "Item", "item_code": ten, "item_name": ten_hien_thi,
				"item_group": frappe.db.get_value("Item Group", {}, "name"),
				"stock_uom": "Cái", "is_stock_item": is_stock_item,
			}).insert(ignore_permissions=True)
		return ten

	def _tao_bin(self, item_code, so_luong):
		"""Tồn Miyano THẬT (`tabBin`) cho một mặt hàng — nguồn DUY NHẤT của
		`trang_thai_hang()` (`portal_mua_le.py`, cơ chế màn mua lẻ đang dùng).
		Ghi thẳng `tabBin` thay vì dựng một phiếu nhập kho: bài test này kiểm
		cột "Tình trạng hàng" được NỐI DÂY đúng, không kiểm kế toán kho."""
		kho = frappe.db.get_value("Warehouse", {"is_group": 0, "disabled": 0}, "name")
		self.assertTrue(kho, "Site test không có kho nào để dựng tồn Miyano.")
		ten_bin = frappe.db.get_value("Bin", {"item_code": item_code, "warehouse": kho}, "name")
		if ten_bin:
			frappe.db.set_value("Bin", ten_bin, "actual_qty", so_luong)
		else:
			frappe.get_doc({
				"doctype": "Bin", "item_code": item_code,
				"warehouse": kho, "actual_qty": so_luong,
			}).insert(ignore_permissions=True)

	def _tao_price_list(self):
		ten = "_TEST DX GOP PRICE"
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

	def _dam_bao_thanh_vien(self, email, customer, vai_tro, khoa_phong):
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

	def _row(self, rows, item_code):
		for r in rows:
			if r["item_code"] == item_code:
				return r
		self.fail(f"Không thấy dòng {item_code} trong kết quả trả về: {rows}")

	# -- tìm kiếm và cách ly ---------------------------------------------------

	def test_ma_chua_co_gia_la_tang_cho_bao_gia_gia_none(self):
		"""`don_gia` phải là `None`, KHÔNG phải `0` — màn hình đọc `None` là
		"chưa có giá", còn `0` sẽ hiện thành "0 đ"."""
		frappe.set_user(self.user_a)
		out = portal_api.portal_catalog_gop(tu_khoa=self.item_ngoai)
		row = self._row(out["rows"], self.item_ngoai)
		self.assertEqual(row["tang"], "cho_bao_gia")
		self.assertIsNone(row["don_gia"])

	def test_tim_khong_dau_van_ra(self):
		"""Collation `utf8mb4_unicode_ci` khớp "kep phau thuat" với "Kẹp
		phẫu thuật" — đã kiểm ở spec §2, test này chỉ xác nhận endpoint
		THẬT SỰ đi qua đường LIKE có collation đó."""
		frappe.set_user(self.user_a)
		out = portal_api.portal_catalog_gop(tu_khoa="kep phau thuat goptest999")
		self._row(out["rows"], self.item_co_dau)

	def test_cach_ly_khach_a_khong_thay_gia_hop_dong_cua_khach_b(self):
		"""Mã CHỈ thuộc hợp đồng của B — khách A tìm ra (danh mục dùng
		chung), nhưng giá B đàm phán (hook nộp hợp đồng chép nó vào bảng giá
		của B, nếu B có) không được hiện với A."""
		frappe.set_user(self.user_a)
		out = portal_api.portal_catalog_gop(tu_khoa=self.item_chi_b)
		row = self._row(out["rows"], self.item_chi_b)
		self.assertEqual(row["tang"], "cho_bao_gia")
		self.assertIsNone(row["don_gia"])

	# -- Ruling P16 — boi_so ---------------------------------------------------

	def test_boi_so_tra_dung_cho_ma_co_khai_boi_so(self):
		frappe.set_user(self.user_a)
		out = portal_api.portal_catalog_gop(tu_khoa=self.item_boi_so)
		row = self._row(out["rows"], self.item_boi_so)
		self.assertEqual(row["boi_so"], 10)

	def test_boi_so_la_none_khong_phai_0_khi_khong_khai(self):
		"""`0`/chưa khai `custom_boi_so_dat` phải trả `None` — `boi_so:
		null` nghĩa là "không ràng buộc", `0` sẽ đọc nhầm thành "bội số bằng
		0" ở màn hình."""
		frappe.set_user(self.user_a)
		out = portal_api.portal_catalog_gop(tu_khoa=self.item_ngoai)
		row = self._row(out["rows"], self.item_ngoai)
		self.assertIsNone(row["boi_so"])

	# -- phân trang phía SERVER -------------------------------------------

	def test_phan_trang_o_server(self):
		"""`start`/`limit` cắt lát NGAY TRONG TRUY VẤN — hai trang liền kề
		(limit=1) phải trả hai mã KHÁC NHAU và `tong` không đổi giữa hai
		lần gọi."""
		frappe.set_user(self.user_a)
		trang0 = portal_api.portal_catalog_gop(tu_khoa="GOPTEST", start=0, limit=1)
		trang1 = portal_api.portal_catalog_gop(tu_khoa="GOPTEST", start=1, limit=1)
		self.assertEqual(len(trang0["rows"]), 1)
		self.assertEqual(len(trang1["rows"]), 1)
		self.assertNotEqual(trang0["rows"][0]["item_code"], trang1["rows"][0]["item_code"])
		self.assertEqual(trang0["tong"], trang1["tong"])
		self.assertGreaterEqual(trang0["tong"], 2)

	# -- tình trạng hàng (đúng cơ chế màn mua lẻ) ------------------------------

	def test_moi_dong_mang_trang_thai_hang_theo_ton_miyano(self):
		"""Vế DƯƠNG hai chiều — mặt hàng CÓ tồn `tabBin` phải ra "Còn hàng",
		mặt hàng KHÔNG có tồn phải ra "Liên hệ". Một chiều thôi thì một hằng
		số cứng cũng qua bài."""
		frappe.set_user(self.user_a)
		out = portal_api.portal_catalog_gop(tu_khoa="GOPTEST")
		self.assertEqual(self._row(out["rows"], self.item_ton_kho)["trang_thai_hang"], "Còn hàng")
		self.assertEqual(self._row(out["rows"], self.item_ngoai)["trang_thai_hang"], "Liên hệ")

	def test_lat_het_cac_trang_ra_dung_tong_khong_lap_khong_sot(self):
		"""Lật từng trang một (limit=2) rồi đối chiếu với một lần gọi lấy hết
		— thứ tự không tất định hoặc `tong` đếm sai sẽ hiện ra ở đây dưới dạng
		dòng lặp hoặc dòng biến mất."""
		frappe.set_user(self.user_a)
		het = portal_api.portal_catalog_gop(tu_khoa="GOPTEST", limit=500)
		self.assertEqual(het["tong"], len(het["rows"]))
		lat = []
		for start in range(0, het["tong"], 2):
			lat += portal_api.portal_catalog_gop(tu_khoa="GOPTEST", start=start, limit=2)["rows"]
		self.assertEqual(
			[r["item_code"] for r in lat], [r["item_code"] for r in het["rows"]]
		)

	# Đảo theo spec 2026-10-09 (giá theo Price List).
	def test_thu_tu_thuan_theo_ten_khong_uu_tien_hang_hop_dong(self):
		"""Trước đây hàng trong hợp đồng của khách đứng đầu (QĐ-G10); nay MỘT
		thứ tự theo tên cho mọi khách. Khoá sắp bỏ dấu rồi `casefold` để khớp
		collation `utf8mb4_unicode_ci` của cột `item_name` (không phân biệt
		dấu): "Có bội số…" đứng trước "Con hang…"."""
		frappe.set_user(self.user_a)
		out = portal_api.portal_catalog_gop(tu_khoa="GOPTEST", limit=200)
		ten = [r["item_name"] for r in out["rows"]]
		self.assertEqual(ten, sorted(ten, key=_khoa_sap_nhu_db))
		# Hai mã hợp đồng của A KHÔNG đứng đầu — chốt vế "không ưu tiên".
		ma = [r["item_code"] for r in out["rows"]]
		self.assertGreater(ma.index(self.item_han_muc), ma.index(self.item_boi_so))

	# -- Nhóm vật tư (28/09/2026, patch v1_36) --------------------------------

	def test_loc_theo_nhom_vat_tu(self):
		"""Chọn một nhóm → CHỈ hàng thuộc nhóm đó; hàng chưa phân nhóm và hàng
		nhóm khác biến mất, `tong` đếm theo đúng bộ lọc."""
		frappe.db.set_value("Item", self.item_ngoai, "custom_nhom_vat_tu", "Huyết học")
		frappe.db.set_value("Item", self.item_co_dau, "custom_nhom_vat_tu", "Vi sinh")
		frappe.set_user(self.user_a)
		out = portal_api.portal_catalog_gop(tu_khoa="GOPTEST", nhom_vat_tu="Huyết học", limit=50)
		self.assertEqual([r["item_code"] for r in out["rows"]], [self.item_ngoai])
		self.assertEqual(out["tong"], 1)
		self.assertEqual(out["rows"][0]["nhom_vat_tu"], "Huyết học")

	def test_khong_chon_nhom_thi_ra_ca_hang_chua_phan_nhom(self):
		frappe.db.set_value("Item", self.item_ngoai, "custom_nhom_vat_tu", "Huyết học")
		frappe.set_user(self.user_a)
		out = portal_api.portal_catalog_gop(tu_khoa="GOPTEST", limit=50)
		row = self._row(out["rows"], self.item_boi_so)
		self.assertIsNone(row["nhom_vat_tu"])
		self._row(out["rows"], self.item_ngoai)

	def test_tra_ve_danh_sach_nhom_de_dung_nut_loc(self):
		frappe.set_user(self.user_a)
		out = portal_api.portal_catalog_gop(tu_khoa="GOPTEST", limit=1)
		self.assertEqual(
			out["nhom_vat_tu_ds"],
			["Hóa sinh", "Vi sinh", "Huyết học", "Test nhanh", "Sinh học phân tử", "Vật tư"],
		)

	def test_nhom_la_bi_tu_choi_khong_lang_le_bo_loc(self):
		frappe.set_user(self.user_a)
		with self.assertRaises(frappe.ValidationError):
			portal_api.portal_catalog_gop(nhom_vat_tu="Không có nhóm này")

	# -- Nhà cung cấp (28/09/2026, patch v1_37 — `Item.supplier_items`) ------

	def _tao_ncc(self, ten):
		if not frappe.db.exists("Supplier", ten):
			frappe.get_doc({
				"doctype": "Supplier", "supplier_name": ten,
				"supplier_group": frappe.db.get_value("Supplier Group", {"is_group": 0}, "name"),
			}).insert(ignore_permissions=True)
		return frappe.db.get_value("Supplier", {"supplier_name": ten}, "name")

	def _gan_ncc(self, item_code, *ds_ncc):
		item = frappe.get_doc("Item", item_code)
		for ncc in ds_ncc:
			item.append("supplier_items", {"supplier": ncc})
		item.save(ignore_permissions=True)

	def test_loc_theo_nha_cung_cap(self):
		"""Một item nhiều NCC ra ở bộ lọc của MỖI NCC; item không gắn NCC đó
		không ra."""
		ncc_x = self._tao_ncc("_TEST GOP NCC X")
		ncc_y = self._tao_ncc("_TEST GOP NCC Y")
		self._gan_ncc(self.item_ngoai, ncc_x, ncc_y)
		self._gan_ncc(self.item_co_dau, ncc_y)
		frappe.set_user(self.user_a)
		out_x = portal_api.portal_catalog_gop(tu_khoa="GOPTEST", nha_cung_cap=ncc_x, limit=50)
		self.assertEqual([r["item_code"] for r in out_x["rows"]], [self.item_ngoai])
		self.assertEqual(out_x["tong"], 1)
		out_y = portal_api.portal_catalog_gop(tu_khoa="GOPTEST", nha_cung_cap=ncc_y, limit=50)
		self.assertEqual(
			sorted(r["item_code"] for r in out_y["rows"]), sorted([self.item_ngoai, self.item_co_dau])
		)
		self.assertEqual(out_y["tong"], 2)

	def test_ket_hop_nha_cung_cap_va_nhom(self):
		ncc_y = self._tao_ncc("_TEST GOP NCC Y")
		self._gan_ncc(self.item_ngoai, ncc_y)
		self._gan_ncc(self.item_co_dau, ncc_y)
		frappe.db.set_value("Item", self.item_co_dau, "custom_nhom_vat_tu", "Vi sinh")
		frappe.set_user(self.user_a)
		out = portal_api.portal_catalog_gop(
			tu_khoa="GOPTEST", nha_cung_cap=ncc_y, nhom_vat_tu="Vi sinh", limit=50
		)
		self.assertEqual([r["item_code"] for r in out["rows"]], [self.item_co_dau])

	def test_danh_sach_ncc_chi_gom_ncc_co_hang(self):
		ncc_x = self._tao_ncc("_TEST GOP NCC X")
		ncc_trong = self._tao_ncc("_TEST GOP NCC KHONG HANG")
		self._gan_ncc(self.item_ngoai, ncc_x)
		frappe.set_user(self.user_a)
		ds = portal_api.portal_catalog_gop(tu_khoa="GOPTEST", limit=1)["nha_cung_cap_ds"]
		gia_tri = [x["value"] for x in ds]
		self.assertIn(ncc_x, gia_tri)
		self.assertNotIn(ncc_trong, gia_tri)
		self.assertEqual(next(x for x in ds if x["value"] == ncc_x)["label"], "_TEST GOP NCC X")

	def test_ncc_la_bi_tu_choi(self):
		frappe.set_user(self.user_a)
		with self.assertRaises(frappe.ValidationError):
			portal_api.portal_catalog_gop(nha_cung_cap="_KHONG CO NCC NAY")

	# -- Máy sử dụng (28/09/2026, patch v1_38 — `Item.custom_may_su_dung`) ---

	def _tao_may(self, ten, hang=None):
		if not frappe.db.exists("Dong May", ten):
			frappe.get_doc({"doctype": "Dong May", "ten_may": ten, "hang_san_xuat": hang}).insert(
				ignore_permissions=True
			)
		return ten

	def _gan_may(self, item_code, *ds_may):
		item = frappe.get_doc("Item", item_code)
		for may in ds_may:
			item.append("custom_may_su_dung", {"may": may})
		item.save(ignore_permissions=True)

	def test_loc_theo_may_su_dung(self):
		may_a = self._tao_may("_TEST GOP MAY A", "Beckman")
		may_b = self._tao_may("_TEST GOP MAY B")
		self._gan_may(self.item_ngoai, may_a, may_b)
		self._gan_may(self.item_co_dau, may_b)
		frappe.set_user(self.user_a)
		out_a = portal_api.portal_catalog_gop(tu_khoa="GOPTEST", may_su_dung=may_a, limit=50)
		self.assertEqual([r["item_code"] for r in out_a["rows"]], [self.item_ngoai])
		self.assertEqual(out_a["tong"], 1)
		out_b = portal_api.portal_catalog_gop(tu_khoa="GOPTEST", may_su_dung=may_b, limit=50)
		self.assertEqual(out_b["tong"], 2)

	def test_ket_hop_may_va_nhom(self):
		may_b = self._tao_may("_TEST GOP MAY B")
		self._gan_may(self.item_ngoai, may_b)
		self._gan_may(self.item_co_dau, may_b)
		frappe.db.set_value("Item", self.item_ngoai, "custom_nhom_vat_tu", "Hóa sinh")
		frappe.set_user(self.user_a)
		out = portal_api.portal_catalog_gop(
			tu_khoa="GOPTEST", may_su_dung=may_b, nhom_vat_tu="Hóa sinh", limit=50
		)
		self.assertEqual([r["item_code"] for r in out["rows"]], [self.item_ngoai])

	def test_danh_sach_may_chi_gom_may_co_hang(self):
		may_a = self._tao_may("_TEST GOP MAY A", "Beckman")
		may_trong = self._tao_may("_TEST GOP MAY KHONG HANG")
		self._gan_may(self.item_ngoai, may_a)
		frappe.set_user(self.user_a)
		ds = portal_api.portal_catalog_gop(tu_khoa="GOPTEST", limit=1)["may_su_dung_ds"]
		self.assertIn({"value": may_a, "label": "_TEST GOP MAY A · Beckman"}, ds)
		self.assertNotIn(may_trong, [x["value"] for x in ds])

	def test_may_la_bi_tu_choi(self):
		frappe.set_user(self.user_a)
		with self.assertRaises(frappe.ValidationError):
			portal_api.portal_catalog_gop(may_su_dung="_KHONG CO MAY NAY")

	# -- Tên thường gọi theo khách hàng (02/10/2026, patch v1_39) -------------

	def _dat_ten_goi(self, item_code, ten, customer):
		# Lớp test chỉ rollback MỘT lần cuối class — dọn tên thường gọi của các
		# mặt hàng test để dòng của method trước không rò sang method sau.
		if not getattr(self, "_da_don_ten_goi", False):
			frappe.db.delete("Item Ten Thuong Goi", {"parent": ["like", "_TEST DX%"]})
			self._da_don_ten_goi = True
		item = frappe.get_doc("Item", item_code)
		item.append("custom_ten_thuong_goi", {"ten_thuong_goi": ten, "customer": customer})
		item.save(ignore_permissions=True)

	def test_tim_theo_ten_thuong_goi_cua_chinh_minh(self):
		self._dat_ten_goi(self.item_ngoai, "Ống đỏ GOIA", self.kh_a)
		frappe.set_user(self.user_a)
		# Không dấu vẫn khớp (collation `utf8mb4_unicode_ci`) — trừ "đ", MariaDB
		# coi "đ" khác "d", nên giữ "đ" trong chuỗi tìm.
		out = portal_api.portal_catalog_gop(ten_thuong_goi="ong đo goia", limit=50)
		self.assertEqual([r["item_code"] for r in out["rows"]], [self.item_ngoai])
		self.assertEqual(out["tong"], 1)
		self.assertEqual(out["rows"][0]["ten_thuong_goi"], ["Ống đỏ GOIA"])

	def test_ten_thuong_goi_cua_khach_khac_khong_tim_ra_khong_hien(self):
		"""Cách ly: tên B đặt không tìm được và không hiện với A."""
		self._dat_ten_goi(self.item_ngoai, "Bí danh của B GOIB", self.kh_b)
		frappe.set_user(self.user_a)
		out = portal_api.portal_catalog_gop(ten_thuong_goi="GOIB", limit=50)
		self.assertEqual(out["rows"], [])
		self.assertEqual(out["tong"], 0)
		row = self._row(
			portal_api.portal_catalog_gop(tu_khoa=self.item_ngoai, limit=50)["rows"], self.item_ngoai
		)
		self.assertEqual(row["ten_thuong_goi"], [])

	def test_tu_khoa_van_tim_theo_ten_xuat_hoa_don(self):
		"""Ô 1 tìm theo `item_name` (tên xuất hoá đơn); tên thường gọi KHÔNG lọt
		vào ô này."""
		self._dat_ten_goi(self.item_ngoai, "Tên riêng GOIC", self.kh_a)
		frappe.set_user(self.user_a)
		self._row(portal_api.portal_catalog_gop(tu_khoa="Ngoài hợp đồng GOPTEST")["rows"], self.item_ngoai)
		self.assertEqual(portal_api.portal_catalog_gop(tu_khoa="GOIC")["rows"], [])

	def test_ket_hop_hai_o_tim(self):
		self._dat_ten_goi(self.item_ngoai, "Chung GOID", self.kh_a)
		self._dat_ten_goi(self.item_co_dau, "Chung GOID", self.kh_a)
		frappe.set_user(self.user_a)
		out = portal_api.portal_catalog_gop(tu_khoa="Kẹp", ten_thuong_goi="GOID", limit=50)
		self.assertEqual([r["item_code"] for r in out["rows"]], [self.item_co_dau])
