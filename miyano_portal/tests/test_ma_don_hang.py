"""Task 9 (chủ đầu tư chốt 21/08/2026) — đơn hàng MANG THẲNG mã đề xuất.

Đơn sinh từ cổng có `Sales Order.name` chính là mã phiếu
(`DXA-HUYETHOC-260821-01`), không còn `SAL-ORD-...`. Khách và Miyano nhìn
CÙNG MỘT mã; hoá đơn ghi đúng mã đó.

Ba ràng buộc của task, mỗi cái một bài test ở đây:

  1. Ép tên trong Frappe v15 chỉ có MỘT đường đúng: gán `so.name` VÀ bật
     `so.flags.name_set = True` trước `insert()`. `Document.set_new_name()`
     (`frappe/model/document.py:530`) thoát sớm khi thấy cờ đó. Gán `name`
     mà QUÊN cờ thì `naming_series` của Sales Order ghi đè và mã bị vứt
     IM LẶNG — hỏng kiểu tệ nhất, vì một bài test nhìn thoáng (chỉ kiểm
     "có tạo được đơn không") vẫn xanh.
  2. DÙNG LẠI `ma_de_xuat` của phiếu, KHÔNG gọi `sinh_ma()` lần nữa: hàm
     đó cấp số qua `getseries`, gọi lại ra số KHÁC và đơn mang mã không
     khớp phiếu nào.
  3. Tham số KHÔNG bắt buộc — đơn Miyano tự lập trong Desk không có mã
     ngắn khách + mã khoa nên không suy ra được mã; thiếu mã thì rơi về
     `SAL-ORD-...` như cũ. Đây là điều kiện TƯƠNG THÍCH NGƯỢC, không phải
     một trường hợp biên.

Đơn CŨ giữ tên cũ — chủ đầu tư chốt không đổi tên 140 đơn đã phát sinh;
không có bước migrate nào trong task này.
"""

import re

import frappe
from frappe.tests.utils import FrappeTestCase

from miyano_portal import dat_hang, de_xuat_duyet
from miyano_portal.miyano_portal.doctype.portal_de_xuat_mua.portal_de_xuat_mua import (
	TRANG_THAI_NHAP,
)
from miyano_portal.tests.fixtures_de_xuat import dung_fixture

COMPANY = "Miyano Việt Nam"


def _rid() -> str:
	return frappe.generate_hash(length=12)


def _don_phieu_cu():
	"""Sales Order → Blanket Order → phiếu. ĐÚNG THỨ TỰ đó.

	Bẫy `revert_series_if_last` (xem `test_de_xuat_duyet.py::_don_phieu_cu`)
	NẶNG HƠN hẳn từ Task 9: trước đây hai phiếu trùng tên chỉ đụng nhau qua
	`custom_request_id`; giờ TÊN ĐƠN cũng là mã phiếu, nên một đơn cũ chưa
	dọn sẽ làm phiếu mới ném `DuplicateEntryError` ngay lúc insert."""
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


class TestMaDonHang(FrappeTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		_don_phieu_cu()
		f = dung_fixture(self)
		self.kh_a = f.kh_a
		self.khoa_huyethoc = f.khoa_huyethoc
		self.item = self._tao_item("_TEST DX MA DON ITEM")

	def tearDown(self):
		frappe.set_user("Administrator")

	def _tao_item(self, ten):
		if not frappe.db.exists("Item", ten):
			frappe.get_doc({
				"doctype": "Item", "item_code": ten, "item_name": ten,
				"item_group": frappe.db.get_value("Item Group", {}, "name"),
				"stock_uom": "Nos", "is_stock_item": 0,
			}).insert(ignore_permissions=True)
		return ten

	def _phieu_cho_duyet(self, so_luong=2):
		doc = frappe.get_doc({
			"doctype": "Portal De Xuat Mua",
			"customer": self.kh_a, "khoa_phong": self.khoa_huyethoc,
			"items": [{"item_code": self.item, "so_luong_de_xuat": so_luong}],
		})
		doc.insert(ignore_permissions=True)
		doc.ly_do_yeu_cau = "cần hàng"
		doc.gui_duyet()
		doc.reload()
		return doc

	# ---- ca CHÍNH ---------------------------------------------------

	def test_duyet_phieu_thi_don_mang_thang_ma_de_xuat(self):
		"""VẾ DƯƠNG, CA CHÍNH. `Sales Order.name` PHẢI bằng đúng
		`ma_de_xuat` của phiếu — không phải một mã mới, không phải
		`SAL-ORD-...`."""
		doc = self._phieu_cho_duyet()
		ma = doc.ma_de_xuat
		self.assertTrue(ma, "phiếu phải có mã sau khi gửi duyệt")
		self.assertTrue(
			ma.startswith("DXA-HUYETHOC-"),
			f"fixture phải sinh mã dạng <mã ngắn>-<mã khoa>-<yymmdd>-<số>, gặp {ma}",
		)

		kq = de_xuat_duyet.duyet_va_tao_don(doc.name, "Administrator")
		self.assertEqual(
			kq["sales_order"], ma,
			"đơn phải MANG THẲNG mã phiếu — nếu ra SAL-ORD-... thì `flags."
			"name_set` chưa bật và `naming_series` đã ghi đè IM LẶNG",
		)
		# Đọc lại từ CSDL, không tin giá trị trong bộ nhớ: `naming_series`
		# ghi đè ở tầng `insert()` nên chỉ bản ghi thật mới là bằng chứng.
		self.assertTrue(frappe.db.exists("Sales Order", ma))
		so = frappe.get_doc("Sales Order", ma)
		self.assertEqual(so.customer, self.kh_a)
		self.assertEqual(so.items[0].item_code, self.item)

	def test_don_khong_co_ma_van_giu_dat_ten_goc(self):
		"""CHỐT TƯƠNG THÍCH NGƯỢC — đơn KHÔNG truyền mã (đơn Miyano tự lập
		trong Desk, khách chưa có Mã ngắn, phiếu tự duyệt của đường giỏ
		hàng...) phải giữ nguyên `SAL-ORD-...`. Thiếu bài này, một bản cài
		đặt "luôn ép tên" sẽ ném lỗi hoặc đặt tên rỗng cho mọi đơn không
		đi từ phiếu đề xuất."""
		kq = dat_hang.tao_sales_order(
			self.kh_a,
			items=[{"item_code": self.item, "qty": 1}],
			request_id=_rid(),
		)
		self.assertRegex(
			kq["sales_order"], r"^SAL-ORD-",
			"đơn không có mã phiếu phải rơi về đặt tên gốc của ERPNext",
		)

	def test_ma_rong_cung_roi_ve_dat_ten_goc(self):
		"""Cùng chốt trên nhưng cho ca `ma=""`/`ma=None` gửi TƯỜNG MINH —
		`_dam_bao_phieu_tu_duyet` để `ma_de_xuat = None` khi khách chưa có
		Mã ngắn (QĐ điều phối viên 19/08), nên đường này có thật, không
		phải giả định."""
		kq = dat_hang.tao_sales_order(
			self.kh_a, ma=None,
			items=[{"item_code": self.item, "qty": 1}],
			request_id=_rid(),
		)
		self.assertRegex(kq["sales_order"], r"^SAL-ORD-")

	def test_custom_ma_tra_cuu_van_duoc_ghi(self):
		"""`custom_ma_tra_cuu` KHÔNG bị bỏ — đơn CŨ (140 đơn đã phát sinh,
		vẫn mang tên `SAL-ORD-...`) còn đọc nó, và `portal_order_history`
		phơi nó ra cho khách tra cứu."""
		doc = self._phieu_cho_duyet()
		kq = de_xuat_duyet.duyet_va_tao_don(doc.name, "Administrator")
		so = frappe.get_doc("Sales Order", kq["sales_order"])
		self.assertEqual(so.custom_ma_tra_cuu, doc.ma_de_xuat)
		self.assertEqual(so.custom_de_xuat, doc.name)

	def test_ep_trung_ten_thi_that_bai_on_ao(self):
		"""Ép một mã ĐÃ CÓ phải NỔ, tuyệt đối không âm thầm cấp một tên
		khác rồi báo thành công: khi đó hệ thống có hai đơn mà chỉ một cái
		mang mã khách đang cầm, và không ai biết.

		`DuplicateEntryError` KHÔNG phải `UniqueValidationError` — khối
		`except` chống-trùng-request_id của `_insert_so_idempotent` cố ý
		không bắt nó. Khẳng định cả THÔNG ĐIỆP để một ngày nào đó ai đó nới
		khối `except` kia ra thì bài này đỏ."""
		doc = self._phieu_cho_duyet()
		kq = de_xuat_duyet.duyet_va_tao_don(doc.name, "Administrator")
		ma = kq["sales_order"]

		rid = _rid()
		with self.assertRaises(frappe.DuplicateEntryError) as ctx:
			dat_hang.tao_sales_order(
				self.kh_a, ma=ma,
				items=[{"item_code": self.item, "qty": 1}],
				request_id=rid,
			)
		self.assertIn(ma, str(ctx.exception))
		# VẾ ÂM — không có đơn thứ hai nào được cấp một tên khác.
		self.assertFalse(
			frappe.db.exists("Sales Order", {"custom_request_id": rid}),
			"thất bại phải là thất bại, không phải một đơn mang tên khác",
		)

	def test_ma_co_ky_tu_cam_thi_bi_tu_choi(self):
		"""Vòng sửa 1 (review độc lập). `so.name = ma` + `flags.name_set`
		ĐI VÒNG QUA `frappe.model.naming.validate_name` — hàm mà đường đặt
		tên bình thường luôn chạy qua (nó cấm `<`/`>` và `.strip()` khoảng
		trắng). `ma_de_xuat` dựng từ `Customer.custom_ma_ngan` +
		`Customer Department.ma_khoa`, CẢ HAI là text nhân viên Miyano tự
		gõ ở Desk — nên một ký tự lạc có thể chui thẳng vào KHOÁ CHÍNH của
		Sales Order, nơi nó đi vào URL, tên file PDF và mọi liên kết."""
		with self.assertRaises(frappe.NameError) as ctx:
			dat_hang.tao_sales_order(
				self.kh_a, ma="DXA-<script>-260821-01",
				items=[{"item_code": self.item, "qty": 1}],
				request_id=_rid(),
			)
		self.assertIn("special characters", str(ctx.exception))

	def test_ma_thua_khoang_trang_duoc_lam_sach(self):
		"""Cùng gốc: `validate_name` `.strip()` tên. Một `ma_khoa` gõ thừa
		khoảng trắng ở Desk không được biến thành một khoá chính có khoảng
		trắng ở đầu/cuối — thứ trông giống hệt mã đúng nhưng không bao giờ
		tra ra."""
		doc = self._phieu_cho_duyet()
		kq = de_xuat_duyet.duyet_va_tao_don(doc.name, "Administrator")
		self.assertEqual(kq["sales_order"], kq["sales_order"].strip())

		kq2 = dat_hang.tao_sales_order(
			self.kh_a, ma="  DXA-HUYETHOC-260821-99  ",
			items=[{"item_code": self.item, "qty": 1}],
			request_id=_rid(),
		)
		self.assertEqual(kq2["sales_order"], "DXA-HUYETHOC-260821-99")
