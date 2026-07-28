import json
import frappe
from frappe.tests.utils import FrappeTestCase
from miyano_portal.setup.seed_demo import seed_demo
from miyano_portal.api import portal


class TestE2EFlow(FrappeTestCase):
    def test_full_happy_path(self):
        seed_demo()
        frappe.set_user("bvbm@demo.miyano")
        self.addCleanup(frappe.set_user, "Administrator")
        bo = portal.portal_contracts()[0]["name"]
        cat = portal.portal_catalog(bo)
        self.assertTrue(cat)
        res = portal.portal_order_place(
            bo, json.dumps([{"item_code": "VT0005", "qty": 50}]), po="PO-E2E")
        so = res["sales_order"]
        track = portal.portal_order_track(so)
        self.assertEqual(track["status_vi"], "Chờ xác nhận")
        # isolation: the other customer cannot see this order
        frappe.set_user("pxnabc@demo.miyano")
        self.assertNotIn(so, {r["name"] for r in portal.portal_order_history()})
