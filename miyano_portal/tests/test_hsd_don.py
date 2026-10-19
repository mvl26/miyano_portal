"""HSD tối thiểu trên Sales Order: kế thừa số tháng, tính kết quả, cảnh báo (spec 2026-10-19 §4.2)."""

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import getdate

from miyano_portal import han_dung_khach

COMPANY = "Miyano Việt Nam"
ITEM_LO = "_Test HSD Co Lo"
ITEM_KHONG_LO = "_Test HSD Khong Lo"
KHACH = "_Test HSD Khach"


def _tao_item(ma, co_lo):
	if not frappe.db.exists("Item", ma):
		frappe.get_doc(
			{
				"doctype": "Item",
				"item_code": ma,
				"item_name": ma,
				"item_group": "All Item Groups",
				"stock_uom": "Nos",
				"is_stock_item": 1,
				"has_batch_no": co_lo,
				"has_expiry_date": co_lo,
				"create_new_batch": 0,
			}
		).insert(ignore_permissions=True)


def _nhap_lo(item, kho, ma_lo, han, qty):
	frappe.get_doc(
		{"doctype": "Batch", "item": item, "batch_id": ma_lo, "expiry_date": han}
	).insert(ignore_permissions=True)
	se = frappe.get_doc(
		{
			"doctype": "Stock Entry",
			"stock_entry_type": "Material Receipt",
			"company": COMPANY,
			"items": [
				{"item_code": item, "qty": qty, "t_warehouse": kho, "basic_rate": 1000, "batch_no": ma_lo}
			],
		}
	)
	se.insert(ignore_permissions=True)
	se.submit()


class TestHsdDon(FrappeTestCase):
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
		_nhap_lo(ITEM_LO, cls.kho, "_TEST-HSD-A", "2027-01-30", 5)
		_nhap_lo(ITEM_LO, cls.kho, "_TEST-HSD-B", "2026-12-20", 10)

	def _so(self, hsd, dong, delivery_date="2026-10-15", submit=False, item=ITEM_LO, **kw):
		items = []
		for d in dong:
			row = {"item_code": item, "rate": 1000, "warehouse": self.kho, "delivery_date": delivery_date}
			row.update(d)
			items.append(row)
		so = frappe.get_doc(
			{
				"doctype": "Sales Order",
				"customer": KHACH,
				"company": COMPANY,
				"transaction_date": "2026-10-01",
				"delivery_date": delivery_date,
				"custom_hsd_toi_thieu_thang": hsd,
				"items": items,
				**kw,
			}
		)
		so.insert(ignore_permissions=True)
		if submit:
			so.submit()
		return so

	def test_dong_ke_thua_so_thang_dau_phieu(self):
		so = self._so(
			hsd=3,
			dong=[{"qty": 2}, {"qty": 2, "custom_hsd_toi_thieu_thang": 6}, {"qty": 1, "custom_hsd_toi_thieu_thang": 0}],
		)
		self.assertEqual([d.custom_hsd_toi_thieu_thang for d in so.items], [3, 6, 0])

	def test_dat_khi_du_ton_lo_dat(self):  # giao 2026-10-15, 3 tháng -> sàn 2027-01-15; lô 30/01 có 5
		so = self._so(hsd=3, dong=[{"qty": 5}], delivery_date="2026-10-15")
		d = so.items[0]
		self.assertEqual((d.custom_ket_qua_hsd, str(d.custom_hsd_yeu_cau_den)), ("Đạt", "2027-01-15"))

	def test_khong_dat_khi_lo_dat_khong_du(self):  # cần 6 > 5
		so = self._so(hsd=3, dong=[{"qty": 6}], delivery_date="2026-10-15")
		self.assertEqual(so.items[0].custom_ket_qua_hsd, "Không đạt")
		self.assertEqual(str(so.items[0].custom_hsd_ton_tot_nhat), "2027-01-30")

	def test_canh_bao_khong_chan_submit(self):
		so = self._so(hsd=12, dong=[{"qty": 1}], submit=True)
		self.assertEqual(so.docstatus, 1)
		self.assertEqual(so.items[0].custom_ket_qua_hsd, "Không đạt")

	def test_khong_ap_dung(self):
		so = self._so(hsd=0, dong=[{"qty": 1}])
		self.assertEqual(so.items[0].custom_ket_qua_hsd, "Không áp dụng")
		so = self._so(hsd=3, dong=[{"qty": 1}], item=ITEM_KHONG_LO)
		self.assertEqual(so.items[0].custom_ket_qua_hsd, "Không áp dụng")
		self.assertFalse(so.items[0].custom_hsd_yeu_cau_den)

	def test_so_thang_ngoai_khoang_bi_tu_choi(self):
		with self.assertRaises(frappe.ValidationError):
			self._so(hsd=61, dong=[{"qty": 1}])

	def test_ngoai_le_tren_nhap_bat_buoc_ly_do(self):
		with self.assertRaises(frappe.ValidationError):
			self._so(
				hsd=12,
				dong=[{"qty": 1, "custom_ngoai_le_hsd": 1, "custom_ngoai_le_hsd_den": "2026-12-20"}],
			)

	def test_ngoai_le_day_du_ghi_nguoi_va_dat(self):
		so = self._so(
			hsd=12,
			dong=[
				{
					"qty": 1,
					"custom_ngoai_le_hsd": 1,
					"custom_ngoai_le_hsd_den": "2026-12-20",
					"custom_ngoai_le_ly_do": "Khách đồng ý",
				}
			],
		)
		d = so.items[0]
		self.assertEqual(d.custom_ngoai_le_boi, "Administrator")
		self.assertTrue(d.custom_ngoai_le_luc)
		self.assertEqual(d.custom_ket_qua_hsd, "Đạt")

	def test_mot_msgprint_gom_cac_dong(self):
		frappe.clear_messages()
		self._so(hsd=12, dong=[{"qty": 1}, {"qty": 2}])
		msgs = [m for m in frappe.get_message_log() if "Không đáp ứng HSD" in str(m)]
		self.assertEqual(len(msgs), 1)
		self.assertIn("Dòng 1", str(msgs[0]))
		self.assertIn("Dòng 2", str(msgs[0]))

	def test_cau_canh_bao_dung_mau(self):
		dong = frappe._dict(
			idx=1, item_code="X", custom_hsd_toi_thieu_thang=3, custom_hsd_yeu_cau_den=getdate("2027-01-15"),
			custom_ngoai_le_hsd=0, custom_ngoai_le_hsd_den=None,
		)
		kq = {"dat": False, "hsd_tot_nhat": getdate("2026-12-30"), "ton_dat": 0}
		cau = han_dung_khach.cau_canh_bao(dong, kq, getdate("2026-10-15"))
		self.assertIn("Dòng 1 – X: Khách hàng yêu cầu hàng còn tối thiểu 03 tháng HSD (đến 15/01/2027).", cau)
		self.assertIn("Tồn kho tốt nhất HSD 30/12/2026, chỉ còn 02 tháng 15 ngày → Không đáp ứng (thiếu 16 ngày)", cau)
		self.assertIn("Vui lòng xác nhận với Khách hàng trước khi giao hàng.", cau)
		kq = {"dat": False, "hsd_tot_nhat": None, "ton_dat": 0}
		cau = han_dung_khach.cau_canh_bao(dong, kq, getdate("2026-10-15"))
		self.assertIn("Không còn tồn kho lô nào.", cau)
		dong.update(custom_ngoai_le_hsd=1, custom_ngoai_le_hsd_den=getdate("2026-12-20"))
		cau = han_dung_khach.cau_canh_bao(dong, kq, getdate("2026-10-15"))
		self.assertIn("Đã ghi ngoại lệ: khách chấp nhận đến 20/12/2026.", cau)

	def test_khach_cong_khong_nhan_canh_bao_noi_bo(self):
		"""Đơn lưu trong phiên khách cổng (Website User) — vd. đặt hàng trên cổng:
		vẫn tính kết quả nhưng KHÔNG msgprint câu tồn kho/HSD nội bộ."""
		import json

		web = "hsd_web_khach@example.com"
		if not frappe.db.exists("User", web):
			frappe.get_doc(
				{"doctype": "User", "email": web, "first_name": "hsd web", "send_welcome_email": 0,
				 "roles": [{"role": "Customer"}]}
			).insert(ignore_permissions=True)
		self.assertEqual(frappe.db.get_value("User", web, "user_type"), "Website User")
		try:
			frappe.set_user(web)
			frappe.clear_messages()
			so = self._so(hsd=12, dong=[{"qty": 1}])
			self.assertEqual(so.items[0].custom_ket_qua_hsd, "Không đạt")
			self.assertNotIn("HSD", json.dumps(frappe.local.message_log, ensure_ascii=False))
		finally:
			frappe.set_user("Administrator")
		# Người dùng nội bộ vẫn nhận cảnh báo.
		frappe.clear_messages()
		self._so(hsd=12, dong=[{"qty": 1}])
		self.assertIn("Không đáp ứng HSD", json.dumps(frappe.local.message_log, ensure_ascii=False))
