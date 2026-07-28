import frappe
from frappe.tests.utils import FrappeTestCase
from miyano_portal.setup.seed_demo import seed_demo


class TestSeedDemo(FrappeTestCase):
    def test_seed_is_idempotent_and_creates_core(self):
        seed_demo()
        seed_demo()  # second run must not raise / duplicate
        self.assertTrue(frappe.db.exists("Customer", "Bệnh viện Bạch Mai"))
        self.assertTrue(frappe.db.exists("Item", "VT0005"))
        self.assertTrue(frappe.db.exists("Blanket Order", {"customer": "Bệnh viện Bạch Mai"}))
        self.assertTrue(frappe.db.exists("Item Price", {"item_code": "VT0005", "price_list": "HĐNT-BVBM-2026"}))
