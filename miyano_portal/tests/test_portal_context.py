import frappe
from frappe.tests.utils import FrappeTestCase
from miyano_portal.portal_context import get_portal_customer, remaining_qty


class TestPortalContext(FrappeTestCase):
    def test_no_contact_raises(self):
        with self.assertRaises(frappe.PermissionError):
            get_portal_customer("Administrator")
