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
		field `allow_on_submit`) không được sinh thêm dòng hàng nào.

		BÀI NÀY MỘT MÌNH KHÔNG CÓ RĂNG (review 22/08, Minor-1 — đúng): lưu
		một đơn đã submit đi vào `_action = "update_after_submit"`, mà
		`run_before_save_methods` (`document.py:1138`) chỉ gọi
		`before_validate` khi `_action in ("save", "submit")` — hook không
		hề chạy ở đường này. Giữ bài lại vì nó vẫn canh đúng thứ tên nó nói
		(lưu lại đơn đã xác nhận không đẻ thêm dòng), nhưng RĂNG của chốt
		`docstatus` nằm ở bài ngay dưới."""
		so = self._dat(dat_ngoai=[self._go_tay()])
		so = self._khop(so, self.item_hd)
		so.submit()
		so.reload()
		so_dong = len(so.items)
		# Sửa một field CÓ `allow_on_submit` (đường sửa hợp lệ duy nhất trên
		# đơn đã xác nhận).
		so.custom_ly_do_hen_giao = "khách xin lùi ngày giao"
		so.save(ignore_permissions=True)
		so.reload()
		self.assertEqual(len(so.items), so_dong)

	def test_chot_docstatus_co_rang_o_duong_SUBMIT(self):
		"""RĂNG của chốt `docstatus != 0`, đi ĐƯỜNG CÔNG KHAI `so.submit()`.

		Lúc submit, `_action = "submit"` nên `before_validate` CÓ chạy, và
		`docstatus` đã bằng 1 khi nó chạy (`Document._submit` gán docstatus
		TRƯỚC `save()`). Đó là đường DUY NHẤT hook này gặp `docstatus != 0`.

		Kịch bản: thêm một dòng gõ tay ĐÃ khớp mã rồi bấm Xác nhận THẲNG,
		không lưu trước. Có chốt → không chuyển, dòng đó vẫn "chưa xử lý",
		`kiem_dat_ngoai_da_xu_ly` giữ đơn lại. Không có chốt → hệ lặng lẽ
		dựng thêm dòng hàng NGAY TRONG lần submit và đơn đi tiếp."""
		so = self._dat(dat_ngoai=[self._go_tay()])
		so = self._khop(so, self.item_hd)
		so.append("custom_dat_ngoai", {
			"ten_hang": "Chèn thẳng lúc xác nhận", "dvt": "Cái",
			"so_luong": 3, "item_khop": self.item_ngoai,
		})
		with self.assertRaises(frappe.ValidationError) as ctx:
			so.submit()
		self.assertIn("chưa xử lý", str(ctx.exception))
		so.reload()
		self.assertEqual(so.docstatus, 0)
		self.assertNotIn(self.item_ngoai, [d.item_code for d in so.items])

	# -- CRITICAL-1 (review 22/08): phần đã gộp phải HOÀN TÁC được ----------

	def test_xoa_dong_go_tay_da_chuyen_thi_tru_lai_DUNG_phan_da_gop(self):
		"""Nền của cả Critical-1. Dòng hàng dùng CHUNG: 2 đơn vị khách tự đặt
		+ 4 đơn vị tới từ dòng gõ tay. Xoá dòng gõ tay khỏi đơn nháp thì phải
		trừ lại ĐÚNG 4, còn nguyên 2 — không trừ thiếu (để lại số lượng ma),
		cũng không gỡ cả dòng (ăn mất phần khách đặt trực tiếp)."""
		so = self._dat(
			items=[{"item_code": self.item_da_co, "qty": 2}],
			dat_ngoai=[self._go_tay(so_luong=4)],
		)
		so = self._khop(so, self.item_da_co)
		self.assertEqual(flt(self._dong(so, self.item_da_co).qty), 6.0)

		so.custom_dat_ngoai = []
		so.save(ignore_permissions=True)
		so.reload()
		self.assertEqual(
			flt(self._dong(so, self.item_da_co).qty), 2.0,
			"phải trừ lại ĐÚNG phần dòng gõ tay đã bơm vào, không hơn không kém",
		)
		self.assertEqual(flt(so.total), 2.0 * GIA_HOP_DONG)

	def test_xoa_dong_go_tay_roi_NHAP_LAI_khong_nhan_doi(self):
		"""Đúng NỬA lời khuyên câu báo lỗi bẫy 6 của tôi đưa ra — "khớp nhầm
		mã thì xoá dòng gõ tay rồi nhập lại" — nên đây KHÔNG phải ca hiếm,
		nó là đường gỡ lỗi tôi tự chỉ cho người dùng.

		Không hoàn tác phần đã gộp thì 5 thành 10: tiền nhân đôi, trong khi
		dòng bằng chứng vẫn ghi 5 và không ai có lý do mở ra soi.

		MỘT lần lưu — đúng thao tác lưới Desk: xoá dòng cũ, gõ dòng mới, bấm
		Lưu một lần. (Đường hai lần lưu — xoá, Lưu, rồi gõ lại — được canh
		riêng ở `test_xoa_dong_go_tay_da_chuyen_thi_tru_lai_DUNG_phan_da_gop`,
		trên một đơn còn dòng hàng khác nên trạng thái giữa chừng lưu được.)"""
		so = self._dat(dat_ngoai=[self._go_tay(so_luong=5)])
		so = self._khop(so, self.item_hd)
		tien_truoc = flt(so.total)
		self.assertEqual(tien_truoc, 5.0 * GIA_HOP_DONG)

		so.custom_dat_ngoai = []
		so.append("custom_dat_ngoai", {
			"ten_hang": TEN_GO_TAY, "dvt": "Hộp", "so_luong": 5,
			"item_khop": self.item_hd,
		})
		so.save(ignore_permissions=True)
		so.reload()

		self.assertEqual(
			len([d for d in so.items if d.item_code == self.item_hd]), 1
		)
		self.assertEqual(flt(self._dong(so, self.item_hd).qty), 5.0)
		self.assertEqual(flt(so.total), tien_truoc)

	def _dong_chung_hai_chu(self):
		"""Một dòng hàng có BA chủ: 2 đơn vị khách đặt trực tiếp, 3 của dòng
		gõ tay A, 4 của dòng gõ tay B → 9."""
		so = self._dat(
			items=[{"item_code": self.item_da_co, "qty": 2}],
			dat_ngoai=[self._go_tay("Dòng A", 3), self._go_tay("Dòng B", 4)],
		)
		for d in so.custom_dat_ngoai:
			d.item_khop = self.item_da_co
		so.save(ignore_permissions=True)
		so.reload()
		self.assertEqual(flt(self._dong(so, self.item_da_co).qty), 9.0)
		return so

	def test_dong_hang_dung_CHUNG_xoa_mot_chu_thi_chu_kia_con_nguyen(self):
		"""Ca chính mà cột `so_luong_da_gop` sinh ra để phục vụ: một dòng
		hàng nhiều chủ. Xoá dòng gõ tay B thì chỉ được trừ 4 — phần của A và
		phần khách đặt trực tiếp phải còn nguyên.

		Cũng là bài canh TÍNH TẤT ĐỊNH: phép hoàn tác gom theo DÒNG HÀNG chứ
		không xử lý từng dòng gõ tay một, nên thứ tự lặp không quyết định
		được kết quả."""
		so = self._dong_chung_hai_chu()
		so.custom_dat_ngoai = [
			d for d in so.custom_dat_ngoai if d.ten_hang != "Dòng B"
		]
		so.save(ignore_permissions=True)
		so.reload()
		self.assertEqual(
			flt(self._dong(so, self.item_da_co).qty), 5.0,
			"2 khách đặt trực tiếp + 3 của dòng A còn lại",
		)
		self.assertEqual(len(so.custom_dat_ngoai), 1)
		self.assertEqual(flt(so.custom_dat_ngoai[0].so_luong_da_gop), 3.0)

	def test_giam_tay_so_luong_roi_xoa_mot_chu_KHONG_lam_boc_hoi_phan_chu_kia(self):
		"""Sửa số lượng ngay trên dòng hàng là thao tác BÌNH THƯỜNG (chính
		câu báo lỗi bẫy 6 bảo người dùng làm thế). Sau khi sales hạ dòng
		hàng 9 xuống 4, phần "đã gộp" ghi trên hai dòng gõ tay (3 + 4) đã
		LỚN HƠN số lượng thật còn lại.

		Trừ mù lúc đó cho ra số âm và gỡ HẲN dòng hàng — cuốn theo cả phần
		dòng gõ tay A vẫn đang đòi lẫn phần khách đặt thẳng.

		CON SỐ ĐỔI ở vòng sửa 2 (Ruling P39), hành vi được canh thì KHÔNG.
		Trước P39 bài này ra 3: cái SÀN trả cho A đủ 3 phần nó đòi, nhưng
		làm thế là lặng lẽ đẩy phần khách đặt thẳng về 0. Giờ sổ sách bị ép
		bám theo `qty` ngay tại lần hạ tay:

		    9 = 2 (đặt thẳng) + A 3 + B 4  →  hạ xuống 4, giảm 5
		    phần giảm ăn vào phần ĐÃ GỘP trước, dòng nhập SAU nhường trước:
		        B 4 → 0  (nhường 4),  A 3 → 2  (nhường 1)
		    còn lại: 4 = 2 (đặt thẳng, GIỮ NGUYÊN) + A 2

		Nên xoá B giờ trừ đúng 0 — phần của B đã được hấp thụ từ lúc hạ tay
		— và dòng hàng đứng yên ở 4. Cả hai chủ còn lại đều nguyên vẹn, đó
		mới là điều bài này canh."""
		so = self._dong_chung_hai_chu()
		so.items[0].qty = 4
		so.save(ignore_permissions=True)
		so.reload()
		self.assertEqual(flt(self._dong(so, self.item_da_co).qty), 4.0)
		theo_ten = {d.ten_hang: d for d in so.custom_dat_ngoai}
		self.assertEqual(flt(theo_ten["Dòng B"].so_luong_da_gop), 0.0)
		self.assertEqual(flt(theo_ten["Dòng A"].so_luong_da_gop), 2.0)
		# Bằng chứng khoa đã xin bao nhiêu thì KHÔNG đổi theo (QĐ-G15).
		self.assertEqual(flt(theo_ten["Dòng A"].so_luong), 3.0)
		self.assertEqual(flt(theo_ten["Dòng B"].so_luong), 4.0)

		so.custom_dat_ngoai = [
			d for d in so.custom_dat_ngoai if d.ten_hang != "Dòng B"
		]
		so.save(ignore_permissions=True)
		so.reload()
		dong = self._dong(so, self.item_da_co)
		self.assertEqual(
			flt(dong.qty), 4.0,
			"2 đặt thẳng + 2 của A — không chủ nào bị bốc hơi, và phần B "
			"đã được hấp thụ từ lúc hạ tay nên không trừ thêm lần nữa",
		)
		# Và đường nối bằng chứng ↔ tiền của A phải còn nguyên, nếu không
		# chốt `before_submit` sẽ chặn một đơn thật ra không có gì sai.
		self.assertEqual(so.custom_dat_ngoai[0].dong_hang, dong.name)
		so.submit()
		so.reload()
		self.assertEqual(so.docstatus, 1)

	def test_xoa_sach_dong_go_tay_tren_don_toan_hang_go_tay_bao_cau_ro(self):
		"""Ca biên còn lại của phép hoàn tác: đơn TOÀN hàng gõ tay, xoá SẠCH
		dòng gõ tay thì `items` rỗng mà cũng không còn nhu cầu nào để dựng
		dòng giữ chỗ. ERPNext sẽ ném `MandatoryError: items` — một câu không
		nói cho nhân viên biết chuyện gì vừa xảy ra. Phải nói thẳng ra."""
		so = self._dat(dat_ngoai=[self._go_tay(so_luong=5)])
		so = self._khop(so, self.item_hd)
		so.custom_dat_ngoai = []
		with self.assertRaises(frappe.ValidationError) as ctx:
			so.save(ignore_permissions=True)
		self.assertIn("không còn dòng hàng nào", str(ctx.exception))
		self.assertIn("huỷ hẳn đơn nháp này", str(ctx.exception))

	def test_xoa_het_dong_go_tay_tren_don_TOAN_hang_go_tay(self):
		"""Ca biên của phép hoàn tác: đơn TOÀN hàng gõ tay, khớp mã xong thì
		dòng giữ chỗ đã bị gỡ (bẫy 3) nên `items` chỉ còn đúng dòng vừa sinh.
		Xoá dòng gõ tay đi là `items` RỖNG — mà ERPNext không lưu nổi một
		Sales Order `items` rỗng (`grand_total` là `None`). Đơn phải quay về
		đúng hình dạng §3.4 của nó, không phải nổ một câu của framework."""
		so = self._dat(dat_ngoai=[self._go_tay(so_luong=5), self._go_tay("Dòng hai", 2)])
		so = self._khop(so, self.item_hd)
		self.assertNotIn(ITEM_GIU_CHO, [d.item_code for d in so.items])

		so.custom_dat_ngoai[0].item_khop = None
		# Xoá dòng ĐÃ chuyển, giữ lại dòng chưa khớp → đơn lại "toàn hàng
		# chưa có mã", đúng tiền đề dòng giữ chỗ sinh ra để phục vụ.
		so.custom_dat_ngoai = [d for d in so.custom_dat_ngoai if not d.da_chuyen]
		so.save(ignore_permissions=True)
		so.reload()
		self.assertEqual(
			[d.item_code for d in so.items], [ITEM_GIU_CHO],
			"đơn không còn hàng thật thì phải có lại đúng MỘT dòng giữ chỗ",
		)
		self.assertEqual(len(so.custom_dat_ngoai), 1)

	def test_nhan_ban_don_khong_nhan_doi_so_luong(self):
		"""Nút Duplicate trên Desk (`frappe.copy_doc`) chép CẢ `items` LẪN
		dòng gõ tay `da_chuyen = 1`. Bản sao đi qua `insert()`, ở đó KHÔNG có
		`doc_before_save` để đối chiếu — nên phép chuyển coi dòng gõ tay là
		chưa chuyển và cộng số lượng vào chính dòng hàng vừa được chép sang:
		5 thành 10, dòng bằng chứng vẫn ghi 5."""
		so = self._dat(dat_ngoai=[self._go_tay(so_luong=5)])
		so = self._khop(so, self.item_hd)

		ban_sao = frappe.copy_doc(so)
		ban_sao.custom_request_id = _rid()
		ban_sao.insert(ignore_permissions=True)

		self.assertEqual(
			len([d for d in ban_sao.items if d.item_code == self.item_hd]), 1
		)
		self.assertEqual(flt(self._dong(ban_sao, self.item_hd).qty), 5.0)
		self.assertEqual(flt(ban_sao.total), flt(so.total))
		# Đường nối bằng chứng ↔ tiền phải trỏ vào dòng CỦA BẢN SAO, không
		# phải tên dòng của bản gốc chép sang (tên đó không tồn tại ở đây).
		self.assertEqual(
			ban_sao.custom_dat_ngoai[0].dong_hang,
			self._dong(ban_sao, self.item_hd).name,
		)

	def test_ban_sao_bi_giam_so_luong_thi_KHONG_neo_ma_chuyen_lai(self):
		"""Phép neo bản sao là chỗ DUY NHẤT toàn hàm tin một `da_chuyen` do
		payload mang tới (lúc `insert` không có `doc_before_save` để đối
		chiếu), nên nó đòi dòng hàng mang ĐỦ số lượng dòng gõ tay yêu cầu.

		Chỉ kiểm "có dòng nào cùng mã không" là chưa đủ: một bản sao bị sửa
		số lượng xuống (hoặc một payload dựng tay) sẽ được đóng dấu
		`da_xu_ly = 1` cho một yêu cầu 5 hộp trong khi đơn chỉ có 1 hộp —
		`da_xu_ly` lại nói dối một lần nữa, chỉ nhỏ hơn lần QĐ-G16 dẹp.
		Không neo được thì KHÔNG chặn mà chuyển bình thường: điều bất biến
		cần giữ là mặt hàng khoa yêu cầu có mặt trên đơn ĐỦ số lượng."""
		so = self._dat(dat_ngoai=[self._go_tay(so_luong=5)])
		so = self._khop(so, self.item_hd)

		ban_sao = frappe.copy_doc(so)
		ban_sao.custom_request_id = _rid()
		ban_sao.items[0].qty = 1
		ban_sao.insert(ignore_permissions=True)

		dong = self._dong(ban_sao, self.item_hd)
		self.assertEqual(
			flt(dong.qty), 6.0,
			"không neo được thì phải CHUYỂN lại: 1 sẵn có + 5 khoa yêu cầu",
		)
		self.assertEqual(ban_sao.custom_dat_ngoai[0].dong_hang, dong.name)
		self.assertEqual(flt(ban_sao.custom_dat_ngoai[0].so_luong_da_gop), 5.0)

	# -- IMPORTANT-1 (re-review 25/08): đường LƯU-VÀ-SUBMIT MỘT NHỊP --------
	#
	# `frappe/desk/form/save.py::savedocs` đặt `doc.docstatus = SUBMITTED`
	# RỒI mới gọi `submit()`, và `document.py:1138` vẫn chạy `before_validate`
	# cho `_action in ("save", "submit")`. Nên bấm Submit trên một đơn nháp
	# ĐANG DỞ là MỘT lần lưu duy nhất, đi qua hook với `docstatus == 1`.
	# `so.submit()` trong test đi đúng đường đó (`Document._submit` cũng gán
	# docstatus TRƯỚC `save()`).
	#
	# Mọi BẤT BIẾN của task phải đứng vững ở đường này. Chỉ có phép CHUYỂN
	# (hành động MỚI) mới được từ chối chạy — bẫy 5.

	def test_submit_mot_nhip_van_HOAN_TAC_dong_go_tay_vua_xoa(self):
		"""Xoá một dòng gõ tay rồi bấm thẳng Submit, không lưu trước.

		Trước bản vá, hook thoát ngay ở dòng đầu vì `docstatus == 1`, nên
		`_hoan_tac_dong_bi_xoa` không chạy: `kiem_dat_ngoai_da_xu_ly` cho qua
		(dòng còn lại đã xử lý), `kiem_dong_chuyen_con_tren_don` cũng cho qua
		(dòng còn lại vẫn trỏ đúng — chốt đó KHÔNG kiểm số lượng), và đơn
		XÁC NHẬN với số lượng của dòng đã xoá vẫn nằm nguyên trong tiền."""
		so = self._dong_chung_hai_chu()
		so.custom_dat_ngoai = [
			d for d in so.custom_dat_ngoai if d.ten_hang != "Dòng B"
		]
		so.submit()
		so.reload()
		self.assertEqual(so.docstatus, 1)
		self.assertEqual(
			flt(self._dong(so, self.item_da_co).qty), 5.0,
			"2 khách đặt trực tiếp + 3 của dòng A — phần của dòng B đã xoá "
			"không được đi theo đơn vào tiền",
		)

	def test_submit_mot_nhip_van_CHAN_sua_dong_da_chuyen(self):
		"""Bẫy 6 phải đứng vững ở đường một nhịp: sửa `so_luong` trên dòng đã
		chuyển rồi bấm thẳng Submit. Trước bản vá, phép kiểm bất biến không
		chạy và dòng bằng chứng bị ghi đè ngay lúc xác nhận đơn."""
		so = self._dat(dat_ngoai=[self._go_tay(so_luong=5)])
		so = self._khop(so, self.item_hd)
		so.custom_dat_ngoai[0].so_luong = 9
		with self.assertRaises(frappe.ValidationError) as ctx:
			so.submit()
		self.assertIn("đã chuyển thành dòng hàng", str(ctx.exception))
		so.reload()
		self.assertEqual(so.docstatus, 0)
		self.assertEqual(flt(so.custom_dat_ngoai[0].so_luong), 5.0)

	def test_submit_mot_nhip_van_VE_SINH_co_da_chuyen_client_gui_len(self):
		"""Vệ sinh payload là nơi DUY NHẤT hạ `da_chuyen`/`dong_hang` do
		client gửi lên. Bỏ qua nó ở đường một nhịp thì một dòng mang
		`da_chuyen = 1` mà KHÔNG có `dong_hang` sẽ được
		`kiem_dong_chuyen_con_tren_don` BỎ QUA (chốt đó chỉ xét dòng có
		`dong_hang`) và đơn xác nhận với mặt hàng khoa yêu cầu vắng mặt —
		đúng con bug QĐ-G16 ban đầu, qua đúng cái cửa mà docstring của chính
		hàm này nêu là mối đe doạ."""
		so = self._dat(dat_ngoai=[self._go_tay()])
		so = self._khop(so, self.item_hd)
		so.append("custom_dat_ngoai", {
			"ten_hang": "Dòng khai khống", "dvt": "Cái", "so_luong": 4,
			"item_khop": self.item_ngoai,
			# Payload tự khai "đã chuyển" mà không có dòng hàng nào đứng sau.
			"da_chuyen": 1,
		})
		with self.assertRaises(frappe.ValidationError) as ctx:
			so.submit()
		self.assertIn("chưa xử lý", str(ctx.exception))
		self.assertIn("Dòng khai khống", str(ctx.exception))
		so.reload()
		self.assertEqual(so.docstatus, 0)
		self.assertNotIn(self.item_ngoai, [d.item_code for d in so.items])

	# -- IMPORTANT-2 / Ruling P39: sổ sách không được trôi khỏi `qty` -------

	def test_ha_tay_so_luong_thi_HA_LUON_so_sach_da_gop(self):
		"""Ruling P39 — `qty` được phép nhỏ hơn tổng khoa yêu cầu (giao một
		phần, thương lượng giảm: nghiệp vụ thật, hệ thống không phủ quyết).
		Nhưng SỔ SÁCH phải theo: với mỗi dòng hàng, tổng `so_luong_da_gop`
		của các dòng gõ tay trỏ vào nó ≤ `qty` của dòng đó.

		Phần giảm ăn vào phần ĐÃ GỘP trước, phần khách đặt thẳng giữ nguyên.

		`so_luong` của dòng gõ tay KHÔNG đổi — đó là bằng chứng khoa đã xin
		bao nhiêu, nó không chạy theo quyết định giao hàng."""
		so = self._dat(
			items=[{"item_code": self.item_da_co, "qty": 2}],
			dat_ngoai=[self._go_tay(so_luong=5)],
		)
		so = self._khop(so, self.item_da_co)
		self.assertEqual(flt(self._dong(so, self.item_da_co).qty), 7.0)
		self.assertEqual(flt(so.custom_dat_ngoai[0].so_luong_da_gop), 5.0)

		so.items[0].qty = 4
		so.save(ignore_permissions=True)
		so.reload()
		self.assertEqual(
			flt(so.custom_dat_ngoai[0].so_luong_da_gop), 2.0,
			"giảm 3 thì phần đã gộp 5 phải xuống 2 — 2 hộp khách đặt thẳng giữ nguyên",
		)
		self.assertEqual(
			flt(so.custom_dat_ngoai[0].so_luong), 5.0,
			"bằng chứng khoa xin 5 KHÔNG được sửa theo (QĐ-G15)",
		)

	def test_ha_tay_roi_xoa_dong_go_tay_KHONG_an_mat_phan_khach_dat_thang(self):
		"""Vế tiền của bài trên, và là hố Important-2 đo được trên Desk
		thường: đơn còn một dòng hàng KHÁC nên `_dam_bao_con_dong_hang`
		không ném gì cả — 2 hộp khách đặt thẳng biến mất IM LẶNG."""
		so = self._dat(
			items=[
				{"item_code": self.item_da_co, "qty": 2},
				{"item_code": self.item_hd, "qty": 1},
			],
			dat_ngoai=[self._go_tay(so_luong=5)],
		)
		so = self._khop(so, self.item_da_co)
		self.assertEqual(flt(self._dong(so, self.item_da_co).qty), 7.0)

		so.items[0].qty = 4
		so.save(ignore_permissions=True)
		so.reload()

		so.custom_dat_ngoai = []
		so.save(ignore_permissions=True)
		so.reload()
		dong = self._dong(so, self.item_da_co)
		self.assertEqual(
			flt(dong.qty), 2.0,
			"2 hộp khách ĐẶT THẲNG phải còn nguyên — chỉ phần đã gộp bị trừ",
		)

	# -- BLOCKING (re-review 25/08): P39 mở lại Important-2 qua cửa NHÂN BẢN

	def test_nhan_ban_don_da_HA_TAY_khong_pha_bat_bien_so_sach(self):
		"""Lỗ do CHÍNH vòng sửa 2 tạo ra. Trước P39, `da_chuyen = 1` mà
		`so_luong_da_gop = 0` chỉ có thể nghĩa là "dòng cũ, cột chưa tồn
		tại". P39 khiến trạng thái đó thành BÌNH THƯỜNG VÀ ĐÚNG — dòng B
		trong chính ví dụ của Ruling P39 kết thúc ở 0.

		Phép neo bản sao lại đọc `not flt(so_luong_da_gop)` (falsy) là
		"vắng mặt" và GHI ĐÈ thành `so_luong`. `copy_doc` mặc định
		`ignore_no_copy=True`, `_ep_bat_bien_so_sach` thoát sớm khi
		`truoc is None` — nên không gì kẹp lại đầu ra của phép neo, và bất
		biến P39 VỠ NGAY LÚC INSERT.

		Toàn bước Desk thường: 9 = 2 đặt thẳng + A3 + B4 → hạ tay xuống 4
		(P39: A=2, B=0) → NHÂN BẢN → trên bản sao xoá mỗi B → sự thật phải
		là 4 (2 đặt thẳng + A còn nợ 2), nhưng B bị neo với sổ sách 4 nên
		phép trừ ăn mất 2 đơn vị khách ĐẶT THẲNG — và vì dòng không bị xoá
		nên KHÔNG thông báo nào nổ."""
		so = self._dong_chung_hai_chu()
		so.items[0].qty = 4
		so.save(ignore_permissions=True)
		so.reload()
		theo_ten = {d.ten_hang: d for d in so.custom_dat_ngoai}
		self.assertEqual(
			flt(theo_ten["Dòng B"].so_luong_da_gop), 0.0,
			"tiền đề: P39 đã hạ sổ sách của B về 0 một cách HỢP LỆ",
		)

		ban_sao = frappe.copy_doc(so)
		ban_sao.custom_request_id = _rid()
		ban_sao.insert(ignore_permissions=True)

		dong = self._dong(ban_sao, self.item_da_co)
		tong_gop = flt(sum(flt(d.so_luong_da_gop) for d in ban_sao.custom_dat_ngoai), 3)
		self.assertLessEqual(
			tong_gop, flt(dong.qty),
			"bất biến P39 (tổng đã gộp ≤ qty) phải đứng NGAY LÚC insert bản sao",
		)

		ban_sao.custom_dat_ngoai = [
			d for d in ban_sao.custom_dat_ngoai if d.ten_hang != "Dòng B"
		]
		ban_sao.save(ignore_permissions=True)
		ban_sao.reload()
		self.assertEqual(
			flt(self._dong(ban_sao, self.item_da_co).qty), 4.0,
			"2 khách đặt thẳng + 2 dòng A còn được nợ — không ai bị ăn mất",
		)

	def test_kep_so_sach_chan_payload_khai_gop_vuot_qty(self):
		"""Lớp kẹp CUỐI của P39, canh riêng. `_ep_bat_bien_so_sach` đối chiếu
		`truoc` với hiện tại nên nó KHÔNG có gì để so ở lần `insert` — đúng
		đường một bản sao (hoặc một payload dựng tay) đi vào. Lớp kẹp đọc
		thẳng trạng thái CUỐI nên không cần mốc trước.

		Payload khai khống sổ sách 99 trên một dòng hàng chỉ có 9: bất biến
		P39 vẫn phải đứng sau khi lưu."""
		so = self._dong_chung_hai_chu()
		ban_sao = frappe.copy_doc(so)
		ban_sao.custom_request_id = _rid()
		for d in ban_sao.custom_dat_ngoai:
			d.so_luong_da_gop = 99
		ban_sao.insert(ignore_permissions=True)

		dong = self._dong(ban_sao, self.item_da_co)
		tong = flt(sum(flt(d.so_luong_da_gop) for d in ban_sao.custom_dat_ngoai), 3)
		self.assertLessEqual(
			tong, flt(dong.qty),
			"tổng sổ sách khai được không bao giờ vượt `qty` của dòng hàng",
		)

	# -- MINOR (re-review 25/08): số thực lẻ ------------------------------

	def test_so_luong_LE_khong_de_lai_dong_hang_gan_bang_khong(self):
		"""Bản vá `flt(x, 3)` của vòng trước — tôi từng khai KHÔNG dựng được
		vế đỏ tất định cho nó. **Khai sai**: `Cái`/`Hộp` có
		`must_be_whole_number = 0` (đã truy vấn site) nên số lượng lẻ đi
		qua được, và `tao_sales_order` chỉ chặn `<= 0`.

		0.7 + 0.1 = 0.7999999999999999 trong Python. Với phép trừ số thực
		thô: `con = 0.8 − 0.7999999999999999 = 1.11e-16`, LỚN HƠN `san = 0`,
		nên dòng hàng SỐNG SÓT ở ~0 — rồi làm tròn thành `0.000` lúc lưu và
		rơi vào `validate_qty_is_not_zero` của ERPNext. Quyết định nhánh
		xảy ra TRONG BỘ NHỚ nên phép làm tròn của cột `decimal(21,3)` không
		che được nó, đúng như re-review chỉ ra."""
		so = self._dat(
			items=[{"item_code": self.item_hd, "qty": 1}],
			dat_ngoai=[self._go_tay("Lẻ A", 0.7), self._go_tay("Lẻ B", 0.1)],
		)
		for d in so.custom_dat_ngoai:
			d.item_khop = self.item_da_co
		so.save(ignore_permissions=True)
		so.reload()
		self.assertEqual(flt(self._dong(so, self.item_da_co).qty, 3), 0.8)

		so.custom_dat_ngoai = []
		so.save(ignore_permissions=True)
		so.reload()
		self.assertNotIn(
			self.item_da_co, [d.item_code for d in so.items],
			"trừ hết thì phải GỠ dòng, không để lại một dòng số lượng ~0",
		)

	def test_submit_khi_da_xoa_sach_dong_hang_bao_DUNG_nguyen_nhan(self):
		"""Chặn đúng nhưng KỂ SAI CHUYỆN. Khi `items` rỗng lúc xác nhận đơn,
		`_dam_bao_con_dong_hang` chèn một dòng giữ chỗ, rồi
		`kiem_khong_con_dong_giu_cho` từ chối bằng một câu nói về DÒNG GIỮ
		CHỖ — thứ người dùng chưa hề thêm; họ vừa xoá dòng hàng.

		Dòng giữ chỗ là hình dạng của đơn NHÁP (§3.4), không bao giờ được
		chèn trong lúc xác nhận đơn.

		Trạng thái này phải dựng thẳng ở DB: vệ sinh payload của vòng sửa 2
		đã bịt mọi đường thường tạo ra một dòng `da_chuyen = 1` mà
		`dong_hang` rỗng — chính vì thế hai chốt `before_submit` (vốn nói
		đúng nguyên nhân hơn) đều không có gì để nói ở đây, và câu sai kia
		mới lọt ra."""
		so = self._dat(dat_ngoai=[self._go_tay()])
		so = self._khop(so, self.item_hd)
		frappe.db.set_value(
			"Sales Order Dat Ngoai Item", so.custom_dat_ngoai[0].name,
			"dong_hang", "", update_modified=False,
		)
		so.reload()
		so.items = []
		with self.assertRaises(frappe.ValidationError) as ctx:
			so.submit()
		loi = str(ctx.exception)
		self.assertIn("không còn dòng hàng nào để xác nhận", loi)
		self.assertNotIn(
			ITEM_GIU_CHO, loi,
			"không được kể chuyện dòng giữ chỗ cho một người vừa xoá dòng hàng",
		)
		so.reload()
		self.assertEqual(so.docstatus, 0)

	def test_submit_khi_xoa_dong_hang_van_uu_tien_cau_cua_chot_cu_the(self):
		"""Vế răng của bài trên: khi một chốt `before_submit` CÓ chuyện đúng
		hơn để kể thì phải nhường lời cho nó, không cướp lời bằng câu chung
		chung."""
		so = self._dat(dat_ngoai=[self._go_tay()])
		so = self._khop(so, self.item_hd)
		so.items = []
		with self.assertRaises(frappe.ValidationError) as ctx:
			so.submit()
		self.assertIn("đã bị xoá hoặc đổi mã", str(ctx.exception))

	# -- CRITICAL-2 (review 22/08): đường GỘP không được vứt giá hợp đồng ---

	def test_gop_vao_dong_dang_cho_bao_gia_thi_DAN_gia_hop_dong(self):
		"""Vòng lặp nghiệp vụ CHÍNH chủ đầu tư mô tả, dựng lại NGUYÊN VẸN —
		không sửa tay dòng đơn ở bất kỳ bước nào:

		  1. khoa đặt một mặt hàng lúc nó còn NGOÀI mọi hợp đồng → dòng tầng
		     2, `rate = 0`, chờ Miyano báo giá;
		  2. Miyano BỔ SUNG chính mặt hàng đó vào một hợp đồng khung và ký;
		  3. Miyano khớp một dòng gõ tay về đúng mã đó.

		Đường gộp `return` sớm sẽ VỨT cả giá hợp đồng vừa tính lẫn
		`blanket_order`, nên TOÀN BỘ số lượng (cũ lẫn mới) submit được với
		tiền bằng 0 và không trừ hạn mức nào — đúng nửa còn lại của con bug
		QĐ-G13 sinh ra để dẹp, đi vào bằng cửa gộp."""
		so = self._dat(
			items=[{"item_code": self.item_ngoai, "qty": 2}],
			dat_ngoai=[self._go_tay(so_luong=4)],
		)
		dong = self._dong(so, self.item_ngoai)
		self.assertEqual(flt(dong.rate), 0.0, "tiền đề: dòng đang ở tầng 2")
		self.assertFalse(dong.blanket_order)

		# Miyano ký bổ sung mặt hàng đó vào hợp đồng khung.
		bo_moi = self._bo(self.kh_a, [
			{"item_code": self.item_ngoai, "qty": 100, "rate": GIA_HOP_DONG},
		])
		self._xoa_gia(self.item_ngoai)

		so.reload()
		so = self._khop(so, self.item_ngoai)
		dong = self._dong(so, self.item_ngoai)
		self.assertEqual(flt(dong.qty), 6.0)
		self.assertEqual(
			flt(dong.rate), float(GIA_HOP_DONG),
			"cả cụm số lượng phải mang giá hợp đồng, không đi tiếp với 0 đồng",
		)
		self.assertEqual(dong.blanket_order, bo_moi)
		self.assertEqual(flt(so.total), 6.0 * GIA_HOP_DONG)

	def test_gop_KHONG_de_len_gia_Miyano_da_chot(self):
		"""Vế răng của bài trên: giá đã chốt trên dòng sẵn có là giá Miyano
		đàm phán/đã báo cho khách. Phép gộp chỉ được ĐIỀN VÀO CHỖ TRỐNG,
		tuyệt đối không đè lên một con số đã có."""
		so = self._dat(
			items=[{"item_code": self.item_da_co, "qty": 2}],
			dat_ngoai=[self._go_tay(so_luong=4)],
		)
		so.items[0].rate = 50000
		so.save(ignore_permissions=True)
		so.reload()
		self.assertEqual(flt(so.items[0].rate), 50000.0, "tiền đề: giá đã chốt")

		so = self._khop(so, self.item_da_co)
		dong = self._dong(so, self.item_da_co)
		self.assertEqual(flt(dong.qty), 6.0)
		self.assertEqual(flt(dong.rate), 50000.0, "giá đã chốt phải giữ nguyên")

	# -- CRITICAL-3 (review 22/08): `da_xu_ly` phải còn đúng LÚC SUBMIT -----

	def test_xoa_dong_hang_da_tao_thi_khong_submit_duoc(self):
		"""`da_xu_ly` chỉ nói thật TẠI LÚC chuyển; không có gì canh khoảng
		giữa lúc đó và lúc xác nhận đơn. Nhân viên Desk xoá dòng `items` do
		phép chuyển sinh ra — một thao tác lưới bình thường, không cảnh báo
		gì — thì cờ vẫn bật, `dong_hang` trỏ vào hư không, và đơn XÁC NHẬN
		ĐƯỢC với mặt hàng khoa yêu cầu không có dòng nào, không giá, không
		lên hoá đơn. Đúng con bug QĐ-G16 dẹp, tới bằng cửa XOÁ."""
		so = self._dat(
			items=[{"item_code": self.item_da_co, "qty": 2}],
			dat_ngoai=[self._go_tay()],
		)
		so = self._khop(so, self.item_hd)
		so.items = [d for d in so.items if d.item_code != self.item_hd]
		for idx, d in enumerate(so.items, start=1):
			d.idx = idx
		so.save(ignore_permissions=True)
		so.reload()
		self.assertTrue(
			so.custom_dat_ngoai[0].da_xu_ly, "cờ vẫn đang nói 'đã xử lý'"
		)
		with self.assertRaises(frappe.ValidationError) as ctx:
			so.submit()
		self.assertIn("đã bị xoá hoặc đổi mã", str(ctx.exception))
		self.assertIn(TEN_GO_TAY, str(ctx.exception))
		so.reload()
		self.assertEqual(so.docstatus, 0)

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
		# Câu báo lỗi phải nêu đường gỡ, và (review 22/08) phải nêu đường gỡ
		# AN TOÀN. Bản trước bảo "xoá dòng gõ tay VÀ dòng hàng đã tạo" — làm
		# nửa đầu rồi nhập lại là nhân đôi số lượng, tức chính câu hướng dẫn
		# đang dẫn người dùng vào cái bẫy Critical-1. Giờ chỉ cần xoá dòng gõ
		# tay, hệ tự trừ lại phần đã gộp.
		self.assertIn("XOÁ DÒNG GÕ TAY NÀY", str(ctx.exception))
		self.assertIn("tự trừ lại", str(ctx.exception))

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

	# -- PATCH: nhánh backfill phải THẬT SỰ chạy được ----------------------

	def test_patch_backfill_dien_so_sach_cho_dong_da_chuyen_cu(self):
		"""Bằng chứng patch ở vòng trước mới chỉ chứng minh CỘT TỒN TẠI:
		site này có 0 bản ghi `da_chuyen = 1` lúc chạy, nên câu `update`
		chưa bao giờ đi qua. Bài này dựng đúng hiện trường một đơn nháp mở
		TỪ TRƯỚC bản vá — dòng đã chuyển nhưng sổ sách còn 0 — rồi chạy
		patch và đòi nó điền đúng.

		Quan trọng vì `so_luong_da_gop = 0` nghĩa là "không hoàn tác gì":
		bỏ sót backfill là giữ nguyên lỗ Critical-1 cho mọi đơn đang mở."""
		from miyano_portal.patches.v1_27.them_cot_so_luong_da_gop import execute

		so = self._dat(dat_ngoai=[self._go_tay(so_luong=5)])
		so = self._khop(so, self.item_hd)
		ten_dong = so.custom_dat_ngoai[0].name
		# Hạ về đúng hình dạng bản ghi có trước khi cột này ra đời.
		frappe.db.set_value(
			"Sales Order Dat Ngoai Item", ten_dong, "so_luong_da_gop", 0,
			update_modified=False,
		)
		self.assertEqual(
			flt(frappe.db.get_value(
				"Sales Order Dat Ngoai Item", ten_dong, "so_luong_da_gop"
			)), 0.0,
			"tiền đề: sổ sách đang rỗng, nếu không bài này không kiểm gì cả",
		)

		execute()

		self.assertEqual(
			flt(frappe.db.get_value(
				"Sales Order Dat Ngoai Item", ten_dong, "so_luong_da_gop"
			)), 5.0,
			"backfill phải điền đúng `so_luong` của chính dòng đó",
		)

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
