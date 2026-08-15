"""Việc 2 / brief 2026-08-15 (bao-gia-hai-chieu) — thêm state "Khách huỷ"
cho SO nháp bị chính khách huỷ ở "Chờ khách đồng ý"
(`api/portal.py::portal_order_huy`), cùng khuôn `v1_8/mo_rong_workflow_e6.py`
(mở rộng workflow ĐANG CHẠY, KHÔNG dùng `setup/install_workflow.
install_portal_workflow()` vì hàm đó thoát sớm khi workflow đã tồn tại).

KHÔNG tái dùng state "Từ chối" có sẵn: nó gắn với Notification "Portal -
Đơn bị từ chối" (thông điệp "Miyano đã từ chối đơn của bạn") — dùng lại cho
một đơn CHÍNH KHÁCH tự huỷ sẽ gửi sai thông điệp cho chính người vừa huỷ.
Đúng bài học đã trả giá và ghi lại ở `v1_8/mo_rong_workflow_e6.py` khi tách
"Báo giá hết hạn" khỏi "Từ chối" cho đúng lý do tương tự.

review I-4 của patch trên áp dụng NGAY TỪ ĐẦU ở đây (không đợi round 2):
1. `allow_edit` = "System Manager" — không role nào tự ý sửa/submit được
   một đơn khách đã huỷ (đúng cùng lý do "Báo giá hết hạn" đã sửa: khách
   đã nhận email huỷ, không ai được lặng lẽ hồi sinh đơn qua Submit).
2. Transition LỐI RA duy nhất: "Khách huỷ" -> "Mở lại" -> "Chờ xác nhận"
   (Sales Manager, DÙNG LẠI action "Mở lại" đã có sẵn từ patch trên — cùng
   ý nghĩa "đưa một đơn đã đóng quay lại xử lý") — một trạng thái một
   chiều là ngõ cụt khi khách đổi ý, đúng lỗi review I-4 đã bắt.

Idempotent theo NỘI DUNG *và* THUỘC TÍNH, cùng khuôn `v1_8`: không chỉ thêm
dòng còn thiếu mà còn CẬP NHẬT dòng đã tồn tại nếu thuộc tính lệch.
"""

import frappe

WF = "Sales Order - Client Portal"
STATE_KHACH_HUY = "Khách huỷ"
ACTION_KHACH_HUY = "Khách huỷ"
ACTION_MO_LAI = "Mở lại"
STATE_KHACH = "Chờ khách đồng ý"
STATE_CHO_XAC_NHAN = "Chờ xác nhận"
ALLOW_EDIT_KHACH_HUY = "System Manager"


def execute():
    if not frappe.db.exists("Workflow", WF):
        # Site chưa cài workflow gốc (patch v1_0 chưa chạy) — không có gì để mở rộng.
        return

    if not frappe.db.exists("Workflow State", STATE_KHACH_HUY):
        frappe.get_doc(
            {"doctype": "Workflow State", "workflow_state_name": STATE_KHACH_HUY, "style": "Danger"}
        ).insert(ignore_permissions=True)
    # ACTION_MO_LAI thường ĐÃ tồn tại (tạo bởi v1_8) — `frappe.db.exists`
    # khiến vòng lặp này là no-op cho nó trên site đã chạy v1_8, vẫn liệt kê
    # tường minh để patch này TỰ ĐỦ (chạy được độc lập trên một site giả định
    # không có v1_8, dù thực tế site nào cũng có).
    for hanh_dong in (ACTION_KHACH_HUY, ACTION_MO_LAI):
        if not frappe.db.exists("Workflow Action Master", hanh_dong):
            frappe.get_doc(
                {"doctype": "Workflow Action Master", "workflow_action_name": hanh_dong}
            ).insert(ignore_permissions=True)

    wf = frappe.get_doc("Workflow", WF)
    thay_doi = False

    hang = next((s for s in wf.states if s.state == STATE_KHACH_HUY), None)
    if hang is None:
        wf.append("states", {
            "state": STATE_KHACH_HUY,
            "doc_status": "0",
            "allow_edit": ALLOW_EDIT_KHACH_HUY,
        })
        thay_doi = True
    elif hang.allow_edit != ALLOW_EDIT_KHACH_HUY:
        hang.allow_edit = ALLOW_EDIT_KHACH_HUY
        thay_doi = True

    # Chuyển được TỪ "Chờ khách đồng ý" bởi System Manager — `portal_order_
    # huy` chạy dưới quyền hệ thống qua trò đổi tạm `session.user` (cùng lý
    # do/khuôn với `portal_order_accept`), không phải qua vai trò thật của
    # phiên khách.
    dang_co = {(t.state, t.action, t.next_state, t.allowed) for t in wf.transitions}
    can_co = [
        (STATE_KHACH, ACTION_KHACH_HUY, STATE_KHACH_HUY, "System Manager"),
        # Lối ra — thiếu cạnh này thì "Khách huỷ" là ngõ cụt một chiều.
        (STATE_KHACH_HUY, ACTION_MO_LAI, STATE_CHO_XAC_NHAN, "Sales Manager"),
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
