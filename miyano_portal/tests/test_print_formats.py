import frappe
from frappe.tests.utils import FrappeTestCase
from miyano_portal.setup.install_print_formats import install_portal_print_formats


class TestPrintFormats(FrappeTestCase):
    def test_print_format_installed(self):
        install_portal_print_formats()
        install_portal_print_formats()
        self.assertTrue(frappe.db.exists("Print Format", "Miyano - Xác nhận đơn hàng"))
