import frappe
from frappe.tests.utils import FrappeTestCase
from miyano_portal.kho import ledger
from miyano_portal.setup.seed_kho_demo import seed_kho_demo


class TestPhieuNhap(FrappeTestCase):
    def setUp(self):
        self.kho = seed_kho_demo()
        frappe.db.delete("Customer Stock Ledger Entry", {"kho": self.kho["kho_bm"]})
        frappe.db.delete("Customer Stock Lot Balance", {"kho": self.kho["kho_bm"]})

    def _phieu(self, so_luong=100, don_gia=50000, so_lo="LO-A", ngay="2026-02-01",
               vat_tu=None):
        doc = frappe.get_doc({
            "doctype": "Customer Stock Receipt",
            "kho": self.kho["kho_bm"],
            "ngay": ngay,
            "loai_nhap": "Nhập khác",
            "nguoi_giao": "Trần Văn Giao",
            "items": [{
                "vat_tu": vat_tu or self.kho["vt_bm"],
                "so_lo": so_lo,
                "han_su_dung": "2027-01-01",
                "so_luong": so_luong,
                "don_gia": don_gia,
            }],
        })
        doc.insert(ignore_permissions=True)
        return doc

    def test_naming_uses_warehouse_code_and_year(self):
        doc = self._phieu()
        self.assertTrue(doc.name.startswith("PN-BM-2026-"), doc.name)

    def test_draft_does_not_touch_ledger(self):
        self._phieu()
        self.assertEqual(
            frappe.db.count("Customer Stock Ledger Entry", {"kho": self.kho["kho_bm"]}), 0
        )

    def test_submit_posts_ledger_and_balance(self):
        doc = self._phieu()
        doc.submit()
        bal = ledger.get_lot_balance(self.kho["kho_bm"], self.kho["vt_bm"], "LO-A")
        self.assertEqual(bal["so_luong"], 100)
        self.assertEqual(doc.tong_tien, 100 * 50000)

    def test_totals_computed_on_validate(self):
        doc = self._phieu(so_luong=3, don_gia=1500)
        self.assertEqual(doc.items[0].thanh_tien, 4500)
        self.assertEqual(doc.tong_tien, 4500)
        self.assertEqual(doc.items[0].ten_vat_tu, "Găng tay y tế size M")

    def test_zero_qty_blocked(self):
        with self.assertRaises(frappe.ValidationError) as ctx:
            self._phieu(so_luong=0)
        self.assertIn("lớn hơn 0", str(ctx.exception))

    def test_negative_price_blocked(self):
        with self.assertRaises(frappe.ValidationError) as ctx:
            self._phieu(don_gia=-1)
        self.assertIn("không được âm", str(ctx.exception))

    def test_date_before_warehouse_start_blocked(self):
        with self.assertRaises(frappe.ValidationError) as ctx:
            self._phieu(ngay="2025-12-31")
        self.assertIn("Ngày bắt đầu quản lý", str(ctx.exception))

    def test_item_from_other_warehouse_blocked(self):
        with self.assertRaises(frappe.ValidationError) as ctx:
            self._phieu(vat_tu=self.kho["vt_pxn"])
        self.assertIn("không thuộc kho", str(ctx.exception))

    def test_cancel_creates_reversal_and_keeps_ledger(self):
        doc = self._phieu()
        doc.submit()
        doc.cancel()

        dao = frappe.get_all(
            "Customer Stock Receipt",
            filters={"phieu_goc": doc.name, "loai_nhap": "Phiếu đảo"},
            fields=["name", "docstatus"],
        )
        self.assertEqual(len(dao), 1)
        self.assertEqual(dao[0]["docstatus"], 1)

        # Sổ giữ nguyên dòng gốc, cộng thêm dòng đảo -> tồn về 0
        self.assertEqual(
            frappe.db.count("Customer Stock Ledger Entry", {"kho": self.kho["kho_bm"]}), 2
        )
        bal = ledger.get_lot_balance(self.kho["kho_bm"], self.kho["vt_bm"], "LO-A")
        self.assertEqual(bal["so_luong"], 0)
        self.assertTrue(all(frappe.get_all(
            "Customer Stock Ledger Entry",
            filters={"chung_tu": doc.name}, pluck="da_dao",
        )))

    def test_reversal_voucher_cannot_be_cancelled(self):
        doc = self._phieu()
        doc.submit()
        doc.cancel()
        dao_name = frappe.db.get_value(
            "Customer Stock Receipt", {"phieu_goc": doc.name}, "name"
        )
        dao = frappe.get_doc("Customer Stock Receipt", dao_name)
        with self.assertRaises(frappe.ValidationError) as ctx:
            dao.cancel()
        self.assertIn("phiếu đảo", str(ctx.exception).lower())
