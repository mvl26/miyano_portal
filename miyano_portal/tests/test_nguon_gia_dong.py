"""Task 2 (gộp luồng đặt hàng, 2026-08-19) — `nguon_gia` xuống cấp DÒNG,
thay cho `loai_don` cấp PHIẾU đã xoá.

Trước task này, một `Portal De Xuat Mua` chỉ có thể là "HĐNT" hay "Mua lẻ"
CHO CẢ PHIẾU. Sau task này, MỖI DÒNG tự suy `nguon_gia` ("Hợp đồng" hay "Chờ
báo giá") + `blanket_order` (hợp đồng khung THẮNG CUỘC của riêng dòng đó).
`co_dong_cho_bao_gia()` thay thế mọi chỗ trước đây hỏi `loai_don`.

Ruling P14 (SỬA sau review màn lập phiếu, thay Ruling P7 bản đầu) — suy
CUSTOMER-WIDE (bất kỳ hợp đồng còn hiệu lực nào của `customer`), KHÔNG còn
đọc `self.hdnt` ở đầu phiếu: `hdnt` chỉ còn LEGACY. Lý do bắt buộc đổi:
`de_xuat_tao_nhap()` tạo phiếu Nháp TRƯỚC KHI chọn mặt hàng (`hdnt` luôn
`None` lúc đó), và `de_xuat_luu_nhap()` không có tham số `hdnt` để sửa lại
— bản đầu (đọc `self.hdnt`) sẽ khiến MỌI phiếu tạo qua UI thật không bao
giờ vào được tầng "Hợp đồng".

Dùng lại fixture khách/khoa/vật tư chung (`fixtures_de_xuat.dung_fixture`,
mã hàng `_TEST DX ITEM`) — cùng khuôn `test_de_xuat_duyet.py`. Tự dựng thêm
các mã hàng phụ (không nằm trong hợp đồng nào, hoặc dành riêng cho từng ca
đa-hợp-đồng) để không đụng giả định số lượng/hạn mức của `self.bo` mà các
test hồi quy hạn mức phụ thuộc.

RIÊNG một class/file — cùng lý do `TestDeXuatDuyetHanMuc` tách khỏi
`TestDeXuatDuyet`: lớp này dựng nhiều `Blanket Order` thật, và
`FrappeTestCase` chỉ rollback một lần mỗi CLASS.
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

	Dọn Blanket Order — RIÊNG của file này (Ruling P14): `setUp()` mỗi
	test method trong `TestNguonGiaDong` tự tạo một `self.bo` MỚI (tên tự
	sinh, tăng dần), và `_nguon_gia_theo_ma()` giờ tìm hợp đồng CUSTOMER-
	WIDE (không lọc theo một `hdnt` cố định như bản đầu). Không dọn hợp
	đồng của method TRƯỚC thì hợp đồng đó vẫn "còn hiệu lực" ở method SAU,
	và tie-break "to_date bằng nhau thì name nhỏ hơn thắng" sẽ luôn chọn
	hợp đồng CŨ NHẤT (tên nhỏ nhất) — phá hỏng khẳng định "blanket_order
	của dòng == self.bo (của CHÍNH test này)". `test_de_xuat_duyet.py` (án
	dùng chung `_TEST DX%`) không cần dọn tương tự vì các test ở ĐÓ không
	đọc `row.blanket_order`, chỉ đọc `doc.hdnt` (field LEGACY, tường minh
	theo từng phiếu, không suy customer-wide)."""
	for r in frappe.get_all(
		"Sales Order", filters={"customer": ["like", "_TEST DX%"], "docstatus": 0}
	):
		frappe.delete_doc("Sales Order", r.name, force=True, ignore_permissions=True)
	for r in frappe.get_all(
		"Blanket Order", filters={"customer": ["like", "_TEST DX%"]}, fields=["name", "docstatus"]
	):
		# I2 / Ruling P18 (review vòng 1) — `_bo()` giờ SUBMIT thật
		# (`docstatus == 1`) mặc định; `delete_doc` từ chối xoá thẳng bản
		# ghi đã nộp, phải HUỶ trước.
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
		self.item_hd = f.item
		self.item_ngoai = self._tao_item("_TEST DX ITEM NGOAI HD")

		self.price_list = self._tao_price_list()
		frappe.db.set_value(
			"Customer", self.kh_a, "default_price_list", self.price_list
		)
		self._tao_gia(self.item_hd, self.price_list, 100)

		# Hạn mức 5, đã dùng 3 -> còn 2 (cùng pattern
		# `TestDeXuatDuyetHanMuc.setUp` ở `test_de_xuat_duyet.py`) — dùng
		# cho vế hồi quy hạn mức bên dưới. Các test khác trong lớp này
		# KHÔNG được đụng thêm hợp đồng nào chứa `item_hd` — sẽ phá giả
		# định "còn đúng 2" của vế hồi quy (dùng mã hàng RIÊNG cho các ca
		# đa-hợp-đồng, xem `_tao_item`/từng test).
		# I2 / Ruling P18 (review vòng 1) — SUBMIT thật (`docstatus == 1`):
		# "còn hiệu lực" không còn chấp nhận Nháp. `ordered_qty: 3` không bị
		# `.submit()` đụng tới — `BlanketOrder.update_ordered_qty()` (core
		# ERPNext) chỉ chạy khi có nơi NGOÀI gọi tới (theo dõi từ Sales
		# Order submit), không phải một `on_submit` hook tự chạy của chính
		# doctype này; xác nhận lại bằng test hạn mức bên dưới vẫn đọc đúng
		# "còn 2" sau khi đổi fixture này.
		self.bo = frappe.get_doc({
			"doctype": "Blanket Order", "blanket_order_type": "Selling",
			"customer": self.kh_a, "company": COMPANY,
			"from_date": frappe.utils.today(),
			"to_date": frappe.utils.add_days(frappe.utils.today(), 365),
			# F-1 (review vòng 1) — `rate = 0` = CHƯA KHAI GIÁ, trạng thái
			# BÌNH THƯỜNG và có thật; dòng vẫn là dòng HỢP ĐỒNG nhưng giá
			# rơi xuống bảng giá. Đây là trạng thái DUY NHẤT còn tới được
			# nhánh `gia_doi` sau QĐ-G12 — xem bài cảnh báo giá cuối lớp.
			"items": [{"item_code": self.item_hd, "qty": 5, "ordered_qty": 3, "rate": 0}],
		}).insert(ignore_permissions=True)
		self.bo.submit()
		self.bo = self.bo.name

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
		ten = "_TEST DX NGUON GIA PRICE"
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

	def _bo(self, customer, items, to_date_offset=365, from_date_offset=0, submit=True):
		"""`submit=True` mặc định (I2 / Ruling P18, review vòng 1) — "còn
		hiệu lực" giờ đòi `docstatus == 1`, nên phần lớn hợp đồng dựng
		trong lớp test này phải SUBMIT thật mới được app coi là hiệu lực.
		`submit=False` CHỈ dùng cho ca cố ý kiểm hợp đồng NHÁP (chưa ký)
		KHÔNG được tính là hiệu lực — xem `test_hop_dong_nhap_chua_ky_
		khong_tinh_la_hieu_luc`."""
		doc = frappe.get_doc({
			"doctype": "Blanket Order", "blanket_order_type": "Selling",
			"customer": customer, "company": COMPANY,
			"from_date": frappe.utils.add_days(frappe.utils.today(), from_date_offset),
			"to_date": frappe.utils.add_days(frappe.utils.today(), to_date_offset),
			"items": items,
		}).insert(ignore_permissions=True)
		if submit:
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

	# ---- _suy_nguon_gia() -------------------------------------------

	def test_dong_trong_hop_dong_thi_nguon_gia_la_hop_dong(self):
		"""VẾ DƯƠNG. Cố Ý gán SAI `nguon_gia` (client gửi "Chờ báo giá") ở
		input — Frappe tự đặt "Hợp đồng" (lựa chọn ĐẦU trong `options`) làm
		giá trị mặc định cho một dòng Select mới hoàn toàn không đụng tới
		(xem `frappe.model.create_new.get_static_default_value`), nên nếu
		test không gán sai trước, một `_suy_nguon_gia()` KHÔNG LÀM GÌ CẢ vẫn
		vô tình cho "Hợp đồng" đúng — FALSE GREEN không bắt được hàm rỗng.
		Gán sai bắt buộc hàm phải THẬT SỰ tính lại mới qua được test.

		KHÔNG đặt `hdnt` trên phiếu (mặc định `_phieu()` là `None`) — Ruling
		P14: suy nguồn giá customer-wide, không còn phụ thuộc `self.hdnt`."""
		doc = self._phieu(items=[{
			"item_code": self.item_hd, "so_luong_de_xuat": 1,
			"nguon_gia": NGUON_GIA_CHO_BAO_GIA,
		}])
		self.assertEqual(doc.items[0].nguon_gia, NGUON_GIA_HOP_DONG)
		self.assertEqual(doc.items[0].blanket_order, self.bo)

	def test_dong_co_ma_nhung_ngoai_hop_dong_thi_cho_bao_gia(self):
		doc = self._phieu(items=[{"item_code": self.item_ngoai, "so_luong_de_xuat": 1}])
		self.assertEqual(doc.items[0].nguon_gia, NGUON_GIA_CHO_BAO_GIA)
		self.assertFalse(doc.items[0].blanket_order)

	def test_hop_dong_het_hieu_luc_thi_dong_thanh_cho_bao_gia(self):
		"""Vế THỨ HAI của điều kiện `và` trong brief ("... và hợp đồng còn
		hiệu lực") — riêng vế NÀY chưa test nào ở trên chạm tới: mọi phiếu
		khác trong lớp này trỏ hợp đồng luôn hiệu lực (`to_date` = +365
		ngày), nên nếu bỏ hẳn điều kiện ngày, hay đảo ngược so sánh, hay
		đòi `docstatus == 1` (khác quyết định `< 2` đã chọn), các test khác
		vẫn xanh — cần MỘT hợp đồng đã HẾT HẠN (`to_date` ở QUÁ KHỨ) chứa
		đúng một mã hàng RIÊNG (không phải `item_hd` — `item_hd` đã có
		`self.bo` còn hiệu lực bao phủ, nên không thử được ca "hợp đồng
		DUY NHẤT chứa mã này lại hết hạn" nếu dùng chung mã) để bắt được lỗ
		đó. KHÔNG đặt `hdnt` trên phiếu — hợp đồng hết hạn vẫn phải bị loại
		dù phiếu không hề "khai" nó, đúng tinh thần customer-wide của
		Ruling P14."""
		item_het_han = self._tao_item("_TEST DX ITEM HET HAN")
		self._bo(self.kh_a, [{"item_code": item_het_han, "qty": 5, "rate": 100}],
		         to_date_offset=-1, from_date_offset=-30)
		doc = self._phieu(items=[{
			"item_code": item_het_han, "so_luong_de_xuat": 1,
			"nguon_gia": NGUON_GIA_HOP_DONG,   # gán SAI, cùng lý do các test trên
		}])
		self.assertEqual(doc.items[0].nguon_gia, NGUON_GIA_CHO_BAO_GIA)
		self.assertFalse(doc.items[0].blanket_order)

	def test_hop_dong_het_han_dung_hom_nay_van_con_hieu_luc(self):
		"""M2 (review vòng 1) — biên `to_date >= hôm nay`, chưa test nào chạm
		riêng biên NÀY (đổi `>=` thành `>` không làm bài nào đỏ trước khi
		thêm test này). Hợp đồng hết hạn ĐÚNG HÔM NAY vẫn phải tính là còn
		hiệu lực — đó chính là ngày khoa gấp rút tiêu nốt hạn mức trước khi
		hợp đồng biến mất."""
		item_bien = self._tao_item("_TEST DX ITEM HET HAN HOM NAY")
		bo_bien = self._bo(self.kh_a, [{"item_code": item_bien, "qty": 5, "rate": 100}],
		                    to_date_offset=0, from_date_offset=-30)
		doc = self._phieu(items=[{
			"item_code": item_bien, "so_luong_de_xuat": 1,
			"nguon_gia": NGUON_GIA_CHO_BAO_GIA,   # gán SAI, cùng lý do các test trên
		}])
		self.assertEqual(doc.items[0].nguon_gia, NGUON_GIA_HOP_DONG)
		self.assertEqual(doc.items[0].blanket_order, bo_bien)

	def test_hop_dong_nhap_chua_ky_khong_tinh_la_hieu_luc(self):
		"""I2 / Ruling P18 (review vòng 1) — "còn hiệu lực" phải là
		`docstatus == 1` (đã ký/nộp), KHÔNG phải `< 2` (bản đầu, chỉ loại
		"Đã huỷ", vẫn cho Nháp lọt qua). Hợp đồng NHÁP — sales còn đang
		soạn, CHƯA trình ký — không được để mã hàng "nhảy" sang tầng "Hợp
		đồng" kèm giá: thống nhất với định nghĩa "còn hiệu lực" đã có sẵn ở
		chỗ khác trong app (BR-R7, `items_thuoc_hdnt_hieu_luc()` tại
		`portal_mua_le.py`, đòi `docstatus == 1`). Bản đầu của task này chọn
		`< 2` và biện minh bằng chính fixture `self.bo`/`_bo()` của FILE NÀY
		(toàn bộ đều `.insert()` không `.submit()`) — review gọi đó là một
		dạng fixture-patching trá hình quanh chính cái gate đang được test;
		test này buộc gate phải đòi SUBMIT thật, không được lấy fixture tiện
		tay của chính nó làm bằng chứng."""
		item_nhap = self._tao_item("_TEST DX ITEM HDNT NHAP CHUA KY")
		self._bo(self.kh_a, [{"item_code": item_nhap, "qty": 5, "rate": 100}], submit=False)
		doc = self._phieu(items=[{
			"item_code": item_nhap, "so_luong_de_xuat": 1,
			"nguon_gia": NGUON_GIA_HOP_DONG,   # gán SAI để không ăn may
		}])
		self.assertEqual(doc.items[0].nguon_gia, NGUON_GIA_CHO_BAO_GIA)
		self.assertFalse(doc.items[0].blanket_order)

	def test_hdnt_rong_van_ra_duoc_tang_1(self):
		"""Đây CHÍNH LÀ ca thật sinh ra Ruling P14 — `de_xuat_tao_nhap()` tạo
		phiếu Nháp TRƯỚC KHI người dùng chọn mặt hàng, `hdnt` khi đó luôn
		`None`, và `de_xuat_luu_nhap()` (hàm DUY NHẤT ghi `items` sau đó)
		KHÔNG có tham số `hdnt` để sửa lại — `hdnt` ở đầu phiếu VĨNH VIỄN
		rỗng cho MỌI phiếu tạo qua đúng luồng UI thật. Suy nguồn giá không
		được phép phụ thuộc field đó."""
		doc = self._phieu(hdnt=None, items=[{
			"item_code": self.item_hd, "so_luong_de_xuat": 1,
			"nguon_gia": NGUON_GIA_CHO_BAO_GIA,
		}])
		self.assertFalse(doc.hdnt)
		self.assertEqual(doc.items[0].nguon_gia, NGUON_GIA_HOP_DONG)
		self.assertEqual(doc.items[0].blanket_order, self.bo)

	def test_gio_tron_hai_hop_dong_ca_hai_dong_deu_hop_dong(self):
		"""Ca chính của Ruling P14 — khách có HAI Blanket Order còn hiệu
		lực, mỗi cái phủ một mã hàng KHÁC nhau; MỘT phiếu chứa cả hai dòng
		phải suy ĐÚNG cho TỪNG dòng — không lẫn hợp đồng của dòng này sang
		dòng kia."""
		item_hd2 = self._tao_item("_TEST DX ITEM HD2")
		bo2 = self._bo(self.kh_a, [{"item_code": item_hd2, "qty": 5, "rate": 200}],
		                to_date_offset=180)
		doc = self._phieu(items=[
			{"item_code": self.item_hd, "so_luong_de_xuat": 1,
			 "nguon_gia": NGUON_GIA_CHO_BAO_GIA},
			{"item_code": item_hd2, "so_luong_de_xuat": 1,
			 "nguon_gia": NGUON_GIA_CHO_BAO_GIA},
		])
		self.assertEqual(doc.items[0].nguon_gia, NGUON_GIA_HOP_DONG)
		self.assertEqual(doc.items[0].blanket_order, self.bo)
		self.assertEqual(doc.items[1].nguon_gia, NGUON_GIA_HOP_DONG)
		self.assertEqual(doc.items[1].blanket_order, bo2)

	def test_phan_dinh_khi_mot_ma_thuoc_hai_hop_dong_het_han_som_hon_thang(self):
		"""Phân định BẮT BUỘC (Ruling P14) khi một mã hàng nằm trong NHIỀU
		hợp đồng còn hiệu lực — hợp đồng hết hạn SỚM HƠN thắng. Lưu lại lần
		nữa phải ra CÙNG kết quả (tất định)."""
		item_x = self._tao_item("_TEST DX ITEM PHANDINH")
		bo_xa = self._bo(self.kh_a, [{"item_code": item_x, "qty": 5, "rate": 300}],
		                  to_date_offset=100)
		bo_gan = self._bo(self.kh_a, [{"item_code": item_x, "qty": 5, "rate": 350}],
		                   to_date_offset=10)
		doc = self._phieu(items=[{
			"item_code": item_x, "so_luong_de_xuat": 1,
			"nguon_gia": NGUON_GIA_CHO_BAO_GIA,
		}])
		self.assertEqual(doc.items[0].blanket_order, bo_gan)
		self.assertNotEqual(doc.items[0].blanket_order, bo_xa)
		# Lưu lại lần nữa — chốt TẤT ĐỊNH, không được nhảy qua lại.
		doc.save(ignore_permissions=True)
		doc.reload()
		self.assertEqual(doc.items[0].blanket_order, bo_gan)

	def test_phan_dinh_khi_trung_to_date_thi_name_nho_hon_thang(self):
		"""I1 (review vòng 1) — vế THỨ HAI của luật phân định P14 ("trùng
		`to_date` thì `name` nhỏ hơn thắng") CHƯA có test nào chạm tới: hai
		hợp đồng ở test trên có `to_date_offset` KHÁC NHAU (100 vs 10), nên
		riêng `to_date asc` đã quyết xong, `name asc` không bao giờ được
		gọi tới. Dựng hai hợp đồng CÙNG `to_date` — MariaDB tự do trả kết
		quả theo thứ tự nào cũng đúng nếu không có `name asc` phá hoà,
		khiến CÙNG một phiếu lưu hai lần có thể ra hai `blanket_order`
		khác nhau, đúng thứ Ruling P14 cấm ("tất định" quan trọng hơn "chọn
		đúng hợp đồng nào")."""
		item_y = self._tao_item("_TEST DX ITEM PHANDINH TRUNG NGAY")
		bo_1 = self._bo(self.kh_a, [{"item_code": item_y, "qty": 5, "rate": 400}],
		                 to_date_offset=50)
		bo_2 = self._bo(self.kh_a, [{"item_code": item_y, "qty": 5, "rate": 450}],
		                 to_date_offset=50)
		thang = min(bo_1, bo_2)
		doc = self._phieu(items=[{
			"item_code": item_y, "so_luong_de_xuat": 1,
			"nguon_gia": NGUON_GIA_CHO_BAO_GIA,
		}])
		self.assertEqual(doc.items[0].blanket_order, thang)
		# Lưu lại lần nữa — chốt TẤT ĐỊNH, không được nhảy qua lại.
		doc.save(ignore_permissions=True)
		doc.reload()
		self.assertEqual(doc.items[0].blanket_order, thang)

	def test_hop_dong_cua_khach_khac_khong_lam_dong_thanh_hop_dong(self):
		"""Cách ly — hợp đồng của khách B (cùng mã hàng) không làm dòng của
		khách A thành "Hợp đồng".

		M1 (review vòng 1) — VẾ DƯƠNG thêm vào CÙNG phiếu: dòng `item_hd`
		(hợp đồng CỦA CHÍNH khách A, `self.bo`) phải VẪN ra "Hợp đồng" đúng
		hợp đồng. Thiếu vế này, một `_nguon_gia_theo_ma()` LUÔN trả `{}`
		(hỏng nặng, hỏng toàn phần) vẫn qua được bài — vế âm một mình không
		phân biệt được "cách ly đúng" với "suy hỏng toàn phần"."""
		self._bo(self.kh_b, [{"item_code": self.item_ngoai, "qty": 5, "rate": 100}])
		doc = self._phieu(items=[
			{
				"item_code": self.item_ngoai, "so_luong_de_xuat": 1,
				"nguon_gia": NGUON_GIA_HOP_DONG,   # gán SAI để không ăn may
			},
			{
				"item_code": self.item_hd, "so_luong_de_xuat": 1,
				"nguon_gia": NGUON_GIA_CHO_BAO_GIA,   # gán SAI, cùng lý do
			},
		])
		self.assertEqual(doc.items[0].nguon_gia, NGUON_GIA_CHO_BAO_GIA)
		self.assertFalse(doc.items[0].blanket_order)
		self.assertEqual(doc.items[1].nguon_gia, NGUON_GIA_HOP_DONG)
		self.assertEqual(doc.items[1].blanket_order, self.bo)

	# ---- co_dong_cho_bao_gia() ---------------------------------------

	def test_phieu_toan_dong_hop_dong_thi_khong_co_dong_cho_bao_gia(self):
		"""VẾ DƯƠNG — bắt buộc theo ràng buộc: nếu không có test này, một hàm
		luôn trả `True` vẫn qua được các test khác. Cùng lý do gán SAI
		`nguon_gia` ở test trên: tránh false green từ default "Hợp đồng"
		(lựa chọn đầu của Select) mà Frappe tự gán cho dòng mới chưa đụng
		tới."""
		doc = self._phieu(items=[{
			"item_code": self.item_hd, "so_luong_de_xuat": 1,
			"nguon_gia": NGUON_GIA_CHO_BAO_GIA,
		}])
		self.assertIs(doc.co_dong_cho_bao_gia(), False)

	def test_phieu_tron_thi_co_dong_cho_bao_gia(self):
		"""Ca chính của cả kế hoạch — phiếu vừa có dòng hợp đồng vừa có dòng
		chờ báo giá vẫn nằm chung MỘT phiếu."""
		doc = self._phieu(items=[
			{"item_code": self.item_hd, "so_luong_de_xuat": 1},
			{"item_code": self.item_ngoai, "so_luong_de_xuat": 1},
		])
		self.assertIs(doc.co_dong_cho_bao_gia(), True)

	def test_phieu_chi_co_dong_dat_ngoai_thi_co_dong_cho_bao_gia(self):
		doc = self._phieu(items=[], dat_ngoai=[
			{"ten_hang": "Hàng chưa có mã", "dvt": "Cái", "so_luong": 1},
		])
		self.assertIs(doc.co_dong_cho_bao_gia(), True)

	# ---- QĐ-G1: không tin nguon_gia/blanket_order client gửi ----------

	def test_client_gui_nguon_gia_sai_thi_bi_ghi_de(self):
		"""Dòng THẬT SỰ ngoài hợp đồng nhưng client tự gán 'Hợp đồng' +
		`blanket_order` giả — `validate()` phải suy lại CẢ HAI field, không
		tin giá trị client gửi."""
		doc = self._phieu(items=[{
			"item_code": self.item_ngoai, "so_luong_de_xuat": 1,
			"nguon_gia": NGUON_GIA_HOP_DONG, "blanket_order": self.bo,
		}])
		self.assertEqual(doc.items[0].nguon_gia, NGUON_GIA_CHO_BAO_GIA)
		self.assertFalse(doc.items[0].blanket_order)

	def test_dong_bang_nguon_gia_luc_gui_duyet_khong_bi_tinh_lai_sau_do(self):
		"""I3 (review vòng 1) — `nguon_gia`/`blanket_order` phải ĐÓNG BĂNG
		cùng lúc `so_luong_de_xuat`/`don_gia` bị khoá (`_chan_sua_so_luong_
		de_xuat`, từ lúc Gửi duyệt trở đi — §5.3 "khoá vĩnh viễn"). Trước
		bản vá, `_suy_nguon_gia()` chạy lại VÔ ĐIỀU KIỆN ở MỌI `validate()`/
		`save()` — một phiếu đã duyệt dựa trên hợp đồng còn hiệu lực lúc
		gửi, nếu hợp đồng đó hết hạn SAU KHI duyệt (bình thường — hợp đồng
		có ngày hết hạn cố định, phiếu có thể còn được lưu lại rất lâu sau
		qua luồng xin sửa/duyệt sửa), một lần lưu bất kỳ sau đó sẽ ÂM THẦM
		ghi đè bằng chứng giá đã dùng lúc duyệt thành "Chờ báo giá" — xoá
		mất bằng chứng phiếu ĐÃ được duyệt dựa trên giá hợp đồng nào.

		Chốt ĐÚNG nơi `_chan_sua_so_luong_de_xuat` đã khoá (`is_new() or
		trang_thai == Nháp`), không phải một điều kiện riêng — cùng một
		"phiếu đã gửi duyệt thì khoá vĩnh viễn", không phải hai luật khoá
		lệch nhau."""
		item = self._tao_item("_TEST DX ITEM DONG BANG NGUON GIA")
		bo = self._bo(self.kh_a, [{"item_code": item, "qty": 5, "rate": 100}], to_date_offset=10)
		doc = self._phieu(items=[{
			"item_code": item, "so_luong_de_xuat": 1,
			"nguon_gia": NGUON_GIA_CHO_BAO_GIA,   # gán SAI, cùng lý do các test trên
		}])
		self.assertEqual(doc.items[0].nguon_gia, NGUON_GIA_HOP_DONG)
		self.assertEqual(doc.items[0].blanket_order, bo)

		doc.ly_do_yeu_cau = "cần gấp"
		doc.gui_duyet()
		doc.reload()
		self.assertEqual(doc.items[0].nguon_gia, NGUON_GIA_HOP_DONG)
		self.assertEqual(doc.items[0].blanket_order, bo)

		doc.items[0].so_luong_duyet = 1
		doc.duyet("Administrator")

		# Hợp đồng hết hạn SAU KHI đã duyệt — mô phỏng thời gian trôi qua.
		frappe.db.set_value(
			"Blanket Order", bo, "to_date", frappe.utils.add_days(frappe.utils.today(), -1)
		)

		doc.reload()
		doc.save(ignore_permissions=True)   # một lần lưu bất kỳ sau khi đã duyệt
		doc.reload()
		self.assertEqual(doc.items[0].nguon_gia, NGUON_GIA_HOP_DONG)
		self.assertEqual(doc.items[0].blanket_order, bo)

	def test_dong_moi_them_sau_gui_duyet_van_duoc_suy_dung_khong_an_theo_mac_dinh(self):
		"""I3 — VẾ THỨ HAI cần thiết: chốt đóng băng ở `_suy_nguon_gia()`
		KHÔNG được `return` sớm mù quáng cho CẢ PHIẾU — `_chan_sua_so_luong_
		de_xuat` (nơi I3 mô phỏng theo) tự nó vẫn CHO PHÉP thêm dòng MỚI sau
		khi gửi duyệt (Đường lọt #1 — quản lý điều chỉnh qua `_ap_dieu_
		chinh`, dòng mới bắt buộc `so_luong_de_xuat = 0`). Nếu `_suy_nguon_
		gia()` return sớm cho TOÀN BỘ `self.items` một khi phiếu đã qua khỏi
		Nháp, dòng MỚI đó không bao giờ được tính — nó giữ nguyên default
		Select "Hợp đồng" (lựa chọn ĐẦU trong `options`, xem
		`get_static_default_value`, CHÍNH cái bẫy false-green đã ghi ở đầu
		task này) dù mã hàng của nó không hề nằm trong hợp đồng nào. Đây là
		bẫy đó quay lại qua một cửa khác — chỉ đóng băng DÒNG ĐÃ CÓ lúc gửi
		duyệt, không đóng băng cả TẬP DÒNG."""
		doc = self._phieu(items=[{"item_code": self.item_hd, "so_luong_de_xuat": 1}])
		doc.ly_do_yeu_cau = "cần gấp"
		doc.gui_duyet()
		doc.reload()

		doc.append("items", {
			"item_code": self.item_ngoai, "so_luong_de_xuat": 0,
			"nguon_gia": NGUON_GIA_HOP_DONG,   # gán SAI để không ăn may
		})
		doc.save(ignore_permissions=True)
		doc.reload()
		self.assertEqual(doc.items[1].item_code, self.item_ngoai)
		self.assertEqual(doc.items[1].nguon_gia, NGUON_GIA_CHO_BAO_GIA)
		self.assertFalse(doc.items[1].blanket_order)

	def test_gui_duyet_lai_sau_tu_choi_tren_doc_tai_moi_khong_vo(self):
		"""I3 (advisor, ngay sau vòng sửa 1) — `_suy_nguon_gia()` đọc
		`self.get_doc_before_save()` khi đóng băng, nhưng lời gọi DUY NHẤT
		của nó ở `_dong_dau_gia()` chạy TRỰC TIẾP từ `gui_duyet()`, TRƯỚC
		`self.save()` — `_doc_before_save` chỉ được Frappe điền trong một
		chu trình `save()` ĐÃ XẢY RA trên CHÍNH object Python đó. Đường
		Nháp→Chờ duyệt an toàn (`trang_thai` vẫn "Nháp" lúc đó, `dong_bang`
		False, không đụng `get_doc_before_save()`); đường RESUBMIT-SAU-TỪ-
		CHỐI (`gui_duyet()` gọi được từ "Từ chối") thì KHÔNG — endpoint
		thật nạp một `Document` MỚI qua `frappe.get_doc()` mỗi request rồi
		gọi `.gui_duyet()` ngay, KHÔNG có `save()` nào trước đó trên CHÍNH
		object này để Frappe điền `_doc_before_save`. Mô phỏng đúng đường
		đó — nạp lại `Document` MỚI thay vì tái dùng object đã tự `save()`
		trong test (khác `test_de_xuat_doctype.py::test_tu_choi_roi_sua_
		roi_gui_lai`, vốn tái dùng MỘT object nên `tu_choi()`'s `save()`
		đã âm thầm điền sẵn `_doc_before_save` cho `gui_duyet()` sau đó)."""
		doc = self._phieu(items=[{"item_code": self.item_hd, "so_luong_de_xuat": 1}])
		doc.ly_do_yeu_cau = "cần gấp"
		doc.gui_duyet()
		doc.tu_choi("Vượt dự toán")
		ten = doc.name

		moi = frappe.get_doc("Portal De Xuat Mua", ten)
		moi.ly_do_yeu_cau = "cần gấp, gửi lại"
		moi.gui_duyet()
		self.assertEqual(moi.trang_thai, "Chờ duyệt")
		self.assertEqual(moi.items[0].nguon_gia, NGUON_GIA_HOP_DONG)
		self.assertEqual(moi.items[0].blanket_order, self.bo)

	# ---- Vế hồi quy — phiếu thuần hợp đồng ----------------------------

	def test_phieu_thuan_hop_dong_van_bi_kiem_han_muc(self):
		"""Hạn mức còn lại chỉ 2 (5 - 3, xem setUp) — xin duyệt 10 phải bị
		chặn, giống hệt hành vi trước task này. Gán sai `nguon_gia` ban đầu
		(cùng lý do các test `_suy_nguon_gia` ở trên) — nếu không, gate
		`not co_dong_cho_bao_gia() and doc.hdnt` ở `de_xuat_duyet.py:52` có
		thể vô tình đúng nhờ default "Hợp đồng" của Select, không phải nhờ
		`_suy_nguon_gia()` tính lại thật. `hdnt=self.bo` BẮT BUỘC ở đây —
		`_kiem_han_muc` (không đổi ở Ruling P14, xem docstring gate ở
		`de_xuat_duyet.py:52`) vẫn đọc `doc.hdnt` (field LEGACY, không phải
		field đã xoá) làm hợp đồng DUY NHẤT để kiểm hạn mức."""
		doc = self._phieu(hdnt=self.bo, items=[{
			"item_code": self.item_hd, "so_luong_de_xuat": 10,
			"nguon_gia": NGUON_GIA_CHO_BAO_GIA,
		}])
		doc.ly_do_yeu_cau = "cần gấp, vượt hạn mức"
		doc.gui_duyet()
		doc.reload()
		doc.items[0].so_luong_duyet = 10
		doc.save(ignore_permissions=True)
		doc.reload()
		with self.assertRaises(frappe.ValidationError) as ctx:
			de_xuat_duyet.duyet_va_tao_don(doc.name, "Administrator")
		self.assertIn("Hạn mức hợp đồng", str(ctx.exception))

	def test_phieu_thuan_hop_dong_trong_han_muc_van_duyet_duoc(self):
		"""VẾ DƯƠNG của vế hồi quy — phiếu thuần hợp đồng vẫn duyệt được
		bình thường khi trong hạn mức. Cùng lý do gán sai `nguon_gia`/giữ
		`hdnt=self.bo` ở test trên."""
		doc = self._phieu(hdnt=self.bo, items=[{
			"item_code": self.item_hd, "so_luong_de_xuat": 2,
			"nguon_gia": NGUON_GIA_CHO_BAO_GIA,
		}])
		doc.ly_do_yeu_cau = "cần hàng"
		doc.gui_duyet()
		doc.reload()
		doc.items[0].so_luong_duyet = 2
		doc.save(ignore_permissions=True)
		doc.reload()
		kq = de_xuat_duyet.duyet_va_tao_don(doc.name, "Administrator")
		so = frappe.get_doc("Sales Order", kq["sales_order"])
		self.assertEqual(so.items[0].qty, 2)
		self.assertEqual(so.items[0].blanket_order, self.bo)

	# ---- Hành vi ngầm định (không nêu rõ trong brief) ------------------
	# §5.6 bẫy #2 — `_dong_dau_gia()`/`_kiem_gia_doi()` là HAI NỬA của MỘT
	# tính năng. Fact #3 của brief chỉ nói rõ nửa đầu (đóng dấu giá theo
	# TỪNG DÒNG thay vì cả phiếu) — nửa sau phải theo, không thì đóng dấu
	# xong rồi không ai so sánh gì cả, tính năng cảnh báo giá coi như chết
	# lặng lẽ cho MỌI phiếu trộn (chính loại phiếu task này sinh ra).

	def test_phieu_tron_van_canh_bao_gia_doi_cho_dong_hop_dong(self):
		"""VẾ DƯƠNG — phiếu TRỘN (có cả dòng Chờ báo giá), KHÔNG khai `hdnt`
		ở đầu phiếu (Ruling P14 — đúng dạng phiếu tạo qua UI thật), vẫn
		phải cảnh báo giá đổi cho DÒNG HỢP ĐỒNG của nó, đúng như một phiếu
		thuần hợp đồng. Dòng Chờ báo giá không có `don_gia` nên không tham
		gia so sánh.

		LỊCH SỬ (đọc trước khi định "đơn giản hoá" bài này): vòng sửa I2 của
		Task 2 từng HẠ CẤP test này xuống gọi THẲNG hàm nội bộ
		`de_xuat_duyet._kiem_gia_doi(doc)`, vì từ khi `self.bo` SUBMIT thật
		(Ruling P18) `item_hd` genuinely nằm trong `items_thuoc_hdnt_hieu_
		luc()` và `mode=` cũ LUÔN chọn "ban_le" cho phiếu TRỘN → `_xay_don_
		ban_le` từ chối thẳng dòng hợp đồng ("đang thuộc hợp đồng khung").
		Tức là ĐƯỜNG CÔNG KHAI đang gãy, và bài test đi vòng qua nó.

		Task 4 (điều phối viên yêu cầu KHÔI PHỤC) — hàm dựng đơn đã gộp làm
		một, quyết theo TỪNG DÒNG, nên phiếu trộn duyệt được. Bài này quay
		lại gọi TRỌN `duyet_va_tao_don()`: nếu nó lại phải lách xuống hàm
		gạch dưới thì đường công khai lại hỏng, và đó là thứ phải báo chứ
		không phải né. Khẳng định cả `canh_bao_gia` LẪN đơn thật sinh ra."""
		doc = self._phieu(items=[
			{
				"item_code": self.item_hd, "so_luong_de_xuat": 1,
				"nguon_gia": NGUON_GIA_CHO_BAO_GIA,
			},
			{"item_code": self.item_ngoai, "so_luong_de_xuat": 1},
		])
		doc.ly_do_yeu_cau = "cần hàng, phiếu trộn"
		doc.gui_duyet()
		doc.reload()
		self.assertEqual(doc.items[0].don_gia, 100)   # đóng dấu đúng dòng HĐ
		self.assertFalse(doc.items[1].don_gia)        # dòng chờ báo giá KHÔNG đóng dấu
		# F-1 (review vòng 1) — "giá đổi" mô phỏng bằng SALES SỬA BẢNG GIÁ,
		# thao tác Miyano làm thật. KHÔNG bẻ `Blanket Order Item.rate` trên
		# hợp đồng đã trình ký: field đó không `allow_on_submit` nên không
		# đường mã nào tạo được trạng thái ấy, và nhánh được kiểm khi đó là
		# `hop_dong_doi` chứ không phải `gia_doi`. Dòng này đi qua được vì
		# hợp đồng khai `rate = 0` (chưa khai giá, xem `setUp`) nên giá của
		# nó vốn đến TỪ bảng giá.
		self._tao_gia(self.item_hd, self.price_list, 150)

		kq = de_xuat_duyet.duyet_va_tao_don(doc.name, "Administrator")
		canh_bao_gia = kq["canh_bao_gia"]
		self.assertEqual(len(canh_bao_gia), 1)
		self.assertEqual(canh_bao_gia[0]["item_code"], self.item_hd)
		self.assertEqual(canh_bao_gia[0]["gia_cu"], 100)
		self.assertEqual(canh_bao_gia[0]["gia_moi"], 150)
		# ĐÚNG NHÁNH, không chỉ "có cảnh báo".
		self.assertEqual(canh_bao_gia[0]["ly_do"], "gia_doi")

		# VẾ DƯƠNG của việc khôi phục: đơn THẬT phải ra, ba tầng đúng chỗ.
		so = frappe.get_doc("Sales Order", kq["sales_order"])
		theo_ma = {d.item_code: d for d in so.items}
		self.assertEqual(sorted(theo_ma), sorted([self.item_hd, self.item_ngoai]))
		self.assertEqual(theo_ma[self.item_hd].blanket_order, self.bo)
		self.assertEqual(float(theo_ma[self.item_ngoai].rate), 0.0)


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
