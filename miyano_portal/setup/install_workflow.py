import frappe

WORKFLOW = "Sales Order - Client Portal"


def _ensure_states():
    for s in ["Chờ xác nhận", "Chờ Miyano xác nhận", "Đã xác nhận", "Từ chối"]:
        if not frappe.db.exists("Workflow State", s):
            frappe.get_doc({"doctype": "Workflow State", "workflow_state_name": s, "style": ""}).insert(ignore_permissions=True)
    for a in ["Gửi duyệt", "Xác nhận", "Từ chối"]:
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
        ],
        "transitions": [
            {"state": "Chờ xác nhận", "action": "Gửi duyệt", "next_state": "Chờ Miyano xác nhận", "allowed": "Sales User"},
            {"state": "Chờ Miyano xác nhận", "action": "Xác nhận", "next_state": "Đã xác nhận", "allowed": "Sales User"},
            {"state": "Chờ Miyano xác nhận", "action": "Từ chối", "next_state": "Từ chối", "allowed": "Sales User"},
        ],
    })
    wf.insert(ignore_permissions=True)
    return wf
