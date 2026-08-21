"""Task 4 (gộp luồng đặt hàng, 2026-08-21) — GỘP hai hàm dựng đơn.

Trước task này `dat_hang.tao_sales_order` rẽ NGAY Ở ĐẦU HÀM thành
`_xay_don_hdnt` / `_xay_don_ban_le` theo tham số `mode`, tức quyết định
"đơn này theo hợp đồng hay chờ báo giá" được hạ MỘT LẦN CHO CẢ ĐƠN. Sau
task này chỉ còn MỘT hàm dựng và quyết định hạ xuống TỪNG DÒNG:

| Dòng                    | Xử lý                                            |
|-------------------------|--------------------------------------------------|
| Có trong hợp đồng       | `rate` = giá hợp đồng, gắn `blanket_order`, trừ hạn mức |
| Có mã, ngoài hợp đồng   | `rate = 0`, chờ Miyano báo giá                   |
| Chưa có mã              | vào `custom_dat_ngoai`, KHÔNG BAO GIỜ vào `items`|

Luật phân định dòng nào thuộc hợp đồng nào dùng CHUNG một hàm với màn lập
phiếu và với `Portal De Xuat Mua._suy_nguon_gia()`
(`portal_de_xuat_mua.nguon_gia_theo_ma_cho_khach`, Ruling P14/P18) — hai
đường tính "hợp đồng nào thắng" khác nhau sớm muộn cũng lệch.

Ruling P19 (điều phối viên, sau review Task 2) — bài test BẮT BUỘC của
vòng này: một phiếu `hdnt = None` (đúng dạng MỌI phiếu tạo qua UI thật,
xem `_nguon_gia_theo_ma()`) mà mọi dòng đều `nguon_gia == "Hợp đồng"`
phải duyệt được thành đơn. Trước Task 4 nó ném
`PermissionError("Hợp đồng không thuộc đơn vị của bạn.")` — `mode="hdnt"`
+ `contract=None` → `frappe.db.get_value("Blanket Order", None, ...)` rơi
vào `get_values_from_single()` và trả `None`. Bài test này đỏ trước, xanh
sau; xem `task-4-5-9-report.md` để có bằng chứng đỏ.

Lớp RIÊNG (không gộp vào `test_dat_hang_core.py`) vì lớp này dựng
`Blanket Order` SUBMIT thật cho `_TEST DX A`, và `FrappeTestCase` chỉ
rollback MỘT LẦN mỗi CLASS — cùng lý do `TestDeXuatDuyetHanMuc` tách khỏi
`TestDeXuatDuyet`.
"""

import frappe
from frappe.tests.utils import FrappeTestCase

from miyano_portal import dat_hang, de_xuat_duyet
from miyano_portal.miyano_portal.doctype.portal_de_xuat_mua.portal_de_xuat_mua import (
	TRANG_THAI_NHAP,
)
from miyano_portal.portal_mua_le import ITEM_GIU_CHO
from miyano_portal.tests.fixtures_de_xuat import dung_fixture

COMPANY = "Miyano Việt Nam"

NGUON_GIA_HOP_DONG = "Hợp đồng"
NGUON_GIA_CHO_BAO_GIA = "Chờ báo giá"


def _rid() -> str:
	return frappe.generate_hash(length=12)


def _don_phieu_cu():
	"""Dọn Sales Order TRƯỚC, rồi Blanket Order, rồi hạ phiếu về Nháp.

	ĐÚNG THỨ TỰ đó, cùng bẫy `test_de_xuat_duyet.py::_don_phieu_cu` và
	`test_nguon_gia_dong.py` đã ghi: `dung_fixture()` xoá phiếu mỗi
	`setUp()`, `revert_series_if_last` LÙI bộ đếm đặt tên khi bản ghi mới
	nhất của chuỗi bị xoá, nên phiếu ở method SAU có thể mang lại đúng tên
	phiếu method TRƯỚC vừa xoá — và chống-trùng-đơn (`custom_request_id`)
	sẽ trả về nguyên đơn CŨ. Task 9 làm bẫy này NẶNG HƠN: đơn giờ mang
	THẲNG mã phiếu làm `name`, nên tên đơn cũng đụng nhau chứ không chỉ
	`custom_request_id`.

	Dọn Blanket Order — bắt buộc từ Ruling P14 (suy nguồn giá CUSTOMER-
	WIDE): hợp đồng SUBMIT của method trước vẫn "còn hiệu lực" ở method
	sau, và tie-break `name asc` sẽ chọn hợp đồng CŨ NHẤT thay vì hợp đồng
	của chính method đang chạy."""
	for r in frappe.get_all(
		"Sales Order", filters={"customer": ["like", "_TEST DX%"], "docstatus": 0}
	):
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


class TestDatHangGop(FrappeTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		_don_phieu_cu()
		f = dung_fixture(self)
		self.kh_a = f.kh_a
		self.kh_b = f.kh_b
		self.khoa_huyethoc = f.khoa_huyethoc
		self.item_hd = f.item
		self.item_ngoai = self._tao_item("_TEST DX GOP NGOAI HD")

		self.price_list = self._tao_price_list()
		frappe.db.set_value("Customer", self.kh_a, "default_price_list", self.price_list)
		self._tao_gia(self.item_hd, self.price_list, 100)
		# CỐ Ý cho mặt hàng NGOÀI hợp đồng một giá trong CÙNG bảng giá:
		# dòng tầng 2 phải ra `rate = 0` vì nó KHÔNG thuộc hợp đồng nào,
		# KHÔNG phải vì tình cờ không tra được giá. Thiếu dòng này, một
		# hàm dựng đơn tra giá cho MỌI dòng vẫn qua được test (giá `None`
		# → 0) — false green kinh điển.
		self._tao_gia(self.item_ngoai, self.price_list, 777)

		self.bo = self._bo(self.kh_a, [
			{"item_code": self.item_hd, "qty": 50, "rate": 100},
		])

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

	def _phieu(self, items, dat_ngoai=None, hdnt=None):
		"""Phiếu đề xuất ĐÃ SẴN SÀNG DUYỆT (gửi duyệt + đóng dấu số lượng
		duyệt), đi đúng đường công khai `gui_duyet()`."""
		doc = frappe.get_doc({
			"doctype": "Portal De Xuat Mua",
			"customer": self.kh_a, "khoa_phong": self.khoa_huyethoc,
			"hdnt": hdnt, "items": items, "dat_ngoai": dat_ngoai or [],
		})
		doc.insert(ignore_permissions=True)
		doc.ly_do_yeu_cau = "cần hàng"
		doc.gui_duyet()
		doc.reload()
		return doc

	# ---- ca CHÍNH: giỏ trộn ba tầng ---------------------------------

	def test_gio_tron_ba_tang_ra_dung_mot_don(self):
		"""CA CHÍNH của Task 4. Một giỏ có cả ba loại dòng phải ra ĐÚNG MỘT
		Sales Order, mỗi dòng được xử lý theo TẦNG CỦA RIÊNG NÓ.

		Trước Task 4 giỏ này KHÔNG tồn tại được: `mode="hdnt"` từ chối
		thẳng `dat_ngoai` ("Dòng đặt ngoài chỉ áp dụng cho chế độ Mua lẻ"),
		còn `mode="ban_le"` từ chối thẳng `item_hd` (BR-R7, "đang thuộc hợp
		đồng khung")."""
		kq = dat_hang.tao_sales_order(
			self.kh_a,
			items=[
				{"item_code": self.item_hd, "qty": 2},
				{"item_code": self.item_ngoai, "qty": 3},
			],
			dat_ngoai=[{"ten_hang": "Găng tay cỡ 7.5", "dvt": "Đôi", "so_luong": 20}],
			request_id=_rid(),
		)
		so = frappe.get_doc("Sales Order", kq["sales_order"])
		self.assertFalse(kq["da_ton_tai"])

		theo_ma = {d.item_code: d for d in so.items}
		self.assertEqual(
			sorted(theo_ma), sorted([self.item_hd, self.item_ngoai]),
			"dòng đặt ngoài KHÔNG BAO GIỜ được lọt vào `items`",
		)

		# Tầng 1 — giá hợp đồng + truy vết về hợp đồng THẮNG CUỘC.
		hd = theo_ma[self.item_hd]
		self.assertEqual(float(hd.rate), 100.0)
		self.assertEqual(hd.blanket_order, self.bo)
		self.assertTrue(hd.against_blanket_order)

		# Tầng 2 — rate 0 dù mặt hàng CÓ giá trong cùng bảng giá (777).
		ngoai = theo_ma[self.item_ngoai]
		self.assertEqual(float(ngoai.rate), 0.0)
		self.assertFalse(ngoai.blanket_order)
		self.assertFalse(ngoai.against_blanket_order)

		# Tầng 3 — nằm trên CHÍNH đơn này, không sinh chứng từ thứ hai.
		self.assertEqual(len(so.custom_dat_ngoai), 1)
		self.assertEqual(so.custom_dat_ngoai[0].ten_hang, "Găng tay cỡ 7.5")

		# `company` phải theo hợp đồng của dòng tầng 1 — sai company thì
		# kho giao của MỌI dòng rơi về kho của một công ty khác và đơn
		# hỏng lặng lẽ ở khâu giao hàng.
		self.assertEqual(so.company, COMPANY)
		# Còn dòng chưa có giá → phải đi qua vòng báo giá của Miyano.
		self.assertEqual(so.custom_loai_don, "Mua lẻ")

	def test_dat_ngoai_di_kem_dong_hop_dong_khong_con_bi_tu_choi(self):
		"""Chốt `dat_hang.py:651` cũ ("Dòng đặt ngoài chỉ áp dụng cho chế
		độ Mua lẻ") là MỘT trong hai vách ngăn task này xoá. VẾ DƯƠNG: giỏ
		chỉ gồm dòng hợp đồng + dòng đặt ngoài (không có dòng tầng 2 nào)
		vẫn phải đặt được."""
		kq = dat_hang.tao_sales_order(
			self.kh_a,
			items=[{"item_code": self.item_hd, "qty": 1}],
			dat_ngoai=[{"ten_hang": "Dây truyền dịch", "dvt": "Cái", "so_luong": 5}],
			request_id=_rid(),
		)
		so = frappe.get_doc("Sales Order", kq["sales_order"])
		self.assertEqual([d.item_code for d in so.items], [self.item_hd])
		self.assertEqual(float(so.items[0].rate), 100.0)
		self.assertEqual(so.items[0].blanket_order, self.bo)
		self.assertEqual(len(so.custom_dat_ngoai), 1)

	# ---- tương thích ngược ------------------------------------------

	def test_don_thuan_hop_dong_giu_nguyen_hanh_vi_cu(self):
		"""CHỐT TƯƠNG THÍCH NGƯỢC — đơn đặt theo đúng cách CŨ (truyền
		`mode="hdnt"` + `contract`) phải hành xử Y HỆT hôm nay: giá hợp
		đồng, gắn hợp đồng lên dòng, `custom_hdnt` ở đầu đơn, loại đơn
		"Theo HĐNT". Sáu tài khoản bệnh viện thật đang đi đúng đường này
		mỗi ngày."""
		kq = dat_hang.tao_sales_order(
			self.kh_a, mode="hdnt", contract=self.bo,
			items=[{"item_code": self.item_hd, "qty": 4}],
			request_id=_rid(),
		)
		so = frappe.get_doc("Sales Order", kq["sales_order"])
		self.assertEqual(len(so.items), 1)
		self.assertEqual(float(so.items[0].rate), 100.0)
		self.assertEqual(float(so.items[0].qty), 4.0)
		self.assertEqual(so.items[0].blanket_order, self.bo)
		self.assertTrue(so.items[0].against_blanket_order)
		self.assertEqual(so.custom_hdnt, self.bo)
		self.assertEqual(so.custom_loai_don, "Theo HĐNT")
		self.assertEqual(so.company, COMPANY)
		self.assertEqual(so.selling_price_list, self.price_list)

	def test_don_thuan_cho_bao_gia_nhu_mua_le_hom_nay(self):
		"""Đơn toàn hàng ngoài hợp đồng — y hệt "mua lẻ" hôm nay: rate 0,
		không gắn hợp đồng, không trừ hạn mức, loại đơn "Mua lẻ"."""
		kq = dat_hang.tao_sales_order(
			self.kh_a,
			items=[{"item_code": self.item_ngoai, "qty": 3}],
			request_id=_rid(),
		)
		so = frappe.get_doc("Sales Order", kq["sales_order"])
		self.assertEqual(len(so.items), 1)
		self.assertEqual(float(so.items[0].rate), 0.0)
		self.assertFalse(so.items[0].blanket_order)
		self.assertFalse(so.custom_hdnt)
		self.assertEqual(so.custom_loai_don, "Mua lẻ")

	def test_gio_toan_dat_ngoai_van_chen_dong_giu_cho(self):
		"""ERPNext không lưu được Sales Order với `items` RỖNG — dòng giữ
		chỗ là lối ra, GIỮ NGUYÊN (không được đụng, theo brief)."""
		kq = dat_hang.tao_sales_order(
			self.kh_a, items=[],
			dat_ngoai=[{"ten_hang": "Kim luồn 22G", "dvt": "Cái", "so_luong": 10}],
			request_id=_rid(),
		)
		so = frappe.get_doc("Sales Order", kq["sales_order"])
		self.assertEqual([d.item_code for d in so.items], [ITEM_GIU_CHO])
		self.assertEqual(len(so.custom_dat_ngoai), 1)

	def test_hop_dong_cua_khach_khac_van_bi_tu_choi(self):
		"""GIỮ NGUYÊN — khi người gọi CÓ truyền `contract`, hợp đồng đó vẫn
		phải thuộc đúng khách hàng. Chỉ bỏ phép kiểm khi KHÔNG truyền
		(`contract=None`, đúng ca Ruling P19)."""
		bo_b = self._bo(self.kh_b, [{"item_code": self.item_hd, "qty": 5, "rate": 100}])
		with self.assertRaises(frappe.PermissionError) as ctx:
			dat_hang.tao_sales_order(
				self.kh_a, mode="hdnt", contract=bo_b,
				items=[{"item_code": self.item_hd, "qty": 1}],
				request_id=_rid(),
			)
		self.assertIn("Hợp đồng không thuộc đơn vị của bạn", str(ctx.exception))

	def test_vuot_han_muc_van_ra_loi_co_cau_truc(self):
		"""GIỮ NGUYÊN phong bì lỗi máy đọc được (`frappe.local.response
		["loi"]` + `frappe.throw`) — nhiều test phụ thuộc. Kiểm trên GIỎ
		TRỘN: dòng tầng 2 đi cùng KHÔNG được làm hỏng phong bì, và cũng
		KHÔNG được tự sinh thêm một mục lỗi nào của riêng nó."""
		frappe.db.set_value(
			"Blanket Order Item", {"parent": self.bo, "item_code": self.item_hd},
			"ordered_qty", 48,      # còn đúng 2
		)
		with self.assertRaises(frappe.ValidationError) as ctx:
			dat_hang.tao_sales_order(
				self.kh_a,
				items=[
					{"item_code": self.item_hd, "qty": 5},
					{"item_code": self.item_ngoai, "qty": 1},
				],
				request_id=_rid(),
			)
		self.assertIn("hạn mức hợp đồng khung", str(ctx.exception))
		loi = frappe.local.response.get("loi")
		self.assertIsNotNone(loi, "phong bì lỗi có cấu trúc phải còn (BR-O3)")
		self.assertEqual(len(loi), 1, "dòng chờ báo giá không được sinh lỗi")
		self.assertEqual(loi[0]["item_code"], self.item_hd)
		self.assertEqual(loi[0]["ly_do"], "vuot_han_muc")
		self.assertEqual(float(loi[0]["con_lai"]), 2.0)

	def test_trung_request_id_van_tra_don_cu(self):
		"""GIỮ NGUYÊN chống trùng đơn qua `custom_request_id` (BR-O12)."""
		rid = _rid()
		kq1 = dat_hang.tao_sales_order(
			self.kh_a, items=[{"item_code": self.item_ngoai, "qty": 1}],
			request_id=rid,
		)
		kq2 = dat_hang.tao_sales_order(
			self.kh_a, items=[{"item_code": self.item_ngoai, "qty": 1}],
			request_id=rid,
		)
		self.assertEqual(kq1["sales_order"], kq2["sales_order"])
		self.assertFalse(kq1["da_ton_tai"])
		self.assertTrue(kq2["da_ton_tai"])

	# ---- Ruling P19 — đường DUYỆT PHIẾU, qua đúng hàm công khai ------

	def test_p19_phieu_thuan_hop_dong_khong_khai_hdnt_van_duyet_duoc(self):
		"""RULING P19 — BÀI TEST THIẾU mà cả kế hoạch bị chặn ở đó.

		Một phiếu tạo qua UI THẬT không bao giờ có `hdnt`
		(`de_xuat_tao_nhap()` tạo phiếu Nháp TRƯỚC khi người dùng chọn mặt
		hàng; `de_xuat_luu_nhap()` không có tham số `hdnt` để sửa lại) —
		nên phiếu ở đây CỐ Ý để `hdnt = None`, đúng thứ giao diện thật
		sinh ra. Mọi dòng của nó thuộc hợp đồng còn hiệu lực.

		Trước Task 4: `co_dong_cho_bao_gia()` False → `mode="hdnt"` +
		`contract=None` → `PermissionError("Hợp đồng không thuộc đơn vị của
		bạn.")` — một thông điệp chỉ vào hoàn toàn sai chỗ.

		Test cũ che được lỗi này vì fixture của nó truyền `hdnt=self.bo`
		— đúng cái field giao diện thật KHÔNG BAO GIỜ điền được."""
		doc = self._phieu(items=[{
			"item_code": self.item_hd, "so_luong_de_xuat": 2,
			"nguon_gia": NGUON_GIA_CHO_BAO_GIA,   # gán SAI, buộc suy lại thật
		}])
		self.assertIsNone(doc.hdnt, "phiếu UI thật KHÔNG có hdnt")
		self.assertEqual(doc.items[0].nguon_gia, NGUON_GIA_HOP_DONG)
		self.assertFalse(doc.co_dong_cho_bao_gia())

		kq = de_xuat_duyet.duyet_va_tao_don(doc.name, "Administrator")
		so = frappe.get_doc("Sales Order", kq["sales_order"])
		self.assertEqual(len(so.items), 1)
		self.assertEqual(float(so.items[0].qty), 2.0)
		self.assertEqual(float(so.items[0].rate), 100.0, "phải có giá hợp đồng")
		self.assertEqual(so.items[0].blanket_order, self.bo, "phải trỏ đúng hợp đồng")
		self.assertEqual(so.custom_hdnt, self.bo)

	def test_p19_phieu_tron_duyet_duoc_qua_duong_cong_khai(self):
		"""Vế thứ hai của cùng chốt: phiếu TRỘN (một dòng hợp đồng, một
		dòng chờ báo giá, một dòng đặt ngoài) phải đi hết `duyet_va_tao_
		don()` — hàm CÔNG KHAI, không phải một hàm gạch dưới nào — và ra
		đơn ba tầng.

		Trước Task 4: `co_dong_cho_bao_gia()` True → `mode="ban_le"` →
		BR-R7 từ chối `item_hd` ("đang thuộc hợp đồng khung"). Tức phiếu
		trộn KHÔNG duyệt được, đúng tính năng chính của cả kế hoạch."""
		doc = self._phieu(
			items=[
				{"item_code": self.item_hd, "so_luong_de_xuat": 2},
				{"item_code": self.item_ngoai, "so_luong_de_xuat": 3},
			],
			dat_ngoai=[{"ten_hang": "Băng gạc vô trùng", "dvt": "Gói", "so_luong": 7}],
		)
		self.assertTrue(doc.co_dong_cho_bao_gia())

		kq = de_xuat_duyet.duyet_va_tao_don(doc.name, "Administrator")
		so = frappe.get_doc("Sales Order", kq["sales_order"])
		theo_ma = {d.item_code: d for d in so.items}
		self.assertEqual(sorted(theo_ma), sorted([self.item_hd, self.item_ngoai]))
		self.assertEqual(float(theo_ma[self.item_hd].rate), 100.0)
		self.assertEqual(
			theo_ma[self.item_hd].blanket_order,
			doc.items[0].blanket_order,
			"hợp đồng trên dòng đơn phải là hợp đồng ĐÃ ĐÓNG BĂNG trên phiếu "
			"lúc gửi duyệt — lệch nhau thì khách bị báo hạn mức của một hợp "
			"đồng họ chưa từng nhìn thấy",
		)
		self.assertEqual(float(theo_ma[self.item_ngoai].rate), 0.0)
		self.assertFalse(theo_ma[self.item_ngoai].blanket_order)
		self.assertEqual(len(so.custom_dat_ngoai), 1)
		self.assertEqual(so.custom_dat_ngoai[0].ten_hang, "Băng gạc vô trùng")

		doc.reload()
		self.assertEqual(doc.trang_thai, "Đã duyệt")
		self.assertEqual(doc.sales_order, kq["sales_order"])
