"""Mẫu "PHIẾU ĐẶT HÀNG" (bản mẫu `docs/03_MVL_Phieu-dat-hang(SO).doc`) — thứ
khách nhận khi bấm "⬇ PDF đơn hàng" trên cổng (`portal_document_download`
→ Print Format "Miyano - Xác nhận đơn hàng").
"""

import json
import re

import frappe
from frappe.tests.utils import FrappeTestCase

from miyano_portal.api import portal
from miyano_portal.portal_mua_le import ITEM_GIU_CHO
from miyano_portal.setup.install_print_formats import HTML, NAME
from miyano_portal.tests.test_e6_mua_le import (
	BVBM, RETAIL_CO_GIA, USER_BVBM, _rid, _seed_mua_le,
)


def _stt(html):
	return re.findall(r'<td style="text-align:center">(\d+)</td>', html)


class TestMauPhieuDatHang(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		_seed_mua_le()

	def setUp(self):
		frappe.set_user(USER_BVBM)
		frappe.db.set_value("Customer", BVBM, "custom_cho_phep_mua_le", 1)
		res = portal.portal_order_place(
			items=json.dumps([{"item_code": RETAIL_CO_GIA, "qty": 1234}]),
			dat_ngoai=json.dumps([]),
			request_id=_rid(),
			mode="ban_le",
			note="Giao trước 9 giờ sáng",
		)
		frappe.set_user("Administrator")
		# Đơn mua lẻ ra cổng với đơn giá 0 (chờ sales báo giá) — gán giá để
		# có số tiền nhiều chữ số mà kiểm dấu phân nhóm.
		so = frappe.get_doc("Sales Order", res["sales_order"])
		so.items[0].rate = 1500
		so.save()
		self.so = so

	def tearDown(self):
		frappe.set_user("Administrator")

	def test_ban_ghi_tren_site_la_mau_moi(self):
		"""Installer bỏ qua mẫu đã có — patch v1_35 phải đưa HTML mới vào."""
		self.assertEqual(frappe.db.get_value("Print Format", NAME, "html"), HTML)

	def test_in_theo_bo_cuc_ban_mau(self):
		html = frappe.get_print("Sales Order", self.so.name, print_format=NAME, no_letterhead=1)
		self.assertIn("PHIẾU ĐẶT HÀNG", html)
		self.assertIn(self.so.name, html)
		self.assertIn((self.so.customer_name or self.so.customer).upper(), html)
		self.assertIn("Tổng số tiền (viết bằng chữ)", html)
		self.assertIn("Giao trước 9 giờ sáng", html)
		self.assertIn("Người lập phiếu/Đại diện Đơn vị mua", html)
		# Số lượng 1234 → thành tiền có dấu chấm phân nhóm, không dấu phẩy.
		tien = "{:,.0f}".format(self.so.total)
		self.assertIn(tien.replace(",", "."), html)
		self.assertNotIn(tien, html)

	def test_nguoi_dat_la_ho_ten_khong_phai_khoa_contact(self):
		if not self.so.contact_person:
			self.skipTest("user cổng của seed không gắn Contact")
		html = frappe.get_print("Sales Order", self.so.name, print_format=NAME, no_letterhead=1)
		ho_ten = frappe.db.get_value("Contact", self.so.contact_person, "full_name")
		self.assertIn(ho_ten, html)
		if ho_ten != self.so.contact_person:
			self.assertNotIn(self.so.contact_person, html)

	def test_dong_giu_cho_bi_loc_va_stt_khong_nhay_so(self):
		"""Dòng giữ chỗ nằm GIỮA hai dòng thật: STT phải là 1, 2 — không 1, 3."""
		so = self.so
		that = so.items[0].as_dict()
		so.items = []
		so.append("items", that)
		so.append("items", {"item_code": ITEM_GIU_CHO, "item_name": ITEM_GIU_CHO, "qty": 1})
		so.append("items", that)
		html = frappe.render_template(HTML, {"doc": so})
		self.assertNotIn(ITEM_GIU_CHO, html)
		self.assertEqual(_stt(html), ["1", "2"])
