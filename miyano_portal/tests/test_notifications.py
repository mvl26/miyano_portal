import frappe
from frappe.tests.utils import FrappeTestCase
from miyano_portal.setup.install_notifications import install_portal_notifications


class TestNotifications(FrappeTestCase):
    def test_notifications_installed(self):
        install_portal_notifications()
        install_portal_notifications()
        self.assertTrue(frappe.db.exists("Notification", "Portal - Đơn mới"))
        self.assertTrue(frappe.db.exists("Notification", "Portal - Đơn xác nhận"))
        self.assertTrue(frappe.db.exists("Notification", "Portal - Đơn bị từ chối"))
        self.assertTrue(frappe.db.exists("Notification", "Portal - Xuất giao"))
        self.assertTrue(frappe.db.exists("Notification", "Portal - Hoá đơn phát hành"))

        reject = frappe.get_doc("Notification", "Portal - Đơn bị từ chối")
        self.assertEqual(reject.document_type, "Sales Order")
        self.assertEqual(reject.event, "Value Change")
        self.assertEqual(reject.value_changed, "workflow_state")

        delivery = frappe.get_doc("Notification", "Portal - Xuất giao")
        self.assertEqual(delivery.document_type, "Delivery Note")
        self.assertEqual(delivery.event, "Submit")

        invoice = frappe.get_doc("Notification", "Portal - Hoá đơn phát hành")
        self.assertEqual(invoice.document_type, "Sales Invoice")
        self.assertEqual(invoice.event, "Submit")
