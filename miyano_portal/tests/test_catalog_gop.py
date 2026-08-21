"""Task 3 (gộp luồng đặt hàng, 2026-08-19) — `portal_catalog_gop`, endpoint
tìm kiếm gộp BA TẦNG cho màn Lập phiếu (`LapPhieu.vue`, Task 8, chạy song
song với task này).

Hình dạng trả về ĐÃ ĐÓNG BĂNG — xem `hop-dong-endpoint-tim-kiem.md`:
`{"rows": [{item_code, item_name, dvt, tang, don_gia, blanket_order,
boi_so}], "tong": int}`. `don_gia`/`blanket_order`/`boi_so` là `None` (KHÔNG
phải `0`) khi không áp dụng — `0` là một giá/bội số HỢP LỆ.

Tầng suy THEO DÒNG, đối chiếu MỌI Blanket Order còn hiệu lực của khách
(Ruling P14) — endpoint dùng LẠI `nguon_gia_theo_ma_cho_khach()` (extract từ
`PortalDeXuatMua._nguon_gia_theo_ma()`, module `portal_de_xuat_mua`, Task 2).
Phép PHÂN ĐỊNH khi một mã thuộc nhiều hợp đồng ("hết hạn sớm nhất thắng,
trùng `to_date` thì `name` nhỏ hơn thắng") + mutation test cho nó đã có ở
`test_nguon_gia_dong.py` — KHÔNG lặp lại ở đây, bộ test này chỉ kiểm phần
ĐÃ NỐI DÂY đúng qua endpoint (khách đúng, hợp đồng đúng, giá đúng, boi_so
đúng, phân trang đúng), không phải logic phân định tự nó.

Gọi THẲNG `portal_api.portal_catalog_gop(...)` sau khi `frappe.set_user()`
sang một Portal Member thật (không mock `get_portal_customer`) — cùng khuôn
`test_de_xuat_endpoint.py`/`test_e6_mua_le.py`: `role Customer` có ZERO
DocPerm trên các doctype cổng, nên đường sống DUY NHẤT của một request thật
là tầng endpoint tự suy khách từ phiên đăng nhập, và test phải đi ĐÚNG
đường đó để không false-green qua một context giả.

`FrappeTestCase` rollback MỘT LẦN mỗi CLASS — dọn `Blanket Order` của
`_TEST DX%` ở ĐẦU MỖI test method (không chỉ 1 lần trong `setUp` — ở đây
`setUp` CHÍNH LÀ nơi tạo Blanket Order cho từng method, nhưng dọn được đặt
TRƯỚC khi tạo mới, đúng bẫy Task 2 đã ghi lại (`task-2-report.md`): hợp
đồng "mồ côi" của method trước vẫn còn hiệu lực ở method sau (rollback chỉ
chạy hết CLASS, không hết từng method), và vì `to_date` của mọi hợp đồng
test giống hệt nhau, tie-break `name asc` sẽ luôn chọn hợp đồng CŨ NHẤT
(tên nhỏ nhất, method chạy alphabet TRƯỚC) — không phải hợp đồng của chính
method đang chạy. Không dọn thì `test_cach_ly_khach_a_thay_dung_hop_dong_
cua_minh` sẽ xanh vì đọc TRÚNG hợp đồng của chính nó tình cờ trùng tên nhỏ
nhất, không phải vì luật customer-wide chạy đúng.
"""

import frappe
from frappe.tests.utils import FrappeTestCase

from miyano_portal.api import portal as portal_api
from miyano_portal.tests.fixtures_de_xuat import dung_fixture

COMPANY = "Miyano Việt Nam"


def _don_bo_cu():
	"""Dọn Blanket Order `_TEST DX%` trước khi mỗi test method tự dựng hợp
	đồng riêng — xem lý do rò rỉ ở docstring module.

	I2 / Ruling P18 (review vòng 1, `nguon_gia_theo_ma_cho_khach()` đòi
	`docstatus == 1`) — `bo_a`/`bo_b` bên dưới giờ SUBMIT thật; bản ghi đã
	nộp không xoá thẳng được, phải HUỶ trước."""
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

		# -- Task 10 -----------------------------------------------------------
		# HAI mặt hàng CÓ TRẦN hạn mức (`qty > 0`) trong hợp đồng của khách A.
		# CỐ Ý không tái dùng `self.item_hd`: dòng đó khai `qty = 0`, mà theo
		# QĐ-8/BR-O15 `0` nghĩa là KHÔNG GIỚI HẠN — một test hạn mức dựng trên
		# nó sẽ xanh vì `han_muc_con()` trả `None`, không phải vì phép tính
		# hạn mức chạy đúng. Tên hàng bắt đầu bằng "GOPTEST" để phép sắp xếp
		# "hàng hợp đồng đứng trước" (QĐ-G10) là một khẳng định THẬT: theo
		# `item_name asc` thuần, ba mã ngoài hợp đồng ("Chỉ thuộc…", "Có bội
		# số…", "Còn hàng…") đứng TRƯỚC hai mã này.
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
		self._tao_gia(self.item_hd, self.price_list, 125000)

		# I2 / Ruling P18 (review vòng 1) — SUBMIT thật (`docstatus == 1`):
		# `nguon_gia_theo_ma_cho_khach()` (dùng chung với `_suy_nguon_gia()`
		# của `Portal De Xuat Mua`) giờ đòi hợp đồng đã NỘP mới tính "còn
		# hiệu lực" — bản NHÁP không còn đủ, thống nhất với BR-R7.
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
		# `ordered_qty` ghi SAU khi nộp, thẳng vào DB: ERPNext tự tính lại cột
		# này từ các Sales Order gắn hợp đồng, nên đặt nó lúc `insert()` sẽ bị
		# vòng đời tài liệu ghi đè. Ở đây cần MỘT trạng thái hạn mức đã tiêu
		# mà không phải dựng cả một Sales Order chỉ để lấy con số đó.
		self._dat_da_dat(self.bo_a, self.item_han_muc, 60)
		self._dat_da_dat(self.bo_a, self.item_het_hm, 50)

		self.bo_b = frappe.get_doc({
			"doctype": "Blanket Order", "blanket_order_type": "Selling",
			"customer": self.kh_b, "company": COMPANY,
			"from_date": frappe.utils.today(),
			"to_date": frappe.utils.add_days(frappe.utils.today(), 365),
			"items": [
				{"item_code": self.item_chi_b, "qty": 0, "ordered_qty": 0, "rate": 50000},
				# Tên xếp CUỐI bảng chữ cái trong tập "GOPTEST" — nếu phép
				# sắp xếp quay về `item_name` thuần, dòng này rơi xuống cuối
				# và bài `test_khach_b_...` đỏ. Thiếu nó, `item_chi_b` tình cờ
				# đứng đầu theo alphabet và bài đó xanh vì may, không phải vì
				# luật "hàng hợp đồng của CHÍNH khách đứng trước" chạy đúng.
				{"item_code": self.item_b_cuoi, "qty": 0, "ordered_qty": 0, "rate": 51000},
			],
		}).insert(ignore_permissions=True)
		self.bo_b.submit()
		self.bo_b = self.bo_b.name

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

	def _dat_da_dat(self, blanket_order, item_code, so_luong):
		ten_dong = frappe.db.get_value(
			"Blanket Order Item", {"parent": blanket_order, "item_code": item_code}, "name"
		)
		self.assertTrue(ten_dong, f"Không thấy dòng {item_code} trong {blanket_order}.")
		frappe.db.set_value("Blanket Order Item", ten_dong, "ordered_qty", so_luong)

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

	# -- test tối thiểu (brief) ----------------------------------------------

	def test_ma_trong_hop_dong_la_tang_hop_dong_co_gia(self):
		"""Vế DƯƠNG — mã trong hợp đồng còn hiệu lực → `tang == "hop_dong"`,
		`don_gia` là số THẬT (không chỉ not-None), `blanket_order` đúng tên
		hợp đồng thắng cuộc."""
		frappe.set_user(self.user_a)
		out = portal_api.portal_catalog_gop(tu_khoa=self.item_hd)
		row = self._row(out["rows"], self.item_hd)
		self.assertEqual(row["tang"], "hop_dong")
		self.assertEqual(row["don_gia"], 125000.0)
		self.assertEqual(row["blanket_order"], self.bo_a)

	def test_ma_ngoai_hop_dong_la_tang_cho_bao_gia_gia_none(self):
		"""`don_gia` phải là `None`, KHÔNG phải `0` — `0` là giá hợp lệ."""
		frappe.set_user(self.user_a)
		out = portal_api.portal_catalog_gop(tu_khoa=self.item_ngoai)
		row = self._row(out["rows"], self.item_ngoai)
		self.assertEqual(row["tang"], "cho_bao_gia")
		self.assertIsNone(row["don_gia"])
		self.assertIsNone(row["blanket_order"])

	def test_tim_khong_dau_van_ra(self):
		"""Collation `utf8mb4_unicode_ci` khớp "kep phau thuat" với "Kẹp
		phẫu thuật" — đã kiểm ở spec §2, test này chỉ xác nhận endpoint
		THẬT SỰ đi qua đường LIKE có collation đó."""
		frappe.set_user(self.user_a)
		out = portal_api.portal_catalog_gop(tu_khoa="kep phau thuat goptest999")
		self._row(out["rows"], self.item_co_dau)

	def test_cach_ly_khach_a_thay_dung_hop_dong_cua_minh(self):
		"""Vế DƯƠNG của cách ly — dòng của A phải trỏ ĐÚNG TÊN hợp đồng của
		A, không chỉ "không phải của B"."""
		frappe.set_user(self.user_a)
		out = portal_api.portal_catalog_gop(tu_khoa=self.item_hd)
		row = self._row(out["rows"], self.item_hd)
		self.assertEqual(row["blanket_order"], self.bo_a)

	def test_cach_ly_khach_a_khong_thay_gia_hop_dong_cua_khach_b(self):
		"""Mã CHỈ thuộc hợp đồng của B — khách A tìm ra (danh mục dùng
		chung), nhưng KHÔNG thấy `tang`/`don_gia`/`blanket_order` của hợp
		đồng B."""
		frappe.set_user(self.user_a)
		out = portal_api.portal_catalog_gop(tu_khoa=self.item_chi_b)
		row = self._row(out["rows"], self.item_chi_b)
		self.assertEqual(row["tang"], "cho_bao_gia")
		self.assertIsNone(row["don_gia"])
		self.assertIsNone(row["blanket_order"])

	def test_khach_b_thay_dung_hop_dong_cua_minh(self):
		"""Vế DƯƠNG còn lại — B cũng phải thấy ĐÚNG hợp đồng của B, không
		phải chỉ A mới được kiểm."""
		frappe.set_user(self.user_b)
		out = portal_api.portal_catalog_gop(tu_khoa=self.item_chi_b)
		row = self._row(out["rows"], self.item_chi_b)
		self.assertEqual(row["tang"], "hop_dong")
		self.assertEqual(row["blanket_order"], self.bo_b)

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

	# -- tham số contract (lọc theo MỘT hợp đồng, không tắt tra hợp đồng) ---

	# -- Task 10 — trạng thái hàng (đúng cơ chế màn mua lẻ) --------------------

	def test_moi_dong_mang_trang_thai_hang_theo_ton_miyano(self):
		"""Vế DƯƠNG hai chiều — mặt hàng CÓ tồn `tabBin` phải ra "Còn hàng",
		mặt hàng KHÔNG có tồn phải ra "Liên hệ". Một chiều thôi thì một hằng
		số cứng cũng qua bài."""
		frappe.set_user(self.user_a)
		out = portal_api.portal_catalog_gop(tu_khoa="GOPTEST")
		self.assertEqual(self._row(out["rows"], self.item_ton_kho)["trang_thai_hang"], "Còn hàng")
		self.assertEqual(self._row(out["rows"], self.item_ngoai)["trang_thai_hang"], "Liên hệ")

	# -- Task 10 — hạn mức còn lại cho dòng hợp đồng (QĐ-G8) -------------------

	def test_dong_hop_dong_mang_han_muc_con_that(self):
		"""Trần 100, đã đặt 60 → còn 40. Ba con số phải ĐỀU đúng: màn hình
		hiện "còn 40/100", và câu cảnh báo vượt hạn mức nêu chính số 40."""
		frappe.set_user(self.user_a)
		row = self._row(
			portal_api.portal_catalog_gop(tu_khoa=self.item_han_muc)["rows"], self.item_han_muc
		)
		self.assertEqual(row["tang"], "hop_dong")
		self.assertEqual(row["remaining"], 40.0)
		self.assertEqual(row["total"], 100.0)
		self.assertEqual(row["used"], 60.0)
		self.assertFalse(row["khong_gioi_han"])

	def test_dong_het_han_muc_tra_0_khong_phai_none(self):
		""""Hết hạn mức" (`0.0`) phải PHÂN BIỆT ĐƯỢC với "không giới hạn"
		(`None`) — gộp hai thứ này là cách chắc chắn hiện sai một trong hai."""
		frappe.set_user(self.user_a)
		row = self._row(
			portal_api.portal_catalog_gop(tu_khoa=self.item_het_hm)["rows"], self.item_het_hm
		)
		self.assertEqual(row["remaining"], 0.0)
		self.assertIsNotNone(row["remaining"])
		self.assertFalse(row["khong_gioi_han"])

	def test_dong_khai_qty_0_la_khong_gioi_han(self):
		"""QĐ-8/BR-O15 — dòng hợp đồng khai `qty = 0` nghĩa KHÔNG GIỚI HẠN,
		không phải "hết hạn mức"."""
		frappe.set_user(self.user_a)
		row = self._row(
			portal_api.portal_catalog_gop(tu_khoa=self.item_hd)["rows"], self.item_hd
		)
		self.assertTrue(row["khong_gioi_han"])
		self.assertIsNone(row["remaining"])

	def test_dong_cho_bao_gia_khong_mang_han_muc(self):
		"""Không có hợp đồng thì không có hạn mức nào để nói — `None` cả ba,
		và `khong_gioi_han` phải là `False` (dòng này KHÔNG "không giới hạn",
		nó chỉ không thuộc hợp đồng nào)."""
		frappe.set_user(self.user_a)
		row = self._row(
			portal_api.portal_catalog_gop(tu_khoa=self.item_ngoai)["rows"], self.item_ngoai
		)
		self.assertEqual(row["tang"], "cho_bao_gia")
		self.assertIsNone(row["remaining"])
		self.assertIsNone(row["total"])
		self.assertIsNone(row["used"])
		self.assertFalse(row["khong_gioi_han"])

	# -- Task 10 — QĐ-G10: hàng trong hợp đồng của khách đứng TRƯỚC -----------

	def test_hang_hop_dong_cua_khach_dung_truoc_danh_muc_chung(self):
		"""Trang đầu là hàng trong hợp đồng của CHÍNH khách, hết rồi mới tới
		danh mục chung. Theo `item_name asc` thuần, ba mã ngoài hợp đồng
		("Chỉ thuộc…", "Con hang…", "Có bội số…") đứng TRƯỚC hai mã hợp đồng
		("GOPTEST han muc…", "GOPTEST het…") — nên bài này đỏ ngay nếu phép
		sắp xếp quay về `item_name` thuần."""
		frappe.set_user(self.user_a)
		out = portal_api.portal_catalog_gop(tu_khoa="GOPTEST", limit=50)
		tang = [r["tang"] for r in out["rows"]]
		self.assertEqual(
			tang[:2], ["hop_dong", "hop_dong"],
			f"Hai dòng đầu phải là hàng hợp đồng của khách A: {out['rows']}",
		)
		self.assertNotIn("hop_dong", tang[2:])
		self.assertEqual(
			[r["item_code"] for r in out["rows"][:2]],
			[self.item_han_muc, self.item_het_hm],
		)

	def test_trang_vat_qua_ranh_gioi_hop_dong_va_danh_muc_chung(self):
		"""Trang cắt NGANG ranh giới hai nửa — dòng cuối của nửa hợp đồng và
		dòng đầu của danh mục chung phải nằm CÙNG một trang, không mất dòng
		nào và không lặp dòng nào."""
		frappe.set_user(self.user_a)
		out = portal_api.portal_catalog_gop(tu_khoa="GOPTEST", start=1, limit=2)
		self.assertEqual(len(out["rows"]), 2)
		self.assertEqual(out["rows"][0]["item_code"], self.item_het_hm)
		self.assertEqual(out["rows"][0]["tang"], "hop_dong")
		self.assertEqual(out["rows"][1]["tang"], "cho_bao_gia")

	def test_lat_het_cac_trang_ra_dung_tong_khong_lap_khong_sot(self):
		"""`tong` phải là tổng của CẢ HAI nửa. Lật từng trang một (limit=2)
		rồi đối chiếu với một lần gọi lấy hết — phép chia hai nửa mà đếm sai
		sẽ hiện ra ở đây dưới dạng dòng lặp hoặc dòng biến mất."""
		frappe.set_user(self.user_a)
		het = portal_api.portal_catalog_gop(tu_khoa="GOPTEST", limit=500)
		self.assertEqual(het["tong"], len(het["rows"]))
		lat = []
		for start in range(0, het["tong"], 2):
			lat += portal_api.portal_catalog_gop(tu_khoa="GOPTEST", start=start, limit=2)["rows"]
		self.assertEqual(
			[r["item_code"] for r in lat], [r["item_code"] for r in het["rows"]]
		)

	def test_khach_b_thay_hang_hop_dong_cua_MINH_dung_truoc(self):
		"""Vế DƯƠNG còn lại của cách ly — thứ tự "hợp đồng trước" phải theo
		hợp đồng của CHÍNH người đang đăng nhập, không phải một danh sách ưu
		tiên dùng chung cho mọi khách."""
		frappe.set_user(self.user_b)
		out = portal_api.portal_catalog_gop(tu_khoa="GOPTEST", limit=50)
		self.assertEqual(
			[r["item_code"] for r in out["rows"][:2]], [self.item_chi_b, self.item_b_cuoi]
		)
		self.assertEqual([r["tang"] for r in out["rows"][:2]], ["hop_dong", "hop_dong"])
		self.assertNotIn("hop_dong", [r["tang"] for r in out["rows"][2:]])

	def test_contract_cua_khach_khac_bi_chan(self):
		"""Cùng chốt cách ly với `portal_catalog` — truyền `contract` không
		thuộc khách đang đăng nhập phải bị chặn, kèm thông điệp."""
		frappe.set_user(self.user_a)
		with self.assertRaises(frappe.PermissionError) as ctx:
			portal_api.portal_catalog_gop(contract=self.bo_b)
		self.assertIn("không thuộc", str(ctx.exception))
