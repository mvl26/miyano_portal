import frappe
from frappe.tests.utils import FrappeTestCase
from miyano_portal.setup.seed_demo import seed_demo
from miyano_portal.api import portal


class TestPortalRead(FrappeTestCase):
    def setUp(self):
        seed_demo()
        frappe.set_user("bvbm@demo.miyano")
        self.addCleanup(frappe.set_user, "Administrator")

    def test_me(self):
        me = portal.portal_me()
        self.assertEqual(me["customer"], "Bệnh viện Bạch Mai")

    def test_me_exposes_tax_id_and_addresses(self):
        me = portal.portal_me()
        # new fields must always be present (even if empty) for the UI to bind
        self.assertIn("tax_id", me)
        self.assertIn("addresses", me)
        self.assertIsInstance(me["addresses"], list)
        for a in me["addresses"]:
            self.assertIn("name", a)
            self.assertIn("display", a)

    def test_invoices_status_is_vietnamese_and_has_due_date(self):
        rows = portal.portal_invoices()["rows"]
        english = {"Unpaid", "Paid", "Overdue", "Partly Paid", "Draft",
                   "Partially Paid", "Return", "Credit Note Issued"}
        for r in rows:
            self.assertIn("due_date", r)
            self.assertIn("status_vi", r)
            # status_vi must be the mapped Vietnamese label, never raw English
            self.assertNotIn(r["status_vi"], english)

    def test_invoice_status_map(self):
        self.assertEqual(portal._invoice_status_vi("Unpaid"), "Chưa thanh toán")
        self.assertEqual(portal._invoice_status_vi("Partly Paid"), "TT một phần")
        self.assertEqual(portal._invoice_status_vi("Partially Paid"), "TT một phần")
        self.assertEqual(portal._invoice_status_vi("Paid"), "Đã thanh toán")
        self.assertEqual(portal._invoice_status_vi("Overdue"), "Quá hạn")

    def test_ba_endpoint_hop_dong_va_danh_muc_cu_da_go(self):
        """Spec 2026-10-09 §7 — không màn nào còn gọi ba endpoint này nên
        chúng bị xoá hẳn; để lại là để lại ba đường đọc hợp đồng/hạn mức
        không ai canh."""
        for ten in ("portal_contracts", "portal_catalog", "portal_catalog_ban_le"):
            self.assertFalse(hasattr(portal, ten), ten)
