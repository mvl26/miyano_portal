import frappe
from frappe.tests.utils import FrappeTestCase


class TestSalesOrderCustomFields(FrappeTestCase):
    def test_custom_fields_exist(self):
        meta = frappe.get_meta("Sales Order")
        for fieldname in (
            "custom_nguon_don",
            "custom_hdnt",
            "custom_so_po_khach",
            "custom_yeu_cau_khach",
        ):
            self.assertTrue(
                meta.has_field(fieldname), f"missing field {fieldname}"
            )

    def test_nguon_don_options(self):
        df = frappe.get_meta("Sales Order").get_field("custom_nguon_don")
        self.assertIn("Client Portal", (df.options or "").split("\n"))
