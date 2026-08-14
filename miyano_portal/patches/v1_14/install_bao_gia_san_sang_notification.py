"""Thiết kế lại mua lẻ §4.6 — cùng khuôn `v1_0/install_portal_notifications_
extra.py`: `install_portal_notifications()` bỏ qua (không sinh trùng) mọi
`Notification.name` đã tồn tại, nên site đã chạy patch gốc một lần cần một
patch MỚI gọi lại hàm cài đặt để "Portal - Báo giá sẵn sàng" (thêm vào DEFS
ở `setup/install_notifications.py`) được cài trên site đó.
"""

from miyano_portal.setup.install_notifications import install_portal_notifications


def execute():
    install_portal_notifications()
