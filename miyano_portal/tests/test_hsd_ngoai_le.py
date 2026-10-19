"""Ghi/gỡ ngoại lệ HSD trên Sales Order đã duyệt (spec 2026-10-19 §4.3)."""

import frappe
from frappe.tests.utils import FrappeTestCase

from miyano_portal.han_dung_khach import VAI_TRO_NGOAI_LE, ghi_ngoai_le, go_ngoai_le
from miyano_portal.tests.test_hsd_don import COMPANY, ITEM_KHONG_LO, ITEM_LO, KHACH, _nhap_lo, _tao_item

USER_STOCK = "hsd_stock_user@example.com"
USER_SALES = "hsd_sales_user@example.com"
USER_CONG = "hsd_khach_cong@example.com"


def _tao_user(email, vai_tro):
	if frappe.db.exists("User", email):
		frappe.delete_doc("User", email, force=True, ignore_permissions=True)
	frappe.get_doc(
		{
			"doctype": "User",
			"email": email,
			"first_name": email.split("@")[0],
			"send_welcome_email": 0,
			"enabled": 1,
			"roles": [{"role": r} for r in vai_tro],
		}
	).insert(ignore_permissions=True)


class TestHsdNgoaiLe(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		from erpnext.warehouse_operations.tests.kho_thu import dam_bao_kho_khong_vi_tri

		frappe.set_user("Administrator")
		cls.kho = dam_bao_kho_khong_vi_tri()
		_tao_item(ITEM_LO, 1)
		_tao_item(ITEM_KHONG_LO, 0)
		if not frappe.db.exists("Customer", KHACH):
			frappe.get_doc(
				{"doctype": "Customer", "customer_name": KHACH, "customer_group": "All Customer Groups",
				 "territory": "All Territories"}
			).insert(ignore_permissions=True)
		if not frappe.db.exists("Batch", "_TEST-NL-A"):
			_nhap_lo(ITEM_LO, cls.kho, "_TEST-NL-A", "2027-01-30", 5)
		_tao_user(USER_STOCK, ["Stock User"])
		_tao_user(USER_SALES, ["Sales User"])
		_tao_user(USER_CONG, ["Customer"])

	def tearDown(self):
		frappe.set_user("Administrator")

	def _so(self, submit=True, hsd=12, item=ITEM_LO):
		frappe.set_user("Administrator")
		so = frappe.get_doc(
			{
				"doctype": "Sales Order",
				"customer": KHACH,
				"company": COMPANY,
				"transaction_date": "2026-10-01",
				"delivery_date": "2026-10-15",
				"custom_hsd_toi_thieu_thang": hsd,
				"items": [
					{"item_code": item, "qty": 1, "rate": 1000, "warehouse": self.kho, "delivery_date": "2026-10-15"}
				],
			}
		)
		so.insert(ignore_permissions=True)
		if submit:
			so.submit()
		return so

	def _comments(self, so):
		return frappe.get_all(
			"Comment",
			filters={"reference_doctype": "Sales Order", "reference_name": so.name, "comment_type": "Comment"},
			pluck="content",
		)

	def test_vai_tro(self):
		self.assertEqual(VAI_TRO_NGOAI_LE, {"Sales User", "Sales Manager", "System Manager"})

	def test_sales_user_ghi_duoc_va_co_comment(self):
		so = self._so()
		d = so.items[0]
		frappe.set_user(USER_SALES)
		kq = ghi_ngoai_le(so.name, d.name, "2026-12-20", "ĐT khách")
		self.assertEqual(
			kq, {"dong": d.name, "custom_ngoai_le_hsd_den": "2026-12-20", "custom_ngoai_le_boi": USER_SALES}
		)
		frappe.set_user("Administrator")
		v = frappe.db.get_value(
			"Sales Order Item", d.name,
			["custom_ngoai_le_hsd", "custom_ngoai_le_hsd_den", "custom_ngoai_le_ly_do", "custom_ngoai_le_boi", "custom_ngoai_le_luc"],
			as_dict=True,
		)
		self.assertEqual(v.custom_ngoai_le_hsd, 1)
		self.assertEqual(str(v.custom_ngoai_le_hsd_den), "2026-12-20")
		self.assertEqual(v.custom_ngoai_le_ly_do, "ĐT khách")
		self.assertEqual(v.custom_ngoai_le_boi, USER_SALES)
		self.assertTrue(v.custom_ngoai_le_luc)
		self.assertTrue(
			any(
				c.startswith(f"Ghi ngoại lệ HSD dòng 1 ({ITEM_LO}): khách chấp nhận đến 20/12/2026 — ĐT khách")
				for c in self._comments(so)
			)
		)

	def test_stock_user_va_khach_cong_bi_tu_choi(self):
		so = self._so()
		d = so.items[0]
		for user in (USER_STOCK, USER_CONG):
			frappe.set_user(user)
			with self.assertRaises(frappe.PermissionError):
				ghi_ngoai_le(so.name, d.name, "2026-12-20", "ĐT khách")
			with self.assertRaises(frappe.PermissionError):
				go_ngoai_le(so.name, d.name, "Nhầm")
		frappe.set_user("Administrator")
		self.assertFalse(frappe.db.get_value("Sales Order Item", d.name, "custom_ngoai_le_hsd"))

	def test_so_nhap_hoac_dong_bi_tu_choi(self):
		nhap = self._so(submit=False)
		with self.assertRaises(frappe.ValidationError):
			ghi_ngoai_le(nhap.name, nhap.items[0].name, "2026-12-20", "ĐT khách")
		so = self._so()
		frappe.db.set_value("Sales Order", so.name, "status", "Closed")
		with self.assertRaises(frappe.ValidationError):
			ghi_ngoai_le(so.name, so.items[0].name, "2026-12-20", "ĐT khách")

	def test_dong_khong_ap_dung_bi_tu_choi(self):
		so = self._so(hsd=0)
		with self.assertRaises(frappe.ValidationError):
			ghi_ngoai_le(so.name, so.items[0].name, "2026-12-20", "ĐT khách")

	def test_thieu_ly_do_hoac_ngay_bi_tu_choi(self):
		so = self._so()
		d = so.items[0]
		with self.assertRaises(frappe.ValidationError):
			ghi_ngoai_le(so.name, d.name, "2026-12-20", "  ")
		with self.assertRaises(frappe.ValidationError):
			ghi_ngoai_le(so.name, d.name, "", "ĐT khách")
		with self.assertRaises(frappe.ValidationError):
			go_ngoai_le(so.name, d.name, "")

	def test_go_ngoai_le(self):
		so = self._so()
		d = so.items[0]
		ghi_ngoai_le(so.name, d.name, "2026-12-20", "ĐT khách")
		go_ngoai_le(so.name, d.name, "Khách đổi ý")
		v = frappe.db.get_value(
			"Sales Order Item", d.name,
			["custom_ngoai_le_hsd", "custom_ngoai_le_hsd_den", "custom_ngoai_le_ly_do"],
			as_dict=True,
		)
		self.assertEqual(v.custom_ngoai_le_hsd, 0)
		self.assertIsNone(v.custom_ngoai_le_hsd_den)
		self.assertEqual(v.custom_ngoai_le_ly_do, "Khách đổi ý")
		self.assertTrue(
			any(c.startswith(f"Gỡ ngoại lệ HSD dòng 1 ({ITEM_LO}) — Khách đổi ý") for c in self._comments(so))
		)

	def test_dong_khong_thuoc_don_bi_tu_choi(self):
		so1, so2 = self._so(), self._so()
		with self.assertRaises(frappe.ValidationError):
			ghi_ngoai_le(so1.name, so2.items[0].name, "2026-12-20", "ĐT khách")
		with self.assertRaises(frappe.ValidationError):
			ghi_ngoai_le(so1.name, "khong-ton-tai", "2026-12-20", "ĐT khách")
