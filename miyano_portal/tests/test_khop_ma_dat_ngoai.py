"""Task 13 (gộp luồng đặt hàng, 2026-08-21) — QĐ-G13…QĐ-G16: khớp mã thì
CHUYỂN dòng gõ tay thành hàng thật, không chỉ dán nhãn.

Triệu chứng chủ đầu tư gặp 21/08: *"khi bên miyano đã khớp mã với yêu cầu
đặt ngoài nhưng anh không thấy chỗ điền giá cho dòng hàng đó, chỉ báo giá
được những hàng trong phần item"*.

Hệ quả THẬT nặng hơn "thiếu ô giá": trước task này `item_khop` chỉ bật
`da_xu_ly`, và `da_xu_ly` là thứ chốt `before_submit` đọc như "đã lo xong"
— nên đơn QUA ĐƯỢC chốt xác nhận trong khi mặt hàng khách gõ tay KHÔNG có
dòng nào trong đơn, không giá, không vào tổng tiền, không lên hoá đơn.

Mọi bài ở đây đi ĐƯỜNG CÔNG KHAI: dựng yêu cầu báo giá bằng
`bao_gia.tao_bao_gia` rồi `bg.save()` sau khi điền `item_khop` — đúng thao
tác nhân viên Miyano làm trên Desk. KHÔNG gọi thẳng hàm chuyển: nếu bài chỉ
xanh khi gọi hàm riêng thì đường công khai vẫn có thể hỏng mà không ai biết —
đúng lớp lỗi task này sinh ra để sửa.

Từ patch v1_44 Sales Order không còn dòng gõ tay: các hook khớp mã chỉ còn
chạy trên Quotation (`hooks.py::doc_events["Quotation"]`), nên mọi bài dựng
trên Quotation. Các chốt `before_submit` của Sales Order về dòng gõ tay đã
bỏ cùng hành vi; trên Quotation, chốt tương ứng là `bao_gia.chot_gui_khach`
lúc gửi khách.

GIÁ — spec 2026-10-09 (giá theo Price List, §4.4) đảo QĐ-G14: dòng sinh ra
khi khớp mã lấy giá từ Price List của khách, không từ hợp đồng khung, và
không gắn `blanket_order`. Fixture CỐ Ý vẫn dựng hợp đồng khung còn hiệu lực
(đã submit) với một giá KHÁC giá bảng giá (`GIA_HOP_DONG` ≠ `GIA_BANG_GIA`):
một bài khẳng định `GIA_BANG_GIA` vì thế đồng thời chứng minh giá hợp đồng
không còn rơi lên đơn.
"""

import frappe
from frappe.model.workflow import apply_workflow
from frappe.tests.utils import FrappeTestCase
from frappe.utils import flt

from miyano_portal import bang_gia_khach, bao_gia
from miyano_portal.miyano_portal.doctype.portal_de_xuat_mua.portal_de_xuat_mua import (
	nguon_gia_theo_ma_cho_khach,
)
from miyano_portal.portal_mua_le import ITEM_GIU_CHO
from miyano_portal.tests.fixtures_de_xuat import dung_fixture

COMPANY = "Miyano Việt Nam"
PRICE_LIST = "_TEST G13 PRICE"
PRICE_LIST_B = "_TEST G13 PRICE B"

# Giá trên HỢP ĐỒNG khung — không còn là giá của đơn; giữ để chứng minh điều đó.
GIA_HOP_DONG = 88000
GIA_HOP_DONG_B = 77000
# Giá trong Price List của khách — nguồn giá DUY NHẤT của cổng.
GIA_BANG_GIA = 54000
GIA_BANG_GIA_B = 43000

TEN_GO_TAY = "Găng tay nitrile size M (khách gõ tay)"


def _rid() -> str:
	return frappe.generate_hash(length=12)


def _don_du_lieu_cu():
	"""Xoá Quotation nháp, HUỶ rồi XOÁ Sales Order/Blanket Order của `_TEST DX%`.

	KHÔNG lọc `docstatus: 0`: bản ghi ĐÃ NỘP do method khác để lại vẫn "còn
	hiệu lực" ở method sau (`FrappeTestCase` rollback MỘT LẦN mỗi CLASS) và
	ăn mất `ordered_qty` của hợp đồng, khiến các bài hạn mức/giá PHỤ THUỘC
	THỨ TỰ CHẠY — đúng bẫy `test_dat_hang_gop.py::_don_phieu_cu` đã ghi.
	"""
	for ten in frappe.get_all(
		"Quotation", filters={"party_name": ["like", "_TEST DX%"], "docstatus": 0},
		pluck="name",
	):
		# Đợt nháp (báo giá theo đợt) bị hook `chan_xoa_dot` chặn xoá: bỏ hook.
		frappe.delete_doc(
			"Quotation", ten, force=True, ignore_permissions=True,
			ignore_on_trash=bool(frappe.db.get_value("Quotation", ten, "custom_phieu_goc")),
		)
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

		self.bo_a = self._bo(self.kh_a, [
			{"item_code": self.item_hd, "qty": 100, "rate": GIA_HOP_DONG},
			{"item_code": self.item_da_co, "qty": 100, "rate": GIA_HOP_DONG},
		])
		self.bo_b = self._bo(self.kh_b, [
			{"item_code": self.item_chi_b, "qty": 100, "rate": GIA_HOP_DONG_B},
		])

		# Hook `Blanket Order.on_submit` vừa dựng `Item Price` cho mọi dòng
		# `rate > 0` (giá HỢP ĐỒNG). Xoá đi rồi dựng bảng giá ĐÚNG Ý của bài:
		# `item_hd`/`item_da_co` có giá trong bảng của khách A, `item_chi_b`
		# chỉ có giá trong bảng của khách B, `item_ngoai` không có giá ở đâu.
		for ma in (self.item_hd, self.item_ngoai, self.item_da_co, self.item_chi_b):
			self._xoa_gia(ma)
		self._tao_gia(self.item_hd, self.price_list, GIA_BANG_GIA)
		self._tao_gia(self.item_da_co, self.price_list, GIA_BANG_GIA)
		self._tao_gia(self.item_chi_b, self.price_list_b, GIA_BANG_GIA_B)

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

	def _tao_gia(self, item_code, price_list, gia):
		return frappe.get_doc({
			"doctype": "Item Price", "item_code": item_code,
			"price_list": price_list, "selling": 1, "uom": "Cái",
			"price_list_rate": gia,
		}).insert(ignore_permissions=True)

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
		kq = bao_gia.tao_bao_gia(
			customer or self.kh_a, items=items or [],
			dat_ngoai=dat_ngoai or [], request_id=_rid(),
		)
		return frappe.get_doc("Quotation", kq["bao_gia"])

	def _go_tay(self, ten=TEN_GO_TAY, so_luong=5):
		return {"ten_hang": ten, "dvt": "Hộp", "so_luong": so_luong}

	def _khop(self, bg, item_code, idx=0):
		bg.custom_dat_ngoai[idx].item_khop = item_code
		bg.save(ignore_permissions=True)
		bg.reload()
		return bg

	def _dong(self, bg, item_code):
		for d in bg.items:
			if d.item_code == item_code:
				return d
		self.fail(
			f"Đơn {bg.name} KHÔNG có dòng hàng nào mang mã {item_code} — "
			f"khớp mã mới chỉ dán nhãn, chưa CHUYỂN thành hàng thật (QĐ-G13). "
			f"Đang có: {[d.item_code for d in bg.items]}"
		)

	# -- CA CHÍNH ----------------------------------------------------------

	def test_khop_ma_co_gia_sinh_dong_mang_gia_bang_gia(self):
		"""CA CHÍNH (QĐ-G13 + spec 2026-10-09 §4.4) — khớp một mã ĐÃ CÓ GIÁ
		trong Price List của khách: đơn phải có một DÒNG HÀNG THẬT, đúng số
		lượng khách gõ, mang ĐÚNG GIÁ BẢNG GIÁ và dấu "Bảng giá"."""
		# Đảo theo spec 2026-10-09 (giá theo Price List).
		self.assertEqual(
			nguon_gia_theo_ma_cho_khach(self.kh_a).get(self.item_hd), self.bo_a,
			"Tiền đề: mã này CŨNG nằm trong một hợp đồng còn hiệu lực với giá "
			"khác — nếu không, bài không chứng minh được giá hợp đồng đã thôi "
			"rơi lên đơn.",
		)
		self.assertEqual(
			bang_gia_khach.gia_bang_gia(self.kh_a, self.item_hd), float(GIA_BANG_GIA)
		)

		bg = self._dat(dat_ngoai=[self._go_tay(so_luong=5)])
		self.assertEqual(
			[d.item_code for d in bg.items], [ITEM_GIU_CHO],
			"đơn toàn hàng gõ tay khởi đầu chỉ có dòng giữ chỗ",
		)

		bg = self._khop(bg, self.item_hd)

		dong = self._dong(bg, self.item_hd)
		self.assertEqual(flt(dong.qty), 5.0)
		self.assertEqual(flt(dong.rate), float(GIA_BANG_GIA))
		self.assertEqual(flt(dong.price_list_rate), float(GIA_BANG_GIA))
		self.assertEqual(dong.custom_nguon_gia, "Bảng giá")
		self.assertFalse(dong.blanket_order, "không còn gắn hợp đồng khung lên dòng")
		# Dòng phải THẬT SỰ vào tiền của đơn — "không vào tổng tiền" là đúng
		# nửa sau của triệu chứng chủ đầu tư gặp.
		self.assertEqual(flt(dong.amount), 5.0 * GIA_BANG_GIA)
		self.assertGreaterEqual(flt(bg.total), 5.0 * GIA_BANG_GIA)

	def test_ma_khop_co_gia_bang_gia_thi_dong_nhan_gia_do(self):
		# Đảo theo spec 2026-10-09 (giá theo Price List).
		# §4.4: mã khớp đã có giá trong Price List
		# của khách thì dòng tự nhận giá, không bắt nhân viên điền tay — kể cả
		# khi mã đó KHÔNG thuộc hợp đồng khung nào (bài cũ khẳng định ngược
		# lại: mã ngoài hợp đồng không được nhặt giá bảng giá).
		self._tao_gia(self.item_ngoai, self.price_list, 123456)
		bg = self._dat(
			items=[{"item_code": self.item_hd, "qty": 1}],
			dat_ngoai=[self._go_tay(so_luong=3)],
		)
		bg = self._khop(bg, self.item_ngoai)
		dong = self._dong(bg, self.item_ngoai)
		self.assertEqual(flt(dong.qty), 3.0)
		self.assertEqual(flt(dong.rate), 123456.0)
		self.assertEqual(dong.custom_nguon_gia, "Bảng giá")
		self.assertEqual(flt(dong.amount), 3.0 * 123456)

	# Đảo theo spec 2026-10-09 (giá theo Price List).
	def test_ma_khop_chua_co_gia_la_dong_bao_gia(self):
		"""Mã chưa có giá trong Price List của khách → `rate = 0`, dấu "Báo
		giá", chờ Miyano báo giá. `price_list_rate` cũng phải là 0 TƯỜNG MINH:
		`taxes_and_totals.calculate_item_values` ÂM THẦM thay `rate = 0` bằng
		`price_list_rate` (0 là falsy) nếu ERPNext tự điền được cột đó."""
		# Đơn TRỘN: có một dòng "Bảng giá" đứng cạnh, đơn mang bảng giá của
		# khách — đúng hình dạng làm bẫy `price_list_rate` sống dậy.
		bg = self._dat(
			items=[{"item_code": self.item_hd, "qty": 1}],
			dat_ngoai=[self._go_tay(so_luong=3)],
		)
		self.assertEqual(bg.selling_price_list, self.price_list)
		bg = self._khop(bg, self.item_ngoai)
		dong = self._dong(bg, self.item_ngoai)
		self.assertEqual(flt(dong.qty), 3.0)
		self.assertEqual(flt(dong.rate), 0.0)
		self.assertEqual(flt(dong.price_list_rate), 0.0)
		self.assertEqual(flt(dong.amount), 0.0)
		self.assertEqual(dong.custom_nguon_gia, "Báo giá")
		self.assertFalse(dong.blanket_order)

	# -- BẪY 1: bất biến ----------------------------------------------------

	def test_luu_ba_lan_van_dung_mot_dong(self):
		"""`validate` chạy mỗi lần lưu — khớp mã rồi lưu ba lần KHÔNG được
		đẻ ba dòng hàng (bẫy 1)."""
		bg = self._dat(dat_ngoai=[self._go_tay()])
		bg = self._khop(bg, self.item_hd)
		so_dong_lan_dau = len(bg.items)
		for _ in range(2):
			bg.save(ignore_permissions=True)
			bg.reload()
		self.assertEqual(len(bg.items), so_dong_lan_dau)
		self.assertEqual(
			len([d for d in bg.items if d.item_code == self.item_hd]), 1
		)
		self.assertEqual(flt(self._dong(bg, self.item_hd).qty), 5.0)

	# -- BẪY 2: gộp vào dòng sẵn có ----------------------------------------

	def test_ma_khop_trung_hang_da_co_thi_cong_don(self):
		"""Hai dòng cùng `item_code` trên một chứng từ là mồi cho lệch hạn
		mức và lệch hoá đơn — phải CỘNG DỒN vào dòng sẵn có."""
		bg = self._dat(
			items=[{"item_code": self.item_da_co, "qty": 2}],
			dat_ngoai=[self._go_tay(so_luong=4)],
		)
		so_dong_truoc = len(bg.items)
		bg = self._khop(bg, self.item_da_co)
		self.assertEqual(
			len(bg.items), so_dong_truoc,
			"gộp số lượng, KHÔNG thêm dòng thứ hai cùng mã",
		)
		self.assertEqual(flt(self._dong(bg, self.item_da_co).qty), 6.0)

	def test_hai_dong_go_tay_cung_mot_ma_cung_gop_lam_mot(self):
		"""Hai dòng gõ tay khác tên nhưng Miyano khớp về CÙNG một mã: vẫn
		đúng MỘT dòng hàng, số lượng cộng dồn."""
		bg = self._dat(dat_ngoai=[
			self._go_tay("Găng tay hộp lớn", so_luong=2),
			self._go_tay("Găng tay hộp nhỏ", so_luong=3),
		])
		for dong in bg.custom_dat_ngoai:
			dong.item_khop = self.item_hd
		bg.save(ignore_permissions=True)
		bg.reload()
		self.assertEqual(
			len([d for d in bg.items if d.item_code == self.item_hd]), 1
		)
		self.assertEqual(flt(self._dong(bg, self.item_hd).qty), 5.0)

	# -- QĐ-G15: dòng gõ tay là BẰNG CHỨNG ----------------------------------

	def test_dong_go_tay_con_nguyen_sau_khi_chuyen(self):
		"""Không xoá, không sửa `ten_hang` khách đã gõ — đó là truy vết chủ
		đầu tư yêu cầu từ đầu ("ghi tên ngày giờ lý do yêu cầu")."""
		bg = self._dat(dat_ngoai=[self._go_tay()])
		bg = self._khop(bg, self.item_hd)
		self.assertEqual(len(bg.custom_dat_ngoai), 1)
		dong_go_tay = bg.custom_dat_ngoai[0]
		self.assertEqual(dong_go_tay.ten_hang, TEN_GO_TAY)
		self.assertEqual(flt(dong_go_tay.so_luong), 5.0)
		self.assertTrue(dong_go_tay.da_chuyen)
		# Đường nối hai chiều: biết dòng bằng chứng nào ứng với dòng tiền nào.
		self.assertEqual(dong_go_tay.dong_hang, self._dong(bg, self.item_hd).name)

	# -- BẪY 3: gỡ dòng giữ chỗ --------------------------------------------

	def test_khop_het_thi_dong_giu_cho_bien_mat(self):
		"""Yêu cầu TOÀN hàng gõ tay: sau khi khớp hết, dòng giữ chỗ kỹ thuật
		phải BIẾN MẤT — `bao_gia.chot_gui_khach` không cho gửi khách một báo
		giá còn dòng đó."""
		bg = self._dat(dat_ngoai=[self._go_tay()])
		self.assertIn(ITEM_GIU_CHO, [d.item_code for d in bg.items])
		bg = self._khop(bg, self.item_hd)
		self.assertNotIn(
			ITEM_GIU_CHO, [d.item_code for d in bg.items],
			"dòng giữ chỗ phải được gỡ khi đã có hàng thật (bẫy 3)",
		)
		self.assertEqual(flt(self._dong(bg, self.item_hd).qty), 5.0)

	def test_xoa_dong_hang_da_chuyen_thi_khong_gui_khach_duoc(self):
		"""Critical-3 trên Quotation: nhân viên xoá dòng hàng mà phép khớp mã
		sinh ra thì dòng gõ tay vẫn `da_xu_ly = 1`, nhưng mặt hàng khách yêu
		cầu không còn trên báo giá — `bao_gia.chot_gui_khach` phải giữ lại.
		Thêm lại đúng dòng đó thì gửi được."""
		bg = self._dat(
			items=[{"item_code": self.item_da_co, "qty": 2}],
			dat_ngoai=[self._go_tay()],
		)
		bg = self._khop(bg, self.item_hd)
		self.assertTrue(bg.custom_dat_ngoai[0].da_xu_ly)

		bg.set("items", [d for d in bg.items if d.item_code != self.item_hd])
		bg.save(ignore_permissions=True)
		bg.reload()
		self.assertTrue(bg.custom_dat_ngoai[0].da_xu_ly, "tiền đề: cờ vẫn nói đã xử lý")
		with self.assertRaises(frappe.ValidationError) as ctx:
			apply_workflow(bg, bao_gia.HD_GUI_KHACH)
		self.assertIn("đã bị xoá hoặc đổi mã", str(ctx.exception))
		self.assertIn(self.item_hd, str(ctx.exception))
		self.assertEqual(
			frappe.db.get_value("Quotation", bg.name, "workflow_state"), bao_gia.TT_CHO_MIYANO
		)

	# -- QĐ-G16: `da_xu_ly` phải nói thật -----------------------------------

	def test_da_xu_ly_chi_bat_sau_khi_da_chuyen(self):
		"""`da_xu_ly` hiện nghĩa "đã gắn mã" nhưng chốt `before_submit` đọc
		nó là "đã lo xong" — nó đang NÓI DỐI. Sau task này nó bật khi và chỉ
		khi dòng đã thành hàng thật."""
		bg = self._dat(dat_ngoai=[self._go_tay()])
		self.assertFalse(bg.custom_dat_ngoai[0].da_xu_ly)
		bg = self._khop(bg, self.item_hd)
		dong = bg.custom_dat_ngoai[0]
		self.assertTrue(dong.da_chuyen, "phải CHUYỂN thật")
		self.assertTrue(dong.da_xu_ly)
		self.assertTrue(
			frappe.db.get_value(
				"Sales Order Dat Ngoai Item", dong.name, "da_xu_ly"
			),
			"giá trị phải xuống DB, không chỉ nằm trong bộ nhớ",
		)

	# -- CRITICAL-1 (review 22/08): phần đã gộp phải HOÀN TÁC được ----------

	def test_xoa_dong_go_tay_da_chuyen_thi_tru_lai_DUNG_phan_da_gop(self):
		"""Nền của cả Critical-1. Dòng hàng dùng CHUNG: 2 đơn vị khách tự đặt
		+ 4 đơn vị tới từ dòng gõ tay. Xoá dòng gõ tay khỏi đơn nháp thì phải
		trừ lại ĐÚNG 4, còn nguyên 2 — không trừ thiếu (để lại số lượng ma),
		cũng không gỡ cả dòng (ăn mất phần khách đặt trực tiếp)."""
		bg = self._dat(
			items=[{"item_code": self.item_da_co, "qty": 2}],
			dat_ngoai=[self._go_tay(so_luong=4)],
		)
		bg = self._khop(bg, self.item_da_co)
		self.assertEqual(flt(self._dong(bg, self.item_da_co).qty), 6.0)

		bg.custom_dat_ngoai = []
		bg.save(ignore_permissions=True)
		bg.reload()
		self.assertEqual(
			flt(self._dong(bg, self.item_da_co).qty), 2.0,
			"phải trừ lại ĐÚNG phần dòng gõ tay đã bơm vào, không hơn không kém",
		)
		self.assertEqual(flt(bg.total), 2.0 * GIA_BANG_GIA)

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
		bg = self._dat(dat_ngoai=[self._go_tay(so_luong=5)])
		bg = self._khop(bg, self.item_hd)
		tien_truoc = flt(bg.total)
		self.assertEqual(tien_truoc, 5.0 * GIA_BANG_GIA)

		bg.custom_dat_ngoai = []
		bg.append("custom_dat_ngoai", {
			"ten_hang": TEN_GO_TAY, "dvt": "Hộp", "so_luong": 5,
			"item_khop": self.item_hd,
		})
		bg.save(ignore_permissions=True)
		bg.reload()

		self.assertEqual(
			len([d for d in bg.items if d.item_code == self.item_hd]), 1
		)
		self.assertEqual(flt(self._dong(bg, self.item_hd).qty), 5.0)
		self.assertEqual(flt(bg.total), tien_truoc)

	def _dong_chung_hai_chu(self):
		"""Một dòng hàng có BA chủ: 2 đơn vị khách đặt trực tiếp, 3 của dòng
		gõ tay A, 4 của dòng gõ tay B → 9."""
		bg = self._dat(
			items=[{"item_code": self.item_da_co, "qty": 2}],
			dat_ngoai=[self._go_tay("Dòng A", 3), self._go_tay("Dòng B", 4)],
		)
		for d in bg.custom_dat_ngoai:
			d.item_khop = self.item_da_co
		bg.save(ignore_permissions=True)
		bg.reload()
		self.assertEqual(flt(self._dong(bg, self.item_da_co).qty), 9.0)
		return bg

	def test_dong_hang_dung_CHUNG_xoa_mot_chu_thi_chu_kia_con_nguyen(self):
		"""Ca chính mà cột `so_luong_da_gop` sinh ra để phục vụ: một dòng
		hàng nhiều chủ. Xoá dòng gõ tay B thì chỉ được trừ 4 — phần của A và
		phần khách đặt trực tiếp phải còn nguyên.

		Cũng là bài canh TÍNH TẤT ĐỊNH: phép hoàn tác gom theo DÒNG HÀNG chứ
		không xử lý từng dòng gõ tay một, nên thứ tự lặp không quyết định
		được kết quả."""
		bg = self._dong_chung_hai_chu()
		bg.custom_dat_ngoai = [
			d for d in bg.custom_dat_ngoai if d.ten_hang != "Dòng B"
		]
		bg.save(ignore_permissions=True)
		bg.reload()
		self.assertEqual(
			flt(self._dong(bg, self.item_da_co).qty), 5.0,
			"2 khách đặt trực tiếp + 3 của dòng A còn lại",
		)
		self.assertEqual(len(bg.custom_dat_ngoai), 1)
		self.assertEqual(flt(bg.custom_dat_ngoai[0].so_luong_da_gop), 3.0)

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
		bg = self._dong_chung_hai_chu()
		bg.items[0].qty = 4
		bg.save(ignore_permissions=True)
		bg.reload()
		self.assertEqual(flt(self._dong(bg, self.item_da_co).qty), 4.0)
		theo_ten = {d.ten_hang: d for d in bg.custom_dat_ngoai}
		self.assertEqual(flt(theo_ten["Dòng B"].so_luong_da_gop), 0.0)
		self.assertEqual(flt(theo_ten["Dòng A"].so_luong_da_gop), 2.0)
		# Bằng chứng khoa đã xin bao nhiêu thì KHÔNG đổi theo (QĐ-G15).
		self.assertEqual(flt(theo_ten["Dòng A"].so_luong), 3.0)
		self.assertEqual(flt(theo_ten["Dòng B"].so_luong), 4.0)

		bg.custom_dat_ngoai = [
			d for d in bg.custom_dat_ngoai if d.ten_hang != "Dòng B"
		]
		bg.save(ignore_permissions=True)
		bg.reload()
		dong = self._dong(bg, self.item_da_co)
		self.assertEqual(
			flt(dong.qty), 4.0,
			"2 đặt thẳng + 2 của A — không chủ nào bị bốc hơi, và phần B "
			"đã được hấp thụ từ lúc hạ tay nên không trừ thêm lần nữa",
		)
		# Và đường nối bằng chứng ↔ tiền của A phải còn nguyên.
		self.assertEqual(bg.custom_dat_ngoai[0].dong_hang, dong.name)

	def test_xoa_sach_dong_go_tay_tren_don_toan_hang_go_tay_bao_cau_ro(self):
		"""Ca biên còn lại của phép hoàn tác: đơn TOÀN hàng gõ tay, xoá SẠCH
		dòng gõ tay thì `items` rỗng mà cũng không còn nhu cầu nào để dựng
		dòng giữ chỗ. ERPNext sẽ ném `MandatoryError: items` — một câu không
		nói cho nhân viên biết chuyện gì vừa xảy ra. Phải nói thẳng ra."""
		bg = self._dat(dat_ngoai=[self._go_tay(so_luong=5)])
		bg = self._khop(bg, self.item_hd)
		bg.custom_dat_ngoai = []
		with self.assertRaises(frappe.ValidationError) as ctx:
			bg.save(ignore_permissions=True)
		self.assertIn("không còn dòng hàng nào", str(ctx.exception))
		self.assertIn("huỷ hẳn đơn nháp này", str(ctx.exception))

	def test_xoa_het_dong_go_tay_tren_don_TOAN_hang_go_tay(self):
		"""Ca biên của phép hoàn tác: đơn TOÀN hàng gõ tay, khớp mã xong thì
		dòng giữ chỗ đã bị gỡ (bẫy 3) nên `items` chỉ còn đúng dòng vừa sinh.
		Xoá dòng gõ tay đi là `items` RỖNG — mà ERPNext không lưu nổi một
		chứng từ bán `items` rỗng (`grand_total` là `None`). Đơn phải quay về
		đúng hình dạng §3.4 của nó, không phải nổ một câu của framework."""
		bg = self._dat(dat_ngoai=[self._go_tay(so_luong=5), self._go_tay("Dòng hai", 2)])
		bg = self._khop(bg, self.item_hd)
		self.assertNotIn(ITEM_GIU_CHO, [d.item_code for d in bg.items])

		bg.custom_dat_ngoai[0].item_khop = None
		# Xoá dòng ĐÃ chuyển, giữ lại dòng chưa khớp → đơn lại "toàn hàng
		# chưa có mã", đúng tiền đề dòng giữ chỗ sinh ra để phục vụ.
		bg.custom_dat_ngoai = [d for d in bg.custom_dat_ngoai if not d.da_chuyen]
		bg.save(ignore_permissions=True)
		bg.reload()
		self.assertEqual(
			[d.item_code for d in bg.items], [ITEM_GIU_CHO],
			"đơn không còn hàng thật thì phải có lại đúng MỘT dòng giữ chỗ",
		)
		self.assertEqual(len(bg.custom_dat_ngoai), 1)

	def test_nhan_ban_don_khong_nhan_doi_so_luong(self):
		"""Nút Duplicate trên Desk (`frappe.copy_doc`) chép CẢ `items` LẪN
		dòng gõ tay `da_chuyen = 1`. Bản sao đi qua `insert()`, ở đó KHÔNG có
		`doc_before_save` để đối chiếu — nên phép chuyển coi dòng gõ tay là
		chưa chuyển và cộng số lượng vào chính dòng hàng vừa được chép sang:
		5 thành 10, dòng bằng chứng vẫn ghi 5."""
		bg = self._dat(dat_ngoai=[self._go_tay(so_luong=5)])
		bg = self._khop(bg, self.item_hd)

		ban_sao = frappe.copy_doc(bg)
		ban_sao.custom_request_id = _rid()
		ban_sao.insert(ignore_permissions=True)

		self.assertEqual(
			len([d for d in ban_sao.items if d.item_code == self.item_hd]), 1
		)
		self.assertEqual(flt(self._dong(ban_sao, self.item_hd).qty), 5.0)
		self.assertEqual(flt(ban_sao.total), flt(bg.total))
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
		bg = self._dat(dat_ngoai=[self._go_tay(so_luong=5)])
		bg = self._khop(bg, self.item_hd)

		ban_sao = frappe.copy_doc(bg)
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
	# RỒI mới gọi `submit()`, và `before_validate` vẫn chạy cho `_action in
	# ("save", "submit")`. Báo giá của cổng chỉ Submit qua `bao_gia.dong_y`
	# (đọc lại từ DB), nhưng báo giá NỘI BỘ Submit thẳng được trên Desk — nên
	# bấm Submit trên một báo giá nháp ĐANG DỞ là MỘT lần lưu duy nhất, đi qua
	# hook với `docstatus == 1`. Bất biến phải đứng vững ở đường này.

	def _noi_bo(self, bg):
		frappe.db.set_value(
			"Quotation", bg.name, "custom_nguon_don", "Nội bộ", update_modified=False
		)
		bg.reload()
		return bg

	def test_submit_mot_nhip_van_HOAN_TAC_dong_go_tay_vua_xoa(self):
		"""Xoá một dòng gõ tay rồi bấm thẳng Submit, không lưu trước: số lượng
		của dòng đã xoá không được đi theo báo giá vào tiền."""
		bg = self._noi_bo(self._dong_chung_hai_chu())
		bg.custom_dat_ngoai = [
			d for d in bg.custom_dat_ngoai if d.ten_hang != "Dòng B"
		]
		bg.submit()
		bg.reload()
		self.assertEqual(bg.docstatus, 1)
		self.assertEqual(
			flt(self._dong(bg, self.item_da_co).qty), 5.0,
			"2 khách đặt trực tiếp + 3 của dòng A — phần của dòng B đã xoá "
			"không được đi theo vào tiền",
		)

	def test_submit_mot_nhip_van_CHAN_sua_dong_da_chuyen(self):
		"""Bẫy 6 phải đứng vững ở đường một nhịp: sửa `so_luong` trên dòng đã
		chuyển rồi bấm thẳng Submit."""
		bg = self._noi_bo(self._khop(self._dat(dat_ngoai=[self._go_tay(so_luong=5)]), self.item_hd))
		bg.custom_dat_ngoai[0].so_luong = 9
		with self.assertRaises(frappe.ValidationError) as ctx:
			bg.submit()
		self.assertIn("đã chuyển thành dòng hàng", str(ctx.exception))
		bg.reload()
		self.assertEqual(bg.docstatus, 0)
		self.assertEqual(flt(bg.custom_dat_ngoai[0].so_luong), 5.0)

	# -- IMPORTANT-2 / Ruling P39: sổ sách không được trôi khỏi `qty` -------

	def test_ha_tay_so_luong_thi_HA_LUON_so_sach_da_gop(self):
		"""Ruling P39 — `qty` được phép nhỏ hơn tổng khoa yêu cầu (giao một
		phần, thương lượng giảm: nghiệp vụ thật, hệ thống không phủ quyết).
		Nhưng SỔ SÁCH phải theo: với mỗi dòng hàng, tổng `so_luong_da_gop`
		của các dòng gõ tay trỏ vào nó ≤ `qty` của dòng đó.

		Phần giảm ăn vào phần ĐÃ GỘP trước, phần khách đặt thẳng giữ nguyên.

		`so_luong` của dòng gõ tay KHÔNG đổi — đó là bằng chứng khoa đã xin
		bao nhiêu, nó không chạy theo quyết định giao hàng."""
		bg = self._dat(
			items=[{"item_code": self.item_da_co, "qty": 2}],
			dat_ngoai=[self._go_tay(so_luong=5)],
		)
		bg = self._khop(bg, self.item_da_co)
		self.assertEqual(flt(self._dong(bg, self.item_da_co).qty), 7.0)
		self.assertEqual(flt(bg.custom_dat_ngoai[0].so_luong_da_gop), 5.0)

		bg.items[0].qty = 4
		bg.save(ignore_permissions=True)
		bg.reload()
		self.assertEqual(
			flt(bg.custom_dat_ngoai[0].so_luong_da_gop), 2.0,
			"giảm 3 thì phần đã gộp 5 phải xuống 2 — 2 hộp khách đặt thẳng giữ nguyên",
		)
		self.assertEqual(
			flt(bg.custom_dat_ngoai[0].so_luong), 5.0,
			"bằng chứng khoa xin 5 KHÔNG được sửa theo (QĐ-G15)",
		)

	def test_ha_tay_roi_xoa_dong_go_tay_KHONG_an_mat_phan_khach_dat_thang(self):
		"""Vế tiền của bài trên, và là hố Important-2 đo được trên Desk
		thường: đơn còn một dòng hàng KHÁC nên `_dam_bao_con_dong_hang`
		không ném gì cả — 2 hộp khách đặt thẳng biến mất IM LẶNG."""
		bg = self._dat(
			items=[
				{"item_code": self.item_da_co, "qty": 2},
				{"item_code": self.item_hd, "qty": 1},
			],
			dat_ngoai=[self._go_tay(so_luong=5)],
		)
		bg = self._khop(bg, self.item_da_co)
		self.assertEqual(flt(self._dong(bg, self.item_da_co).qty), 7.0)

		bg.items[0].qty = 4
		bg.save(ignore_permissions=True)
		bg.reload()

		bg.custom_dat_ngoai = []
		bg.save(ignore_permissions=True)
		bg.reload()
		dong = self._dong(bg, self.item_da_co)
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
		bg = self._dong_chung_hai_chu()
		bg.items[0].qty = 4
		bg.save(ignore_permissions=True)
		bg.reload()
		theo_ten = {d.ten_hang: d for d in bg.custom_dat_ngoai}
		self.assertEqual(
			flt(theo_ten["Dòng B"].so_luong_da_gop), 0.0,
			"tiền đề: P39 đã hạ sổ sách của B về 0 một cách HỢP LỆ",
		)

		ban_sao = frappe.copy_doc(bg)
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
		bg = self._dong_chung_hai_chu()
		ban_sao = frappe.copy_doc(bg)
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
		bg = self._dat(
			items=[{"item_code": self.item_hd, "qty": 1}],
			dat_ngoai=[self._go_tay("Lẻ A", 0.7), self._go_tay("Lẻ B", 0.1)],
		)
		for d in bg.custom_dat_ngoai:
			d.item_khop = self.item_da_co
		bg.save(ignore_permissions=True)
		bg.reload()
		self.assertEqual(flt(self._dong(bg, self.item_da_co).qty, 3), 0.8)

		bg.custom_dat_ngoai = []
		bg.save(ignore_permissions=True)
		bg.reload()
		self.assertNotIn(
			self.item_da_co, [d.item_code for d in bg.items],
			"trừ hết thì phải GỠ dòng, không để lại một dòng số lượng ~0",
		)

	# -- CRITICAL-2 (review 22/08) + spec 2026-10-09 §4.4: LUẬT GỘP ----------
	#
	# Gộp vào dòng sẵn có chỉ ĐIỀN VÀO CHỖ TRỐNG: dòng `rate = 0` nhận giá
	# bảng giá và dấu "Bảng giá"; dòng đã có giá LUÔN giữ nguyên giá, còn dấu
	# thì "Bảng giá" chỉ khi giá đó đúng bằng giá bảng (ruling R14).

	def test_gop_vao_dong_dang_cho_bao_gia_thi_DAN_gia_bang_gia(self):
		"""Vòng lặp nghiệp vụ thật, dựng lại NGUYÊN VẸN — không sửa tay dòng
		đơn ở bất kỳ bước nào:

		  1. khoa đặt một mặt hàng lúc nó CHƯA có giá → dòng "Báo giá",
		     `rate = 0`, chờ Miyano báo giá;
		  2. mặt hàng đó CÓ GIÁ trong Price List của khách (một đơn khác được
		     khách đồng ý, hoặc nhân viên nhập bảng giá);
		  3. Miyano khớp một dòng gõ tay về đúng mã đó.

		Đường gộp `return` sớm sẽ VỨT giá vừa tra, nên TOÀN BỘ số lượng (cũ
		lẫn mới) đi tiếp với tiền bằng 0 — đúng nửa còn lại của con bug
		QĐ-G13 sinh ra để dẹp, đi vào bằng cửa gộp."""
		# Đảo theo spec 2026-10-09 (giá theo Price List).
		bg = self._dat(
			items=[{"item_code": self.item_ngoai, "qty": 2}],
			dat_ngoai=[self._go_tay(so_luong=4)],
		)
		dong = self._dong(bg, self.item_ngoai)
		self.assertEqual(flt(dong.rate), 0.0, "tiền đề: dòng đang chờ báo giá")
		self.assertEqual(dong.custom_nguon_gia, "Báo giá")

		# Giá xuất hiện SAU khi đơn đã lập.
		self._tao_gia(self.item_ngoai, self.price_list, GIA_BANG_GIA)

		bg.reload()
		bg = self._khop(bg, self.item_ngoai)
		dong = self._dong(bg, self.item_ngoai)
		self.assertEqual(flt(dong.qty), 6.0)
		self.assertEqual(
			flt(dong.rate), float(GIA_BANG_GIA),
			"cả cụm số lượng phải mang giá bảng giá, không đi tiếp với 0 đồng",
		)
		self.assertEqual(flt(dong.price_list_rate), float(GIA_BANG_GIA))
		self.assertEqual(dong.custom_nguon_gia, "Bảng giá")
		self.assertFalse(dong.blanket_order)
		self.assertEqual(flt(bg.total), 6.0 * GIA_BANG_GIA)

	def test_gop_KHONG_de_len_gia_nhan_vien_dang_bao(self):
		"""Vế răng của bài trên. Dòng "Báo giá" đã mang giá nhân viên vừa gõ
		là giá ĐANG ĐÀM PHÁN với khách; giữa chừng mã đó có giá trong bảng
		(đơn khác được đồng ý). Phép gộp không được đè giá bảng giá lên, cũng
		không được đổi dấu — nếu đổi thành "Bảng giá", lúc khách đồng ý giá
		50.000 này sẽ không được ghi vào Price List và chốt 3 thôi canh nó."""
		bg = self._dat(
			items=[{"item_code": self.item_ngoai, "qty": 2}],
			dat_ngoai=[self._go_tay(so_luong=4)],
		)
		self._dong(bg, self.item_ngoai).rate = 50000
		bg.save(ignore_permissions=True)
		bg.reload()
		dong = self._dong(bg, self.item_ngoai)
		self.assertEqual(flt(dong.rate), 50000.0, "tiền đề: nhân viên đã gõ giá")
		self.assertEqual(dong.custom_nguon_gia, "Báo giá")

		self._tao_gia(self.item_ngoai, self.price_list, GIA_BANG_GIA)

		bg = self._khop(bg, self.item_ngoai)
		dong = self._dong(bg, self.item_ngoai)
		self.assertEqual(flt(dong.qty), 6.0)
		self.assertEqual(flt(dong.rate), 50000.0, "giá đang báo phải giữ nguyên")
		self.assertEqual(dong.custom_nguon_gia, "Báo giá", "dấu cũng giữ nguyên")
		self.assertEqual(flt(bg.total), 6.0 * 50000)

	# Đảo theo spec 2026-10-09 (giá theo Price List).
	def test_gop_vao_dong_bang_gia_da_bi_sua_gia_thi_thanh_bao_gia(self):
		"""Ruling R14. Dòng mang dấu "Bảng giá" nhưng nhân viên đã sửa giá tay
		trên Desk (50.000 ≠ giá bảng 54.000): phép gộp vẫn KHÔNG đè con số đó,
		nhưng đóng lại dấu "Báo giá" — một giá nhân viên gõ là một báo giá: nó
		phải được ghi vào Price List khi khách đồng ý và được chốt
		`before_submit` canh. Bài cũ khẳng định dấu vẫn là "Bảng giá"."""
		bg = self._dat(
			items=[{"item_code": self.item_da_co, "qty": 2}],
			dat_ngoai=[self._go_tay(so_luong=4)],
		)
		bg.items[0].rate = 50000
		bg.save(ignore_permissions=True)
		bg.reload()
		self.assertEqual(flt(bg.items[0].rate), 50000.0, "tiền đề: giá đã sửa tay")
		self.assertEqual(bg.items[0].custom_nguon_gia, "Bảng giá")
		# R16 dựa vào đúng điều này: sửa `rate` trên dòng đã lưu KHÔNG kéo
		# `price_list_rate` theo — cột đó vẫn nhớ giá bảng lúc lập đơn.
		self.assertEqual(flt(bg.items[0].price_list_rate), float(GIA_BANG_GIA))

		bg = self._khop(bg, self.item_da_co)
		dong = self._dong(bg, self.item_da_co)
		self.assertEqual(flt(dong.qty), 6.0)
		self.assertEqual(flt(dong.rate), 50000.0, "giá nhân viên gõ phải giữ nguyên")
		self.assertEqual(dong.custom_nguon_gia, "Báo giá")

	# -- Ruling R16: dòng "Bảng giá" KHÔNG ai sửa mà giá bảng đã đổi ----------

	def _don_bang_gia_roi_bang_doi(self, gia_moi):
		"""Đơn có dòng "Bảng giá" ở 54.000 (`rate == price_list_rate`, không ai
		sửa) + một dòng gõ tay; rồi giá bảng đổi thành `gia_moi` (`None` = mã
		bị rút khỏi bảng giá)."""
		bg = self._dat(
			items=[{"item_code": self.item_da_co, "qty": 2}],
			dat_ngoai=[self._go_tay(so_luong=4)],
		)
		dong = self._dong(bg, self.item_da_co)
		self.assertEqual(dong.custom_nguon_gia, "Bảng giá")
		self.assertEqual(flt(dong.rate), float(GIA_BANG_GIA))
		self.assertEqual(flt(dong.price_list_rate), float(GIA_BANG_GIA))
		if gia_moi is None:
			self._xoa_gia(self.item_da_co)
		else:
			bang_gia_khach.ghi_gia_vao_bang(
				self.price_list, self.kh_a, self.item_da_co, gia_moi
			)
		self.assertEqual(
			bang_gia_khach.gia_bang_gia(self.kh_a, self.item_da_co), gia_moi
		)
		return bg

	def test_gop_vao_dong_bang_gia_khi_gia_bang_da_doi_thi_lay_gia_moi(self):
		"""R16 — giá bảng trôi từ 54.000 lên 60.000 sau khi lập đơn. Gộp phải
		làm mới dòng theo giá hôm nay và GIỮ dấu "Bảng giá"; đóng "Báo giá" ở
		54.000 thì lúc khách đồng ý, giá cũ bị ghi đè lên giá bảng hiện hành.

		Đơn sinh từ báo giá ghi mọi dòng vào Price List lúc khách đồng ý, nên
		bài canh GIÁ TRỊ trong bảng sau khi đồng ý, không canh việc có ghi."""
		bg = self._don_bang_gia_roi_bang_doi(60000.0)
		bg = self._khop(bg, self.item_da_co)
		dong = self._dong(bg, self.item_da_co)
		self.assertEqual(flt(dong.qty), 6.0)
		self.assertEqual(flt(dong.rate), 60000.0)
		self.assertEqual(flt(dong.price_list_rate), 60000.0)
		self.assertEqual(dong.custom_nguon_gia, "Bảng giá")
		self.assertEqual(flt(bg.total), 6.0 * 60000)

		def gia_trong_bang():
			return frappe.get_all(
				"Item Price", filters={"item_code": self.item_da_co, "selling": 1},
				fields=["name", "price_list", "price_list_rate"],
				order_by="name asc",
			)

		truoc = gia_trong_bang()
		bg = apply_workflow(bg, bao_gia.HD_GUI_KHACH)
		bao_gia.dong_y(bg.name)
		self.assertEqual(gia_trong_bang(), truoc, "khách đồng ý không được đổi giá trong bảng")
		self.assertEqual(
			bang_gia_khach.gia_bang_gia(self.kh_a, self.item_da_co), 60000.0
		)

	def test_gop_vao_dong_bang_gia_khi_ma_bi_rut_gia_thi_cho_bao_gia(self):
		"""R16 — mã bị rút khỏi bảng giá sau khi lập đơn: dòng không còn là
		dòng giá bảng. Dấu "Báo giá", `rate = 0` (một giá đã rút không được
		ghi ngược vào bảng lúc khách đồng ý), và chốt 2 giữ đơn lại cho tới
		khi nhân viên gõ giá."""
		bg = self._don_bang_gia_roi_bang_doi(None)
		bg = self._khop(bg, self.item_da_co)
		dong = self._dong(bg, self.item_da_co)
		self.assertEqual(flt(dong.qty), 6.0)
		self.assertEqual(flt(dong.rate), 0.0)
		self.assertEqual(flt(dong.price_list_rate), 0.0)
		self.assertEqual(dong.custom_nguon_gia, "Báo giá")

		with self.assertRaises(frappe.ValidationError) as ctx:
			apply_workflow(bg, bao_gia.HD_GUI_KHACH)
		self.assertIn("chưa có đơn giá", str(ctx.exception))
		bg.reload()
		self._dong(bg, self.item_da_co).rate = 58000
		bg.save(ignore_permissions=True)
		bg = apply_workflow(bg, bao_gia.HD_GUI_KHACH)
		self.assertEqual(bg.workflow_state, bao_gia.TT_CHO_KHACH)

	def _bo_dau(self, bg, item_code, **them):
		"""Hạ dòng về hình dạng dòng CHƯA có dấu — dòng nhân viên thêm tay trên
		Desk, hoặc đơn lập trước spec 2026-10-09."""
		frappe.db.set_value(
			"Quotation Item", self._dong(bg, item_code).name,
			{"custom_nguon_gia": "", **them}, update_modified=False,
		)
		bg.reload()
		return bg

	def test_gop_vao_dong_chua_dau_gia_khac_gia_bang_thi_la_bao_gia(self):
		"""Ruling R14 — dòng chưa có dấu mang 50.000, giá bảng 54.000: gộp giữ
		50.000 và đóng dấu "Báo giá", KHÔNG "Bảng giá" (nếu không, lần khách
		sửa số lượng kế tiếp sẽ lặng lẽ thay giá nhân viên bằng giá bảng)."""
		bg = self._dat(
			items=[{"item_code": self.item_da_co, "qty": 2}],
			dat_ngoai=[self._go_tay(so_luong=4)],
		)
		bg.items[0].rate = 50000
		bg.save(ignore_permissions=True)
		bg = self._bo_dau(bg, self.item_da_co)
		self.assertFalse(self._dong(bg, self.item_da_co).custom_nguon_gia)

		bg = self._khop(bg, self.item_da_co)
		dong = self._dong(bg, self.item_da_co)
		self.assertEqual(flt(dong.rate), 50000.0)
		self.assertEqual(dong.custom_nguon_gia, "Báo giá")

	def test_gop_vao_dong_chua_dau_gia_bang_gia_bang_thi_la_bang_gia(self):
		"""Vế còn lại của R14: dòng chưa có dấu mà `rate` ĐÚNG BẰNG giá bảng
		thì đó là giá bảng — dấu "Bảng giá"."""
		bg = self._dat(
			items=[{"item_code": self.item_da_co, "qty": 2}],
			dat_ngoai=[self._go_tay(so_luong=4)],
		)
		bg = self._bo_dau(bg, self.item_da_co)
		self.assertEqual(flt(self._dong(bg, self.item_da_co).rate), float(GIA_BANG_GIA))

		bg = self._khop(bg, self.item_da_co)
		dong = self._dong(bg, self.item_da_co)
		self.assertEqual(flt(dong.rate), float(GIA_BANG_GIA))
		self.assertEqual(dong.custom_nguon_gia, "Bảng giá")

	def test_gop_vao_dong_chua_dau_co_gia_ma_ma_chua_co_gia_bang_la_bao_gia(self):
		"""R14 — dòng chưa có dấu mang giá nhân viên gõ, mã KHÔNG có giá bảng."""
		bg = self._dat(
			items=[{"item_code": self.item_ngoai, "qty": 2}],
			dat_ngoai=[self._go_tay(so_luong=4)],
		)
		self._dong(bg, self.item_ngoai).rate = 50000
		bg.save(ignore_permissions=True)
		bg = self._bo_dau(bg, self.item_ngoai)

		bg = self._khop(bg, self.item_ngoai)
		dong = self._dong(bg, self.item_ngoai)
		self.assertEqual(flt(dong.rate), 50000.0)
		self.assertEqual(dong.custom_nguon_gia, "Báo giá")

	def test_gop_dien_gia_bang_xoa_phan_chenh_cu_cua_dong(self):
		"""Bẫy ERPNext: dòng `rate = 0` còn mang `margin_rate_or_amount` cũ thì
		`taxes_and_totals.calculate_margin` cộng phần chênh đó lên giá bảng
		vừa điền. Phép gộp phải xoá phần chênh để dòng mang ĐÚNG giá bảng."""
		bg = self._dat(
			items=[{"item_code": self.item_ngoai, "qty": 2}],
			dat_ngoai=[self._go_tay(so_luong=4)],
		)
		frappe.db.set_value(
			"Quotation Item", self._dong(bg, self.item_ngoai).name,
			{"margin_type": "Amount", "margin_rate_or_amount": 111},
			update_modified=False,
		)
		self._tao_gia(self.item_ngoai, self.price_list, GIA_BANG_GIA)
		bg.reload()
		bg = self._khop(bg, self.item_ngoai)
		dong = self._dong(bg, self.item_ngoai)
		self.assertEqual(flt(dong.rate), float(GIA_BANG_GIA))
		self.assertEqual(flt(dong.margin_rate_or_amount), 0.0)
		self.assertEqual(flt(bg.total), 6.0 * GIA_BANG_GIA)

	def test_dong_khop_ma_luon_theo_don_vi_goc(self):
		"""Ruling R15 — ERPNext mặc định `uom` của dòng mới theo `Item.
		sales_uom`, còn giá bảng tính theo `stock_uom`. Dòng sinh ra khi khớp
		mã phải mang đơn vị gốc, hệ số 1, đúng giá bảng."""
		item = frappe.get_doc("Item", self.item_hd)
		item.append("uoms", {"uom": "Box", "conversion_factor": 10})
		item.sales_uom = "Box"
		item.save(ignore_permissions=True)

		bg = self._dat(dat_ngoai=[self._go_tay(so_luong=5)])
		bg = self._khop(bg, self.item_hd)
		dong = self._dong(bg, self.item_hd)
		self.assertEqual(dong.uom, "Cái")
		self.assertEqual(flt(dong.conversion_factor), 1.0)
		self.assertEqual(flt(dong.stock_qty), 5.0)
		self.assertEqual(flt(dong.rate), float(GIA_BANG_GIA))

	# -- BẪY 6: đổi dòng gõ tay SAU khi đã chuyển ---------------------------

	def test_doi_so_luong_sau_khi_chuyen_bi_chan(self):
		"""Bẫy 6 — CHỌN CHẶN, không đồng bộ. Lý do đầy đủ ở docstring
		`portal_mua_le._kiem_dong_da_chuyen_khong_doi`: sau khi số lượng đã
		được GỘP vào một dòng sẵn có (bẫy 2), không còn cách trung thực nào
		để biết phần nào của dòng đó tới từ dòng gõ tay."""
		bg = self._dat(dat_ngoai=[self._go_tay(so_luong=5)])
		bg = self._khop(bg, self.item_hd)
		bg.custom_dat_ngoai[0].so_luong = 9
		with self.assertRaises(frappe.ValidationError) as ctx:
			bg.save(ignore_permissions=True)
		self.assertIn("đã chuyển thành dòng hàng", str(ctx.exception))
		self.assertIn(self.item_hd, str(ctx.exception))
		bg.reload()
		self.assertEqual(flt(bg.custom_dat_ngoai[0].so_luong), 5.0)
		self.assertEqual(flt(self._dong(bg, self.item_hd).qty), 5.0)

	def test_doi_ma_khop_sau_khi_chuyen_bi_chan(self):
		"""Cùng lý do bẫy 6: `da_chuyen = 1` mà `item_khop` trỏ mã khác là
		một lời nói dối y hệt cái QĐ-G16 vừa dẹp. Câu báo lỗi phải chỉ ra
		đường gỡ, vì trên đơn NHÁP dòng gõ tay vẫn xoá được."""
		bg = self._dat(dat_ngoai=[self._go_tay()])
		bg = self._khop(bg, self.item_hd)
		bg.custom_dat_ngoai[0].item_khop = self.item_ngoai
		with self.assertRaises(frappe.ValidationError) as ctx:
			bg.save(ignore_permissions=True)
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
		bg = self._dat(dat_ngoai=[self._go_tay()])
		bg.custom_dat_ngoai[0].item_khop = ITEM_GIU_CHO
		with self.assertRaises(frappe.ValidationError) as ctx:
			bg.save(ignore_permissions=True)
		self.assertIn("mã kỹ thuật nội bộ", str(ctx.exception))
		self.assertIn(ITEM_GIU_CHO, str(ctx.exception))
		bg.reload()
		# Không được để lại một trạng thái NỬA VỜI: dòng gõ tay vẫn "chưa xử
		# lý", nên `bao_gia.chot_gui_khach` vẫn giữ báo giá lại.
		self.assertFalse(bg.custom_dat_ngoai[0].da_chuyen)
		self.assertFalse(bg.custom_dat_ngoai[0].da_xu_ly)
		self.assertEqual([d.item_code for d in bg.items], [ITEM_GIU_CHO])
		with self.assertRaises(frappe.ValidationError) as ctx2:
			apply_workflow(bg, bao_gia.HD_GUI_KHACH)
		self.assertIn("chưa khớp mã", str(ctx2.exception))

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

		bg = self._dat(dat_ngoai=[self._go_tay(so_luong=5)])
		bg = self._khop(bg, self.item_hd)
		ten_dong = bg.custom_dat_ngoai[0].name
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

	def test_gia_bang_gia_khach_b_khong_roi_vao_don_khach_a(self):
		"""HAI vế, cả hai đều DƯƠNG:

		  * mã có giá trong bảng của CHÍNH khách A ra đúng giá đó — nếu vế
		    này chết, vế cách ly bên dưới xanh chỉ vì phép chuyển luôn cho
		    `rate = 0`;
		  * mã CHỈ có giá trong bảng của khách B (và chỉ có trong hợp đồng
		    của B) ra `rate = 0`, dấu "Báo giá" — cả 43.000 trong bảng giá B
		    lẫn 77.000 trên hợp đồng B đều không được rơi sang đơn của A.
		"""
		# Đảo theo spec 2026-10-09 (giá theo Price List).
		self.assertEqual(
			bang_gia_khach.gia_bang_gia(self.kh_b, self.item_chi_b),
			float(GIA_BANG_GIA_B),
			"tiền đề: khách B THẬT SỰ có giá cho mã này",
		)
		bg = self._dat(dat_ngoai=[
			self._go_tay("Hàng của chính khách A", so_luong=1),
			self._go_tay("Hàng chỉ có giá ở khách B", so_luong=1),
		])
		bg.custom_dat_ngoai[0].item_khop = self.item_hd
		bg.custom_dat_ngoai[1].item_khop = self.item_chi_b
		bg.save(ignore_permissions=True)
		bg.reload()

		cua_a = self._dong(bg, self.item_hd)
		self.assertEqual(flt(cua_a.rate), float(GIA_BANG_GIA))
		self.assertEqual(cua_a.custom_nguon_gia, "Bảng giá")

		cua_b = self._dong(bg, self.item_chi_b)
		self.assertEqual(flt(cua_b.rate), 0.0)
		self.assertEqual(cua_b.custom_nguon_gia, "Báo giá")
		self.assertFalse(cua_b.blanket_order)
