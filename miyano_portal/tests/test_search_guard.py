import frappe
from frappe.tests.utils import FrappeTestCase

from miyano_portal.search_guard import search_link, search_widget
from miyano_portal.setup.seed_demo import seed_demo

BVBM = "Bệnh viện Bạch Mai"
KHAC = "PXN ABC"
USER_BVBM = "bvbm@demo.miyano"


def _draft_so(customer: str) -> str:
    item = frappe.get_all("Item", limit=1, pluck="name")[0]
    company = frappe.get_all("Company", limit=1, pluck="name")[0]
    so = frappe.new_doc("Sales Order")
    so.customer = customer
    so.company = company
    so.transaction_date = frappe.utils.today()
    so.delivery_date = frappe.utils.add_days(frappe.utils.today(), 2)
    so.append("items", {
        "item_code": item, "qty": 1, "rate": 1000,
        "delivery_date": so.delivery_date,
    })
    so.flags.ignore_permissions = True
    so.insert(ignore_permissions=True)
    return so.name


class TestSearchGuard(FrappeTestCase):
    def setUp(self):
        seed_demo()
        self.so_khac = _draft_so(KHAC)
        self.so_minh = _draft_so(BVBM)
        self.addCleanup(frappe.set_user, "Administrator")

    # ---------- chặn được ----------
    def test_search_widget_khong_ro_ri_don_khach_khac(self):
        frappe.set_user(USER_BVBM)
        rows = search_widget("Sales Order", self.so_khac, ignore_user_permissions=1)
        self.assertNotIn(self.so_khac, [r[0] for r in rows])

    def test_search_link_khong_ro_ri_don_khach_khac(self):
        frappe.set_user(USER_BVBM)
        rows = search_link("Sales Order", self.so_khac, ignore_user_permissions=1)
        self.assertNotIn(self.so_khac, [r.get("value") for r in rows])

    def test_filter_fields_khong_keo_duoc_tong_tien(self):
        """filter_fields là đường lấy grand_total / outstanding_amount."""
        frappe.set_user(USER_BVBM)
        rows = search_widget(
            "Sales Order", self.so_khac,
            filter_fields=["name", "grand_total"],
            as_dict=True, ignore_user_permissions=1,
        )
        for r in rows:
            self.assertNotEqual(r.get("name"), self.so_khac)
            self.assertNotIn("grand_total", r)

    def test_doctype_kho_tra_rong_chu_khong_nem_loi(self):
        frappe.set_user(USER_BVBM)
        self.assertEqual(search_widget("Customer Stock Receipt", ""), [])
        self.assertEqual(search_link("Customer Warehouse Item", ""), [])

    # ---------- vẫn thấy phần của mình ----------
    def test_khach_van_thay_don_cua_chinh_minh(self):
        frappe.set_user(USER_BVBM)
        rows = search_widget("Sales Order", self.so_minh)
        self.assertIn(self.so_minh, [r[0] for r in rows])

    # ---------- không chặn nhầm nhân viên Miyano ----------
    def test_desk_user_van_tim_duoc_moi_don(self):
        frappe.set_user("Administrator")
        rows = search_widget("Sales Order", self.so_khac, ignore_user_permissions=1)
        self.assertIn(self.so_khac, [r[0] for r in rows])

    # ---------- override thật sự được đăng ký ----------
    def test_hooks_da_dang_ky_ca_hai_endpoint(self):
        h = frappe.get_hooks("override_whitelisted_methods") or {}
        self.assertEqual(
            h.get("frappe.desk.search.search_link"),
            ["miyano_portal.search_guard.search_link"],
        )
        self.assertEqual(
            h.get("frappe.desk.search.search_widget"),
            ["miyano_portal.search_guard.search_widget"],
        )
