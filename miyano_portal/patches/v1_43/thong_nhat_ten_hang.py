"""Thống nhất cách hiện mã và tên mặt hàng (chủ đầu tư 13/10/2026).

Quy tắc ở `miyano_portal/ten_hang.py`: Mã → Tên mặt hàng, không cắt tên. Phần
cổng và Desk là code/CSS, không cần patch. Thư "Portal - Đơn xác nhận" liệt kê
từng mặt hàng theo kiểu "Tên (Mã)" — đổi sang "Mã — Tên".
`install_portal_notifications()` BỎ QUA bản ghi đã tồn tại, nên phải ghi đè
`message` của bản ghi đang có ở đây (cùng cách patch v1_40).
"""

import frappe

from miyano_portal.setup.install_notifications import DEFS

THU_CAP_NHAT = ("Portal - Đơn xác nhận",)


def execute():
	for d in DEFS:
		if d["name"] in THU_CAP_NHAT and frappe.db.exists("Notification", d["name"]):
			frappe.db.set_value("Notification", d["name"], "message", d["message"])
