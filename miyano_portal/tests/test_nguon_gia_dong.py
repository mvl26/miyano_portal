"""`nguon_gia` cấp DÒNG của phiếu đề xuất (Task 2 gộp luồng đặt hàng,
2026-08-19 — thay cho `loai_don` cấp PHIẾU đã xoá).

Spec 2026-10-09 (giá theo Price List, §3.2 / §4.3) đổi NGUỒN của nó: mỗi
dòng tự suy `nguon_gia` từ Price List của khách — có giá → "Bảng giá", chưa
có → "Chờ báo giá"; `blanket_order` luôn rỗng. Hợp đồng khung không còn
được hỏi, nên các bài về luật phân định giữa nhiều hợp đồng (Ruling P14),
về ngày hiệu lực/`docstatus` của hợp đồng (Ruling P18) và về hạn mức lúc
duyệt đã bị xoá cùng hành vi; các bài còn lại đã đổi fixture từ "đưa mã vào
hợp đồng" sang "đặt `Item Price`" (mỗi bài đảo kỳ vọng mang chú thích "Đảo
theo spec …"). Phần đóng băng dòng (`dong_bang`) giữ nguyên luật, trừ
ngoại lệ của Ruling R5: dòng "Bảng giá" đã mất giá chuyển sang "Chờ báo
giá" ở lần gửi duyệt kế tiếp (ca đầy đủ ở `test_phieu_bang_gia.py`).
`co_dong_cho_bao_gia()` vẫn thay thế mọi chỗ trước đây hỏi `loai_don`.

Dùng lại fixture khách/khoa/vật tư chung (`fixtures_de_xuat.dung_fixture`,
mã hàng `_TEST DX ITEM`) — cùng khuôn `test_de_xuat_duyet.py`. Tự dựng thêm
các mã hàng phụ để mỗi ca có mã RIÊNG, không dùng chung trạng thái giá.

`FrappeTestCase` chỉ rollback một lần mỗi CLASS, nên `setUp` tự đặt lại
trạng thái giá của hai mã dùng chung thay vì tin method trước để lại gì.
"""

import frappe
from frappe.tests.utils import FrappeTestCase

from miyano_portal import de_xuat_duyet
from miyano_portal.miyano_portal.doctype.portal_de_xuat_mua.portal_de_xuat_mua import (
	TRANG_THAI_NHAP,
)
from miyano_portal.tests.fixtures_de_xuat import dung_fixture

COMPANY = "Miyano Việt Nam"

NGUON_GIA_HOP_DONG = "Hợp đồng"
NGUON_GIA_BANG_GIA = "Bảng giá"
NGUON_GIA_CHO_BAO_GIA = "Chờ báo giá"


def _don_phieu_cu():
	"""Dọn Sales Order + Blanket Order test TRƯỚC, rồi mới hạ phiếu
	`_TEST DX%` về Nháp cho `dung_fixture()` xoá — ĐÚNG THỨ TỰ bẫy
	`test_de_xuat_duyet.py::_don_phieu_cu` đã ghi: `dung_fixture()` xoá
	`Portal De Xuat Mua` mỗi `setUp()`, Frappe (`revert_series_if_last`)
	LÙI bộ đếm đặt tên khi bản ghi mới nhất của chuỗi "DXM-2026-" bị xoá,
	nên phiếu ở test SAU có thể được cấp LẠI đúng tên phiếu test TRƯỚC vừa
	xoá. Nếu Sales Order của test trước (lớp này CÓ tạo — `duyet_va_tao_
	don`) còn sống với `custom_request_id` = đúng tên đó, BR-O12 (chống
	trùng đơn) sẽ coi phiếu MỚI là bấm-lại của đơn CŨ và trả nguyên Sales
	Order cũ. Dọn Sales Order trước cắt đứt khả năng đó.

	Dọn Blanket Order — vài bài trong `TestNguonGiaDong` còn dựng hợp đồng
	khung thật (để chứng minh nó KHÔNG còn quyết định gì); dọn để các dòng
	phiếu đang trỏ `blanket_order` vào chúng không cản việc xoá ở lần chạy
	sau, không phải vì chúng còn ảnh hưởng tới nguồn giá."""
	for r in frappe.get_all(
		"Sales Order", filters={"customer": ["like", "_TEST DX%"], "docstatus": 0}
	):
		frappe.delete_doc("Sales Order", r.name, force=True, ignore_permissions=True)
	for r in frappe.get_all(
		"Blanket Order", filters={"customer": ["like", "_TEST DX%"]}, fields=["name", "docstatus"]
	):
		# `delete_doc` từ chối xoá thẳng bản ghi đã nộp, phải HUỶ trước.
		if r.docstatus == 1:
			frappe.get_doc("Blanket Order", r.name).cancel()
		frappe.delete_doc("Blanket Order", r.name, force=True, ignore_permissions=True)
	frappe.db.sql(
		"""UPDATE `tabPortal De Xuat Mua` SET trang_thai = %s
		   WHERE customer LIKE '\\_TEST DX%%'""",
		TRANG_THAI_NHAP,
	)


class TestNguonGiaDong(FrappeTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		_don_phieu_cu()
		f = dung_fixture(self)
		self.kh_a = f.kh_a
		self.kh_b = f.kh_b
		self.khoa_huyethoc = f.khoa_huyethoc
		# Hai mã dùng chung của lớp: `item_co_gia` LUÔN có giá 100 trong
		# Price List của khách A, `item_chua_gia` KHÔNG có dòng giá nào.
		self.item_co_gia = f.item
		self.item_chua_gia = self._tao_item("_TEST DX ITEM NGOAI HD")

		self.price_list = self._tao_price_list("_TEST DX NGUON GIA PRICE")
		frappe.db.set_value(
			"Customer", self.kh_a, "default_price_list", self.price_list
		)
		self._xoa_gia(self.item_co_gia)
		self._xoa_gia(self.item_chua_gia)
		self._tao_gia(self.item_co_gia, self.price_list, 100)

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

	def _tao_price_list(self, ten):
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

	def _xoa_gia(self, item_code):
		"""Gỡ MỌI dòng giá bán của mã hàng thử nghiệm này (ở mọi bảng giá) —
		"sales gỡ giá khỏi Price List" là thao tác thật làm một dòng mất
		giá."""
		for ten in frappe.get_all(
			"Item Price", filters={"item_code": item_code, "selling": 1}, pluck="name"
		):
			frappe.delete_doc("Item Price", ten, force=True, ignore_permissions=True)

	def _item_co_gia_rieng(self, ten, rate=100):
		"""Mã hàng RIÊNG của một ca, có giá trong Price List của khách A —
		để ca đó gỡ/sửa giá mà không đụng `item_co_gia` dùng chung."""
		ma = self._tao_item(ten)
		self._xoa_gia(ma)
		self._tao_gia(ma, self.price_list, rate)
		return ma

	def _bo(self, customer, items):
		"""Blanket Order SUBMIT thật, còn hiệu lực — chỉ để chứng minh hợp
		đồng khung KHÔNG còn quyết định nguồn giá hay chặn việc duyệt.

		Mọi lời gọi trong lớp này khai `rate: 0` (hợp đồng CHƯA KHAI GIÁ):
		hook `on_submit` (`gia_hdnt.tu_hdnt`) chép đơn giá hợp đồng > 0 sang
		Price List của khách, tức một hợp đồng có khai giá sẽ tự làm mã đó
		"có giá" — đúng, nhưng là một đường khác, không phải thứ các bài ở
		đây muốn cô lập."""
		doc = frappe.get_doc({
			"doctype": "Blanket Order", "blanket_order_type": "Selling",
			"customer": customer, "company": COMPANY,
			"from_date": frappe.utils.today(),
			"to_date": frappe.utils.add_days(frappe.utils.today(), 365),
			"items": items,
		}).insert(ignore_permissions=True)
		doc.submit()
		return doc.name

	def _phieu(self, items=None, dat_ngoai=None, hdnt=None):
		doc = frappe.get_doc({
			"doctype": "Portal De Xuat Mua",
			"customer": self.kh_a, "khoa_phong": self.khoa_huyethoc,
			"hdnt": hdnt,
			"items": items or [],
			"dat_ngoai": dat_ngoai or [],
		})
		doc.insert(ignore_permissions=True)
		return doc

	def _dong_don(self, sales_order):
		return {
			d.item_code: d
			for d in frappe.get_doc("Sales Order", sales_order).items
		}

	# ---- _suy_nguon_gia() -------------------------------------------

	# Đảo theo spec 2026-10-09 (giá theo Price List).
	def test_dong_co_gia_trong_price_list_thi_nguon_gia_la_bang_gia(self):
		"""VẾ DƯƠNG. Cố Ý gán SAI `nguon_gia` (client gửi "Chờ báo giá") ở
		input, để một `_suy_nguon_gia()` KHÔNG LÀM GÌ CẢ không thể qua được
		bài này — hàm phải THẬT SỰ tính lại.

		KHÔNG đặt `hdnt` trên phiếu (mặc định `_phieu()` là `None`) — đúng
		dạng MỌI phiếu tạo qua UI thật (`de_xuat_tao_nhap()` tạo phiếu Nháp
		trước khi người dùng chọn mặt hàng); nguồn giá không được phụ thuộc
		field legacy đó. Dòng không mang hợp đồng khung nào."""
		doc = self._phieu(items=[{
			"item_code": self.item_co_gia, "so_luong_de_xuat": 1,
			"nguon_gia": NGUON_GIA_CHO_BAO_GIA,
		}])
		self.assertFalse(doc.hdnt)
		self.assertEqual(doc.items[0].nguon_gia, NGUON_GIA_BANG_GIA)
		self.assertFalse(doc.items[0].blanket_order)

	def test_dong_chua_co_gia_thi_cho_bao_gia(self):
		"""Gán SAI "Bảng giá" ở input, cùng lý do bài trên. Không gán gì
		cũng không ăn may được: default của Select là "Hợp đồng" (lựa chọn
		ĐẦU trong `options`), khác cả hai giá trị hàm được phép ghi."""
		doc = self._phieu(items=[{
			"item_code": self.item_chua_gia, "so_luong_de_xuat": 1,
			"nguon_gia": NGUON_GIA_BANG_GIA,
		}])
		self.assertEqual(doc.items[0].nguon_gia, NGUON_GIA_CHO_BAO_GIA)
		self.assertFalse(doc.items[0].blanket_order)

	# Đảo theo spec 2026-10-09 (giá theo Price List).
	def test_hop_dong_khung_con_hieu_luc_KHONG_con_quyet_dinh_nguon_gia(self):
		"""Trước spec này: mã hàng nằm trong một hợp đồng khung còn hiệu lực
		của khách → "Hợp đồng" + `blanket_order` = hợp đồng thắng cuộc. Giờ
		hợp đồng không được hỏi nữa: mã CHỈ có trong hợp đồng (Price List
		chưa có giá — hợp đồng khai `rate = 0`, xem `_bo`) là "Chờ báo giá";
		mã vừa có hợp đồng vừa có giá Price List là "Bảng giá". Cả hai đều
		không mang `blanket_order`."""
		chi_hd = self._tao_item("_TEST DX ITEM CHI CO HOP DONG")
		self._xoa_gia(chi_hd)
		self._bo(self.kh_a, [
			{"item_code": chi_hd, "qty": 5, "rate": 0},
			{"item_code": self.item_co_gia, "qty": 5, "rate": 0},
		])
		doc = self._phieu(items=[
			{"item_code": chi_hd, "so_luong_de_xuat": 1},
			{"item_code": self.item_co_gia, "so_luong_de_xuat": 1},
		])
		self.assertEqual(doc.items[0].nguon_gia, NGUON_GIA_CHO_BAO_GIA)
		self.assertFalse(doc.items[0].blanket_order)
		self.assertEqual(doc.items[1].nguon_gia, NGUON_GIA_BANG_GIA)
		self.assertFalse(doc.items[1].blanket_order)

	# Đảo theo spec 2026-10-09 (giá theo Price List).
	def test_gia_trong_bang_gia_cua_khach_khac_khong_lam_dong_thanh_bang_gia(self):
		"""Cách ly — giá chỉ có trong Price List của khách B (cùng mã hàng)
		không làm dòng của khách A thành "Bảng giá".

		VẾ DƯƠNG trong CÙNG phiếu: dòng `item_co_gia` (có giá trong Price
		List của CHÍNH khách A) vẫn phải ra "Bảng giá". Thiếu vế này, một
		phép suy hỏng toàn phần (luôn "Chờ báo giá") vẫn qua được bài — vế
		âm một mình không phân biệt được "cách ly đúng" với "hỏng hết"."""
		bang_b = self._tao_price_list("_TEST DX NGUON GIA PRICE B")
		frappe.db.set_value("Customer", self.kh_b, "default_price_list", bang_b)
		self._tao_gia(self.item_chua_gia, bang_b, 999)
		doc = self._phieu(items=[
			{
				"item_code": self.item_chua_gia, "so_luong_de_xuat": 1,
				"nguon_gia": NGUON_GIA_BANG_GIA,   # gán SAI để không ăn may
			},
			{
				"item_code": self.item_co_gia, "so_luong_de_xuat": 1,
				"nguon_gia": NGUON_GIA_CHO_BAO_GIA,   # gán SAI, cùng lý do
			},
		])
		self.assertEqual(doc.items[0].nguon_gia, NGUON_GIA_CHO_BAO_GIA)
		self.assertEqual(doc.items[1].nguon_gia, NGUON_GIA_BANG_GIA)

	# ---- co_dong_cho_bao_gia() ---------------------------------------

	def test_phieu_toan_dong_bang_gia_thi_khong_co_dong_cho_bao_gia(self):
		"""VẾ DƯƠNG — bắt buộc: nếu không có test này, một hàm luôn trả
		`True` vẫn qua được các test khác. Gán SAI `nguon_gia` ở input để
		kết quả không đến từ giá trị client gửi."""
		doc = self._phieu(items=[{
			"item_code": self.item_co_gia, "so_luong_de_xuat": 1,
			"nguon_gia": NGUON_GIA_CHO_BAO_GIA,
		}])
		self.assertEqual(doc.items[0].nguon_gia, NGUON_GIA_BANG_GIA)
		self.assertIs(doc.co_dong_cho_bao_gia(), False)

	def test_phieu_co_dong_cho_bao_gia_thi_co_dong_cho_bao_gia(self):
		"""Một dòng có giá, một dòng chưa có giá nằm chung MỘT phiếu (việc
		tách giỏ theo loại là của tầng trên, §4.1 — doctype không cấm)."""
		doc = self._phieu(items=[
			{"item_code": self.item_co_gia, "so_luong_de_xuat": 1},
			{"item_code": self.item_chua_gia, "so_luong_de_xuat": 1},
		])
		self.assertEqual(doc.items[1].nguon_gia, NGUON_GIA_CHO_BAO_GIA)
		self.assertIs(doc.co_dong_cho_bao_gia(), True)

	def test_phieu_chi_co_dong_dat_ngoai_thi_co_dong_cho_bao_gia(self):
		doc = self._phieu(items=[], dat_ngoai=[
			{"ten_hang": "Hàng chưa có mã", "dvt": "Cái", "so_luong": 1},
		])
		self.assertIs(doc.co_dong_cho_bao_gia(), True)

	# ---- QĐ-G1: không tin nguon_gia/blanket_order client gửi ----------

	def test_client_gui_nguon_gia_sai_thi_bi_ghi_de(self):
		"""Client tự gán nguồn giá + một `blanket_order` CÓ THẬT lên cả hai
		loại dòng — `validate()` phải suy lại `nguon_gia` và XOÁ `blanket_
		order` trên cả hai, không tin giá trị client gửi."""
		bo = self._bo(self.kh_a, [{"item_code": self.item_chua_gia, "qty": 5, "rate": 0}])
		doc = self._phieu(items=[
			{
				"item_code": self.item_chua_gia, "so_luong_de_xuat": 1,
				"nguon_gia": NGUON_GIA_HOP_DONG, "blanket_order": bo,
			},
			{
				"item_code": self.item_co_gia, "so_luong_de_xuat": 1,
				"nguon_gia": NGUON_GIA_HOP_DONG, "blanket_order": bo,
			},
		])
		self.assertEqual(doc.items[0].nguon_gia, NGUON_GIA_CHO_BAO_GIA)
		self.assertFalse(doc.items[0].blanket_order)
		self.assertEqual(doc.items[1].nguon_gia, NGUON_GIA_BANG_GIA)
		self.assertFalse(doc.items[1].blanket_order)

	# ---- Đóng băng dòng (`dong_bang`) --------------------------------

	# Đảo theo spec 2026-10-09 (giá theo Price List).
	def test_dong_bang_nguon_gia_luc_gui_duyet_khong_bi_tinh_lai_sau_do(self):
		"""I3 (review vòng 1) — `nguon_gia` phải ĐÓNG BĂNG từ lúc Gửi duyệt.
		Không có chốt đó, `_suy_nguon_gia()` chạy lại ở MỌI `validate()`/
		`save()`: một phiếu đã duyệt với dòng "Bảng giá", nếu giá bị gỡ khỏi
		Price List SAU KHI duyệt (phiếu còn được lưu lại rất lâu sau qua
		luồng xin sửa/duyệt sửa), một lần lưu bất kỳ sẽ ÂM THẦM ghi đè
		thành "Chờ báo giá" — xoá mất bằng chứng dòng đó đã gửi đi với
		nguồn giá nào.

		Hai chiều: dòng "Bảng giá" mất giá vẫn là "Bảng giá"; dòng "Chờ báo
		giá" vừa có giá vẫn là "Chờ báo giá"."""
		item = self._item_co_gia_rieng("_TEST DX ITEM DONG BANG NGUON GIA")
		doc = self._phieu(items=[
			{"item_code": item, "so_luong_de_xuat": 1,
			 "nguon_gia": NGUON_GIA_CHO_BAO_GIA},   # gán SAI, cùng lý do các test trên
			{"item_code": self.item_chua_gia, "so_luong_de_xuat": 1},
		])
		self.assertEqual(doc.items[0].nguon_gia, NGUON_GIA_BANG_GIA)
		self.assertEqual(doc.items[1].nguon_gia, NGUON_GIA_CHO_BAO_GIA)

		doc.ly_do_yeu_cau = "cần gấp"
		doc.gui_duyet()
		doc.reload()
		self.assertEqual(doc.items[0].nguon_gia, NGUON_GIA_BANG_GIA)

		doc.duyet("Administrator")

		# Giá đổi chiều SAU KHI đã duyệt — thao tác thật của sales.
		self._xoa_gia(item)
		self._tao_gia(self.item_chua_gia, self.price_list, 555)

		doc.reload()
		doc.save(ignore_permissions=True)   # một lần lưu bất kỳ sau khi đã duyệt
		doc.reload()
		self.assertEqual(doc.items[0].nguon_gia, NGUON_GIA_BANG_GIA)
		self.assertEqual(doc.items[1].nguon_gia, NGUON_GIA_CHO_BAO_GIA)

	def _phieu_da_gui_roi_mat_gia(self):
		"""Dựng ca: dòng đang là `Bảng giá` (đóng dấu 100), giá bị GỠ khỏi
		Price List trong lúc phiếu nằm chờ duyệt. Trả `(doc, item)`."""
		item = self._item_co_gia_rieng("_TEST DX ITEM THU HOI DONG BANG")
		doc = self._phieu(items=[{"item_code": item, "so_luong_de_xuat": 1}])
		doc.ly_do_yeu_cau = "cần gấp"
		doc.gui_duyet()
		doc.reload()
		self.assertEqual(doc.items[0].nguon_gia, NGUON_GIA_BANG_GIA)
		self.assertEqual(float(doc.items[0].don_gia), 100.0)
		self._xoa_gia(item)
		return doc, item

	# Đảo theo spec 2026-10-09 (giá theo Price List).
	def test_thu_hoi_KHONG_mo_bang_nguon_gia_cua_dong_cu(self):
		"""Review TOÀN NHÁNH (Important) — `thu_hoi()` đặt `trang_thai =
		"Nháp"` TRƯỚC `save()`, nên `validate()` của chính lần lưu đó sẽ
		chạy với cờ đóng băng = False nếu gate hỏi TRẠNG THÁI, và `_suy_
		nguon_gia()` tính lại nguồn giá cho MỌI dòng.

		Bất biến phải giữ: một phiếu ĐÃ TỪNG gửi duyệt thì nguồn giá của các
		dòng CŨ giữ nguyên, kể cả sau khi thu hồi về Nháp. Nên gate hỏi
		`ma_de_xuat` (dấu "đã từng gửi" duy nhất còn sống sau thu hồi),
		không hỏi trạng thái — cùng câu hỏi `on_trash` đã chuyển sang."""
		doc, item = self._phieu_da_gui_roi_mat_gia()
		doc.thu_hoi()
		doc.reload()
		self.assertEqual(doc.trang_thai, TRANG_THAI_NHAP)
		self.assertEqual(doc.items[0].nguon_gia, NGUON_GIA_BANG_GIA)

	# Đảo theo spec 2026-10-09 (giá theo Price List).
	def test_thu_hoi_roi_gui_lai_dong_mat_gia_thanh_cho_bao_gia_KHONG_giu_gia_cu(self):
		"""HẬU QUẢ THẬT mà bài trên canh. Nếu chính `thu_hoi()` lật dòng sang
		"Chờ báo giá" (qua `validate()`), `don_gia` cũ (100, của một giá đã
		bị gỡ) sống nguyên: `_dong_dau_gia` bỏ qua dòng chờ báo giá ở lần
		gửi sau, và quản lý duyệt một dòng còn khoe con số không bảng giá
		nào còn đỡ.

		Ruling R5 — việc chuyển là của LẦN GỬI LẠI (`_dong_dau_gia`), nơi nó
		xoá con dấu CÙNG LÚC: dòng thành "Chờ báo giá", `don_gia = 0`, và
		`_kiem_gia_doi` không còn gì để chặn hay cảnh báo. (Trước R5 dòng
		giữ "Bảng giá" và bị chặn lúc duyệt; trước spec 2026-10-09 tín hiệu
		này là cảnh báo `hop_dong_doi`.)"""
		doc, item = self._phieu_da_gui_roi_mat_gia()
		doc.thu_hoi()
		doc.reload()
		self.assertEqual(float(doc.items[0].don_gia), 100.0)   # thu hồi chưa đụng gì
		doc.gui_duyet()
		doc.reload()
		self.assertEqual(doc.items[0].nguon_gia, NGUON_GIA_CHO_BAO_GIA)
		self.assertEqual(float(doc.items[0].don_gia or 0), 0.0)
		self.assertIs(doc.co_dong_cho_bao_gia(), True)
		self.assertEqual(de_xuat_duyet._kiem_gia_doi(doc), [])

	# Đảo theo spec 2026-10-09 (giá theo Price List).
	def test_thu_hoi_dong_mat_gia_gui_lai_DUYET_DUOC_thanh_don_bao_gia(self):
		"""Bài trên gọi THẲNG `_kiem_gia_doi()` — một hàm nội bộ. Điều người
		dùng thật nhận được là kết quả của `duyet_va_tao_don()`: phiếu gửi
		lại phải duyệt được, đơn đi vòng báo giá với `rate = 0` — không mang
		con số 100 của giá đã bị gỡ."""
		doc, item = self._phieu_da_gui_roi_mat_gia()
		doc.thu_hoi()
		doc.reload()
		doc.gui_duyet()
		doc.reload()
		kq = de_xuat_duyet.duyet_va_tao_don(doc.name, "Administrator")
		self.assertEqual(kq["canh_bao_gia"], [])
		dong = self._dong_don(kq["sales_order"])[item]
		self.assertEqual(float(dong.rate), 0.0)
		self.assertEqual(dong.custom_nguon_gia, "Báo giá")
		self.assertEqual(
			frappe.db.get_value("Sales Order", kq["sales_order"], "custom_loai_don"),
			"Mua lẻ",
		)

	def test_quan_ly_ha_dong_mat_gia_ve_0_thi_duyet_duoc_phan_con_lai(self):
		"""`_kiem_gia_doi` chỉ xét dòng SẼ VÀO ĐƠN. Dòng "Bảng giá" mất giá
		mà quản lý đã hạ `so_luong_duyet` về 0 không được chặn các dòng còn
		lại của phiếu."""
		mat = self._item_co_gia_rieng("_TEST DX ITEM MAT GIA HA VE 0")
		doc = self._phieu(items=[
			{"item_code": mat, "so_luong_de_xuat": 1},
			{"item_code": self.item_co_gia, "so_luong_de_xuat": 2},
		])
		doc.ly_do_yeu_cau = "cần hàng"
		doc.gui_duyet()
		doc.reload()
		self._xoa_gia(mat)
		doc.items[0].so_luong_duyet = 0
		doc.save(ignore_permissions=True)

		kq = de_xuat_duyet.duyet_va_tao_don(doc.name, "Administrator")
		self.assertEqual(kq["canh_bao_gia"], [])
		self.assertEqual(list(self._dong_don(kq["sales_order"])), [self.item_co_gia])

	def test_thu_hoi_roi_them_dong_MOI_van_duoc_suy_dung(self):
		"""VẾ DƯƠNG — bản vá không được biến thành "phiếu có mã thì đóng băng
		CẢ TẬP DÒNG". Thu hồi tồn tại để nhân viên SỬA phiếu; một dòng thêm
		vào sau khi thu hồi chưa từng được ai đóng dấu, nên nó phải được suy
		bình thường — nếu không nó giữ default Select "Hợp đồng" (lựa chọn
		ĐẦU trong `options`), nguồn giá không dòng mới nào được mang nữa."""
		doc, item = self._phieu_da_gui_roi_mat_gia()
		doc.thu_hoi()
		doc.reload()
		doc.append("items", {
			"item_code": self.item_chua_gia, "so_luong_de_xuat": 2,
			"nguon_gia": NGUON_GIA_HOP_DONG,   # gán SAI để không ăn may
		})
		doc.append("items", {
			"item_code": self.item_co_gia, "so_luong_de_xuat": 2,
			"nguon_gia": NGUON_GIA_HOP_DONG,   # gán SAI để không ăn may
		})
		doc.save(ignore_permissions=True)
		doc.reload()
		self.assertEqual(doc.items[1].item_code, self.item_chua_gia)
		self.assertEqual(doc.items[1].nguon_gia, NGUON_GIA_CHO_BAO_GIA)
		self.assertEqual(doc.items[2].item_code, self.item_co_gia)
		self.assertEqual(doc.items[2].nguon_gia, NGUON_GIA_BANG_GIA)
		self.assertFalse(doc.items[2].blanket_order)

	def test_dong_moi_them_sau_gui_duyet_van_duoc_suy_dung_khong_an_theo_mac_dinh(self):
		"""I3 — VẾ THỨ HAI cần thiết: chốt đóng băng ở `_suy_nguon_gia()`
		KHÔNG được `return` sớm mù quáng cho CẢ PHIẾU — `_chan_sua_so_luong_
		de_xuat` tự nó vẫn CHO PHÉP thêm dòng MỚI sau khi gửi duyệt (Đường
		lọt #1 — quản lý điều chỉnh qua `_ap_dieu_chinh`, dòng mới bắt buộc
		`so_luong_de_xuat = 0`). Nếu `_suy_nguon_gia()` return sớm cho TOÀN
		BỘ `self.items` một khi phiếu đã qua khỏi Nháp, dòng MỚI đó không
		bao giờ được tính — nó giữ nguyên default Select "Hợp đồng" (lựa
		chọn ĐẦU trong `options`, xem `get_static_default_value`). Chỉ đóng
		băng DÒNG ĐÃ CÓ lúc gửi duyệt, không đóng băng cả TẬP DÒNG."""
		doc = self._phieu(items=[{"item_code": self.item_co_gia, "so_luong_de_xuat": 1}])
		doc.ly_do_yeu_cau = "cần gấp"
		doc.gui_duyet()
		doc.reload()

		doc.append("items", {
			"item_code": self.item_chua_gia, "so_luong_de_xuat": 0,
			"nguon_gia": NGUON_GIA_HOP_DONG,   # gán SAI để không ăn may
		})
		doc.save(ignore_permissions=True)
		doc.reload()
		self.assertEqual(doc.items[1].item_code, self.item_chua_gia)
		self.assertEqual(doc.items[1].nguon_gia, NGUON_GIA_CHO_BAO_GIA)
		self.assertFalse(doc.items[1].blanket_order)

	# Đảo theo spec 2026-10-09 (giá theo Price List).
	def test_gui_duyet_lai_sau_tu_choi_tren_doc_tai_moi_khong_vo(self):
		"""I3 (advisor, ngay sau vòng sửa 1) — `_suy_nguon_gia()` KHÔNG được
		đọc `self.get_doc_before_save()` khi đóng băng: nó còn được gọi từ
		`_dong_dau_gia()` chạy TRỰC TIẾP trong `gui_duyet()`, TRƯỚC `self.
		save()`, mà `_doc_before_save` chỉ được Frappe điền trong một chu
		trình `save()` ĐÃ XẢY RA trên CHÍNH object Python đó. Lần gửi ĐẦU cũng
		đi qua nhánh đóng băng (mã phiếu được cấp TRƯỚC `_dong_dau_gia()`),
		nhưng bài này canh đường dễ vỡ hơn — RESUBMIT-SAU-TỪ-CHỐI: endpoint
		thật nạp một `Document` MỚI qua `frappe.get_doc()`
		mỗi request rồi gọi `.gui_duyet()` ngay. Mô phỏng đúng đường đó —
		nạp lại `Document` MỚI thay vì tái dùng object đã tự `save()` trong
		test (khác `test_de_xuat_doctype.py::test_tu_choi_roi_sua_roi_gui_
		lai`, vốn tái dùng MỘT object nên `tu_choi()`'s `save()` đã âm thầm
		điền sẵn `_doc_before_save` cho `gui_duyet()` sau đó)."""
		doc = self._phieu(items=[{"item_code": self.item_co_gia, "so_luong_de_xuat": 1}])
		doc.ly_do_yeu_cau = "cần gấp"
		doc.gui_duyet()
		doc.tu_choi("Vượt dự toán")
		ten = doc.name

		moi = frappe.get_doc("Portal De Xuat Mua", ten)
		moi.ly_do_yeu_cau = "cần gấp, gửi lại"
		moi.gui_duyet()
		self.assertEqual(moi.trang_thai, "Chờ duyệt")
		self.assertEqual(moi.items[0].nguon_gia, NGUON_GIA_BANG_GIA)
		self.assertFalse(moi.items[0].blanket_order)
		self.assertEqual(float(moi.items[0].don_gia), 100.0)

	# ---- Đường duyệt: không còn hạn mức, không còn hợp đồng ------------

	# Đảo theo spec 2026-10-09 (giá theo Price List).
	def test_so_luong_vuot_han_muc_hop_dong_van_duyet_duoc(self):
		"""Trước spec này: hợp đồng khung còn 2 (hạn mức 5, đã dùng 3) mà
		phiếu duyệt 10 thì bị chặn "Hạn mức hợp đồng…". `_kiem_han_muc` đã
		bị xoá (§4.3) — cùng tình huống đó giờ duyệt được nguyên số, đơn
		mang giá Price List và không gắn hợp đồng."""
		self._bo(self.kh_a, [
			{"item_code": self.item_co_gia, "qty": 5, "ordered_qty": 3, "rate": 0},
		])
		doc = self._phieu(items=[{"item_code": self.item_co_gia, "so_luong_de_xuat": 10}])
		doc.ly_do_yeu_cau = "cần gấp"
		doc.gui_duyet()
		kq = de_xuat_duyet.duyet_va_tao_don(doc.name, "Administrator")
		dong = self._dong_don(kq["sales_order"])[self.item_co_gia]
		self.assertEqual(float(dong.qty), 10.0)
		self.assertEqual(float(dong.rate), 100.0)
		self.assertFalse(dong.blanket_order)

	# Đảo theo spec 2026-10-09 (giá theo Price List).
	def test_phieu_co_ca_hai_loai_dong_van_canh_bao_gia_doi_cho_dong_bang_gia(self):
		"""`_dong_dau_gia()`/`_kiem_gia_doi()` là HAI NỬA của MỘT tính năng
		(§4.3), và cả hai làm việc THEO TỪNG DÒNG: trong một phiếu có cả hai
		loại dòng, dòng "Bảng giá" được đóng dấu và được so lại; dòng "Chờ
		báo giá" không có `don_gia` nên không tham gia.

		Đi TRỌN đường công khai `duyet_va_tao_don()` — khẳng định cả `canh_
		bao_gia` LẪN đơn thật sinh ra. "Giá đổi" mô phỏng bằng SALES SỬA
		BẢNG GIÁ, thao tác Miyano làm thật."""
		doc = self._phieu(items=[
			{
				"item_code": self.item_co_gia, "so_luong_de_xuat": 1,
				"nguon_gia": NGUON_GIA_CHO_BAO_GIA,
			},
			{"item_code": self.item_chua_gia, "so_luong_de_xuat": 1},
		])
		doc.ly_do_yeu_cau = "cần hàng, hai loại dòng"
		doc.gui_duyet()
		doc.reload()
		self.assertEqual(doc.items[0].don_gia, 100)   # đóng dấu đúng dòng Bảng giá
		self.assertFalse(doc.items[1].don_gia)        # dòng chờ báo giá KHÔNG đóng dấu
		self._tao_gia(self.item_co_gia, self.price_list, 150)

		kq = de_xuat_duyet.duyet_va_tao_don(doc.name, "Administrator")
		self.assertEqual(kq["canh_bao_gia"], [{
			"item_code": self.item_co_gia, "gia_cu": 100.0, "gia_moi": 150.0,
			"ly_do": "gia_doi",
		}])

		theo_ma = self._dong_don(kq["sales_order"])
		self.assertEqual(sorted(theo_ma), sorted([self.item_co_gia, self.item_chua_gia]))
		self.assertEqual(float(theo_ma[self.item_co_gia].rate), 150.0)
		self.assertEqual(theo_ma[self.item_co_gia].custom_nguon_gia, "Bảng giá")
		self.assertFalse(theo_ma[self.item_co_gia].blanket_order)
		self.assertEqual(float(theo_ma[self.item_chua_gia].rate), 0.0)
		self.assertEqual(theo_ma[self.item_chua_gia].custom_nguon_gia, "Báo giá")

	# ---- Phiếu CŨ còn dòng "Hợp đồng" đang chờ duyệt -------------------

	def _phieu_cu_dong_hop_dong(self, item):
		"""Phiếu "Chờ duyệt" lập TRƯỚC spec 2026-10-09: dòng đã đóng băng
		`nguon_gia = "Hợp đồng"` + `blanket_order` + `don_gia` (300) của hồi
		đó.
		Ghi thẳng DB — không đường mã nào còn tạo ra được trạng thái này,
		nhưng dữ liệu thật đang có nó. Trả `(doc, bo)`."""
		bo = self._bo(self.kh_a, [{"item_code": item, "qty": 5, "rate": 0}])
		doc = self._phieu(items=[{"item_code": item, "so_luong_de_xuat": 2}])
		doc.ly_do_yeu_cau = "phiếu cũ"
		doc.gui_duyet()
		frappe.db.set_value("Portal De Xuat Mua Item", doc.items[0].name, {
			"nguon_gia": NGUON_GIA_HOP_DONG, "blanket_order": bo, "don_gia": 300,
		})
		doc.reload()
		self.assertEqual(doc.items[0].nguon_gia, NGUON_GIA_HOP_DONG)
		return doc, bo

	def test_phieu_cu_dong_hop_dong_chua_co_gia_van_duyet_duoc_thanh_dong_bao_gia(self):
		"""Dòng cũ "Hợp đồng" mà Price List của khách CHƯA có giá: không
		được chặn việc duyệt (luật "mất giá thì chặn" chỉ áp cho dòng đóng
		dấu "Bảng giá"), không sinh cảnh báo; đơn nhận `rate = 0`, dấu "Báo
		giá" và đi vòng báo giá. Bằng chứng đóng băng trên phiếu giữ
		nguyên."""
		doc, bo = self._phieu_cu_dong_hop_dong(self.item_chua_gia)
		self.assertIs(doc.co_dong_cho_bao_gia(), False)
		self.assertEqual(de_xuat_duyet._kiem_gia_doi(doc), [])

		kq = de_xuat_duyet.duyet_va_tao_don(doc.name, "Administrator")
		self.assertEqual(kq["canh_bao_gia"], [])
		dong = self._dong_don(kq["sales_order"])[self.item_chua_gia]
		self.assertEqual(float(dong.qty), 2.0)
		self.assertEqual(float(dong.rate), 0.0)
		self.assertEqual(dong.custom_nguon_gia, "Báo giá")
		self.assertFalse(dong.blanket_order)
		self.assertEqual(
			frappe.db.get_value("Sales Order", kq["sales_order"], "custom_loai_don"),
			"Mua lẻ",
		)

		doc.reload()
		self.assertEqual(doc.trang_thai, "Đã duyệt")
		self.assertEqual(doc.items[0].nguon_gia, NGUON_GIA_HOP_DONG)
		self.assertEqual(doc.items[0].blanket_order, bo)
		self.assertEqual(float(doc.items[0].don_gia), 300.0)

	def test_phieu_cu_dong_hop_dong_co_gia_thi_don_mang_gia_price_list(self):
		"""Dòng cũ "Hợp đồng" mà Price List CÓ giá (100, khác con dấu 300 của
		hồi đó): đơn mang giá Price List, dấu "Bảng giá". Không có cảnh báo
		`gia_doi` — con dấu của dòng cũ đến từ đường định giá theo hợp đồng,
		so nó với Price List là so hai thứ khác loại."""
		doc, bo = self._phieu_cu_dong_hop_dong(self.item_co_gia)
		kq = de_xuat_duyet.duyet_va_tao_don(doc.name, "Administrator")
		self.assertEqual(kq["canh_bao_gia"], [])
		dong = self._dong_don(kq["sales_order"])[self.item_co_gia]
		self.assertEqual(float(dong.rate), 100.0)
		self.assertEqual(dong.custom_nguon_gia, "Bảng giá")
		self.assertFalse(dong.blanket_order)


class TestBackfillNguonGia(FrappeTestCase):
	"""Patch `patches/v1_25/them_nguon_gia_dong_phieu.py` — backfill
	`nguon_gia`/`blanket_order` cho phiếu ĐÃ CÓ từ `loai_don`/`hdnt` cũ, đọc
	`loai_don` thẳng cột DB (field đã xoá khỏi doctype nên `get_doc` không
	còn thấy nó nữa; `hdnt` thì đọc bình thường qua field còn sống, legacy).

	RIÊNG một class — không đụng `self.bo`/Blanket Order của
	`TestNguonGiaDong`, và tự dọn state DB thô nó tạo ra."""

	def setUp(self):
		frappe.set_user("Administrator")
		_don_phieu_cu()
		f = dung_fixture(self)
		self.kh_a = f.kh_a
		self.khoa_huyethoc = f.khoa_huyethoc
		self.item = f.item

	def tearDown(self):
		frappe.set_user("Administrator")

	def _phieu_cu(self, loai_don_cu, hdnt=None):
		"""Dựng một phiếu qua ORM bình thường (để có cấu trúc hợp lệ) rồi
		XOÁ `nguon_gia`/`blanket_order` vừa được `_suy_nguon_gia()` ghi +
		GHI cột `loai_don` mồ côi (SQL thô) + `hdnt` (field còn sống, ghi
		thẳng qua `db.set_value`, KHÔNG cần một Blanket Order thật tồn tại
		— `db.set_value` bỏ qua kiểm tra Link, đủ dùng cho việc test cơ chế
		backfill của patch) — mô phỏng ĐÚNG state một phiếu tạo TRƯỚC task
		này để lại trong DB thật."""
		doc = frappe.get_doc({
			"doctype": "Portal De Xuat Mua",
			"customer": self.kh_a, "khoa_phong": self.khoa_huyethoc,
			"items": [{"item_code": self.item, "so_luong_de_xuat": 1}],
		})
		doc.insert(ignore_permissions=True)
		if hdnt:
			frappe.db.set_value("Portal De Xuat Mua", doc.name, "hdnt", hdnt)
		frappe.db.sql(
			"update `tabPortal De Xuat Mua Item` set nguon_gia=NULL, "
			"blanket_order=NULL where parent=%s",
			doc.name,
		)
		frappe.db.sql(
			"update `tabPortal De Xuat Mua` set loai_don=%s where name=%s",
			(loai_don_cu, doc.name),
		)
		return doc.name

	def _dong_db(self, ten_phieu):
		return frappe.db.sql(
			"select nguon_gia, blanket_order from `tabPortal De Xuat Mua Item` "
			"where parent=%s",
			ten_phieu, as_dict=True,
		)[0]

	def test_backfill_hdnt_thanh_hop_dong_va_giu_dung_hop_dong_cu(self):
		"""VẾ DƯƠNG — backfill dùng ĐÚNG `hdnt` cũ của chính phiếu đó, KHÔNG
		tính lại "hợp đồng thắng cuộc" theo luật mới (không có ý nghĩa với
		dữ liệu đã đóng băng trong quá khứ)."""
		ten = self._phieu_cu("HĐNT", hdnt="FAKE-BO-BACKFILL-001")
		from miyano_portal.patches.v1_25 import them_nguon_gia_dong_phieu as patch
		patch.execute()
		dong = self._dong_db(ten)
		self.assertEqual(dong.nguon_gia, NGUON_GIA_HOP_DONG)
		self.assertEqual(dong.blanket_order, "FAKE-BO-BACKFILL-001")

	def test_backfill_mua_le_thanh_cho_bao_gia(self):
		ten = self._phieu_cu("Mua lẻ")
		from miyano_portal.patches.v1_25 import them_nguon_gia_dong_phieu as patch
		patch.execute()
		dong = self._dong_db(ten)
		self.assertEqual(dong.nguon_gia, NGUON_GIA_CHO_BAO_GIA)
		self.assertFalse(dong.blanket_order)

	def test_backfill_loai_don_rong_thanh_cho_bao_gia(self):
		"""M3 (review vòng 1) — phiếu cũ CHƯA TỪNG khai `loai_don` (rỗng/
		NULL, dữ liệu rác/thử nghiệm cũ) phải mặc định về "Chờ báo giá",
		KHÔNG bị BỎ QUA để `nguon_gia` trơ NULL. `co_dong_cho_bao_gia()` so
		`nguon_gia == "Chờ báo giá"` bằng chuỗi — `NULL` không khớp so sánh
		đó, nên bỏ qua sẽ khiến phiếu rác này bị đọc NHẦM thành "không có
		dòng chờ báo giá" (trông như thuần hợp đồng), sai theo hướng nguy
		hiểm hơn so với mặc định an toàn."""
		ten = self._phieu_cu(None)
		from miyano_portal.patches.v1_25 import them_nguon_gia_dong_phieu as patch
		patch.execute()
		dong = self._dong_db(ten)
		self.assertEqual(dong.nguon_gia, NGUON_GIA_CHO_BAO_GIA)
		self.assertFalse(dong.blanket_order)

	def test_co_cot_loai_don_dung_trong_moi_truong_test_hien_tai(self):
		"""Guard `_co_cot_loai_don()` phải thấy ĐÚNG cột hiện có trong DB
		test hiện tại (chưa xoá cột mồ côi) — không tự trả `False` một cách
		vô căn cứ. Vế "cột đã biến mất" xác nhận bằng tay ở bước migrate
		cuối task (không ALTER TABLE trong test tự động: DDL không nằm
		trong giao dịch rollback của `FrappeTestCase`, xoá thật một cột sẽ
		làm hỏng schema cho mọi test chạy SAU trong cùng phiên)."""
		from miyano_portal.patches.v1_25 import them_nguon_gia_dong_phieu as patch
		self.assertTrue(patch._co_cot_loai_don())
