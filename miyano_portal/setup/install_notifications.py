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
    # E6/US-E6.3 — email xác nhận yêu cầu hàng hoá. `Portal Item Request`
    # không có field `contact_email` (không phải doctype ERPNext bán hàng);
    # người nhận là chính field `nguoi_yeu_cau` (email khách gõ lúc gửi yêu
    # cầu) — xem `recipient_field` bên dưới và `install_portal_notifications()`.
    {
        "name": "Portal - Yêu cầu hàng hoá đã ghi nhận",
        "subject": "Yêu cầu hàng hoá {{ doc.name }} đã được ghi nhận",
        "document_type": "Portal Item Request",
        "event": "New",
        "condition": "",
        "message": (
            "Kính gửi Quý khách,\n\nYêu cầu hàng hoá {{ doc.name }} "
            "({{ doc.ten_hang }}) đã được ghi nhận. Miyano sẽ phản hồi trong "
            "thời gian SLA quy định."
        ),
        "recipient_field": "nguoi_yeu_cau",
    },
    # BR-Y2 — email PHẢI mang đúng lý do, không phải câu chung chung. Cùng
    # khuôn "Portal - Đơn bị từ chối" ở trên (US-E2.2): message nhúng thẳng
    # field lý do bằng Jinja, không diễn giải lại.
    {
        "name": "Portal - Yêu cầu không đáp ứng được",
        "subject": "Yêu cầu hàng hoá {{ doc.name }} không đáp ứng được",
        "document_type": "Portal Item Request",
        "event": "Value Change",
        "value_changed": "trang_thai",
        "condition": "doc.trang_thai == 'Không đáp ứng được'",
        "message": (
            "Kính gửi Quý khách,\n\nMiyano rất tiếc chưa thể đáp ứng yêu cầu "
            "{{ doc.name }} ({{ doc.ten_hang }}).\n\nLý do: "
            "{{ doc.ly_do_khong_dap_ung }}"
        ),
        "recipient_field": "nguoi_yeu_cau",
    },
    # NL-11.3 — khách nhận email khi Miyano cần thêm thông tin. Việc TRẢ LỜI
    # (comment 2 chiều, tự chuyển "Đang tìm nguồn") nằm ở
    # api/portal.py::portal_yeu_cau_tra_loi; trigger email này độc lập với
    # đường trả lời đó.
    {
        "name": "Portal - Yêu cầu cần thêm thông tin",
        "subject": "Yêu cầu hàng hoá {{ doc.name }} cần bổ sung thông tin",
        "document_type": "Portal Item Request",
        "event": "Value Change",
        "value_changed": "trang_thai",
        "condition": "doc.trang_thai == 'Cần thêm thông tin'",
        "message": (
            "Kính gửi Quý khách,\n\nMiyano cần thêm thông tin để xử lý yêu "
            "cầu {{ doc.name }} ({{ doc.ten_hang }}). Vui lòng xem chi tiết "
            "và phản hồi trên cổng khách hàng.\n\n{{ doc.phan_hoi or '' }}"
        ),
        "recipient_field": "nguoi_yeu_cau",
    },
    # Thiết kế lại mua lẻ §4.6 — khách nhận thông báo NGAY TRÊN đơn khi báo
    # giá sẵn sàng ("Chờ khách đồng ý"), kèm email cùng khuôn Notification
    # đã có (không dựng cơ chế gửi thư riêng). `custom_nguon_don ==
    # 'Client Portal'` — cùng điều kiện scoping "Portal - Đơn mới"/"Portal -
    # Đơn xác nhận" ở trên; transition "Gửi khách duyệt" -> "Chờ khách đồng
    # ý" áp cho MỌI đơn portal (không riêng Mua lẻ, xem
    # patches/v1_4/mo_rong_workflow_e2.py), nên KHÔNG lọc thêm theo
    # `custom_loai_don`.
    #
    # `han_hieu_luc_bao_gia(doc)` — hàm DUY NHẤT tính hạn hiệu lực, đăng ký
    # làm jinja global ở `hooks.py` (`jinja.methods`). KHÔNG tính lại "+N
    # ngày" ngay trong template: N đọc từ `Miyano Portal Settings.
    # hieu_luc_bao_gia_ngay` (mặc định 7 nếu chưa cấu hình) — hardcode số
    # ngày ở đây sẽ lệch với `portal_order_accept`/`portal_order_track`/job
    # daily `quet_bao_gia_het_han` ngay khi ai đó đổi Settings.
    {
        "name": "Portal - Báo giá sẵn sàng",
        "subject": "Báo giá cho đơn hàng {{ doc.name }} đã sẵn sàng",
        "document_type": "Sales Order",
        "event": "Value Change",
        "value_changed": "workflow_state",
        "condition": (
            "doc.custom_nguon_don == 'Client Portal' and "
            "doc.workflow_state == 'Chờ khách đồng ý'"
        ),
        "message": (
            "Kính gửi Quý khách,\n\nMiyano đã gửi báo giá cho đơn hàng "
            "{{ doc.name }}, tổng giá trị {{ frappe.utils.fmt_money(doc.grand_total, "
            "currency='VND') }}.\n\nBáo giá có hiệu lực đến hết ngày "
            "{{ han_hieu_luc_bao_gia(doc).strftime('%d/%m/%Y') }}. Sau thời hạn này, "
            "nếu Quý khách chưa phản hồi, đơn sẽ tự động đóng.\n\nVui lòng đăng nhập "
            "cổng khách hàng để xem chi tiết và xác nhận."
        ),
        "send_system_notification": 1,
        "attach_print": 1,
        "print_format": "Miyano - Báo giá",
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
            "recipients": [
                {"receiver_by_document_field": d.get("recipient_field", "contact_email")}
            ],
            "message": d["message"],
            "enabled": 1,
            # §4.6 — "thông báo trên chính đơn đặt hàng" = system notification
            # (Notification Log) TRÊN CÙNG cơ chế Email, không phải hai luồng
            # gửi riêng. Mặc định 0 cho mọi định nghĩa cũ — hành vi các
            # Notification hiện có KHÔNG đổi.
            "send_system_notification": d.get("send_system_notification", 0),
            "attach_print": d.get("attach_print", 0),
            "print_format": d.get("print_format"),
        })
        doc.insert(ignore_permissions=True)
