import frappe

DEFS = [
    {
        "name": "Portal - Đơn mới",
        "subject": "Đơn hàng {{ doc.name }} đã được ghi nhận",
        "document_type": "Sales Order",
        "event": "New",
        "condition": "doc.custom_nguon_don == 'Client Portal'",
        "message": "Kính gửi Quý khách,\n\nĐơn hàng {{ doc.name }} đã được ghi nhận và đang chờ Miyano xác nhận.",
    },
    {
        "name": "Portal - Đơn xác nhận",
        "subject": "Đơn hàng {{ doc.name }} đã được xác nhận",
        "document_type": "Sales Order",
        "event": "Submit",
        "condition": "doc.custom_nguon_don == 'Client Portal'",
        "message": "Kính gửi Quý khách,\n\nĐơn hàng {{ doc.name }} đã được Miyano xác nhận và chuyển sang xử lý.",
    },
    {
        "name": "Portal - Đơn bị từ chối",
        "subject": "Đơn hàng {{ doc.name }} đã bị từ chối",
        "document_type": "Sales Order",
        "event": "Value Change",
        "value_changed": "workflow_state",
        "condition": "doc.custom_nguon_don == 'Client Portal' and doc.workflow_state == 'Từ chối'",
        "message": "Kính gửi Quý khách,\n\nĐơn hàng {{ doc.name }} đã bị Miyano từ chối. Vui lòng liên hệ để biết thêm chi tiết.",
    },
    {
        "name": "Portal - Xuất giao",
        "subject": "Hàng đã xuất giao cho phiếu {{ doc.name }}",
        "document_type": "Delivery Note",
        "event": "Submit",
        "condition": "",
        "message": "Kính gửi Quý khách,\n\nĐơn hàng của Quý khách đã được xuất giao theo phiếu giao hàng {{ doc.name }}.",
    },
    {
        "name": "Portal - Hoá đơn phát hành",
        "subject": "Hoá đơn {{ doc.name }} đã được phát hành",
        "document_type": "Sales Invoice",
        "event": "Submit",
        "condition": "",
        "message": "Kính gửi Quý khách,\n\nHoá đơn {{ doc.name }} đã được phát hành. Quý khách có thể xem chi tiết trên cổng khách hàng.",
    },
]


def install_portal_notifications():
    for d in DEFS:
        if frappe.db.exists("Notification", d["name"]):
            continue
        doc = frappe.get_doc({
            "doctype": "Notification",
            "name": d["name"],
            "subject": d["subject"],
            "document_type": d["document_type"],
            "event": d["event"],
            "value_changed": d.get("value_changed"),
            "condition": d["condition"],
            "channel": "Email",
            "recipients": [{"receiver_by_document_field": "contact_email"}],
            "message": d["message"],
            "enabled": 1,
        })
        doc.insert(ignore_permissions=True)
