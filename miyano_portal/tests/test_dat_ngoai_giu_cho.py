"""Spec 2026-08-15 §3.4 — đơn mua lẻ TOÀN hàng chưa có mã.

ERPNext không lưu nổi Sales Order với `items` rỗng (đã kiểm thực nghiệm, ghi
ở api/portal.py:655). Item giữ chỗ `HANG-DAT-NGOAI` là lối ra — nhưng CHỈ khi
giỏ không còn mặt hàng thật nào: `resolve_ban_le_company()` GIAO tập company
của mọi mặt hàng trong giỏ, nên chèn vô điều kiện có thể làm RỖNG phép giao
và hỏng một đơn giỏ hỗn hợp vốn đang hợp lệ.
"""

import json

import frappe
from frappe.tests.utils import FrappeTestCase

from miyano_portal.api import portal
from miyano_portal.portal_mua_le import ITEM_GIU_CHO
from miyano_portal.tests.test_e6_mua_le import (
    BVBM, RETAIL_CO_GIA, USER_BVBM, _rid, _seed_mua_le,
)

DAT_NGOAI_MAU = [
    {"ten_hang": "Găng tay nitrile size M", "dvt": "Hộp", "so_luong": 5},
    {"ten_hang": "Dây truyền dịch", "dvt": "Cái", "so_luong": 20},
]


class TestDatNgoaiGiuCho(FrappeTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        _seed_mua_le()

    def setUp(self):
        frappe.set_user(USER_BVBM)
        frappe.db.set_value("Customer", BVBM, "custom_cho_phep_mua_le", 1)

    def tearDown(self):
        frappe.set_user("Administrator")

    def test_don_toan_hang_chua_co_ma_van_dat_duoc(self):
        res = portal.portal_order_place(
            items=json.dumps([]),
            dat_ngoai=json.dumps(DAT_NGOAI_MAU),
            request_id=_rid(),
            mode="ban_le",
        )
        so = frappe.get_doc("Sales Order", res["sales_order"])
        self.assertEqual(
            [i.item_code for i in so.items], [ITEM_GIU_CHO],
            "đơn toàn hàng lạ phải có đúng MỘT dòng giữ chỗ",
        )
        self.assertEqual(len(so.custom_dat_ngoai), 2)

    def test_gio_hon_hop_KHONG_chen_dong_giu_cho(self):
        res = portal.portal_order_place(
            items=json.dumps([{"item_code": RETAIL_CO_GIA, "qty": 2}]),
            dat_ngoai=json.dumps(DAT_NGOAI_MAU),
            request_id=_rid(),
            mode="ban_le",
        )
        so = frappe.get_doc("Sales Order", res["sales_order"])
        ma = [i.item_code for i in so.items]
        self.assertNotIn(
            ITEM_GIU_CHO, ma,
            "chèn giữ chỗ vào giỏ hỗn hợp sẽ thu hẹp resolve_ban_le_company()",
        )
        self.assertEqual(ma, [RETAIL_CO_GIA])

    def test_gio_rong_hoan_toan_van_bi_tu_choi(self):
        """Không hàng có mã, KHÔNG cả dòng đặt ngoài — không có nhu cầu nào
        để phục vụ, đơn rỗng là lỗi client chứ không phải tình huống nghiệp vụ."""
        with self.assertRaises(frappe.ValidationError):
            portal.portal_order_place(
                items=json.dumps([]),
                dat_ngoai=json.dumps([]),
                request_id=_rid(),
                mode="ban_le",
            )

    def test_khong_submit_duoc_khi_con_dong_chua_khop_ma(self):
        res = portal.portal_order_place(
            items=json.dumps([]),
            dat_ngoai=json.dumps(DAT_NGOAI_MAU),
            request_id=_rid(),
            mode="ban_le",
        )
        frappe.set_user("Administrator")
        so = frappe.get_doc("Sales Order", res["sales_order"])
        with self.assertRaises(frappe.ValidationError):
            so.submit()
