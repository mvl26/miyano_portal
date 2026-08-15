import frappe
from frappe.tests.utils import FrappeTestCase

from miyano_portal.setup.install_notifications import install_portal_notifications
from miyano_portal.setup.seed_demo import seed_demo


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
    """Đóng đúng khoảng trống advisor nêu: chứng minh cờ `send_system_
    notification = 1` THẬT SỰ sinh một dòng Notification Log cho đúng người,
    không chỉ đọc field trên định nghĩa Notification."""

    def setUp(self):
        # Cùng lý do với TestSendSystemNotificationFlags — đi qua patch v1_19
        # để phản ánh đúng trạng thái SAU MIGRATE (site test đã cài các bản
        # ghi này với cờ cũ từ trước brief 2026-08-15).
        from miyano_portal.patches.v1_19 import bat_thong_bao_he_thong_huong_khach as patch

        patch.execute()
        seed_demo()
        frappe.db.delete("Notification Log", {"for_user": "bvbm@demo.miyano"})

        # Site test không cấu hình Email Account mặc định — kênh Email của
        # Notification (`send_an_email`) ném `OutgoingEmailError` NGAY khi
        # resolve tài khoản gửi, và (phát hiện khi viết test này) exception
        # đó nằm CHUNG một try/except với `create_system_notification` trong
        # `Notification.send_notification_by_channel` (core Frappe) — email
        # hỏng làm HỎNG LUÔN system notification dù hai việc tưởng độc lập.
        # Cùng cơ chế test chuẩn của Frappe mà `test_e6_mua_le.
        # test_gui_email_hai_phia` đã dùng: `mute_emails` khiến
        # `EmailAccount.find_outgoing` rơi về tài khoản dummy thay vì ném
        # lỗi. `frappe.flags` là dict toàn tiến trình, không tự rollback
        # theo FrappeTestCase — phải tự thu hồi.
        frappe.flags.mute_emails = True
        self.addCleanup(frappe.flags.pop, "mute_emails", None)

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
