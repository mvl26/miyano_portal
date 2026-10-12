import frappe
from frappe.tests.utils import FrappeTestCase
from miyano_portal.setup.install_workflow import install_portal_workflow

WF = "Sales Order - Client Portal"
CANH_GUI_LAI = ("Chờ Miyano xác nhận", "Gửi khách duyệt", "Chờ khách đồng ý", "Sales User")


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

    def test_patch_them_canh_gui_khach_duyet_lai_va_chay_lai_khong_them_trung(self):
        """Final-fix I-1 — lối ra của chốt 3 trên workflow ĐANG CHẠY."""
        from miyano_portal.patches.v1_41 import gia_theo_price_list as patch

        wf = frappe.get_doc("Workflow", WF)
        wf.set("transitions", [
            t for t in wf.transitions
            if (t.state, t.action, t.next_state, t.allowed) != CANH_GUI_LAI
        ])
        wf.flags.ignore_permissions = True
        wf.save()
        truoc = _hinh_dang()
        self.assertNotIn(CANH_GUI_LAI, truoc[1])

        self.assertTrue(patch.mo_rong_workflow())
        sau = _hinh_dang()
        self.assertEqual(sau[0], truoc[0], "không thêm trạng thái mới")
        self.assertEqual(sau[1], sorted(truoc[1] + [CANH_GUI_LAI]))

        self.assertFalse(patch.mo_rong_workflow())
        self.assertEqual(_hinh_dang(), sau)

    def test_site_moi_va_site_nang_cap_co_cung_workflow(self):
        """Site mới: `install_portal_workflow()` (v1_0) rồi các patch mở rộng,
        đúng thứ tự `after_install` chạy `patches.txt`. Site nâng cấp: workflow
        sẵn có + patch v1_41. Hai đường phải ra CÙNG trạng thái và cạnh."""
        from miyano_portal.patches.v1_4 import mo_rong_workflow_e2
        from miyano_portal.patches.v1_8 import mo_rong_workflow_e6
        from miyano_portal.patches.v1_18 import mo_rong_workflow_khach_huy
        from miyano_portal.patches.v1_41 import gia_theo_price_list as patch

        patch.mo_rong_workflow()
        nang_cap = _hinh_dang()
        self.assertIn(CANH_GUI_LAI, nang_cap[1])

        frappe.delete_doc("Workflow", WF, force=True, ignore_permissions=True)
        self.assertFalse(frappe.db.exists("Workflow", WF))
        install_portal_workflow()
        self.assertIn(CANH_GUI_LAI, _hinh_dang()[1], "định nghĩa gốc đã có cạnh")
        mo_rong_workflow_e2.execute()
        mo_rong_workflow_e6.execute()
        mo_rong_workflow_khach_huy.execute()
        self.assertFalse(patch.mo_rong_workflow(), "site mới: patch không còn gì để thêm")

        self.assertEqual(_hinh_dang(), nang_cap)
