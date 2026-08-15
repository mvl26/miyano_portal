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

    def test_patch_bat_co_cho_khach_dang_tat(self):
        """Kiểm đúng thứ patch hứa — backfill khách hiện hữu — mà KHÔNG phán xét
        trạng thái nghiệp vụ của site.

        Bản trước assert "không Customer nào còn cờ 0", tức là cấm luôn điều
        spec §3.5 cho phép: sales tắt cờ cho một khách cụ thể (khách nợ quá
        hạn, chỉ cho mua theo hợp đồng). Test đó sẽ đỏ vào đúng ngày ai đó
        làm đúng điều spec cho phép.
        """
        from miyano_portal.patches.v1_15.bat_mua_le_mac_dinh import execute

        khach = frappe.db.get_value("Customer", {"disabled": 0}, "name")
        frappe.db.set_value("Customer", khach, "custom_cho_phep_mua_le", 0)

        execute()

        self.assertEqual(
            frappe.db.get_value("Customer", khach, "custom_cho_phep_mua_le"), 1,
            "patch phải bật cờ cho khách hiện hữu đang tắt",
        )
