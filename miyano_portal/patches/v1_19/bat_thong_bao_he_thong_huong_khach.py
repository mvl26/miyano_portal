"""Brief 2026-08-15 (trang thông báo) Phần 1 — `install_notifications.py` đã
bật `send_system_notification: 1` cho bốn Notification hướng về khách
("Portal - Đơn xác nhận"/"Đơn bị từ chối"/"Xuất giao"/"Hoá đơn phát hành"),
cạnh "Portal - Báo giá sẵn sàng" đã bật từ `v1_14`. Nhưng
`install_portal_notifications()` BỎ QUA (không ghi đè) bản ghi `Notification`
đã tồn tại — site đã chạy `v1_0.install_portal_notifications` từ trước cần
patch NÀY để bật cờ cho bốn bản ghi ĐÃ CÀI đó, cùng khuôn
`v1_15.gioi_han_bao_gia_pdf_mua_le`.

Idempotent: `frappe.db.set_value` ghi cùng giá trị nhiều lần vô hại;
`install_portal_notifications()` an toàn gọi lại (bỏ qua bản ghi đã có, và
site MỚI chưa từng chạy patch trước sẽ insert đã đúng cờ mới ngay từ DEFS
hiện hành).
"""

import frappe

from miyano_portal.setup.install_notifications import install_portal_notifications

# CHỈ bốn cái này — "Portal - Đơn mới" và ba "Portal - Yêu cầu hàng hoá *"
# CỐ Ý không nằm trong danh sách (xem chú thích tại DEFS trong
# install_notifications.py: sự kiện "New" không phải tin mới với khách vừa
# tự bấm ra nó; recipient_field của Portal Item Request là ô text khách gõ,
# không đảm bảo khớp tài khoản cổng).
BAT_CO = [
    "Portal - Đơn xác nhận",
    "Portal - Đơn bị từ chối",
    "Portal - Xuất giao",
    "Portal - Hoá đơn phát hành",
]


def execute():
    # Site MỚI (chưa từng chạy patch trước) — insert đã đúng cờ mới ngay từ
    # DEFS hiện hành, không cần set lại.
    install_portal_notifications()
    for ten in BAT_CO:
        if frappe.db.exists("Notification", ten):
            frappe.db.set_value("Notification", ten, "send_system_notification", 1)
