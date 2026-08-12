"""NG-37d — chặn `frappe.client.get_value` / `validate_link` / `has_permission`.

Trục HÀM còn hở sau NG-37b (trục hàm `get_list`/`get`) và NG-37c (trục route
REST). Cơ chế lỗ và lý do mỗi hàm cần một lớp bọc RIÊNG: xem khối comment
`NG-37d` ở cuối `miyano_portal/search_guard.py`. Tóm tắt: ba hàm gọi lẫn nhau
bằng tham chiếu NỘI BỘ trong `frappe/client.py` (`validate_link` → `get_value`
→ `get_list` cùng file), nên bản vá NG-37b bọc `frappe.client.get_list` không
chạm tới đường nào trong số này.

RED gate (2026-08-12, in-process, phiên `bvbm@demo.miyano`, dòng
`Sales Order Item` thuộc đơn khách khác) — cả ba đều ĐỎ trước khi vá:

    FAIL test_get_value...        AssertionError: PermissionError not raised
    FAIL test_validate_link...    AssertionError: PermissionError not raised
    FAIL test_has_permission...   AssertionError: True is not false

Tái lập độc lập probe HTTP đã ghi ở §1 sổ theo dõi. File này là bản GREEN,
gọi wrapper, đúng khuôn `test_client_guard.py`.
"""

import frappe
from frappe.tests.utils import FrappeTestCase

from miyano_portal.search_guard import (
    client_get_value,
    client_has_permission,
    client_validate_link,
)
from miyano_portal.setup.seed_demo import seed_demo
from miyano_portal.tests.test_search_guard import BVBM, KHAC, USER_BVBM, USER_SALES, _draft_so


class TestClientValueGuard(FrappeTestCase):
    def setUp(self):
        seed_demo()
        self.so_khac = _draft_so(KHAC)
        self.so_minh = _draft_so(BVBM)
        self.dong_khac = frappe.get_all(
            "Sales Order Item", filters={"parent": self.so_khac}, pluck="name"
        )[0]
        self.addCleanup(frappe.set_user, "Administrator")

    # ---------- chặn được: doctype con, Website User ----------
    def test_get_value_chan_dong_hang_khach_khac(self):
        frappe.set_user(USER_BVBM)
        with self.assertRaises(frappe.PermissionError):
            client_get_value(
                "Sales Order Item",
                fieldname=["parent", "rate", "amount"],
                filters={"name": self.dong_khac},
                parent="Sales Order",
            )

    def test_get_value_chan_ca_dong_hang_cua_chinh_minh(self):
        """Chặn THẲNG, không lọc — giống `client_get_list`. Cổng có API riêng
        (`portal_order_track`…) cho dữ liệu của chính khách; `frappe.client.*`
        trên doctype con không có màn nào cần tới, nên không mở hé cửa nào."""
        dong_minh = frappe.get_all(
            "Sales Order Item", filters={"parent": self.so_minh}, pluck="name"
        )[0]
        frappe.set_user(USER_BVBM)
        with self.assertRaises(frappe.PermissionError):
            client_get_value(
                "Sales Order Item",
                fieldname=["rate"],
                filters={"name": dong_minh},
                parent="Sales Order",
            )

    def test_validate_link_chan_dong_hang_khach_khac(self):
        frappe.set_user(USER_BVBM)
        with self.assertRaises(frappe.PermissionError):
            client_validate_link("Sales Order Item", self.dong_khac)

    def test_has_permission_tra_false_cho_dong_khach_khac(self):
        """Oracle phải trả câu trả lời ĐÚNG, không ném — hợp đồng của endpoint
        là một dict. Trước khi vá nó trả `True` cho dòng của khách khác."""
        frappe.set_user(USER_BVBM)
        self.assertEqual(
            client_has_permission("Sales Order Item", self.dong_khac, "read"),
            {"has_permission": False},
        )

    # ---------- doctype KHÔNG phải bảng con: uỷ quyền nguyên trạng ----------
    def test_get_value_doctype_cha_van_uy_quyen_va_loc_dung(self):
        """`Sales Order` không phải `is_table` — wrapper uỷ quyền cho bản gốc,
        và `permission_query_conditions::sales_query` sẵn có vẫn lọc theo hàng.
        Nếu ca này hỏng thì wrapper đã chặn quá tay, không phải chặn đúng."""
        frappe.set_user(USER_BVBM)
        self.assertEqual(
            client_get_value("Sales Order", fieldname="name", filters={"name": self.so_minh}),
            {"name": self.so_minh},
        )

    def test_validate_link_doctype_cha_van_chay(self):
        frappe.set_user(USER_BVBM)
        self.assertEqual(
            client_validate_link("Sales Order", self.so_minh).get("name"), self.so_minh
        )

    # ---------- không chặn nhầm Desk ----------
    def test_desk_user_van_dung_duoc_ca_ba_ham(self):
        """`sales_user@demo.miyano` — System User thật, không mang role
        `Customer`. Chặn nhầm Desk là casualty thường gặp nhất của loại sửa
        này; Administrator không dùng được vì `_la_khach_cong()` early-return
        trước khi chạm nhánh `user_type`."""
        frappe.set_user(USER_SALES)
        self.assertEqual(
            client_get_value(
                "Sales Order Item",
                fieldname=["parent"],
                filters={"name": self.dong_khac},
                parent="Sales Order",
            ),
            {"parent": self.so_khac},
        )
        self.assertEqual(
            client_validate_link("Sales Order Item", self.dong_khac).get("name"),
            self.dong_khac,
        )
        self.assertTrue(
            client_has_permission("Sales Order Item", self.dong_khac, "read").get(
                "has_permission"
            )
        )

    # ---------- hooks đăng ký VÀ dispatch thật resolve đúng ----------
    def test_hooks_da_dang_ky_ca_ba_ham(self):
        h = frappe.get_hooks("override_whitelisted_methods") or {}
        for goc, dich in (
            ("frappe.client.get_value", "miyano_portal.search_guard.client_get_value"),
            ("frappe.client.validate_link", "miyano_portal.search_guard.client_validate_link"),
            ("frappe.client.has_permission", "miyano_portal.search_guard.client_has_permission"),
        ):
            with self.subTest(goc=goc):
                self.assertEqual(h.get(goc), [dich])

    def test_override_resolve_dung_ba_ham_moi(self):
        """Kiểm đúng hàm mà `handler.py:67` / `v2.py:36` thật sự dùng để định
        tuyến, không chỉ nội dung dict thô."""
        for goc, dich in (
            ("frappe.client.get_value", "miyano_portal.search_guard.client_get_value"),
            ("frappe.client.validate_link", "miyano_portal.search_guard.client_validate_link"),
            ("frappe.client.has_permission", "miyano_portal.search_guard.client_has_permission"),
        ):
            with self.subTest(goc=goc):
                self.assertEqual(frappe.override_whitelisted_method(goc), dich)


class TestClientValueGuardNgoaiBaTenCu(FrappeTestCase):
    """Chứng minh gate đi theo THUỘC TÍNH `is_table`, không theo danh sách tên.

    `Payment Schedule` cố ý nằm ngoài ba doctype PoC gốc và mang `outstanding`
    — đúng trường mà probe ở §1 sổ theo dõi đã kéo được của khách khác qua
    `get_value`. Dùng dữ liệu thật sẵn có, chỉ đọc.
    """

    def setUp(self):
        self.addCleanup(frappe.set_user, "Administrator")
        rows = frappe.get_all(
            "Payment Schedule", fields=["name", "parenttype"], limit=1
        )
        if not rows:
            self.skipTest("Site không có dữ liệu Payment Schedule thật để probe.")
        self.mot_dong = rows[0]

    def test_get_value_chan_payment_schedule(self):
        frappe.set_user(USER_BVBM)
        with self.assertRaises(frappe.PermissionError):
            client_get_value(
                "Payment Schedule",
                fieldname=["parent", "payment_amount", "outstanding"],
                filters={"name": self.mot_dong["name"]},
                parent=self.mot_dong["parenttype"],
            )

    def test_has_permission_chan_payment_schedule(self):
        frappe.set_user(USER_BVBM)
        self.assertEqual(
            client_has_permission("Payment Schedule", self.mot_dong["name"], "read"),
            {"has_permission": False},
        )
