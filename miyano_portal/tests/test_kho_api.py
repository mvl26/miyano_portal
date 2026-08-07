import frappe
from frappe.tests.utils import FrappeTestCase
from miyano_portal.api import kho as kho_api
from miyano_portal.setup.seed_kho_demo import seed_kho_demo

BM_USER = "bvbm@demo.miyano"
PXN_USER = "pxnabc@demo.miyano"


class TestKhoApi(FrappeTestCase):
    def setUp(self):
        self.kho = seed_kho_demo()
        frappe.db.delete("Customer Stock Ledger Entry", {"kho": self.kho["kho_bm"]})
        frappe.db.delete("Customer Stock Lot Balance", {"kho": self.kho["kho_bm"]})
        doc = frappe.get_doc({
            "doctype": "Customer Stock Receipt",
            "kho": self.kho["kho_bm"], "ngay": "2026-02-01",
            "loai_nhap": "Nhập khác",
            "items": [
                {"vat_tu": self.kho["vt_bm"], "so_lo": "LO-A",
                 "han_su_dung": "2027-01-01", "so_luong": 100, "don_gia": 50000},
                {"vat_tu": self.kho["vt_bm"], "so_lo": "LO-B",
                 "han_su_dung": "2026-09-01", "so_luong": 40, "don_gia": 50000},
            ],
        })
        doc.insert(ignore_permissions=True)
        doc.submit()

    def tearDown(self):
        frappe.set_user("Administrator")

    def test_kho_me_returns_own_warehouse(self):
        frappe.set_user(BM_USER)
        out = kho_api.kho_me()
        self.assertEqual(out["kho"], self.kho["kho_bm"])
        self.assertEqual(out["customer"], "Bệnh viện Bạch Mai")
        self.assertEqual(out["ma_kho"], "BM")

    def test_kho_ton_aggregates_lots_per_item(self):
        frappe.set_user(BM_USER)
        rows = kho_api.kho_ton()
        row = next(r for r in rows if r["vat_tu"] == self.kho["vt_bm"])
        self.assertEqual(row["so_luong"], 140)
        self.assertEqual(row["gia_tri"], 140 * 50000)
        self.assertEqual(row["so_lo_count"], 2)
        self.assertEqual(str(row["han_gan_nhat"]), "2026-09-01")

    # FINDING N2 (review cuối): test_kho_ton_never_leaks_other_customers đã bị
    # XOÁ khỏi đây. Nó pass một cách vô nghĩa — setUp không seed dòng nào cho
    # PXN, nên "không thấy vật tư của PXN" đúng ngay cả khi bộ lọc bị gỡ sạch;
    # phần dữ liệu PXN mà nó vô tình dựa vào là rác rò rỉ giữa các test (
    # FrappeTestCase chỉ rollback ở cuối class) cộng thứ tự chạy theo bảng chữ
    # cái. Bản thay thế có seed CẢ HAI khách là
    # test_kho_ton_isolated_with_both_customers_seeded ở cuối file.

    def test_kho_lo_is_fefo_ordered(self):
        frappe.set_user(BM_USER)
        lots = kho_api.kho_lo(self.kho["vt_bm"])
        self.assertEqual([l["so_lo"] for l in lots], ["LO-B", "LO-A"])

    def test_kho_lo_rejects_other_customers_item(self):
        frappe.set_user(BM_USER)
        with self.assertRaises(frappe.PermissionError):
            kho_api.kho_lo(self.kho["vt_pxn"])

    def test_search_filters_by_name_and_code(self):
        frappe.set_user(BM_USER)
        self.assertTrue(kho_api.kho_ton(tim="Găng"))
        self.assertEqual(kho_api.kho_ton(tim="không-có-gì-cả"), [])

    # ------------------------------------------------------------------
    # Beyond-brief tests. Each one targets a specific guard and must fail
    # if that guard is removed (verified manually, see task-7-report.md).
    # ------------------------------------------------------------------

    def test_no_customer_link_denies_every_endpoint(self):
        """A Website User whose Contact exists but links to NO customer must
        be denied by every endpoint with a Vietnamese PermissionError, and
        must get no data back — not an empty-but-silent result.

        We sever the existing BM Contact's Customer link only inside a DB
        savepoint scoped to this test, then roll back to the savepoint
        before returning: no persisted change survives the test, and no
        User record is created (User.insert() commits internally and could
        not be cleanly undone — see seed_demo.py / task instructions).
        """
        frappe.set_user(BM_USER)
        contact = frappe.db.get_value("Contact", {"user": BM_USER}, "name")
        self.assertTrue(contact, "fixture assumption: BM_USER has a Contact")

        sp = "test_no_customer_link_sp"
        frappe.db.savepoint(sp)
        try:
            frappe.db.delete(
                "Dynamic Link",
                {"parenttype": "Contact", "parent": contact, "link_doctype": "Customer"},
            )
            for label, call in [
                ("kho_me", lambda: kho_api.kho_me()),
                ("kho_ton", lambda: kho_api.kho_ton()),
                ("kho_lo", lambda: kho_api.kho_lo(self.kho["vt_bm"])),
            ]:
                with self.assertRaises(frappe.PermissionError, msg=label) as cm:
                    call()
                message = str(cm.exception)
                self.assertIn("khách hàng", message, msg=label)
                self.assertNotIn("Traceback", message, msg=label)
        finally:
            frappe.db.rollback(save_point=sp)
            # frappe.db.rollback(save_point=...) undoes the row but not any
            # doc/value cache that a write may have populated in between —
            # savepoint rollback is DB-only (see frappe.database.savepoint
            # docstring). Nothing here currently goes through a cached read
            # path, but clearing defensively costs nothing and keeps this
            # test from becoming a future source of cross-test flakiness.
            frappe.clear_document_cache("Contact", contact)

    def test_kho_lo_other_customers_item_raises_not_empty(self):
        """kho_lo on a vat_tu owned by another customer must raise
        PermissionError, not quietly return []: an empty list would look
        like "vật tư tồn tại nhưng hết hàng" to the caller and hide the
        cross-tenant access attempt instead of surfacing it.
        """
        frappe.set_user(BM_USER)
        with self.assertRaises(frappe.PermissionError) as cm:
            result = kho_api.kho_lo(self.kho["vt_pxn"])
            # If the guard were replaced by a silent empty-list fallback,
            # execution would reach here instead of raising.
            self.fail(f"expected PermissionError, got {result!r}")
        self.assertNotIn("Traceback", str(cm.exception))

    def test_kho_ton_isolated_with_both_customers_seeded(self):
        """kho_ton for BM must never include a row for PXN's item, proven
        with real stock seeded for BOTH customers (not just BM) so the
        absence is demonstrably due to filtering, not to PXN having no data
        at all.
        """
        receipt_pxn = frappe.get_doc({
            "doctype": "Customer Stock Receipt",
            "kho": self.kho["kho_pxn"], "ngay": "2026-02-01",
            "loai_nhap": "Nhập khác",
            "items": [
                {"vat_tu": self.kho["vt_pxn"], "so_lo": "LO-PXN",
                 "han_su_dung": "2027-01-01", "so_luong": 30, "don_gia": 20000},
            ],
        })
        receipt_pxn.insert(ignore_permissions=True)
        receipt_pxn.submit()

        # Positive control: PXN really does have stock for this item, so a
        # clean result for BM below is filtering at work, not an accident.
        self.assertTrue(frappe.db.exists(
            "Customer Stock Lot Balance",
            {"kho": self.kho["kho_pxn"], "vat_tu": self.kho["vt_pxn"]},
        ))

        frappe.set_user(BM_USER)
        rows = kho_api.kho_ton()
        self.assertTrue(all(r["vat_tu"] != self.kho["vt_pxn"] for r in rows))
        self.assertTrue(all(r["ten_vat_tu"] != "Bơm tiêm 10ml" for r in rows))

        frappe.set_user(PXN_USER)
        pxn_rows = kho_api.kho_ton()
        self.assertTrue(any(r["vat_tu"] == self.kho["vt_pxn"] for r in pxn_rows))
        self.assertTrue(all(r["vat_tu"] != self.kho["vt_bm"] for r in pxn_rows))

    def test_customer_without_warehouse_gets_specific_message(self):
        """A customer whose account/user exists but has no Customer
        Warehouse provisioned must get the specific "chưa được mở kho"
        Vietnamese message, not a generic crash or a different error.

        FrappeTestCase only rolls back at class-cleanup time, not after each
        test method, so deactivating kho_pxn here would otherwise leak into
        every later test in this class that relies on PXN having a live
        warehouse. Scope the change to a savepoint and roll it back before
        returning.
        """
        sp = "test_no_warehouse_sp"
        frappe.db.savepoint(sp)
        try:
            frappe.db.set_value("Customer Warehouse", self.kho["kho_pxn"], "active", 0)
            frappe.set_user(PXN_USER)
            for label, call in [
                ("kho_me", lambda: kho_api.kho_me()),
                ("kho_ton", lambda: kho_api.kho_ton()),
                ("kho_lo", lambda: kho_api.kho_lo(self.kho["vt_pxn"])),
            ]:
                with self.assertRaises(frappe.PermissionError, msg=label) as cm:
                    call()
                self.assertIn("chưa được mở kho", str(cm.exception), msg=label)
        finally:
            frappe.db.rollback(save_point=sp)
            # See the matching comment in test_no_customer_link_denies_every_endpoint:
            # frappe.db.set_value() clears the doc cache on write, and a
            # savepoint rollback does not repopulate it, so drop it
            # explicitly rather than trust it stayed empty by accident.
            frappe.clear_document_cache("Customer Warehouse", self.kho["kho_pxn"])
