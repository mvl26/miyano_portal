import json
import os
import tempfile

import frappe
from frappe.tests.utils import FrappeTestCase

from miyano_portal.migration.import_erpnext import import_masters

FIXTURE = {
    "item_groups": [
        {"name": "MIG Vat tu tieu hao", "group_name": "MIG Vat tu tieu hao", "is_group": 0},
        {"name": "MIG Hoa chat", "group_name": "MIG Hoa chat", "is_group": 0},
    ],
    "uoms": [
        {"name": "MIG Cai", "uom_name": "MIG Cai"},
        {"name": "MIG Hop", "uom_name": "MIG Hop"},
    ],
    "items": [
        {
            "name": "MIG-IT-0001",
            "item_code": "MIG-IT-0001",
            "item_name": "Gang tay kham nghiem (migration test)",
            "description": "Test item 1",
            "item_group": "MIG Vat tu tieu hao",
            "uom": "MIG Cai",
            "is_stock_item": 1,
            "has_batch_no": 0,
            "disabled": 0,
            "selling_price": 1200,
        },
        {
            "name": "MIG-IT-0002",
            "item_code": "MIG-IT-0002",
            "item_name": "Thuoc thu sinh hoa (migration test)",
            "description": "Test item 2",
            "item_group": "MIG Hoa chat",
            "uom": "MIG Hop",
            "is_stock_item": 1,
            "has_batch_no": 1,
            "disabled": 0,
            "selling_price": 350000,
        },
    ],
    "customers": [
        {
            "name": "SC-CUS-MIG-0001",
            "customer_name": "MIG Benh vien Test A",
            "tax_code": "0100000001",
            "email": "mig-a@demo.miyano",
            "phone": "0900000001",
            "billing_address": "123 Test Street A",
            "shipping_address": "456 Shipping Street A",
            "credit_limit": 100000000,
            "status": "Hoạt động",
        },
        {
            "name": "SC-CUS-MIG-0002",
            "customer_name": "MIG PXN Test B",
            "tax_code": "0100000002",
            "email": "mig-b@demo.miyano",
            "phone": "0900000002",
            "billing_address": "789 Test Street B",
            "shipping_address": "",
            "credit_limit": 50000000,
            "status": "Hoạt động",
        },
    ],
    "framework_contracts": [
        {
            "name": "SC-SFC-MIG-0001",
            "customer": "SC-CUS-MIG-0001",
            "contract_number": "MIG-TEST-2026",
            "valid_from": "2026-01-01",
            "valid_to": "2026-12-31",
            "status": "Hiệu lực",
            "items": [
                {
                    "item": "MIG-IT-0001",
                    "uom": "MIG Cai",
                    "contract_qty": 10000,
                    "sold_qty": 0,
                    "unit_price": 1150,
                },
                {
                    "item": "MIG-IT-0002",
                    "uom": "MIG Hop",
                    "contract_qty": 500,
                    "sold_qty": 0,
                    "unit_price": 340000,
                },
            ],
        }
    ],
}


class TestMigrationImport(FrappeTestCase):
    def test_import_masters_is_idempotent_and_creates_native_records(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            infile = os.path.join(tmpdir, "supplycore_export.json")
            with open(infile, "w", encoding="utf-8") as f:
                json.dump(FIXTURE, f, ensure_ascii=False)

            first = import_masters(infile)
            second = import_masters(infile)  # must not raise / must not duplicate

        # Items
        self.assertTrue(frappe.db.exists("Item", "MIG-IT-0001"))
        self.assertTrue(frappe.db.exists("Item", "MIG-IT-0002"))
        self.assertTrue(
            frappe.db.exists(
                "Item Price", {"item_code": "MIG-IT-0001", "price_list": "Standard Selling", "selling": 1}
            )
        )

        # Customers
        self.assertTrue(frappe.db.exists("Customer", "MIG Benh vien Test A"))
        self.assertTrue(frappe.db.exists("Customer", "MIG PXN Test B"))
        self.assertTrue(frappe.db.exists("Contact", "MIG Benh vien Test A-Contact"))
        self.assertTrue(frappe.db.exists("Address", "MIG Benh vien Test A-Shipping"))
        # Customer B had no shipping_address -> no Address created.
        self.assertFalse(frappe.db.exists("Address", "MIG PXN Test B-Shipping"))

        # Blanket Order for the contract's customer, with 2 items.
        bo_name = frappe.db.get_value(
            "Blanket Order",
            {"customer": "MIG Benh vien Test A", "order_no": "MIG-TEST-2026", "blanket_order_type": "Selling"},
            "name",
        )
        self.assertTrue(bo_name)
        bo = frappe.get_doc("Blanket Order", bo_name)
        self.assertEqual(len(bo.items), 2)
        self.assertEqual({d.item_code for d in bo.items}, {"MIG-IT-0001", "MIG-IT-0002"})

        # Per-contract Price List + Item Price rows.
        price_list = "HĐNT-MIG-TEST-2026"
        self.assertTrue(frappe.db.exists("Price List", price_list))
        self.assertTrue(
            frappe.db.exists("Item Price", {"item_code": "MIG-IT-0001", "price_list": price_list, "selling": 1})
        )
        self.assertTrue(
            frappe.db.exists("Item Price", {"item_code": "MIG-IT-0002", "price_list": price_list, "selling": 1})
        )

        # Customer's default_price_list points at the contract price list.
        self.assertEqual(
            frappe.db.get_value("Customer", "MIG Benh vien Test A", "default_price_list"), price_list
        )

        # Idempotency: second run created nothing new.
        self.assertEqual(second["items"], 0)
        self.assertEqual(second["customers"], 0)
        self.assertEqual(second["blanket_orders"], 0)
        self.assertEqual(second["price_lists"], 0)
        self.assertGreater(first["items"], 0)
        self.assertGreater(first["blanket_orders"], 0)

        # Only one Blanket Order exists for this contract after both runs.
        self.assertEqual(
            frappe.db.count(
                "Blanket Order",
                {"customer": "MIG Benh vien Test A", "order_no": "MIG-TEST-2026"},
            ),
            1,
        )
