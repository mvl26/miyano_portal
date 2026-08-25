import frappe

from miyano_portal.portal_mua_le import LOAI_DON_BAO_GIA

DEFS = [
    {
        # Brief 2026-08-15 (trang thông báo) Phần 1 — CỐ Ý KHÔNG bật
        # `send_system_notification` ở đây: sự kiện "New" xảy ra ĐÚNG lúc
        # khách vừa tự bấm đặt hàng trên cổng — không phải tin gì MỚI với họ
        # (họ vừa làm ra chính sự kiện đó), khác "Đơn xác nhận"/"Đơn bị từ
        # chối"/"Xuất giao"/"Hoá đơn phát hành"/"Báo giá sẵn sàng" bên dưới,
        # đều là việc Miyano LÀM và khách cần được báo. Ba Notification
        # "Portal Item Request" phía dưới cũng giữ nguyên 0 vì lý do khác —
        # xem chú thích tại chỗ.
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
        # Brief 2026-08-15 (trang thông báo) — sự kiện HƯỚNG VỀ KHÁCH: bật kèm
        # System Notification (Notification Log) để hiện trên trang Thông báo
        # cổng, cùng khuôn "Portal - Báo giá sẵn sàng" đã bật từ v1_14. Bản ghi
        # ĐÃ CÀI trên site cần patch riêng cập nhật (`install_portal_notifications()`
        # bỏ qua bản ghi đã tồn tại) — xem `patches/v1_19`.
        "send_system_notification": 1,
    },
    {
        "name": "Portal - Đơn bị từ chối",
        "subject": "Đơn hàng {{ doc.name }} đã bị từ chối",
        "document_type": "Sales Order",
        "event": "Value Change",
        "value_changed": "workflow_state",
        "condition": "doc.custom_nguon_don == 'Client Portal' and doc.workflow_state == 'Từ chối'",
        "message": "Kính gửi Quý khách,\n\nĐơn hàng {{ doc.name }} đã bị Miyano từ chối. Vui lòng liên hệ để biết thêm chi tiết.",
        "send_system_notification": 1,
    },
    {
        "name": "Portal - Xuất giao",
        "subject": "Hàng đã xuất giao cho phiếu {{ doc.name }}",
        "document_type": "Delivery Note",
        "event": "Submit",
        "condition": "",
        "message": "Kính gửi Quý khách,\n\nĐơn hàng của Quý khách đã được xuất giao theo phiếu giao hàng {{ doc.name }}.",
        "send_system_notification": 1,
    },
    {
        "name": "Portal - Hoá đơn phát hành",
        "subject": "Hoá đơn {{ doc.name }} đã được phát hành",
        "document_type": "Sales Invoice",
        "event": "Submit",
        "condition": "",
        "message": "Kính gửi Quý khách,\n\nHoá đơn {{ doc.name }} đã được phát hành. Quý khách có thể xem chi tiết trên cổng khách hàng.",
        "send_system_notification": 1,
    },
    # E6/US-E6.3 — email xác nhận yêu cầu hàng hoá. `Portal Item Request`
    # không có field `contact_email` (không phải doctype ERPNext bán hàng);
    # người nhận là chính field `nguoi_yeu_cau` (email khách gõ lúc gửi yêu
    # cầu) — xem `recipient_field` bên dưới và `install_portal_notifications()`.
    #
    # Brief 2026-08-15 Phần 1 — ba Notification "Portal Item Request" dưới
    # đây CỐ Ý giữ `send_system_notification` mặc định 0, dù hai cái sau là
    # tin Miyano chủ động báo cho khách (đáng lẽ thuộc diện bật): `nguoi_yeu_
    # cau` là một Ô TEXT khách tự gõ khi gửi yêu cầu, KHÔNG đảm bảo trùng
    # tài khoản cổng đang đăng nhập — bật system notification ở đây là nhân
    # rộng đúng điểm giòn mà brief yêu cầu xử lý (contact_email không khớp
    # User), chỉ đổi tên field. Ngoài phạm vi việc thêm nhỏ này.
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
            "cầu {{ doc.name }} ({{ doc.ten_hang }}). Vui lòng liên hệ nhân "
            "viên phụ trách hoặc trả lời email này để cung cấp thêm thông "
            "tin.\n\n{{ doc.phan_hoi or '' }}"
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
        # review I-2 — thêm `custom_loai_don == 'Mua lẻ'`: "hiệu lực báo giá"
        # là khái niệm CHỈ của Mua lẻ (portal_order_track trả `han_hieu_luc:
        # None` cho đơn khác; `portal_bao_gia.quet_bao_gia_het_han` lọc đúng
        # `custom_loai_don: "Mua lẻ"`). Thiếu điều kiện này thì MỌI đơn hợp
        # đồng khung vào "Chờ khách đồng ý" (luồng E2 gốc) cũng gửi kèm một
        # chứng từ đề "BÁO GIÁ / QUOTATION" với "Hiệu lực đến..." mà không
        # job nào thi hành — sai sự thật nghiệp vụ khách đọc được.
        #
        # Task 6 (QĐ-G2b) — chốt này KHÔNG gọi được `portal_mua_le.
        # di_vong_bao_gia()`: `Notification.condition` là một CHUỖI chạy qua
        # `frappe.safe_eval` trên `doc`, không phải mã Python gọi hàm app
        # được. Cùng `portal_bao_gia.quet_bao_gia_het_han` (filter CSDL),
        # đây là lý do vị ngữ kia đọc DẤU ĐÓNG `custom_loai_don` chứ không
        # suy lại từ dòng — xem docstring `di_vong_bao_gia`.
        #
        # Task 7 — chuỗi này KHÔNG gọi được hàm, nhưng nó CHIA ĐƯỢC MỘT TÊN
        # với vị ngữ: `LOAI_DON_BAO_GIA` nội suy vào đây. Không có nó, ngày
        # ai đó đổi giá trị dấu ở `portal_mua_le` thì thông báo "Báo giá sẵn
        # sàng" LẶNG LẼ thôi bắn cho đúng những đơn cần nó.
        "condition": (
            "doc.custom_nguon_don == 'Client Portal' and "
            f"doc.custom_loai_don == '{LOAI_DON_BAO_GIA}' and "
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
        # review I-1 — `attach_print`/`print_format` KHÔNG đặt ở đây nữa.
        # `Notification.print_format` là Link tới `Print Format`, và
        # `Document.insert` chạy `_validate_links()` VÔ ĐIỀU KIỆN — nếu
        # `execute()` của `v1_14.install_bao_gia_san_sang_notification` chạy
        # trên một site đi qua patch này TRƯỚC khi mẫu in "Miyano - Báo giá"
        # tồn tại (mẫu đó chỉ được tạo sau, ở `v1_15.install_print_format_
        # bao_gia`), `doc.insert()` ở dưới ném `LinkValidationError` và
        # `bench migrate` chết giữa chừng. `v1_15.install_print_format_
        # bao_gia` là nơi DUY NHẤT ghi hai field này — nó dùng
        # `frappe.db.set_value` (bỏ qua `_validate_links`), và luôn chạy SAU
        # khi mẫu in đã tồn tại vì tự nó gọi `install_portal_print_formats()`
        # trước khi set. Xem thêm `v1_15.gioi_han_bao_gia_pdf_mua_le` (patch
        # cập nhật `condition` cho bản ghi đã cài trên site, review I-2).
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
