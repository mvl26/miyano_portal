"""review I-2 — Notification "Portal - Báo giá sẵn sàng" (cài từ v1_14) gắn
PDF báo giá vào MỌI đơn portal chuyển sang "Chờ khách đồng ý", không giới
hạn theo `custom_loai_don`. Nhưng "hạn hiệu lực báo giá" là khái niệm CHỈ
của Mua lẻ (`portal_order_track` trả `han_hieu_luc: None` cho đơn khác;
`portal_bao_gia.quet_bao_gia_het_han` lọc `custom_loai_don: "Mua lẻ"` để
không tự đóng đơn hợp đồng khung) — thiếu điều kiện này thì mọi đơn hợp
đồng khung vào "Chờ khách đồng ý" cũng gửi kèm một chứng từ đề "BÁO GIÁ /
QUOTATION" với "Hiệu lực đến..." mà không job nào thi hành.

`install_notifications.py` đã sửa `condition` trong DEFS cho lần cài MỚI
(site chưa từng có bản ghi này), nhưng `install_portal_notifications()`
BỎ QUA (không ghi đè) bản ghi `Notification` đã tồn tại — site đã chạy
`v1_14.install_bao_gia_san_sang_notification` cần patch NÀY để cập nhật
`condition` của bản ghi đã cài.

Idempotent: `frappe.db.set_value` ghi cùng giá trị nhiều lần vô hại;
`install_portal_notifications()` an toàn gọi lại (bỏ qua bản ghi đã có).
"""

import frappe

from miyano_portal.setup.install_notifications import install_portal_notifications

NOTI = "Portal - Báo giá sẵn sàng"
CONDITION = (
    "doc.custom_nguon_don == 'Client Portal' and "
    "doc.custom_loai_don == 'Mua lẻ' and "
    "doc.workflow_state == 'Chờ khách đồng ý'"
)


def execute():
    # Site MỚI (chưa từng chạy patch trước) — insert đã đúng `condition` mới
    # ngay từ DEFS hiện hành, không cần set lại.
    install_portal_notifications()
    if frappe.db.exists("Notification", NOTI):
        frappe.db.set_value("Notification", NOTI, "condition", CONDITION)
