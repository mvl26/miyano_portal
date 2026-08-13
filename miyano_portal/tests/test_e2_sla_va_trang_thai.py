"""US-E2.2 (email lý do), US-E2.3 (SLA), US-E2.4 (đóng sớm)."""
import frappe
from frappe.tests.utils import FrappeTestCase
from miyano_portal.api import portal
from miyano_portal.setup.seed_demo import seed_demo

MAIL_TU_CHOI = "Portal - Đơn bị từ chối"


def _tao_so_bi_tu_choi(ly_do: str):
    """Sales Order đã ở trạng thái "Từ chối", mang `ly_do` trong
    `custom_ly_do_tu_choi`.

    Đi thẳng qua `frappe.db.set_value` để bỏ qua `kiem_ly_do_tu_choi`
    (validate hook) — test này không kiểm tra hook đó, nó kiểm tra
    `portal_order_track` đọc lại đúng lý do đã có sẵn trên đơn.
    """
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
        "Sales Order", so.name, "custom_ly_do_tu_choi", ly_do, update_modified=False
    )
    frappe.db.set_value(
        "Sales Order", so.name, "workflow_state", "Từ chối", update_modified=False
    )
    so.reload()
    return so


class TestMailTuChoi(FrappeTestCase):
    def setUp(self):
        # seed_demo() idempotent — cần cho test thứ ba (customer, item, price
        # list); hai test đầu không đụng dữ liệu demo nhưng gọi chung cho gọn.
        seed_demo()

    def test_mail_co_chen_lay_do_tu_choi(self):
        msg = frappe.db.get_value("Notification", MAIL_TU_CHOI, "message")
        self.assertIn(
            "custom_ly_do_tu_choi", msg,
            "email từ chối phải mang đúng lý do (US-E2.2), không phải câu "
            "'liên hệ để biết thêm chi tiết'",
        )

    def test_mail_van_bat_va_dung_dieu_kien_cu(self):
        n = frappe.get_doc("Notification", MAIL_TU_CHOI)
        self.assertTrue(n.enabled)
        self.assertEqual(n.value_changed, "workflow_state")
        self.assertIn("Từ chối", n.condition)

    def test_order_track_tra_ly_do_tu_choi(self):
        so = _tao_so_bi_tu_choi("Hết hàng trong kho, dự kiến về ngày 20/08.")
        frappe.set_user("bvbm@demo.miyano")
        self.addCleanup(frappe.set_user, "Administrator")
        kq = portal.portal_order_track(so.name)
        self.assertIn("ngày 20/08", kq["ly_do_tu_choi"])
