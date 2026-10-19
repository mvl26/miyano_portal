"""Phiếu giao: tự chốt lô đạt HSD khách yêu cầu và chặn duyệt lô không đạt (spec 2026-10-19 §4.4, §4.5)."""

from unittest.mock import patch

import frappe
from frappe.tests.utils import FrappeTestCase

from miyano_portal import han_dung_khach
from miyano_portal.han_dung_khach import (
	chot_lo_truoc_validate,
	ghi_ngoai_le,
	go_ngoai_le,
	han_toi_thieu_lo_xuat,
	kiem_phieu_giao,
)
from miyano_portal.tests.test_hsd_don import COMPANY, ITEM_KHONG_LO, KHACH, _tao_item

ITEM_PG = "_Test HSD PG Co Lo"
LO_A = "_TEST-PG-A"  # HSD 30/01/2027, tồn 5
LO_B = "_TEST-PG-B"  # HSD 20/12/2026, tồn 10


def _nhap(item, kho, qty, ma_lo=None, han=None):
	"""Nhập tồn ngày 01/10/2026 — trước ngày ghi sổ của các phiếu giao trong test."""
	if ma_lo and not frappe.db.exists("Batch", ma_lo):
		frappe.get_doc({"doctype": "Batch", "item": item, "batch_id": ma_lo, "expiry_date": han}).insert(
			ignore_permissions=True
		)
	dong = {"item_code": item, "qty": qty, "t_warehouse": kho, "basic_rate": 1000}
	if ma_lo:
		dong.update({"batch_no": ma_lo, "use_serial_batch_fields": 1})
	se = frappe.get_doc(
		{
			"doctype": "Stock Entry",
			"stock_entry_type": "Material Receipt",
			"company": COMPANY,
			"set_posting_time": 1,
			"posting_date": "2026-10-01",
			"posting_time": "08:00:00",
			"items": [dong],
		}
	)
	se.insert(ignore_permissions=True)
	se.submit()


class TestHsdPhieuGiao(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		from erpnext.warehouse_operations.tests.kho_thu import dam_bao_kho_khong_vi_tri

		frappe.set_user("Administrator")
		cls.kho = dam_bao_kho_khong_vi_tri()
		_tao_item(ITEM_PG, 1)
		_tao_item(ITEM_KHONG_LO, 0)
		if not frappe.db.exists("Customer", KHACH):
			frappe.get_doc(
				{"doctype": "Customer", "customer_name": KHACH, "customer_group": "All Customer Groups",
				 "territory": "All Territories"}
			).insert(ignore_permissions=True)
		_nhap(ITEM_PG, cls.kho, 5, LO_A, "2027-01-30")
		_nhap(ITEM_PG, cls.kho, 10, LO_B, "2026-12-20")
		_nhap(ITEM_KHONG_LO, cls.kho, 20)

	def setUp(self):
		frappe.set_user("Administrator")
		frappe.db.savepoint("hsd_phieu_giao")

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.rollback(save_point="hsd_phieu_giao")

	# ---- dựng dữ liệu ----

	def _so(self, hsd=3, dong=((4,),), item=ITEM_PG):
		items = [
			{"item_code": item, "qty": d[0], "rate": 1000, "warehouse": self.kho, "delivery_date": "2026-10-15"}
			for d in dong
		]
		so = frappe.get_doc(
			{
				"doctype": "Sales Order",
				"customer": KHACH,
				"company": COMPANY,
				"transaction_date": "2026-10-01",
				"delivery_date": "2026-10-15",
				"custom_hsd_toi_thieu_thang": hsd,
				"items": items,
			}
		)
		so.insert(ignore_permissions=True)
		so.submit()
		return so

	def _dn(self, so, lo=None, posting_date="2026-10-15", insert=True):
		from erpnext.selling.doctype.sales_order.sales_order import make_delivery_note

		dn = make_delivery_note(so.name)
		dn.set_posting_time = 1
		dn.posting_date = posting_date
		dn.posting_time = "10:00:00"
		for i, d in enumerate(dn.items):
			ma = lo[i] if isinstance(lo, (list, tuple)) else lo
			if ma:
				d.batch_no = ma
				d.use_serial_batch_fields = 1
		if insert:
			dn.insert(ignore_permissions=True)
		return dn

	def _lo_da_xuat(self, dn):
		"""Các lô thực xuất (theo bundle ERPNext sinh khi ghi sổ) của mọi dòng."""
		dn.reload()
		lo = set()
		for d in dn.items:
			if d.serial_and_batch_bundle:
				lo.update(
					frappe.get_all(
						"Serial and Batch Entry", filters={"parent": d.serial_and_batch_bundle}, pluck="batch_no"
					)
				)
			elif d.batch_no:
				lo.add(d.batch_no)
		return lo

	# ---- test ----

	def test_tu_chot_lo_dat(self):
		so = self._so()
		dn = self._dn(so)
		# Chốt ngay khi lưu nháp (before_validate), trước khi ERPNext tự điền lô B.
		self.assertEqual(dn.items[0].batch_no, LO_A)
		dn.submit()
		self.assertEqual(dn.items[0].batch_no, LO_A)
		self.assertEqual(frappe.db.get_value("Delivery Note Item", dn.items[0].name, "batch_no"), LO_A)
		self.assertEqual(self._lo_da_xuat(dn), {LO_A})

	def test_chan_lo_khong_dat(self):
		so = self._so()
		dn = self._dn(so, lo=LO_B)
		self.assertEqual(dn.items[0].batch_no, LO_B)  # lô người chọn không bao giờ bị đổi
		with self.assertRaises(frappe.ValidationError) as cm:
			dn.submit()
		tb = str(cm.exception)
		self.assertIn(f"lô {LO_B}", tb)
		self.assertNotIn("không có lô nào đạt", tb)  # lô A đủ: chỉ báo lô không đạt
		self.assertIn("thiếu 26 ngày", tb)
		self.assertIn(
			f"Dòng 1 – {ITEM_PG}, lô {LO_B}: Khách hàng yêu cầu hàng còn tối thiểu 03 tháng HSD (đến 15/01/2027). "
			"Lô này HSD 20/12/2026, chỉ còn 02 tháng 05 ngày → Không đáp ứng (thiếu 26 ngày). "
			f"Vui lòng xác nhận với Khách hàng và ghi ngoại lệ trên SO {so.name} trước khi giao.",
			tb,
		)
		self.assertEqual(frappe.db.get_value("Delivery Note", dn.name, "docstatus"), 0)

	def test_khong_lo_nao_du(self):
		so = self._so(dong=((6,),))
		dn = self._dn(so)
		with self.assertRaises(frappe.ValidationError) as cm:
			dn.submit()
		tb = str(cm.exception)
		self.assertIn("không có lô nào đạt", tb)
		self.assertIn(
			f"Dòng 1 – {ITEM_PG}: không có lô nào đạt HSD yêu cầu (đến 15/01/2027) đủ 6 Nos. "
			f"Lô đạt hiện có: {LO_A} (5) — tách dòng theo lô, hoặc ghi ngoại lệ trên SO {so.name}.",
			tb,
		)
		# Nháp vẫn lưu được; ERPNext tự điền lô B (không đạt) → chốt duyệt báo cả hai câu.
		self.assertEqual(dn.items[0].batch_no, LO_B)
		self.assertIn(f"lô {LO_B}", tb)

	def test_hai_dong_cung_hang(self):
		so = self._so(dong=((4,), (4,)))
		dn = self._dn(so)
		with self.assertRaises(frappe.ValidationError) as cm:
			dn.submit()
		tb = str(cm.exception)
		self.assertIn(f"Dòng 2 – {ITEM_PG}: không có lô nào đạt", tb)
		self.assertIn(f"Lô đạt hiện có: {LO_A} (1)", tb)
		self.assertNotIn("Dòng 1", tb)
		self.assertEqual(dn.items[0].batch_no, LO_A)
		self.assertNotEqual(dn.items[1].batch_no, LO_A)  # không chốt A lần hai
		self.assertEqual(dn.items[1].batch_no, LO_B)  # ERPNext tự điền

	def test_ngoai_le_mo_den_san(self):
		so = self._so()
		ghi_ngoai_le(so.name, so.items[0].name, "2026-12-20", "ĐT khách")
		dn = self._dn(so, lo=LO_B)
		dn.submit()
		self.assertEqual(dn.docstatus, 1)

		so2 = self._so()
		ghi_ngoai_le(so2.name, so2.items[0].name, "2026-12-25", "ĐT khách")
		dn2 = self._dn(so2, lo=LO_B)
		with self.assertRaises(frappe.ValidationError) as cm:
			dn2.submit()
		tb = str(cm.exception)
		self.assertIn("(khách chấp nhận đến 25/12/2026)", tb)
		self.assertIn("thiếu 5 ngày", tb)

	def test_go_ngoai_le_sau_khi_lap_nhap(self):
		so = self._so()
		ghi_ngoai_le(so.name, so.items[0].name, "2026-12-20", "ĐT khách")
		dn = self._dn(so, lo=LO_B)
		go_ngoai_le(so.name, so.items[0].name, "Khách đổi ý")
		with self.assertRaises(frappe.ValidationError) as cm:
			dn.submit()
		self.assertIn("thiếu 26 ngày", str(cm.exception))

	def test_giao_tre_dung_posting_date(self):
		so = self._so()
		dn = self._dn(so, lo=LO_A, posting_date="2026-11-01")
		self.assertEqual(str(han_toi_thieu_lo_xuat(dn, dn.items[0])), "2027-02-01")
		with self.assertRaises(frappe.ValidationError) as cm:
			dn.submit()
		tb = str(cm.exception)
		self.assertIn(f"lô {LO_A}", tb)
		self.assertIn("(đến 01/02/2027)", tb)
		self.assertIn("thiếu 2 ngày", tb)

	def test_doi_ngay_giao_tren_so(self):
		so = self._so()
		dn = self._dn(so)
		self.assertEqual(dn.items[0].batch_no, LO_A)
		frappe.db.set_value("Sales Order Item", so.items[0].name, "delivery_date", "2026-11-01")
		self.assertEqual(str(han_toi_thieu_lo_xuat(dn, dn.items[0])), "2027-02-01")
		with self.assertRaises(frappe.ValidationError) as cm:
			dn.submit()
		tb = str(cm.exception)
		self.assertIn(f"lô {LO_A}: Khách hàng yêu cầu hàng còn tối thiểu 03 tháng HSD (đến 01/02/2027)", tb)
		self.assertIn("không có lô nào đạt HSD yêu cầu (đến 01/02/2027)", tb)
		self.assertIn("Không còn lô nào đạt.", tb)

	def test_bo_qua(self):
		# Phiếu trả hàng
		so = self._so()
		dn = self._dn(so, lo=LO_B, insert=False)
		dn.is_return = 1
		self.assertIsNone(han_toi_thieu_lo_xuat(dn, dn.items[0]))
		kiem_phieu_giao(dn)
		self.assertEqual(dn.items[0].batch_no, LO_B)
		dn.items[0].batch_no = None
		chot_lo_truoc_validate(dn)
		self.assertFalse(dn.items[0].batch_no)

		# Dòng không lập từ SO
		dn = self._dn(so, lo=LO_B, insert=False)
		dn.items[0].so_detail = None
		self.assertIsNone(han_toi_thieu_lo_xuat(dn, dn.items[0]))
		kiem_phieu_giao(dn)
		self.assertEqual(dn.items[0].batch_no, LO_B)
		dn.items[0].batch_no = None
		chot_lo_truoc_validate(dn)
		self.assertFalse(dn.items[0].batch_no)

		# SO không yêu cầu HSD
		so0 = self._so(hsd=0)
		dn = self._dn(so0, lo=LO_B)
		self.assertIsNone(han_toi_thieu_lo_xuat(dn, dn.items[0]))
		dn.submit()
		self.assertEqual(self._lo_da_xuat(dn), {LO_B})

		# Mặt hàng không quản lý lô
		so_kl = self._so(item=ITEM_KHONG_LO)
		dn = self._dn(so_kl)
		self.assertIsNone(han_toi_thieu_lo_xuat(dn, dn.items[0]))
		dn.submit()
		self.assertFalse(dn.items[0].batch_no)

	def test_bat_bien_khong_yeu_cau(self):
		so = self._so(hsd=0)
		# Phiếu chưa lưu, dòng trống: hai hook không gán lô, không hỏi tồn.
		dn = self._dn(so, insert=False)
		with patch("erpnext.stock.doctype.batch.batch.get_batch_qty") as goi_ton:
			chot_lo_truoc_validate(dn)
			kiem_phieu_giao(dn)
		goi_ton.assert_not_called()
		self.assertFalse(dn.items[0].batch_no)
		self.assertFalse(dn.items[0].serial_and_batch_bundle)
		# Lưu: ERPNext tự chọn như cũ (Stock Settings theo HSD) → lô B hết hạn sớm hơn;
		# hai hook để nguyên lựa chọn đó.
		dn.insert(ignore_permissions=True)
		self.assertEqual(dn.items[0].batch_no, LO_B)
		with patch("erpnext.stock.doctype.batch.batch.get_batch_qty") as goi_ton:
			chot_lo_truoc_validate(dn)
			kiem_phieu_giao(dn)
		goi_ton.assert_not_called()
		self.assertEqual(dn.items[0].batch_no, LO_B)
		dn.submit()
		self.assertEqual(self._lo_da_xuat(dn), {LO_B})

	def test_hook_dang_ky(self):
		hooks = frappe.get_hooks("doc_events")["Delivery Note"]["before_submit"]
		self.assertIn("miyano_portal.han_dung_khach.kiem_phieu_giao", hooks)
		self.assertLess(
			hooks.index("miyano_portal.portal_thoi_gian_giao.dien_thoi_gian_giao"),
			hooks.index("miyano_portal.han_dung_khach.kiem_phieu_giao"),
		)
		self.assertEqual(
			frappe.get_hooks("doc_events")["Delivery Note"]["before_validate"],
			["miyano_portal.han_dung_khach.chot_lo_truoc_validate"],
		)
		self.assertTrue(callable(han_dung_khach.kiem_phieu_giao))
