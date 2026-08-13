"""US-E2.5 — trạng thái "Chờ khách đồng ý" và endpoint portal_order_accept."""
import frappe
from frappe.tests.utils import FrappeTestCase
from miyano_portal.api import portal
from miyano_portal.setup.seed_demo import seed_demo

WF = "Sales Order - Client Portal"
STATE_KHACH = "Chờ khách đồng ý"


def _tao_so_cho_khach_duyet():
    from miyano_portal.setup.seed_demo import PRICE_LIST
    so = frappe.new_doc("Sales Order")
    so.customer = "Bệnh viện Bạch Mai"
    so.transaction_date = frappe.utils.today()
    so.delivery_date = frappe.utils.add_days(frappe.utils.today(), 7)
    so.selling_price_list = PRICE_LIST
    so.append("items", {
        "item_code": "VT0005", "qty": 1, "rate": 1200,
        "delivery_date": so.delivery_date,
    })
    so.taxes = []
    so.taxes_and_charges = None
    so.insert(ignore_permissions=True)
    # BẪY 4 — không gán workflow_state trước insert(). Xem Global Constraints.
    frappe.db.set_value(
        "Sales Order", so.name, "workflow_state", "Chờ khách đồng ý",
        update_modified=False,
    )
    so.reload()
    return so


class TestWorkflowMoRong(FrappeTestCase):
    def test_co_state_cho_khach_dong_y(self):
        wf = frappe.get_doc("Workflow", WF)
        s = next((x for x in wf.states if x.state == STATE_KHACH), None)
        self.assertIsNotNone(s, "thiếu state 'Chờ khách đồng ý'")
        self.assertEqual(str(s.doc_status), "0")

    def test_du_bon_transition_moi(self):
        wf = frappe.get_doc("Workflow", WF)
        co = {(t.state, t.action, t.next_state) for t in wf.transitions}
        for mong_doi in [
            ("Chờ xác nhận", "Gửi khách duyệt", STATE_KHACH),
            (STATE_KHACH, "Khách đồng ý", "Chờ Miyano xác nhận"),
            (STATE_KHACH, "Khách không đồng ý", "Chờ xác nhận"),
            ("Chờ Miyano xác nhận", "Xác nhận", "Đã xác nhận"),
        ]:
            with self.subTest(t=mong_doi):
                self.assertIn(mong_doi, co)

    def test_khong_transition_nao_mo_cho_role_customer(self):
        """Rào an toàn: role `Customer` lọt vào `allowed` là khách tự duyệt
        được đơn của chính mình từ Desk."""
        wf = frappe.get_doc("Workflow", WF)
        for t in wf.transitions:
            with self.subTest(t=f"{t.state}->{t.next_state}"):
                self.assertNotIn("Customer", (t.allowed or ""))

    def test_transition_cu_van_con_nguyen(self):
        """Không được dựng lại workflow — đơn nội bộ vẫn đi đường cũ (DoD)."""
        wf = frappe.get_doc("Workflow", WF)
        co = {(t.state, t.action, t.next_state) for t in wf.transitions}
        self.assertIn(("Chờ xác nhận", "Gửi duyệt", "Chờ Miyano xác nhận"), co)
        self.assertIn(("Chờ Miyano xác nhận", "Từ chối", "Từ chối"), co)


class TestOrderAccept(FrappeTestCase):
    def setUp(self):
        seed_demo()
        self.so = _tao_so_cho_khach_duyet()   # helper dưới
        self.addCleanup(frappe.set_user, "Administrator")

    def test_dong_y_chuyen_sang_cho_miyano_xac_nhan(self):
        frappe.set_user("bvbm@demo.miyano")
        kq = portal.portal_order_accept(self.so.name, "dong_y")
        self.assertEqual(kq["trang_thai_moi"], "Chờ Miyano xác nhận")
        frappe.set_user("Administrator")
        self.assertEqual(
            frappe.db.get_value("Sales Order", self.so.name, "workflow_state"),
            "Chờ Miyano xác nhận",
        )

    def test_dong_y_ghi_log_nguoi_bam_vao_comment(self):
        frappe.set_user("bvbm@demo.miyano")
        portal.portal_order_accept(self.so.name, "dong_y")
        frappe.set_user("Administrator")
        cmt = frappe.get_all(
            "Comment",
            filters={"reference_doctype": "Sales Order", "reference_name": self.so.name},
            pluck="content",
        )
        self.assertTrue(
            any("bvbm@demo.miyano" in (c or "") for c in cmt),
            "phải ghi lại AI bấm đồng ý — không có log thì không truy được trách nhiệm",
        )

    def test_khong_dong_y_bat_buoc_ly_do(self):
        frappe.set_user("bvbm@demo.miyano")
        with self.assertRaises(frappe.ValidationError):
            portal.portal_order_accept(self.so.name, "khong_dong_y")

    def test_khong_dong_y_kem_ly_do_ve_cho_xac_nhan(self):
        frappe.set_user("bvbm@demo.miyano")
        kq = portal.portal_order_accept(
            self.so.name, "khong_dong_y", ly_do="Giá cao hơn dự toán của đơn vị."
        )
        self.assertEqual(kq["trang_thai_moi"], "Chờ xác nhận")

    # ---------- TC-E2-06 ----------
    def test_don_cua_khach_khac_bi_tu_choi_403(self):
        frappe.set_user("pxnabc@demo.miyano")
        with self.assertRaises(frappe.PermissionError):
            portal.portal_order_accept(self.so.name, "dong_y")
        frappe.set_user("Administrator")
        self.assertEqual(
            frappe.db.get_value("Sales Order", self.so.name, "workflow_state"),
            "Chờ khách đồng ý",
            "đơn không được đổi trạng thái khi bị chặn",
        )

    def test_don_khong_o_trang_thai_cho_khach_thi_chan(self):
        frappe.db.set_value("Sales Order", self.so.name, "workflow_state", "Chờ xác nhận")
        frappe.set_user("bvbm@demo.miyano")
        with self.assertRaises(frappe.ValidationError):
            portal.portal_order_accept(self.so.name, "dong_y")
