"""Logic thuần của HSD tối thiểu theo yêu cầu khách hàng (spec 2026-10-19)."""

import frappe
from frappe.tests.utils import FrappeTestCase
from frappe.utils import getdate

from miyano_portal.han_dung_khach import (
	danh_gia_lo,
	hsd_yeu_cau_den,
	kiem_so_thang,
	mo_ta_chenh_lech,
	san_cho_phep,
)


class TestHsdLogic(FrappeTestCase):
	def test_cong_thang(self):
		self.assertEqual(hsd_yeu_cau_den("2026-10-15", 3), getdate("2027-01-15"))
		self.assertEqual(hsd_yeu_cau_den("2027-01-31", 1), getdate("2027-02-28"))
		self.assertEqual(hsd_yeu_cau_den("2028-01-31", 1), getdate("2028-02-29"))
		self.assertIsNone(hsd_yeu_cau_den("2026-10-15", 0))
		self.assertIsNone(hsd_yeu_cau_den("2026-10-15", None))

	def test_bien_danh_gia_lo(self):
		self.assertTrue(danh_gia_lo("2027-01-15", getdate("2027-01-15")))
		self.assertFalse(danh_gia_lo("2027-01-14", getdate("2027-01-15")))
		self.assertFalse(danh_gia_lo(None, getdate("2027-01-15")))
		self.assertTrue(danh_gia_lo(None, None))  # không yêu cầu

	def test_san_ap_ngoai_le(self):
		d = frappe._dict(custom_hsd_toi_thieu_thang=3, custom_ngoai_le_hsd=0, custom_ngoai_le_hsd_den=None)
		self.assertEqual(san_cho_phep(d, "2026-10-15"), getdate("2027-01-15"))
		d.update(custom_ngoai_le_hsd=1, custom_ngoai_le_hsd_den="2026-12-30")
		self.assertEqual(san_cho_phep(d, "2026-10-15"), getdate("2026-12-30"))
		self.assertIsNone(san_cho_phep(frappe._dict(custom_hsd_toi_thieu_thang=0), "2026-10-15"))

	def test_mo_ta_chenh_lech_vi_du_tai_lieu(self):
		kq = mo_ta_chenh_lech(getdate("2027-01-15"), getdate("2026-12-30"), getdate("2026-10-15"))
		self.assertEqual(kq, {"con_lai": "02 tháng 15 ngày", "thieu_ngay": 16})
		kq = mo_ta_chenh_lech(getdate("2027-01-15"), getdate("2026-10-01"), getdate("2026-10-15"))
		self.assertEqual(kq["con_lai"], "đã hết hạn")
		kq = mo_ta_chenh_lech(getdate("2027-01-15"), getdate("2027-01-15"), getdate("2026-10-15"))
		self.assertEqual(kq, {"con_lai": "03 tháng", "thieu_ngay": 0})

	def test_kiem_so_thang(self):
		self.assertEqual(kiem_so_thang(None), 0)
		self.assertEqual(kiem_so_thang("3"), 3)
		for xau in (-1, 61, "abc", 2.5):
			with self.assertRaises(frappe.ValidationError):
				kiem_so_thang(xau)

	def test_patch_chay_lai_duoc_va_tao_truong(self):
		from miyano_portal.patches.v1_46 import hsd_toi_thieu

		hsd_toi_thieu.execute()
		hsd_toi_thieu.execute()
		for f in ("custom_hsd_toi_thieu_thang", "custom_ngoai_le_hsd_den", "custom_ket_qua_hsd"):
			self.assertTrue(frappe.get_meta("Sales Order Item").has_field(f))
		self.assertTrue(frappe.get_meta("Sales Order").has_field("custom_hsd_toi_thieu_thang"))
		self.assertTrue(frappe.get_meta("Sales Order Item").get_field("custom_ngoai_le_hsd").allow_on_submit)
		self.assertTrue(frappe.get_meta("Portal De Xuat Mua Item").has_field("hsd_toi_thieu_thang"))
