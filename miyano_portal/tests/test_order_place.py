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
        self.assertEqual(so.items[0].against_blanket_order, 1)

    def test_over_quota_rejected(self):
        with self.assertRaises(frappe.ValidationError):
            portal.portal_order_place(
                self.bo, json.dumps([{"item_code": "HC0009", "qty": 999999}]),
            )

    def test_duplicate_lines_aggregated_over_quota_rejected(self):
        # Remaining qty for HC0009 is 500; two lines of 300 each pass
        # individually but total 600 > 500, so the aggregated total must
        # be rejected.
        with self.assertRaises(frappe.ValidationError):
            portal.portal_order_place(
                self.bo,
                json.dumps([
                    {"item_code": "HC0009", "qty": 300},
                    {"item_code": "HC0009", "qty": 300},
                ]),
            )

    def test_migrated_item_without_default_warehouse_gets_delivery_warehouse(self):
        # Items migrated from SupplyCore (e.g. VTTH-GAUZE-5) have no Item
        # Default warehouse for the portal's company - only the demo-seeded
        # items (seed_demo.py) get one. Without a fix, the Sales Order would
        # be created with items[0].warehouse empty and ERPNext's
        # Sales Order.validate_warehouse() would raise WarehouseRequired.
        # Reproduce that condition with a fresh item that has no item_defaults
        # row at all, and assert the order still succeeds as a Draft with a
        # delivery warehouse resolved onto the Sales Order.
        item_code = "TEST-MIGRATED-NO-WAREHOUSE"
        if not frappe.db.exists("Item", item_code):
            frappe.get_doc({
                "doctype": "Item",
                "item_code": item_code,
                "item_name": "Test migrated item (no default warehouse)",
                "item_group": "All Item Groups",
                "stock_uom": "Cái",
                "is_stock_item": 1,
            }).insert(ignore_permissions=True)
        # ERPNext may auto-add an Item Default for the system's global
        # default company on Item insert, but never for the portal's own
        # company ("Miyano Việt Nam") - which is the exact real-world
        # condition (VTTH-GAUZE-5 only carries an Item Default for the
        # unrelated "Miyano" company).
        self.assertFalse(
            any(
                d.company == "Miyano Việt Nam" and d.default_warehouse
                for d in frappe.get_doc("Item", item_code).item_defaults
            )
        )

        customer = portal.portal_me()["customer"]
        price_list = frappe.db.get_value("Customer", customer, "default_price_list")
        if not frappe.db.exists(
            "Item Price", {"item_code": item_code, "price_list": price_list, "selling": 1}
        ):
            frappe.get_doc({
                "doctype": "Item Price",
                "item_code": item_code,
                "price_list": price_list,
                "uom": "Cái",
                "selling": 1,
                "price_list_rate": 5000,
                "currency": "VND",
            }).insert(ignore_permissions=True)

        # Give the item its own quota row directly on the Blanket Order Item
        # child table - the parent Blanket Order is already submitted, but a
        # standalone child-doctype insert bypasses that (it's just a row, not
        # a modification of the submitted document's own fields).
        frappe.get_doc({
            "doctype": "Blanket Order Item",
            "parenttype": "Blanket Order",
            "parentfield": "items",
            "parent": self.bo,
            "item_code": item_code,
            "qty": 10,
            "ordered_qty": 0,
            "rate": 5000,
            "uom": "Cái",
        }).insert(ignore_permissions=True)

        res = portal.portal_order_place(
            self.bo, json.dumps([{"item_code": item_code, "qty": 1}]),
        )
        so = frappe.get_doc("Sales Order", res["sales_order"])
        self.assertEqual(so.docstatus, 0)
        self.assertTrue(so.set_warehouse or so.items[0].warehouse)
