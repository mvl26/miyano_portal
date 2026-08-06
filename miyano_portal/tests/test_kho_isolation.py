import frappe
from frappe.tests.utils import FrappeTestCase
from miyano_portal.kho import permissions as kho_perms
from miyano_portal.portal_context import get_portal_kho
from miyano_portal.setup.seed_kho_demo import seed_kho_demo

BM_USER = "bvbm@demo.miyano"
PXN_USER = "pxnabc@demo.miyano"

# Sáu doctype gốc (Task 6 ban đầu) cộng hai bảng item con của Receipt/Issue
# (vá theo review) — tổng cộng tám doctype phải có mặt trong cả hai hook dict.
ALL_EIGHT_DOCTYPES = [
    "Customer Warehouse", "Customer Warehouse Item",
    "Customer Stock Receipt", "Customer Stock Issue",
    "Customer Stock Ledger Entry", "Customer Stock Lot Balance",
    "Customer Stock Receipt Item", "Customer Stock Issue Item",
]


def _make_receipt(kho, vat_tu, so_lo):
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


def _make_issue(kho, vat_tu, so_lo):
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


def _ensure_staff_user():
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


def _ensure_orphan_user():
    """Website User có role Customer (nên có base doctype-level read, đúng
    như một tài khoản portal thật) nhưng Contact không link tới Customer nào
    — đúng kịch bản review đã khai thác: get_allowed_khos() trả về [], các
    hàm _kho_condition/_child_condition phải render "1=0", KHÔNG PHẢI để
    trần ra một PermissionError từ vòng kiểm tra role cơ bản (điều sẽ xảy ra
    nếu thiếu role Customer, che mất chính cái cần kiểm ở đây)."""
    u = "orphan@demo.miyano"
    if not frappe.db.exists("User", u):
        frappe.get_doc({
            "doctype": "User", "email": u, "first_name": "Orphan",
            "user_type": "Website User", "send_welcome_email": 0,
            "roles": [{"role": "Customer"}],
        }).insert(ignore_permissions=True)
    else:
        usr = frappe.get_doc("User", u)
        if not any(r.role == "Customer" for r in usr.roles):
            usr.append("roles", {"role": "Customer"})
            usr.save(ignore_permissions=True)
    return u


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

    def test_grandchild_item_queries_scope_to_own_warehouse_via_parent(self):
        """Customer Stock Receipt Item / Issue Item không có field `kho`
        riêng — điều kiện lọc phải đi qua subquery trên bảng cha."""
        for fn, table, parent_table in [
            (kho_perms.receipt_item_query, "Customer Stock Receipt Item",
             "Customer Stock Receipt"),
            (kho_perms.issue_item_query, "Customer Stock Issue Item",
             "Customer Stock Issue"),
        ]:
            cond = fn(BM_USER)
            self.assertIn(f"`tab{table}`.`parent`", cond)
            self.assertIn(f"`tab{parent_table}`", cond)
            self.assertIn(self.kho["kho_bm"], cond)
            self.assertNotIn(self.kho["kho_pxn"], cond)

    def test_system_user_unrestricted(self):
        for fn in [
            kho_perms.kho_query, kho_perms.vat_tu_query,
            kho_perms.receipt_query, kho_perms.issue_query,
            kho_perms.sle_query, kho_perms.lot_query,
            kho_perms.receipt_item_query, kho_perms.issue_item_query,
        ]:
            with self.subTest(fn=fn.__name__):
                self.assertEqual(fn("Administrator"), "")

    def test_user_without_customer_sees_nothing(self):
        # NOTE (deviation from brief): the brief's snippet referenced
        # "orphan@demo.miyano" without creating it, implicitly depending on
        # test_get_portal_kho_blocks_user_without_warehouse (run earlier by
        # alphabetical order) to have created it as a side effect. That's a
        # hidden ordering dependency, and it broke once that other test's
        # fixture was fixed (see NOTE above) to use a differently-named user.
        # Made self-sufficient here via the module-level _ensure_orphan_user().
        u = _ensure_orphan_user()
        self.assertIn("1=0", kho_perms.kho_query(u))
        self.assertIn("1=0", kho_perms.vat_tu_query(u))
        self.assertIn("1=0", kho_perms.receipt_item_query(u))
        self.assertIn("1=0", kho_perms.issue_item_query(u))

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

    def test_hooks_registered_for_all_eight_doctypes(self):
        # FINDING 2 (review): kiểm tra membership trong dict LITERAL của
        # module hooks.py đã import không chứng minh gì về hook THẬT SỰ được
        # Frappe dùng lúc chạy — nó pass ngay cả khi cache hook cũ (đã bị
        # clear-cache quên chạy) hoặc app chưa cài. Phải hỏi thẳng
        # frappe.get_hooks(), nguồn mà framework thực sự đọc.
        pqc = frappe.get_hooks("permission_query_conditions")
        hp = frappe.get_hooks("has_permission")
        for dt in ALL_EIGHT_DOCTYPES:
            self.assertIn(dt, pqc, dt)
            self.assertIn(dt, hp, dt)


# ---------------------------------------------------------------------------
# Phần dưới đây vượt ra ngoài yêu cầu tối thiểu của brief. Lỗ hổng mà một bộ
# test "trông có vẻ đủ" hay bỏ sót:
#
#   1. check_permission() phải chặn cho CẢ SÁU doctype gốc, không chỉ Customer
#      Warehouse Item như test_check_permission_raises_for_other_customer ở
#      trên. permission_query_conditions và has_permission được nối dây riêng
#      cho từng doctype trong hooks.py — thiếu một dòng ở đâu đó vẫn để lọt.
#   2. frappe.get_list() — con đường list-view thật sự đi qua — không được rò
#      rỉ bản ghi của khách khác, cho CẢ SÁU doctype gốc. Đây là cơ chế khác
#      hẳn has_permission (permission_query_conditions), nên phải kiểm riêng.
#   3. Nhân viên Miyano (System Manager, không phải Website User) vẫn phải
#      thấy toàn bộ dữ liệu của mọi khách hàng — cách ly không được lỡ tay
#      chặn luôn cả desk.
#
# Và sau vòng review: Customer Stock Receipt Item / Customer Stock Issue Item
# là istable=1, permissions=[] trong JSON, KHÔNG có field `kho` riêng, và
# KHÔNG nằm trong hai hook dict ở bản Task 6 đầu tiên — has_permission chỉ
# được hỏi ở cấp PARENT (role Customer read=1 là đủ để qua), còn db_query lọc
# CHILD table lại không có điều kiện gì. frappe.client.get_list được whitelist
# cho Website User đọc thẳng bảng con theo parent/parenttype, không đi qua
# get_doc(parent) nào cả — rò rỉ đơn giá, số lô, số lượng của MỌI khách hàng
# cho bất kỳ ai có role Customer, kể cả user không gắn khách hàng nào.
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

        self.receipt_bm = _make_receipt(self.kho["kho_bm"], self.kho["vt_bm"], "LO-BM-A")
        self.receipt_pxn = _make_receipt(self.kho["kho_pxn"], self.kho["vt_pxn"], "LO-PXN-A")
        self.issue_bm = _make_issue(self.kho["kho_bm"], self.kho["vt_bm"], "LO-BM-A")
        self.issue_pxn = _make_issue(self.kho["kho_pxn"], self.kho["vt_pxn"], "LO-PXN-A")

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

    def _ensure_staff_user(self):
        return _ensure_staff_user()

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


# ---------------------------------------------------------------------------
# FINDING 1 (CRITICAL, từ vòng review): Customer Stock Receipt Item / Customer
# Stock Issue Item — hai bảng item con của Receipt/Issue — hoàn toàn không có
# cách ly cho tới bản vá này. Bài test dưới đây bám sát đúng năm điểm review
# yêu cầu, cho CẢ HAI bảng item con.
# ---------------------------------------------------------------------------


class TestKhoIsolationChildItems(FrappeTestCase):
    def setUp(self):
        self.kho = seed_kho_demo()
        frappe.db.delete(
            "Customer Stock Ledger Entry",
            {"kho": ["in", [self.kho["kho_bm"], self.kho["kho_pxn"]]]},
        )
        frappe.db.delete(
            "Customer Stock Lot Balance",
            {"kho": ["in", [self.kho["kho_bm"], self.kho["kho_pxn"]]]},
        )

        self.receipt_bm = _make_receipt(self.kho["kho_bm"], self.kho["vt_bm"], "LO-BM-A")
        self.receipt_pxn = _make_receipt(self.kho["kho_pxn"], self.kho["vt_pxn"], "ZZLO-PXN")
        self.issue_bm = _make_issue(self.kho["kho_bm"], self.kho["vt_bm"], "LO-BM-A")
        self.issue_pxn = _make_issue(self.kho["kho_pxn"], self.kho["vt_pxn"], "ZZLO-PXN")

        # doctype của bảng con -> (tên doctype cha, tên dòng con của PXN,
        # tên dòng con của BM). Đây chính là bốn giá trị các test dưới đây
        # xoay quanh.
        self.child_map = {
            "Customer Stock Receipt Item": {
                "parent_doctype": "Customer Stock Receipt",
                "pxn_parent": self.receipt_pxn.name,
                "bm_parent": self.receipt_bm.name,
                "pxn_row": self.receipt_pxn.items[0].name,
                "bm_row": self.receipt_bm.items[0].name,
            },
            "Customer Stock Issue Item": {
                "parent_doctype": "Customer Stock Issue",
                "pxn_parent": self.issue_pxn.name,
                "bm_parent": self.issue_bm.name,
                "pxn_row": self.issue_pxn.items[0].name,
                "bm_row": self.issue_bm.items[0].name,
            },
        }

    def tearDown(self):
        frappe.set_user("Administrator")

    def _rows(self, dt, parent_doctype):
        return frappe.get_list(
            dt,
            parent_doctype=parent_doctype,
            fields=["name", "parent", "vat_tu", "so_lo", "don_gia"],
            limit_page_length=0,
        )

    # -- 1. Khách A không thấy dòng con thuộc chứng từ của khách B -----------

    def test_get_list_excludes_other_customers_child_rows(self):
        frappe.set_user(BM_USER)
        for dt, info in self.child_map.items():
            with self.subTest(doctype=dt):
                rows = self._rows(dt, info["parent_doctype"])
                parents = {r.parent for r in rows}
                self.assertNotIn(info["pxn_parent"], parents)

    # -- 2. User không gắn khách hàng nào thấy đúng 0 dòng ở cả hai bảng -----

    def test_orphan_user_sees_zero_rows(self):
        u = _ensure_orphan_user()
        frappe.set_user(u)
        for dt, info in self.child_map.items():
            with self.subTest(doctype=dt):
                rows = self._rows(dt, info["parent_doctype"])
                self.assertEqual(rows, [])

    # -- 3. check_permission() phải ném lỗi cho dòng con của khách khác ------
    #
    # `frappe.permissions.has_child_permission()` chỉ suy ra parent đúng khi
    # dòng con có `parent_doc` gắn sẵn (tức lấy từ `.items` của parent doc đã
    # load) — một dòng LOAD ĐỘC LẬP qua frappe.get_doc(child_dt, name) (đúng
    # như /api/resource/<dt>/<name>/ và /api/v2/document/<dt>/<name>/ đều
    # làm) có `parent_doc` resolve về None và TỤT VỀ kiểm role thuần, bỏ qua
    # hoàn toàn `kho`. Vì vậy has_permission() được ghi đè thẳng trên
    # CustomerStockReceiptItem/CustomerStockIssueItem (xem hai file
    # customer_stock_*_item.py) thay vì chỉ đăng ký hook has_permission
    # trong hooks.py — hook đó vẫn được đăng ký (voucher_item_has_permission)
    # nhưng không bao giờ được framework gọi tới cho doctype istable=1; ghi
    # đè ở đây mới là cơ chế thật sự chặn. Kiểm cả hai hình thức load: độc
    # lập VÀ đính kèm qua parent doc, để chứng minh override có hiệu lực bất
    # kể đường vào.

    def test_check_permission_raises_for_other_customers_child_row(self):
        frappe.set_user(BM_USER)
        for dt, info in self.child_map.items():
            with self.subTest(doctype=dt, form="standalone"):
                doc = frappe.get_doc(dt, info["pxn_row"])
                self.assertIsNone(doc.parent_doc)
                with self.assertRaises(frappe.PermissionError):
                    doc.check_permission("read")
            with self.subTest(doctype=dt, form="attached"):
                parent = frappe.get_doc(info["parent_doctype"], info["pxn_parent"])
                self.assertIsNotNone(parent.items[0].parent_doc)
                with self.assertRaises(frappe.PermissionError):
                    parent.items[0].check_permission("read")

    # -- 4. Positive control: khách A vẫn thấy dòng con CỦA CHÍNH MÌNH -------
    #
    # Không có test này thì một hook "1=0" vô điều kiện cho mọi Website User
    # sẽ làm test #1-#3 pass hết trong khi phá luôn portal của chính BM.

    def test_get_list_and_check_permission_allow_own_child_rows(self):
        frappe.set_user(BM_USER)
        for dt, info in self.child_map.items():
            with self.subTest(doctype=dt):
                rows = self._rows(dt, info["parent_doctype"])
                parents = {r.parent for r in rows}
                self.assertIn(info["bm_parent"], parents)
                # Cả hai hình thức load đều phải KHÔNG ném lỗi.
                frappe.get_doc(dt, info["bm_row"]).check_permission("read")
                parent = frappe.get_doc(info["parent_doctype"], info["bm_parent"])
                parent.items[0].check_permission("read")

    # -- 5. Nhân viên Miyano (System Manager) vẫn thấy dòng con của mọi khách -

    def test_staff_user_sees_all_customers_child_rows(self):
        staff = _ensure_staff_user()
        frappe.set_user(staff)
        for dt, info in self.child_map.items():
            with self.subTest(doctype=dt):
                rows = self._rows(dt, info["parent_doctype"])
                parents = {r.parent for r in rows}
                self.assertIn(info["pxn_parent"], parents)
                self.assertIn(info["bm_parent"], parents)
                frappe.get_doc(dt, info["pxn_row"]).check_permission("read")
                frappe.get_doc(dt, info["bm_row"]).check_permission("read")
