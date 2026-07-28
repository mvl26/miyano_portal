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
        # Dirty real-world record: empty item_group -> must fall back to the
        # default Item Group ("Sản phẩm") instead of raising MandatoryError.
        {
            "name": "MIG-IT-0003",
            "item_code": "MIG-IT-0003",
            "item_name": "Kim tiem (migration test, no group)",
            "description": "Test item 3 - missing item_group",
            "item_group": "",
            "uom": "MIG Cai",
            "is_stock_item": 1,
            "has_batch_no": 0,
            "disabled": 0,
            "selling_price": 500,
        },
        # Dirty real-world record: stock_uom references a UOM that doesn't
        # exist anywhere in the export -> must fall back to the default UOM
        # ("Cái") instead of raising MandatoryError.
        {
            "name": "MIG-IT-0004",
            "item_code": "MIG-IT-0004",
            "item_name": "Bong bang (migration test, bad uom)",
            "description": "Test item 4 - nonexistent stock_uom",
            "item_group": "MIG Vat tu tieu hao",
            "uom": "MIG Khong Ton Tai",
            "is_stock_item": 1,
            "has_batch_no": 0,
            "disabled": 0,
            "selling_price": 0,
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

        # Dirty-data resilience: item with an empty item_group still gets
        # created, defaulted to the fallback Item Group.
        self.assertTrue(frappe.db.exists("Item Group", "Sản phẩm"))
        self.assertTrue(frappe.db.exists("Item", "MIG-IT-0003"))
        self.assertEqual(frappe.db.get_value("Item", "MIG-IT-0003", "item_group"), "Sản phẩm")

        # Dirty-data resilience: item referencing a nonexistent stock_uom
        # still gets created, defaulted to the fallback UOM (and does NOT
        # silently vivify a one-off "MIG Khong Ton Tai" UOM).
        self.assertTrue(frappe.db.exists("UOM", "Cái"))
        self.assertTrue(frappe.db.exists("Item", "MIG-IT-0004"))
        self.assertEqual(frappe.db.get_value("Item", "MIG-IT-0004", "stock_uom"), "Cái")
        self.assertFalse(frappe.db.exists("UOM", "MIG Khong Ton Tai"))

        # Both dirty records are hard successes, not reported as skipped.
        self.assertEqual(first["items"]["skipped"], [])

        # Idempotency: second run created nothing new.
        self.assertEqual(second["items"]["created"], 0)
        self.assertEqual(second["items"]["skipped"], [])
        self.assertEqual(second["customers"]["created"], 0)
        self.assertEqual(second["contracts"]["created"], 0)
        self.assertEqual(second["blanket_orders"], 0)
        self.assertEqual(second["price_lists"], 0)
        self.assertGreater(first["items"]["created"], 0)
        self.assertGreater(first["blanket_orders"], 0)

        # Only one Blanket Order exists for this contract after both runs.
        self.assertEqual(
            frappe.db.count(
                "Blanket Order",
                {"customer": "MIG Benh vien Test A", "order_no": "MIG-TEST-2026"},
            ),
            1,
        )

    def test_import_masters_skips_bad_records_without_aborting_the_run(self):
        """Bad records of every flavour must not abort the whole import:

        - an Item that genuinely raises during creation (non-numeric
          selling_price -> ValueError) is caught by the per-record
          try/except, its partial insert is rolled back via a savepoint,
          it's recorded in `skipped`, and the run continues;
        - a contract line referencing an item_code that doesn't resolve to
          an existing Item is dropped (`skipped_lines`) without failing the
          whole contract;
        - a contract left with zero valid lines is skipped outright
          (`skipped`, with a reason), rather than creating an empty
          Blanket Order or crashing the run.

        Uses its own self-contained fixture (distinct names from FIXTURE)
        so it doesn't depend on test execution order or on state left
        behind by other tests in this class (FrappeTestCase only rolls the
        DB back at class teardown, not between individual test methods).
        """
        fixture = {
            "item_groups": [
                {"name": "MIG2 Vat tu", "group_name": "MIG2 Vat tu", "is_group": 0},
            ],
            "uoms": [
                {"name": "MIG2 Cai", "uom_name": "MIG2 Cai"},
            ],
            "items": [
                {
                    "name": "MIG2-IT-0001",
                    "item_code": "MIG2-IT-0001",
                    "item_name": "Item OK (resilience test)",
                    "item_group": "MIG2 Vat tu",
                    "uom": "MIG2 Cai",
                    "is_stock_item": 1,
                    "selling_price": 0,
                },
                {
                    "name": "MIG2-IT-0002",
                    "item_code": "MIG2-IT-0002",
                    "item_name": "Item OK 2 (resilience test)",
                    "item_group": "MIG2 Vat tu",
                    "uom": "MIG2 Cai",
                    "is_stock_item": 1,
                    "selling_price": 0,
                },
                # Genuinely broken record: non-numeric selling_price. The
                # Item insert succeeds first, then `float(selling_price)`
                # raises ValueError -> must be caught, the partial Item
                # insert rolled back via the savepoint, recorded in
                # `skipped`, and the run must continue (not abort).
                {
                    "name": "MIG2-IT-BAD-PRICE",
                    "item_code": "MIG2-IT-BAD-PRICE",
                    "item_name": "Item with broken price (resilience test)",
                    "item_group": "MIG2 Vat tu",
                    "uom": "MIG2 Cai",
                    "is_stock_item": 1,
                    "selling_price": "not-a-number",
                },
            ],
            "customers": [
                {
                    "name": "SC-CUS-MIG2-0001",
                    "customer_name": "MIG2 Benh vien Test",
                    "tax_code": "0200000001",
                    "email": "mig2@demo.miyano",
                    "phone": "0900000099",
                    "billing_address": "1 Test Street",
                    "shipping_address": "2 Shipping Street",
                    "credit_limit": 1000000,
                    "status": "Hoạt động",
                },
            ],
            "framework_contracts": [
                {
                    # Good contract: one resolvable line + one line whose
                    # item_code was never imported -> that line is dropped,
                    # the contract still gets created with the good line.
                    "name": "SC-SFC-MIG2-0001",
                    "customer": "SC-CUS-MIG2-0001",
                    "contract_number": "MIG2-TEST-GOOD",
                    "valid_from": "2026-01-01",
                    "valid_to": "2026-12-31",
                    "status": "Hiệu lực",
                    "items": [
                        {
                            "item": "MIG2-IT-0001",
                            "uom": "MIG2 Cai",
                            "contract_qty": 10,
                            "sold_qty": 0,
                            "unit_price": 100,
                        },
                        {
                            "item": "MIG2-IT-DOES-NOT-EXIST",
                            "uom": "MIG2 Cai",
                            "contract_qty": 10,
                            "sold_qty": 0,
                            "unit_price": 999,
                        },
                    ],
                },
                {
                    # All-bad contract: every referenced item_code is
                    # unresolvable -> zero valid lines -> the whole contract
                    # is skipped (no Blanket Order at all), not a crash.
                    "name": "SC-SFC-MIG2-0002",
                    "customer": "SC-CUS-MIG2-0001",
                    "contract_number": "MIG2-TEST-BAD",
                    "valid_from": "2026-01-01",
                    "valid_to": "2026-12-31",
                    "status": "Hiệu lực",
                    "items": [
                        {
                            "item": "MIG2-IT-ALSO-MISSING",
                            "uom": "MIG2 Cai",
                            "contract_qty": 1,
                            "sold_qty": 0,
                            "unit_price": 1,
                        }
                    ],
                },
            ],
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            infile = os.path.join(tmpdir, "supplycore_export_dirty.json")
            with open(infile, "w", encoding="utf-8") as f:
                json.dump(fixture, f, ensure_ascii=False)

            result = import_masters(infile)  # must not raise

        # The good contract still gets its Blanket Order, with only the 1
        # resolvable line (the bad line was dropped, not fatal).
        bo_name = frappe.db.get_value(
            "Blanket Order",
            {"customer": "MIG2 Benh vien Test", "order_no": "MIG2-TEST-GOOD", "blanket_order_type": "Selling"},
            "name",
        )
        self.assertTrue(bo_name)
        bo = frappe.get_doc("Blanket Order", bo_name)
        self.assertEqual(len(bo.items), 1)
        self.assertEqual(bo.items[0].item_code, "MIG2-IT-0001")

        # The bad line is reported, not silently dropped.
        self.assertTrue(
            any(
                line["item_code"] == "MIG2-IT-DOES-NOT-EXIST"
                for line in result["contracts"]["skipped_lines"]
            )
        )

        # The all-bad contract is skipped entirely, with a reason, and no
        # Blanket Order was created for it.
        self.assertTrue(
            any(c["contract"] == "MIG2-TEST-BAD" for c in result["contracts"]["skipped"])
        )
        self.assertFalse(frappe.db.exists("Blanket Order", {"order_no": "MIG2-TEST-BAD"}))

        # The genuinely-broken item (non-numeric selling_price) did NOT
        # abort the run: it's reported in `skipped`, its partial insert was
        # rolled back (savepoint), and it does not exist in the DB...
        self.assertFalse(frappe.db.exists("Item", "MIG2-IT-BAD-PRICE"))
        skipped_item_codes = {rec["item_code"] for rec in result["items"]["skipped"]}
        self.assertIn("MIG2-IT-BAD-PRICE", skipped_item_codes)

        # ...while the other, valid items in the very same run still got
        # created (proving the failure didn't abort the whole import).
        self.assertTrue(frappe.db.exists("Item", "MIG2-IT-0001"))
        self.assertTrue(frappe.db.exists("Item", "MIG2-IT-0002"))
        self.assertEqual(result["items"]["created"], 2)

        # No other, unrelated records were mistakenly reported as skipped.
        self.assertEqual(result["customers"]["skipped"], [])
