"""Spec 2026-08-15 §3.6 — PDF báo giá.

Ba thứ được bảo vệ ở đây, theo thứ tự quan trọng: KHÔNG lộ đơn của khách
khác; KHÔNG lộ giá sales chưa gửi; và bản báo giá phải ĐỦ — thiếu dòng đặt
ngoài đã khớp mã là khách nhận báo giá thiếu đúng món họ lo nhất.
"""

import json

import frappe
from frappe.tests.utils import FrappeTestCase

from miyano_portal.api import portal
from miyano_portal.portal_mua_le import ITEM_GIU_CHO, TRANG_THAI_CHO_KHACH
from miyano_portal.tests.test_e6_mua_le import (
    BVBM, PXN, RETAIL_CO_GIA, USER_BVBM, USER_PXN, _rid, _seed_mua_le,
)

PRINT_FORMAT = "Miyano - Báo giá"


class TestBaoGiaPdf(FrappeTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        _seed_mua_le()

    def setUp(self):
        frappe.set_user(USER_BVBM)

    def tearDown(self):
        frappe.set_user("Administrator")

    def _don_cho_khach_dong_y(self):
        res = portal.portal_order_place(
            items=json.dumps([{"item_code": RETAIL_CO_GIA, "qty": 3}]),
            dat_ngoai=json.dumps([
                {"ten_hang": "Găng tay nitrile size M", "dvt": "Hộp", "so_luong": 5},
            ]),
            request_id=_rid(),
            mode="ban_le",
        )
        frappe.set_user("Administrator")
        so = frappe.get_doc("Sales Order", res["sales_order"])
        so.items[0].rate = 25000
        # Khớp mã cho dòng đặt ngoài — đúng thao tác sales làm khi báo giá.
        so.custom_dat_ngoai[0].item_khop = RETAIL_CO_GIA
        so.workflow_state = TRANG_THAI_CHO_KHACH
        so.save(ignore_permissions=True)
        frappe.set_user(USER_BVBM)
        return so.name

    def test_print_format_da_duoc_cai(self):
        self.assertTrue(frappe.db.exists("Print Format", PRINT_FORMAT))
        self.assertEqual(
            frappe.db.get_value("Print Format", PRINT_FORMAT, "doc_type"), "Sales Order"
        )

    def test_pdf_chua_dong_dat_ngoai_da_khop_ma(self):
        ten = self._don_cho_khach_dong_y()
        html = frappe.get_print(
            "Sales Order", ten, print_format=PRINT_FORMAT, no_letterhead=1
        )
        self.assertIn("Găng tay nitrile size M", html)

    def test_pdf_khong_chua_dong_giu_cho(self):
        res = portal.portal_order_place(
            items=json.dumps([]),
            dat_ngoai=json.dumps([{"ten_hang": "Dây truyền dịch", "dvt": "Cái", "so_luong": 20}]),
            request_id=_rid(),
            mode="ban_le",
        )
        frappe.set_user("Administrator")
        html = frappe.get_print(
            "Sales Order", res["sales_order"], print_format=PRINT_FORMAT, no_letterhead=1
        )
        self.assertNotIn(ITEM_GIU_CHO, html)

    def test_khach_khac_khong_tai_duoc(self):
        ten = self._don_cho_khach_dong_y()
        frappe.set_user(USER_PXN)
        with self.assertRaises(frappe.PermissionError):
            portal.portal_bao_gia_pdf(order=ten)

    def test_don_chua_gui_khach_thi_khong_tai_duoc(self):
        """Đơn còn ở "Chờ xác nhận" = sales chưa chốt giá. Cho tải là lộ
        giá nháp và biến một con số đang sửa thành cam kết với khách."""
        res = portal.portal_order_place(
            items=json.dumps([{"item_code": RETAIL_CO_GIA, "qty": 1}]),
            request_id=_rid(),
            mode="ban_le",
        )
        with self.assertRaises(frappe.ValidationError):
            portal.portal_bao_gia_pdf(order=res["sales_order"])
