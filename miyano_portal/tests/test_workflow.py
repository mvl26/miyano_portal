import frappe
from frappe.tests.utils import FrappeTestCase
from miyano_portal.setup.install_workflow import install_portal_workflow


class TestWorkflow(FrappeTestCase):
    def test_workflow_installed(self):
        install_portal_workflow()
        install_portal_workflow()  # idempotent
        self.assertTrue(frappe.db.exists("Workflow", "Sales Order - Client Portal"))
        wf = frappe.get_doc("Workflow", "Sales Order - Client Portal")
        states = {s.state for s in wf.states}
        self.assertTrue({"Chờ Miyano xác nhận", "Đã xác nhận", "Từ chối"} <= states)
