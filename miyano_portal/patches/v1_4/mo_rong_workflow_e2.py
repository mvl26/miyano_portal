"""US-E2.5 — thêm state "Chờ khách đồng ý" và 4 transition vào workflow ĐANG CHẠY.

KHÔNG dùng `setup/install_workflow.install_portal_workflow()`: hàm đó thoát sớm
khi workflow đã tồn tại (`install_workflow.py:17-18`), nên nó không sửa được gì.

Idempotent theo NỘI DUNG: mỗi state/transition chỉ thêm khi chưa có đúng bộ
khoá của nó, nên chạy `migrate` bao nhiêu lần cũng không sinh dòng trùng.
"""

import frappe

WF = "Sales Order - Client Portal"
STATE_KHACH = "Chờ khách đồng ý"

TRANSITIONS = [
    ("Chờ xác nhận", "Gửi khách duyệt", STATE_KHACH, "Sales User"),
    (STATE_KHACH, "Khách đồng ý", "Chờ Miyano xác nhận", "System Manager"),
    (STATE_KHACH, "Khách không đồng ý", "Chờ xác nhận", "System Manager"),
    ("Chờ Miyano xác nhận", "Xác nhận", "Đã xác nhận", "Sales Manager"),
]


def execute():
    if not frappe.db.exists("Workflow", WF):
        # Site chưa cài workflow gốc (patch v1_0 chưa chạy) — không có gì để mở rộng.
        return

    if not frappe.db.exists("Workflow State", STATE_KHACH):
        frappe.get_doc(
            {"doctype": "Workflow State", "workflow_state_name": STATE_KHACH, "style": "Warning"}
        ).insert(ignore_permissions=True)
    for hanh_dong in ("Gửi khách duyệt", "Khách đồng ý", "Khách không đồng ý"):
        if not frappe.db.exists("Workflow Action Master", hanh_dong):
            frappe.get_doc(
                {"doctype": "Workflow Action Master", "workflow_action_name": hanh_dong}
            ).insert(ignore_permissions=True)

    wf = frappe.get_doc("Workflow", WF)
    thay_doi = False

    if not any(s.state == STATE_KHACH for s in wf.states):
        wf.append("states", {
            "state": STATE_KHACH,
            "doc_status": "0",
            "allow_edit": "Sales User",
        })
        thay_doi = True

    dang_co = {(t.state, t.action, t.next_state, t.allowed) for t in wf.transitions}
    for state, action, next_state, allowed in TRANSITIONS:
        if (state, action, next_state, allowed) not in dang_co:
            wf.append("transitions", {
                "state": state,
                "action": action,
                "next_state": next_state,
                "allowed": allowed,
            })
            thay_doi = True

    if thay_doi:
        wf.flags.ignore_permissions = True
        wf.save()
