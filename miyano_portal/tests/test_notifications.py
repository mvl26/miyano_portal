import frappe
from frappe.tests.utils import FrappeTestCase
from miyano_portal.setup.install_notifications import install_portal_notifications


class TestNotifications(FrappeTestCase):
    def test_notifications_installed(self):
        install_portal_notifications()
        install_portal_notifications()
        self.assertTrue(frappe.db.exists("Notification", "Portal - Đơn mới"))
        self.assertTrue(frappe.db.exists("Notification", "Portal - Đơn xác nhận"))
