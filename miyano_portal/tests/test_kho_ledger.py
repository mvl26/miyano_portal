import frappe
from frappe.tests.utils import FrappeTestCase
from miyano_portal.setup.seed_kho_demo import seed_kho_demo
from miyano_portal.kho import ledger


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


class _FakeVoucher:
    """Đủ thuộc tính để post_lines dùng, không cần doctype thật ở task này."""

    def __init__(self, kho, ngay="2026-02-01", doctype="Customer Stock Receipt",
                 name="TEST-PN-001"):
        self.kho = kho
        self.ngay = ngay
        self.doctype = doctype
        self.name = name


class TestKhoLedger(FrappeTestCase):
    def setUp(self):
        self.kho = seed_kho_demo()
        frappe.db.delete("Customer Stock Ledger Entry", {"kho": self.kho["kho_bm"]})
        frappe.db.delete("Customer Stock Lot Balance", {"kho": self.kho["kho_bm"]})

    def _nhap(self, so_luong, don_gia, so_lo="LO-A", han="2027-01-01", row="r1",
              name="TEST-PN-001"):
        v = _FakeVoucher(self.kho["kho_bm"], name=name)
        return ledger.post_lines(v, [{
            "vat_tu": self.kho["vt_bm"], "so_lo": so_lo, "han_su_dung": han,
            "so_luong": so_luong, "don_gia": don_gia, "chung_tu_row": row,
        }])

    def test_receipt_creates_lot_balance(self):
        self._nhap(100, 50000)
        bal = ledger.get_lot_balance(self.kho["kho_bm"], self.kho["vt_bm"], "LO-A")
        self.assertEqual(bal["so_luong"], 100)
        self.assertEqual(bal["don_gia"], 50000)

    def test_issue_reduces_lot_balance(self):
        self._nhap(100, 50000)
        v = _FakeVoucher(self.kho["kho_bm"], doctype="Customer Stock Issue",
                         name="TEST-PX-001")
        ledger.post_lines(v, [{
            "vat_tu": self.kho["vt_bm"], "so_lo": "LO-A", "han_su_dung": "2027-01-01",
            "so_luong": -30, "don_gia": 50000, "chung_tu_row": "r9",
        }])
        bal = ledger.get_lot_balance(self.kho["kho_bm"], self.kho["vt_bm"], "LO-A")
        self.assertEqual(bal["so_luong"], 70)
        # Xuất không đổi đơn giá của lô
        self.assertEqual(bal["don_gia"], 50000)

    def test_same_lot_twice_gives_weighted_average_price(self):
        self._nhap(100, 50000, row="r1", name="TEST-PN-001")
        self._nhap(100, 70000, row="r2", name="TEST-PN-002")
        bal = ledger.get_lot_balance(self.kho["kho_bm"], self.kho["vt_bm"], "LO-A")
        self.assertEqual(bal["so_luong"], 200)
        self.assertEqual(bal["don_gia"], 60000)

    def test_entry_records_signed_qty_and_value(self):
        self._nhap(100, 50000)
        entries = frappe.get_all(
            "Customer Stock Ledger Entry",
            filters={"kho": self.kho["kho_bm"]},
            fields=["name", "so_luong", "gia_tri", "chung_tu"],
        )
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["gia_tri"], 100 * 50000)

    def test_ledger_entry_cannot_be_edited(self):
        self._nhap(100, 50000)
        name = frappe.db.get_value(
            "Customer Stock Ledger Entry", {"kho": self.kho["kho_bm"]}, "name"
        )
        doc = frappe.get_doc("Customer Stock Ledger Entry", name)
        doc.so_luong = 999
        with self.assertRaises(frappe.ValidationError) as ctx:
            doc.save(ignore_permissions=True)
        self.assertIn("Không được sửa", str(ctx.exception))
        # Không chỉ kiểm tra exception — phải chắc dữ liệu trong DB không bị
        # ghi đè trước khi guard ném lỗi (guard chạy ở before_save, trước
        # db_update()). Nếu guard tụt lại on_update thì dòng dưới sẽ fail vì
        # DB đã bị ghi 999 trước khi ValidationError được ném ra.
        self.assertEqual(
            frappe.db.get_value("Customer Stock Ledger Entry", name, "so_luong"), 100
        )

    def test_ledger_entry_cannot_be_deleted(self):
        self._nhap(100, 50000)
        name = frappe.db.get_value(
            "Customer Stock Ledger Entry", {"kho": self.kho["kho_bm"]}, "name"
        )
        with self.assertRaises(frappe.ValidationError) as ctx:
            frappe.delete_doc("Customer Stock Ledger Entry", name, ignore_permissions=True)
        self.assertIn("Không được xoá", str(ctx.exception))

    def test_duplicate_row_is_not_posted_twice(self):
        self._nhap(100, 50000, row="r1")
        self._nhap(100, 50000, row="r1")
        self.assertEqual(
            frappe.db.count(
                "Customer Stock Ledger Entry", {"kho": self.kho["kho_bm"]}
            ),
            1,
        )

    def test_over_issue_is_rejected_and_not_posted(self):
        self._nhap(100, 50000)
        v = _FakeVoucher(self.kho["kho_bm"], doctype="Customer Stock Issue",
                         name="TEST-PX-001")
        with self.assertRaises(frappe.ValidationError) as ctx:
            ledger.post_lines(v, [{
                "vat_tu": self.kho["vt_bm"], "so_lo": "LO-A",
                "han_su_dung": "2027-01-01", "so_luong": -150, "don_gia": 50000,
                "chung_tu_row": "r9",
            }])
        self.assertIn("Không đủ tồn", str(ctx.exception))
        # Sổ append-only không xoá được: dòng xuất vượt tồn không được phép
        # tồn tại dù chỉ một khoảnh khắc, nên phải chặn TRƯỚC insert. Nếu guard
        # tụt sau insert, dòng này đã có mặt trong sổ tại đây.
        self.assertFalse(
            frappe.db.exists(
                "Customer Stock Ledger Entry",
                {"kho": self.kho["kho_bm"], "chung_tu": "TEST-PX-001"},
            )
        )
        bal = ledger.get_lot_balance(self.kho["kho_bm"], self.kho["vt_bm"], "LO-A")
        self.assertEqual(bal["so_luong"], 100)

    def test_mark_reversed_flags_entries(self):
        self._nhap(100, 50000)
        ledger.mark_reversed("Customer Stock Receipt", "TEST-PN-001")
        flags = frappe.get_all(
            "Customer Stock Ledger Entry",
            filters={"chung_tu": "TEST-PN-001"}, pluck="da_dao",
        )
        self.assertTrue(flags)  # assertTrue(all([])) là True một cách vô nghĩa
        self.assertTrue(all(flags))

    def test_rebuild_lot_balance_matches_ledger(self):
        self._nhap(100, 50000)
        self._nhap(50, 50000, so_lo="LO-B", han="2026-12-01", row="r2",
                   name="TEST-PN-002")
        frappe.db.delete("Customer Stock Lot Balance", {"kho": self.kho["kho_bm"]})
        written = ledger.rebuild_lot_balance(self.kho["kho_bm"])
        self.assertEqual(written, 2)
        self.assertEqual(
            ledger.get_lot_balance(
                self.kho["kho_bm"], self.kho["vt_bm"], "LO-A")["so_luong"], 100
        )
        self.assertEqual(
            ledger.get_lot_balance(
                self.kho["kho_bm"], self.kho["vt_bm"], "LO-B")["so_luong"], 50
        )

    def test_rebuild_lot_balance_matches_ledger_with_mixed_price_and_issue(self):
        """Phần khó của bất biến: rebuild phải cho đúng cả don_gia bình quân
        gia quyền, không chỉ so_luong. Hai lần nhập cùng lô khác giá cộng một
        lần xuất — kết quả tái dựng phải khớp với kết quả đường ghi tuần tự.
        """
        self._nhap(100, 50000, row="r1", name="TEST-PN-001")
        self._nhap(100, 70000, row="r2", name="TEST-PN-002")
        v = _FakeVoucher(self.kho["kho_bm"], doctype="Customer Stock Issue",
                         name="TEST-PX-001")
        ledger.post_lines(v, [{
            "vat_tu": self.kho["vt_bm"], "so_lo": "LO-A", "han_su_dung": "2027-01-01",
            "so_luong": -40, "don_gia": 60000, "chung_tu_row": "r9",
        }])
        incremental = ledger.get_lot_balance(
            self.kho["kho_bm"], self.kho["vt_bm"], "LO-A"
        )
        self.assertEqual(incremental["so_luong"], 160)
        self.assertEqual(incremental["don_gia"], 60000)

        frappe.db.delete("Customer Stock Lot Balance", {"kho": self.kho["kho_bm"]})
        ledger.rebuild_lot_balance(self.kho["kho_bm"])
        rebuilt = ledger.get_lot_balance(
            self.kho["kho_bm"], self.kho["vt_bm"], "LO-A"
        )
        self.assertEqual(rebuilt["so_luong"], incremental["so_luong"])
        self.assertEqual(rebuilt["don_gia"], incremental["don_gia"])

    def test_get_lot_balances_is_fefo_ordered(self):
        self._nhap(10, 1000, so_lo="LO-XA", han="2028-01-01", row="r1",
                   name="TEST-PN-001")
        self._nhap(10, 1000, so_lo="LO-GAN", han="2026-09-01", row="r2",
                   name="TEST-PN-002")
        self._nhap(10, 1000, so_lo=ledger.LOT_KHONG_CO, han=None, row="r3",
                   name="TEST-PN-003")
        lots = ledger.get_lot_balances(self.kho["kho_bm"], self.kho["vt_bm"])
        self.assertEqual([l["so_lo"] for l in lots],
                         ["LO-GAN", "LO-XA", ledger.LOT_KHONG_CO])

    def test_zero_balance_lot_excluded_from_fefo(self):
        self._nhap(10, 1000, so_lo="LO-HET", han="2026-09-01")
        v = _FakeVoucher(self.kho["kho_bm"], doctype="Customer Stock Issue",
                         name="TEST-PX-001")
        ledger.post_lines(v, [{
            "vat_tu": self.kho["vt_bm"], "so_lo": "LO-HET",
            "han_su_dung": "2026-09-01", "so_luong": -10, "don_gia": 1000,
            "chung_tu_row": "r9",
        }])
        lots = ledger.get_lot_balances(self.kho["kho_bm"], self.kho["vt_bm"])
        self.assertEqual(lots, [])
