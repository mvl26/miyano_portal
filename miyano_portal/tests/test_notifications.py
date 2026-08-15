import json

import frappe
from frappe.tests.utils import FrappeTestCase

from miyano_portal.api import portal
from miyano_portal.portal_mua_le import TRANG_THAI_CHO_KHACH
from miyano_portal.setup.install_notifications import install_portal_notifications
from miyano_portal.setup.seed_demo import seed_demo
from miyano_portal.tests.test_e6_mua_le import RETAIL_CO_GIA, USER_BVBM, _rid, _seed_mua_le


class TestNotifications(FrappeTestCase):
    def test_notifications_installed(self):
        install_portal_notifications()
        install_portal_notifications()
        self.assertTrue(frappe.db.exists("Notification", "Portal - Đơn mới"))
        self.assertTrue(frappe.db.exists("Notification", "Portal - Đơn xác nhận"))
        self.assertTrue(frappe.db.exists("Notification", "Portal - Đơn bị từ chối"))
        self.assertTrue(frappe.db.exists("Notification", "Portal - Xuất giao"))
        self.assertTrue(frappe.db.exists("Notification", "Portal - Hoá đơn phát hành"))

        reject = frappe.get_doc("Notification", "Portal - Đơn bị từ chối")
        self.assertEqual(reject.document_type, "Sales Order")
        self.assertEqual(reject.event, "Value Change")
        self.assertEqual(reject.value_changed, "workflow_state")

        delivery = frappe.get_doc("Notification", "Portal - Xuất giao")
        self.assertEqual(delivery.document_type, "Delivery Note")
        self.assertEqual(delivery.event, "Submit")

        invoice = frappe.get_doc("Notification", "Portal - Hoá đơn phát hành")
        self.assertEqual(invoice.document_type, "Sales Invoice")
        self.assertEqual(invoice.event, "Submit")


class TestSendSystemNotificationFlags(FrappeTestCase):
    """Brief 2026-08-15 (trang thông báo) Phần 1 — chỉ NĂM Notification hướng
    về khách được bật `send_system_notification`; "Đơn mới" và ba "Portal -
    Yêu cầu hàng hoá *" phải giữ nguyên 0."""

    BAT = [
        "Portal - Đơn xác nhận",
        "Portal - Đơn bị từ chối",
        "Portal - Xuất giao",
        "Portal - Hoá đơn phát hành",
        "Portal - Báo giá sẵn sàng",
    ]
    KHONG_BAT = [
        "Portal - Đơn mới",
        "Portal - Yêu cầu hàng hoá đã ghi nhận",
        "Portal - Yêu cầu không đáp ứng được",
        "Portal - Yêu cầu cần thêm thông tin",
    ]

    def test_dinh_nghia_dung_co(self):
        # `install_portal_notifications()` một mình BỎ QUA bản ghi đã tồn
        # tại trên site (site test này đã chạy patch cũ với cờ 0 từ trước
        # khi brief 2026-08-15 ra đời) — phải qua đúng patch v1_19 để phản
        # ánh trạng thái SAU MIGRATE thật, không phải chỉ gọi hàm cài gốc.
        from miyano_portal.patches.v1_19 import bat_thong_bao_he_thong_huong_khach as patch

        patch.execute()
        for ten in self.BAT:
            self.assertEqual(
                frappe.db.get_value("Notification", ten, "send_system_notification"), 1,
                f"{ten} phải bật send_system_notification",
            )
        for ten in self.KHONG_BAT:
            self.assertEqual(
                frappe.db.get_value("Notification", ten, "send_system_notification"), 0,
                f"{ten} KHÔNG được bật send_system_notification",
            )


class TestPatchBatThongBaoHeThong(FrappeTestCase):
    """Patch v1_19 phải cập nhật CỜ của bản ghi Notification ĐÃ CÀI trên site
    (install_portal_notifications() bỏ qua bản ghi đã tồn tại — chỉ sửa DEFS
    không đủ), cùng khuôn test_patch_cap_nhat_condition_cua_ban_ghi_da_cai
    của v1_15.gioi_han_bao_gia_pdf_mua_le."""

    CAN_BAT = [
        "Portal - Đơn xác nhận",
        "Portal - Đơn bị từ chối",
        "Portal - Xuất giao",
        "Portal - Hoá đơn phát hành",
    ]

    def setUp(self):
        install_portal_notifications()

    def test_patch_bat_lai_co_cho_ban_ghi_da_cai(self):
        from miyano_portal.patches.v1_19 import bat_thong_bao_he_thong_huong_khach as patch

        # Dựng lại tình huống site đi TRƯỚC patch này: bốn bản ghi đã cài với
        # cờ 0 (đúng hành vi install_portal_notifications() trước brief này).
        for ten in self.CAN_BAT:
            frappe.db.set_value("Notification", ten, "send_system_notification", 0)
        for ten in self.CAN_BAT:
            self.assertEqual(
                frappe.db.get_value("Notification", ten, "send_system_notification"), 0
            )

        patch.execute()

        for ten in self.CAN_BAT:
            self.assertEqual(
                frappe.db.get_value("Notification", ten, "send_system_notification"), 1,
                f"Patch phải bật lại cờ cho {ten}",
            )

    def test_patch_idempotent(self):
        from miyano_portal.patches.v1_19 import bat_thong_bao_he_thong_huong_khach as patch

        patch.execute()
        patch.execute()
        for ten in self.CAN_BAT:
            self.assertEqual(
                frappe.db.get_value("Notification", ten, "send_system_notification"), 1
            )


class TestNotificationLogEndToEnd(FrappeTestCase):
    """BLOCKING FIX brief 2026-08-15 (trang thông báo) — chứng minh
    `Notification Log` THẬT SỰ được tạo khi kênh Email HỎNG THẬT (không có
    Email Account gửi ra trên site, KHÔNG dùng `mute_emails`).

    Phiên bản trước của lớp test này dùng `frappe.flags.mute_emails = True`
    để tránh đúng lỗi mà brief yêu cầu tái hiện — `mute_emails` khiến
    `EmailAccount.find_outgoing` rơi về tài khoản dummy thay vì ném lỗi, nên
    test đó XANH ngay cả khi tính năng CHẾT CÂM (chính là bug advisor phát
    hiện: `Notification.send_notification_by_channel` — core Frappe — bọc
    CẢ kênh Email lẫn nhánh tạo System Notification trong CÙNG MỘT
    try/except; `send_an_email` ném lỗi thì dòng tạo System Notification
    không bao giờ chạy tới). KHÔNG mute ở đây — để lỗi thật nổ ra, và khẳng
    định `overrides/notification.py` (bọc riêng từng nhánh kênh, đăng ký qua
    `override_doctype_class`) đã chặn đứng lỗi đó."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        _seed_mua_le()

    def setUp(self):
        seed_demo()
        frappe.db.delete("Notification Log", {"for_user": "bvbm@demo.miyano"})
        self.assertFalse(
            frappe.get_all("Email Account", filters={"enable_outgoing": 1}),
            "Test này cần KHÔNG có Email Account gửi ra để tái hiện đúng lỗi thật "
            "(đúng tình huống site chưa cấu hình email) — nếu site test bắt đầu "
            "có Email Account, test không còn canh đúng bug nữa.",
        )

    def test_don_xac_nhan_sinh_notification_log_cho_dung_khach(self):
        so = frappe.new_doc("Sales Order")
        so.customer = "Bệnh viện Bạch Mai"
        so.company = "Miyano Việt Nam"
        so.transaction_date = frappe.utils.today()
        so.delivery_date = frappe.utils.add_days(frappe.utils.today(), 2)
        so.custom_nguon_don = "Client Portal"
        so.contact_email = "bvbm@demo.miyano"
        so.append("items", {
            "item_code": "VT0005", "qty": 5, "rate": 1200,
            "delivery_date": frappe.utils.add_days(frappe.utils.today(), 2),
        })
        so.insert(ignore_permissions=True)
        so.submit()

        logs = frappe.get_all(
            "Notification Log",
            filters={
                "for_user": "bvbm@demo.miyano",
                "document_type": "Sales Order",
                "document_name": so.name,
            },
            fields=["subject", "read"],
        )
        self.assertEqual(len(logs), 1, "Phải có đúng một Notification Log cho khách")
        self.assertEqual(logs[0].read, 0)
        self.assertIn(so.name, logs[0].subject)

    def test_bao_gia_san_sang_sinh_notification_log_du_dinh_kem_pdf(self):
        """"Portal - Báo giá sẵn sàng" là bản ghi RỦI RO NHẤT: ngoài kênh
        Email hỏng, nó còn `attach_print = 1` — `create_system_notification`
        tự gọi `get_attachment(doc)` (`frappe.get_print`) TRƯỚC KHI tạo log,
        nên một lỗi sinh PDF độc lập với email cũng có thể xoá mất log này
        dù kênh Email đã được vá đúng. Đơn còn ở dạng nháp (`docstatus=0`)
        khi vào "Chờ khách đồng ý" — `Print Settings.allow_print_for_draft`
        phải bật (đã kiểm site test có bật) để `get_print` không tự chặn."""
        frappe.set_user(USER_BVBM)
        res = portal.portal_order_place(
            items=json.dumps([{"item_code": RETAIL_CO_GIA, "qty": 2}]),
            request_id=_rid(),
            mode="ban_le",
        )
        frappe.set_user("Administrator")
        so = frappe.get_doc("Sales Order", res["sales_order"])
        so.items[0].rate = 25000
        so.workflow_state = TRANG_THAI_CHO_KHACH
        so.save(ignore_permissions=True)

        logs = frappe.get_all(
            "Notification Log",
            filters={
                "for_user": "bvbm@demo.miyano",
                "document_type": "Sales Order",
                "document_name": so.name,
                "subject": ["like", "Báo giá cho đơn hàng%"],
            },
            fields=["subject"],
        )
        self.assertEqual(
            len(logs), 1,
            "Phải có Notification Log 'Báo giá sẵn sàng' dù email hỏng và có đính PDF",
        )
