"""US-E2.2 — email từ chối phải mang ĐÚNG lý do.

`setup/install_notifications.install_portal_notifications()` bỏ qua Notification
đã tồn tại (`continue` ở dòng 50-51), nên sửa DEFS trong file đó KHÔNG có tác
dụng trên site đã cài. Patch này sửa bản ghi tại chỗ.

Idempotent theo NỘI DUNG: chỉ ghi khi message hiện tại chưa chứa placeholder.
Cố ý không đụng `condition`, `event`, `recipients` — bản ghi này đang bật và
đang gửi mail thật, sửa quá tay là làm hỏng một luồng đang chạy.
"""

import frappe

TEN = "Portal - Đơn bị từ chối"

NOI_DUNG = """Kính gửi Quý khách,

Đơn hàng {{ doc.name }} đã bị Miyano từ chối.

Lý do: {{ doc.custom_ly_do_tu_choi }}

Quý khách vui lòng liên hệ nhân viên phụ trách nếu cần trao đổi thêm."""


def execute():
    if not frappe.db.exists("Notification", TEN):
        return
    hien_tai = frappe.db.get_value("Notification", TEN, "message") or ""
    if "custom_ly_do_tu_choi" in hien_tai:
        return
    doc = frappe.get_doc("Notification", TEN)
    doc.message = NOI_DUNG
    doc.flags.ignore_permissions = True
    doc.save()
