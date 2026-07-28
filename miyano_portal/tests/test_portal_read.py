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

    def test_catalog_rejects_foreign_contract(self):
        with self.assertRaises(frappe.PermissionError):
            portal.portal_catalog("nonexistent-bo")
