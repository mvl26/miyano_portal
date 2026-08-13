"""US-E2.2 / BR-O14 — từ chối phải có lý do. TC-E2-04."""
import frappe
from frappe.tests.utils import FrappeTestCase
from miyano_portal.setup.seed_demo import seed_demo


class TestLyDoTuChoi(FrappeTestCase):
    def setUp(self):
        seed_demo()
        self.so = _tao_so_nhap("Chờ Miyano xác nhận")

    def test_khong_co_ly_do_thi_khong_chuyen_duoc(self):
        self.so.workflow_state = "Từ chối"
        with self.assertRaises(frappe.ValidationError) as ctx:
            self.so.save()
        self.assertIn("lý do từ chối", str(ctx.exception).lower())

    def test_ly_do_qua_ngan_bi_chan(self):
        self.so.workflow_state = "Từ chối"
        self.so.custom_ly_do_tu_choi = "hết hàng"   # 8 ký tự < 10
        with self.assertRaises(frappe.ValidationError):
            self.so.save()

    def test_ly_do_du_dai_thi_luu_duoc(self):
        self.so.workflow_state = "Từ chối"
        self.so.custom_ly_do_tu_choi = "Hết hàng trong kho, dự kiến về ngày 20/08."
        self.so.save()
        self.assertEqual(
            frappe.db.get_value("Sales Order", self.so.name, "workflow_state"), "Từ chối"
        )

    def test_trang_thai_khac_khong_bi_doi_hoi_ly_do(self):
        """Đơn nội bộ đi qua máy trạng thái như cũ — DoD E2."""
        self.so.workflow_state = "Chờ Miyano xác nhận"
        self.so.save()   # không được ném


def _tao_so_nhap(trang_thai: str, tong_muc_tieu: float = 1200):
    """Sales Order nháp của khách demo, ở đúng workflow_state cần thử.

    `qty = 1` nên `rate` chính là `grand_total` — miễn là không có thuế. Ca
    ngưỡng phụ thuộc vào con số này nên phải KHẲNG ĐỊNH, không phỏng đoán:
    site có `Sales Taxes and Charges Template` mặc định là mọi ca ngưỡng lệch
    đi 8-10% và đỏ vì lý do chẳng liên quan gì tới quy tắc đang thử.
    """
    from miyano_portal.setup.seed_demo import PRICE_LIST
    so = frappe.new_doc("Sales Order")
    so.customer = "Bệnh viện Bạch Mai"
    so.transaction_date = frappe.utils.today()
    so.delivery_date = frappe.utils.add_days(frappe.utils.today(), 7)
    so.selling_price_list = PRICE_LIST
    so.append("items", {
        "item_code": "VT0005",
        "qty": 1,
        "rate": tong_muc_tieu,
        "delivery_date": so.delivery_date,
    })
    so.taxes = []            # không để template thuế mặc định chen vào
    so.taxes_and_charges = None
    so.flags.ignore_permissions = True
    # KHÔNG gán workflow_state trước insert(): với doc mới, khung
    # `validate_workflow` (frappe/model/workflow.py) ném WorkflowPermissionError
    # bất kỳ khi nào state đích khác state đầu tiên của workflow, vì
    # `_doc_before_save` chưa tồn tại cho doc chưa lưu (nhánh "transitioning
    # directly to a state other than the first"). Cứ để insert() tự gán
    # state đầu (`Chờ xác nhận`), rồi ghi thẳng xuống DB (không qua ORM, nên
    # không đụng validate_workflow) để đưa đơn về đúng trạng thái cần thử,
    # sau đó reload() để đối tượng trong bộ nhớ khớp DB — nếu không, lần
    # `.save()` kế tiếp trong test sẽ dính TimestampMismatchError.
    so.insert(ignore_permissions=True)
    if so.workflow_state != trang_thai:
        frappe.db.set_value(
            "Sales Order", so.name, "workflow_state", trang_thai, update_modified=False
        )
        so.reload()
    assert float(so.grand_total) == float(tong_muc_tieu), (
        f"grand_total={so.grand_total} khác mức cần thử {tong_muc_tieu} — "
        "có thuế hoặc chiết khấu chen vào, ca ngưỡng sẽ vô nghĩa"
    )
    return so
