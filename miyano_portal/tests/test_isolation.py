import frappe
from frappe.tests.utils import FrappeTestCase
from miyano_portal.setup.seed_demo import seed_demo
from miyano_portal.permissions import sales_query


class TestIsolation(FrappeTestCase):
    def setUp(self):
        seed_demo()

    def test_query_condition_scopes_to_user_customer(self):
        cond = sales_query("bvbm@demo.miyano")
        self.assertIn("Bệnh viện Bạch Mai", cond)
        self.assertNotIn("PXN ABC", cond)

    def test_system_user_unrestricted(self):
        # System users (desk) are not constrained by this hook
        self.assertEqual(sales_query("Administrator"), "")

    def test_website_user_without_customer_is_blocked(self):
        # A Website User with no linked Customer must see nothing
        u = "orphan@demo.miyano"
        if not frappe.db.exists("User", u):
            usr = frappe.get_doc({
                "doctype": "User", "email": u, "first_name": "Orphan",
                "user_type": "Website User", "send_welcome_email": 0,
            })
            usr.insert(ignore_permissions=True)
        self.assertIn("1=0", sales_query(u))
