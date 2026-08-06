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


class TestKhoWarehouseItem(FrappeTestCase):
    def setUp(self):
        self.kho = seed_kho_demo()

    def test_miyano_item_links_to_real_item(self):
        vt = frappe.get_doc("Customer Warehouse Item", self.kho["vt_bm"])
        self.assertEqual(vt.item_code, "MYN-GLOVE-M")
        self.assertEqual(vt.kho, self.kho["kho_bm"])

    def test_customer_private_code_has_no_item(self):
        vt = frappe.get_doc("Customer Warehouse Item", self.kho["vt_rieng_bm"])
        self.assertFalse(vt.item_code)
        self.assertFalse(frappe.db.exists("Item", "BM-GAC-01"))

    def test_duplicate_code_in_same_warehouse_blocked(self):
        doc = frappe.get_doc({
            "doctype": "Customer Warehouse Item",
            "kho": self.kho["kho_bm"],
            "ma_vat_tu": "BM-GAC-01",
            "ten_vat_tu": "Gạc trùng mã",
            "dvt": "Cái",
        })
        with self.assertRaises(frappe.ValidationError) as ctx:
            doc.insert(ignore_permissions=True)
        self.assertIn("đã tồn tại", str(ctx.exception))

    def test_same_code_allowed_in_different_warehouse(self):
        doc = frappe.get_doc({
            "doctype": "Customer Warehouse Item",
            "kho": self.kho["kho_pxn"],
            "ma_vat_tu": "BM-GAC-01",
            "ten_vat_tu": "Gạc của PXN",
            "dvt": "Cái",
        })
        doc.insert(ignore_permissions=True)
        self.assertTrue(doc.name)
