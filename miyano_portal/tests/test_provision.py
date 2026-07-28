import frappe
from frappe.tests.utils import FrappeTestCase
from miyano_portal.setup.seed_demo import seed_demo
from miyano_portal.api import portal


class TestProvision(FrappeTestCase):
    def setUp(self):
        seed_demo()

    def test_provision_creates_website_user_and_link(self):
        res = portal.portal_provision("PXN ABC", "buyer2@demo.miyano")
        self.assertEqual(res["user"], "buyer2@demo.miyano")
        self.assertEqual(
            frappe.get_cached_value("User", "buyer2@demo.miyano", "user_type"),
            "Website User",
        )
        frappe.set_user("buyer2@demo.miyano")
        self.addCleanup(frappe.set_user, "Administrator")
        from miyano_portal.portal_context import get_portal_customer
        self.assertEqual(get_portal_customer(), "PXN ABC")

    def test_provision_requires_admin_role(self):
        # Use an existing seeded portal user (Customer role only) to attempt provisioning.
        frappe.set_user("pxnabc@demo.miyano")
        self.addCleanup(frappe.set_user, "Administrator")
        with self.assertRaises(frappe.PermissionError):
            portal.portal_provision("PXN ABC", "buyer3@demo.miyano")
