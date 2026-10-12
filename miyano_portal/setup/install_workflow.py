import frappe

WORKFLOW = "Sales Order - Client Portal"

# "Chờ khách đồng ý" có mặt NGAY trong định nghĩa gốc (trước đây chỉ do
# `patches/v1_4/mo_rong_workflow_e2.py` thêm) vì cạnh "Chờ Miyano xác nhận" →
# «Gửi khách duyệt» nối vào nó, và Workflow từ chối một cạnh trỏ tới trạng
# thái không khai trong `states`. Các patch mở rộng (v1_4, v1_8, v1_18, v1_41)
# idempotent theo nội dung nên gặp trạng thái / cạnh đã có thì bỏ qua: site
# mới và site nâng cấp kết thúc với CÙNG một workflow.
STATE_KHACH = "Chờ khách đồng ý"


def _ensure_states():
    for s, style in [
        ("Chờ xác nhận", ""), ("Chờ Miyano xác nhận", ""), ("Đã xác nhận", ""),
        ("Từ chối", ""), (STATE_KHACH, "Warning"),
    ]:
        if not frappe.db.exists("Workflow State", s):
            frappe.get_doc({"doctype": "Workflow State", "workflow_state_name": s, "style": style}).insert(ignore_permissions=True)
    for a in ["Gửi duyệt", "Xác nhận", "Từ chối", "Gửi khách duyệt"]:
        if not frappe.db.exists("Workflow Action Master", a):
            frappe.get_doc({"doctype": "Workflow Action Master", "workflow_action_name": a}).insert(ignore_permissions=True)


def install_portal_workflow():
    _ensure_states()
    if frappe.db.exists("Workflow", WORKFLOW):
        return frappe.get_doc("Workflow", WORKFLOW)
    wf = frappe.get_doc({
        "doctype": "Workflow",
        "workflow_name": WORKFLOW,
        "document_type": "Sales Order",
        "is_active": 1,
        "workflow_state_field": "workflow_state",
        "states": [
            {"state": "Chờ xác nhận", "doc_status": "0", "allow_edit": "Sales User"},
            {"state": "Chờ Miyano xác nhận", "doc_status": "0", "allow_edit": "Sales User"},
            {"state": "Đã xác nhận", "doc_status": "1", "allow_edit": "Sales Manager"},
            {"state": "Từ chối", "doc_status": "0", "allow_edit": "Sales Manager"},
            {"state": STATE_KHACH, "doc_status": "0", "allow_edit": "Sales User"},
        ],
        "transitions": [
            {"state": "Chờ xác nhận", "action": "Gửi duyệt", "next_state": "Chờ Miyano xác nhận", "allowed": "Sales User"},
            {"state": "Chờ Miyano xác nhận", "action": "Xác nhận", "next_state": "Đã xác nhận", "allowed": "Sales User"},
            {"state": "Chờ Miyano xác nhận", "action": "Từ chối", "next_state": "Từ chối", "allowed": "Sales User"},
            # Spec 2026-10-09 §5.4 — lối ra của chốt 3: giá bị sửa sau khi khách
            # đồng ý thì gửi khách duyệt lại (cùng cạnh với patch v1_41
            # `mo_rong_workflow`, dành cho site đang chạy).
            {"state": "Chờ Miyano xác nhận", "action": "Gửi khách duyệt", "next_state": STATE_KHACH, "allowed": "Sales User"},
        ],
    })
    wf.insert(ignore_permissions=True)
    return wf
