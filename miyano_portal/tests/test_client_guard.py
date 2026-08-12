"""NG-37b — chặn rò rỉ dòng hàng qua frappe.client trên ba doctype con.

Xem docstring dài ở đầu `miyano_portal/search_guard.py` cho cơ chế lỗ và
PHẠM VI CHƯA đóng (REST `/api/resource`, `/api/v2/document`,
`frappe.client.get_value`) — các test dưới đây chỉ chứng minh phần ĐÃ đóng:
`frappe.client.get_list`/`frappe.client.get` khi định tuyến bằng CHUỖI TÊN
qua `frappe.override_whitelisted_method()`.

RED gate ban đầu (Step 1-2 của brief) gọi thẳng `frappe.client.get_list`/
`frappe.client.get` GỐC (chưa qua `search_guard`) và xác nhận FAIL — xem
`task-1b-report.md` cho log verbatim. File này là bản GREEN cuối cùng, gọi
wrapper `client_get_list`/`client_get`, đúng khuôn mẫu đã dùng ở
`test_search_guard.py`.
"""

import frappe
from frappe.tests.utils import FrappeTestCase

from miyano_portal.search_guard import client_get, client_get_list
from miyano_portal.setup.seed_demo import seed_demo
from miyano_portal.tests.test_search_guard import BVBM, KHAC, USER_BVBM, USER_SALES, _draft_so


class TestClientGuard(FrappeTestCase):
    def setUp(self):
        seed_demo()
        self.so_khac = _draft_so(KHAC)
        self.so_minh = _draft_so(BVBM)
        self.addCleanup(frappe.set_user, "Administrator")

    # ---------- chặn được: ba doctype con, Website User ----------
    def test_client_get_list_chan_han_dong_hang_website_user(self):
        """Chặn THẲNG, không lọc: kể cả dòng hàng của CHÍNH khách gọi cũng
        không trả về qua đường này — cổng có API riêng
        (`portal_order_track`...) cho việc đó, `frappe.client.get_list`
        trên ba doctype con không có màn nào cần tới."""
        frappe.set_user(USER_BVBM)
        rows = client_get_list(
            "Sales Order Item",
            fields=["parent", "item_code", "rate", "amount"],
            filters=[["parent", "in", [self.so_khac, self.so_minh]]],
            parent="Sales Order",
        )
        self.assertEqual(rows, [])

    def test_client_get_chan_han_dong_hang_website_user(self):
        item_name = frappe.get_all(
            "Sales Order Item", filters={"parent": self.so_minh}, pluck="name"
        )[0]
        frappe.set_user(USER_BVBM)
        with self.assertRaises(frappe.PermissionError):
            client_get("Sales Order Item", name=item_name, parent="Sales Order")

    def test_client_get_list_chan_ca_delivery_note_item_va_sales_invoice_item(self):
        frappe.set_user(USER_BVBM)
        self.assertEqual(
            client_get_list("Delivery Note Item", parent="Delivery Note"), []
        )
        self.assertEqual(
            client_get_list("Sales Invoice Item", parent="Sales Invoice"), []
        )

    # ---------- doctype cha (ngoài phạm vi deny-list) vẫn lọc đúng ----------
    def test_client_get_list_doctype_khac_van_uy_quyen_va_loc_dung(self):
        """`Sales Order` không nằm trong `_TU_CHOI_DONG_HANG` — wrapper uỷ
        quyền nguyên trạng cho `frappe.client.get_list` gốc, và cơ chế lọc
        theo hàng ĐÃ CÓ TỪ TRƯỚC (`permission_query_conditions::sales_query`)
        vẫn có hiệu lực, không bị wrapper này đụng vào."""
        frappe.set_user(USER_BVBM)
        rows = client_get_list("Sales Order", fields=["name"])
        names = [r["name"] for r in rows]
        self.assertIn(self.so_minh, names)
        self.assertNotIn(self.so_khac, names)

    def test_client_get_doctype_khac_van_tra_dung_don_cua_minh(self):
        frappe.set_user(USER_BVBM)
        doc = client_get("Sales Order", name=self.so_minh)
        self.assertEqual(doc["name"], self.so_minh)

    # ---------- không chặn nhầm Desk ----------
    def test_desk_user_van_doc_duoc_dong_hang_moi_khach(self):
        """`sales_user@demo.miyano` — System User thật, role `Sales User`,
        không mang role `Customer` — phải KHÔNG bị `_la_khach_cong()` phân
        loại nhầm thành khách cổng (cùng lý do dùng System User thật thay vì
        Administrator như `test_search_guard.py` đã giải thích: Administrator
        early-return trước khi chạm nhánh `user_type`)."""
        frappe.set_user(USER_SALES)
        rows = client_get_list(
            "Sales Order Item",
            fields=["parent"],
            filters=[["parent", "in", [self.so_khac, self.so_minh]]],
            parent="Sales Order",
        )
        self.assertEqual({r["parent"] for r in rows}, {self.so_khac, self.so_minh})

        item_name = frappe.get_all(
            "Sales Order Item", filters={"parent": self.so_khac}, pluck="name"
        )[0]
        doc = client_get("Sales Order Item", name=item_name, parent="Sales Order")
        self.assertEqual(doc["parent"], self.so_khac)

    # ---------- hooks thật sự đăng ký VÀ dispatch thật sự resolve đúng ----------
    def test_hooks_da_dang_ky_ca_hai_ham(self):
        h = frappe.get_hooks("override_whitelisted_methods") or {}
        self.assertEqual(
            h.get("frappe.client.get_list"),
            ["miyano_portal.search_guard.client_get_list"],
        )
        self.assertEqual(
            h.get("frappe.client.get"),
            ["miyano_portal.search_guard.client_get"],
        )

    def test_override_resolve_dung_ham_moi(self):
        """Kiểm đúng hàm mà `handler.py:67`/`v2.py:36` thật sự dùng để định
        tuyến (`frappe.override_whitelisted_method`), không chỉ nội dung
        dict thô — production dùng route `/api/method/frappe.client.get_list`
        chạy qua đúng hàm này, các test khác trong file chỉ gọi thẳng
        `client_get_list`/`client_get` (bỏ qua tầng dispatch HTTP)."""
        self.assertEqual(
            frappe.override_whitelisted_method("frappe.client.get_list"),
            "miyano_portal.search_guard.client_get_list",
        )
        self.assertEqual(
            frappe.override_whitelisted_method("frappe.client.get"),
            "miyano_portal.search_guard.client_get",
        )
