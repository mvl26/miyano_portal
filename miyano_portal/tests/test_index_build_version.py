import frappe
from frappe.tests.utils import FrappeTestCase
from miyano_portal.setup.seed_demo import seed_demo
from miyano_portal.www.portal.index import get_context


class TestIndexBuildVersion(FrappeTestCase):
    def setUp(self):
        seed_demo()
        frappe.set_user("bvbm@demo.miyano")
        self.addCleanup(frappe.set_user, "Administrator")

    def test_context_carries_build_version_for_cache_busting(self):
        context = get_context(frappe._dict())
        self.assertTrue(context.get("build_version"))
