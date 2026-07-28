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

        # Stock: setup_uat must have stocked the warehouse via a submitted opening
        # Material Receipt for each item. We deliberately do NOT assert a hard
        # actual_qty >= OPENING_STOCK_QTY here: setup_uat's opening stock entry is
        # idempotent (fires once, only while the warehouse has zero stock for these
        # items) and a real order-to-cash UAT flow may since have consumed some of
        # that opening stock via deliveries. Asserting against the live, mutable
        # Bin quantity would make this test brittle to legitimate stock consumption
        # that happens outside of setup_uat. Instead we prove setup_uat did its job
        # by asserting: (a) there is some stock at all, and (b) a submitted
        # Material Receipt Stock Entry actually created that opening stock.
        for it in ITEMS:
            qty = frappe.db.get_value(
                "Bin", {"item_code": it["item_code"], "warehouse": warehouse}, "actual_qty"
            )
            self.assertGreater(qty or 0, 0)

            opening_receipt_exists = frappe.db.sql(
                """
                select sed.name
                from `tabStock Entry Detail` sed
                inner join `tabStock Entry` se on se.name = sed.parent
                where se.docstatus = 1
                    and se.stock_entry_type = 'Material Receipt'
                    and sed.t_warehouse = %s
                    and sed.item_code = %s
                    and sed.qty = %s
                limit 1
                """,
                (warehouse, it["item_code"], OPENING_STOCK_QTY),
            )
            self.assertTrue(
                opening_receipt_exists,
                f"Expected a submitted opening Material Receipt of qty {OPENING_STOCK_QTY} "
                f"for {it['item_code']} into {warehouse}",
            )

        # Portal user resolves to the customer.
        frappe.set_user(second["portal_user"])
        self.addCleanup(frappe.set_user, "Administrator")
        self.assertEqual(get_portal_customer(), CUSTOMER)
