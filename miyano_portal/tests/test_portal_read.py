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

    def test_contracts_and_catalog(self):
        contracts = portal.portal_contracts()
        self.assertTrue(contracts)
        bo = contracts[0]["name"]
        catalog = portal.portal_catalog(bo)
        codes = {r["item_code"] for r in catalog}
        self.assertEqual(codes, {"VT0005", "HC0009"})
        vt = next(r for r in catalog if r["item_code"] == "VT0005")
        self.assertEqual(vt["remaining"], 10000)
        self.assertEqual(vt["rate"], 1200)

    def test_contracts_expose_item_count(self):
        contracts = portal.portal_contracts()
        self.assertTrue(contracts)
        c = contracts[0]
        self.assertIn("item_count", c)
        # the seeded contract has the two catalog items above
        self.assertEqual(c["item_count"], len(portal.portal_catalog(c["name"])))
        self.assertGreaterEqual(c["item_count"], 1)

    def test_catalog_exposes_quota_and_group_fields(self):
        contracts = portal.portal_contracts()
        catalog = portal.portal_catalog(contracts[0]["name"])
        vt = next(r for r in catalog if r["item_code"] == "VT0005")
        for f in ("total", "used", "item_group", "remaining", "uom", "vat_pct"):
            self.assertIn(f, vt)
        # remaining is derived from total - used
        self.assertEqual(vt["remaining"], vt["total"] - vt["used"])
        self.assertEqual(vt["total"], 10000)
        self.assertIsInstance(vt["item_group"], str)

    def test_invoices_status_is_vietnamese_and_has_due_date(self):
        rows = portal.portal_invoices()
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

    def test_catalog_rejects_foreign_contract(self):
        with self.assertRaises(frappe.PermissionError):
            portal.portal_catalog("nonexistent-bo")
