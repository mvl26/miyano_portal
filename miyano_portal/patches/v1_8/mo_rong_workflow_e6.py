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

review I-4 — SỬA so với bản đầu:
1. `allow_edit` của state "Báo giá hết hạn" đổi "Sales User" -> "System
   Manager": bản đầu để Sales User sửa/Submit được một nháp đã bị job daily
   tự đóng — khách đã nhận email "đơn đã tự động đóng", Sales User vẫn mở
   được đơn hôm sau và bấm Submit thành đơn bán THẬT mà khách chưa từng
   đồng ý (ngược QĐ-6). Không role nào tự ý sửa/submit được nháp đã chết.
2. Thêm transition LỐI RA duy nhất: "Báo giá hết hạn" -> "Mở lại" ->
   "Chờ xác nhận" (Sales Manager) — bản đầu là NGÕ CỤT một chiều, không ai
   đưa được một nháp hết hạn quay lại xử lý nếu khách đổi ý muốn mua.

Idempotent theo NỘI DUNG *và* theo THUỘC TÍNH — không chỉ thêm dòng còn
thiếu mà còn CẬP NHẬT dòng đã tồn tại nếu thuộc tính lệch (site đã chạy bản
đầu của patch này trước khi có bản sửa I-4 sẽ được kéo về đúng cấu hình mới
khi hàm này chạy lại, dù `Patch Log` không tự re-run patch đã ghi nhận —
phải gọi lại `execute()` một lần thủ công trên các site đã lỡ chạy bản cũ).
"""

import frappe

WF = "Sales Order - Client Portal"
STATE_HET_HAN = "Báo giá hết hạn"
ACTION_HET_HAN = "Báo giá hết hạn"
ACTION_MO_LAI = "Mở lại"
STATE_KHACH = "Chờ khách đồng ý"
STATE_CHO_XAC_NHAN = "Chờ xác nhận"
ALLOW_EDIT_HET_HAN = "System Manager"


def execute():
    if not frappe.db.exists("Workflow", WF):
        # Site chưa cài workflow gốc (patch v1_0 chưa chạy) — không có gì để mở rộng.
        return

    if not frappe.db.exists("Workflow State", STATE_HET_HAN):
        frappe.get_doc(
            {"doctype": "Workflow State", "workflow_state_name": STATE_HET_HAN, "style": "Danger"}
        ).insert(ignore_permissions=True)
    for hanh_dong in (ACTION_HET_HAN, ACTION_MO_LAI):
        if not frappe.db.exists("Workflow Action Master", hanh_dong):
            frappe.get_doc(
                {"doctype": "Workflow Action Master", "workflow_action_name": hanh_dong}
            ).insert(ignore_permissions=True)

    wf = frappe.get_doc("Workflow", WF)
    thay_doi = False

    hang = next((s for s in wf.states if s.state == STATE_HET_HAN), None)
    if hang is None:
        wf.append("states", {
            "state": STATE_HET_HAN,
            "doc_status": "0",
            "allow_edit": ALLOW_EDIT_HET_HAN,
        })
        thay_doi = True
    elif hang.allow_edit != ALLOW_EDIT_HET_HAN:
        # review I-4 — CẬP NHẬT dòng đã tồn tại, không chỉ chèn dòng thiếu:
        # site đã chạy bản đầu (allow_edit="Sales User") phải được kéo về
        # đúng cấu hình mới ở đây, không phải một dòng thứ hai song song.
        hang.allow_edit = ALLOW_EDIT_HET_HAN
        thay_doi = True

    # Chuyển được TỪ "Chờ khách đồng ý" bởi System Manager — job daily chạy
    # dưới quyền hệ thống (Administrator), không phải qua phiên khách hay
    # sales, cùng lý do "System Manager" đã dùng cho hai transition
    # đồng ý/không đồng ý ở v1_4/mo_rong_workflow_e2.py.
    dang_co = {(t.state, t.action, t.next_state, t.allowed) for t in wf.transitions}
    can_co = [
        (STATE_KHACH, ACTION_HET_HAN, STATE_HET_HAN, "System Manager"),
        # review I-4 — lối ra: không có cạnh này thì "Báo giá hết hạn" là
        # ngõ cụt, không ai đưa một nháp hết hạn quay lại xử lý được nữa dù
        # khách đổi ý muốn mua.
        (STATE_HET_HAN, ACTION_MO_LAI, STATE_CHO_XAC_NHAN, "Sales Manager"),
    ]
    for moi in can_co:
        if moi not in dang_co:
            wf.append("transitions", {
                "state": moi[0], "action": moi[1], "next_state": moi[2], "allowed": moi[3],
            })
            thay_doi = True

    if thay_doi:
        wf.flags.ignore_permissions = True
        wf.save()
