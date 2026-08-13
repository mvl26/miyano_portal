from miyano_portal.setup.install_notifications import install_portal_notifications


def execute():
    # Idempotent: install_portal_notifications() tự bỏ qua mọi Notification
    # đã tồn tại theo `name` — gọi lại ở đây chỉ chèn thêm ba định nghĩa MỚI
    # của E6 (đã nối vào DEFS), không đụng năm định nghĩa cũ.
    install_portal_notifications()
