import frappe
from frappe.tests.utils import FrappeTestCase
from miyano_portal.setup.install_workflow import install_portal_workflow

WF = "Sales Order - Client Portal"


def _hinh_dang():
    """`(trạng thái, cạnh)` của workflow — so theo NỘI DUNG, không theo thứ tự."""
    wf = frappe.get_doc("Workflow", WF)
    return (
        sorted((s.state, str(s.doc_status), s.allow_edit) for s in wf.states),
        sorted((t.state, t.action, t.next_state, t.allowed) for t in wf.transitions),
    )


class TestWorkflow(FrappeTestCase):
    @classmethod
    def setUpClass(cls):
        # Bản Workflow trong cache tài liệu không theo giao dịch của lớp test:
        # xoá nó SAU rollback (đăng ký trước `super()` vì cleanup chạy ngược).
        cls.addClassCleanup(frappe.clear_document_cache, "Workflow", WF)
        super().setUpClass()

    def test_workflow_installed(self):
        install_portal_workflow()
        install_portal_workflow()  # idempotent
        self.assertTrue(frappe.db.exists("Workflow", "Sales Order - Client Portal"))
        wf = frappe.get_doc("Workflow", "Sales Order - Client Portal")
        states = {s.state for s in wf.states}
        self.assertTrue({"Chờ Miyano xác nhận", "Đã xác nhận", "Từ chối"} <= states)

    def test_khong_transition_nao_mo_cho_role_customer(self):
        """Rào an toàn: role `Customer` lọt vào `allowed` là khách tự duyệt
        được đơn của chính mình từ Desk."""
        wf = frappe.get_doc("Workflow", WF)
        for t in wf.transitions:
            with self.subTest(t=f"{t.state}->{t.next_state}"):
                self.assertNotIn("Customer", (t.allowed or ""))

    def test_site_moi_va_site_nang_cap_co_cung_workflow(self):
        """Site mới: `install_portal_workflow()` (v1_0) rồi các patch đụng
        workflow, đúng thứ tự `after_install` chạy `patches.txt`. Site nâng
        cấp: workflow đang chạy (đã qua v1_44). Hai đường phải ra CÙNG trạng
        thái và cạnh."""
        from miyano_portal.patches.v1_4 import mo_rong_workflow_e2
        from miyano_portal.patches.v1_8 import mo_rong_workflow_e6
        from miyano_portal.patches.v1_18 import mo_rong_workflow_khach_huy
        from miyano_portal.patches.v1_41 import gia_theo_price_list
        from miyano_portal.patches.v1_44 import bo_vong_bao_gia_tren_don

        nang_cap = _hinh_dang()

        frappe.delete_doc("Workflow", WF, force=True, ignore_permissions=True)
        self.assertFalse(frappe.db.exists("Workflow", WF))
        install_portal_workflow()
        mo_rong_workflow_e2.execute()
        mo_rong_workflow_e6.execute()
        mo_rong_workflow_khach_huy.execute()
        gia_theo_price_list.mo_rong_workflow()
        bo_vong_bao_gia_tren_don.execute()

        self.assertEqual(_hinh_dang(), nang_cap)
