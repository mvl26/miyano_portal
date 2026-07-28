import frappe
from frappe.tests.utils import FrappeTestCase
from miyano_portal.setup.install_print_formats import install_portal_print_formats


class TestPrintFormats(FrappeTestCase):
    def test_print_format_installed(self):
        install_portal_print_formats()
        install_portal_print_formats()
        self.assertTrue(frappe.db.exists("Print Format", "Miyano - Xác nhận đơn hàng"))
        self.assertTrue(frappe.db.exists("Print Format", "Miyano - Phiếu giao hàng"))
        self.assertTrue(frappe.db.exists("Print Format", "Miyano - Hoá đơn"))
        dn_pf = frappe.db.get_value("Print Format", "Miyano - Phiếu giao hàng", "doc_type")
        si_pf = frappe.db.get_value("Print Format", "Miyano - Hoá đơn", "doc_type")
        self.assertEqual(dn_pf, "Delivery Note")
        self.assertEqual(si_pf, "Sales Invoice")
