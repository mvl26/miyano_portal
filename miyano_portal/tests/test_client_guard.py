"""NG-37b — chặn rò rỉ dòng hàng qua frappe.client trên MỌI doctype con.

Xem docstring dài ở đầu `miyano_portal/search_guard.py` cho cơ chế lỗ và
PHẠM VI CHƯA đóng (REST `/api/resource`, `/api/v2/document`,
`frappe.client.get_value`/`validate_link`/`has_permission` — duyệt thành
NG-37c) — các test dưới đây chỉ chứng minh phần ĐÃ đóng: `frappe.client.
get_list`/`frappe.client.get` khi định tuyến bằng CHUỖI TÊN qua
`frappe.override_whitelisted_method()`, cho MỌI doctype con
(`frappe.is_table`), không riêng ba doctype PoC gốc.

RED gate ban đầu (Step 1-2 của brief) gọi thẳng `frappe.client.get_list`/
`frappe.client.get` GỐC (chưa qua `search_guard`) và xác nhận FAIL — xem
`task-1b-report.md` cho log verbatim. File này là bản GREEN cuối cùng, gọi
wrapper `client_get_list`/`client_get`, đúng khuôn mẫu đã dùng ở
`test_search_guard.py`.

**Critical C1 (review round 1, 2026-08-12)**: bản vá đầu tiên chỉ liệt kê ba
tên doctype con (`Sales Order Item`/`Delivery Note Item`/`Sales Invoice
Item`) — allow-by-omission trên trục doctype, fail OPEN với mọi doctype con
KHÁC (`Payment Schedule` là ví dụ reviewer dùng, vì nó mang field
`outstanding` — đúng loại field NG-37 tồn tại để chặn). Gate đã sửa thành
`frappe.is_table(doctype)`. `TestClientGuardC1Regression` bên dưới dùng
`Payment Schedule` — CỐ Ý một doctype ngoài tập ba tên cũ — để chứng minh
gate mới không còn phụ thuộc danh sách tên. RED gate cho C1 KHÔNG được tự
tái tạo lại (bản vá round 1 đã bị ghi đè trước khi review round 1 tới) —
bằng chứng RED là probe thật của reviewer, trích trong `task-1b-report.md`
phần "Fix round 1", không phải tự chạy lại trong task này.
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
        """Tiền điều kiện KHÔNG rỗng trước (M4, review round 1): nếu không,
        `assertEqual([], [])` xanh vô nghĩa khi site không có dữ liệu — hai
        bảng này có dữ liệu thật đã tồn tại sẵn trên `erptest.local` (không
        phải do fixture của test này tạo ra), dùng `frappe.get_all` (luôn bỏ
        qua quyền, theo đúng ghi chú ràng buộc) để xác nhận trước khi khẳng
        định phần bị chặn."""
        self.assertTrue(frappe.get_all("Delivery Note Item", limit=1))
        self.assertTrue(frappe.get_all("Sales Invoice Item", limit=1))

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


class TestClientGuardC1Regression(FrappeTestCase):
    """Critical C1, review round 1: gate round 1 chỉ liệt kê ba tên doctype
    con và fail OPEN với mọi doctype con khác. `Payment Schedule` là doctype
    con CỐ Ý KHÔNG nằm trong tập ba tên đó — chọn đúng theo gợi ý của
    reviewer vì nó mang field `outstanding`, đúng loại field NG-37 tồn tại
    để chặn (số tiền còn phải trả).

    Dùng dữ liệu THẬT đã có sẵn trên `erptest.local` (không tự tạo `Payment
    Schedule` mới) — bảng này có 26 dòng thật tại thời điểm viết test (xác
    nhận bằng `frappe.get_all`, hàm luôn bỏ qua quyền theo đúng ghi chú ràng
    buộc), đủ để chứng minh gate KHÔNG phụ thuộc `parent=` do client gửi lẫn
    danh sách tên cứng — chỉ đọc, không ghi, an toàn với dữ liệu thật."""

    def setUp(self):
        self.addCleanup(frappe.set_user, "Administrator")
        rows = frappe.get_all(
            "Payment Schedule", fields=["name", "parent", "parenttype"], limit=1
        )
        if not rows:
            self.skipTest(
                "Không có dữ liệu Payment Schedule thật trên site để probe "
                "— cần dữ liệu demo có Sales Invoice/Sales Order đã lập lịch "
                "thanh toán."
            )
        self.mot_dong = rows[0]

    def test_payment_schedule_bi_chan_du_khong_nam_trong_ba_ten_cu(self):
        """Trước khi sửa C1 (gate liệt kê ba tên), lời gọi y hệt này lọt qua
        nguyên trạng — reviewer đã probe thật trên bản vá round 1 và thấy 26
        dòng `outstanding`/`payment_amount` của nhiều khách hàng khác nhau
        (trích trong `task-1b-report.md`, mục "Fix round 1"). Sau khi gate
        đổi sang `frappe.is_table(doctype)`, phải trả `[]` vô điều kiện."""
        frappe.set_user(USER_BVBM)
        rows = client_get_list(
            "Payment Schedule",
            fields=["parent", "parenttype", "payment_amount", "outstanding"],
            parent=self.mot_dong["parenttype"],
            limit_page_length=0,
        )
        self.assertEqual(rows, [])

    def test_payment_schedule_get_bi_chan_du_khong_nam_trong_ba_ten_cu(self):
        frappe.set_user(USER_BVBM)
        with self.assertRaises(frappe.PermissionError):
            client_get(
                "Payment Schedule",
                name=self.mot_dong["name"],
                parent=self.mot_dong["parenttype"],
            )

    def test_parent_client_gui_khong_quyet_dinh_co_chan_hay_khong(self):
        """`parent=` chỉ là chìa khoá tra quyền phía framework, không phải
        điều kiện lọc hàng — gate mới chặn theo DOCTYPE, không nhìn `parent`
        client gửi là gì (kể cả `parent` "sai"/không khớp `parenttype` thật
        của dòng)."""
        frappe.set_user(USER_BVBM)
        self.assertEqual(
            client_get_list("Payment Schedule", parent="Sales Order"), []
        )
        self.assertEqual(
            client_get_list("Payment Schedule", parent="Sales Invoice"), []
        )
