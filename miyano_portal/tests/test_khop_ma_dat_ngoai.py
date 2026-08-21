"""Task 13 (gộp luồng đặt hàng, 2026-08-21) — QĐ-G13…QĐ-G16: khớp mã thì
CHUYỂN dòng gõ tay thành hàng thật, không chỉ dán nhãn.

Triệu chứng chủ đầu tư gặp 21/08: *"khi bên miyano đã khớp mã với yêu cầu
đặt ngoài nhưng anh không thấy chỗ điền giá cho dòng hàng đó, chỉ báo giá
được những hàng trong phần item"*.

Hệ quả THẬT nặng hơn "thiếu ô giá": trước task này `item_khop` chỉ bật
`da_xu_ly`, và `da_xu_ly` là thứ chốt `before_submit` đọc như "đã lo xong"
— nên đơn QUA ĐƯỢC chốt xác nhận trong khi mặt hàng khách gõ tay KHÔNG có
dòng nào trong đơn, không giá, không vào tổng tiền, không lên hoá đơn.

Mọi bài ở đây đi ĐƯỜNG CÔNG KHAI: dựng đơn bằng `dat_hang.tao_sales_order`
rồi `so.save()` sau khi điền `item_khop` — đúng thao tác nhân viên Miyano
làm trên Desk. KHÔNG gọi thẳng hàm chuyển: nếu bài chỉ xanh khi gọi hàm
riêng thì đường công khai vẫn có thể hỏng mà không ai biết — đúng lớp lỗi
task này sinh ra để sửa.

BẪY FIXTURE của chính file này (đọc trước khi sửa): `Blanket Order` phải
được SUBMIT thật (`docstatus == 1`) mới "còn hiệu lực" — một fixture quên
submit sẽ làm CA CHÍNH xanh qua nhánh `rate = 0` (tầng chờ báo giá) chứ
không qua nhánh giá hợp đồng, tức là che mất đúng cái cổng đang kiểm. Ca
chính vì vậy KHẲNG ĐỊNH `gia_hdnt.con_hieu_luc()` trước khi khẳng định giá.
"""

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import flt

from miyano_portal import dat_hang, gia_hdnt
from miyano_portal.portal_mua_le import ITEM_GIU_CHO
from miyano_portal.tests.fixtures_de_xuat import dung_fixture

COMPANY = "Miyano Việt Nam"
PRICE_LIST = "_TEST G13 PRICE"
PRICE_LIST_B = "_TEST G13 PRICE B"

GIA_HOP_DONG = 88000
GIA_HOP_DONG_B = 77000

TEN_GO_TAY = "Găng tay nitrile size M (khách gõ tay)"


def _rid() -> str:
	return frappe.generate_hash(length=12)


def _don_du_lieu_cu():
	"""HUỶ rồi XOÁ Sales Order/Blanket Order của `_TEST DX%`.

	KHÔNG lọc `docstatus: 0`: bản ghi ĐÃ NỘP do method khác để lại vẫn "còn
	hiệu lực" ở method sau (`FrappeTestCase` rollback MỘT LẦN mỗi CLASS) và
	ăn mất `ordered_qty` của hợp đồng, khiến các bài hạn mức/giá PHỤ THUỘC
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


class TestKhopMaDatNgoai(FrappeTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		_don_du_lieu_cu()
		f = dung_fixture(self)
		self.kh_a, self.kh_b = f.kh_a, f.kh_b

		self.item_hd = self._item("_TEST G13 TRONG HOP DONG")
		self.item_ngoai = self._item("_TEST G13 NGOAI HOP DONG")
		self.item_da_co = self._item("_TEST G13 DA CO TREN DON")
		self.item_chi_b = self._item("_TEST G13 CHI KHACH B")

		# MỖI khách một bảng giá RIÊNG (Ruling P32): bảng giá dùng chung là
		# trộn giá đàm phán của hai bệnh viện.
		self.price_list = self._price_list(PRICE_LIST)
		self.price_list_b = self._price_list(PRICE_LIST_B)
		frappe.db.set_value("Customer", self.kh_a, "default_price_list", self.price_list)
		frappe.db.set_value("Customer", self.kh_b, "default_price_list", self.price_list_b)

		# `qty` DƯƠNG cho mọi dòng, KHÔNG phải 0: BR-O15 coi hạn mức 0 là
		# KHÔNG GIỚI HẠN, và dòng không giới hạn CỐ Ý không được gắn
		# `Sales Order Item.blanket_order` — fixture `qty = 0` sẽ làm mọi
		# khẳng định "dòng truy vết đúng hợp đồng" dưới đây thành vô nghĩa.
		self.bo_a = self._bo(self.kh_a, [
			{"item_code": self.item_hd, "qty": 100, "rate": GIA_HOP_DONG},
			{"item_code": self.item_da_co, "qty": 100, "rate": GIA_HOP_DONG},
		])
		self.bo_b = self._bo(self.kh_b, [
			{"item_code": self.item_chi_b, "qty": 100, "rate": GIA_HOP_DONG_B},
		])

		# Hook `Blanket Order.on_submit` vừa dựng `Item Price` cho mọi dòng
		# `rate > 0`. Xoá đi để dựng đúng hiện trường "hợp đồng có giá, bảng
		# giá trống" — nếu để nguyên, ca chính có thể xanh qua bảng giá chứ
		# không qua hợp đồng, và cách ly khách B mất ý nghĩa.
		for ma in (self.item_hd, self.item_ngoai, self.item_da_co, self.item_chi_b):
			self._xoa_gia(ma)

	def tearDown(self):
		frappe.set_user("Administrator")

	# -- fixture -----------------------------------------------------------

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

	def _xoa_gia(self, item_code):
		for r in frappe.get_all("Item Price", filters={"item_code": item_code}, pluck="name"):
			frappe.delete_doc("Item Price", r, force=True, ignore_permissions=True)

	def _bo(self, customer, items):
		"""SUBMIT thật — Ruling P18: "còn hiệu lực" đòi `docstatus == 1`.
		Một fixture quên submit giấu được cả một luồng hỏng sau màn xanh."""
		doc = frappe.get_doc({
			"doctype": "Blanket Order", "blanket_order_type": "Selling",
			"customer": customer, "company": COMPANY,
			"from_date": frappe.utils.today(),
			"to_date": frappe.utils.add_days(frappe.utils.today(), 365),
			"items": items,
		}).insert(ignore_permissions=True)
		doc.submit()
		return doc.name

	def _dat(self, items=None, dat_ngoai=None, customer=None):
		kq = dat_hang.tao_sales_order(
			customer or self.kh_a, items=items or [],
			dat_ngoai=dat_ngoai or [], request_id=_rid(),
		)
		return frappe.get_doc("Sales Order", kq["sales_order"])

	def _go_tay(self, ten=TEN_GO_TAY, so_luong=5):
		return {"ten_hang": ten, "dvt": "Hộp", "so_luong": so_luong}

	def _khop(self, so, item_code, idx=0):
		so.custom_dat_ngoai[idx].item_khop = item_code
		so.save(ignore_permissions=True)
		so.reload()
		return so

	def _dong(self, so, item_code):
		for d in so.items:
			if d.item_code == item_code:
				return d
		self.fail(
			f"Đơn {so.name} KHÔNG có dòng hàng nào mang mã {item_code} — "
			f"khớp mã mới chỉ dán nhãn, chưa CHUYỂN thành hàng thật (QĐ-G13). "
			f"Đang có: {[d.item_code for d in so.items]}"
		)

	# -- CA CHÍNH ----------------------------------------------------------

	def test_khop_ma_hang_trong_hop_dong_sinh_dong_mang_gia_hop_dong(self):
		"""CA CHÍNH (QĐ-G13 + QĐ-G14) — khớp một mã ĐANG NẰM TRONG hợp đồng
		khung còn hiệu lực của khách: đơn phải có một DÒNG HÀNG THẬT, đúng
		số lượng khách gõ, mang ĐÚNG GIÁ HỢP ĐỒNG và gắn đúng hợp đồng."""
		self.assertTrue(
			gia_hdnt.con_hieu_luc(self.bo_a),
			"Tiền đề của ca này là hợp đồng CÒN HIỆU LỰC (đã submit) — "
			"fixture đang che mất chính cổng cần kiểm.",
		)
		self.assertFalse(
			frappe.db.exists("Item Price", {
				"item_code": self.item_hd, "price_list": self.price_list,
			}),
			"Tiền đề: bảng giá TRỐNG, giá phải tới từ CHÍNH hợp đồng.",
		)

		so = self._dat(dat_ngoai=[self._go_tay(so_luong=5)])
		self.assertEqual(
			[d.item_code for d in so.items], [ITEM_GIU_CHO],
			"đơn toàn hàng gõ tay khởi đầu chỉ có dòng giữ chỗ",
		)

		so = self._khop(so, self.item_hd)

		dong = self._dong(so, self.item_hd)
		self.assertEqual(flt(dong.qty), 5.0)
		self.assertEqual(flt(dong.rate), float(GIA_HOP_DONG))
		self.assertEqual(dong.blanket_order, self.bo_a)
		# Dòng phải THẬT SỰ vào tiền của đơn — "không vào tổng tiền" là đúng
		# nửa sau của triệu chứng chủ đầu tư gặp.
		self.assertEqual(flt(dong.amount), 5.0 * GIA_HOP_DONG)
		self.assertGreaterEqual(flt(so.total), 5.0 * GIA_HOP_DONG)

	# -- QĐ-G14 vế âm ------------------------------------------------------

	def test_khop_ma_hang_ngoai_hop_dong_thi_rate_0(self):
		"""Không thuộc hợp đồng còn hiệu lực nào → `rate = 0`, chờ Miyano
		báo giá như mọi dòng tầng 2; KHÔNG gắn hợp đồng nào."""
		so = self._dat(dat_ngoai=[self._go_tay(so_luong=3)])
		so = self._khop(so, self.item_ngoai)
		dong = self._dong(so, self.item_ngoai)
		self.assertEqual(flt(dong.qty), 3.0)
		self.assertEqual(flt(dong.rate), 0.0)
		self.assertFalse(dong.blanket_order)

	def test_hang_ngoai_hop_dong_khong_nhat_gia_cu_trong_bang_gia(self):
		"""Vế răng của bài trên. Hai bẫy chồng nhau, cả hai đều im lặng:

		  * bước 2 của QĐ-G12 (`Item Price`) là bước LUI CỦA DÒNG HỢP ĐỒNG —
		    hỏi nó cho một mã NGOÀI mọi hợp đồng sẽ đọc trúng một giá bảng
		    giá cũ, trong khi cùng mã đó đặt qua giỏ hàng lại ra 0;
		  * `taxes_and_totals.calculate_item_values` ÂM THẦM thay `rate = 0`
		    bằng `price_list_rate` (0 là falsy) — nên kể cả khi phép tra trả
		    0, ERPNext vẫn có thể dán giá bảng giá lên dòng.

		Đơn này mang bảng giá của khách, và bảng giá THẬT SỰ có dòng cho mã
		đó — nếu không, bài này vô nghĩa.
		"""
		gia_cu = 123456
		frappe.get_doc({
			"doctype": "Item Price", "item_code": self.item_ngoai,
			"price_list": self.price_list, "selling": 1,
			"price_list_rate": gia_cu,
		}).insert(ignore_permissions=True)
		self.assertEqual(
			flt(frappe.db.get_value(
				"Item Price",
				{"item_code": self.item_ngoai, "price_list": self.price_list},
				"price_list_rate",
			)),
			float(gia_cu),
			"Tiền đề: bảng giá phải THẬT SỰ khai một giá cho mã ngoài hợp đồng.",
		)
		# Có ÍT NHẤT một dòng hợp đồng trên đơn để `selling_price_list` của
		# đơn là bảng giá của khách — đúng hình dạng đơn TRỘN đã làm bẫy
		# `price_list_rate` sống dậy ở Task 4.
		so = self._dat(
			items=[{"item_code": self.item_hd, "qty": 1}],
			dat_ngoai=[self._go_tay(so_luong=3)],
		)
		self.assertEqual(so.selling_price_list, self.price_list)
		so = self._khop(so, self.item_ngoai)
		dong = self._dong(so, self.item_ngoai)
		self.assertEqual(flt(dong.rate), 0.0)
		self.assertEqual(flt(dong.amount), 0.0)

	# -- BẪY 1: bất biến ----------------------------------------------------

	def test_luu_ba_lan_van_dung_mot_dong(self):
		"""`validate` chạy mỗi lần lưu — khớp mã rồi lưu ba lần KHÔNG được
		đẻ ba dòng hàng (bẫy 1)."""
		so = self._dat(dat_ngoai=[self._go_tay()])
		so = self._khop(so, self.item_hd)
		so_dong_lan_dau = len(so.items)
		for _ in range(2):
			so.save(ignore_permissions=True)
			so.reload()
		self.assertEqual(len(so.items), so_dong_lan_dau)
		self.assertEqual(
			len([d for d in so.items if d.item_code == self.item_hd]), 1
		)
		self.assertEqual(flt(self._dong(so, self.item_hd).qty), 5.0)

	# -- BẪY 2: gộp vào dòng sẵn có ----------------------------------------

	def test_ma_khop_trung_hang_da_co_thi_cong_don(self):
		"""Hai dòng cùng `item_code` trên một Sales Order là mồi cho lệch hạn
		mức và lệch hoá đơn — phải CỘNG DỒN vào dòng sẵn có."""
		so = self._dat(
			items=[{"item_code": self.item_da_co, "qty": 2}],
			dat_ngoai=[self._go_tay(so_luong=4)],
		)
		so_dong_truoc = len(so.items)
		so = self._khop(so, self.item_da_co)
		self.assertEqual(
			len(so.items), so_dong_truoc,
			"gộp số lượng, KHÔNG thêm dòng thứ hai cùng mã",
		)
		self.assertEqual(flt(self._dong(so, self.item_da_co).qty), 6.0)

	def test_hai_dong_go_tay_cung_mot_ma_cung_gop_lam_mot(self):
		"""Hai dòng gõ tay khác tên nhưng Miyano khớp về CÙNG một mã: vẫn
		đúng MỘT dòng hàng, số lượng cộng dồn."""
		so = self._dat(dat_ngoai=[
			self._go_tay("Găng tay hộp lớn", so_luong=2),
			self._go_tay("Găng tay hộp nhỏ", so_luong=3),
		])
		for dong in so.custom_dat_ngoai:
			dong.item_khop = self.item_hd
		so.save(ignore_permissions=True)
		so.reload()
		self.assertEqual(
			len([d for d in so.items if d.item_code == self.item_hd]), 1
		)
		self.assertEqual(flt(self._dong(so, self.item_hd).qty), 5.0)

	# -- QĐ-G15: dòng gõ tay là BẰNG CHỨNG ----------------------------------

	def test_dong_go_tay_con_nguyen_sau_khi_chuyen(self):
		"""Không xoá, không sửa `ten_hang` khách đã gõ — đó là truy vết chủ
		đầu tư yêu cầu từ đầu ("ghi tên ngày giờ lý do yêu cầu")."""
		so = self._dat(dat_ngoai=[self._go_tay()])
		so = self._khop(so, self.item_hd)
		self.assertEqual(len(so.custom_dat_ngoai), 1)
		dong_go_tay = so.custom_dat_ngoai[0]
		self.assertEqual(dong_go_tay.ten_hang, TEN_GO_TAY)
		self.assertEqual(flt(dong_go_tay.so_luong), 5.0)
		self.assertTrue(dong_go_tay.da_chuyen)
		# Đường nối hai chiều: biết dòng bằng chứng nào ứng với dòng tiền nào.
		self.assertEqual(dong_go_tay.dong_hang, self._dong(so, self.item_hd).name)

	# -- BẪY 3: gỡ dòng giữ chỗ --------------------------------------------

	def test_khop_het_thi_dong_giu_cho_bien_mat_va_submit_duoc(self):
		"""Đơn TOÀN hàng gõ tay: sau khi khớp hết, dòng giữ chỗ kỹ thuật phải
		BIẾN MẤT (mẫu in "Xác nhận đơn hàng" không lọc nó) và đơn submit
		được — trước task này đơn cũng submit được, nhưng KHÔNG có dòng hàng
		nào cho thứ khách yêu cầu."""
		so = self._dat(dat_ngoai=[self._go_tay()])
		self.assertIn(ITEM_GIU_CHO, [d.item_code for d in so.items])
		so = self._khop(so, self.item_hd)
		self.assertNotIn(
			ITEM_GIU_CHO, [d.item_code for d in so.items],
			"dòng giữ chỗ phải được gỡ khi đã có hàng thật (bẫy 3)",
		)
		so.submit()
		so.reload()
		self.assertEqual(so.docstatus, 1)
		self.assertEqual(flt(self._dong(so, self.item_hd).qty), 5.0)

	# -- QĐ-G16: `da_xu_ly` phải nói thật -----------------------------------

	def test_da_xu_ly_chi_bat_sau_khi_da_chuyen(self):
		"""`da_xu_ly` hiện nghĩa "đã gắn mã" nhưng chốt `before_submit` đọc
		nó là "đã lo xong" — nó đang NÓI DỐI. Sau task này nó bật khi và chỉ
		khi dòng đã thành hàng thật."""
		so = self._dat(dat_ngoai=[self._go_tay()])
		self.assertFalse(so.custom_dat_ngoai[0].da_xu_ly)
		so = self._khop(so, self.item_hd)
		dong = so.custom_dat_ngoai[0]
		self.assertTrue(dong.da_chuyen, "phải CHUYỂN thật")
		self.assertTrue(dong.da_xu_ly)
		self.assertTrue(
			frappe.db.get_value(
				"Sales Order Dat Ngoai Item", dong.name, "da_xu_ly"
			),
			"giá trị phải xuống DB, không chỉ nằm trong bộ nhớ",
		)

	def test_don_da_submit_khong_chay_lai_phep_chuyen(self):
		"""Bẫy 5 — chỉ chạy khi đơn còn NHÁP. Đơn đã submit lưu lại (đổi
		field `allow_on_submit`) không được sinh thêm dòng hàng nào."""
		so = self._dat(dat_ngoai=[self._go_tay()])
		so = self._khop(so, self.item_hd)
		so.submit()
		so.reload()
		so_dong = len(so.items)
		# Sửa một field CÓ `allow_on_submit` (đường sửa hợp lệ duy nhất trên
		# đơn đã xác nhận) để `before_validate` thật sự chạy lại.
		so.custom_ly_do_hen_giao = "khách xin lùi ngày giao"
		so.save(ignore_permissions=True)
		so.reload()
		self.assertEqual(len(so.items), so_dong)

	# -- BẪY 6: đổi dòng gõ tay SAU khi đã chuyển ---------------------------

	def test_doi_so_luong_sau_khi_chuyen_bi_chan(self):
		"""Bẫy 6 — CHỌN CHẶN, không đồng bộ. Lý do đầy đủ ở docstring
		`portal_mua_le._kiem_dong_da_chuyen_khong_doi`: sau khi số lượng đã
		được GỘP vào một dòng sẵn có (bẫy 2), không còn cách trung thực nào
		để biết phần nào của dòng đó tới từ dòng gõ tay."""
		so = self._dat(dat_ngoai=[self._go_tay(so_luong=5)])
		so = self._khop(so, self.item_hd)
		so.custom_dat_ngoai[0].so_luong = 9
		with self.assertRaises(frappe.ValidationError) as ctx:
			so.save(ignore_permissions=True)
		self.assertIn("đã chuyển thành dòng hàng", str(ctx.exception))
		self.assertIn(self.item_hd, str(ctx.exception))
		so.reload()
		self.assertEqual(flt(so.custom_dat_ngoai[0].so_luong), 5.0)
		self.assertEqual(flt(self._dong(so, self.item_hd).qty), 5.0)

	def test_doi_ma_khop_sau_khi_chuyen_bi_chan(self):
		"""Cùng lý do bẫy 6: `da_chuyen = 1` mà `item_khop` trỏ mã khác là
		một lời nói dối y hệt cái QĐ-G16 vừa dẹp. Câu báo lỗi phải chỉ ra
		đường gỡ, vì trên đơn NHÁP dòng gõ tay vẫn xoá được."""
		so = self._dat(dat_ngoai=[self._go_tay()])
		so = self._khop(so, self.item_hd)
		so.custom_dat_ngoai[0].item_khop = self.item_ngoai
		with self.assertRaises(frappe.ValidationError) as ctx:
			so.save(ignore_permissions=True)
		self.assertIn("đã chuyển thành dòng hàng", str(ctx.exception))
		self.assertIn("xoá dòng gõ tay", str(ctx.exception))

	def test_khop_ma_ve_chinh_dong_giu_cho_bi_tu_choi(self):
		"""Cửa sau của đúng con bug task này dẹp. `item_khop` là Link `Item`
		KHÔNG lọc gì, còn `HANG-DAT-NGOAI` là Item THẬT, không disabled — nên
		trên Desk nó chọn được. Không có chốt, phép gộp (bẫy 2) sẽ dồn số
		lượng vào CHÍNH dòng giữ chỗ rồi phép gỡ (bẫy 3) xoá dòng đó đi:
		`da_chuyen = 1`, `da_xu_ly = 1`, `dong_hang` trỏ vào hư không, và đơn
		submit được trong khi mặt hàng khách yêu cầu không có dòng nào.

		`dat_hang._xay_don` đã chặn đúng mã này ở đường ghi thứ nhất
		(`mat_hang_giu_cho_khong_the_dat`); đây là đường ghi thứ hai."""
		so = self._dat(dat_ngoai=[self._go_tay()])
		so.custom_dat_ngoai[0].item_khop = ITEM_GIU_CHO
		with self.assertRaises(frappe.ValidationError) as ctx:
			so.save(ignore_permissions=True)
		self.assertIn("mã kỹ thuật nội bộ", str(ctx.exception))
		self.assertIn(ITEM_GIU_CHO, str(ctx.exception))
		so.reload()
		# Không được để lại một trạng thái NỬA VỜI: dòng gõ tay vẫn "chưa xử
		# lý", nên chốt `before_submit` vẫn giữ được đơn lại.
		self.assertFalse(so.custom_dat_ngoai[0].da_chuyen)
		self.assertFalse(so.custom_dat_ngoai[0].da_xu_ly)
		self.assertEqual([d.item_code for d in so.items], [ITEM_GIU_CHO])
		with self.assertRaises(frappe.ValidationError) as ctx2:
			so.submit()
		self.assertIn("chưa xử lý", str(ctx2.exception))

	# -- CÁCH LY ------------------------------------------------------------

	def test_gia_hop_dong_khach_b_khong_roi_vao_don_khach_a(self):
		"""HAI vế, cả hai đều DƯƠNG:

		  * mã của CHÍNH khách A ra đúng giá hợp đồng A — nếu vế này chết,
		    vế cách ly bên dưới xanh chỉ vì phép chuyển luôn cho `rate = 0`;
		  * mã CHỈ có trong hợp đồng khách B ra `rate = 0` và KHÔNG gắn hợp
		    đồng nào — 77.000 của B không được rơi sang đơn của A.
		"""
		so = self._dat(dat_ngoai=[
			self._go_tay("Hàng của chính khách A", so_luong=1),
			self._go_tay("Hàng chỉ có trong hợp đồng khách B", so_luong=1),
		])
		so.custom_dat_ngoai[0].item_khop = self.item_hd
		so.custom_dat_ngoai[1].item_khop = self.item_chi_b
		so.save(ignore_permissions=True)
		so.reload()

		cua_a = self._dong(so, self.item_hd)
		self.assertEqual(flt(cua_a.rate), float(GIA_HOP_DONG))
		self.assertEqual(cua_a.blanket_order, self.bo_a)

		cua_b = self._dong(so, self.item_chi_b)
		self.assertEqual(flt(cua_b.rate), 0.0)
		self.assertFalse(cua_b.blanket_order)
