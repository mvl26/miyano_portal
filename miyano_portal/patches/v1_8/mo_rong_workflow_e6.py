"""US-E6.5/NL-10.5 — thêm state "Báo giá hết hạn" cho SO nháp bị job daily
tự đóng khi quá hạn hiệu lực báo giá, cùng khuôn với
`v1_4/mo_rong_workflow_e2.py` (mở rộng workflow ĐANG CHẠY, KHÔNG dùng
`setup/install_workflow.install_portal_workflow()` vì hàm đó thoát sớm khi
workflow đã tồn tại).

KHÔNG tái dùng state "Từ chối" có sẵn: "Từ chối" đã gắn với Notification
"Portal - Đơn bị từ chối" (thông điệp "Miyano đã từ chối đơn của bạn") — dùng
lại cho một báo giá tự hết hạn (không ai từ chối cả) sẽ gửi sai thông điệp
cho khách. State riêng giữ đúng ngữ nghĩa và cho phép job daily tự apply
transition mà không đụng nhánh "Đơn bị từ chối" của sales.

Idempotent theo NỘI DUNG — chạy `migrate` bao nhiêu lần cũng không sinh dòng
trùng.
"""

import frappe

WF = "Sales Order - Client Portal"
STATE_HET_HAN = "Báo giá hết hạn"
ACTION_HET_HAN = "Báo giá hết hạn"
STATE_KHACH = "Chờ khách đồng ý"


def execute():
    if not frappe.db.exists("Workflow", WF):
        # Site chưa cài workflow gốc (patch v1_0 chưa chạy) — không có gì để mở rộng.
        return

    if not frappe.db.exists("Workflow State", STATE_HET_HAN):
        frappe.get_doc(
            {"doctype": "Workflow State", "workflow_state_name": STATE_HET_HAN, "style": "Danger"}
        ).insert(ignore_permissions=True)
    if not frappe.db.exists("Workflow Action Master", ACTION_HET_HAN):
        frappe.get_doc(
            {"doctype": "Workflow Action Master", "workflow_action_name": ACTION_HET_HAN}
        ).insert(ignore_permissions=True)

    wf = frappe.get_doc("Workflow", WF)
    thay_doi = False

    if not any(s.state == STATE_HET_HAN for s in wf.states):
        wf.append("states", {
            "state": STATE_HET_HAN,
            "doc_status": "0",
            "allow_edit": "Sales User",
        })
        thay_doi = True

    # Chuyển được TỪ "Chờ khách đồng ý" bởi System Manager — job daily chạy
    # dưới quyền hệ thống (Administrator), không phải qua phiên khách hay
    # sales, cùng lý do "System Manager" đã dùng cho hai transition
    # đồng ý/không đồng ý ở v1_4/mo_rong_workflow_e2.py.
    dang_co = {(t.state, t.action, t.next_state, t.allowed) for t in wf.transitions}
    moi = (STATE_KHACH, ACTION_HET_HAN, STATE_HET_HAN, "System Manager")
    if moi not in dang_co:
        wf.append("transitions", {
            "state": moi[0], "action": moi[1], "next_state": moi[2], "allowed": moi[3],
        })
        thay_doi = True

    if thay_doi:
        wf.flags.ignore_permissions = True
        wf.save()
