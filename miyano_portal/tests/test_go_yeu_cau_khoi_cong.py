"""Spec 2026-08-15 §3.2 — "Yêu cầu hàng hoá" bị gỡ khỏi CỔNG, GIỮ cho Desk.

Hai nửa của một quyết định, nên nằm chung một file: nếu ai đó "dọn dẹp" nốt
doctype thì nửa dưới đỏ ngay, thay vì mất im lặng khả năng theo dõi nhu cầu
của back-office.
"""

import frappe
from frappe.tests.utils import FrappeTestCase

from miyano_portal.api import portal

ENDPOINT_DA_GO = [
    "portal_yeu_cau_list",
    "portal_yeu_cau_detail",
    "portal_yeu_cau_save",
    "portal_yeu_cau_cancel",
    "portal_yeu_cau_tra_loi",
    "portal_yeu_cau_file",
]


class TestGoYeuCauKhoiCong(FrappeTestCase):
    def test_khong_con_endpoint_yeu_cau_tren_cong(self):
        con_sot = [ten for ten in ENDPOINT_DA_GO if hasattr(portal, ten)]
        self.assertEqual(
            con_sot, [],
            f"còn endpoint cổng chưa gỡ: {con_sot} — khách vẫn gọi được",
        )

    def test_doctype_van_con_cho_desk(self):
        """Cơ sở của quyết định "giữ cho Desk" — xoá doctype là đổi quyết
        định, không phải dọn dẹp."""
        self.assertTrue(
            frappe.db.exists("DocType", "Portal Item Request"),
            "doctype bị xoá — back-office mất công cụ theo dõi nhu cầu",
        )

    def test_nhan_vien_desk_van_co_quyen(self):
        perms = frappe.get_meta("Portal Item Request").permissions
        roles = {p.role for p in perms if p.read}
        for role in ("Sales Manager", "Sales User", "Purchase User"):
            self.assertIn(role, roles, f"{role} mất quyền đọc trên Desk")
