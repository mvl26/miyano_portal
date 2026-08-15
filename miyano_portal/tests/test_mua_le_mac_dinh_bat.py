"""Spec 2026-08-15 §3.5 — Mua lẻ mặc định BẬT.

Bỏ "Yêu cầu hàng hoá" khỏi cổng nghĩa là khách chưa bật cờ KHÔNG CÒN cách nào
đặt hàng ngoài hợp đồng khung. Đổi mặc định là điều kiện để việc gỡ ở Task 1-2
không cắt đường của ai.
"""

import frappe
from frappe.tests.utils import FrappeTestCase

TEN_KHACH_MOI = "Khách Test Mặc Định Mua Lẻ"


class TestMuaLeMacDinhBat(FrappeTestCase):
    def test_custom_field_co_default_bang_1(self):
        default = frappe.db.get_value(
            "Custom Field",
            {"dt": "Customer", "fieldname": "custom_cho_phep_mua_le"},
            "default",
        )
        self.assertEqual(str(default), "1", "đổi default là cốt lõi của §3.5")

    def test_khach_moi_tao_duoc_bat_san(self):
        if frappe.db.exists("Customer", TEN_KHACH_MOI):
            frappe.delete_doc("Customer", TEN_KHACH_MOI, force=True, ignore_permissions=True)
        kh = frappe.get_doc({
            "doctype": "Customer",
            "customer_name": TEN_KHACH_MOI,
            "customer_type": "Company",
        }).insert(ignore_permissions=True)
        self.assertTrue(kh.custom_cho_phep_mua_le, "khách mới phải mua lẻ được ngay")

    def test_khong_con_khach_nao_bi_tat(self):
        con_tat = frappe.get_all(
            "Customer",
            filters={"custom_cho_phep_mua_le": 0, "disabled": 0},
            pluck="name",
        )
        self.assertEqual(con_tat, [], f"patch chưa bật cho khách hiện hữu: {con_tat}")
