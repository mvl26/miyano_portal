import frappe
from frappe.tests.utils import FrappeTestCase
from miyano_portal.setup.uat_scenario import setup_uat, CUSTOMER, ITEMS, WAREHOUSE_NAME, OPENING_STOCK_QTY
from miyano_portal.portal_context import get_portal_customer


class TestUatScenario(FrappeTestCase):
    def test_setup_uat_is_idempotent_and_creates_full_scenario(self):
        first = setup_uat()
        second = setup_uat()  # second run must not raise / duplicate / re-submit

        # Same identifiers both times.
        self.assertEqual(first["customer"], second["customer"])
        self.assertEqual(first["contract"], second["contract"])
        self.assertEqual(first["warehouse"], second["warehouse"])

        # Customer
        self.assertTrue(frappe.db.exists("Customer", CUSTOMER))

        # Warehouse (verify actual resulting name, in case ERPNext suffixed it)
        warehouse = second["warehouse"]
        self.assertTrue(frappe.db.exists("Warehouse", warehouse))

        # Items
        for it in ITEMS:
            self.assertTrue(frappe.db.exists("Item", it["item_code"]))

        # Blanket Order (framework contract): submitted, with 3 items
        bo_name = second["contract"]
        bo = frappe.get_doc("Blanket Order", bo_name)
        self.assertEqual(bo.docstatus, 1)
        self.assertEqual(len(bo.items), len(ITEMS))

        # Stock: actual_qty >= 300 for each item in the warehouse
        for it in ITEMS:
            qty = frappe.db.get_value(
                "Bin", {"item_code": it["item_code"], "warehouse": warehouse}, "actual_qty"
            )
            self.assertGreaterEqual(qty or 0, OPENING_STOCK_QTY)

        # Portal user resolves to the customer.
        frappe.set_user(second["portal_user"])
        self.addCleanup(frappe.set_user, "Administrator")
        self.assertEqual(get_portal_customer(), CUSTOMER)
