import frappe
from frappe.tests.utils import FrappeTestCase
from miyano_portal.kho import permissions as kho_perms
from miyano_portal.portal_context import get_portal_kho
from miyano_portal.setup.seed_kho_demo import seed_kho_demo

BM_USER = "bvbm@demo.miyano"
PXN_USER = "pxnabc@demo.miyano"


class TestKhoIsolation(FrappeTestCase):
    def setUp(self):
        self.kho = seed_kho_demo()

    def tearDown(self):
        frappe.set_user("Administrator")

    def test_get_portal_kho_resolves_own_warehouse(self):
        frappe.set_user(BM_USER)
        self.assertEqual(get_portal_kho(), self.kho["kho_bm"])

    def test_get_portal_kho_blocks_user_without_warehouse(self):
        # NOTE (deviation from brief's literal fixture): the brief's snippet
        # reused the fully-orphan "orphan@demo.miyano" user (no Contact, no
        # Customer at all) here. With get_portal_kho() as specified, that
        # user always hits the FIRST guard ("chưa gắn với khách hàng nào"),
        # never the second ("chưa được mở kho") — the two are genuinely
        # different failure modes. This test's name says "without_warehouse",
        # so the fixture must give the user a real Customer that simply has
        # no Customer Warehouse yet, distinct from
        # test_user_without_customer_sees_nothing below (which correctly
        # keeps using the fully-orphan user).
        cust = "Himedic Chưa Mở Kho"
        if not frappe.db.exists("Customer", cust):
            frappe.get_doc({
                "doctype": "Customer", "customer_name": cust,
                "customer_type": "Company", "customer_group": "All Customer Groups",
                "territory": "All Territories",
            }).insert(ignore_permissions=True)
        u = "chua_mo_kho@demo.miyano"
        if not frappe.db.exists("User", u):
            frappe.get_doc({
                "doctype": "User", "email": u, "first_name": "Chua Mo Kho",
                "user_type": "Website User", "send_welcome_email": 0,
            }).insert(ignore_permissions=True)
        contact_name = f"{cust}-portal"
        if not frappe.db.exists("Contact", contact_name):
            ct = frappe.new_doc("Contact")
            ct.first_name = cust
            ct.user = u
            ct.append("email_ids", {"email_id": u, "is_primary": 1})
            ct.append("links", {"link_doctype": "Customer", "link_name": cust})
            ct.name = contact_name
            ct.insert(ignore_permissions=True, set_name=contact_name)
        frappe.set_user(u)
        with self.assertRaises(frappe.PermissionError) as ctx:
            get_portal_kho()
        self.assertIn("chưa được mở kho", str(ctx.exception))

    def test_warehouse_query_scopes_to_own_customer(self):
        cond = kho_perms.kho_query(BM_USER)
        self.assertIn("Bệnh viện Bạch Mai", cond)
        self.assertNotIn("PXN ABC", cond)

    def test_child_queries_scope_to_own_warehouse(self):
        for fn, table in [
            (kho_perms.vat_tu_query, "Customer Warehouse Item"),
            (kho_perms.receipt_query, "Customer Stock Receipt"),
            (kho_perms.issue_query, "Customer Stock Issue"),
            (kho_perms.sle_query, "Customer Stock Ledger Entry"),
            (kho_perms.lot_query, "Customer Stock Lot Balance"),
        ]:
            cond = fn(BM_USER)
            self.assertIn(f"`tab{table}`.`kho`", cond)
            self.assertIn(self.kho["kho_bm"], cond)
            self.assertNotIn(self.kho["kho_pxn"], cond)

    def test_system_user_unrestricted(self):
        self.assertEqual(kho_perms.kho_query("Administrator"), "")
        self.assertEqual(kho_perms.vat_tu_query("Administrator"), "")

    def test_user_without_customer_sees_nothing(self):
        # NOTE (deviation from brief): the brief's snippet referenced
        # "orphan@demo.miyano" without creating it, implicitly depending on
        # test_get_portal_kho_blocks_user_without_warehouse (run earlier by
        # alphabetical order) to have created it as a side effect. That's a
        # hidden ordering dependency, and it broke once that other test's
        # fixture was fixed (see NOTE above) to use a differently-named user.
        # Made self-sufficient here, matching the _ensure_orphan_user()
        # pattern already used in tests/test_isolation.py.
        u = "orphan@demo.miyano"
        if not frappe.db.exists("User", u):
            frappe.get_doc({
                "doctype": "User", "email": u, "first_name": "Orphan",
                "user_type": "Website User", "send_welcome_email": 0,
            }).insert(ignore_permissions=True)
        self.assertIn("1=0", kho_perms.kho_query(u))
        self.assertIn("1=0", kho_perms.vat_tu_query(u))

    def test_has_permission_blocks_other_customers_warehouse(self):
        kho_pxn = frappe.get_doc("Customer Warehouse", self.kho["kho_pxn"])
        self.assertFalse(kho_perms.kho_has_permission(kho_pxn, user=BM_USER))
        kho_bm = frappe.get_doc("Customer Warehouse", self.kho["kho_bm"])
        self.assertTrue(kho_perms.kho_has_permission(kho_bm, user=BM_USER))

    def test_has_permission_blocks_other_customers_item(self):
        vt_pxn = frappe.get_doc("Customer Warehouse Item", self.kho["vt_pxn"])
        self.assertFalse(kho_perms.kho_child_has_permission(vt_pxn, user=BM_USER))
        vt_bm = frappe.get_doc("Customer Warehouse Item", self.kho["vt_bm"])
        self.assertTrue(kho_perms.kho_child_has_permission(vt_bm, user=BM_USER))

    def test_check_permission_raises_for_other_customer(self):
        """Đường thoát thật sự: doc.check_permission() phải chặn."""
        frappe.set_user(BM_USER)
        doc = frappe.get_doc("Customer Warehouse Item", self.kho["vt_pxn"])
        with self.assertRaises(frappe.PermissionError):
            doc.check_permission("read")

    def test_hooks_registered_for_all_six_doctypes(self):
        from miyano_portal import hooks
        for dt in [
            "Customer Warehouse", "Customer Warehouse Item",
            "Customer Stock Receipt", "Customer Stock Issue",
            "Customer Stock Ledger Entry", "Customer Stock Lot Balance",
        ]:
            self.assertIn(dt, hooks.permission_query_conditions, dt)
            self.assertIn(dt, hooks.has_permission, dt)


# ---------------------------------------------------------------------------
# Phần dưới đây vượt ra ngoài yêu cầu tối thiểu của brief. Ba lỗ hổng mà một
# bộ test "trông có vẻ đủ" hay bỏ sót:
#
#   1. check_permission() phải chặn cho CẢ SÁU doctype, không chỉ Customer
#      Warehouse Item như test_check_permission_raises_for_other_customer ở
#      trên. permission_query_conditions và has_permission được nối dây riêng
#      cho từng doctype trong hooks.py — thiếu một dòng ở đâu đó vẫn để lọt.
#   2. frappe.get_list() — con đường list-view thật sự đi qua — không được rò
#      rỉ bản ghi của khách khác, cho CẢ SÁU doctype. Đây là cơ chế khác hẳn
#      has_permission (permission_query_conditions), nên phải kiểm riêng.
#   3. Nhân viên Miyano (System Manager, không phải Website User) vẫn phải
#      thấy toàn bộ dữ liệu của mọi khách hàng — cách ly không được lỡ tay
#      chặn luôn cả desk.
# ---------------------------------------------------------------------------


class TestKhoIsolationDeep(FrappeTestCase):
    def setUp(self):
        self.kho = seed_kho_demo()
        # Dọn sổ của cả hai kho để đếm/lọc đúng trong phạm vi test này, giống
        # cách test_kho_receipt.py / test_kho_issue.py đã làm.
        frappe.db.delete(
            "Customer Stock Ledger Entry",
            {"kho": ["in", [self.kho["kho_bm"], self.kho["kho_pxn"]]]},
        )
        frappe.db.delete(
            "Customer Stock Lot Balance",
            {"kho": ["in", [self.kho["kho_bm"], self.kho["kho_pxn"]]]},
        )

        self.receipt_bm = self._receipt(self.kho["kho_bm"], self.kho["vt_bm"], "LO-BM-A")
        self.receipt_pxn = self._receipt(self.kho["kho_pxn"], self.kho["vt_pxn"], "LO-PXN-A")
        self.issue_bm = self._issue(self.kho["kho_bm"], self.kho["vt_bm"], "LO-BM-A")
        self.issue_pxn = self._issue(self.kho["kho_pxn"], self.kho["vt_pxn"], "LO-PXN-A")

        self.sle_pxn = frappe.db.get_value(
            "Customer Stock Ledger Entry", {"kho": self.kho["kho_pxn"]}, "name"
        )
        self.lot_pxn = frappe.db.get_value(
            "Customer Stock Lot Balance", {"kho": self.kho["kho_pxn"]}, "name"
        )

        self.sle_bm = frappe.db.get_value(
            "Customer Stock Ledger Entry", {"kho": self.kho["kho_bm"]}, "name"
        )
        self.lot_bm = frappe.db.get_value(
            "Customer Stock Lot Balance", {"kho": self.kho["kho_bm"]}, "name"
        )

        # Một bản ghi của PXN (khách B) cho từng doctype trong sáu doctype kho.
        self.pxn_records = {
            "Customer Warehouse": self.kho["kho_pxn"],
            "Customer Warehouse Item": self.kho["vt_pxn"],
            "Customer Stock Receipt": self.receipt_pxn.name,
            "Customer Stock Issue": self.issue_pxn.name,
            "Customer Stock Ledger Entry": self.sle_pxn,
            "Customer Stock Lot Balance": self.lot_pxn,
        }
        # Cùng sáu doctype, nhưng bản ghi của chính BM (khách A) — dùng để
        # chứng minh cách ly không lỡ tay chặn luôn dữ liệu CỦA CHÍNH khách
        # đang đăng nhập. Một hook trả "1=0" vô điều kiện sẽ pass hết mọi
        # test "PXN không lộ" ở trên nhưng phá luôn portal của BM.
        self.bm_records = {
            "Customer Warehouse": self.kho["kho_bm"],
            "Customer Warehouse Item": self.kho["vt_bm"],
            "Customer Stock Receipt": self.receipt_bm.name,
            "Customer Stock Issue": self.issue_bm.name,
            "Customer Stock Ledger Entry": self.sle_bm,
            "Customer Stock Lot Balance": self.lot_bm,
        }

    def tearDown(self):
        frappe.set_user("Administrator")

    def _receipt(self, kho, vat_tu, so_lo):
        doc = frappe.get_doc({
            "doctype": "Customer Stock Receipt",
            "kho": kho,
            "ngay": "2026-02-01",
            "loai_nhap": "Nhập khác",
            "nguoi_giao": "Trần Văn Giao",
            "items": [{
                "vat_tu": vat_tu,
                "so_lo": so_lo,
                "han_su_dung": "2027-01-01",
                "so_luong": 50,
                "don_gia": 20000,
            }],
        })
        doc.insert(ignore_permissions=True)
        doc.submit()
        return doc

    def _issue(self, kho, vat_tu, so_lo):
        doc = frappe.get_doc({
            "doctype": "Customer Stock Issue",
            "kho": kho,
            "ngay": "2026-03-01",
            "loai_xuat": "Xuất sử dụng",
            "noi_nhan": "Khoa test",
            "nguoi_nhan": "Nhân viên test",
            "items": [{
                "vat_tu": vat_tu,
                "so_lo": so_lo,
                "so_luong": 5,
            }],
        })
        doc.insert(ignore_permissions=True)
        doc.submit()
        return doc

    def _ensure_staff_user(self):
        """Nhân viên Miyano ngồi desk: System User + role System Manager,
        KHÔNG phải Website User và KHÔNG có role Customer."""
        u = "staff@demo.miyano"
        if not frappe.db.exists("User", u):
            frappe.get_doc({
                "doctype": "User",
                "email": u,
                "first_name": "Staff",
                "user_type": "System User",
                "send_welcome_email": 0,
                "roles": [{"role": "System Manager"}],
            }).insert(ignore_permissions=True)
        return u

    def _pxn_filter(self, doctype):
        if doctype == "Customer Warehouse":
            return {"customer": "PXN ABC"}
        return {"kho": self.kho["kho_pxn"]}

    def _bm_filter(self, doctype):
        if doctype == "Customer Warehouse":
            return {"customer": "Bệnh viện Bạch Mai"}
        return {"kho": self.kho["kho_bm"]}

    # -- 1. check_permission() phải chặn cho CẢ SÁU doctype ------------------

    def test_check_permission_blocks_other_customer_for_all_six_doctypes(self):
        frappe.set_user(BM_USER)
        for dt, name in self.pxn_records.items():
            with self.subTest(doctype=dt):
                doc = frappe.get_doc(dt, name)
                with self.assertRaises(frappe.PermissionError):
                    doc.check_permission("read")

    # -- 2. frappe.get_list() không rò rỉ bản ghi của khách khác, mọi doctype -

    def test_get_list_excludes_other_customer_for_all_six_doctypes(self):
        frappe.set_user(BM_USER)
        for dt in self.pxn_records:
            with self.subTest(doctype=dt):
                rows = frappe.get_list(
                    dt, filters=self._pxn_filter(dt), pluck="name"
                )
                self.assertEqual(rows, [])

    # -- 2b. Chiều ngược lại: BM vẫn phải thấy được DỮ LIỆU CỦA CHÍNH MÌNH ----
    #
    # Test #2 ở trên chỉ chứng minh "PXN không lộ ra". Một hook trả "1=0" vô
    # điều kiện cho mọi Website User (không phân biệt khách nào) sẽ làm toàn
    # bộ test phía trên PASS trong khi thực ra đã khoá luôn cổng của BM. Phải
    # kiểm cả hai chiều mới chứng minh được cách ly ĐÚNG khách, không phải
    # cách ly-tất-cả.

    def test_get_list_and_check_permission_allow_own_customer_for_all_six_doctypes(self):
        frappe.set_user(BM_USER)
        for dt, name in self.bm_records.items():
            with self.subTest(doctype=dt):
                rows = frappe.get_list(
                    dt, filters=self._bm_filter(dt), pluck="name"
                )
                self.assertIn(name, rows)
                doc = frappe.get_doc(dt, name)
                doc.check_permission("read")  # không được ném lỗi

    # -- 3. Nhân viên Miyano (System Manager) vẫn thấy toàn bộ ----------------

    def test_staff_user_sees_all_customers(self):
        staff = self._ensure_staff_user()
        frappe.set_user(staff)
        for dt, name in self.pxn_records.items():
            with self.subTest(doctype=dt):
                # assertIn, not assertEqual: Customer Stock Ledger Entry gets
                # one row from the receipt and another from the issue in
                # this same setUp, so "exactly one row" is not the invariant
                # — "the PXN row is visible to staff" is.
                rows = frappe.get_list(
                    dt, filters=self._pxn_filter(dt), pluck="name"
                )
                self.assertIn(name, rows)
                doc = frappe.get_doc(dt, name)
                doc.check_permission("read")  # không được ném lỗi
