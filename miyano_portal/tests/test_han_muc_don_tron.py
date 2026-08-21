"""Task 5 (gộp luồng đặt hàng, 2026-08-21) — hạn mức CHỈ trên dòng hợp đồng.

`de_xuat_duyet._kiem_han_muc` trước task này giả định MỌI dòng của phiếu
đều nằm trên `doc.hdnt` (một hợp đồng duy nhất khai ở ĐẦU PHIẾU). Phiếu
trộn phá giả định đó theo hai hướng cùng lúc:

  * dòng "Chờ báo giá" KHÔNG thuộc hợp đồng nào — `han_muc_con()` trả
    `(0.0, 0.0)` cho nó ("hạn mức 0"), nên đưa nó vào phép kiểm là chặn
    một dòng chưa từng bị hạn mức ràng buộc;
  * dòng "Hợp đồng" của một phiếu trộn có thể nằm trên hợp đồng KHÁC
    `doc.hdnt` (Ruling P14 — suy customer-wide, hợp đồng hết hạn sớm nhất
    thắng), nên hỏi hạn mức của `doc.hdnt` là hỏi nhầm sổ.

Sau Task 5: kiểm theo TỪNG DÒNG có `nguon_gia == "Hợp đồng"`, trên ĐÚNG
`blanket_order` đã ĐÓNG BĂNG trên dòng đó lúc gửi duyệt (Task 2, I3) —
tức đúng hợp đồng đã định giá dòng ấy cho khoa xem.

LỖ HỔNG TASK NÀY ĐÓNG LẠI (điều phối viên ghi trong ledger Task 2: "Task 5
phải đóng lại"): gate cũ `if not doc.co_dong_cho_bao_gia() and doc.hdnt:`
đọc `doc.hdnt`, mà MỌI phiếu tạo qua UI thật đều có `hdnt = None`
(`de_xuat_tao_nhap()` tạo phiếu Nháp trước khi chọn mặt hàng) — nghĩa là
hạn mức KHÔNG BAO GIỜ được kiểm trên đường đề xuất thật, kể cả phiếu
THUẦN hợp đồng.

Giữ nguyên hành vi đã chốt (§5.6): hết hạn mức → THẤT BẠI kèm TÊN KHOA đã
tiêu mất, tuyệt đối KHÔNG im lặng cắt số lượng.
"""

import frappe
from frappe.tests.utils import FrappeTestCase

from miyano_portal import de_xuat_duyet
from miyano_portal.miyano_portal.doctype.portal_de_xuat_mua.portal_de_xuat_mua import (
	TRANG_THAI_NHAP,
)
from miyano_portal.tests.fixtures_de_xuat import dung_fixture

COMPANY = "Miyano Việt Nam"
WAREHOUSE = "Stores - MYN"

NGUON_GIA_HOP_DONG = "Hợp đồng"
NGUON_GIA_CHO_BAO_GIA = "Chờ báo giá"

TEN_KHOA_DA_TIEU = "Dược nội trú"


def _don_phieu_cu():
	"""Sales Order → Blanket Order → phiếu. ĐÚNG THỨ TỰ đó — xem docstring
	cùng tên ở `test_dat_hang_gop.py`/`test_de_xuat_duyet.py`."""
	# Vòng sửa 1 (review độc lập) — KHÔNG lọc `docstatus: 0`. Một đơn
	# `_TEST DX%` ĐÃ SUBMIT do class khác để lại sẽ sống sót qua bước dọn
	# này và ăn mất `ordered_qty` của hợp đồng (`StockController.update_
	# blanket_order` chạy ở `on_submit`), khiến mọi bài test biên hạn mức
	# trong file này PHỤ THUỘC THỨ TỰ CHẠY — đúng loại chập chờn tốn nhiều
	# giờ nhất để truy. Huỷ trước rồi xoá (cùng khuôn `test_catalog_gop.py`
	# làm với Blanket Order); `cancel()` cũng trả lại `ordered_qty`.
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


class TestHanMucDonTron(FrappeTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		_don_phieu_cu()
		f = dung_fixture(self)
		self.kh_a = f.kh_a
		self.khoa_huyethoc = f.khoa_huyethoc
		self.item_hd = f.item
		self.item_ngoai = self._tao_item("_TEST DX HM NGOAI HD")
		self.khoa_duoc_a = self._khoa(self.kh_a, TEN_KHOA_DA_TIEU, "DUOCNT")

		self.price_list = self._tao_price_list()
		frappe.db.set_value("Customer", self.kh_a, "default_price_list", self.price_list)
		self._tao_gia(self.item_hd, self.price_list, 100)

		# Hạn mức 5, đã dùng 3 → CÒN 2 (cùng khuôn `TestDeXuatDuyetHanMuc`).
		self.bo = frappe.get_doc({
			"doctype": "Blanket Order", "blanket_order_type": "Selling",
			"customer": self.kh_a, "company": COMPANY,
			"from_date": frappe.utils.today(),
			"to_date": frappe.utils.add_days(frappe.utils.today(), 365),
			"items": [{"item_code": self.item_hd, "qty": 5, "ordered_qty": 3, "rate": 100}],
		}).insert(ignore_permissions=True)
		self.bo.submit()
		self.bo = self.bo.name

		# Đơn "đã tiêu" của KHOA KHÁC trên CÙNG hợp đồng — nguồn dữ liệu
		# duy nhất cho vế "kèm TÊN KHOA đã tiêu mất" của §5.6.
		frappe.get_doc({
			"doctype": "Sales Order", "customer": self.kh_a, "company": COMPANY,
			"transaction_date": frappe.utils.today(),
			"delivery_date": frappe.utils.add_days(frappe.utils.today(), 5),
			"selling_price_list": self.price_list,
			"custom_hdnt": self.bo, "custom_khoa_phong": self.khoa_duoc_a,
			"items": [{"item_code": self.item_hd, "qty": 3, "rate": 100,
			           "warehouse": WAREHOUSE}],
		}).insert(ignore_permissions=True)

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

	def _khoa(self, customer, ten, ma):
		co = frappe.db.get_value(
			"Customer Department", {"customer": customer, "ma_khoa": ma}, "name"
		)
		if co:
			return co
		return frappe.get_doc({
			"doctype": "Customer Department", "customer": customer,
			"ten_khoa_phong": ten, "ma_khoa": ma, "active": 1,
		}).insert(ignore_permissions=True).name

	def _tao_price_list(self):
		ten = "_TEST DX HM PRICE"
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

	def _bo(self, items, to_date_offset=365):
		"""Blanket Order SUBMIT thật (Ruling P18 — "còn hiệu lực" đòi
		`docstatus == 1`)."""
		doc = frappe.get_doc({
			"doctype": "Blanket Order", "blanket_order_type": "Selling",
			"customer": self.kh_a, "company": COMPANY,
			"from_date": frappe.utils.today(),
			"to_date": frappe.utils.add_days(frappe.utils.today(), to_date_offset),
			"items": items,
		}).insert(ignore_permissions=True)
		doc.submit()
		return doc.name

	def _phieu_cho_duyet(self, items, dat_ngoai=None):
		"""Phiếu đi qua ĐÚNG đường công khai `gui_duyet()`, `hdnt` để RỖNG
		— đúng dạng MỌI phiếu tạo qua giao diện thật."""
		doc = frappe.get_doc({
			"doctype": "Portal De Xuat Mua",
			"customer": self.kh_a, "khoa_phong": self.khoa_huyethoc,
			"items": items, "dat_ngoai": dat_ngoai or [],
		})
		doc.insert(ignore_permissions=True)
		doc.ly_do_yeu_cau = "cần hàng"
		doc.gui_duyet()
		doc.reload()
		return doc

	def _dat_so_luong_duyet(self, doc, theo_ma: dict):
		for row in doc.items:
			if row.item_code in theo_ma:
				row.so_luong_duyet = theo_ma[row.item_code]
		doc.save(ignore_permissions=True)
		doc.reload()
		return doc

	# ---- ba ca của Task 5 -------------------------------------------

	def test_don_tron_dong_hop_dong_con_han_muc_thi_duyet_duoc(self):
		"""VẾ DƯƠNG — bắt buộc: thiếu nó, một `_kiem_han_muc` LUÔN NÉM vẫn
		qua được ca âm bên dưới."""
		doc = self._phieu_cho_duyet(items=[
			{"item_code": self.item_hd, "so_luong_de_xuat": 2},
			{"item_code": self.item_ngoai, "so_luong_de_xuat": 3},
		])
		self.assertEqual(doc.items[0].nguon_gia, NGUON_GIA_HOP_DONG)
		self.assertEqual(doc.items[1].nguon_gia, NGUON_GIA_CHO_BAO_GIA)

		kq = de_xuat_duyet.duyet_va_tao_don(doc.name, "Administrator")
		so = frappe.get_doc("Sales Order", kq["sales_order"])
		theo_ma = {d.item_code: d for d in so.items}
		self.assertEqual(float(theo_ma[self.item_hd].qty), 2.0)   # đúng bằng phần còn lại
		self.assertEqual(theo_ma[self.item_hd].blanket_order, self.bo)
		self.assertEqual(float(theo_ma[self.item_ngoai].qty), 3.0)

	def test_don_tron_dong_hop_dong_vuot_han_muc_thi_that_bai_kem_ten_khoa(self):
		"""§5.6 — thất bại ỒN ÀO kèm TÊN KHOA đã tiêu mất hạn mức. Tuyệt
		đối KHÔNG im lặng cắt số lượng: người duyệt không được duyệt một
		con số khác con số họ nhìn thấy."""
		doc = self._phieu_cho_duyet(items=[
			{"item_code": self.item_hd, "so_luong_de_xuat": 5},
			{"item_code": self.item_ngoai, "so_luong_de_xuat": 3},
		])
		with self.assertRaises(frappe.ValidationError) as ctx:
			de_xuat_duyet.duyet_va_tao_don(doc.name, "Administrator")
		self.assertIn(TEN_KHOA_DA_TIEU, str(ctx.exception))
		self.assertIn(self.item_hd, str(ctx.exception))

		# VẾ ÂM của cùng luật: không có gì bị đổi lặng lẽ.
		doc.reload()
		self.assertEqual(doc.trang_thai, "Chờ duyệt")
		self.assertEqual(doc.items[0].so_luong_duyet, 5)
		self.assertFalse(doc.sales_order)

	def test_dong_cho_bao_gia_khong_bi_kiem_han_muc(self):
		"""Dòng "Chờ báo giá" chưa thuộc hợp đồng nào — `han_muc_con()` trả
		`(0.0, 0.0)` ("hạn mức 0") cho MỌI mã hàng không có dòng trong hợp
		đồng, nên nếu nó lọt vào phép kiểm thì MỘT SỐ LƯỢNG BẤT KỲ cũng
		"vượt hạn mức". Đặt số lượng RẤT LỚN cho đúng dòng đó, và KHÔNG có
		dòng hợp đồng nào trong phiếu để không có gì khác che mất.

		Không đỏ được trước Task 5 (gate cũ bỏ qua cả phiếu vì nó có dòng
		Chờ báo giá) — canh bằng mutation: bỏ phép lọc `nguon_gia` trong
		`_kiem_han_muc` thì đúng bài này đỏ. Xem `task-4-5-9-report.md`."""
		doc = self._phieu_cho_duyet(items=[
			{"item_code": self.item_ngoai, "so_luong_de_xuat": 9999},
		])
		self.assertEqual(doc.items[0].nguon_gia, NGUON_GIA_CHO_BAO_GIA)
		kq = de_xuat_duyet.duyet_va_tao_don(doc.name, "Administrator")
		so = frappe.get_doc("Sales Order", kq["sales_order"])
		self.assertEqual(float(so.items[0].qty), 9999.0)
		self.assertFalse(so.items[0].blanket_order)

	# ---- lỗ hổng Task 5 đóng lại ------------------------------------

	def test_phieu_thuan_hop_dong_khong_khai_hdnt_van_bi_kiem_han_muc(self):
		"""LỖ HỔNG ĐÓNG LẠI Ở TASK NÀY. Gate cũ đọc `doc.hdnt`, mà mọi
		phiếu tạo qua UI thật đều có `hdnt = None` — nên `_kiem_han_muc`
		KHÔNG BAO GIỜ chạy trên đường đề xuất thật, kể cả phiếu THUẦN hợp
		đồng vượt hạn mức. Phiếu ở đây cố ý KHÔNG khai `hdnt`."""
		doc = self._phieu_cho_duyet(items=[
			{"item_code": self.item_hd, "so_luong_de_xuat": 5},
		])
		self.assertIsNone(doc.hdnt)
		self.assertEqual(doc.items[0].blanket_order, self.bo)
		with self.assertRaises(frappe.ValidationError) as ctx:
			de_xuat_duyet.duyet_va_tao_don(doc.name, "Administrator")
		self.assertIn(TEN_KHOA_DA_TIEU, str(ctx.exception))

	def test_kiem_dung_hop_dong_cua_rieng_tung_dong(self):
		"""Hai dòng, hai hợp đồng KHÁC NHAU: mỗi dòng phải hỏi hạn mức của
		ĐÚNG hợp đồng của nó. Hợp đồng thứ hai hết hạn SỚM HƠN nên nó
		thắng cho mã hàng riêng của nó (Ruling P14); nó còn thừa hạn mức,
		trong khi `self.bo` chỉ còn 2 — một `_kiem_han_muc` hỏi CHUNG một
		hợp đồng cho cả phiếu sẽ báo "hạn mức 0" cho mã hàng của hợp đồng
		kia (nó không có dòng nào trong `self.bo`)."""
		item_hd2 = self._tao_item("_TEST DX HM ITEM HD2")
		self._tao_gia(item_hd2, self.price_list, 200)
		bo2 = frappe.get_doc({
			"doctype": "Blanket Order", "blanket_order_type": "Selling",
			"customer": self.kh_a, "company": COMPANY,
			"from_date": frappe.utils.today(),
			"to_date": frappe.utils.add_days(frappe.utils.today(), 30),
			"items": [{"item_code": item_hd2, "qty": 100, "rate": 200}],
		}).insert(ignore_permissions=True)
		bo2.submit()
		bo2 = bo2.name

		doc = self._phieu_cho_duyet(items=[
			{"item_code": self.item_hd, "so_luong_de_xuat": 2},
			{"item_code": item_hd2, "so_luong_de_xuat": 40},
		])
		self.assertEqual(doc.items[0].blanket_order, self.bo)
		self.assertEqual(doc.items[1].blanket_order, bo2)

		kq = de_xuat_duyet.duyet_va_tao_don(doc.name, "Administrator")
		so = frappe.get_doc("Sales Order", kq["sales_order"])
		theo_ma = {d.item_code: d for d in so.items}
		self.assertEqual(theo_ma[self.item_hd].blanket_order, self.bo)
		self.assertEqual(theo_ma[item_hd2].blanket_order, bo2)
		self.assertEqual(float(theo_ma[item_hd2].qty), 40.0)

	# ---- Ruling P28 — MỘT nguồn duy nhất: bản SUY LẠI lúc duyệt --------

	def test_hop_dong_dong_bang_het_han_thi_dung_hop_dong_con_song(self):
		"""RULING P28, VẾ DƯƠNG, ca CHÍNH của vòng sửa 1.

		Mặt hàng X nằm trong HAI hợp đồng: `bo_som` (hết hạn sớm → THẮNG
		lúc gửi duyệt theo Ruling P14, nhưng chỉ còn 1) và `bo_dai` (còn
		1000). Phiếu đóng băng `bo_som`. Rồi `bo_som` HẾT HẠN trong lúc chờ
		duyệt — chuyện có thật, không phải giả định.

		Trước vòng sửa này: `_kiem_han_muc` đọc `row.blanket_order` ĐÓNG
		BĂNG và KHÔNG hề kiểm nó còn hiệu lực không, nên nó viện dẫn hạn
		mức của một hợp đồng ĐÃ CHẾT để chặn thẳng việc duyệt — trong khi
		`dat_hang._xay_don` (suy lại) lẽ ra định giá dòng đó theo `bo_dai`
		với 1000 còn lại. Quản lý bị từ chối oan, và thông điệp lỗi không
		cho họ đường nào để gỡ.

		Sau: hợp đồng dùng để QUYẾT ĐỊNH là bản suy lại tại thời điểm
		duyệt, ở CẢ HAI tầng. Bản đóng băng giữ nguyên vai trò BẰNG CHỨNG
		(khoa đã nhìn thấy hợp đồng nào lúc gửi) — test khẳng định nó
		KHÔNG bị xoá — và việc hai bản lệch nhau phải ĐI VÀO cảnh báo, không
		bị nuốt."""
		item_x = self._tao_item("_TEST DX HM ITEM HAI HD")
		self._tao_gia(item_x, self.price_list, 300)
		bo_som = self._bo([{"item_code": item_x, "qty": 1, "rate": 300}],
		                  to_date_offset=5)
		bo_dai = self._bo([{"item_code": item_x, "qty": 1000, "rate": 300}],
		                  to_date_offset=200)

		doc = self._phieu_cho_duyet(items=[
			{"item_code": item_x, "so_luong_de_xuat": 5},
		])
		self.assertEqual(
			doc.items[0].blanket_order, bo_som,
			"Ruling P14 — hết hạn sớm nhất thắng lúc gửi duyệt",
		)

		# `bo_som` hết hạn TRONG lúc phiếu nằm chờ duyệt. Ghi thẳng DB:
		# `to_date` của một Blanket Order đã nộp không sửa qua `save()`
		# được, và đây mô phỏng đúng việc thời gian trôi qua.
		frappe.db.set_value(
			"Blanket Order", bo_som, "to_date",
			frappe.utils.add_days(frappe.utils.today(), -1),
		)

		kq = de_xuat_duyet.duyet_va_tao_don(doc.name, "Administrator")
		so = frappe.get_doc("Sales Order", kq["sales_order"])
		self.assertEqual(float(so.items[0].qty), 5.0)
		self.assertEqual(
			so.items[0].blanket_order, bo_dai,
			"dòng phải được định giá và trừ hạn mức theo hợp đồng CÒN SỐNG",
		)
		self.assertEqual(float(so.items[0].rate), 300.0)

		# Bằng chứng đóng băng KHÔNG bị xoá, không bị đổi ý nghĩa.
		doc.reload()
		self.assertEqual(doc.items[0].blanket_order, bo_som)

		# Và việc đổi hợp đồng KHÔNG được nuốt lặng lẽ.
		cb = [c for c in kq["canh_bao_gia"] if c["item_code"] == item_x]
		self.assertEqual(len(cb), 1, "đổi hợp đồng phải được báo lên")
		self.assertEqual(cb[0]["hop_dong_cu"], bo_som)
		self.assertEqual(cb[0]["hop_dong_moi"], bo_dai)

	def test_dong_backfill_thieu_blanket_order_van_bi_kiem_han_muc(self):
		"""Hệ quả THỨ HAI cùng gốc. Phiếu CŨ đang "Chờ duyệt" được patch
		`them_nguon_gia_dong_phieu.py` backfill mang `nguon_gia = "Hợp
		đồng"` nhưng `blanket_order = NULL` (patch chép từ `hdnt`, vốn NULL
		với mọi phiếu lập từ giao diện thật). `_suy_nguon_gia` đóng băng
		dòng sau Nháp nên chúng KHÔNG tự lành.

		Trước vòng sửa: nhánh `or not bo: continue` bỏ qua hẳn những dòng
		đó → hạn mức vẫn được canh (ở tầng `dat_hang`) nhưng thông điệp
		KHÔNG có tên khoa — hỏng đúng vế đặc tả §5.6 mà Task 5 phải giữ."""
		doc = self._phieu_cho_duyet(items=[
			{"item_code": self.item_hd, "so_luong_de_xuat": 5},
		])
		# Mô phỏng ĐÚNG dữ liệu patch để lại: có `nguon_gia`, không có
		# `blanket_order`. Ghi thẳng DB vì `_suy_nguon_gia` đã đóng băng.
		frappe.db.set_value(
			"Portal De Xuat Mua Item", doc.items[0].name, "blanket_order", None
		)
		doc.reload()
		self.assertFalse(doc.items[0].blanket_order)
		self.assertEqual(doc.items[0].nguon_gia, NGUON_GIA_HOP_DONG)

		with self.assertRaises(frappe.ValidationError) as ctx:
			de_xuat_duyet.duyet_va_tao_don(doc.name, "Administrator")
		self.assertIn(TEN_KHOA_DA_TIEU, str(ctx.exception))
