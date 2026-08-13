"""US-E2.5 — trạng thái "Chờ khách đồng ý" và endpoint portal_order_accept."""
import frappe
from frappe.tests.utils import FrappeTestCase
from miyano_portal.setup.seed_demo import seed_demo

WF = "Sales Order - Client Portal"
STATE_KHACH = "Chờ khách đồng ý"


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
