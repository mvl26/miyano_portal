import json
import frappe
from frappe.tests.utils import FrappeTestCase
from miyano_portal.setup.seed_demo import seed_demo
from miyano_portal.api import portal


class TestTracking(FrappeTestCase):
    def setUp(self):
        seed_demo()
        frappe.set_user("bvbm@demo.miyano")
        self.addCleanup(frappe.set_user, "Administrator")
        bo = portal.portal_contracts()[0]["name"]
        self.so = portal.portal_order_place(
            bo, json.dumps([{"item_code": "VT0005", "qty": 10}])
        )["sales_order"]

    def test_history_shows_order(self):
        names = {r["name"] for r in portal.portal_order_history()}
        self.assertIn(self.so, names)

    def test_track_has_milestones(self):
        t = portal.portal_order_track(self.so)
        self.assertEqual(t["status_vi"], "Chờ xác nhận")
        self.assertTrue(any(m["key"] == "ordered" and m["done"] for m in t["milestones"]))

    def test_cancel_request_on_draft(self):
        res = portal.portal_request_cancel(self.so, "Đặt nhầm")
        self.assertTrue(res["ok"])

    def test_cross_customer_cannot_track_or_cancel(self):
        frappe.set_user("pxnabc@demo.miyano")
        self.assertRaises(frappe.PermissionError, portal.portal_order_track, self.so)
        self.assertRaises(
            frappe.PermissionError, portal.portal_request_cancel, self.so, "x"
        )
