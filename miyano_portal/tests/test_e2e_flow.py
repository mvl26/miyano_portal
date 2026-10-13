import json
import frappe
from frappe.tests.utils import FrappeTestCase
from miyano_portal.setup.seed_demo import seed_demo
from miyano_portal.api import portal
from miyano_portal.tests.fixtures_hop_dong import hop_dong_hieu_luc_dau_tien


class TestE2EFlow(FrappeTestCase):
    def test_full_happy_path(self):
        seed_demo()
        frappe.set_user("bvbm@demo.miyano")
        self.addCleanup(frappe.set_user, "Administrator")
        bo = hop_dong_hieu_luc_dau_tien()
        # Danh mục theo hợp đồng (`portal_catalog`) đã gỡ (spec 2026-10-09 §7);
        # khách tìm hàng qua danh mục gộp.
        cat = portal.portal_catalog_gop(tu_khoa="VT0005")["rows"]
        self.assertIn("VT0005", {r["item_code"] for r in cat})
        res = portal.portal_order_place(
            bo,
            json.dumps([{"item_code": "VT0005", "qty": 50}]),
            po="PO-E2E",
            request_id=frappe.generate_hash(length=12),
        )
        so = res["sales_order"]
        track = portal.portal_order_track(so)
        self.assertEqual(track["status_vi"], "Chờ xác nhận")
        # isolation: the other customer cannot see this order
        frappe.set_user("pxnabc@demo.miyano")
        self.assertNotIn(so, {r["name"] for r in portal.portal_order_history()["rows"]})
