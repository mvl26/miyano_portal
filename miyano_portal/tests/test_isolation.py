import frappe
from frappe.tests.utils import FrappeTestCase
from miyano_portal.setup.seed_demo import seed_demo
from miyano_portal.permissions import (
    sales_query,
    delivery_query,
    invoice_query,
    blanket_query,
)


class TestIsolation(FrappeTestCase):
    def setUp(self):
        seed_demo()

    def _ensure_orphan_user(self):
        u = "orphan@demo.miyano"
        if not frappe.db.exists("User", u):
            usr = frappe.get_doc({
                "doctype": "User", "email": u, "first_name": "Orphan",
                "user_type": "Website User", "send_welcome_email": 0,
            })
            usr.insert(ignore_permissions=True)
        return u

    def test_query_condition_scopes_to_user_customer(self):
        cond = sales_query("bvbm@demo.miyano")
        self.assertIn("Bệnh viện Bạch Mai", cond)
        self.assertNotIn("PXN ABC", cond)

    def test_system_user_unrestricted(self):
        # System users (desk) are not constrained by this hook
        self.assertEqual(sales_query("Administrator"), "")

    def test_website_user_without_customer_is_blocked(self):
        # A Website User with no linked Customer must see nothing
        u = self._ensure_orphan_user()
        self.assertIn("1=0", sales_query(u))

    def test_delivery_query_scopes_to_user_customer(self):
        cond = delivery_query("bvbm@demo.miyano")
        self.assertIn("`tabDelivery Note`.`customer`", cond)
        self.assertIn("Bệnh viện Bạch Mai", cond)
        self.assertNotIn("PXN ABC", cond)

    def test_delivery_query_blocks_user_without_customer(self):
        u = self._ensure_orphan_user()
        self.assertIn("1=0", delivery_query(u))

    def test_invoice_query_scopes_to_user_customer(self):
        cond = invoice_query("bvbm@demo.miyano")
        self.assertIn("`tabSales Invoice`.`customer`", cond)
        self.assertIn("Bệnh viện Bạch Mai", cond)
        self.assertNotIn("PXN ABC", cond)

    def test_invoice_query_blocks_user_without_customer(self):
        u = self._ensure_orphan_user()
        self.assertIn("1=0", invoice_query(u))

    def test_blanket_query_scopes_to_user_customer(self):
        cond = blanket_query("bvbm@demo.miyano")
        self.assertIn("`tabBlanket Order`.`customer`", cond)
        self.assertIn("Bệnh viện Bạch Mai", cond)
        self.assertNotIn("PXN ABC", cond)

    def test_blanket_query_blocks_user_without_customer(self):
        u = self._ensure_orphan_user()
        self.assertIn("1=0", blanket_query(u))
