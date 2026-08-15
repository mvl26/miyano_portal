"""Spec 2026-08-15 §3.6 — cài Print Format "Miyano - Báo giá" và đính nó vào
Notification "Portal - Báo giá sẵn sàng" đã cài từ v1_14.

Hai hàm cài đặt gốc đều BỎ QUA bản ghi đã tồn tại (`install_print_formats.py`
và `install_notifications.py` cùng khuôn "exists → continue"), nên Notification
cũ sẽ KHÔNG tự nhận `attach_print` — phải set thẳng ở đây.

Idempotent: `install_portal_print_formats()` tự bỏ qua mẫu đã có;
`frappe.db.set_value` ghi cùng giá trị nhiều lần là vô hại.
"""

import frappe

from miyano_portal.setup.install_print_formats import install_portal_print_formats

NOTI = "Portal - Báo giá sẵn sàng"
PF = "Miyano - Báo giá"


def execute():
    install_portal_print_formats()
    if frappe.db.exists("Notification", NOTI) and frappe.db.exists("Print Format", PF):
        frappe.db.set_value("Notification", NOTI, {"attach_print": 1, "print_format": PF})
