"""Đợt bị từ chối hoặc hết hạn → dòng quay về phiếu gốc (spec 2026-10-15 §4.3)."""

import frappe
from frappe.model.workflow import apply_workflow
from frappe.utils import add_days, nowdate

from miyano_portal import bao_gia, bao_gia_theo_dot as dot
from miyano_portal.tests.nen_bao_gia import NenBaoGiaTheoDot


class TestTraDongVe(NenBaoGiaTheoDot):
	def setUp(self):
		super().setUp()
		self.ql = self._quan_ly("dottv.ql@demo.miyano", self.kh_a)

	def _tach(self, goc, *ma):
		goc.reload()
		ten = [d.name for d in goc.items if d.item_code in ma]
		return frappe.get_doc("Quotation", dot.tach_dot(goc.name, ten)["dot"])

	def _lui_han(self, dot_):
		# `transaction_date` lùi theo: ERPNext không cho `valid_till` trước ngày lập.
		frappe.db.set_value("Quotation", dot_.name, {
			"valid_till": add_days(nowdate(), -1),
			"transaction_date": add_days(nowdate(), -8),
		}, update_modified=False)

	def _khach_tu_choi(self, ten):
		frappe.set_user(self.ql)
		try:
			bao_gia.tu_choi(ten, "Giá cao")
		finally:
			frappe.set_user("Administrator")

	def test_khach_tu_choi_tra_dong_ve_giu_gia(self):
		goc = self._goc_ba_dong()
		d1 = self._tach(goc, self.item_ngoai)
		self._khach_tu_choi(d1.name)
		goc.reload()
		self.assertEqual(
			sorted((d.item_code, d.rate) for d in goc.items),
			sorted([(self.item_boi_so, 7000), (self.item_co_dau, 12000), (self.item_ngoai, 54000)]),
		)
		self.assertEqual(frappe.db.get_value("Quotation", d1.name, "custom_da_tra_ve"), 1)
		self.assertEqual(frappe.db.get_value("Quotation", d1.name, "workflow_state"), bao_gia.TT_KHACH_TU_CHOI)
		self.assertTrue(frappe.db.exists("Comment", {
			"reference_name": goc.name, "content": ["like", "%đã trả về 1 dòng%"],
		}))

	def test_miyano_tu_choi_dot_tra_dong_ve(self):
		goc = self._goc_ba_dong()
		d1 = self._tach(goc, self.item_ngoai)
		d1 = apply_workflow(d1, bao_gia.HD_THU_HOI)
		d1.custom_ly_do_tu_choi = "Nhà cung cấp báo hết hàng"
		d1.save()
		apply_workflow(d1, bao_gia.HD_TU_CHOI)
		goc.reload()
		self.assertIn(self.item_ngoai, [d.item_code for d in goc.items])

	def test_het_han_tra_dong_ve(self):
		goc = self._goc_ba_dong()
		d1 = self._tach(goc, self.item_ngoai)
		self._lui_han(d1)
		self.assertGreaterEqual(bao_gia.quet_het_han(), 1)
		goc.reload()
		self.assertIn(self.item_ngoai, [d.item_code for d in goc.items])
		self.assertEqual(frappe.db.get_value("Quotation", d1.name, "custom_da_tra_ve"), 1)

	def test_dong_tra_ve_mo_lai_phieu_da_bao_het(self):
		goc = self._goc_ba_dong()
		goc.reload()
		dot.tach_dot(goc.name, [d.name for d in goc.items if d.item_code == self.item_ngoai])
		d2 = self._tach(goc, self.item_boi_so, self.item_co_dau)
		goc.reload()
		self.assertEqual(goc.workflow_state, bao_gia.TT_DA_BAO_HET)
		self._khach_tu_choi(d2.name)
		goc.reload()
		self.assertEqual(goc.workflow_state, bao_gia.TT_CHO_MIYANO)
		self.assertEqual(sorted(d.item_code for d in goc.items), sorted([self.item_boi_so, self.item_co_dau]))

	def test_khong_gop_voi_dong_trung_ma(self):
		goc = self._goc_ba_dong()
		goc.append("items", {"item_code": self.item_ngoai, "qty": 3, "rate": 50000, "price_list_rate": 50000})
		goc.save()
		dau = [d for d in goc.items if d.item_code == self.item_ngoai][0]
		d1 = frappe.get_doc("Quotation", dot.tach_dot(goc.name, [dau.name])["dot"])
		self._khach_tu_choi(d1.name)
		goc.reload()
		self.assertEqual(len([d for d in goc.items if d.item_code == self.item_ngoai]), 2)

	def test_khong_tra_hai_lan_va_chan_mo_lai(self):
		goc = self._goc_ba_dong()
		d1 = self._tach(goc, self.item_ngoai)
		self._lui_han(d1)
		bao_gia.quet_het_han()
		bao_gia.quet_het_han()
		goc.reload()
		self.assertEqual(len([d for d in goc.items if d.item_code == self.item_ngoai]), 1)
		d1.reload()
		with self.assertRaisesRegex(frappe.ValidationError, "không mở lại được"):
			apply_workflow(d1, bao_gia.HD_MO_LAI)

	def test_dot_da_dong_y_khong_tra_ve(self):
		goc = self._goc_ba_dong()
		d1 = self._tach(goc, self.item_ngoai)
		frappe.set_user(self.ql)
		try:
			bao_gia.dong_y(d1.name)
		finally:
			frappe.set_user("Administrator")
		goc.reload()
		self.assertNotIn(self.item_ngoai, [d.item_code for d in goc.items])

	def test_email_het_han_noi_ro_dot_va_tra_ve(self):
		from unittest.mock import patch

		goc = self._goc_ba_dong(contact_email="khach.hh@demo.miyano")
		d1 = self._tach(goc, self.item_ngoai)
		self._lui_han(d1)
		with patch("frappe.sendmail") as gui:
			bao_gia.quet_het_han()
		thu = [c.kwargs for c in gui.call_args_list if c.kwargs["reference_name"] == d1.name]
		self.assertTrue(thu)
		self.assertIn("(đợt 1)", thu[0]["subject"])
		self.assertIn(f"đã trả về phiếu {goc.name}", thu[0]["message"])
		self.assertNotIn("gửi yêu cầu báo giá mới", thu[0]["message"])
