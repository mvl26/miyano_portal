import json
import frappe
from frappe.tests.utils import FrappeTestCase
from miyano_portal.setup.seed_demo import seed_demo
from miyano_portal.api import portal


class TestOrderPlace(FrappeTestCase):
    def setUp(self):
        seed_demo()
        frappe.set_user("bvbm@demo.miyano")
        self.addCleanup(frappe.set_user, "Administrator")
        self.bo = portal.portal_contracts()[0]["name"]

    def test_place_creates_draft_sales_order(self):
        res = portal.portal_order_place(
            self.bo, json.dumps([{"item_code": "VT0005", "qty": 100}]),
            po="PO-123", delivery_date="2026-08-01",
        )
        so = frappe.get_doc("Sales Order", res["sales_order"])
        self.assertEqual(so.docstatus, 0)
        self.assertEqual(so.custom_nguon_don, "Client Portal")
        self.assertEqual(so.custom_hdnt, self.bo)
        self.assertEqual(so.custom_so_po_khach, "PO-123")
        self.assertEqual(so.items[0].blanket_order, self.bo)

    def test_over_quota_rejected(self):
        with self.assertRaises(frappe.ValidationError):
            portal.portal_order_place(
                self.bo, json.dumps([{"item_code": "HC0009", "qty": 999999}]),
            )
