"""Hook Delivery Note → Phiếu Nhập Kho nháp trong kho khách (thiết kế §4.3).

RÀNG BUỘC CAO NHẤT của cả file này: hook KHÔNG BAO GIỜ được làm hỏng Delivery
Note của Miyano. Mọi test ở đây đều assert `dn.docstatus == 1` (hoặc == 2 với
đường huỷ) TRƯỚC khi assert bất cứ điều gì về kho khách — nếu chỉ assert phía
kho, một hook làm vỡ nghiệp vụ bán hàng vẫn có thể lọt qua.
"""

import unittest.mock

import frappe
from frappe.tests.utils import FrappeTestCase

from erpnext.stock.doctype.stock_entry.stock_entry_utils import make_stock_entry

from miyano_portal.kho import delivery_hook, ledger
from miyano_portal.setup.seed_kho_demo import seed_kho_demo

COMPANY = "Miyano Việt Nam"
KHO_MYN = "Kho Miyano - MYN"
COST_CENTER = "Main - MYN"
KHACH = "Bệnh viện Bạch Mai"

ITEM = "MYN-GLOVE-M"
ITEM_2 = "MYN-SYR-10"
# Vật tư Miyano CHƯA có trong danh mục kho của Bạch Mai — dùng cho test tự tạo
# Customer Warehouse Item.
ITEM_MOI = "MYN-ALT"
ITEM_LO = "MYNTEST-DN-LO"

LOT_A = "LOTTEST-DNHOOK-A"
LOT_B = "LOTTEST-DNHOOK-B"
# Lô CÓ THẬT nhưng chưa khai hạn dùng — không phải lô không tồn tại.
LOT_CHUA_KHAI_HAN = "LOTTEST-DNHOOK-CHUAHAN"
HAN_A = "2027-03-31"
HAN_B = "2026-11-30"

LOAI = "Từ đơn hàng Miyano"


class TestDeliveryNoteHook(FrappeTestCase):
	def setUp(self):
		self.kho = seed_kho_demo()
		self.kho_bm = self.kho["kho_bm"]
		# `FrappeTestCase` của Frappe v15.113 rollback ĐÚNG MỘT LẦN cho cả
		# class (`setUpClass` → `addClassCleanup(_rollback_db)`), KHÔNG rollback
		# sau từng test. Mọi thay đổi phải tự đưa về mốc chuẩn ở đây, nếu không
		# một test sẽ phá mọi test đứng sau nó theo thứ tự bảng chữ cái — đúng
		# cái bẫy đã làm 12 test trong module này đỏ khi mới viết.
		frappe.db.set_value(
			"Customer Warehouse", self.kho_bm,
			{"active": 1, "ngay_bat_dau": "2026-01-01"},
		)
		frappe.db.delete("Customer Stock Ledger Entry", {"kho": self.kho_bm})
		frappe.db.delete("Customer Stock Lot Balance", {"kho": self.kho_bm})
		frappe.db.delete(
			"Customer Warehouse Item", {"kho": self.kho_bm, "item_code": ITEM_MOI}
		)
		self._nap_ton(ITEM, 500)
		self._nap_ton(ITEM_2, 500)
		self._nap_ton(ITEM_MOI, 500)
		# `tabError Log` khai engine MyISAM — bảng PHI GIAO DỊCH, nên các dòng
		# log do test ép lỗi sinh ra KHÔNG bị rollback cuối class cuốn đi mà ở
		# lại vĩnh viễn trên site. Tự dọn đúng những dòng của hook này.
		self.addCleanup(
			frappe.db.delete, "Error Log", {"method": ["like", "Kho khách:%"]}
		)

	# ------------------------------------------------------------------ setup
	def _nap_ton(self, item_code, qty, batch_no=None):
		make_stock_entry(
			item_code=item_code, qty=qty, to_warehouse=KHO_MYN, rate=1000,
			batch_no=batch_no, company=COMPANY, purpose="Material Receipt",
		)

	def _tao_vat_tu_co_lo(self):
		"""Item có lô + hai lô hạn dùng khác nhau + tồn ở kho Miyano."""
		if not frappe.db.exists("Item", ITEM_LO):
			frappe.get_doc({
				"doctype": "Item", "item_code": ITEM_LO,
				"item_name": "Vật tư test theo lô",
				"item_group": frappe.get_all(
					"Item Group", filters={"is_group": 0}, pluck="name"
				)[0],
				"stock_uom": "Hộp", "is_stock_item": 1,
				"has_batch_no": 1, "create_new_batch": 0,
			}).insert(ignore_permissions=True)
		for lot, han in ((LOT_A, HAN_A), (LOT_B, HAN_B)):
			if not frappe.db.exists("Batch", lot):
				frappe.get_doc({
					"doctype": "Batch", "batch_id": lot,
					"item": ITEM_LO, "expiry_date": han,
				}).insert(ignore_permissions=True)
			self._nap_ton(ITEM_LO, 50, batch_no=lot)

	def _dn(self, rows=None, customer=KHACH, posting_date=None, submit=True,
	        is_return=False, return_against=None):
		dn = frappe.new_doc("Delivery Note")
		dn.company = COMPANY
		dn.customer = customer
		dn.posting_date = posting_date or frappe.utils.today()
		dn.posting_time = frappe.utils.nowtime()
		dn.set_posting_time = 1
		if is_return:
			dn.is_return = 1
			dn.return_against = return_against
		for r in rows or [{"item_code": ITEM, "qty": 10, "rate": 95000}]:
			row = {
				"item_code": r["item_code"],
				"qty": r["qty"],
				"rate": r["rate"],
				"warehouse": r.get("warehouse", KHO_MYN),
				"cost_center": COST_CENTER,
				"batch_no": r.get("batch_no"),
				"use_serial_batch_fields": 1 if r.get("batch_no") else 0,
				"serial_and_batch_bundle": r.get("bundle"),
			}
			if r.get("uom"):
				# Chỉ ghi đè khi test CHỦ Ý truyền — để trống thì hành vi cũ
				# (ERPNext tự điền theo stock_uom của Item) không đổi, tránh
				# ảnh hưởng mọi test khác đã dựa vào việc tự điền đó.
				row["uom"] = r["uom"]
			dn.append("items", row)
		dn.insert(ignore_permissions=True)
		if submit:
			dn.submit()
		return dn

	def _phieu_cua(self, dn_name, docstatus_lt=2):
		return frappe.get_all(
			"Customer Stock Receipt",
			filters={"delivery_note": dn_name, "docstatus": ["<", docstatus_lt]},
			pluck="name",
		)

	def _phieu_duy_nhat(self, dn):
		names = self._phieu_cua(dn.name)
		self.assertEqual(len(names), 1, f"Kỳ vọng đúng 1 phiếu cho {dn.name}, có {names}")
		return frappe.get_doc("Customer Stock Receipt", names[0])

	# ---------------------------------------------------------- luồng cơ bản
	def test_submit_tao_dung_mot_phieu_nhap_nhap(self):
		dn = self._dn(rows=[
			{"item_code": ITEM, "qty": 10, "rate": 95000},
			{"item_code": ITEM_2, "qty": 4, "rate": 88000},
		])
		self.assertEqual(dn.docstatus, 1)

		phieu = self._phieu_duy_nhat(dn)
		self.assertEqual(phieu.docstatus, 0, "Phiếu phải ở trạng thái NHÁP")
		self.assertEqual(phieu.kho, self.kho_bm)
		self.assertEqual(phieu.loai_nhap, LOAI)
		self.assertEqual(phieu.delivery_note, dn.name)
		self.assertEqual(str(phieu.ngay), str(dn.posting_date))

		self.assertEqual(len(phieu.items), 2)
		theo_ma = {
			frappe.db.get_value("Customer Warehouse Item", r.vat_tu, "item_code"): r
			for r in phieu.items
		}
		self.assertEqual(theo_ma[ITEM].so_luong, 10)
		self.assertEqual(theo_ma[ITEM].don_gia, 95000)
		self.assertEqual(theo_ma[ITEM_2].so_luong, 4)
		self.assertEqual(theo_ma[ITEM_2].don_gia, 88000)
		# Vật tư phải là vật tư CỦA KHO NÀY, không phải của kho khác.
		for r in phieu.items:
			self.assertEqual(
				frappe.db.get_value("Customer Warehouse Item", r.vat_tu, "kho"),
				self.kho_bm,
			)

	def test_phieu_nhap_khong_ghi_so_ngay(self):
		"""Nháp nghĩa là sổ kho chưa được chạm — thủ kho đối chiếu rồi mới ghi."""
		dn = self._dn()
		self.assertEqual(dn.docstatus, 1)
		self._phieu_duy_nhat(dn)
		self.assertEqual(
			frappe.db.count("Customer Stock Ledger Entry", {"kho": self.kho_bm}), 0
		)

	def test_chay_lai_hook_khong_tao_phieu_thu_hai(self):
		dn = self._dn()
		self._phieu_duy_nhat(dn)
		delivery_hook.on_delivery_note_submit(dn)
		delivery_hook.on_delivery_note_submit(frappe.get_doc("Delivery Note", dn.name))
		self.assertEqual(len(self._phieu_cua(dn.name)), 1)

	def test_chong_trung_van_dung_khi_phieu_da_ghi_so(self):
		"""docstatus < 2 gồm cả phiếu ĐÃ SUBMIT, không chỉ phiếu nháp."""
		dn = self._dn()
		phieu = self._phieu_duy_nhat(dn)
		phieu.submit()
		delivery_hook.on_delivery_note_submit(dn)
		self.assertEqual(len(self._phieu_cua(dn.name)), 1)

	def test_giao_hang_lan_hai_cung_don_tao_phieu_rieng(self):
		"""Giao từng phần → nhiều phiếu, KHÔNG được gộp/khử trùng."""
		dn1 = self._dn(rows=[{"item_code": ITEM, "qty": 6, "rate": 95000}])
		dn2 = self._dn(rows=[{"item_code": ITEM, "qty": 4, "rate": 95000}])
		self.assertEqual(dn1.docstatus, 1)
		self.assertEqual(dn2.docstatus, 1)
		p1 = self._phieu_duy_nhat(dn1)
		p2 = self._phieu_duy_nhat(dn2)
		self.assertNotEqual(p1.name, p2.name)
		self.assertEqual(p1.items[0].so_luong, 6)
		self.assertEqual(p2.items[0].so_luong, 4)

	def test_sales_order_duoc_ghi_de_truy_vet(self):
		from erpnext.selling.doctype.sales_order.sales_order import make_delivery_note

		so = self._sales_order()
		dn = make_delivery_note(so.name)
		dn.posting_date = frappe.utils.today()
		dn.set_posting_time = 1
		for r in dn.items:
			r.qty = 3
			r.warehouse = KHO_MYN
			r.cost_center = COST_CENTER
		dn.insert(ignore_permissions=True)
		dn.submit()
		self.assertEqual(dn.docstatus, 1)
		phieu = self._phieu_duy_nhat(dn)
		self.assertEqual(phieu.sales_order, so.name)

	def _sales_order(self):
		so = frappe.new_doc("Sales Order")
		so.customer = KHACH
		so.company = COMPANY
		so.transaction_date = frappe.utils.today()
		so.delivery_date = frappe.utils.add_days(frappe.utils.today(), 2)
		so.append("items", {
			"item_code": ITEM, "qty": 10, "rate": 95000,
			"warehouse": KHO_MYN, "delivery_date": frappe.utils.add_days(frappe.utils.today(), 2),
		})
		so.insert(ignore_permissions=True)
		so.submit()
		return so

	# ------------------------------------------------- không bao giờ chặn DN
	def test_khach_khong_co_kho_van_giao_hang_duoc(self):
		khach = "Bệnh viện Đa khoa Miyano"
		self.assertFalse(
			frappe.db.exists("Customer Warehouse", {"customer": khach}),
			"Tiền đề của test: khách này chưa mở kho.",
		)
		dn = self._dn(customer=khach)
		self.assertEqual(dn.docstatus, 1)
		self.assertEqual(self._phieu_cua(dn.name), [])

	def test_kho_ngung_hoat_dong_khong_nhan_phieu_dn_van_submit(self):
		frappe.db.set_value("Customer Warehouse", self.kho_bm, "active", 0)
		dn = self._dn()
		self.assertEqual(dn.docstatus, 1)
		self.assertEqual(self._phieu_cua(dn.name), [])

	def test_loi_ben_trong_khong_chan_delivery_note(self):
		"""Ép hook hỏng từ bên trong: DN vẫn phải submit, lỗi phải vào Error Log.

		`_kho_cua_khach` được DÙNG CHUNG bởi cả hai lệnh gọi `_chay_an_toan()`
		trong `on_delivery_note_submit` (tạo phiếu VÀ gửi thông báo đã nhập
		hàng — brief 2026-08-15, xem chú thích ở đó) — ép hỏng nó nên hỏng
		CẢ HAI, mỗi lệnh gọi có savepoint/log RIÊNG. Đúng hai dòng Error Log
		là bằng chứng cả hai lớp bọc đều hoạt động độc lập, không phải một
		lỗi đếm sai.
		"""
		with unittest.mock.patch.object(
			delivery_hook, "_kho_cua_khach", side_effect=RuntimeError("hỏng có chủ ý")
		):
			dn = self._dn()
		self.assertEqual(dn.docstatus, 1, "Delivery Note PHẢI submit được dù hook hỏng")
		self.assertEqual(frappe.db.get_value("Delivery Note", dn.name, "docstatus"), 1)
		self.assertEqual(self._phieu_cua(dn.name), [])

		# Đếm tổng số dòng Error Log là một assert rỗng: bất kỳ lỗi nào khác
		# xảy ra trong test cũng làm nó tăng. Phải soi ĐÚNG dòng log của hook
		# này, đúng Delivery Note này, và đúng lỗi đã ép ra.
		log = frappe.get_all(
			"Error Log",
			filters={"reference_doctype": "Delivery Note", "reference_name": dn.name},
			fields=["method", "error"],
		)
		self.assertEqual(
			len(log), 2,
			"Cả hai lệnh gọi _chay_an_toan (tạo phiếu + gửi thông báo) đều "
			"phải tự log lỗi riêng",
		)
		tieu_de = {r.method for r in log}
		self.assertIn("Kho khách: lỗi khi tạo phiếu nhập từ Delivery Note", tieu_de)
		self.assertIn("Kho khách: lỗi khi gửi thông báo đã nhập hàng", tieu_de)
		for r in log:
			self.assertIn("hỏng có chủ ý", r.error)

	def test_loi_giua_chung_khong_de_lai_du_lieu_nua_voi(self):
		"""Hỏng SAU khi đã tạo Customer Warehouse Item → savepoint phải cuốn lại."""
		cwi_truoc = frappe.db.count("Customer Warehouse Item", {"kho": self.kho_bm})
		with unittest.mock.patch.object(
			delivery_hook, "_tao_phieu", side_effect=RuntimeError("hỏng sau khi tạo vật tư")
		):
			dn = self._dn(rows=[{"item_code": ITEM_MOI, "qty": 2, "rate": 1250000}])
		self.assertEqual(dn.docstatus, 1)
		self.assertEqual(
			frappe.db.count("Customer Warehouse Item", {"kho": self.kho_bm}), cwi_truoc,
			"Vật tư tạo dở phải bị cuốn lại cùng savepoint",
		)

	def test_dn_truoc_ngay_bat_dau_van_tao_phieu_ghim_ngay_va_luu_ngay_that(self):
		"""Hàng giao trước Ngày bắt đầu quản lý kho KHÔNG được biến mất (review
		Item 1): phiếu vẫn phải sinh ra, `ngay` ghim vào đúng `ngay_bat_dau`
		(để qua được validate_ngay), và ngày giao THẬT phải lộ ra trên
		`dien_giai` chứ không bị giấu."""
		ngay_bat_dau = frappe.utils.today()
		ngay_giao_that = frappe.utils.add_days(ngay_bat_dau, -100)
		frappe.db.set_value("Customer Warehouse", self.kho_bm, "ngay_bat_dau", ngay_bat_dau)
		# Tồn của Miyano phải có SẴN TỪ TRƯỚC ngay_giao_that — nếu không, bản
		# thân DN backdated bị chặn bởi kiểm tra tồn âm của ERPNext
		# (NegativeStockError), không liên quan gì tới hook đang test ở đây.
		make_stock_entry(
			item_code=ITEM, qty=500, to_warehouse=KHO_MYN, rate=1000,
			company=COMPANY, purpose="Material Receipt",
			posting_date=frappe.utils.add_days(ngay_giao_that, -10),
		)

		dn = self._dn(posting_date=ngay_giao_that)
		self.assertEqual(dn.docstatus, 1, "DN vẫn phải submit được dù backdated")

		phieu = self._phieu_duy_nhat(dn)
		self.assertEqual(
			frappe.utils.getdate(phieu.ngay), frappe.utils.getdate(ngay_bat_dau),
			"Ngày phiếu phải ghim vào ngay_bat_dau, không giữ nguyên ngày backdated",
		)
		self.assertIn(
			frappe.utils.formatdate(ngay_giao_that), phieu.dien_giai,
			"Ngày giao hàng thật phải hiện trên dien_giai để không bị giấu",
		)
		# Hàng không được coi là "lỗi": _chay_an_toan không được để lại log nào
		# cho luồng này, vì đây không phải một lỗi bị nuốt mà là hàng vi đã
		# được ghi nhận đúng qua nhánh ghim ngày.
		self.assertEqual(
			frappe.get_all(
				"Error Log",
				filters={"reference_doctype": "Delivery Note", "reference_name": dn.name},
			),
			[],
		)

	def test_dn_dung_ngay_bat_dau_khong_bi_ghim_lai(self):
		"""Đối chứng: DN đúng hoặc sau ngay_bat_dau thì ngay của phiếu PHẢI là
		chính posting_date của DN, không bị ghim đi đâu khác."""
		dn = self._dn(posting_date=frappe.utils.today())
		phieu = self._phieu_duy_nhat(dn)
		self.assertEqual(
			frappe.utils.getdate(phieu.ngay), frappe.utils.getdate(dn.posting_date)
		)
		self.assertNotIn("CẢNH BÁO", phieu.dien_giai)

	def test_dn_tra_hang_khong_tao_phieu(self):
		goc = self._dn(rows=[{"item_code": ITEM, "qty": 10, "rate": 95000}])
		self._phieu_duy_nhat(goc)
		tra = self._dn(
			rows=[{"item_code": ITEM, "qty": -2, "rate": 95000}],
			is_return=True, return_against=goc.name,
		)
		self.assertEqual(tra.docstatus, 1)
		self.assertEqual(
			self._phieu_cua(tra.name), [],
			"Hàng trả VỀ Miyano không được cộng vào kho khách",
		)

	# ------------------------------------------------------------- lô và hạn
	def test_khong_co_lo_thi_dung_LOT_KHONG_CO_va_khong_han(self):
		dn = self._dn()
		phieu = self._phieu_duy_nhat(dn)
		self.assertEqual(phieu.items[0].so_lo, ledger.LOT_KHONG_CO)
		self.assertFalse(phieu.items[0].han_su_dung)

	def test_lo_va_han_lay_tu_bundle_mot_lo(self):
		self._tao_vat_tu_co_lo()
		bundle = self._bundle({LOT_A: -5}, qty=-5)
		dn = self._dn(rows=[
			{"item_code": ITEM_LO, "qty": 5, "rate": 12000, "bundle": bundle}
		])
		self.assertEqual(dn.docstatus, 1)
		phieu = self._phieu_duy_nhat(dn)
		self.assertEqual(len(phieu.items), 1)
		self.assertEqual(phieu.items[0].so_lo, LOT_A)
		self.assertEqual(str(phieu.items[0].han_su_dung), HAN_A)
		self.assertEqual(phieu.items[0].so_luong, 5)

	def test_mot_dong_dn_hai_lo_thanh_hai_dong_phieu(self):
		self._tao_vat_tu_co_lo()
		bundle = self._bundle({LOT_A: -3, LOT_B: -2}, qty=-5)
		dn = self._dn(rows=[
			{"item_code": ITEM_LO, "qty": 5, "rate": 12000, "bundle": bundle}
		])
		self.assertEqual(dn.docstatus, 1)
		phieu = self._phieu_duy_nhat(dn)
		self.assertEqual(len(phieu.items), 2, "Một dòng DN tách hai lô → hai dòng phiếu")
		theo_lo = {r.so_lo: r for r in phieu.items}
		self.assertEqual(theo_lo[LOT_A].so_luong, 3)
		self.assertEqual(str(theo_lo[LOT_A].han_su_dung), HAN_A)
		self.assertEqual(theo_lo[LOT_B].so_luong, 2)
		self.assertEqual(str(theo_lo[LOT_B].han_su_dung), HAN_B)
		# Đơn giá là rate của DÒNG DN, giống nhau cho cả hai lô.
		self.assertEqual(theo_lo[LOT_A].don_gia, 12000)
		self.assertEqual(theo_lo[LOT_B].don_gia, 12000)
		self.assertEqual(phieu.tong_tien, 5 * 12000)

	def test_dn_gan_batch_no_cho_ra_dung_lo_va_han(self):
		"""Đường thật của build này: gắn `batch_no`, ERPNext tự sinh bundle."""
		self._tao_vat_tu_co_lo()
		dn = self._dn(rows=[
			{"item_code": ITEM_LO, "qty": 4, "rate": 12000, "batch_no": LOT_B}
		])
		self.assertEqual(dn.docstatus, 1)
		phieu = self._phieu_duy_nhat(dn)
		self.assertEqual(len(phieu.items), 1)
		self.assertEqual(phieu.items[0].so_lo, LOT_B)
		self.assertEqual(str(phieu.items[0].han_su_dung), HAN_B)
		self.assertEqual(phieu.items[0].so_luong, 4)

	def test_doc_batch_no_khi_dong_khong_co_bundle(self):
		"""Nhánh dự phòng: bundle rỗng → đọc `Delivery Note Item.batch_no`.

		Tách riêng khỏi test end-to-end ở trên vì trên build này ERPNext LUÔN
		sinh bundle cho dòng có batch_no trước khi hook chạy, nên đường
		end-to-end không bao giờ chạm được nhánh này.
		"""
		self._tao_vat_tu_co_lo()
		row = frappe._dict(
			item_code=ITEM_LO, qty=4, conversion_factor=1,
			serial_and_batch_bundle=None, batch_no=LOT_A,
		)
		self.assertEqual(
			delivery_hook._lo_cua_dong(row), [(LOT_A, HAN_A, 4.0)]
		)

	def test_bundle_duoc_uu_tien_hon_batch_no(self):
		"""Thứ tự đọc là bundle TRƯỚC, batch_no sau — không phải ngược lại."""
		self._tao_vat_tu_co_lo()
		bundle = self._bundle({LOT_A: -3, LOT_B: -2}, qty=-5)
		row = frappe._dict(
			item_code=ITEM_LO, qty=5, conversion_factor=1,
			serial_and_batch_bundle=bundle, batch_no=LOT_B,
		)
		self.assertEqual(
			sorted(delivery_hook._lo_cua_dong(row)),
			sorted([(LOT_A, HAN_A, 3.0), (LOT_B, HAN_B, 2.0)]),
		)

	def test_nhieu_entry_cung_lo_trong_bundle_gop_thanh_mot_dong(self):
		"""Hàng theo serial cho ra N entry qty 1 — không được thành N dòng phiếu."""
		row = frappe._dict(
			item_code=ITEM_LO, qty=3, conversion_factor=1,
			serial_and_batch_bundle="BUNDLE-GIA-DINH", batch_no=None,
		)
		entries = [
			frappe._dict(batch_no=LOT_A, qty=-1),
			frappe._dict(batch_no=LOT_A, qty=-1),
			frappe._dict(batch_no=LOT_A, qty=-1),
		]
		self._tao_vat_tu_co_lo()
		with unittest.mock.patch.object(
			delivery_hook, "_entry_cua_bundle", return_value=entries
		):
			self.assertEqual(delivery_hook._lo_cua_dong(row), [(LOT_A, HAN_A, 3.0)])

	def test_entry_bundle_khong_co_batch_no_van_ra_mot_dong_LOT_KHONG_CO(self):
		"""Hàng chỉ theo serial: entry có serial_no nhưng batch_no rỗng."""
		row = frappe._dict(
			item_code=ITEM, qty=2, conversion_factor=1,
			serial_and_batch_bundle="BUNDLE-GIA-DINH", batch_no=None,
		)
		entries = [frappe._dict(batch_no=None, qty=-1), frappe._dict(batch_no="", qty=-1)]
		with unittest.mock.patch.object(
			delivery_hook, "_entry_cua_bundle", return_value=entries
		):
			self.assertEqual(
				delivery_hook._lo_cua_dong(row), [(ledger.LOT_KHONG_CO, None, 2.0)]
			)

	def test_lo_khong_co_han_van_giu_dung_CAP_lo_thu_n_han_thu_n(self):
		"""`lo_han_cho_in` hứa trong docstring: "lô thứ n ứng với hạn thứ n".

		Bản trước dựng `so_lo` từ MỌI lô nhưng `han_dung` chỉ từ lô CÓ hạn, nên
		một dòng trộn lô-có-hạn với lô-chưa-khai-hạn in ra hai cột LỆCH NHAU:
		lô đầu tiên (chưa khai hạn) nhận hạn của lô thứ hai. Đó là GHI SAI HẠN
		DÙNG cho một lô, trên biên bản bàn giao dược phẩm có chữ ký hai bên —
		không phải chuyện trình bày.

		Thứ tự cố ý đặt lô KHÔNG hạn ĐỨNG TRƯỚC: đó là ca gây hại thật. Nếu lô
		không hạn đứng sau, người đọc vẫn ghép đúng nhờ may.
		"""
		self._tao_vat_tu_co_lo()
		if not frappe.db.exists("Batch", LOT_CHUA_KHAI_HAN):
			frappe.get_doc({
				"doctype": "Batch", "batch_id": LOT_CHUA_KHAI_HAN,
				"item": ITEM_LO,
			}).insert(ignore_permissions=True)
		row = frappe._dict(
			item_code=ITEM_LO, qty=5, conversion_factor=1,
			serial_and_batch_bundle="BUNDLE-GIA-DINH", batch_no=None,
		)
		entries = [
			frappe._dict(batch_no=LOT_CHUA_KHAI_HAN, qty=-2),
			frappe._dict(batch_no=LOT_A, qty=-3),
		]
		with unittest.mock.patch.object(
			delivery_hook, "_entry_cua_bundle", return_value=entries
		):
			kq = delivery_hook.lo_han_cho_in(row)
		self.assertEqual(kq["so_lo"], f"{LOT_CHUA_KHAI_HAN}, {LOT_A}")
		self.assertEqual(
			kq["han_dung"],
			f"{delivery_hook.KHONG_KHAI_HAN}, {frappe.utils.formatdate(HAN_A, 'dd/MM/yyyy')}",
			"cột Hạn dùng lệch cột Số lô — lô đầu nhận hạn của lô sau",
		)

	def test_ca_dong_khong_lo_nao_co_han_thi_cot_han_de_TRONG(self):
		"""Không được in một hàng gạch ngang cho một dòng mà KHÔNG lô nào khai
		hạn: ô trống nghĩa là "không có thông tin", còn gạch ngang chỉ có nghĩa
		khi đứng cạnh một hạn thật để giữ cặp."""
		self._tao_vat_tu_co_lo()
		if not frappe.db.exists("Batch", LOT_CHUA_KHAI_HAN):
			frappe.get_doc({
				"doctype": "Batch", "batch_id": LOT_CHUA_KHAI_HAN,
				"item": ITEM_LO,
			}).insert(ignore_permissions=True)
		row = frappe._dict(
			item_code=ITEM_LO, qty=2, conversion_factor=1,
			serial_and_batch_bundle="BUNDLE-GIA-DINH", batch_no=None,
		)
		entries = [frappe._dict(batch_no=LOT_CHUA_KHAI_HAN, qty=-2)]
		with unittest.mock.patch.object(
			delivery_hook, "_entry_cua_bundle", return_value=entries
		):
			kq = delivery_hook.lo_han_cho_in(row)
		self.assertEqual(kq["so_lo"], LOT_CHUA_KHAI_HAN)
		self.assertEqual(kq["han_dung"], "")

	# ------------------------------------------- cam kết bàn giao (Ruling P47)
	def _dong_don(self, qty):
		"""Một dòng Sales Order ĐÃ GHI SỔ, trả về `name` của dòng (`so_detail`)."""
		so = frappe.new_doc("Sales Order")
		so.customer = KHACH
		so.company = COMPANY
		so.transaction_date = frappe.utils.today()
		so.delivery_date = frappe.utils.add_days(frappe.utils.today(), 3)
		so.append("items", {
			"item_code": ITEM, "qty": qty, "rate": 1000,
			"warehouse": KHO_MYN, "delivery_date": so.delivery_date,
			"cost_center": COST_CENTER,
		})
		so.insert(ignore_permissions=True)
		so.submit()
		self.addCleanup(self._huy_don, so.name)
		return so.items[0].name

	@staticmethod
	def _huy_don(ten):
		doc = frappe.get_doc("Sales Order", ten)
		if doc.docstatus == 1:
			doc.cancel()
		frappe.delete_doc("Sales Order", ten, force=True, ignore_permissions=True)

	def test_giao_du_va_giao_thua_deu_dung_cau_goc(self):
		sd = self._dong_don(10)
		du = frappe._dict(is_return=0, items=[frappe._dict(so_detail=sd, qty=10)])
		thua = frappe._dict(is_return=0, items=[frappe._dict(so_detail=sd, qty=12)])
		self.assertTrue(delivery_hook.giao_du_theo_don(du))
		self.assertTrue(
			delivery_hook.giao_du_theo_don(thua),
			"giao THỪA không phải giao thiếu — câu cam kết gốc vẫn đúng",
		)

	def test_mot_dong_don_tach_nhieu_dong_phieu_van_la_giao_DU(self):
		"""Một dòng đơn hàng tách thành nhiều dòng trên CÙNG một phiếu (khác
		kho, khác lô). So từng dòng một sẽ báo "thiếu" cho một phiếu giao đủ —
		phải gộp theo `so_detail` TRƯỚC khi so."""
		sd = self._dong_don(10)
		doc = frappe._dict(is_return=0, items=[
			frappe._dict(so_detail=sd, qty=6),
			frappe._dict(so_detail=sd, qty=4),
		])
		self.assertTrue(delivery_hook.giao_du_theo_don(doc))

	def test_phieu_TRA_HANG_chan_ngay_khong_di_so_sanh(self):
		"""Chốt `is_return` phải chặn TRƯỚC phép so, không phải trùng kết quả
		với nó: dựng một phiếu trả hàng mà phép so sẽ nói "đủ" (số dương, bằng
		đúng số đã đặt). Bỏ chốt đi thì hàm trả "đủ" và tờ trả hàng khẳng định
		"bàn giao đầy đủ" — một câu vô nghĩa trên chứng từ hàng đi ngược."""
		sd = self._dong_don(10)
		doc = frappe._dict(is_return=1, items=[frappe._dict(so_detail=sd, qty=10)])
		self.assertFalse(delivery_hook.giao_du_theo_don(doc))

	def test_khong_co_so_detail_thi_khong_bi_coi_la_thieu(self):
		doc = frappe._dict(is_return=0, items=[frappe._dict(so_detail=None, qty=7)])
		self.assertTrue(delivery_hook.giao_du_theo_don(doc))

	def test_dong_don_da_bi_xoa_thi_khong_suy_doan(self):
		"""`so_detail` trỏ vào một dòng đơn không còn tồn tại: không so được.
		Đoán bừa "thiếu" là đổi câu cam kết vì một lý do không ai kiểm được."""
		doc = frappe._dict(
			is_return=0,
			items=[frappe._dict(so_detail="KHONG-CO-DONG-NAY", qty=1)],
		)
		self.assertTrue(delivery_hook.giao_du_theo_don(doc))

	# ---------------------------------------------------------- danh mục vật tư
	def test_vat_tu_chua_co_duoc_tao_moi_va_khong_tao_Item(self):
		item_truoc = frappe.db.count("Item")
		self.assertFalse(
			frappe.db.exists(
				"Customer Warehouse Item", {"kho": self.kho_bm, "item_code": ITEM_MOI}
			),
			"Tiền đề của test: vật tư này chưa có trong kho khách.",
		)
		dn = self._dn(rows=[{"item_code": ITEM_MOI, "qty": 2, "rate": 1250000}])
		self.assertEqual(dn.docstatus, 1)
		phieu = self._phieu_duy_nhat(dn)
		vt = frappe.get_doc("Customer Warehouse Item", phieu.items[0].vat_tu)
		self.assertEqual(vt.kho, self.kho_bm)
		self.assertEqual(vt.item_code, ITEM_MOI, "item_code phải trỏ về Item THẬT")
		self.assertEqual(vt.ma_vat_tu, ITEM_MOI)
		self.assertEqual(
			frappe.db.count("Item"), item_truoc, "Hook KHÔNG được tạo Item của ERPNext"
		)

	def test_vat_tu_da_co_duoc_dung_lai_dung_ban_ghi_do(self):
		"""Vật tư đã có trong danh mục kho phải được DÙNG LẠI, đúng bản ghi đó.

		Cố ý KHÔNG kiểm bằng mỗi số đếm bản ghi. `CustomerWarehouseItem
		._unique_within_warehouse()` đã chặn trùng mã ở tầng doctype, nên số
		đếm vẫn y nguyên KỂ CẢ khi hook tra cứu sai hoàn toàn — lúc đó hook chỉ
		ném lỗi rồi bị `_chay_an_toan` nuốt, và một assert đếm sẽ xanh trong khi
		tính năng đã hỏng. Phải soi đúng bản ghi mà dòng phiếu trỏ tới.
		"""
		co_san = frappe.db.get_value(
			"Customer Warehouse Item", {"kho": self.kho_bm, "ma_vat_tu": ITEM}, "name"
		)
		self.assertTrue(co_san, "Tiền đề của test: vật tư này đã có sẵn trong kho.")
		truoc = frappe.db.count("Customer Warehouse Item", {"kho": self.kho_bm})

		dn = self._dn(rows=[
			{"item_code": ITEM, "qty": 2, "rate": 95000},
			{"item_code": ITEM, "qty": 3, "rate": 95000},
		])
		phieu = self._phieu_duy_nhat(dn)
		self.assertEqual([r.vat_tu for r in phieu.items], [co_san, co_san])
		self.assertEqual(
			frappe.db.count("Customer Warehouse Item", {"kho": self.kho_bm}), truoc
		)

	# ------------------------------------------------- lệch ĐVT (review Item 2)
	def test_dvt_khac_danh_muc_khong_gay_le_kho_ma_hien_canh_bao(self):
		"""Giao lần đầu bằng "Hộp" (khớp dvt của vt_bm), lần hai bằng "Cái":
		hook KHÔNG được âm thầm cộng 10 Hộp + 5 Cái thành "15" của một đơn vị
		không xác định — dòng lệch phải mang cảnh báo hiển thị, không phải
		một con số câm."""
		co_san = frappe.db.get_value(
			"Customer Warehouse Item", {"kho": self.kho_bm, "ma_vat_tu": ITEM}, "name"
		)
		dvt_kho = frappe.db.get_value("Customer Warehouse Item", co_san, "dvt")
		self.assertEqual(dvt_kho, "Hộp", "Tiền đề của test: dvt đã chốt của vt_bm là Hộp.")

		dn = self._dn(rows=[{"item_code": ITEM, "qty": 5, "rate": 95000, "uom": "Cái"}])
		self.assertEqual(dn.docstatus, 1, "DN vẫn phải submit được dù ĐVT lệch danh mục")

		phieu = self._phieu_duy_nhat(dn)
		self.assertEqual(phieu.items[0].vat_tu, co_san, "Vẫn dùng lại đúng vật tư cũ")
		self.assertIn("CẢNH BÁO", phieu.items[0].ghi_chu)
		self.assertIn("Cái", phieu.items[0].ghi_chu)
		self.assertIn("Hộp", phieu.items[0].ghi_chu)
		self.assertIn(
			"CẢNH BÁO", phieu.dien_giai,
			"Cảnh báo phải nổi lên cả phần mô tả đầu phiếu, không chỉ ở dòng",
		)
		# dvt đã chốt của danh mục KHÔNG được hook âm thầm sửa lại.
		self.assertEqual(
			frappe.db.get_value("Customer Warehouse Item", co_san, "dvt"), "Hộp"
		)

		log = frappe.get_all(
			"Error Log",
			filters={"reference_doctype": "Customer Warehouse Item", "reference_name": co_san},
			fields=["method"],
		)
		self.assertEqual(len(log), 1, "Lệch ĐVT phải để lại đúng một dòng Error Log")
		self.assertIn("Kho khách", log[0].method)

	def test_dvt_khop_danh_muc_khong_co_canh_bao(self):
		"""Đối chứng: ĐVT trùng thì KHÔNG được báo lệch — tránh báo động giả
		trên mọi phiếu bình thường (đây là đường đi của TUYỆT ĐẠI ĐA SỐ DN)."""
		dn = self._dn(rows=[{"item_code": ITEM, "qty": 5, "rate": 95000, "uom": "Hộp"}])
		phieu = self._phieu_duy_nhat(dn)
		self.assertEqual(phieu.items[0].ghi_chu, "")
		self.assertNotIn("CẢNH BÁO", phieu.dien_giai)

	def test_canh_bao_lech_dvt_khoan_dung_hoa_thuong_va_khoang_trang(self):
		"""Đơn vị: `_canh_bao_lech_dvt` không được báo lệch giả vì hoa/thường
		hay khoảng trắng thừa — "Hộp" và " hộp " là MỘT ĐVT. Test thẳng hàm
		nội bộ (như `_lo_cua_dong` đã được test trong file này) vì trường Link
		`uom` của Delivery Note Item không chấp nhận các biến thể này để dựng
		một DN thật."""
		co_san = frappe.db.get_value(
			"Customer Warehouse Item", {"kho": self.kho_bm, "ma_vat_tu": ITEM}, "name"
		)
		self.assertIsNone(delivery_hook._canh_bao_lech_dvt(co_san, " hộp "))
		self.assertIsNone(delivery_hook._canh_bao_lech_dvt(co_san, "HỘP"))
		self.assertIsNotNone(delivery_hook._canh_bao_lech_dvt(co_san, "Cái"))

	def test_vat_tu_moi_tao_khong_bao_gio_bao_lech_voi_chinh_no(self):
		"""Vật tư MỚI tạo trong chính hook này lấy dvt từ đúng dòng DN đó — so
		nó với chính nó sẽ luôn khớp, không được báo lệch giả trên phiếu đầu
		tiên của một mặt hàng."""
		dn = self._dn(rows=[{"item_code": ITEM_MOI, "qty": 2, "rate": 1250000, "uom": "Thùng"}])
		phieu = self._phieu_duy_nhat(dn)
		self.assertEqual(phieu.items[0].ghi_chu, "")
		vt = frappe.get_doc("Customer Warehouse Item", phieu.items[0].vat_tu)
		self.assertEqual(vt.dvt, "Thùng")

	# --------------------------------------------------------------- huỷ DN
	def test_huy_dn_xoa_phieu_con_nhap(self):
		dn = self._dn()
		phieu = self._phieu_duy_nhat(dn)
		dn.cancel()
		self.assertEqual(dn.docstatus, 2)
		self.assertFalse(frappe.db.exists("Customer Stock Receipt", phieu.name))
		self.assertEqual(self._phieu_cua(dn.name), [])

	def test_huy_dn_dao_phieu_da_ghi_so(self):
		dn = self._dn()
		phieu = self._phieu_duy_nhat(dn)
		phieu.submit()
		vat_tu = phieu.items[0].vat_tu
		self.assertEqual(
			ledger.get_lot_balance(self.kho_bm, vat_tu, ledger.LOT_KHONG_CO)["so_luong"], 10
		)

		dn.cancel()
		self.assertEqual(dn.docstatus, 2)
		self.assertEqual(
			frappe.db.get_value("Customer Stock Receipt", phieu.name, "docstatus"), 2
		)
		# Đảo bằng bút toán đối ứng, KHÔNG xoá dòng sổ gốc.
		self.assertEqual(
			ledger.get_lot_balance(self.kho_bm, vat_tu, ledger.LOT_KHONG_CO)["so_luong"], 0
		)
		self.assertEqual(
			frappe.db.count("Customer Stock Ledger Entry", {"kho": self.kho_bm}), 2
		)

	def test_phieu_dao_khong_mang_delivery_note(self):
		"""Nếu phiếu đảo copy `delivery_note`, truy vấn chống trùng sẽ hỏng."""
		dn = self._dn()
		phieu = self._phieu_duy_nhat(dn)
		phieu.submit()
		dn.cancel()
		dao = frappe.get_all(
			"Customer Stock Receipt",
			filters={"phieu_goc": phieu.name},
			fields=["name", "delivery_note", "loai_nhap"],
		)
		self.assertEqual(len(dao), 1)
		self.assertEqual(dao[0].loai_nhap, "Phiếu đảo")
		self.assertFalse(dao[0].delivery_note)

	def test_huy_dn_khong_bi_chan_khi_hang_da_xuat_mat(self):
		"""Đảo sẽ làm tồn âm → controller chặn. DN vẫn PHẢI huỷ được."""
		dn = self._dn()
		phieu = self._phieu_duy_nhat(dn)
		phieu.submit()
		vat_tu = phieu.items[0].vat_tu
		xuat = frappe.get_doc({
			"doctype": "Customer Stock Issue", "kho": self.kho_bm,
			"ngay": frappe.utils.today(), "loai_xuat": "Xuất sử dụng",
			"items": [{
				"vat_tu": vat_tu, "so_lo": ledger.LOT_KHONG_CO, "so_luong": 10,
			}],
		})
		xuat.insert(ignore_permissions=True)
		xuat.submit()

		dn.cancel()
		self.assertEqual(dn.docstatus, 2, "DN phải huỷ được dù không đảo được phiếu")
		self.assertEqual(
			frappe.db.get_value("Customer Stock Receipt", phieu.name, "docstatus"), 1,
			"Phiếu đã ghi sổ vẫn còn nguyên, không bị huỷ nửa vời",
		)
		self.assertEqual(
			ledger.get_lot_balance(self.kho_bm, vat_tu, ledger.LOT_KHONG_CO)["so_luong"], 0
		)

	def test_amend_dn_khong_sinh_phieu_thu_hai(self):
		dn = self._dn()
		self._phieu_duy_nhat(dn)
		dn.cancel()
		moi = frappe.copy_doc(dn)
		moi.docstatus = 0
		moi.amended_from = dn.name
		moi.posting_date = frappe.utils.today()
		moi.set_posting_time = 1
		moi.insert(ignore_permissions=True)
		moi.submit()
		self.assertEqual(moi.docstatus, 1)
		con_lai = frappe.get_all(
			"Customer Stock Receipt",
			filters={
				"delivery_note": ["in", [dn.name, moi.name]],
				"docstatus": ["<", 2],
			},
			pluck="name",
		)
		self.assertEqual(len(con_lai), 1, f"Chỉ được còn đúng 1 phiếu sống: {con_lai}")
		self.assertEqual(
			frappe.db.get_value("Customer Stock Receipt", con_lai[0], "delivery_note"),
			moi.name,
		)

	def test_huy_dn_cua_khach_khong_co_kho_khong_no(self):
		dn = self._dn(customer="Bệnh viện Đa khoa Miyano")
		dn.cancel()
		self.assertEqual(dn.docstatus, 2)

	# ----------------------------------------------- thông báo "đã nhập hàng"
	# brief 2026-08-15 (trang thông báo) Phần 3 — QĐ nền 4: lệnh gọi RIÊNG,
	# savepoint RIÊNG với lệnh tạo phiếu (xem chú thích ở
	# `on_delivery_note_submit`). `KHACH` ("Bệnh viện Bạch Mai") có tài khoản
	# cổng thật (`bvbm@demo.miyano`, cấp bởi `seed_demo()` mà `seed_kho_demo()`
	# gọi trong `setUp`).
	USER_KHACH = "bvbm@demo.miyano"

	def test_giao_hang_gui_thong_bao_da_nhap_hang_dung_nguoi(self):
		frappe.db.delete("Notification Log", {"for_user": self.USER_KHACH})
		dn = self._dn()
		phieu = self._phieu_duy_nhat(dn)
		log = frappe.get_all(
			"Notification Log",
			filters={
				"for_user": self.USER_KHACH,
				"document_type": "Customer Stock Receipt",
				"document_name": phieu.name,
			},
			fields=["subject", "type"],
		)
		self.assertEqual(len(log), 1)
		self.assertIn(phieu.name, log[0].subject)
		self.assertEqual(log[0].type, "Alert")

	def test_thong_bao_khong_trung_khi_chay_lai_hook(self):
		frappe.db.delete("Notification Log", {"for_user": self.USER_KHACH})
		dn = self._dn()
		phieu = self._phieu_duy_nhat(dn)
		delivery_hook.on_delivery_note_submit(dn)
		delivery_hook.on_delivery_note_submit(frappe.get_doc("Delivery Note", dn.name))
		self.assertEqual(
			frappe.db.count(
				"Notification Log",
				{"for_user": self.USER_KHACH, "document_type": "Customer Stock Receipt", "document_name": phieu.name},
			),
			1,
		)

	def test_gui_thong_bao_hong_khong_chan_dn_va_khong_mat_phieu(self):
		"""QĐ nền 4 nguyên văn — ép RIÊNG bước gửi thông báo hỏng (không đụng
		bước tạo phiếu): DN vẫn submit, VÀ phiếu vừa tạo KHÔNG bị cuốn theo
		(hai lệnh `_chay_an_toan` savepoint riêng — xem chú thích)."""
		with unittest.mock.patch.object(
			delivery_hook, "_bao_da_nhap_hang", side_effect=RuntimeError("gửi thông báo hỏng có chủ ý")
		):
			dn = self._dn()
		self.assertEqual(dn.docstatus, 1, "DN PHẢI submit được dù thông báo hỏng")
		# Phiếu vẫn phải tồn tại — lỗi ở BƯỚC SAU (thông báo) không được cuốn
		# theo dữ liệu đã tạo ở BƯỚC TRƯỚC (savepoint riêng).
		phieu = self._phieu_duy_nhat(dn)
		self.assertEqual(phieu.docstatus, 0)

		log = frappe.get_all(
			"Error Log",
			filters={
				"reference_doctype": "Delivery Note", "reference_name": dn.name,
				"method": "Kho khách: lỗi khi gửi thông báo đã nhập hàng",
			},
		)
		self.assertEqual(len(log), 1)

	def test_khong_gui_thong_bao_cho_hang_tra_ve(self):
		frappe.db.delete("Notification Log", {"for_user": self.USER_KHACH})
		goc = self._dn(rows=[{"item_code": ITEM, "qty": 10, "rate": 95000}])
		self._phieu_duy_nhat(goc)
		truoc = frappe.db.count("Notification Log", {"for_user": self.USER_KHACH})
		self._dn(
			rows=[{"item_code": ITEM, "qty": -2, "rate": 95000}],
			is_return=True, return_against=goc.name,
		)
		self.assertEqual(
			frappe.db.count("Notification Log", {"for_user": self.USER_KHACH}), truoc,
			"Hàng trả về Miyano không tạo phiếu -> không có gì để báo",
		)

	# ------------------------------------------------------------------ tiện ích
	def _bundle(self, batches, qty):
		from erpnext.stock.doctype.serial_and_batch_bundle.test_serial_and_batch_bundle import (
			make_serial_batch_bundle,
		)

		return make_serial_batch_bundle({
			"item_code": ITEM_LO, "warehouse": KHO_MYN, "qty": qty,
			"batches": frappe._dict(batches), "voucher_type": "Delivery Note",
			"posting_date": frappe.utils.today(), "posting_time": frappe.utils.nowtime(),
			"type_of_transaction": "Outward", "company": COMPANY, "do_not_submit": True,
		}).name
