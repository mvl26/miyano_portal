import frappe
from frappe.tests.utils import FrappeTestCase
from miyano_portal.setup.seed_kho_demo import seed_kho_demo


class TestKhoWarehouse(FrappeTestCase):
    def setUp(self):
        self.kho = seed_kho_demo()

    def test_seed_creates_one_warehouse_per_customer(self):
        self.assertTrue(frappe.db.exists("Customer Warehouse", self.kho["kho_bm"]))
        self.assertEqual(
            frappe.db.get_value("Customer Warehouse", self.kho["kho_bm"], "customer"),
            "Bệnh viện Bạch Mai",
        )

    def test_seed_is_idempotent(self):
        again = seed_kho_demo()
        self.assertEqual(again["kho_bm"], self.kho["kho_bm"])
        self.assertEqual(
            frappe.db.count("Customer Warehouse", {"customer": "Bệnh viện Bạch Mai"}), 1
        )

    def test_one_warehouse_per_customer_enforced(self):
        doc = frappe.get_doc({
            "doctype": "Customer Warehouse",
            "customer": "Bệnh viện Bạch Mai",
            "ten_kho": "Kho trùng",
            "ma_kho": "BM2",
            "ngay_bat_dau": "2026-01-01",
        })
        with self.assertRaises(frappe.ValidationError) as ctx:
            doc.insert(ignore_permissions=True)
        self.assertIn("đã có kho", str(ctx.exception))

    def test_ma_kho_unique_across_customers(self):
        if not frappe.db.exists("Customer", "Himedic"):
            frappe.get_doc({
                "doctype": "Customer",
                "customer_name": "Himedic",
                "customer_type": "Company",
                "customer_group": "All Customer Groups",
                "territory": "All Territories",
            }).insert(ignore_permissions=True)

        doc = frappe.get_doc({
            "doctype": "Customer Warehouse",
            "customer": "Himedic",
            "ten_kho": "Kho Himedic",
            "ma_kho": "BM",
            "ngay_bat_dau": "2026-01-01",
        })
        with self.assertRaises(frappe.ValidationError) as ctx:
            doc.insert(ignore_permissions=True)
        self.assertIn("đã được dùng", str(ctx.exception))
